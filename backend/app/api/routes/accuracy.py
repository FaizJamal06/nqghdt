"""Forecast Trust page: how wrong, when, how often (PRD §8, DECISIONS #23-26)."""

from collections.abc import Callable
from typing import Any

import pandas as pd
from fastapi import APIRouter

from app.api.deps import SelectedMode, Store, records
from app.core import bands, metrics
from app.schemas import AccuracyResponse

router = APIRouter()
LEVEL_NAMES = ["low", "mid", "high"]


def _breakdown(scored: pd.DataFrame, by: pd.Series, label: Callable[[Any], str]) -> list[dict]:
    """metrics.breakdown grouped on the raw values (so they sort), then labelled as `key`."""
    rows = metrics.breakdown(scored.assign(key=by), "key")
    rows["key"] = rows["key"].map(label)
    return records(rows)


def _compare(table: pd.DataFrame) -> list[dict[str, object]]:
    return records(table.rename_axis("name").reset_index())


@router.get("/accuracy", response_model=AccuracyResponse)
def accuracy(store: Store, m: SelectedMode) -> AccuracyResponse:
    """Every accuracy number for the selected mode, on the forecast the trader had (R3)."""
    scored, coverage = store.scored(m.key)
    level = bands.assign_bins(scored, store.fitted(m.key).model)["level_bin"]
    names = LEVEL_NAMES if store.s.band_level_bins == 3 else None
    label = m.cutoff if m.mode == "cutoff" else f"h={m.horizon_h:g}"
    latest = store.scored(("horizon", 0.0))[0]
    worst = metrics.worst_misses(scored).rename(columns={"startTime": "start_time"})
    shortfall = metrics.max_shortfall(scored)
    return AccuracyResponse(
        summary=metrics.summary(scored),
        quantiles=metrics.quantiles(scored),
        exceedance=metrics.exceedance(scored),
        max_shortfall={"error_mw": shortfall["error_mw"], "start_time": shortfall["startTime"]},
        breakdowns={
            "by_hour": _breakdown(scored, scored["hour_uk"], lambda h: f"{h:02d}:00"),
            "by_level": _breakdown(scored, level, lambda b: names[b] if names else str(b)),
            "by_day": _breakdown(scored, scored["delivery_date"], str),
        },
        histogram=records(metrics.histogram(scored)),
        worst_misses=records(worst),
        comparison=_compare(
            metrics.on_common_periods({label: scored, "latest_before_delivery": latest})
        ),
        value_of_waiting=_compare(store.value_of_waiting()),
        lead_time=records(store.lead_time()),
        bias_by_level=records(metrics.ratio_by_level(scored)),
        coverage=coverage,
    )
