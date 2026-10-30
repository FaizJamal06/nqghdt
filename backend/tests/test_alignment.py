"""Joining forecasts to actuals: hourly averaging, coverage counts, clock-change days."""

from datetime import date

import pandas as pd
import pytest

from app.core.alignment import expected_starts, score, train_test_split

DAY = date(2026, 1, 2)


def actuals(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """rows = (startTime, actual_mw) half-hours."""
    df = pd.DataFrame(rows, columns=["startTime", "actual_mw"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    return df


def selected(rows: list[tuple[str, float]]) -> pd.DataFrame:
    """rows = (startTime, forecast_mw), all from one 07:30 D-1 publish."""
    df = pd.DataFrame(rows, columns=["startTime", "forecast_mw"])
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.Timestamp("2026-01-01T07:30Z")
    df["horizon_h"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    return df


def test_hourly_forecast_vs_mean_of_two_half_hours() -> None:
    sel = selected([("2026-01-02T00:00Z", 200.0), ("2026-01-02T01:00Z", 200.0)])
    act = actuals(
        [
            ("2026-01-02T00:00Z", 100.0),
            ("2026-01-02T00:30Z", 200.0),  # hour 00:00 -> mean 150, not sum 300
            ("2026-01-02T01:00Z", 999.0),  # hour 01:00 has one half-hour only: excluded
        ]
    )
    out, cov = score(sel, act, 60, DAY, DAY)
    assert out[["actual_mw", "error_mw", "dt_h"]].iloc[0].tolist() == [150.0, -50.0, 1.0]
    assert cov == {"expected": 24, "scored": 1, "missing_forecast": 22, "missing_actual": 1}


def test_half_hourly_join_and_columns() -> None:
    sel = selected([("2026-01-02T17:30Z", 80.0)])
    out, cov = score(sel, actuals([("2026-01-02T17:30Z", 100.0)]), 30, DAY, DAY)
    row = out.iloc[0]
    assert (row["sp"], row["hour_uk"], row["error_mw"], row["dt_h"]) == (36, 17, 20.0, 0.5)
    assert row["delivery_date"] == DAY
    assert cov["expected"] == 48


def test_forecasts_outside_the_window_are_ignored() -> None:
    sel = selected([("2026-01-03T00:00Z", 1.0)])  # next day, outside DAY..DAY
    _, cov = score(sel, actuals([("2026-01-03T00:00Z", 1.0)]), 30, DAY, DAY)
    assert cov["scored"] == 0 and cov["missing_forecast"] == 48


def test_train_holds_only_actuals_known_at_the_first_test_decision() -> None:
    starts = pd.Series(
        pd.to_datetime(["2026-01-20T08:00Z", "2026-01-20T09:00Z", "2026-01-21T00:00Z"])
    )
    scored = pd.DataFrame({"startTime": starts, "delivery_date": starts.dt.date})
    train, test = train_test_split(scored, date(2026, 1, 20), "09:00")
    # 08:00 is known by 09:00; 09:00-23:00 on 20 Jan is in neither set; 21 Jan is test
    assert train["startTime"].tolist() == [starts[0]]
    assert test["startTime"].tolist() == [starts[2]]


@pytest.mark.parametrize("day,hours", [(date(2026, 3, 29), 23), (date(2026, 10, 25), 25)])
def test_expected_periods_on_clock_change_days(day: date, hours: int) -> None:
    assert len(expected_starts(day, day, 60)) == hours
    assert len(expected_starts(day, day, 30)) == hours * 2
