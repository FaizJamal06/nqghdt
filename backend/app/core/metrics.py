"""Accuracy metrics on a scored frame (PRD §5.4). e = error_mw = actual - forecast, in MW.

Negative e = wind came in below the forecast = desk short (R7). Every summary carries
n (periods) and n_days, because ~31 days is the real sample size, not ~744 hours.
No MAPE: it explodes on low-wind hours (Methodology page).
"""

import numpy as np
import pandas as pd

QUANTILE_LEVELS = (0.05, 0.10, 0.20, 0.50, 0.80, 0.90, 0.95)


def summary(scored: pd.DataFrame) -> dict[str, float]:
    """MAE, RMSE, bias (MW); nMAE, NRMSE (% of mean actual); share of periods over-forecast.

    pct_over_forecast = % of periods with e < 0, i.e. the forecast was too high.
    """
    e = scored["error_mw"]
    mean_actual = float(scored["actual_mw"].mean())
    mae = float(e.abs().mean())
    rmse = float(np.sqrt((e**2).mean()))
    return {
        "n": len(scored),
        "n_days": scored["delivery_date"].nunique(),
        "mae": mae,
        "rmse": rmse,
        "bias": float(e.mean()),
        "nmae": mae / mean_actual * 100,
        "nrmse": rmse / mean_actual * 100,
        "pct_over_forecast": float((e < 0).mean() * 100),
    }


def quantiles(
    scored: pd.DataFrame, levels: tuple[float, ...] = QUANTILE_LEVELS
) -> dict[str, float]:
    """Empirical error quantiles in MW, keyed "p5", "p10", ... (linear interpolation)."""
    q = scored["error_mw"].quantile(list(levels))
    return {f"p{round(lv * 100)}": float(v) for lv, v in q.items()}


def exceedance(
    scored: pd.DataFrame, thresholds: tuple[int, ...] = (1000, 2000)
) -> dict[str, float]:
    """% of periods short by more than each threshold (e < -threshold MW)."""
    e = scored["error_mw"]
    return {f"short_gt_{t}": float((e < -t).mean() * 100) for t in thresholds}


def max_shortfall(scored: pd.DataFrame) -> dict[str, object]:
    """The single worst shortfall: min(e) in MW and its startTime (UTC)."""
    row = scored.loc[scored["error_mw"].idxmin()]
    return {"error_mw": float(row["error_mw"]), "startTime": row["startTime"]}


def daily_energy(scored: pd.DataFrame, peak_hours: tuple[int, int] = (16, 19)) -> pd.DataFrame:
    """Per delivery day: error_mwh = sum(e * dt_h), and the same for the peak block.

    Peak block = periods starting from peak_hours[0]:00 up to (not incl.) peak_hours[1]:00
    UK local, i.e. 16:00-18:30 starts (DECISIONS #5). Days with no peak periods get 0.
    """
    mwh = scored["error_mw"] * scored["dt_h"]
    peak = scored["hour_uk"].between(peak_hours[0], peak_hours[1] - 1)
    out = pd.DataFrame(
        {"delivery_date": scored["delivery_date"], "error_mwh": mwh, "peak_error_mwh": mwh * peak}
    )
    return out.groupby("delivery_date", as_index=False).sum()


def breakdown(scored: pd.DataFrame, by: str) -> pd.DataFrame:
    """n, MAE, RMSE, bias (MW) per value of column `by` (e.g. hour_uk, level_bin)."""
    e = scored["error_mw"]
    g = pd.DataFrame({"abs": e.abs(), "sq": e**2, "e": e}).groupby(scored[by])
    return pd.DataFrame(
        {
            "n": g.size(),
            "mae": g["abs"].mean(),
            "rmse": np.sqrt(g["sq"].mean()),
            "bias": g["e"].mean(),
        }
    ).reset_index()


def worst_misses(scored: pd.DataFrame, k: int = 10) -> pd.DataFrame:
    """The k most negative errors (biggest shortfalls), worst first."""
    cols = ["startTime", "delivery_date", "sp", "forecast_mw", "actual_mw", "error_mw", "horizon_h"]
    return scored.nsmallest(k, "error_mw")[cols].reset_index(drop=True)


def on_common_periods(frames: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """MAE/RMSE/bias for several selections, restricted to periods all of them scored.

    Used for "honest vs flattering" (09:20 vs latest-before-delivery) and "value of
    waiting" (09:20 vs 09:50 vs 15:30): comparing on different periods would mix
    a better forecast with an easier sample.
    """
    common = set.intersection(*(set(f["startTime"]) for f in frames.values()))
    rows = {}
    for name, f in frames.items():
        s = summary(f[f["startTime"].isin(common)])
        rows[name] = {k: s[k] for k in ("n", "mae", "rmse", "bias", "pct_over_forecast")}
    return pd.DataFrame.from_dict(rows, orient="index")


def ratio_by_level(scored: pd.DataFrame, bins: int = 5) -> pd.DataFrame:
    """Bias diagnosis (DECISIONS #23): mean actual / mean forecast per forecast-level quintile.

    A flat ratio below 1 is consistent with a scaling/coverage gap (e.g. capacity the
    forecast counts but metering doesn't). A ratio that falls at high forecast levels is
    consistent with curtailment on windy hours. Neither can be confirmed from these two
    datasets alone.
    """
    level = pd.qcut(scored["forecast_mw"], bins, labels=False)
    g = scored.groupby(level)
    out = pd.DataFrame(
        {
            "n": g.size(),
            "forecast_min": g["forecast_mw"].min(),
            "forecast_max": g["forecast_mw"].max(),
            "mean_forecast": g["forecast_mw"].mean(),
            "mean_actual": g["actual_mw"].mean(),
        }
    )
    out["ratio"] = out["mean_actual"] / out["mean_forecast"]
    out["bias"] = out["mean_actual"] - out["mean_forecast"]
    return out.rename_axis("quintile").reset_index()
