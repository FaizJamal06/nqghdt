# Architecture

_Status: M5 (all five pages: Overview, Decision View, Forecast Trust, Buffer Planner, Methodology). Updated after every milestone._

```
            offline, once                         runtime (one container / one process)
┌──────────────────────────────┐      ┌────────────────────────────────────────────────┐
│ python -m app.data.ingest    │      │ FastAPI (backend/app/main.py)                   │
│ Elexon FUELHH + WINDFOR  ────┼─────►│  api/   thin routes, pydantic contracts          │
│ → data/raw/*.csv.gz (git)    │      │  core/  pure pandas functions (analytics)        │
└──────────────────────────────┘      │  data/  load + clean the committed snapshot      │
                                      │  /*     React build (SPA fallback to index.html) │
                                      └────────────────────────────────────────────────┘
```

- **One process serves everything.** The root `Dockerfile` builds the React app in a Node stage and copies only `dist/` into a `python:3.12-slim` image. FastAPI serves `/api/*` and the static files on the same origin, so no CORS is needed.
- **Dev mode:** `uvicorn` on :8000 plus `npm run dev` on :5173. Vite proxies `/api` to :8000.
- **Config:** `backend/app/config.py` (pydantic-settings). Paths can be overridden by env vars (`DATA_DIR`, `STATIC_DIR`, `PORT` in Docker).

## Data layer (`backend/app/data/`)

| File | Job |
|---|---|
| `elexon_client.py` | `ElexonClient`: one-day chunked GETs with retries on 429/5xx (exponential backoff, honours `Retry-After`), raising after N tries. Pydantic row models plus `validate_rows`, which skips and counts malformed rows. |
| `ingest.py` | CLI. `python -m app.data.ingest` fetches and writes `data/raw/{fuelhh_wind,windfor}.csv.gz` + `manifest.json`. The gzip files are deterministic (`mtime=0`), so re-runs give identical bytes. `--check` prints cleaning counts, resolution and per-day coverage. |
| `loaders.py` | `load_snapshot()` reads the CSVs, then the pure `clean_actuals` / `clean_forecasts` count every dropped row. `detect_resolution_min` returns 30 or 60. |
| `store.py` | `DataStore`: the snapshot plus bounded LRU caches per mode key (`("cutoff","09:20")` / `("horizon",24.0)`): selection, scored frame, fitted correction + bands; cached lead-time curve and value-of-waiting table; `day_frame()` for one delivery day. Built and warmed once in `create_app()`. |

Snapshot (committed): 116 KB in total. FUELHH 1,584 half-hours; WINDFOR 19,856 rows → 15,775 after cleaning, hourly resolution.

## Core layer (`backend/app/core/`): pure functions, no I/O

One request's numbers flow through these in order:

```
forecasts ─► selection ─► alignment.score ─► scored frame ─► metrics
                                   actuals ─┘        │
                                                     └► correction (centre_mw) ─► bands ─► planner
```

| File | Job |
|---|---|
| `timeutils.py` | UK-local rules on UTC data: delivery date (R5), DST-safe D-1 cutoff (R1), settlement period. |
| `selection.py` | One forecast row per hour: latest `publishTime ≤` D-1 cutoff (R2) or `≤ startTime − h` (R8). Previous publish → revision. |
| `alignment.py` | Hourly mean of the two FUELHH half-hours, join, `error_mw = actual − forecast` (R7), coverage counts (R11). |
| `metrics.py` | MAE/RMSE/bias, quantiles, exceedance, breakdowns, worst misses, same-period comparisons, actual ÷ forecast by level. |
| `correction.py` | raw / constant / linear / proportional post-processing; output `centre_mw`. Reads only the forecast (guarded). Fitted, like the bands, on `alignment.train_test_split`'s train rows: only actuals known at the first test decision. |
| `bands.py` | Train residuals per cell (supports horizon × level; config uses 3 wind-level cells), fallback horizon → pooled, quantiles on demand, PICP + by-day bootstrap. |
| `planner.py` | Newsvendor alpha (R9), planned wind = centre + residual quantile (≥ 0, R10), policy backtest in MWh (and £). |
| `decision.py` | One delivery day: band, planned wind, flags (`low_wind`; `big_revision` = abs(revision) ≥ `revision_flag_mw`, 1,000 MW), freshness from the cutoff, day and peak-block MWh totals (plus hindsight: actual, trusting WINDFOR, following the plan). |

`backend/app/report.py` (`python -m app.report`) prints the January summary through the same `DataStore` the API uses.

## API layer (`backend/app/api/`): validate → call → serialise

`deps.py` holds the shared query parameters (422 on bad input), the `Store` dependency and `records()` (DataFrame → JSON rows, NaN → null). Each route file is one page of the UI and stays under ~25 lines of logic. Every response is validated against `backend/app/schemas.py`.

| Route | File | Page | Key params |
|---|---|---|---|
| `GET /api/health` | `routes/meta.py` | — | — |
| `GET /api/meta` | `routes/meta.py` | all (startup) | — |
| `GET /api/decision` | `routes/decision.py` | Decision View | `date` (required), mode, `confidence`, `band` 0.5/0.8/0.9 |
| `GET /api/accuracy` | `routes/accuracy.py` | Forecast Trust | mode |
| `GET /api/calibration` | `routes/calibration.py` | Forecast Trust, Methodology | mode |
| `GET /api/planner` | `routes/planner.py` | Buffer Planner | `confidence` or `c_short`+`c_long` or `price_short`+`price_long`; optional `date` |
| `GET /api/timeseries` | `routes/timeseries.py` | Overview | mode |
| `GET /docs` | FastAPI built-in | live API docs | — |

Mode params everywhere: `mode=cutoff|horizon`, `cutoff=HH:MM` (default 09:20), `horizon_h` 0–40 (default 24).

### One request, end to end: `GET /api/decision?date=2026-01-21`

1. `deps.get_mode` validates `cutoff`/`mode`/`horizon_h` and builds the key `("cutoff", "09:20")`; `check_date` checks 21 Jan is in the window.
2. `store.fitted(key)`: already cached at startup (selection → scored frame → leak-free split → proportional correction → 3 level cells).
3. `store.day_frame(key, 21 Jan)`: that day's 24 selected rows (all from the 20 Jan 07:30 publish) with `centre_mw`, SP, local time and actuals.
4. `core.decision.day_periods`: band (P10–P90 of the cell's residuals around the centre), planned wind (P20 at 80% confidence), flags. `freshness`: 07:30 publish, 110 min before the 09:20 cutoff, not stale. `day_totals`: MWh.
5. `records()` → `DecisionResponse` validates the shape → JSON. Warm: ~25 ms.

## Frontend (`frontend/src/`)

React 18 + TypeScript strict + Vite, Tailwind, TanStack Query (fetch + cache), Recharts, react-router 7.

| File | Job |
|---|---|
| `main.tsx`, `App.tsx` | Router, layout (header nav + settings bar), query client |
| `state/settings.ts` | Global settings **in the URL query string** (`cutoff`, `mode`, `h`, `conf`, `cs`/`cl`): shareable, survive refresh, no extra context provider. `modeParams()`, `effectiveConfidence()` (cost ratio → confidence, R9) |
| `api/types.ts`, `api/client.ts` | TS mirror of `schemas.py`; typed `get()`; one query hook per endpoint. Cached forever (the January data never changes) |
| `components/SettingsBar.tsx` | Gate closure / fixed horizon, cutoff presets + custom, confidence slider or cost ratio |
| `components/charts/DecisionChart.tsx` | 80% range (fill), expected (solid), **plan on** (accent, boldest), WINDFOR (thin grey dashed), actual only when toggled; plain-words legend |
| `components/charts/MonthChart.tsx` | Overview: forecast at the gate vs actual, shortfalls shaded |
| `pages/Overview.tsx` | 4 KPI tiles (with n), one January chart, 4 sentences generated from `/api/accuracy` (the problem) and `/api/planner` (the solution, test days) |
| `pages/DecisionView.tsx` | Day picker (default 21 Jan), in/out-of-sample badge, freshness, hover-driven sentence ("Based on 2–20 Jan…", range from `/api/meta`), risky hours, MWh totals, period table; fewer axis labels below 640 px (`lib/useNarrow.ts`) |
| `pages/ForecastTrust.tsx` + `charts/TrustCharts.tsx` | KPI tiles; error vs lead time; honest vs flattering; value of waiting; error by hour and by wind level (+ bias diagnosis); histogram with P10/P90; band coverage (train/test, by-day range); correction candidates; 10 worst misses. Every takeaway sentence generated |
| `pages/BufferPlanner.tsx` | Uses the global confidence / cost-ratio dial; one-sentence alpha explanation; headline backtest sentence; policy table with "yours" highlighted; optional £/MWh (empty by default, "your assumption") |
| `pages/Methodology.tsx` | Data, cutoff rule, sign convention, metrics, why not MAPE, correction/bands/plan, limitations; data-dependent numbers from `/api/meta` + `/api/calibration` |
| `components/ChartCard.tsx` | Card = title + generated note + chart + "Show as table" twin (no value reachable by hover only) |

Dev: `npm run dev` on :5173 proxies `/api` to uvicorn on :8000. Production: `npm run build` → `frontend/dist`, served by FastAPI on the same origin.
