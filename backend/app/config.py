"""All tunables in one place (PRD §11: no magic numbers in routes).

Every field can be overridden by an env var of the same name, e.g. ``DATA_DIR=/app/data``.
"""

from datetime import date
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

    data_mode: Literal["snapshot", "live"] = "snapshot"
    data_dir: Path = REPO_ROOT / "data" / "raw"
    # Built React app. If the directory exists, FastAPI serves it (single-container deploy).
    static_dir: Path = REPO_ROOT / "frontend" / "dist"
