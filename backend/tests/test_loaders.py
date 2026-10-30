"""Cleaning rules from PRD §4 / §10, on fixtures small enough to check by hand."""

import pandas as pd
import pytest

from app.data.loaders import clean_actuals, clean_forecasts, detect_resolution_min


def fuel(rows: list[tuple[str, str, str, float | None]]) -> pd.DataFrame:
    """rows = (startTime, publishTime, fuelType, generation)."""
    return pd.DataFrame(
        [
            {
                "startTime": s,
                "publishTime": p,
                "settlementDate": "2026-01-02",
                "settlementPeriod": 1,
                "fuelType": ft,
                "generation": g,
            }
            for s, p, ft, g in rows
        ]
    )


def windfor(rows: list[tuple[str, str, float | None]]) -> pd.DataFrame:
    """rows = (publishTime, startTime, generation)."""
    return pd.DataFrame(rows, columns=["publishTime", "startTime", "generation"])


def test_actuals_keep_latest_revision_drop_nulls_and_non_wind() -> None:
    raw = fuel(
        [
            ("2026-01-02T00:00Z", "2026-01-02T00:30Z", "WIND", 100.0),
            ("2026-01-02T00:00Z", "2026-01-02T05:00Z", "WIND", 120.0),  # revision: wins
            ("2026-01-02T00:30Z", "2026-01-02T01:00Z", "WIND", None),  # null: dropped
            ("2026-01-02T00:30Z", "2026-01-02T01:00Z", "CCGT", 9999.0),  # not wind
        ]
    )
    out, counts = clean_actuals(raw)
    assert out["actual_mw"].tolist() == [120.0]
    assert counts == {
        "rows_in": 4,
        "non_wind": 1,
        "null_generation": 1,
        "revised_duplicates": 1,
        "rows_out": 1,
    }
    assert str(out["startTime"].dt.tz) == "UTC"


def test_forecasts_dedupe_nulls_past_rows_and_horizon() -> None:
    raw = windfor(
        [
            ("2026-01-01T07:30Z", "2026-01-01T06:00Z", 50.0),  # start before publish: dropped
            ("2026-01-01T07:30Z", "2026-01-01T07:30Z", 60.0),  # horizon 0: kept
            ("2026-01-01T07:30Z", "2026-01-02T00:00Z", 70.0),
            ("2026-01-01T07:30Z", "2026-01-02T00:00Z", 75.0),  # duplicate: last wins
            ("2026-01-01T07:30Z", "2026-01-02T01:00Z", None),  # null: dropped
        ]
    )
    out, counts = clean_forecasts(raw)
    assert out["forecast_mw"].tolist() == [60.0, 75.0]
    assert out["horizon_h"].tolist() == [0.0, 16.5]  # 07:30 -> 00:00 next day = 16.5 h
    assert counts == {
        "rows_in": 5,
        "null_generation": 1,
        "duplicates": 1,
        "start_before_publish": 1,
        "rows_out": 2,
    }


@pytest.mark.parametrize("freq,expected", [("60min", 60), ("30min", 30)])
def test_detect_resolution(freq: str, expected: int) -> None:
    starts = pd.date_range("2026-01-02", periods=6, freq=freq, tz="UTC")
    df = pd.DataFrame({"publishTime": pd.Timestamp("2026-01-01T07:30Z"), "startTime": starts})
    assert detect_resolution_min(df) == expected


def test_detect_resolution_rejects_other_spacing() -> None:
    starts = pd.date_range("2026-01-02", periods=4, freq="15min", tz="UTC")
    df = pd.DataFrame({"publishTime": pd.Timestamp("2026-01-01T07:30Z"), "startTime": starts})
    with pytest.raises(ValueError, match="15 min"):
        detect_resolution_min(df)
