"""Band lookup, fallback on thin cells, clipping, PICP and the by-day bootstrap."""

import pandas as pd
import pytest
from conftest import Frame

from app.core import bands

# Low-wind cell: residuals -10..+10. High-wind cell: -100..+100. Level edge = 550 MW.
LOW, HIGH = [-10, -5, 5, 10], [-100, -50, 50, 100]


@pytest.fixture
def train(frame: Frame) -> pd.DataFrame:
    forecast = [100] * 4 + [1000] * 4
    return frame(forecast, [f + r for f, r in zip(forecast, LOW + HIGH, strict=True)])


def fit(train: pd.DataFrame, min_cell: int) -> bands.BandModel:
    return bands.fit_bands(train, n_horizon=1, n_level=2, min_cell=min_cell)


def test_quantile_lookup_per_cell(train: pd.DataFrame, frame: Frame) -> None:
    model = fit(train, min_cell=4)
    rows = frame([200, 900], [0, 0])
    q, used = bands.residual_quantile(model, rows, 1.0)
    assert q.tolist() == [10, 100] and used.tolist() == ["cell", "cell"]


def test_fallback_order_on_thin_cells(train: pd.DataFrame, frame: Frame) -> None:
    rows = frame([200], [0])
    _, used = bands.residual_quantile(fit(train, min_cell=5), rows, 0.5)
    assert used.item() == "horizon"  # cells have 4 < 5 rows; the bucket has 8
    q, used = bands.residual_quantile(fit(train, min_cell=9), rows, 1.0)
    assert (used.item(), q.item()) == ("pooled", 100)


def test_band_clipped_at_zero(train: pd.DataFrame, frame: Frame) -> None:
    b = bands.band(fit(train, 4), frame([5], [5]), central=1.0)  # [5 - 10, 5 + 10]
    assert b[["band_low_mw", "band_high_mw"]].iloc[0].tolist() == [0, 15]


def test_picp_all_inside_and_none_inside(train: pd.DataFrame, frame: Frame) -> None:
    model = fit(train, 4)
    assert bands.picp(model, frame([200, 900], [200, 900]), 0.8) == 1.0
    assert bands.picp(model, frame([200, 900], [5000, 5000]), 0.8) == 0.0


def test_bootstrap_resamples_days(train: pd.DataFrame, frame: Frame) -> None:
    model = fit(train, 4)
    # Day 21 fully inside, day 22 fully outside -> day-level PICP is 0 or 1.
    test = frame([200, 200, 200, 200], [200, 200, 5000, 5000], days=[21, 21, 22, 22])
    lo, hi = bands.bootstrap_picp(model, test, 0.8, n_boot=500)
    assert 0 <= lo < 0.5 < hi <= 1
    assert bands.bootstrap_picp(model, test, 0.8, n_boot=500) == (lo, hi)  # seeded
    cal = bands.calibration(model, train, test)
    assert cal["nominal"].tolist() == [0.5, 0.8, 0.9]
    assert cal["test_picp"].tolist() == [0.5, 0.5, 0.5]
