// Methodology: how every number is computed, and what it can't tell you (PRD §9).
// Definitions are prose; numbers that depend on the data come from the API.
import type { ReactNode } from "react";
import { useCalibration, useMeta } from "../api/client";
import { ErrorState, Skeleton } from "../components/Status";
import {
  dayLabel,
  dayRange,
  formula,
  mw,
  splitLabels,
  ukDate,
  ukTime,
} from "../lib/format";
import { useSettings } from "../state/settings";

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="space-y-2 rounded-lg border bg-white p-4 text-sm leading-relaxed text-slate-800">
      <h2 className="text-base font-semibold text-slate-900">{title}</h2>
      {children}
    </section>
  );
}

export default function Methodology() {
  const [s] = useSettings();
  const meta = useMeta();
  const cal = useCalibration(s);
  if (meta.isError)
    return <ErrorState error={meta.error} retry={() => meta.refetch()} />;
  if (!meta.data || !cal.data) return <Skeleton className="h-96" />;
  const m = meta.data;
  const days = m.delivery_days;
  const split = splitLabels(m);
  const edges = cal.data.cells
    .map((c) => c.hi_mw)
    .filter((v): v is number => v !== null);

  return (
    <div className="mx-auto max-w-3xl space-y-4">
      <h1 className="text-xl font-semibold">Methodology</h1>

      <Section title="Data">
        <p>
          Two public Elexon BMRS datasets, fetched once and stored with the app
          {m.snapshot_fetched_at &&
            ` (snapshot ${ukDate(m.snapshot_fetched_at)} ${ukTime(m.snapshot_fetched_at)} UK)`}
          ; nothing is called at runtime.
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <b>WINDFOR</b>: national wind forecasts, one value per{" "}
            {m.forecast_resolution_min} min, republished about 8 times a day.
          </li>
          <li>
            <b>FUELHH</b> (fuel type WIND): actual generation per half-hour.
            Each forecast hour is compared with the mean of its two half-hours.
          </li>
        </ul>
        <p>
          Delivery days {dayRange(days[0], days[days.length - 1])} (decisions
          made in January): {m.coverage.scored} of {m.coverage.expected} hours
          scored; {m.coverage.missing_forecast} missing a forecast,{" "}
          {m.coverage.missing_actual} missing an actual. Missing data is
          counted, never filled.
        </p>
      </Section>

      <Section title="Which forecast counts (no look-ahead)">
        <p>
          For delivery day D the trader decides on D−1 at the cutoff, UK time
          (default {m.cutoff_default}, the EPEX day-ahead gate; presets{" "}
          {m.cutoff_presets.join(", ")}). Each hour uses the{" "}
          <b>latest forecast published at or before the cutoff</b>. A forecast
          published later is never used, even if it was better: that is the
          look-ahead the app exists to avoid.
        </p>
        <p>
          Fixed-horizon mode instead uses, for each hour, the latest forecast
          published at least h hours before it (0–{m.horizon_max_h} h; beyond{" "}
          {m.horizon_max_h} h some hours have no forecast, so the curve would
          compare different hours).
        </p>
      </Section>

      <Section title="Sign convention and metrics">
        <p>
          <b>Error = actual − forecast.</b> Negative means less wind than
          forecast: the desk is <span className="text-red-600">short</span> and
          must buy the gap. Red always means short.
        </p>
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <b>MAE</b>: average size of the miss, in MW. <b>RMSE</b>: the same,
            but big misses count more. <b>Bias</b>: average signed error.
          </li>
          <li>
            <b>P10 / P90</b>: 10% of errors fall below P10, 10% above P90.
          </li>
          <li>
            <b>Coverage</b>: the share of hours where the actual landed inside
            the band. An 80% band should catch about 80%.
          </li>
          <li>Every number shows how many hours and days it rests on (n).</li>
        </ul>
        <p>
          <b>Why not MAPE?</b> It divides by the actual, so calm hours with
          little wind blow up the average, and it punishes over- and
          under-forecasts unequally. MW errors are what the desk pays for.
        </p>
      </Section>

      <Section title="Correction, bands and the plan">
        <p>
          The forecast ran high in January, so the bands are built around a
          corrected centre: <b>{formula(cal.data.correction)}</b>. It uses the
          forecast alone, fitted only on hours whose actual was known by{" "}
          {dayLabel(m.band_train_end)} {m.train_known_before_local} (
          {split.train}), and judged on {split.test}, which it never saw.
        </p>
        <p>
          The <b>band</b> is the centre plus the 10th–90th percentile of past
          misses, taken separately for low, mid and high wind (split at{" "}
          {edges.map(mw).join(" and ")} of forecast). Never below 0 MW.
        </p>
        <p>
          The <b>plan</b> uses the newsvendor rule: plan on the alpha-quantile
          of likely wind, alpha = 1 − confidence, or cost of long ÷ (cost of
          short + cost of long). Short costs more → lower alpha → plan on less
          wind → buy more up front.
        </p>
      </Section>

      <Section title="Limitations">
        <ul className="list-disc space-y-1 pl-5">
          <li>
            <b>One month</b>: about 31 independent days, {split.test} for
            testing. Ranges are shown where it matters.
          </li>
          <li>
            The correction was <b>chosen by looking at the test days</b> (4
            candidates), so its test numbers are slightly optimistic.
          </li>
          <li>
            <b>Curtailment</b>: wind farms told to cut output generate less than
            the wind allows, which looks like a forecast miss. Not separable
            with these data.
          </li>
          <li>
            <b>Embedded wind</b> (small farms on local distribution networks)
            isn't in these figures, so they understate total GB wind output.
          </li>
          <li>
            Bands jump at the wind-level edges; a smooth version is on the
            polish list.
          </li>
          <li>
            £ costs use flat prices you type in; real imbalance prices spike
            when wind under-delivers.
          </li>
        </ul>
      </Section>
    </div>
  );
}
