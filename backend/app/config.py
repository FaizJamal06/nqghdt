"""All tunables in one place (PRD §11: no magic numbers in routes).

Every field can be overridden by an env var of the same name, e.g. ``DATA_DIR=/app/data``.
"""

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings

# backend/app/config.py -> repo root. Docker overrides the paths below via env vars.
REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """App configuration. Dates are UK-local delivery dates; times are Europe/London HH:MM."""

    # R1: decision cutoff on D-1, Europe/London. Presets = the GB day-ahead gate closures.
    cutoff_default: str = "09:20"
    cutoff_presets: list[str] = ["09:20", "09:50", "15:30"]

    # R4: decisions on 1–31 Jan 2026 -> delivery days 2 Jan – 1 Feb 2026.
    delivery_first: date = date(2026, 1, 2)
    delivery_last: date = date(2026, 2, 1)

    # PRD §5.5: bands fitted on delivery days up to and including this date, tested after it.
    band_train_end: date = date(2026, 1, 20)
    # DECISIONS #38: fit only on actuals known at the first test decision (20 Jan 09:20),
    # i.e. periods starting before band_train_end at this UK time.
    train_known_before: str = "09:00"
    band_central_default: float = 0.8  # Decision View band = P10-P90 (DECISIONS #3)
    # DECISIONS #21, #42: cells = horizon buckets x forecast-level bins. The 2-bucket horizon
    # split showed no consistent width difference, so both modes use wind level only.
    band_horizon_buckets: int = 1
    band_level_bins: int = 3
    band_min_cell: int = 40  # fewer train rows -> fall back to horizon bucket, then pooled
    # DECISIONS #22: every January period has a forecast up to 40 h ahead (589/744 at 48 h).
    horizon_max_h: float = 40
    # DECISIONS #5: peak block = periods starting 16:00-18:30 UK local.
    peak_hours: tuple[int, int] = (16, 19)
    # DECISIONS #29: the centre bands and planner sit on. Fitted on train days only.
    # proportional won test MAE at all three cutoffs (DECISIONS #39, confirmed).
    correction: Literal["raw", "constant", "linear", "proportional"] = "proportional"

    # PRD §4 fetch windows, padded so every preset cutoff, horizon mode and the
    # "latest before delivery" comparison have data at both edges of the window.
    fuelhh_from: date = date(2026, 1, 1)  # settlement dates, inclusive
    fuelhh_to: date = date(2026, 2, 2)
    windfor_from: datetime = datetime(2025, 12, 30, tzinfo=UTC)  # publish times, UTC
    windfor_to: datetime = datetime(2026, 2, 2, tzinfo=UTC)  # exclusive

    data_mode: Literal["snapshot", "live"] = "snapshot"
    data_dir: Path = REPO_ROOT / "data" / "raw"
    # Built React app. If the directory exists, FastAPI serves it (single-container deploy).
    static_dir: Path = REPO_ROOT / "frontend" / "dist"
