"""Shared query parameters, the DataStore dependency and DataFrame -> JSON rows.

Validation lives here so every route rejects the same bad input the same way (422).
"""

import json
from dataclasses import dataclass
from datetime import date
from typing import Annotated, Any, Literal

import pandas as pd
from fastapi import Depends, HTTPException, Query, Request

from app.data.store import DataStore, Key

HHMM = r"^([01]\d|2[0-3]):[0-5]\d$"


def get_store(request: Request) -> DataStore:
    """The app's single DataStore (created in main.create_app)."""
    store: DataStore = request.app.state.store
    return store


Store = Annotated[DataStore, Depends(get_store)]


@dataclass(frozen=True)
class Mode:
    """Validated selection mode plus its cache key."""

    mode: Literal["cutoff", "horizon"]
    cutoff: str
    horizon_h: float
    key: Key


def get_mode(
    store: Store,
    mode: Literal["cutoff", "horizon"] = "cutoff",
    cutoff: Annotated[str, Query(pattern=HHMM, description="D-1 cutoff, HH:MM UK")] = "09:20",
    horizon_h: Annotated[float, Query(ge=0, description="hours ahead, horizon mode")] = 24,
) -> Mode:
    """R1 cutoff or R8 horizon. Horizon is capped at horizon_max_h (DECISIONS #22)."""
    if horizon_h > store.s.horizon_max_h:
        raise HTTPException(422, f"horizon_h must be <= {store.s.horizon_max_h:g}")
    return Mode(mode, cutoff, horizon_h, DataStore.key(mode, cutoff, horizon_h))


SelectedMode = Annotated[Mode, Depends(get_mode)]
# D3: planner confidence capped at 0.95 (alpha >= 0.05 keeps tail quantiles estimable).
Confidence = Annotated[float, Query(ge=0.5, le=0.95, description="0.5-0.95")]


def check_date(store: DataStore, day: date) -> date:
    """422 unless day is a delivery day in the window (R4)."""
    if not store.s.delivery_first <= day <= store.s.delivery_last:
        raise HTTPException(
            422, f"date must be between {store.s.delivery_first} and {store.s.delivery_last}"
        )
    return day


def records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """DataFrame -> JSON-safe rows: NaN -> None, numpy -> Python, times -> ISO strings."""
    rows: list[dict[str, Any]] = json.loads(
        df.to_json(orient="records", date_format="iso", default_handler=str)
    )
    return rows
