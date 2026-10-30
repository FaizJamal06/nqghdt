"""Buffer planner: turn the error distribution into a planned wind level (PRD §5.7, R9).

Newsvendor rule: plan at the alpha-quantile of what wind will actually do, i.e.
planned = centre + q_alpha(residual | cell), clipped at 0 MW (R10). A low alpha
plans less wind, so the desk buys more power up front and is short less often.
Energy is MW x dt_h hours = MWh.
"""

import pandas as pd

from app.core.bands import BandModel, residual_quantile


def alpha_from_confidence(confidence: float) -> float:
    """alpha = 1 - confidence: "80% sure wind is at least this" -> the 20th percentile."""
    if not 0 < confidence < 1:
        raise ValueError("confidence must be between 0 and 1")
    return round(1 - confidence, 10)  # 0.2, not 0.19999999999999996


def alpha_from_costs(c_short: float, c_long: float) -> float:
    """alpha = c_long / (c_short + c_long). Short costing 3x long -> 0.25."""
    if c_short <= 0 or c_long <= 0:
        raise ValueError("costs must be positive")
    return c_long / (c_short + c_long)


def planned_wind(model: BandModel, df: pd.DataFrame, alpha: float) -> pd.Series:
    """Planned wind in MW per period: centre_mw + alpha-quantile of the cell's residuals."""
    q, _ = residual_quantile(model, df, alpha)
    return (df["centre_mw"] + q).clip(lower=0)


def policy_stats(
    df: pd.DataFrame, planned: pd.Series, prices: tuple[float, float] | None = None
) -> dict[str, float]:
    """Backtest one policy on scored rows.

    pct_short: % of periods where wind came in below plan (planned > actual).
    shortfall_mwh / excess_mwh: sum of max(planned - actual, 0) / max(actual - planned, 0) x dt_h.
    extra_mwh: sum((forecast - planned) x dt_h), energy bought beyond trusting the raw forecast.
    prices = (short GBP/MWh, long GBP/MWh), the user's assumption (DECISIONS #6): adds cost_gbp.
    """
    dt = df["dt_h"]
    gap = planned - df["actual_mw"]
    out = {
        "pct_short": (gap > 0).mean() * 100,
        "shortfall_mwh": (gap.clip(lower=0) * dt).sum(),
        "excess_mwh": ((-gap).clip(lower=0) * dt).sum(),
        "extra_mwh": ((df["forecast_mw"] - planned) * dt).sum(),
    }
    if prices is not None:
        out["cost_gbp"] = prices[0] * out["shortfall_mwh"] + prices[1] * out["excess_mwh"]
    return out


def backtest(
    model: BandModel,
    test: pd.DataFrame,
    alpha: float,
    prices: tuple[float, float] | None = None,
) -> pd.DataFrame:
    """Policies raw forecast, P50, P20, P10 and the user's alpha, scored on the test rows."""
    policies: dict[str, tuple[float | None, pd.Series]] = {"raw": (None, test["forecast_mw"])}
    for name, a in (("P50", 0.5), ("P20", 0.2), ("P10", 0.1), ("yours", alpha)):
        policies[name] = (a, planned_wind(model, test, a))
    rows = [
        {"policy": name, "alpha": a} | policy_stats(test, planned, prices)
        for name, (a, planned) in policies.items()
    ]
    return pd.DataFrame(rows)
