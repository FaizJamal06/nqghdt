# WindDesk

A day-ahead planning aid for a UK wind trading desk. For each delivery day it shows the national wind forecast the trader actually had at the 09:20 gate (Elexon WINDFOR), how wrong that forecast has been (Elexon FUELHH actuals), and how much wind to plan on for a chosen confidence. January 2026 data, no look-ahead.

**Live app:** https://nqghdt.vercel.app (API docs: https://nqghdt.vercel.app/docs)

## How to run

**Docker** (the whole app, one container):

```bash
docker compose up --build
```

Then open http://localhost:8080.

**Dev mode without Docker** (two terminals; Vite proxies `/api` to port 8000):

```bash
# terminal 1, from backend/ (Python 3.12, deps from ../requirements-dev.txt)
python -m uvicorn app.main:app --reload --port 8000
# terminal 2, from frontend/
npm install
npm run dev        # http://localhost:5173
```

**Refresh the data** (January 2026 is history, so the snapshot in `data/raw/` is committed):

```bash
cd backend
python -m app.data.ingest           # fetch from Elexon and overwrite
python -m app.data.ingest --check   # report coverage of what is on disk
```

**Tests:** `scripts/check` (Git Bash) runs exactly what CI runs and stops at the first failure: ruff, pytest, frontend lint and build. Timing checks are kept out of CI: `pytest -m perf`, or `python -m app.report` for warm response times.

## Deployment

The app runs on **Vercel's Container runtime (beta)**: Vercel builds the root `Dockerfile` as a Container project and the server listens on `$PORT` (8000). `Dockerfile.vercel` is an identical copy, because Vercel's docs say it makes the Container preset win over the frameworks it detects in `backend/` and `frontend/`; CI fails if the two differ. One image serves the React build and the FastAPI `/api`, the same as local Docker.

The container scales to zero after about 5 minutes without traffic, so **the first load after an idle spell may take a few seconds**. Later requests are fast.
