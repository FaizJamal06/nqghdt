"""Read the committed snapshot and clean it (PRD §4 "Cleaning on load").

Every dropped row is counted, never silently discarded (R11). The clean_* functions
are pure (DataFrame in, DataFrame + counts out) so they are tested on tiny fixtures;
load_snapshot is the only function that touches the disk.
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

FUELHH_FILE = "fuelhh_wind.csv.gz"
WINDFOR_FILE = "windfor.csv.gz"
MANIFEST_FILE = "manifest.json"


@dataclass(frozen=True)
class Snapshot:
    """Cleaned frames plus what cleaning did. All timestamps are UTC-aware."""

    actuals: pd.DataFrame  # startTime, publishTime, settlementDate, settlementPeriod, actual_mw
    forecasts: pd.DataFrame  # publishTime, startTime, forecast_mw, horizon_h
    resolution_min: int  # WINDFOR startTime spacing: 30 or 60
    cleaning: dict[str, dict[str, int]]
    manifest: dict[str, Any] = field(default_factory=dict)


def clean_actuals(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """FUELHH -> one row per half-hour startTime, actual_mw in average MW.

    - Keep fuelType WIND only (defensive: ingest already filters by fuelType).
    - Drop null generation, counted (R11: excluded and counted, never filled).
    - If a startTime repeats, keep the latest publishTime: a later publish is
      Elexon's revision of the same half-hour.
    """
    counts = {"rows_in": len(raw)}
    df = raw[raw["fuelType"] == "WIND"].copy()
    counts["non_wind"] = len(raw) - len(df)
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)

    nulls = df["generation"].isna()
    counts["null_generation"] = int(nulls.sum())
    df = df[~nulls]

    before = len(df)
    df = df.sort_values(["startTime", "publishTime"]).drop_duplicates("startTime", keep="last")
    counts["revised_duplicates"] = before - len(df)

    df = df.rename(columns={"generation": "actual_mw"})
    out = df[["startTime", "publishTime", "settlementDate", "settlementPeriod", "actual_mw"]]
    counts["rows_out"] = len(out)
    return out.reset_index(drop=True), counts


def clean_forecasts(raw: pd.DataFrame) -> tuple[pd.DataFrame, dict[str, int]]:
    """WINDFOR -> (publishTime, startTime) unique rows with forecast_mw (MW) and horizon_h.

    - Drop null generation, counted.
    - Identical (publishTime, startTime) pairs: keep the last one seen, counted.
    - horizon_h = (startTime - publishTime) in hours (R6).
    - Drop startTime < publishTime: Elexon publishes include a few hours *before*
      the publish time, which are not forecasts and would leak hindsight into
      horizon mode. startTime == publishTime (horizon 0) is kept.
    """
    counts = {"rows_in": len(raw)}
    df = raw.copy()
    df["startTime"] = pd.to_datetime(df["startTime"], utc=True)
    df["publishTime"] = pd.to_datetime(df["publishTime"], utc=True)

    nulls = df["generation"].isna()
    counts["null_generation"] = int(nulls.sum())
    df = df[~nulls]

    before = len(df)
    df = df.drop_duplicates(["publishTime", "startTime"], keep="last")
    counts["duplicates"] = before - len(df)

    df["horizon_h"] = (df["startTime"] - df["publishTime"]).dt.total_seconds() / 3600
    past = df["horizon_h"] < 0
    counts["start_before_publish"] = int(past.sum())
    df = df[~past]

    df = df.rename(columns={"generation": "forecast_mw"})
    out = df[["publishTime", "startTime", "forecast_mw", "horizon_h"]]
    out = out.sort_values(["publishTime", "startTime"])
    counts["rows_out"] = len(out)
    return out.reset_index(drop=True), counts


def detect_resolution_min(forecasts: pd.DataFrame) -> int:
    """Median gap in minutes between consecutive startTimes within one publish.

    Decides the alignment in core/alignment.py: 30 = join half-hours directly,
    60 = average the two FUELHH half-hours of each hour first. Raises on anything
    else, because the alignment logic only supports those two.
    """
    gaps = forecasts.sort_values("startTime").groupby("publishTime")["startTime"].diff().dropna()
    minutes = int(round(gaps.median().total_seconds() / 60))
    if minutes not in (30, 60):
        raise ValueError(f"unsupported WINDFOR resolution: {minutes} min")
    return minutes


def load_snapshot(data_dir: Path) -> Snapshot:
    """Read data_dir/{fuelhh_wind,windfor}.csv.gz (+ manifest.json) and clean them."""
    actuals, a_counts = clean_actuals(pd.read_csv(data_dir / FUELHH_FILE))
    forecasts, f_counts = clean_forecasts(pd.read_csv(data_dir / WINDFOR_FILE))
    manifest_path = data_dir / MANIFEST_FILE
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    return Snapshot(
        actuals=actuals,
        forecasts=forecasts,
        resolution_min=detect_resolution_min(forecasts),
        cleaning={"actuals": a_counts, "forecasts": f_counts},
        manifest=manifest,
    )
