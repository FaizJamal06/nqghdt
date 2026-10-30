"""Response contracts for every /api endpoint (PRD §8). Mirrored by frontend/src/api/types.ts.

Units: power in MW, energy in MWh, horizons in hours, money in GBP. Datetimes are UTC
(ISO 8601, "Z"); fields named *_local are Europe/London wall-clock strings.
Every metric block carries n (periods) and, where it summarises days, n_days.
"""

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: Literal["ok"]


# ---------- shared blocks ----------


class Coverage(BaseModel):
    expected: int
    scored: int
    missing_forecast: int
    missing_actual: int


class Summary(BaseModel):
    n: int
    n_days: int
    mae: float
    rmse: float
    bias: float
    nmae: float
    nrmse: float
    pct_over_forecast: float


class CompareRow(BaseModel):
    """Same-period comparison row (honest vs flattering, value of waiting)."""

    name: str
    n: int
    mae: float
    rmse: float
    bias: float
    pct_over_forecast: float


class CorrectionInfo(BaseModel):
    """The configured centre: centre_mw = max(a + b x forecast_mw, 0)."""

    kind: str
    a: float
    b: float


# ---------- /api/meta ----------


class MetaResponse(BaseModel):
    delivery_days: list[date]
    band_train_end: date
    train_known_before_local: str
    forecast_resolution_min: int
    snapshot_fetched_at: str | None
    row_counts: dict[str, int]
    cleaning: dict[str, dict[str, int]]
    coverage: Coverage
    cutoff_default: str
    cutoff_presets: list[str]
    horizon_max_h: float
    band_central_default: float
    correction: CorrectionInfo


# ---------- /api/decision ----------


class Freshness(BaseModel):
    latest_publish: datetime
    minutes_before_cutoff: float
    is_stale: bool


class Period(BaseModel):
    start_time: datetime
    local_time: str
    sp: int
    publish_time: datetime
    horizon_h: float
    forecast_mw: float
    centre_mw: float
    band_low_mw: float
    band_high_mw: float
    planned_mw: float
    previous_mw: float | None
    revision_mw: float | None
    actual_mw: float | None  # hindsight: hidden in the UI by default (R3)
    error_mw: float | None
    flags: list[Literal["low_wind", "big_revision"]]


class DayTotals(BaseModel):
    forecast_mwh: float
    centre_mwh: float
    planned_mwh: float
    extra_mwh: float
    peak_forecast_mwh: float
    peak_planned_mwh: float
    actual_mwh: float | None
    peak_actual_mwh: float | None
    # Hindsight, gross like the planner: short = sum max(planned - actual, 0) x dt_h, long the reverse.
    raw_short_mwh: float | None  # trusting WINDFOR
    raw_long_mwh: float | None
    peak_raw_short_mwh: float | None
    peak_raw_long_mwh: float | None
    plan_short_mwh: float | None  # following the plan
    plan_long_mwh: float | None
    peak_plan_short_mwh: float | None
    peak_plan_long_mwh: float | None


class DayCoverage(BaseModel):
    expected: int
    with_forecast: int
    with_actual: int


class DecisionResponse(BaseModel):
    date: date
    mode: Literal["cutoff", "horizon"]
    cutoff_local: str | None
    cutoff_utc: datetime | None
    sample: Literal["in-sample", "out-of-sample"]
    freshness: Freshness | None  # cutoff mode only
    band_central: float
    alpha: float
    correction: CorrectionInfo
    periods: list[Period]
    totals: DayTotals
    coverage: DayCoverage


# ---------- /api/accuracy ----------


class BreakdownRow(BaseModel):
    key: str
    n: int
    mae: float
    rmse: float
    bias: float


class Breakdowns(BaseModel):
    by_hour: list[BreakdownRow]
    by_level: list[BreakdownRow]
    by_day: list[BreakdownRow]


class HistogramBin(BaseModel):
    lo_mw: float
    hi_mw: float
    count: int


class Miss(BaseModel):
    start_time: datetime
    delivery_date: date
    sp: int
    forecast_mw: float
    actual_mw: float
    error_mw: float
    horizon_h: float


class LeadTimePoint(BaseModel):
    horizon_h: int
    n: int
    mae: float
    bias: float


class LevelRatio(BaseModel):
    quintile: int
    n: int
    forecast_min: float
    forecast_max: float
    mean_forecast: float
    mean_actual: float
    ratio: float
    bias: float


class MaxShortfall(BaseModel):
    error_mw: float
    start_time: datetime


class AccuracyResponse(BaseModel):
    summary: Summary
    quantiles: dict[str, float]
    exceedance: dict[str, float]
    max_shortfall: MaxShortfall
    breakdowns: Breakdowns
    histogram: list[HistogramBin]
    worst_misses: list[Miss]
    comparison: list[CompareRow]  # this mode vs latest-before-delivery, same periods
    value_of_waiting: list[CompareRow]  # cutoff presets, same periods
    lead_time: list[LeadTimePoint]  # horizon mode h = 1..max, independent of mode
    bias_by_level: list[LevelRatio]
    coverage: Coverage


# ---------- /api/calibration ----------


class CalibrationLevel(BaseModel):
    nominal: float
    train_picp: float
    test_picp: float
    test_lo: float  # by-day bootstrap, 5th percentile
    test_hi: float  # 95th percentile
    n_train: int
    n_test: int


class Cell(BaseModel):
    horizon_bucket: int
    level_bin: int
    lo_mw: float | None
    hi_mw: float | None
    n: int
    p10: float
    p90: float
    width: float


class CorrectionRow(BaseModel):
    kind: str
    a: float
    b: float
    n: int
    mae: float
    rmse: float
    bias: float
    pct_over_forecast: float
    bias_by_quintile: list[float]  # calmest first


class CalibrationResponse(BaseModel):
    levels: list[CalibrationLevel]
    cells: list[Cell]
    correction: CorrectionInfo
    corrections: list[CorrectionRow]  # all candidates, test window only


# ---------- /api/planner ----------


class Policy(BaseModel):
    policy: str
    alpha: float | None
    pct_short: float
    shortfall_mwh: float
    excess_mwh: float
    extra_mwh: float
    cost_gbp: float | None = None


class PlannerPeriod(BaseModel):
    start_time: datetime
    local_time: str
    forecast_mw: float
    centre_mw: float
    planned_mw: float
    actual_mw: float | None


class PlannerResponse(BaseModel):
    alpha: float
    alpha_source: Literal["confidence", "cost_ratio", "prices"]
    policies: list[Policy]
    n_test: int
    n_test_days: int
    day: list[PlannerPeriod] | None


# ---------- /api/timeseries ----------


class Point(BaseModel):
    start_time: datetime
    forecast_mw: float
    centre_mw: float
    actual_mw: float
    error_mw: float


class TimeseriesResponse(BaseModel):
    points: list[Point]
