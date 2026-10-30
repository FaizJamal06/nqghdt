"""Overview chart: the whole month, forecast-at-selection vs centre vs actual (PRD §8)."""

from fastapi import APIRouter

from app.api.deps import SelectedMode, Store, records
from app.core import correction
from app.schemas import TimeseriesResponse

router = APIRouter()


@router.get("/timeseries", response_model=TimeseriesResponse)
def timeseries(store: Store, m: SelectedMode) -> TimeseriesResponse:
    """One point per scored period (744 in January), UTC start times."""
    scored = correction.with_centre(store.scored(m.key)[0], store.fitted(m.key).correction)
    cols = ["startTime", "forecast_mw", "centre_mw", "actual_mw", "error_mw"]
    return TimeseriesResponse(
        points=records(scored[cols].rename(columns={"startTime": "start_time"}))
    )
