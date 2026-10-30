# Methodology

_Status: data section (M1); horizon cap, bias diagnosis and correction (M2). Metric, band and planner write-ups are completed in M5._

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
- All publish times are on the whole minute (`hh:mm:00`). Every January delivery hour gets the same publish from each preset: 09:20 → 07:30, 09:50 → 09:30, 15:30 → 15:30 (a forecast published exactly at the cutoff counts as available).

## Fixed-horizon mode is capped at 40 hours

Horizon mode asks "how good is a forecast made *h* hours ahead?" Up to h = 40, every one of the 744 periods has such a forecast. Beyond that, coverage drops (713 periods at 44 h, 589 at 48 h), because a publish only reaches 47–67 hours ahead. A curve over h would then compare different, smaller sets of hours, so the slider stops at 40 h.

## Why the forecast ran high (bias diagnosis)

At the 09:20 cutoff the forecast was too high in 85% of hours (mean error −1,748 MW). Actual ÷ forecast by forecast-level quintile:

| Forecast quintile | Forecast range (MW) | Actual ÷ forecast | Mean error (MW) |
|---|---|---|---|
| 1 (lowest) | 3,161–8,214 | 0.94 | −380 |
| 2 | 8,230–11,282 | 0.85 | −1,425 |
| 3 | 11,302–14,959 | 0.88 | −1,567 |
| 4 | 15,013–18,097 | 0.89 | −1,913 |
| 5 (highest) | 18,098–21,064 | 0.82 | −3,453 |

The ratio is below 1 at every level, which is **consistent with a general scaling or coverage gap** (e.g. the forecast and the metered actuals covering slightly different wind capacity). It is lowest in the windiest fifth, which is **consistent with curtailment** (wind farms told to reduce output). Neither can be confirmed from these two datasets. The bias also barely shrinks closer to delivery (−1,474 MW at 1 h ahead vs −1,849 MW at 40 h), so it isn't a forecasting-horizon problem.

## Forecast correction (post-processing)

Three centres, fitted on delivery days 2–20 Jan and scored **only** on 21 Jan – 1 Feb (288 hours). The input is the forecast alone; no actual is used as an input.

| 09:20 cutoff | Fitted on 2–20 Jan | Test MAE | Test RMSE | Test bias | Hours over-forecast |
|---|---|---|---|---|---|
| Raw WINDFOR | — | 2,417 | 2,790 | −2,415 | 100% |
| Constant | forecast − 1,327 MW | 1,331 | 1,771 | −1,088 | 74% |
| Linear | 1,387 + 0.768 × forecast | 1,132 | 1,590 | −288 | 54% |

Linear is best at all three cutoff presets. A constant shift changes the centre line but not the bands or the planner: shifting the centre by *a* shifts the residuals by −*a*, so the two cancel. Limitation: the parameters come from 19 days, and the model is frozen at the end of 20 Jan, so the first test decision (made 20 Jan 09:20) uses a fit that includes about 15 hours it couldn't yet have seen.
