"""FastAPI app factory. Serves /api and, when built, the React app from one process."""

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api.routes import meta
from app.config import Settings


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the app. Tests pass their own Settings (e.g. a temp static_dir).

    No CORS middleware: in dev Vite proxies /api, in production the API and the
    React build share one origin, so the browser never makes a cross-origin call.
    """
    settings = settings or Settings()
    app = FastAPI(title="WindDesk API", version="0.1.0")
    app.include_router(meta.router, prefix="/api")

    if settings.static_dir.is_dir():
        _mount_spa(app, settings.static_dir.resolve())
    return app


def _mount_spa(app: FastAPI, static_dir: Path) -> None:
    """Serve built files, falling back to index.html so client-side routes
    like /decision/2026-01-15 survive a page refresh."""

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str) -> FileResponse:
        # Unknown API routes must stay 404 (PRD §8), not turn into the SPA shell.
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404)
        file = (static_dir / path).resolve()
        # is_relative_to blocks ../ traversal out of the static dir.
        if path and file.is_file() and file.is_relative_to(static_dir):
            return FileResponse(file)
        return FileResponse(static_dir / "index.html")


app = create_app()
