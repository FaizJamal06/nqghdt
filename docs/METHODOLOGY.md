# Methodology

_Status: data section complete (M1). Metric, band and planner sections are added in M2–M5._

## Data

| | FUELHH (actuals) | WINDFOR (forecasts) |
|---|---|---|
| Endpoint | `/datasets/FUELHH/stream`, `fuelType=WIND` | `/datasets/WINDFOR/stream` |
| Fetched for | settlement dates 1 Jan – 2 Feb 2026 | publish times 30 Dec 2025 00:00 UTC – 2 Feb 2026 00:00 UTC |
| Resolution | 30 min (average MW per settlement period) | **60 min** (hourly `startTime`s) |
| Rows (raw → clean) | 1,584 → 1,584 | 19,856 → 15,775 |

The data is fetched once, one day per request, by `python -m app.data.ingest` and committed to `data/raw/`. The app never calls Elexon at runtime. The fetch windows are padded by a day or more on each side, so every cutoff preset, horizon mode and the "latest before delivery" comparison have data at the edges of the window.

**Cleaning** (`backend/app/data/loaders.py`). Every dropped row is counted:
- FUELHH: 0 nulls, 0 revised duplicates and 0 missing half-hours in 2 Jan – 1 Feb.
- WINDFOR: 0 nulls and 0 duplicates. **4,081 rows dropped because `startTime < publishTime`.** Each publish repeats a few hours before its own publish time. Those rows aren't forecasts, and keeping them would leak hindsight into horizon mode.

## Decision window (R4)

"Decisions made in January 2026" means decisions on 1–31 Jan. Each decision is about the next day, so the **delivery days are 2 Jan – 1 Feb 2026** (UK local dates). That gives 31 days × 24 hourly forecast periods = **744 scored periods**.

## Forecast resolution

WINDFOR forecasts are hourly and FUELHH actuals are half-hourly. Each forecast hour is compared with the **mean of its two FUELHH half-hours** (e.g. the 17:00 forecast against the average of 17:00 and 17:30). An hour with only one half-hour of actuals is excluded and counted. January has none. Energy figures use `dt_h = 1.0` hour per period.

## Forecast publishing pattern (January 2026)

- 8 publishes a day at **02:30, 04:30, 07:30, 09:30, 11:30, 15:30, 18:30, 22:30** UK time. The 11:30 publish appeared at 12:25 on one day. No other gaps.
- Each publish covers about 47–67 hourly periods ahead.
- At the **09:20** cutoff, the latest forecast is always the **07:30 publish (110 min old)**. It covers all 24 hours of D, at horizons of **16.5 h** (D 00:00) to **39.5 h** (D 23:00).
- The 09:30 publish arrives 10 minutes *after* the EPEX gate, so it can only inform the N2EX auction (09:50 cutoff preset).
