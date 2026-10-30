"""Fetch the January snapshot from Elexon into data/raw (PRD §4).

    python -m app.data.ingest           # fetch + write (overwrites: idempotent)
    python -m app.data.ingest --check   # report on what is already on disk

Run from backend/. January 2026 is history, so this runs once and the output is committed.
"""

import argparse
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from app.config import Settings
from app.data.elexon_client import (
    BASE_URL,
    FUELHH_PATH,
    WINDFOR_PATH,
    ElexonClient,
    FuelhhRow,
    WindforRow,
    validate_rows,
)
from app.data.loaders import FUELHH_FILE, MANIFEST_FILE, WINDFOR_FILE, load_snapshot

FUELHH_COLS = [
    "startTime",
    "settlementDate",
    "settlementPeriod",
    "publishTime",
    "fuelType",
    "generation",
]
WINDFOR_COLS = ["publishTime", "startTime", "generation"]
UK = "Europe/London"

log = logging.getLogger("ingest")


def _to_frame(rows: list[Any], cols: list[str], sort: list[str]) -> pd.DataFrame:
    df = pd.DataFrame([r.model_dump() for r in rows], columns=cols)
    return df.sort_values(sort).reset_index(drop=True)


def _write_csv_gz(df: pd.DataFrame, path: Path) -> None:
    # mtime=0 makes the gzip bytes depend only on content, so re-runs give clean git diffs.
    df.to_csv(
        path,
        index=False,
        date_format="%Y-%m-%dT%H:%M:%SZ",
        compression={"method": "gzip", "mtime": 0},
    )


def ingest(settings: Settings, client: ElexonClient) -> dict[str, Any]:
    """Fetch both datasets for the configured windows; write CSVs + manifest; return manifest."""
    out = settings.data_dir
    out.mkdir(parents=True, exist_ok=True)

    fuel_raw = [
        r for day in client.fetch_fuelhh_wind(settings.fuelhh_from, settings.fuelhh_to) for r in day
    ]
    fuel, fuel_bad = validate_rows(fuel_raw, FuelhhRow)
    log.info("FUELHH: %d rows (%d malformed)", len(fuel), fuel_bad)

    wf_raw = [
        r for day in client.fetch_windfor(settings.windfor_from, settings.windfor_to) for r in day
    ]
    wf, wf_bad = validate_rows(wf_raw, WindforRow)
    log.info("WINDFOR: %d rows (%d malformed)", len(wf), wf_bad)

    _write_csv_gz(_to_frame(fuel, FUELHH_COLS, ["startTime", "publishTime"]), out / FUELHH_FILE)
    _write_csv_gz(_to_frame(wf, WINDFOR_COLS, ["publishTime", "startTime"]), out / WINDFOR_FILE)

    manifest = {
        "fetched_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "source": BASE_URL,
        "fuelhh": {
            "url": f"{BASE_URL}{FUELHH_PATH}",
            "params": "settlementDateFrom/To per day, fuelType=WIND",
            "window": [settings.fuelhh_from.isoformat(), settings.fuelhh_to.isoformat()],
            "rows": len(fuel),
            "malformed_skipped": fuel_bad,
        },
        "windfor": {
            "url": f"{BASE_URL}{WINDFOR_PATH}",
            "params": "publishDateTimeFrom/To per day (UTC)",
            "window": [settings.windfor_from.isoformat(), settings.windfor_to.isoformat()],
            "rows": len(wf),
            "malformed_skipped": wf_bad,
        },
    }
    (out / MANIFEST_FILE).write_text(json.dumps(manifest, indent=2) + "\n", newline="\n")
    return manifest


def check(settings: Settings) -> bool:
    """Print row counts, coverage of the delivery window, resolution, duplicates.

    Returns True when every delivery day has all its actual half-hours and every
    forecast hour is covered by at least one publish. Whether the *09:20* publish
    covers the day is a selection question, answered in M2.
    """
    snap = load_snapshot(settings.data_dir)
    print(f"snapshot fetched at: {snap.manifest.get('fetched_at', '?')}")
    for name, counts in snap.cleaning.items():
        print(f"{name:9s} cleaning: {counts}")
    print(f"forecast resolution: {snap.resolution_min} min")

    days = pd.date_range(settings.delivery_first, settings.delivery_last, freq="D").date
    # Expected half-hours per UK day: 48 normally, 46/50 on clock-change days.
    local_midnights = pd.DatetimeIndex(pd.to_datetime(days)).tz_localize(UK)
    expected_hh = ((local_midnights + pd.DateOffset(days=1)) - local_midnights) / timedelta(
        minutes=30
    )

    act_day = snap.actuals["startTime"].dt.tz_convert(UK).dt.date.value_counts()
    fc_hours = snap.forecasts.drop_duplicates("startTime")["startTime"]
    fc_day = fc_hours.dt.tz_convert(UK).dt.date.value_counts()

    ok = True
    print("\ndelivery day  actual_hh/expected  forecast_slots/expected")
    for day, exp in zip(days, expected_hh, strict=True):
        a, f = int(act_day.get(day, 0)), int(fc_day.get(day, 0))
        exp_fc = int(exp) * 30 // snap.resolution_min  # 24 hourly slots, or 48 half-hours
        flag = "" if (a == exp and f == exp_fc) else "  <-- GAP"
        ok &= not flag
        print(f"{day}    {a:3d}/{int(exp):<3d}            {f:3d}/{exp_fc}{flag}")
    print(f"\nfull coverage of {days[0]} .. {days[-1]}: {'YES' if ok else 'NO'}")
    return ok


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--check", action="store_true", help="report on the snapshot on disk; no fetch"
    )
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    settings = Settings()
    if args.check:
        raise SystemExit(0 if check(settings) else 1)
    ingest(settings, ElexonClient())
    check(settings)


if __name__ == "__main__":
    main()
