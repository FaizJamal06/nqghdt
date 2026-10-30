"""API smoke + contract tests. Endpoint coverage grows in M3."""

from pathlib import Path

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


def test_health() -> None:
    client = TestClient(create_app(Settings(static_dir=Path("does-not-exist"))))
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_spa_fallback_and_api_404(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("shell")
    (tmp_path / "app.js").write_text("js")
    (tmp_path.parent / "secret.txt").write_text("nope")
    client = TestClient(create_app(Settings(static_dir=tmp_path)))

    assert client.get("/app.js").text == "js"
    assert client.get("/decision/2026-01-15").text == "shell"  # deep link -> SPA
    assert client.get("/api/nope").status_code == 404  # never the SPA shell
    assert client.get("/..%2Fsecret.txt").text == "shell"  # traversal blocked
