"""Uncertainty bands from past errors (PRD §5.5-5.6, DECISIONS #3, #4, #21).

Empirical and conditional: store the train-window residuals (actual - centre, MW) per
cell and read any quantile on demand. Cells = horizon bucket x forecast-level bin;
config uses 1 x 3 (wind level only) in both modes, see DECISIONS #42.
Edges are train-set quantiles. A cell with < min_cell train rows falls back to its
horizon bucket, then to all train rows; the level used is recorded.
Input frames come from correction.with_centre (need horizon_h, forecast_mw,
centre_mw, actual_mw, resid_mw, delivery_date).
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd


@dataclass(frozen=True)
class BandModel:
    """Fitted edges plus train residuals (MW) per cell, per horizon bucket and pooled."""

    horizon_edges: np.ndarray  # inner edges in hours; empty = one bucket
    level_edges: np.ndarray  # inner edges in forecast MW
    cells: dict[tuple[int, int], np.ndarray]
    by_horizon: dict[int, np.ndarray]
    pooled: np.ndarray


def _inner_quantiles(x: pd.Series, n: int) -> np.ndarray:
    """n-1 inner edges splitting x into n equal-count groups (terciles for n=3)."""
    return x.quantile(np.linspace(0, 1, n + 1)[1:-1]).to_numpy()


def assign_bins(df: pd.DataFrame, model: BandModel) -> pd.DataFrame:
    """horizon_bucket and level_bin (0 = shortest / lowest wind) for each row."""
    return pd.DataFrame(
        {
            "horizon_bucket": np.searchsorted(model.horizon_edges, df["horizon_h"], side="right"),
            "level_bin": np.searchsorted(model.level_edges, df["forecast_mw"], side="right"),
        },
        index=df.index,
    )


def fit_bands(
    train: pd.DataFrame, n_horizon: int = 2, n_level: int = 3, min_cell: int = 40
) -> BandModel:
    """Fit edges on train and keep every cell / bucket with >= min_cell residuals."""
    skeleton = BandModel(
        horizon_edges=_inner_quantiles(train["horizon_h"], n_horizon),
        level_edges=_inner_quantiles(train["forecast_mw"], n_level),
        cells={},
        by_horizon={},
        pooled=train["resid_mw"].to_numpy(),
    )
    bins = assign_bins(train, skeleton)
    resid = train["resid_mw"]
    cells = {
        (int(h), int(lv)): g.to_numpy()
        for (h, lv), g in resid.groupby([bins["horizon_bucket"], bins["level_bin"]])
        if len(g) >= min_cell
    }
    by_horizon = {
        int(h): g.to_numpy() for h, g in resid.groupby(bins["horizon_bucket"]) if len(g) >= min_cell
    }
    return BandModel(
        skeleton.horizon_edges, skeleton.level_edges, cells, by_horizon, skeleton.pooled
    )


def cell_table(model: BandModel) -> pd.DataFrame:
    """One row per fitted cell: train rows, P10, P90 and P10-P90 width of residuals (MW).

    lo_mw / hi_mw are the cell's forecast-level range (None = open-ended).
    """
    edges = [None, *model.level_edges.tolist(), None]
    rows = [
        {
            "horizon_bucket": h,
            "level_bin": lv,
            "lo_mw": edges[lv],
            "hi_mw": edges[lv + 1],
            "n": len(errs),
            "p10": float(np.quantile(errs, 0.1)),
            "p90": float(np.quantile(errs, 0.9)),
        }
        for (h, lv), errs in sorted(model.cells.items())
    ]
    out = pd.DataFrame(rows)
    out["width"] = out["p90"] - out["p10"]
    return out


def residual_quantile(model: BandModel, df: pd.DataFrame, q: float) -> tuple[pd.Series, pd.Series]:
    """q-quantile of train residuals (MW) for each row's cell, and which level was used.

    Level is "cell", "horizon" or "pooled" (fallback order, PRD §5.5 step 3).
    """
    bins = assign_bins(df, model)
    value = pd.Series(float(np.quantile(model.pooled, q)), index=df.index)
    used = pd.Series("pooled", index=df.index)
    for h, errs in model.by_horizon.items():
        m = bins["horizon_bucket"] == h
        value[m], used[m] = float(np.quantile(errs, q)), "horizon"
    for (h, lv), errs in model.cells.items():
        m = (bins["horizon_bucket"] == h) & (bins["level_bin"] == lv)
        value[m], used[m] = float(np.quantile(errs, q)), "cell"
    return value, used


def band(model: BandModel, df: pd.DataFrame, central: float = 0.8) -> pd.DataFrame:
    """Central band around centre_mw: e.g. 0.8 -> [centre + q10, centre + q90], >= 0 MW (R10)."""
    lo_q = (1 - central) / 2
    lo, used = residual_quantile(model, df, lo_q)
    hi, _ = residual_quantile(model, df, 1 - lo_q)
    return pd.DataFrame(
        {
            "band_low_mw": (df["centre_mw"] + lo).clip(lower=0),
            "band_high_mw": (df["centre_mw"] + hi).clip(lower=0),
            "band_level": used,
        }
    )


def _inside(model: BandModel, df: pd.DataFrame, central: float) -> pd.Series:
    b = band(model, df, central)
    return df["actual_mw"].between(b["band_low_mw"], b["band_high_mw"])


def picp(model: BandModel, df: pd.DataFrame, central: float) -> float:
    """PICP: share of actuals inside the central band (1.0 = all inside)."""
    return float(_inside(model, df, central).mean())


def bootstrap_picp(
    model: BandModel, df: pd.DataFrame, central: float, n_boot: int = 2000, seed: int = 42
) -> tuple[float, float]:
    """5th-95th percentile range of PICP when resampling whole days (DECISIONS #4).

    Hours within a day share weather, so days (not hours) are the independent units.
    """
    inside = _inside(model, df, central).groupby(df["delivery_date"]).agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(inside), size=(n_boot, len(inside)))
    hits, n = inside["sum"].to_numpy()[idx].sum(1), inside["count"].to_numpy()[idx].sum(1)
    lo, hi = np.percentile(hits / n, [5, 95])
    return float(lo), float(hi)


def calibration(
    model: BandModel,
    train: pd.DataFrame,
    test: pd.DataFrame,
    levels: tuple[float, ...] = (0.5, 0.8, 0.9),
) -> pd.DataFrame:
    """Nominal vs observed coverage on train and test, with the test by-day range."""
    rows = []
    for c in levels:
        lo, hi = bootstrap_picp(model, test, c)
        rows.append(
            {
                "nominal": c,
                "train_picp": picp(model, train, c),
                "test_picp": picp(model, test, c),
                "test_lo": lo,
                "test_hi": hi,
                "n_train": len(train),
                "n_test": len(test),
            }
        )
    return pd.DataFrame(rows)
