"""R2/R8 selection: the most important tests. Which row did the trader really have?"""

import pandas as pd

from app.config import Settings
from app.core.selection import (
    previous_publish,
    select_at_cutoff,
    select_at_horizon,
    select_latest_before_delivery,
)
from app.data.loaders import load_snapshot


def fc(rows: list[tuple[str, str, float]]) -> pd.DataFrame:
    """rows = (publishTime, startTime, forecast_mw), in UTC (January: UTC = UK)."""
    df = pd.DataFrame(rows, columns=["publishTime", "startTime", "forecast_mw"])
    for col in ("publishTime", "startTime"):
        df[col] = pd.to_datetime(df[col], utc=True)
    df["horizon_h"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    return df


# Delivery 2 Jan 00:00 -> cutoff 1 Jan 09:20. Delivery 2 Jan 01:00 has only a late publish.
FIXTURE = fc(
    [
        ("2026-01-01T07:30:00Z", "2026-01-02T00:00Z", 100.0),
        ("2026-01-01T09:20:00Z", "2026-01-02T00:00Z", 110.0),  # exactly at the gate: in
        ("2026-01-01T09:20:01Z", "2026-01-02T00:00Z", 120.0),  # one second late: out
        ("2026-01-01T11:30:00Z", "2026-01-02T01:00Z", 130.0),  # only publish is after cutoff
    ]
)


def test_cutoff_includes_equality_and_excludes_one_second_late() -> None:
    out = select_at_cutoff(FIXTURE, "09:20")
    assert out["forecast_mw"].tolist() == [110.0]
    assert out["horizon_h"].iloc[0] == 14 + 40 / 60  # 09:20 -> 00:00 next day


def test_period_without_eligible_forecast_is_absent() -> None:
    out = select_at_cutoff(FIXTURE, "09:20")
    assert pd.Timestamp("2026-01-02T01:00Z") not in set(out["startTime"])


def test_horizon_mode_equals_cutoff_mode_when_limits_coincide() -> None:
    # For the 00:00 period, h = 14h40m puts the limit exactly at 1 Jan 09:20.
    by_h = select_at_horizon(FIXTURE, 14 + 40 / 60)
    at_cut = select_at_cutoff(FIXTURE, "09:20")
    assert by_h.iloc[[0]].equals(at_cut)


def test_latest_before_delivery_takes_the_last_publish() -> None:
    out = select_latest_before_delivery(FIXTURE)
    assert out["forecast_mw"].tolist() == [120.0, 130.0]


def test_previous_publish_and_revision() -> None:
    out = previous_publish(FIXTURE, select_at_cutoff(FIXTURE, "09:20"))
    assert out[["previous_mw", "revision_mw"]].iloc[0].tolist() == [100.0, 10.0]
    first = previous_publish(FIXTURE, FIXTURE.iloc[[0]])
    assert first["previous_mw"].isna().all()  # nothing earlier covered that hour


def test_real_snapshot_picks_for_15_jan_1700() -> None:
    """The M1 worked example, on the committed data. The 15:30 publish lands exactly at
    the 15:30 cutoff (real timestamp 2026-01-14T15:30:00Z) and must be included."""
    f = load_snapshot(Settings().data_dir).forecasts
    hour = pd.Timestamp("2026-01-15T17:00Z")
    picks = {}
    for cutoff in ("09:20", "09:50", "15:30"):
        sel = select_at_cutoff(f, cutoff)
        row = sel[sel["startTime"] == hour].iloc[0]
        picks[cutoff] = (row["publishTime"], row["forecast_mw"])
    assert picks == {
        "09:20": (pd.Timestamp("2026-01-14T07:30:00Z"), 8870.0),
        "09:50": (pd.Timestamp("2026-01-14T09:30:00Z"), 8966.0),
        "15:30": (pd.Timestamp("2026-01-14T15:30:00Z"), 8137.0),
    }
    # Move that publish one second later: 15:30 must fall back to the 11:30 publish.
    late = f.copy()
    late.loc[late["publishTime"] == pd.Timestamp("2026-01-14T15:30Z"), "publishTime"] += (
        pd.Timedelta(seconds=1)
    )
    sel = select_at_cutoff(late, "15:30")
    assert sel.loc[sel["startTime"] == hour, "forecast_mw"].item() == 9030.0
