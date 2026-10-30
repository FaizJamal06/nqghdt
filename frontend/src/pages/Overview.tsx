// Overview: the 10-second story. 4 KPI tiles, one January chart, 4 generated sentences
// (3 on the problem, 1 on the solution).
import { useAccuracy, useMeta, usePlanner, useTimeseries } from "../api/client";
import type { Accuracy, Meta, Planner } from "../api/types";
import MonthChart from "../components/charts/MonthChart";
import KpiTile from "../components/KpiTile";
import { ErrorState, Skeleton } from "../components/Status";
import { gw, mw, pct, signedMw, splitLabels } from "../lib/format";
import {
  type Settings,
  effectiveConfidence,
  useSettings,
} from "../state/settings";

/** The solution, backtested on the out-of-sample days only (planner policies). */
function solution(p: Planner, meta: Meta, s: Settings): string {
  const yours = p.policies.find((r) => r.policy === "yours")!;
  const raw = p.policies.find((r) => r.policy === "raw")!;
  // A count, not a %: 99.7% would round to a false "100%".
  const rawShort = Math.round((raw.pct_short / 100) * p.n_test);
  return `Planning with WindDesk at ${pct(effectiveConfidence(s) * 100)} on the test days (${splitLabels(meta).test}): short in ${pct(yours.pct_short)} of hours, by design. Trusting WINDFOR: short in ${rawShort} of ${p.n_test}.`;
}

/** Plain sentences generated from the numbers (no hand-written claims). */
function sentences(a: Accuracy, s: Settings): string[] {
  const when =
    s.mode === "cutoff"
      ? `At the ${s.cutoff} gate`
      : `${s.horizonH} hours ahead`;
  const bias = a.summary.bias;
  const dir = bias < 0 ? "too high" : "too low";
  const p10 = a.quantiles.p10;
  const wait = Object.fromEntries(
    a.value_of_waiting.map((r) => [r.name, r.mae]),
  );
  const names = a.value_of_waiting.map((r) => r.name);
  const first = names[0];
  const last = names[names.length - 1];
  return [
    `${when}, WINDFOR forecast more wind than turned up in ${pct(a.summary.pct_over_forecast)} of hours: on average ${gw(Math.abs(bias))} ${dir}.`,
    `In 1 hour in 10 the wind came in more than ${gw(Math.abs(p10))} below the forecast; trusting it left the desk short by over 1 GW in ${pct(a.exceedance.short_gt_1000)} of hours.`,
    `Waiting for later forecasts helps only a little: the typical miss is ${gw(wait[first])} at ${first} and ${gw(wait[last])} at ${last}.`,
  ];
}

export default function Overview() {
  const [s] = useSettings();
  const acc = useAccuracy(s);
  const ts = useTimeseries(s);
  const plan = usePlanner(s);
  const meta = useMeta().data;

  if (acc.isError)
    return <ErrorState error={acc.error} retry={() => acc.refetch()} />;
  if (ts.isError)
    return <ErrorState error={ts.error} retry={() => ts.refetch()} />;
  const a = acc.data;
  const n = a ? `n = ${a.summary.n} hours · ${a.summary.n_days} days` : "";

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {a ? (
          <>
            <KpiTile
              label="Typical miss (MAE)"
              value={mw(a.summary.mae)}
              note={n}
            />
            <KpiTile
              label="Average bias"
              value={signedMw(a.summary.bias)}
              note={`${n} · negative = too high`}
              warn={a.summary.bias < 0}
            />
            <KpiTile
              label="1-in-10 shortfall (P10)"
              value={signedMw(a.quantiles.p10)}
              note={n}
              warn
            />
            <KpiTile
              label="Hours short by > 1 GW"
              value={pct(a.exceedance.short_gt_1000)}
              note={n}
              warn
            />
          </>
        ) : (
          [0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24" />)
        )}
      </div>

      <section className="rounded-lg border bg-white p-4">
        <h2 className="mb-2 text-sm font-semibold text-slate-700">
          January: the forecast the trader had vs what happened (shaded = desk
          short)
        </h2>
        {ts.data ? (
          <MonthChart points={ts.data.points} />
        ) : (
          <Skeleton className="h-72" />
        )}
      </section>

      {a && (
        <ul className="space-y-2 rounded-lg border bg-white p-4 text-slate-800">
          {sentences(a, s).map((t) => (
            <li key={t}>{t}</li>
          ))}
          {plan.data && meta && (
            <li className="font-medium">{solution(plan.data, meta, s)}</li>
          )}
        </ul>
      )}
    </div>
  );
}
