"""Which forecast did the trader have? (R2, R3, R8)

Every function here answers one question per delivery startTime: of all the WINDFOR
rows for this hour, which is the latest one published at or before a limit? Only the
limit differs: a D-1 wall-clock cutoff (R2) or "h hours before the period" (R8).
Input frames are the cleaned forecasts from data/loaders.py
(publishTime, startTime, forecast_mw, horizon_h; UTC).
"""

import pandas as pd

from app.core.timeutils import decision_cutoffs

COLUMNS = ["startTime", "publishTime", "forecast_mw", "horizon_h"]


def _latest_before(forecasts: pd.DataFrame, limit: pd.Series) -> pd.DataFrame:
    """Per startTime, the row with the greatest publishTime <= limit (row-aligned UTC).

    Equality is included: a forecast published at exactly 09:20:00 was on the screen
    at the gate. Periods with no eligible row are absent; callers count them (R11).
    """
    eligible = forecasts[forecasts["publishTime"] <= limit]
    latest = eligible.sort_values(["startTime", "publishTime"]).groupby("startTime").tail(1)
    return latest[COLUMNS].reset_index(drop=True)


def select_at_cutoff(forecasts: pd.DataFrame, cutoff_hhmm: str = "09:20") -> pd.DataFrame:
    """R2: per startTime, the latest forecast published <= cutoff_hhmm UK time on D-1.

    D is the UK-local date of the period start (R5). Returns startTime, publishTime,
    forecast_mw (MW), horizon_h (hours), one row per startTime, sorted by startTime.
    """
    return _latest_before(forecasts, decision_cutoffs(forecasts["startTime"], cutoff_hhmm))


def select_at_horizon(forecasts: pd.DataFrame, horizon_h: float) -> pd.DataFrame:
    """R8: per startTime, the latest forecast published <= startTime - horizon_h hours.

    So every selected row has horizon_h >= the requested h. Same output as select_at_cutoff.
    """
    return _latest_before(forecasts, forecasts["startTime"] - pd.Timedelta(hours=horizon_h))


def select_latest_before_delivery(forecasts: pd.DataFrame) -> pd.DataFrame:
    """Comparison only (the "flattering" number): the last forecast before each period.

    Not available at the gate, so never used for the decision view (R3).
    """
    return select_at_horizon(forecasts, 0)


def previous_publish(forecasts: pd.DataFrame, selected: pd.DataFrame) -> pd.DataFrame:
    """Add previous_mw and revision_mw = forecast_mw - previous_mw to selected rows.

    previous_mw comes from the most recent *earlier* publish that covered the same
    startTime. NaN when there is none (the first publish to reach that hour).
    """
    prev = forecasts[["startTime", "publishTime", "forecast_mw"]].rename(
        columns={"publishTime": "prev_publish", "forecast_mw": "previous_mw"}
    )
    out = pd.merge_asof(
        selected.sort_values("publishTime"),
        prev.sort_values("prev_publish"),
        left_on="publishTime",
        right_on="prev_publish",
        by="startTime",
        allow_exact_matches=False,  # strictly before the selected publish
    )
    out["revision_mw"] = out["forecast_mw"] - out["previous_mw"]
    return out.drop(columns="prev_publish").sort_values("startTime").reset_index(drop=True)
