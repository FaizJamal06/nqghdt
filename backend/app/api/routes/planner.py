"""Buffer planner: a confidence or cost ratio -> planned wind + policy backtest (PRD §8, R9)."""

from datetime import date as Date
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import Confidence, SelectedMode, Store, check_date, records
from app.core import planner as core
from app.core.decision import day_periods
from app.schemas import PlannerResponse

router = APIRouter()
Positive = Annotated[float | None, Query(gt=0, description="cost ratio part, e.g. 3 and 1")]
Price = Annotated[float | None, Query(gt=0, description="GBP/MWh, your assumption")]


@router.get("/planner", response_model=PlannerResponse)
def planner(
    store: Store,
    m: SelectedMode,
    confidence: Confidence = 0.8,
    c_short: Positive = None,
    c_long: Positive = None,
    price_short: Price = None,
    price_long: Price = None,
    date: Date | None = None,
) -> PlannerResponse:
    """alpha from (priority) c_short:c_long, then £/MWh prices, then 1 - confidence.

    The backtest runs on the test window only (21 Jan - 1 Feb). With prices, each policy
    also gets cost_gbp = price_short x shortfall + price_long x excess (DECISIONS #6).
    """
    if (c_short is None) != (c_long is None) or (price_short is None) != (price_long is None):
        raise HTTPException(422, "give both c_short and c_long (or both prices), or neither")
    if c_short is not None and c_long is not None:
        alpha, source = core.alpha_from_costs(c_short, c_long), "cost_ratio"
    elif price_short is not None and price_long is not None:
        alpha, source = core.alpha_from_costs(price_short, price_long), "prices"
    else:
        alpha, source = core.alpha_from_confidence(confidence), "confidence"
    prices = (price_short, price_long) if price_short and price_long else None

    fit = store.fitted(m.key)
    day = None
    if date is not None:
        frame = store.day_frame(m.key, check_date(store, date))
        rows = day_periods(frame, fit.model, store.s.band_central_default, alpha)
        day = records(rows.rename(columns={"startTime": "start_time"}))
    return PlannerResponse(
        alpha=alpha,
        alpha_source=source,
        policies=records(core.backtest(fit.model, fit.test, alpha, prices)),
        n_test=len(fit.test),
        n_test_days=fit.test["delivery_date"].nunique(),
        day=day,
    )
