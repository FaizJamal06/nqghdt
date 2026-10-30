"""Elexon client against httpx.MockTransport: no network, instant retries."""

from datetime import UTC, date, datetime

import httpx
import pytest

from app.data.elexon_client import BASE_URL, ElexonClient, WindforRow, validate_rows


def client_for(handler: httpx.MockTransport, sleeps: list[float]) -> ElexonClient:
    http = httpx.Client(base_url=BASE_URL, transport=handler)
    return ElexonClient(http, max_retries=3, backoff_s=1.0, pause_s=0.0, sleep=sleeps.append)


def test_retries_5xx_then_succeeds_with_exponential_backoff() -> None:
    responses = iter(
        [httpx.Response(503), httpx.Response(429), httpx.Response(200, json=[{"a": 1}])]
    )
    sleeps: list[float] = []
    c = client_for(httpx.MockTransport(lambda req: next(responses)), sleeps)
    assert c.get_stream("/x", {}) == [{"a": 1}]
    assert sleeps == [1.0, 2.0, 0.0]  # backoff 1s, 2s, then the politeness pause


def test_honours_retry_after_header() -> None:
    responses = iter(
        [httpx.Response(429, headers={"Retry-After": "7"}), httpx.Response(200, json=[])]
    )
    sleeps: list[float] = []
    client_for(httpx.MockTransport(lambda req: next(responses)), sleeps).get_stream("/x", {})
    assert sleeps[0] == 7.0


def test_fails_loudly_after_max_retries() -> None:
    sleeps: list[float] = []
    c = client_for(httpx.MockTransport(lambda req: httpx.Response(503)), sleeps)
    with pytest.raises(httpx.HTTPStatusError):
        c.get_stream("/x", {})
    assert len(sleeps) == 3  # 3 retries, then the 4th failure raises


def test_windfor_chunks_are_daily_and_do_not_overlap() -> None:
    seen: list[tuple[str, str]] = []

    def handler(req: httpx.Request) -> httpx.Response:
        seen.append((req.url.params["publishDateTimeFrom"], req.url.params["publishDateTimeTo"]))
        return httpx.Response(200, json=[])

    c = client_for(httpx.MockTransport(handler), [])
    list(c.fetch_windfor(datetime(2026, 1, 1, tzinfo=UTC), datetime(2026, 1, 3, tzinfo=UTC)))
    assert seen == [
        ("2026-01-01T00:00:00Z", "2026-01-01T23:59:59Z"),
        ("2026-01-02T00:00:00Z", "2026-01-02T23:59:59Z"),
    ]


def test_fuelhh_one_request_per_settlement_date() -> None:
    days: list[str] = []

    def handler(req: httpx.Request) -> httpx.Response:
        assert req.url.params["fuelType"] == "WIND"
        days.append(req.url.params["settlementDateFrom"])
        return httpx.Response(200, json=[])

    list(
        client_for(httpx.MockTransport(handler), []).fetch_fuelhh_wind(
            date(2026, 1, 1), date(2026, 1, 3)
        )
    )
    assert days == ["2026-01-01", "2026-01-02", "2026-01-03"]


def test_validate_rows_skips_and_counts_malformed() -> None:
    raw = [
        {
            "publishTime": "2026-01-01T07:30:00Z",
            "startTime": "2026-01-02T00:00:00Z",
            "generation": 5,
        },
        {"publishTime": "not a time", "startTime": "2026-01-02T00:00:00Z", "generation": 5},
        {
            "publishTime": "2026-01-01T07:30:00Z",
            "startTime": "2026-01-02T01:00:00Z",
            "generation": None,
        },
    ]
    rows, bad = validate_rows(raw, WindforRow)
    assert bad == 1
    assert [r.generation for r in rows] == [5.0, None]  # nulls survive for loaders to count
