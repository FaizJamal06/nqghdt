"""Decision View: one delivery day as the trader saw it at the gate (PRD §8)."""

from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import Confidence, SelectedMode, Store, check_date, records
from app.core.alignment import expected_starts
from app.core.decision import day_periods, day_totals, freshness
from app.core.planner import alpha_from_confidence
from app.core.timeutils import decision_cutoff
from app.schemas import CorrectionInfo, DecisionResponse

router = APIRouter()
BAND_LEVELS = (0.5, 0.8, 0.9)  # DECISIONS #3: P25-P75, P10-P90, P5-P95


@router.get("/decision", response_model=DecisionResponse)
def decision(
    store: Store,
    m: SelectedMode,
    date: Date,
    confidence: Confidence = 0.8,
    band: Annotated[float | None, Query(description="central band: 0.5, 0.8 or 0.9")] = None,
) -> DecisionResponse:
    """Periods with forecast, centre, band, planned wind, revision, flags; actuals as hindsight."""
    day = check_date(store, date)
    central = store.s.band_central_default if band is None else band
    if central not in BAND_LEVELS:
        raise HTTPException(422, f"band must be one of {BAND_LEVELS}")
    fit, alpha = store.fitted(m.key), alpha_from_confidence(confidence)
    frame = store.day_frame(m.key, day)
    periods = day_periods(frame, fit.model, central, alpha, store.s.revision_flag_mw)

    cutoff_utc = decision_cutoff(day, m.cutoff) if m.mode == "cutoff" else None
    rows = records(
        periods.rename(columns={"startTime": "start_time", "publishTime": "publish_time"})
    )
    return DecisionResponse(
        date=day,
        mode=m.mode,
        cutoff_local=m.cutoff if cutoff_utc is not None else None,
        cutoff_utc=cutoff_utc,
        sample="in-sample" if day <= store.s.band_train_end else "out-of-sample",
        freshness=freshness(store.publish_times, cutoff_utc) if cutoff_utc is not None else None,
        band_central=central,
        alpha=alpha,
        correction=CorrectionInfo(kind=fit.correction.kind, a=fit.correction.a, b=fit.correction.b),
        periods=rows,
        totals=day_totals(periods, store.s.peak_hours),
        coverage={
            "expected": len(expected_starts(day, day, store.snap.resolution_min)),
            "with_forecast": len(periods),
            "with_actual": int(periods["actual_mw"].notna().sum()),
        },
    )
