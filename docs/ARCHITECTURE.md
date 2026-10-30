# Architecture

_Status: M2 (core analytics). Updated after every milestone._

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

`backend/app/report.py` (`python -m app.report`) composes these and prints the January summary. `scored_for()` there is what the M3 `DataStore` will cache.

## Current endpoints
| Route | File |
|---|---|
| `GET /api/health` | `backend/app/api/routes/meta.py` |
| `GET /docs` | FastAPI built-in |
