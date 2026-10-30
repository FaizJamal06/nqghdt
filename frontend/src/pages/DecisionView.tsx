// Decision View: one delivery day as the trader saw it at the gate (PRD §9).
import { useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router";
import { useDecision, useMeta } from "../api/client";
import type { Decision, Period } from "../api/types";
import DecisionChart, {
  DecisionLegend,
} from "../components/charts/DecisionChart";
import { Empty, ErrorState, Skeleton } from "../components/Status";
import { C } from "../lib/colors";
import {
  dayLabel,
  gw,
  mw,
  mwh,
  shortLong,
  signedMw,
  splitLabels,
  ukDate,
  ukTime,
} from "../lib/format";
import { DEFAULT_DAY, useSettings } from "../state/settings";

export default function DecisionView() {
  const date = useParams().date ?? DEFAULT_DAY;
  const [settings] = useSettings();
  const meta = useMeta().data;
  const q = useDecision(settings, date);
  const [showActual, setShowActual] = useState(false);
  const [hover, setHover] = useState<string | null>(null);

  return (
    <div className="space-y-4">
      <DayPicker days={meta?.delivery_days ?? []} date={date} />
      {q.isPending && <Skeleton className="h-96" />}
      {q.isError && <ErrorState error={q.error} retry={() => q.refetch()} />}
      {q.data && meta && (
        <DayContent
          d={q.data}
          trainDays={splitLabels(meta).train}
          hover={hover}
          setHover={setHover}
          showActual={showActual}
          setShowActual={setShowActual}
        />
      )}
    </div>
  );
}

function DayPicker({ days, date }: { days: string[]; date: string }) {
  const { search } = useLocation();
  const navigate = useNavigate();
  const i = days.indexOf(date);
  const to = (d: string) => ({ pathname: `/decision/${d}`, search });
  const step = "rounded border px-2 py-1 text-sm hover:bg-slate-100";
  return (
    <div className="flex items-center gap-2">
      {i > 0 ? (
        <Link className={step} to={to(days[i - 1])}>
          ←
        </Link>
      ) : (
        <span className={`${step} opacity-30`}>←</span>
      )}
      <select
        className="rounded border border-slate-300 bg-white px-2 py-1 text-sm"
        value={date}
        onChange={(e) => navigate(to(e.target.value))}
      >
        {days.map((d) => (
          <option key={d} value={d}>
            {dayLabel(d)}
          </option>
        ))}
      </select>
      {i >= 0 && i < days.length - 1 ? (
        <Link className={step} to={to(days[i + 1])}>
          →
        </Link>
      ) : (
        <span className={`${step} opacity-30`}>→</span>
      )}
    </div>
  );
}

function SampleBadge({ sample }: { sample: Decision["sample"] }) {
  if (sample === "out-of-sample") {
    return (
      <span className="rounded-full bg-emerald-100 px-3 py-1 text-sm font-medium text-emerald-800">
        Out-of-sample: an honest test day
      </span>
    );
  }
  const tip =
    "The correction and bands were fitted on data including this day; use 21 Jan onwards for an honest view.";
  return (
    <span
      className="group relative cursor-help rounded-full bg-amber-400 px-3 py-1 text-sm font-semibold text-amber-950"
      title={tip}
      tabIndex={0}
    >
      ⚠ In-sample day ⓘ
      <span className="pointer-events-none absolute left-0 top-full z-10 mt-2 hidden w-72 rounded bg-slate-900 p-2 text-xs font-normal text-white shadow group-hover:block group-focus:block">
        {tip}
      </span>
    </span>
  );
}

function Freshness({ d }: { d: Decision }) {
  if (!d.freshness || !d.cutoff_utc) {
    return (
      <p className="text-sm text-slate-600">
        Fixed horizon: each hour uses the latest forecast published at least
        that many hours before it. There is no single decision time in this
        mode.
      </p>
    );
  }
  const f = d.freshness;
  const tone = f.is_stale
    ? "bg-amber-100 text-amber-900"
    : "bg-slate-100 text-slate-700";
  return (
    <p className={`rounded px-3 py-2 text-sm ${tone}`}>
      Forecast published {ukTime(f.latest_publish)},{" "}
      {Math.round(f.minutes_before_cutoff)} min before the {d.cutoff_local}{" "}
      cutoff on {dayLabel(ukDate(d.cutoff_utc))}
      {f.is_stale && " — stale: publishes were missed"}.
    </p>
  );
}

/** "WINDFOR says 20.9 GW at 17:00. Based on 2–20 Jan, expect about 18.1 GW; plan on 16.3 GW…" */
function sentence(
  p: Period,
  d: Decision,
  trainDays: string,
  showActual: boolean,
) {
  const covered = Math.round((1 - d.alpha) * 100);
  const expect =
    d.correction.kind === "raw"
      ? ""
      : ` Based on ${trainDays}, expect about ${gw(p.centre_mw)};`;
  const what =
    showActual && p.actual_mw !== null
      ? ` What happened: ${gw(p.actual_mw)}.`
      : "";
  return `WINDFOR says ${gw(p.forecast_mw)} at ${p.local_time}.${expect} plan on ${gw(p.planned_mw)} to be covered ${covered}% of the time.${what}`;
}

function DayContent({
  d,
  trainDays,
  hover,
  setHover,
  showActual,
  setShowActual,
}: {
  d: Decision;
  trainDays: string;
  hover: string | null;
  setHover: (t: string | null) => void;
  showActual: boolean;
  setShowActual: (v: boolean) => void;
}) {
  if (d.periods.length === 0)
    return (
      <Empty>No forecast was available at decision time for this day.</Empty>
    );
  const showCentre = d.correction.kind !== "raw";
  const focus =
    d.periods.find((p) => p.local_time === hover) ??
    d.periods.find((p) => p.local_time === "17:00") ??
    d.periods[0];
  const risky = d.periods.filter((p) => p.flags.length > 0);

  return (
    <>
      <div className="flex flex-wrap items-center gap-3">
        <h1 className="text-xl font-semibold">
          Delivery {dayLabel(d.date)} 2026
        </h1>
        <SampleBadge sample={d.sample} />
      </div>
      <Freshness d={d} />

      <section className="rounded-lg border bg-white p-4">
        <p className="mb-3 min-h-12 text-lg leading-snug text-slate-900">
          {sentence(focus, d, trainDays, showActual)}
        </p>
        <DecisionChart
          periods={d.periods}
          showCentre={showCentre}
          showActual={showActual}
          onHover={setHover}
        />
        <div className="mt-2 flex flex-wrap items-center justify-between gap-3">
          <DecisionLegend
            showCentre={showCentre}
            showActual={showActual}
            central={d.band_central}
          />
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={showActual}
              onChange={(e) => setShowActual(e.target.checked)}
            />
            Show what happened
          </label>
        </div>
      </section>

      <div className="grid gap-4 lg:grid-cols-3">
        <section className="rounded-lg border bg-white p-4 text-sm">
          <h2 className="mb-2 font-semibold">Risky hours</h2>
          {risky.length === 0 ? (
            <p className="text-slate-500">No risky hours flagged.</p>
          ) : (
            <ul className="space-y-1">
              {risky.map((p) => (
                <li key={p.start_time}>
                  <span className="font-medium tabular-nums">
                    {p.local_time}
                  </span>{" "}
                  {p.flags.includes("big_revision") &&
                    p.revision_mw !== null && (
                      <span>
                        big revision {signedMw(p.revision_mw)} vs previous
                        publish.{" "}
                      </span>
                    )}
                  {p.flags.includes("low_wind") && (
                    <span className="text-slate-600">Low wind.</span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>
        <Totals d={d} showActual={showActual} />
      </div>

      <PeriodTable
        periods={d.periods}
        showCentre={showCentre}
        showActual={showActual}
        central={d.band_central}
      />
    </>
  );
}

function Totals({ d, showActual }: { d: Decision; showActual: boolean }) {
  const t = d.totals;
  const row = (label: string, day: string, peak: string) => (
    <tr className="border-t">
      <td className="py-1 pr-3 text-slate-600">{label}</td>
      <td className="py-1 pr-3 text-right tabular-nums">{day}</td>
      <td className="py-1 text-right tabular-nums">{peak}</td>
    </tr>
  );
  return (
    <section className="rounded-lg border bg-white p-4 text-sm lg:col-span-2">
      <h2 className="mb-2 font-semibold">Energy for the day</h2>
      <table className="w-full">
        <thead className="text-xs text-slate-500">
          <tr>
            <th />
            <th className="text-right font-normal">Whole day</th>
            <th className="text-right font-normal">Peak 16:00–19:00</th>
          </tr>
        </thead>
        <tbody>
          {row(
            "Forecast (WINDFOR)",
            mwh(t.forecast_mwh),
            mwh(t.peak_forecast_mwh),
          )}
          {row("Plan on", mwh(t.planned_mwh), mwh(t.peak_planned_mwh))}
          {row(
            "Buy extra vs forecast",
            mwh(t.extra_mwh),
            mwh(t.peak_forecast_mwh - t.peak_planned_mwh),
          )}
          {showActual && t.actual_mwh !== null && (
            <>
              {row("Actual", mwh(t.actual_mwh), mwh(t.peak_actual_mwh!))}
              {row(
                "If you'd trusted WINDFOR",
                shortLong(t.error_mwh!),
                shortLong(t.peak_error_mwh!),
              )}
              {row(
                "Following the plan",
                shortLong(t.plan_error_mwh!),
                shortLong(t.peak_plan_error_mwh!),
              )}
            </>
          )}
        </tbody>
      </table>
      {showActual && t.actual_mwh === null && (
        <p className="mt-2 text-xs text-slate-500">
          Some hours have no actual yet, so no hindsight totals.
        </p>
      )}
      {showActual && t.actual_mwh !== null && (
        <p className="mt-2 text-xs text-slate-500">
          Net over the hours: actual minus what you planned on.
        </p>
      )}
    </section>
  );
}

function PeriodTable({
  periods,
  showCentre,
  showActual,
  central,
}: {
  periods: Period[];
  showCentre: boolean;
  showActual: boolean;
  central: number;
}) {
  const th = "px-2 py-1 text-right font-normal whitespace-nowrap";
  const td = "px-2 py-1 text-right tabular-nums whitespace-nowrap"; // scroll, don't wrap, on phones
  return (
    <section className="overflow-x-auto rounded-lg border bg-white p-4 text-sm">
      <table className="w-full">
        <thead className="text-xs text-slate-500">
          <tr>
            <th className="px-2 py-1 text-left font-normal">Time</th>
            <th className={th}>SP</th>
            <th className={th}>Forecast</th>
            {showCentre && <th className={th}>Expected</th>}
            <th className={th}>Plan on</th>
            <th className={th}>{Math.round(central * 100)}% range</th>
            <th className={th}>Revision</th>
            {showActual && <th className={th}>Actual</th>}
            {showActual && <th className={th}>Error</th>}
          </tr>
        </thead>
        <tbody>
          {periods.map((p) => (
            <tr key={p.start_time} className="border-t">
              <td className="px-2 py-1 tabular-nums">{p.local_time}</td>
              <td className={td}>{p.sp}</td>
              <td className={td}>{mw(p.forecast_mw)}</td>
              {showCentre && <td className={td}>{mw(p.centre_mw)}</td>}
              <td className={`${td} font-semibold`} style={{ color: C.plan }}>
                {mw(p.planned_mw)}
              </td>
              <td className={td}>
                {Math.round(p.band_low_mw).toLocaleString("en-GB")}–
                {mw(p.band_high_mw)}
              </td>
              <td className={td}>
                {p.revision_mw === null ? "—" : signedMw(p.revision_mw)}
              </td>
              {showActual && (
                <td className={td}>
                  {p.actual_mw === null ? "—" : mw(p.actual_mw)}
                </td>
              )}
              {showActual && (
                <td
                  className={td}
                  style={{
                    color:
                      p.error_mw !== null && p.error_mw < 0
                        ? C.short
                        : undefined,
                  }}
                >
                  {p.error_mw === null ? "—" : signedMw(p.error_mw)}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}
