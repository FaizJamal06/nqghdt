// TypeScript mirror of backend/app/schemas.py (the parts the M4 pages use).
// Units: MW, MWh, hours. Datetimes are UTC ISO strings; *_local / local_time are UK clock.

export type Mode = "cutoff" | "horizon";

export interface CorrectionInfo {
  kind: "raw" | "constant" | "linear" | "proportional";
  a: number;
  b: number;
}

export interface Coverage {
  expected: number;
  scored: number;
  missing_forecast: number;
  missing_actual: number;
}

export interface Meta {
  delivery_days: string[];
  band_train_end: string;
  train_known_before_local: string;
  forecast_resolution_min: number;
  snapshot_fetched_at: string | null;
  cutoff_default: string;
  cutoff_presets: string[];
  horizon_max_h: number;
  band_central_default: number;
  correction: CorrectionInfo;
  coverage: Coverage;
}

export type Flag = "low_wind" | "big_revision";

export interface Period {
  start_time: string;
  local_time: string;
  sp: number;
  publish_time: string;
  horizon_h: number;
  forecast_mw: number;
  centre_mw: number;
  band_low_mw: number;
  band_high_mw: number;
  planned_mw: number;
  previous_mw: number | null;
  revision_mw: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  flags: Flag[];
}

export interface DayTotals {
  forecast_mwh: number;
  centre_mwh: number;
  planned_mwh: number;
  extra_mwh: number;
  peak_forecast_mwh: number;
  peak_planned_mwh: number;
  actual_mwh: number | null;
  peak_actual_mwh: number | null;
  error_mwh: number | null; // trusting WINDFOR: actual − forecast (negative = short)
  peak_error_mwh: number | null;
  plan_error_mwh: number | null; // following the plan: actual − planned
  peak_plan_error_mwh: number | null;
}

export interface Decision {
  date: string;
  mode: Mode;
  cutoff_local: string | null;
  cutoff_utc: string | null;
  sample: "in-sample" | "out-of-sample";
  freshness: {
    latest_publish: string;
    minutes_before_cutoff: number;
    is_stale: boolean;
  } | null;
  band_central: number;
  alpha: number;
  correction: CorrectionInfo;
  periods: Period[];
  totals: DayTotals;
  coverage: { expected: number; with_forecast: number; with_actual: number };
}

export interface Summary {
  n: number;
  n_days: number;
  mae: number;
  rmse: number;
  bias: number;
  nmae: number;
  nrmse: number;
  pct_over_forecast: number;
}

export interface CompareRow {
  name: string;
  n: number;
  mae: number;
  rmse: number;
  bias: number;
  pct_over_forecast: number;
}

export interface BreakdownRow {
  key: string;
  n: number;
  mae: number;
  rmse: number;
  bias: number;
}

export interface Miss {
  start_time: string;
  delivery_date: string;
  sp: number;
  forecast_mw: number;
  actual_mw: number;
  error_mw: number;
  horizon_h: number;
}

export interface LevelRatio {
  quintile: number;
  n: number;
  forecast_min: number;
  forecast_max: number;
  mean_forecast: number;
  mean_actual: number;
  ratio: number;
  bias: number;
}

export interface Accuracy {
  summary: Summary;
  quantiles: Record<string, number>;
  exceedance: Record<string, number>;
  breakdowns: { by_hour: BreakdownRow[]; by_level: BreakdownRow[] };
  histogram: { lo_mw: number; hi_mw: number; count: number }[];
  worst_misses: Miss[];
  value_of_waiting: CompareRow[];
  comparison: CompareRow[];
  lead_time: { horizon_h: number; n: number; mae: number; bias: number }[];
  bias_by_level: LevelRatio[];
}

export interface Calibration {
  levels: {
    nominal: number;
    train_picp: number;
    test_picp: number;
    test_lo: number;
    test_hi: number;
    n_train: number;
    n_test: number;
  }[];
  cells: {
    level_bin: number;
    lo_mw: number | null;
    hi_mw: number | null;
    n: number;
    p10: number;
    p90: number;
    width: number;
  }[];
  correction: CorrectionInfo;
  corrections: {
    kind: CorrectionInfo["kind"];
    a: number;
    b: number;
    n: number;
    mae: number;
    rmse: number;
    bias: number;
    pct_over_forecast: number;
    bias_by_quintile: number[];
  }[];
}

export interface Policy {
  policy: "raw" | "P50" | "P20" | "P10" | "yours";
  alpha: number | null;
  pct_short: number;
  shortfall_mwh: number;
  excess_mwh: number;
  extra_mwh: number;
  cost_gbp: number | null;
}

export interface Planner {
  alpha: number;
  alpha_source: "confidence" | "cost_ratio" | "prices";
  policies: Policy[];
  n_test: number;
  n_test_days: number;
}

export interface Point {
  start_time: string;
  forecast_mw: number;
  centre_mw: number;
  actual_mw: number;
  error_mw: number;
}

export interface Timeseries {
  points: Point[];
}
