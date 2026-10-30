"""Join selected forecasts to actuals: the "scored frame" every metric is computed on.

WINDFOR is hourly in January (data finding, DECISIONS #19), FUELHH half-hourly.
MW is a rate, so an hour's actual is the *mean* of its two half-hours, not the sum.
Missing data is excluded and counted, never filled (R11).
"""

from datetime import date, timedelta

import pandas as pd

from app.core.timeutils import UK, delivery_date, settlement_period

SCORED_COLUMNS = [
    "startTime",
    "delivery_date",
    "hour_uk",
    "sp",
    "publishTime",
    "horizon_h",
    "forecast_mw",
    "actual_mw",
    "error_mw",
    "dt_h",
]


def expected_starts(first: date, last: date, resolution_min: int) -> pd.DatetimeIndex:
    """Every period start (UTC) of UK delivery days first..last, inclusive.

    Built on the local clock, so a clock-change day has 23 or 25 hours.
    """
    start = pd.Timestamp(first).tz_localize(UK)
    end = pd.Timestamp(last + timedelta(days=1)).tz_localize(UK)
    idx = pd.date_range(start, end, freq=f"{resolution_min}min", inclusive="left")
    return idx.tz_convert("UTC")


def to_resolution(actuals: pd.DataFrame, resolution_min: int) -> pd.DataFrame:
    """Actuals on the forecast's grid -> (startTime, actual_mw).

    30 min: unchanged. 60 min: mean of the two half-hours of each hour; an hour with
    only one half-hour is dropped (its mean would be biased) and so shows up in
    score()'s missing_actual count (R11).
    """
    if resolution_min == 30:
        return actuals[["startTime", "actual_mw"]].copy()
    hourly = actuals.groupby(actuals["startTime"].dt.floor("h"))["actual_mw"].agg(["mean", "count"])
    complete = hourly.loc[hourly["count"] == 2, "mean"]
    return complete.rename("actual_mw").rename_axis("startTime").reset_index()


def score(
    selected: pd.DataFrame,
    actuals: pd.DataFrame,
    resolution_min: int,
    first: date,
    last: date,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Scored frame for delivery days first..last, plus a coverage report.

    selected: one row per startTime from core/selection.py. actuals: cleaned FUELHH.
    Output columns (SCORED_COLUMNS): UTC times, UK date/hour, SP, MW values,
    error_mw = actual_mw - forecast_mw (R7: negative = desk short), dt_h in hours.
    Coverage: expected periods, scored, missing_forecast, missing_actual.
    """
    expected = expected_starts(first, last, resolution_min)
    actual = to_resolution(actuals, resolution_min)
    in_window = selected[selected["startTime"].isin(expected)]
    df = in_window.merge(actual, on="startTime", how="inner")

    df["delivery_date"] = delivery_date(df["startTime"])
    df["hour_uk"] = df["startTime"].dt.tz_convert(UK).dt.hour
    df["sp"] = settlement_period(df["startTime"])
    df["error_mw"] = df["actual_mw"] - df["forecast_mw"]
    df["dt_h"] = resolution_min / 60
    coverage = {
        "expected": len(expected),
        "scored": len(df),
        "missing_forecast": len(expected) - len(in_window),
        "missing_actual": len(in_window) - len(df),
    }
    return df[SCORED_COLUMNS].sort_values("startTime").reset_index(drop=True), coverage
