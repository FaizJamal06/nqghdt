// Forecast Trust: how wrong, when, how often, and do the bands hold (PRD §9).
// Every takeaway sentence is generated from /api/accuracy and /api/calibration.
import { useAccuracy, useCalibration, useMeta } from "../api/client";
import type { Accuracy, Calibration } from "../api/types";
import ChartCard, { DataTable } from "../components/ChartCard";
import {
  CalibrationChart,
  ErrorHistogram,
  LeadTimeChart,
  MaeBiasBars,
} from "../components/charts/TrustCharts";
import KpiTile from "../components/KpiTile";
import { ErrorState, Skeleton } from "../components/Status";
import { formula, mw, pct, signedMw, splitLabels, ukTime } from "../lib/format";
import { useSettings } from "../state/settings";

const n0 = (v: number) => Math.round(v).toLocaleString("en-GB");

export default function ForecastTrust() {
  const [s] = useSettings();
  const acc = useAccuracy(s);
  const cal = useCalibration(s);
  const meta = useMeta().data;

  if (acc.isError)
    return <ErrorState error={acc.error} retry={() => acc.refetch()} />;
  if (cal.isError)
    return <ErrorState error={cal.error} retry={() => cal.refetch()} />;
  if (!acc.data || !cal.data || !meta) return <Skeleton className="h-96" />;
  const a = acc.data;
  const n = `n = ${a.summary.n} hours · ${a.summary.n_days} days`;
  const when =
    s.mode === "cutoff" ? `at the ${s.cutoff} gate` : `${s.horizonH} h ahead`;

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-xl font-semibold">Forecast Trust</h1>
        <p className="text-sm text-slate-600">
          How wrong was the forecast the trader had {when}? Error = actual −
          forecast; negative = wind came in below the forecast (desk short).
        </p>
      </div>
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <KpiTile
          label="Typical miss (MAE)"
          value={mw(a.summary.mae)}
          note={n}
        />
        <KpiTile
          label="RMSE (punishes big misses)"
          value={mw(a.summary.rmse)}
          note={n}
        />
        <KpiTile
          label="Bias"
          value={signedMw(a.summary.bias)}
          note={`${n} · too high in ${pct(a.summary.pct_over_forecast)} of hours`}
          warn={a.summary.bias < 0}
        />
        <KpiTile
          label="1-in-10 range (P10 / P90)"
          value={`${signedMw(a.quantiles.p10)} / ${signedMw(a.quantiles.p90)}`}
          note={n}
        />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <LeadTime a={a} />
        <div className="space-y-4">
          <Honest a={a} />
          <Waiting a={a} />
        </div>
        <ChartCard
          title="Error by hour of day (UK)"
          note={hourNote(a)}
          table={breakdownTable(a.breakdowns.by_hour, "Hour")}
        >
          <MaeBiasBars rows={a.breakdowns.by_hour} />
        </ChartCard>
        <Level a={a} cal={cal.data} />
        <ChartCard
          title="Error distribution"
          note={`Median error ${signedMw(a.quantiles.p50)}; in 1 hour in 10 the wind came in more than ${mw(-a.quantiles.p10)} below the forecast.`}
          table={{
            cols: ["Error (MW)", "Hours"],
            rows: a.histogram.map((b) => [
              `${n0(b.lo_mw)} to ${n0(b.hi_mw)}`,
              b.count,
            ]),
          }}
        >
          <ErrorHistogram
            bins={a.histogram}
            p10={a.quantiles.p10}
            p90={a.quantiles.p90}
          />
        </ChartCard>
        <Bands cal={cal.data} test={splitLabels(meta).test} />
      </div>

      <Corrections cal={cal.data} split={splitLabels(meta)} />
      <Worst a={a} />
    </div>
  );
}

function breakdownTable(rows: Accuracy["breakdowns"]["by_hour"], key: string) {
  return {
    cols: [key, "n", "MAE (MW)", "Bias (MW)"],
    rows: rows.map((r) => [r.key, r.n, n0(r.mae), n0(r.bias)]),
  };
}

function hourNote(a: Accuracy) {
  const rows = a.breakdowns.by_hour;
  const worst = rows.reduce((w, r) => (r.bias < w.bias ? r : w));
  const high = rows.filter((r) => r.bias < 0).length;
  return `On average the forecast ran high at ${high} of ${rows.length} hours of the day; worst at ${worst.key} (bias ${signedMw(worst.bias)}).`;
}

function LeadTime({ a }: { a: Accuracy }) {
  const first = a.lead_time[0];
  const last = a.lead_time[a.lead_time.length - 1];
  return (
    <ChartCard
      title="Error vs lead time (any setting)"
      note={`The miss grows from ${mw(first.mae)} at ${first.horizon_h} h to ${mw(last.mae)} at ${last.horizon_h} h ahead, but the bias is ${signedMw(first.bias)} even 1 h ahead: waiting can't fix it.`}
      table={{
        cols: ["Hours ahead", "n", "MAE (MW)", "Bias (MW)"],
        rows: a.lead_time.map((r) => [r.horizon_h, r.n, n0(r.mae), n0(r.bias)]),
      }}
    >
      <LeadTimeChart points={a.lead_time} />
    </ChartCard>
  );
}

/** PRD "honest vs flattering": the forecast you had vs the last one before delivery. */
function Honest({ a }: { a: Accuracy }) {
  const [had, latest] = a.comparison;
  const better = (1 - latest.mae / had.mae) * 100;
  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">
        Honest vs flattering
      </h2>
      <p className="mt-1 text-sm text-slate-600">
        Scoring the last forecast before delivery would make WINDFOR look{" "}
        {pct(better)} better than the one the trader could act on.
      </p>
      <DataTable
        cols={["Forecast scored", "MAE", "Bias"]}
        rows={[
          [`The one you had (${had.name})`, mw(had.mae), signedMw(had.bias)],
          [
            "Last before delivery (hindsight)",
            mw(latest.mae),
            signedMw(latest.bias),
          ],
        ]}
      />
      <p className="mt-1 text-xs text-slate-500">Same {had.n} hours.</p>
    </section>
  );
}

function Waiting({ a }: { a: Accuracy }) {
  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">Value of waiting</h2>
      <p className="mt-1 text-sm text-slate-600">
        Deciding at a later gate, on the same {a.value_of_waiting[0].n} hours.
      </p>
      <DataTable
        cols={["Cutoff (D-1)", "MAE", "Bias"]}
        rows={a.value_of_waiting.map((r) => [
          r.name,
          mw(r.mae),
          signedMw(r.bias),
        ])}
      />
    </section>
  );
}

/** By wind level + the bias diagnosis (DECISIONS #23: "consistent with X; can't be confirmed"). */
function Level({ a, cal }: { a: Accuracy; cal: Calibration }) {
  const ratios = a.bias_by_level.map((r) => r.ratio.toFixed(2)).join(", ");
  const edges = cal.cells
    .map((c) => c.hi_mw)
    .filter((v): v is number => v !== null);
  return (
    <ChartCard
      title="Error by wind level"
      note={
        <>
          Levels split at {edges.map(mw).join(" and ")} of forecast. Actual ÷
          forecast by fifth of forecast level, calm → windy: {ratios}. Below 1
          everywhere is consistent with a scaling or coverage gap; lowest when
          windiest is consistent with curtailment. Neither can be confirmed from
          these two datasets.
        </>
      }
      table={breakdownTable(a.breakdowns.by_level, "Level")}
    >
      <MaeBiasBars rows={a.breakdowns.by_level} />
    </ChartCard>
  );
}

function Bands({ cal, test }: { cal: Calibration; test: string }) {
  const l80 = cal.levels.find((l) => l.nominal === 0.8);
  return (
    <ChartCard
      title="Do the bands hold?"
      note={
        l80 &&
        `The 80% band caught ${pct(l80.test_picp * 100)} of ${l80.n_test} test hours (${test}); by-day resampling puts that between ${pct(l80.test_lo * 100)} and ${pct(l80.test_hi * 100)}. Whiskers show that range.`
      }
      table={{
        cols: ["Band", "Train", "Test", "Test range (5–95%)"],
        rows: cal.levels.map((l) => [
          pct(l.nominal * 100),
          pct(l.train_picp * 100),
          pct(l.test_picp * 100),
          `${pct(l.test_lo * 100)}–${pct(l.test_hi * 100)}`,
        ]),
      }}
    >
      <CalibrationChart levels={cal.levels} />
    </ChartCard>
  );
}

function Corrections({
  cal,
  split,
}: {
  cal: Calibration;
  split: { train: string; test: string };
}) {
  return (
    <section className="rounded-lg border bg-white p-4 text-sm">
      <h2 className="font-semibold text-slate-800">
        Correction candidates, scored on the test days only ({split.test})
      </h2>
      <p className="mt-1 text-slate-600">
        Each is fitted on {split.train} from the forecast alone. In use:{" "}
        <b>{formula(cal.correction)}</b>.
      </p>
      <div className="mt-2 overflow-x-auto">
        <table className="w-full">
          <thead className="text-xs text-slate-500">
            <tr>
              {[
                "Centre",
                "Formula",
                "MAE",
                "RMSE",
                "Bias",
                "Bias, calmest fifth",
              ].map((c, i) => (
                <th
                  key={c}
                  className={`px-2 py-1 font-normal whitespace-nowrap ${i > 1 ? "text-right" : "text-left"}`}
                >
                  {c}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {cal.corrections.map((c) => {
              const used = c.kind === cal.correction.kind;
              const td = "px-2 py-1 text-right tabular-nums whitespace-nowrap";
              return (
                <tr
                  key={c.kind}
                  className={`border-t ${used ? "bg-violet-50 font-semibold" : ""}`}
                >
                  <td className="px-2 py-1">
                    {c.kind}
                    {used && " ✓"}
                  </td>
                  <td className="px-2 py-1 whitespace-nowrap">{formula(c)}</td>
                  <td className={td}>{mw(c.mae)}</td>
                  <td className={td}>{mw(c.rmse)}</td>
                  <td className={td}>{signedMw(c.bias)}</td>
                  <td className={td}>{signedMw(c.bias_by_quintile[0])}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <p className="mt-2 text-xs text-slate-500">
        n = {cal.corrections[0].n} test hours. The centre was picked by looking
        at these numbers (4 candidates), so they are slightly optimistic.
      </p>
    </section>
  );
}

function Worst({ a }: { a: Accuracy }) {
  return (
    <section className="rounded-lg border bg-white p-4 text-sm">
      <h2 className="mb-2 font-semibold text-slate-800">
        The {a.worst_misses.length} biggest shortfalls
      </h2>
      <DataTable
        cols={[
          "Delivery",
          "Hour (UK)",
          "SP",
          "Hours ahead",
          "Forecast",
          "Actual",
          "Error",
        ]}
        rows={a.worst_misses.map((m) => [
          m.delivery_date,
          ukTime(m.start_time),
          m.sp,
          m.horizon_h,
          mw(m.forecast_mw),
          mw(m.actual_mw),
          signedMw(m.error_mw),
        ])}
      />
    </section>
  );
}
