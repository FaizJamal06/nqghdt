# Methodology

_Status: final (M7); every number here is reproduced by `python -m app.report` from `backend/`. The in-app Methodology page (`/methodology`) is the short version of this file; its data-dependent numbers come from `/api/meta` and `/api/calibration`._

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

## Sign convention and metrics

**Error = actual − forecast** (R7). Negative = less wind than forecast = the desk is short and buys the gap; red always means short in the UI.

- **MAE**: mean |error|, MW. **RMSE**: root mean squared error, MW; big misses weigh more. **Bias**: mean error, MW.
- **nMAE / nRMSE**: the same as a % of mean actual (in the API, not headlined).
- **Quantiles** (P5…P95) of the error; **exceedance**: % of hours short by more than 1 GW / 2 GW.
- **Coverage (PICP)**: share of hours whose actual lies inside the band.
- Every metric carries `n` (hours) and `n_days`; comparisons (honest vs flattering, value of waiting) are computed on the **same hours** for each side.

**Why not MAPE?** It divides by the actual, so calm hours (a few hundred MW) dominate the average and a 500 MW miss can read as 100%. It also treats over- and under-forecasts asymmetrically. The desk pays for MW and MWh, so errors stay in MW.

**Headline numbers (09:20 cutoff, 744 hours, 31 days).** MAE 2,039 MW, RMSE 2,505 MW, bias −1,748 MW (too high in 85% of hours). P10 −4,098 MW, P90 +549 MW. Short by more than 1 GW in 68% of hours. Worst miss: **12 Jan 01:00**, forecast 20,942 MW vs actual 14,072 MW (−6,870 MW, 17.5 h ahead); the hours around it on that night were almost as bad.

**Honest vs flattering.** Scoring the last forecast before delivery (MAE 1,687 MW) instead of the one available at 09:20 (2,039 MW) would make WINDFOR look 17% better than what the trader could act on.

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

Four candidate centres. The input is the forecast alone; no actual is ever an input.

- **Fit (corrections *and* band quantiles):** only hours whose actual was known at the first test decision, i.e. starting before **20 Jan 09:00 UK** (that decision is made at 20 Jan 09:20). That is 441 hours, 2 Jan 00:00 – 20 Jan 08:00.
- **Test:** delivery days 21 Jan – 1 Feb (288 hours). Hours 20 Jan 09:00–23:00 are in neither set.

| 09:20 cutoff | Fitted | Test MAE | Test RMSE | Test bias | Hours over-forecast | Test bias, calmest fifth |
|---|---|---|---|---|---|---|
| Raw WINDFOR | — | 2,417 | 2,790 | −2,415 | 100% | −1,937 |
| Constant | forecast − 1,345 MW | 1,322 | 1,760 | −1,070 | 74% | −593 |
| Linear | 1,460 + 0.756 × forecast | 1,153 | 1,597 | −186 | 50% | −1,300 |
| **Proportional** | **0.865 × forecast** | **1,032** | **1,465** | −370 | 57% | −775 |

Test bias by forecast-level fifth, calmest first (MW):

| | 1 | 2 | 3 | 4 | 5 |
|---|---|---|---|---|---|
| Raw | −1,937 | −2,938 | −1,870 | −2,164 | −3,168 |
| Linear | −1,300 | −1,326 | +732 | +781 | +180 |
| Proportional | −775 | −1,236 | +381 | +277 | −503 |

Linear's intercept *raises* every forecast below ~6,000 MW, although actual ÷ forecast is below 1 at every level, so it leaves the calm hours most over-forecast. Proportional scales every hour down and has the lowest test MAE at all three cutoffs (09:50: 997 vs 1,106; 15:30: 770 vs 920). A constant shift changes the centre line but not the bands or the planner: shifting the centre by *a* shifts the residuals by −*a*, so the two cancel.

**Does the correction improve the decision?** Planner at 80% confidence, test window:

| Centre | Hours short | Shortfall MWh | Excess MWh | Extra MWh bought vs raw forecast |
|---|---|---|---|---|
| Raw | 21% | 107,985 | 416,371 | 1,003,797 |
| Linear | 23% | 106,754 | 370,598 | 959,254 |
| **Proportional** (default) | 22% | 108,191 | 388,741 | 975,961 |

Only a little. The planner already plans at a quantile of past *residuals*, so it absorbs most of the bias even around the raw forecast. The proportional centre leaves the share of hours short and the shortfall essentially unchanged and cuts unneeded buying (excess) by about 7%. It mainly improves the centre line.

## Uncertainty bands

**Cells.** Residuals (actual − centre) are grouped by forecast level: terciles of the train forecasts, edges **8,868 MW and 13,650 MW**, 147 train hours per cell. The planned split by horizon (< 27.5 h vs ≥ 27.5 h) was dropped. Its P10–P90 widths showed no consistent pattern (shorter horizon *narrower* for low wind, 3,668 vs 4,053 MW, but *wider* for mid, 3,144 vs 2,897, and high, 4,652 vs 4,145), so splitting only halved each cell's data. Both modes now use the same 3 level cells.

| Cell (proportional centre, train) | P10 (MW) | P90 (MW) | P10–P90 width (MW) |
|---|---|---|---|
| Low wind (< 8,868 MW) | −1,376 | +2,551 | 3,928 |
| Mid wind | −678 | +2,179 | 2,857 |
| High wind (> 13,650 MW) | −2,935 | +1,644 | 4,578 |

The mid-wind cell is narrower than low-wind, but a by-day bootstrap of the width difference spans −621 to +2,327 MW (5th–95th percentile), which includes zero. With 19 days it can't be told apart from noise.

**Coverage on the test window** (by-day bootstrap, 5th–95th percentile):

| Nominal | Raw | Linear | Proportional (default) |
|---|---|---|---|
| 50% | 65% (52–76) | 58% (47–68) | 63% (51–74) |
| 80% | 81% (67–92) | 77% (63–90) | 80% (66–92) |
| 90% | 90% (76–99) | 87% (73–97) | 89% (74–98) |

The 50% band over-covers on the test window (63%, range 51–74%), while the 80% band holds (80%). The Decision View shows the 80% band by default.

## Buffer planner

Newsvendor rule (R9): plan on the alpha-quantile of likely wind, `planned = centre + q_alpha(residual | cell)`, clipped at 0 MW (R10). alpha = 1 − confidence, or c_long / (c_short + c_long) from a cost ratio or from £/MWh prices the user types in (labelled "your assumption"; nothing is assumed by default). The backtest scores raw, P50, P20, P10 and the user's alpha on the 288 test hours only: % hours short, shortfall MWh, excess MWh, MWh bought beyond the forecast and, with prices, £. At 80%: short in 22% of hours, against 287 of 288 when trusting WINDFOR, for 975,961 MWh more than the forecast (81,330 MWh a day).

## Decision View rules

For one delivery day, `core/decision.py` adds, per hour:

- **Band** (default 80%, P10–P90; 50% and 90% are selectable) and **plan on** (the planner's alpha-quantile). Both come from the same cell residuals around the centre, and both are clipped at 0 MW.
- **Flags.** `low_wind`: the forecast falls in the lowest wind-level cell (below 8,868 MW). `big_revision`: the selected forecast moved by **1,000 MW or more** since the previous publish for that hour (`revision_flag_mw`). The threshold is absolute, so a calm day flags nothing: at 09:20 it fires on 42 of 744 hours, spread over 9 days.
- **Freshness.** The latest publish at or before the cutoff, and its age. It is **stale** if older than 2 × the median gap between publishes (3 h in January, so stale after 6 h). At 09:20 the forecast is always the 07:30 publish, 110 min old.
- **Sample badge.** Days up to 20 Jan are *in-sample* (the bands saw them); 21 Jan – 1 Feb are *out-of-sample*.
- **Energy totals.** MWh = MW × 1 h, for the whole day and the 16:00–19:00 peak block. Hindsight rows, shown only with "Show what happened", are **gross**, like the planner backtest: short = Σ max(planned − actual, 0) and long = Σ max(actual − planned, 0), counted separately so that long hours can't hide short ones. On 21 Jan: trusting WINDFOR was 87,800 MWh short and 0 long; following the plan was 2,331 MWh short (03:00–07:00) and 21,056 MWh long.

## Limitations (whole app)

- **Curtailment vs coverage can't be separated.** The bias is consistent with both a scaling or coverage gap (low ratio at every level) and curtailment (lowest ratio in the windiest fifth). Telling them apart would need data on curtailment or on how the two datasets were built, which these two datasets don't contain.
- **One winter month.** The bias and spread are January's; they may differ in a calmer or summer month. A live product would refit on a rolling window.
- **About 31 independent days.** Hours within a day share weather, so days are the real sample. The test window is only 12 days, so coverage is shown with a by-day bootstrap range.
- **Model chosen on the test window.** The proportional centre was picked from 4 candidates by looking at their test numbers, so those numbers are slightly optimistic.
- **Embedded wind** (small farms on distribution networks) isn't in these figures, so they understate total GB wind output.
- **Flat £ prices understate cost**: imbalance prices tend to spike when wind under-delivers.

**Band limitations.** The cells are fitted on 19 days (441 hours, 147 per cell). Binned bands jump at the cell edges (8,868 and 13,650 MW); smoothing between cells is Phase 2.
