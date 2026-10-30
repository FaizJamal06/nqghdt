"""Metrics on a 4-row fixture: e = [-2500, -1500, 0, +1000] MW (forecast 5000 each)."""

import math

import pandas as pd
import pytest
from conftest import Frame

from app.core import metrics


@pytest.fixture
def four(frame: Frame) -> pd.DataFrame:
    df = frame([5000] * 4, [2500, 3500, 5000, 6000], days=[2, 2, 3, 3])
    df["hour_uk"] = [15, 16, 18, 19]  # 16 and 18 are in the 16:00-18:30 peak block
    df["sp"] = [31, 33, 37, 39]
    return df


def test_summary_by_hand(four: pd.DataFrame) -> None:
    s = metrics.summary(four)
    assert (s["n"], s["n_days"]) == (4, 2)
    assert s["mae"] == 1250  # (2500 + 1500 + 0 + 1000) / 4
    assert s["bias"] == -750  # negative: forecast too high, desk short (R7)
    assert s["rmse"] == pytest.approx(math.sqrt((2500**2 + 1500**2 + 1000**2) / 4))
    assert s["nmae"] == pytest.approx(1250 / 4250 * 100)
    assert s["pct_over_forecast"] == 50


def test_quantiles_exceedance_and_worst(four: pd.DataFrame) -> None:
    assert metrics.quantiles(four, (0.5,)) == {"p50": -750.0}
    assert metrics.exceedance(four) == {"short_gt_1000": 50.0, "short_gt_2000": 25.0}
    assert metrics.max_shortfall(four)["error_mw"] == -2500
    assert metrics.worst_misses(four, 2)["error_mw"].tolist() == [-2500, -1500]


def test_daily_energy_and_peak_block(four: pd.DataFrame) -> None:
    out = metrics.daily_energy(four)
    assert out["error_mwh"].tolist() == [-4000, 1000]
    assert out["peak_error_mwh"].tolist() == [-1500, 0]  # 15:00 and 19:00 are outside


def test_breakdown(four: pd.DataFrame) -> None:
    out = metrics.breakdown(four, "delivery_date")
    assert out[["n", "mae", "bias"]].values.tolist() == [[2, 2000, -2000], [2, 500, 500]]


def test_on_common_periods_uses_shared_periods_only(four: pd.DataFrame) -> None:
    out = metrics.on_common_periods({"a": four, "b": four.iloc[:2]})
    assert out["n"].tolist() == [2, 2]
    assert out.loc["a", "mae"] == 2000


def test_ratio_by_level(frame: Frame) -> None:
    df = frame([100, 100, 1000, 1000], [90, 90, 500, 500])
    out = metrics.ratio_by_level(df, bins=2)
    assert out["ratio"].tolist() == [0.9, 0.5]  # ratio falls at high level
    assert out["bias"].tolist() == [-10, -500]
