"""Liveness and "what data exists" (PRD §8)."""

from fastapi import APIRouter

from app.api.deps import Store
from app.core.timeutils import delivery_days
from app.schemas import CorrectionInfo, HealthResponse, MetaResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe for Docker HEALTHCHECK and the deploy platform."""
    return HealthResponse(status="ok")


@router.get("/meta", response_model=MetaResponse)
def meta(store: Store) -> MetaResponse:
    """Delivery window, snapshot provenance, cleaning counts and the defaults the UI starts from."""
    s, snap = store.s, store.snap
    default = store.key("cutoff", s.cutoff_default, 0)
    corr = store.fitted(default).correction
    return MetaResponse(
        delivery_days=delivery_days(s.delivery_first, s.delivery_last),
        band_train_end=s.band_train_end,
        train_known_before_local=s.train_known_before,
        forecast_resolution_min=snap.resolution_min,
        snapshot_fetched_at=snap.manifest.get("fetched_at"),
        row_counts={"actuals": len(snap.actuals), "forecasts": len(snap.forecasts)},
        cleaning=snap.cleaning,
        coverage=store.scored(default)[1],
        cutoff_default=s.cutoff_default,
        cutoff_presets=s.cutoff_presets,
        horizon_max_h=s.horizon_max_h,
        band_central_default=s.band_central_default,
        correction=CorrectionInfo(kind=corr.kind, a=corr.a, b=corr.b),
    )
