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
  error_mwh: number | null;
  peak_error_mwh: number | null;
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

export interface Accuracy {
  summary: Summary;
  quantiles: Record<string, number>;
  exceedance: Record<string, number>;
  value_of_waiting: CompareRow[];
  comparison: CompareRow[];
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
