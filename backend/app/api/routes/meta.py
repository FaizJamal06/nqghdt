"""Liveness and dataset metadata endpoints. /api/meta arrives in M3."""

from fastapi import APIRouter

from app.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness probe for Docker HEALTHCHECK and the deploy smoke test."""
    return HealthResponse(status="ok")
