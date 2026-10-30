"""Decision View helpers: flags, freshness/staleness, day totals."""

import math

import pandas as pd
from conftest import Frame

from app.core import bands
from app.core.decision import day_periods, day_totals, freshness


def test_flags_and_planned(frame: Frame) -> None:
    train = frame([100] * 4 + [1000] * 4, [90, 100, 100, 110, 800, 1000, 1000, 1200])
    model = bands.fit_bands(train, n_horizon=1, n_level=2, min_cell=4)
    day = frame([100, 100, 100, 100, 1000], [0] * 5)
    day["revision_mw"] = [0, 10, -10, 500, None]
    out = day_periods(day, model, central=0.8, alpha=0.5)
    assert out["flags"].tolist() == [
        ["low_wind"],
        ["low_wind"],
        ["low_wind"],
        ["low_wind", "big_revision"],  # |500| is above the day's 80th percentile
        ["wide_band"],  # high-wind cell is wider; no previous publish -> no revision flag
    ]
    assert out["planned_mw"].iloc[0] == 100  # median residual of the low cell is 0
    # Ties: if every hour has the same width, none is "wider than the 80th percentile".
    same = day_periods(day.iloc[:4], model, central=0.8, alpha=0.5)
    assert not any("wide_band" in f for f in same["flags"])


def test_freshness_and_staleness() -> None:
    pubs = pd.Series(
        pd.to_datetime(["2026-01-01T01:30Z", "2026-01-01T04:30Z", "2026-01-01T07:30Z"])
    )
    fresh = freshness(pubs, pd.Timestamp("2026-01-01T09:20Z"))
    assert fresh["latest_publish"] == pubs[2] and fresh["minutes_before_cutoff"] == 110
    assert fresh["is_stale"] is False
    # 3 h median gap -> stale after 6 h: 07:30 is 6 h 50 m old at 14:20
    assert freshness(pubs, pd.Timestamp("2026-01-01T14:20Z"))["is_stale"] is True


def test_day_totals(frame: Frame) -> None:
    day = frame([100, 200], [80, 210])
    day["planned_mw"], day["hour_uk"] = [90, 150], [16, 20]
    t = day_totals(day, (16, 19))
    assert (t["forecast_mwh"], t["planned_mwh"], t["extra_mwh"]) == (300, 240, 60)
    assert (t["error_mwh"], t["peak_error_mwh"], t["peak_planned_mwh"]) == (-10, -20, 90)
    day.loc[1, "actual_mw"] = math.nan
    assert day_totals(day, (16, 19))["actual_mwh"] is None  # partial day: no fake total
