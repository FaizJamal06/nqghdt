# Architecture

_Status: M0 scaffold. Updated after every milestone._

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

## Current endpoints
| Route | File |
|---|---|
| `GET /api/health` | `backend/app/api/routes/meta.py` |
| `GET /docs` | FastAPI built-in |
