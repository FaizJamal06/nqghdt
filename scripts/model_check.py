"""Offline check: does gradient boosting beat the proportional correction? Not part of the app.

Same leak-free split as the app (alignment.train_test_split: fit on the 441 hours whose
actual was known by 20 Jan 09:00 UK, score on delivery days 21 Jan - 1 Feb) and the same
test metrics as correction.compare: MAE, RMSE, bias, % over-forecast (MW) and bias per
forecast-level fifth. Inputs are only what the trader had at the gate (R3): the forecast,
the UK hour, and the revision vs the previous publish. The target is actual_mw.
Default hyperparameters, no tuning: tuning on the test window would make the test a
training set. Days, not hours, are the independent units, so the MAE difference also
gets a by-day bootstrap range (as for band coverage, DECISIONS #4).

scikit-learn is kept out of the app: it is only in requirements-offline.txt. From the repo root:
    .venv/Scripts/pip install -r requirements-offline.txt
    .venv/Scripts/python scripts/model_check.py
"""

import sys
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.config import Settings  # noqa: E402
from app.core import correction  # noqa: E402
from app.core.alignment import train_test_split  # noqa: E402
from app.core.metrics import summary  # noqa: E402
from app.core.timeutils import decision_cutoff  # noqa: E402
from app.data.loaders import load_snapshot  # noqa: E402
from app.data.store import DataStore  # noqa: E402

FEATURE_SETS = {
    "gbm: forecast only": ["forecast_mw"],
    "gbm: + hour, revision": ["forecast_mw", "hour_uk", "revision_mw"],
}


def test_metrics(test: pd.DataFrame, centre: pd.Series) -> dict[str, float]:
    """correction.compare's columns for one centre: summary of actual - centre on test,
    plus mean error per forecast-level fifth (bias_q1 = calmest), all MW."""
    t = test.assign(error_mw=test["actual_mw"] - centre.clip(lower=0))
    s = summary(t)
    level = pd.qcut(test["forecast_mw"], 5, labels=False) + 1
    per_bin = t["error_mw"].groupby(level).mean()
    return {k: s[k] for k in ("n", "mae", "rmse", "bias", "pct_over_forecast")} | {
        f"bias_q{q}": v for q, v in per_bin.items()
    }


def mae_diff_by_day(test: pd.DataFrame, a: pd.Series, b: pd.Series, seed: int = 42) -> tuple:
    """5th-95th percentile of MAE(a) - MAE(b) when resampling whole test days, MW."""
    err = pd.DataFrame(
        {
            "day": test["delivery_date"],
            "d": (test["actual_mw"] - a).abs() - (test["actual_mw"] - b).abs(),
        }
    )
    per_day = err.groupby("day")["d"].agg(["sum", "count"])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(per_day), size=(2000, len(per_day)))
    sums, counts = per_day["sum"].to_numpy()[idx].sum(1), per_day["count"].to_numpy()[idx].sum(1)
    return tuple(np.percentile(sums / counts, [5, 95]))


def main() -> None:
    """Print one comparison table per cutoff preset."""
    s = Settings()
    store = DataStore(load_snapshot(s.data_dir), s)
    for cutoff in s.cutoff_presets:
        key = ("cutoff", cutoff)
        scored = store.scored(key)[0].merge(
            store.selected(key)[["startTime", "revision_mw"]], on="startTime"
        )
        train, test = train_test_split(scored, s.band_train_end, s.train_known_before)
        # The guard this check exists for: no train hour's actual was unknown at the first
        # test decision, and no test day was trained on.
        known = decision_cutoff(s.band_train_end + timedelta(days=1), s.train_known_before)
        assert train["startTime"].max() < known  # 20 Jan 09:00 UK
        assert test["delivery_date"].min() > s.band_train_end

        prop = correction.apply(correction.fit(train, "proportional"), test)
        centres = {"proportional (app)": prop}
        for name, cols in FEATURE_SETS.items():
            model = HistGradientBoostingRegressor(random_state=0).fit(
                train[cols], train["actual_mw"]
            )
            centres[name] = pd.Series(model.predict(test[cols]), index=test.index)

        table = pd.DataFrame({n: test_metrics(test, c) for n, c in centres.items()}).T
        print(
            f"\n== cutoff {cutoff}: fit on {len(train)} h, TEST {len(test)} h "
            f"({test['delivery_date'].nunique()} days) =="
        )
        print(table.to_string(float_format=lambda v: f"{v:,.0f}"))
        for name in FEATURE_SETS:
            lo, hi = mae_diff_by_day(test, centres[name], prop)
            print(f"  MAE({name}) - MAE(proportional), by-day 5-95%: {lo:+,.0f} to {hi:+,.0f} MW")
        tr, te = train["forecast_mw"], test["forecast_mw"]
        print(
            f"  forecast range: train {tr.min():,.0f}-{tr.max():,.0f} MW, "
            f"test {te.min():,.0f}-{te.max():,.0f} MW"
        )
        # Trees predict a constant beyond the last split, so if extrapolation were the
        # problem, GBM's bias would concentrate on test hours above the train range.
        for label, mask in (
            (f"> train P90 ({tr.quantile(0.9):,.0f} MW)", te > tr.quantile(0.9)),
            (f"> train max ({tr.max():,.0f} MW)", te > tr.max()),
            ("<= train P90", te <= tr.quantile(0.9)),
        ):
            if not mask.any():
                print(f"  test hours {label}: 0")
                continue
            bias = {n: (test["actual_mw"] - c)[mask].mean() for n, c in centres.items()}
            print(
                f"  test hours {label}: {int(mask.sum())}; bias (actual - centre) "
                + ", ".join(f"{n} {b:+,.0f}" for n, b in bias.items())
            )
        # What the trees learned at the top: how many days the windy train hours come from,
        # and actual / forecast there vs on the windy test hours.
        for name, df in (("train", train), ("test", test)):
            top = df[df["forecast_mw"] > tr.quantile(0.9)]
            ratio = top["actual_mw"].sum() / top["forecast_mw"].sum()
            days = top["delivery_date"].value_counts()
            print(
                f"  {name} hours > train P90: {len(top)} on {len(days)} days "
                f"(most: {days.index[0]} with {days.iloc[0]}); actual / forecast {ratio:.2f}"
            )


if __name__ == "__main__":
    main()
