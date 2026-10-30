"""Correction models, and the guard that they never read actuals."""

import pytest
from conftest import Frame

from app.core import correction


def test_fits_recover_known_parameters(frame: Frame) -> None:
    df = frame([1000, 2000, 3000], [600, 1100, 1600])  # actual = 100 + 0.5 x forecast
    assert correction.fit(df, "raw") == correction.Correction("raw")
    assert correction.fit(df, "constant").a == pytest.approx(-900)  # mean(actual - forecast)
    lin = correction.fit(df, "linear")
    assert (lin.a, lin.b) == (pytest.approx(100), pytest.approx(0.5))


def test_apply_clips_at_zero(frame: Frame) -> None:
    df = frame([100, 1000], [0, 0])
    assert correction.apply(correction.Correction("constant", a=-300), df).tolist() == [0, 700]


def test_correction_ignores_actuals(frame: Frame) -> None:
    c = correction.Correction("linear", a=50, b=0.8)
    df = frame([1000, 2000], [1, 2])
    scrambled = df.assign(actual_mw=[9e9, -9e9])
    assert correction.apply(c, df).equals(correction.apply(c, scrambled))


def test_guard_rejects_actual_features(frame: Frame, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(correction, "FEATURES", ("forecast_mw", "actual_mw"))
    with pytest.raises(ValueError, match="must not use actuals"):
        correction.apply(correction.Correction("raw"), frame([1], [1]))


def test_with_centre_and_compare(frame: Frame) -> None:
    train = frame([1000, 2000, 3000], [600, 1100, 1600])
    test = frame([4000], [2100])
    t = correction.with_centre(test, correction.fit(train, "linear"))
    assert t["resid_mw"].item() == pytest.approx(0)
    out = correction.compare(train, test)
    assert out.index.tolist() == ["raw", "constant", "linear"]
    assert out.loc["raw", "mae"] == 1900 and out.loc["linear", "mae"] == pytest.approx(0)
