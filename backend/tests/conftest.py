"""Shared hand-checkable fixture: a scored frame with centre = raw forecast."""

from collections.abc import Callable
from datetime import date

import pandas as pd
import pytest

Frame = Callable[..., pd.DataFrame]


@pytest.fixture
def frame() -> Frame:
    """frame(forecast, actual, horizon_h=24, days=None) -> scored-like DataFrame (MW, 1 h rows).

    centre_mw = forecast_mw (raw); resid_mw = error_mw = actual - forecast. `days` are
    day-of-January numbers, one per row (default: all on 2 Jan).
    """

    def make(
        forecast: list[float],
        actual: list[float],
        horizon_h: float | list[float] = 24,
        days: list[int] | None = None,
    ) -> pd.DataFrame:
        df = pd.DataFrame({"forecast_mw": forecast, "actual_mw": actual, "horizon_h": horizon_h})
        df["delivery_date"] = [date(2026, 1, d) for d in (days or [2] * len(df))]
        df["startTime"] = pd.date_range("2026-01-02", periods=len(df), freq="h", tz="UTC")
        df["centre_mw"] = df["forecast_mw"]
        df["error_mw"] = df["resid_mw"] = df["actual_mw"] - df["forecast_mw"]
        df["dt_h"] = 1.0
        return df

    return make
