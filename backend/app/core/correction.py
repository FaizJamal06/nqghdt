"""Forecast correction (DECISIONS #29): post-processing of WINDFOR, not a new forecaster.

Four options, fitted on the train rows and scored only on the test days:
  raw           centre = forecast
  constant      centre = forecast + a          (a = mean train error, MW)
  linear        centre = a + b * forecast      (least squares on train)
  proportional  centre = b * forecast          (least squares through the origin)
Proportional exists because linear's intercept (a > 0) *raises* low forecasts even
though actual / forecast < 1 at every wind level in January.
The result is the "centre" that bands and the planner sit on (column centre_mw), so
switching model is a config value, not a code change.

Look-ahead guard: a correction may only read FEATURES. Today that is the forecast
itself. Any future feature must be known at decision time, i.e. no actual after
09:00 on D-1; _features() refuses actual_* columns outright.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd

from app.core.metrics import summary

Kind = Literal["raw", "constant", "linear", "proportional"]
KINDS: tuple[Kind, ...] = ("raw", "constant", "linear", "proportional")
FEATURES = ("forecast_mw",)


@dataclass(frozen=True)
class Correction:
    """centre_mw = max(a + b * forecast_mw, 0). a in MW, b unitless."""

    kind: Kind
    a: float = 0.0
    b: float = 1.0


def _features(frame: pd.DataFrame) -> pd.DataFrame:
    """The only columns a correction may read. Raises if an actual sneaks in (R3)."""
    leaked = [c for c in FEATURES if c.startswith("actual")]
    if leaked:
        raise ValueError(f"correction features must not use actuals: {leaked}")
    return frame[list(FEATURES)]


def fit(train: pd.DataFrame, kind: Kind) -> Correction:
    """Fit a correction on a scored train frame (forecast_mw, actual_mw in MW)."""
    if kind == "raw":
        return Correction("raw")
    x = _features(train)["forecast_mw"]
    y = train["actual_mw"]
    if kind == "constant":
        return Correction("constant", a=float((y - x).mean()))
    if kind == "proportional":
        return Correction("proportional", b=float((x * y).sum() / (x * x).sum()))
    b, a = np.polyfit(x, y, 1)
    return Correction("linear", a=float(a), b=float(b))


def apply(correction: Correction, frame: pd.DataFrame) -> pd.Series:
    """centre_mw for each row, clipped at 0 MW (R10). Reads only FEATURES."""
    x = _features(frame)["forecast_mw"]
    return (correction.a + correction.b * x).clip(lower=0)


def with_centre(scored: pd.DataFrame, correction: Correction) -> pd.DataFrame:
    """Copy of scored with centre_mw and resid_mw = actual_mw - centre_mw (MW)."""
    out = scored.copy()
    out["centre_mw"] = apply(correction, out)
    out["resid_mw"] = out["actual_mw"] - out["centre_mw"]
    return out


def compare(train: pd.DataFrame, test: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    """One row per kind: fitted a, b; test-only MAE, RMSE, bias, % over-forecast; and test
    bias per forecast-level quintile, bias_q1 (calmest) ... bias_q5 (windiest), in MW."""
    level = pd.qcut(test["forecast_mw"], bins, labels=False) + 1
    rows = {}
    for kind in KINDS:
        c = fit(train, kind)
        t = with_centre(test, c)
        s = summary(t.assign(error_mw=t["resid_mw"]))
        per_bin = t["resid_mw"].groupby(level).mean()
        rows[kind] = (
            {"a": c.a, "b": c.b}
            | {k: s[k] for k in ("n", "mae", "rmse", "bias", "pct_over_forecast")}
            | {f"bias_q{q}": v for q, v in per_bin.items()}
        )
    return pd.DataFrame.from_dict(rows, orient="index")
