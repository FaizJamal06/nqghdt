"""Print the January summary from the committed snapshot.

Run from backend/:  python -m app.report
Pure composition of core/ functions through the same DataStore the API uses.
"""

import time
from pathlib import Path

import pandas as pd

from app.config import Settings
from app.core import bands, correction, metrics, planner, selection
from app.core.alignment import train_test_split
from app.core.timeutils import UK
from app.data.loaders import Snapshot, load_snapshot
from app.data.store import DataStore


def fmt(df: pd.DataFrame) -> str:
    """Compact table: whole MW, 3 decimals for ratios."""
    return df.to_string(float_format=lambda v: f"{v:,.3f}" if abs(v) < 10 else f"{v:,.0f}")


def publish_schedule(snap: Snapshot, s: Settings) -> None:
    """DECISIONS #27: exact publish clock times, gaps, and what each preset picks."""
    pubs = pd.Series(snap.forecasts["publishTime"].unique())
    local = pubs.dt.tz_convert(UK)
    print("Publish clock times (UK, to the second) -> count of days:")
    print(fmt(local.dt.strftime("%H:%M:%S").value_counts().sort_index().to_frame("days")))
    days, clocks = local.dt.date, local.dt.strftime("%H:%M")
    for clock in sorted(clocks.value_counts().index):
        missing = sorted(set(days) - set(days[clocks == clock]))
        if 0 < len(missing) < 3:
            print(f"  days without a {clock} publish: {[str(d) for d in missing]}")
    for cutoff in s.cutoff_presets:
        sel = selection.select_at_cutoff(snap.forecasts, cutoff)
        sel = sel[
            sel["startTime"].dt.tz_convert(UK).dt.date.between(s.delivery_first, s.delivery_last)
        ]
        picks = sel["publishTime"].dt.tz_convert(UK).dt.strftime("%H:%M:%S").value_counts()
        print(f"  cutoff {cutoff} picks publishes at: {picks.to_dict()}")


def warm_timings() -> None:
    """PRD §8 (< 300 ms warm): time a second request to each heavy endpoint, in ms."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    client = TestClient(create_app(Settings(static_dir=Path("does-not-exist"))))
    print("\nWarm response times (second request, this machine):")
    for url in ("/api/decision?date=2026-01-21", "/api/accuracy", "/api/calibration"):
        client.get(url)
        t = time.perf_counter()
        client.get(url)
        print(f"  {url}: {(time.perf_counter() - t) * 1000:,.0f} ms")


def main() -> None:
    """Print every M2 number on the real January data."""
    s = Settings()
    snap = load_snapshot(s.data_dir)
    store = DataStore(snap, s)
    print(f"Resolution {snap.resolution_min} min. Cleaning: {snap.cleaning}\n")
    publish_schedule(snap, s)

    main_df, cov = store.scored(("cutoff", s.cutoff_default))
    print(f"\n== Cutoff {s.cutoff_default} ==  coverage {cov}")
    print({k: round(v, 1) for k, v in metrics.summary(main_df).items()})
    print("quantiles", {k: round(v) for k, v in metrics.quantiles(main_df).items()})
    print("exceedance %", {k: round(v, 1) for k, v in metrics.exceedance(main_df).items()})
    print("max shortfall", metrics.max_shortfall(main_df))

    latest, _ = store.scored(("horizon", 0.0))
    print("\nHonest vs flattering (same periods):")
    print(fmt(metrics.on_common_periods({"09:20": main_df, "latest_before_delivery": latest})))
    print("\nValue of waiting (same periods):")
    print(fmt(store.value_of_waiting()))

    print("\nError vs lead time (horizon mode):")
    curve = store.lead_time().set_index("horizon_h")
    print(fmt(curve.loc[[1, 2, 4, 6, 12, 18, 24, 30, 36, int(s.horizon_max_h)]]))

    print("\nBias diagnosis: actual / forecast by forecast-level quintile (09:20):")
    print(fmt(metrics.ratio_by_level(main_df)))

    daily = metrics.daily_energy(main_df, s.peak_hours)
    print(
        f"\nMean daily error {daily['error_mwh'].mean():,.0f} MWh, "
        f"of which peak block (16:00-18:30 starts) {daily['peak_error_mwh'].mean():,.0f} MWh"
    )

    for c in s.cutoff_presets:
        df = store.scored(("cutoff", c))[0]
        train, test = train_test_split(df, s.band_train_end, s.train_known_before)
        print(f"\nCorrection, cutoff {c}: fit on {len(train)} h known by 20 Jan 09:00, TEST only")
        print(fmt(correction.compare(train, test)))

    # Every centre side by side (the store only fits the configured one).
    train, test = train_test_split(main_df, s.band_train_end, s.train_known_before)
    alpha = planner.alpha_from_confidence(0.8)
    plans = {}
    for kind in correction.KINDS:
        corr = correction.fit(train, kind)
        tr, te = correction.with_centre(train, corr), correction.with_centre(test, corr)
        model = bands.fit_bands(tr, s.band_horizon_buckets, s.band_level_bins, s.band_min_cell)
        print(f"\n== centre = {kind} ==  band cells:")
        print(fmt(bands.cell_table(model)))
        print(fmt(bands.calibration(model, tr, te)))
        plans[kind] = planner.backtest(model, te, alpha).set_index("policy").loc["yours"]
    print("\nPlanner at 80% confidence (P20 of residuals around each centre), TEST window:")
    print(fmt(pd.DataFrame(plans).T.drop(columns="alpha")))
    warm_timings()


if __name__ == "__main__":
    main()
