"""API contract tests on the committed snapshot: 200 + schema on valid params, 422 on bad ones.

response_model validates every 200 body against schemas.py, so a 200 here means the
contract held. Value checks pin the worked examples from the study notes.
"""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(create_app(Settings(static_dir=Path("does-not-exist"))))


def test_health(client: TestClient) -> None:
    assert client.get("/api/health").json() == {"status": "ok"}


@pytest.mark.parametrize(
    "url",
    [
        "/api/meta",
        "/api/decision?date=2026-01-02",
        "/api/decision?date=2026-02-01&mode=horizon&horizon_h=40&band=0.5",
        "/api/accuracy",
        "/api/accuracy?mode=horizon&horizon_h=2",
        "/api/calibration?cutoff=15:30",
        "/api/planner",
        "/api/planner?c_short=3&c_long=1&date=2026-01-21",
        "/api/planner?price_short=200&price_long=60",
        "/api/timeseries",
    ],
)
def test_valid_requests_return_200(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 200


@pytest.mark.parametrize(
    "url",
    [
        "/api/decision",  # date is required
        "/api/decision?date=2026-01-01",  # outside the delivery window (R4)
        "/api/decision?date=2026-01-21&band=0.7",  # not one of 0.5 / 0.8 / 0.9
        "/api/accuracy?cutoff=9:20",  # must be HH:MM
        "/api/accuracy?cutoff=24:00",
        "/api/accuracy?mode=horizon&horizon_h=41",  # capped at 40 h (DECISIONS #22)
        "/api/accuracy?mode=sideways",
        "/api/planner?confidence=0.99",  # capped at 0.95 (DECISIONS #3)
        "/api/planner?c_short=3",  # needs both parts of the ratio
        "/api/planner?price_short=-1&price_long=60",
    ],
)
def test_bad_params_return_422(client: TestClient, url: str) -> None:
    assert client.get(url).status_code == 422


def test_decision_worked_example(client: TestClient) -> None:
    """21 Jan 17:00 (M2 note): first test day, 07:30 publish, proportional centre."""
    d = client.get("/api/decision?date=2026-01-21").json()
    assert d["sample"] == "out-of-sample"
    assert d["cutoff_utc"] == "2026-01-20T09:20:00Z"
    assert d["freshness"] == {
        "latest_publish": "2026-01-20T07:30:00Z",
        "minutes_before_cutoff": 110.0,
        "is_stale": False,
    }
    p = next(p for p in d["periods"] if p["local_time"] == "17:00")
    assert (p["sp"], p["forecast_mw"], p["horizon_h"]) == (35, 20918.0, 33.5)
    assert round(p["centre_mw"]) == 18094
    assert (round(p["band_low_mw"]), round(p["band_high_mw"])) == (15160, 19738)
    assert round(p["planned_mw"]) == 16273
    assert p["actual_mw"] == 16530.5
    assert d["coverage"] == {"expected": 24, "with_forecast": 24, "with_actual": 24}


def test_in_sample_badge_and_horizon_mode_has_no_cutoff(client: TestClient) -> None:
    assert client.get("/api/decision?date=2026-01-20").json()["sample"] == "in-sample"
    h = client.get("/api/decision?date=2026-01-20&mode=horizon&horizon_h=6").json()
    assert h["cutoff_utc"] is None and h["freshness"] is None
    assert min(p["horizon_h"] for p in h["periods"]) >= 6  # R8


def test_accuracy_headline_and_tables(client: TestClient) -> None:
    a = client.get("/api/accuracy").json()
    assert a["summary"]["n"] == 744 and a["summary"]["n_days"] == 31
    assert round(a["summary"]["mae"]) == 2039 and round(a["summary"]["bias"]) == -1748
    assert [r["key"] for r in a["breakdowns"]["by_hour"]][:3] == ["00:00", "01:00", "02:00"]
    assert [r["key"] for r in a["breakdowns"]["by_level"]] == ["low", "mid", "high"]
    assert [r["name"] for r in a["value_of_waiting"]] == ["09:20", "09:50", "15:30"]
    assert len(a["lead_time"]) == 40
    assert sum(b["count"] for b in a["histogram"]) == 744


def test_planner_alpha_sources(client: TestClient) -> None:
    assert client.get("/api/planner").json()["alpha"] == 0.2
    ratio = client.get("/api/planner?c_short=3&c_long=1").json()
    assert (ratio["alpha"], ratio["alpha_source"]) == (0.25, "cost_ratio")
    priced = client.get("/api/planner?price_short=300&price_long=100").json()
    assert priced["alpha_source"] == "prices"
    assert all(p["cost_gbp"] is not None for p in priced["policies"])


def test_warm_responses_are_fast(client: TestClient) -> None:
    """PRD §8: < 300 ms warm. Generous margin for CI runners."""
    for url in ("/api/decision?date=2026-01-21", "/api/accuracy", "/api/calibration"):
        client.get(url)
        t = time.perf_counter()
        client.get(url)
        assert time.perf_counter() - t < 0.3


def test_spa_fallback_and_api_404(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("shell")
    (tmp_path / "app.js").write_text("js")
    (tmp_path.parent / "secret.txt").write_text("nope")
    client = TestClient(create_app(Settings(static_dir=tmp_path)))

    assert client.get("/app.js").text == "js"
    assert client.get("/decision/2026-01-15").text == "shell"  # deep link -> SPA
    assert client.get("/api/nope").status_code == 404  # never the SPA shell
    assert client.get("/..%2Fsecret.txt").text == "shell"  # traversal blocked
