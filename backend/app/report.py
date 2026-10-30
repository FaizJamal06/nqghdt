"""Print the January summary from the committed snapshot (M2 "done when").

Run from backend/:  python -m app.report
Pure composition of core/ functions; the M3 DataStore will reuse scored_for().
"""

import pandas as pd

from app.config import Settings
from app.core import bands, correction, metrics, planner, selection
from app.core.alignment import score
from app.core.timeutils import UK
from app.data.loaders import Snapshot, load_snapshot


def scored_for(
    snap: Snapshot, s: Settings, cutoff: str | None = None, horizon_h: float | None = None
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Scored frame + coverage for one selection mode: a D-1 cutoff or a fixed horizon."""
    if horizon_h is None:
        sel = selection.select_at_cutoff(snap.forecasts, cutoff or s.cutoff_default)
    else:
        sel = selection.select_at_horizon(snap.forecasts, horizon_h)
    return score(sel, snap.actuals, snap.resolution_min, s.delivery_first, s.delivery_last)


def split(scored: pd.DataFrame, s: Settings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Train = delivery days up to band_train_end, test = the rest (PRD §5.5)."""
    is_train = scored["delivery_date"] <= s.band_train_end
    return scored[is_train], scored[~is_train]


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


def main() -> None:
    """Print every M2 number on the real January data."""
    s = Settings()
    snap = load_snapshot(s.data_dir)
    print(f"Resolution {snap.resolution_min} min. Cleaning: {snap.cleaning}\n")
    publish_schedule(snap, s)

    at = {c: scored_for(snap, s, cutoff=c) for c in s.cutoff_presets}
    main_df, cov = at[s.cutoff_default]
    print(f"\n== Cutoff {s.cutoff_default} ==  coverage {cov}")
    print({k: round(v, 1) for k, v in metrics.summary(main_df).items()})
    print("quantiles", {k: round(v) for k, v in metrics.quantiles(main_df).items()})
    print("exceedance %", {k: round(v, 1) for k, v in metrics.exceedance(main_df).items()})
    print("max shortfall", metrics.max_shortfall(main_df))

    latest, _ = scored_for(snap, s, horizon_h=0)
    print("\nHonest vs flattering (same periods):")
    print(fmt(metrics.on_common_periods({"09:20": main_df, "latest_before_delivery": latest})))
    print("\nValue of waiting (same periods):")
    print(fmt(metrics.on_common_periods({c: f for c, (f, _) in at.items()})))

    print("\nError vs lead time (horizon mode):")
    for h in (1, 2, 4, 6, 12, 18, 24, 30, 36, int(s.horizon_max_h)):
        sh = metrics.summary(scored_for(snap, s, horizon_h=h)[0])
        print(f"  h={h:>2}  n={sh['n']}  MAE={sh['mae']:,.0f}  bias={sh['bias']:,.0f}")

    print("\nBias diagnosis: actual / forecast by forecast-level quintile (09:20):")
    print(fmt(metrics.ratio_by_level(main_df)))

    daily = metrics.daily_energy(main_df, s.peak_hours)
    print(
        f"\nMean daily error {daily['error_mwh'].mean():,.0f} MWh, "
        f"of which peak block (16:00-18:30 starts) {daily['peak_error_mwh'].mean():,.0f} MWh"
    )

    for c, (df, _) in at.items():
        train, test = split(df, s)
        print(f"\nCorrection, cutoff {c}: fit 2-20 Jan, TEST 21 Jan-1 Feb only")
        print(fmt(correction.compare(train, test)))

    train, test = split(main_df, s)
    for kind in correction.KINDS:
        corr = correction.fit(train, kind)
        tr, te = correction.with_centre(train, corr), correction.with_centre(test, corr)
        model = bands.fit_bands(tr, s.band_horizon_buckets, s.band_level_bins, s.band_min_cell)
        print(
            f"\n== centre = {kind} ==  band cells (train rows): "
            f"{ {k: len(v) for k, v in model.cells.items()} }"
        )
        print(fmt(bands.calibration(model, tr, te)))
        print(fmt(planner.backtest(model, te, planner.alpha_from_confidence(0.8))))


if __name__ == "__main__":
    main()
