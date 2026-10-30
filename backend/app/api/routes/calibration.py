"""Band trust and model transparency: coverage, cells, correction candidates (PRD §8)."""

from fastapi import APIRouter

from app.api.deps import SelectedMode, Store, records
from app.core import bands
from app.schemas import CalibrationResponse, CorrectionInfo

router = APIRouter()


@router.get("/calibration", response_model=CalibrationResponse)
def calibration(store: Store, m: SelectedMode) -> CalibrationResponse:
    """Nominal vs observed band coverage (train and test, with by-day range), the fitted
    cells, and every correction candidate scored on the test window only."""
    fit = store.fitted(m.key)
    levels, compare = store.calibration(m.key)
    compare = compare.rename_axis("kind").reset_index()  # a copy: the cached frame stays as is
    q_cols = [c for c in compare.columns if c.startswith("bias_q")]
    compare["bias_by_quintile"] = compare[q_cols].values.tolist()
    return CalibrationResponse(
        levels=records(levels),
        cells=records(bands.cell_table(fit.model)),
        correction=CorrectionInfo(kind=fit.correction.kind, a=fit.correction.a, b=fit.correction.b),
        corrections=records(compare.drop(columns=q_cols)),
    )
