// Buffer Planner: turn the error into a decision (PRD §9, R9). The dial is the global
// confidence / cost-ratio control in the settings bar; £ prices here are optional.
import { useState } from "react";
import { Link, useLocation } from "react-router";
import { useMeta, usePlanner } from "../api/client";
import type { Planner, Policy } from "../api/types";
import { ErrorState, Skeleton } from "../components/Status";
import { mwh, pct, splitLabels } from "../lib/format";
import { DEFAULT_DAY, type Settings, useSettings } from "../state/settings";

const P = (alpha: number) => `P${Math.round(alpha * 100)}`;

/** One sentence: where alpha came from (R9). */
function alphaSentence(p: Planner, s: Settings, prices: Prices | null) {
  const a = p.alpha.toFixed(2);
  if (prices)
    return `Short costs £${prices.short}/MWh and long £${prices.long}/MWh, so alpha = ${prices.long} / (${prices.short} + ${prices.long}) = ${a}: plan on ${P(p.alpha)} of likely wind.`;
  if (s.costShort && s.costLong)
    return `Being short costs ${s.costShort}× as much as being long (${s.costShort}:${s.costLong}), so alpha = ${s.costLong} / (${s.costShort} + ${s.costLong}) ≈ ${a}: plan on ${P(p.alpha)} of likely wind.`;
  return `To be ${pct((1 - p.alpha) * 100)} sure the wind comes in at or above your plan, plan on ${P(p.alpha)} of likely wind (alpha = 1 − ${(1 - p.alpha).toFixed(2)} = ${a}).`;
}

const LABELS: Record<Policy["policy"], string> = {
  raw: "Trust WINDFOR",
  P50: "P50 (middle)",
  P20: "P20",
  P10: "P10",
  yours: "Yours",
};

interface Prices {
  short: number;
  long: number;
}

export default function BufferPlanner() {
  const [s] = useSettings();
  const meta = useMeta().data;
  const [usePrices, setUsePrices] = useState(false);
  const [short, setShort] = useState("");
  const [long, setLong] = useState("");
  const prices =
    usePrices && Number(short) > 0 && Number(long) > 0
      ? { short: Number(short), long: Number(long) }
      : null;
  const q = usePlanner(s, prices ?? undefined);
  const { search } = useLocation();

  if (q.isError)
    return <ErrorState error={q.error} retry={() => q.refetch()} />;
  if (!q.data || !meta) return <Skeleton className="h-96" />;
  const p = q.data;
  const yours = p.policies.find((r) => r.policy === "yours")!;
  const raw = p.policies.find((r) => r.policy === "raw")!;
  const rawShort = Math.round((raw.pct_short / 100) * p.n_test);
  const field = "w-20 rounded border border-slate-300 px-2 py-1";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Buffer Planner</h1>
        <p className="text-sm text-slate-600">
          How much wind to plan on, backtested on the {p.n_test_days} test days
          ({splitLabels(meta).test}, {p.n_test} hours) that the model never saw.
          Move the confidence or cost ratio in the bar above.
        </p>
      </div>

      <section className="space-y-3 rounded-lg border bg-white p-4">
        <p className="text-slate-800">{alphaSentence(p, s, prices)}</p>
        <p className="text-lg leading-snug text-slate-900">
          Plan at {P(p.alpha)} and you'd have been short in{" "}
          <b>{pct(yours.pct_short)}</b> of hours instead of {rawShort} of{" "}
          {p.n_test}, by buying {mwh(yours.extra_mwh)} more than WINDFOR said (
          {mwh(yours.extra_mwh / p.n_test_days)} a day).
        </p>
        <div className="flex flex-wrap items-center gap-3 text-sm">
          <label className="flex items-center gap-2">
            <input
              type="checkbox"
              checked={usePrices}
              onChange={(e) => setUsePrices(e.target.checked)}
            />
            Use £/MWh prices
          </label>
          {usePrices && (
            <>
              <label className="flex items-center gap-1">
                short £
                <input
                  className={field}
                  type="number"
                  min={0}
                  value={short}
                  onChange={(e) => setShort(e.target.value)}
                />
              </label>
              <label className="flex items-center gap-1">
                long £
                <input
                  className={field}
                  type="number"
                  min={0}
                  value={long}
                  onChange={(e) => setLong(e.target.value)}
                />
              </label>
              <span className="rounded bg-amber-100 px-2 py-0.5 text-amber-900">
                your assumption
              </span>
              <span className="text-slate-500">
                {prices
                  ? "These prices set alpha on this page."
                  : "Enter both to cost each policy."}
              </span>
            </>
          )}
        </div>
      </section>

      <PolicyTable p={p} />

      <p className="text-sm text-slate-600">
        A flat price understates the real cost: imbalance prices tend to spike
        when wind under-delivers. To see the plan on one day, open the{" "}
        <Link
          className="text-violet-700 underline"
          to={{ pathname: `/decision/${DEFAULT_DAY}`, search }}
        >
          Decision View
        </Link>
        .
      </p>
    </div>
  );
}

function PolicyTable({ p }: { p: Planner }) {
  const withCost = p.policies.some((r) => r.cost_gbp !== null);
  const td = "px-2 py-1 text-right tabular-nums whitespace-nowrap";
  const cols = [
    "Policy",
    "Plans on",
    "Hours short",
    "Shortfall",
    "Excess",
    "Bought beyond forecast",
    ...(withCost ? ["Cost (your prices)"] : []),
  ];
  return (
    <section className="overflow-x-auto rounded-lg border bg-white p-4 text-sm">
      <table className="w-full">
        <thead className="text-xs text-slate-500">
          <tr>
            {cols.map((c, i) => (
              <th
                key={c}
                className={`px-2 py-1 font-normal whitespace-nowrap ${i ? "text-right" : "text-left"}`}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {p.policies.map((r) => (
            <tr
              key={r.policy}
              className={`border-t ${r.policy === "yours" ? "bg-violet-50 font-semibold text-violet-900" : ""}`}
            >
              <td className="px-2 py-1">{LABELS[r.policy]}</td>
              <td className={td}>
                {r.alpha === null ? "the forecast" : P(r.alpha)}
              </td>
              <td className={td}>{pct(r.pct_short)}</td>
              <td className={td}>{mwh(r.shortfall_mwh)}</td>
              <td className={td}>{mwh(r.excess_mwh)}</td>
              <td className={td}>{mwh(r.extra_mwh)}</td>
              {withCost && (
                <td className={td}>
                  {r.cost_gbp === null
                    ? "—"
                    : `£${Math.round(r.cost_gbp).toLocaleString("en-GB")}`}
                </td>
              )}
            </tr>
          ))}
        </tbody>
      </table>
      <p className="mt-2 text-xs text-slate-500">
        Shortfall = wind below plan (you buy the gap at the imbalance price);
        excess = wind above plan (you sell it back). Energy in MWh over{" "}
        {p.n_test} test hours.
      </p>
    </section>
  );
}
