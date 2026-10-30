"""Decision View for one delivery day (PRD §8 "decision period object").

Pure functions on one day's selected rows (with centre_mw, previous_mw, revision_mw;
actual_mw/error_mw may be NaN). Everything here uses only what the trader had at the
gate, except actual_mw/error_mw, which the UI hides until "Show what happened" (R3).
"""

import pandas as pd

from app.core.bands import BandModel, assign_bins, band
from app.core.planner import planned_wind


def day_periods(
    frame: pd.DataFrame, model: BandModel, central: float, alpha: float, revision_flag_mw: float
) -> pd.DataFrame:
    """Add band_low_mw / band_high_mw (central band), planned_mw (alpha) and flags.

    Flags (PRD §8): low_wind = forecast in the lowest level cell; big_revision =
    |revision vs previous publish| >= revision_flag_mw (absolute, so a calm day can
    flag nothing; DECISIONS #60). No wide_band flag: with 3 level cells band width has
    only 3 values, so it just repeated "high wind" (DECISIONS #44, #52).
    """
    out = frame.join(band(model, frame, central))
    out["planned_mw"] = planned_wind(model, frame, alpha)
    flags = pd.DataFrame(
        {
            "low_wind": assign_bins(frame, model)["level_bin"] == 0,
            "big_revision": out["revision_mw"].abs() >= revision_flag_mw,  # NaN -> False
        }
    )
    out["flags"] = [[name for name in flags.columns if row[name]] for _, row in flags.iterrows()]
    return out


def freshness(
    publish_times: pd.Series, cutoff_utc: pd.Timestamp, stale_factor: float = 2
) -> dict[str, object]:
    """Latest publish at the cutoff, its age in minutes, and whether it is stale.

    Stale = older than stale_factor x the median gap between publishes (PRD §10),
    measured from the cutoff (DECISIONS #5). January: 3 h median, so stale > 6 h.
    """
    pubs = publish_times.sort_values()
    latest = pubs[pubs <= cutoff_utc].max()
    age = cutoff_utc - latest
    return {
        "latest_publish": latest,
        "minutes_before_cutoff": age.total_seconds() / 60,
        "is_stale": bool(age > stale_factor * pubs.diff().median()),
    }


def day_totals(periods: pd.DataFrame, peak_hours: tuple[int, int]) -> dict[str, float | None]:
    """Energy totals for the day in MWh (MW x dt_h), plus the peak block.

    extra_mwh = energy bought beyond trusting the raw forecast. Hindsight totals (net,
    actual minus what you planned on; negative = short, R7): error_mwh = trusting WINDFOR,
    plan_error_mwh = following the plan. They are None unless every period has an actual
    (a partial sum would mislead).
    """
    dt = periods["dt_h"]
    peak = periods["hour_uk"].between(peak_hours[0], peak_hours[1] - 1)
    has_actual = bool(periods["actual_mw"].notna().all())

    def mwh(col: str, mask: pd.Series | None = None) -> float:
        e = periods[col] * dt
        return float(e[mask].sum() if mask is not None else e.sum())

    def hindsight(col: str, mask: pd.Series | None = None) -> float | None:
        return mwh(col, mask) if has_actual else None

    periods = periods.assign(plan_error_mw=periods["actual_mw"] - periods["planned_mw"])
    return {
        "forecast_mwh": mwh("forecast_mw"),
        "centre_mwh": mwh("centre_mw"),
        "planned_mwh": mwh("planned_mw"),
        "extra_mwh": mwh("forecast_mw") - mwh("planned_mw"),
        "peak_forecast_mwh": mwh("forecast_mw", peak),
        "peak_planned_mwh": mwh("planned_mw", peak),
        "actual_mwh": hindsight("actual_mw"),
        "peak_actual_mwh": hindsight("actual_mw", peak),
        "error_mwh": hindsight("error_mw"),
        "peak_error_mwh": hindsight("error_mw", peak),
        "plan_error_mwh": hindsight("plan_error_mw"),
        "peak_plan_error_mwh": hindsight("plan_error_mw", peak),
    }
