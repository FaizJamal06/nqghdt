"""Newsvendor alpha (R9), planned wind clipping (R10), backtest arithmetic."""

import pandas as pd
import pytest
from conftest import Frame

from app.core import bands, planner


def test_alpha_rules() -> None:
    assert planner.alpha_from_confidence(0.8) == pytest.approx(0.2)
    assert planner.alpha_from_costs(3, 1) == 0.25  # short costs 3x long
    with pytest.raises(ValueError):
        planner.alpha_from_confidence(1.0)
    with pytest.raises(ValueError):
        planner.alpha_from_costs(0, 1)


def test_policy_stats_by_hand(frame: Frame) -> None:
    df = frame([100, 100], [80, 120])
    out = planner.policy_stats(df, pd.Series([90.0, 90.0]), prices=(3, 1))
    # gaps planned - actual = [+10, -30]: short once by 10 MWh, long once by 30 MWh
    assert out == {
        "pct_short": 50,
        "shortfall_mwh": 10,
        "excess_mwh": 30,
        "extra_mwh": 20,  # (100 - 90) x 1 h x 2 periods bought beyond the forecast
        "cost_gbp": 3 * 10 + 1 * 30,
    }


def test_backtest_raw_buys_nothing_extra_and_plans_clip(frame: Frame) -> None:
    train = frame([10] * 4, [0, 0, 10, 10])  # residuals -10, -10, 0, 0
    model = bands.fit_bands(train, n_horizon=1, n_level=1, min_cell=1)
    test = frame([5, 50], [5, 50])
    assert planner.planned_wind(model, test, 0.0).tolist() == [0, 40]  # 5 - 10 -> 0
    out = planner.backtest(model, test, alpha=0.2).set_index("policy")
    assert out.loc["raw", "extra_mwh"] == 0
    assert out.index.tolist() == ["raw", "P50", "P20", "P10", "yours"]
