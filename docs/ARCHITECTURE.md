# Architecture

_Status: M1 (data layer + snapshot). Updated after every milestone._

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

## Current endpoints
| Route | File |
|---|---|
| `GET /api/health` | `backend/app/api/routes/meta.py` |
| `GET /docs` | FastAPI built-in |
