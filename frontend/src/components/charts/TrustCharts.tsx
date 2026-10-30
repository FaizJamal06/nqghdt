// Forecast Trust charts. One y-axis each, in MW (or %): MAE and bias share a unit, so
// they share an axis. Blue = typical miss (MAE), red = bias (negative = desk short).
import {
  Bar,
  BarChart,
  CartesianGrid,
  ErrorBar,
  Legend,
  Line,
  LineChart,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Accuracy, BreakdownRow, Calibration } from "../../api/types";
import { C } from "../../lib/colors";
import { signedMw } from "../../lib/format";

const grid = <CartesianGrid stroke="#e2e8f0" vertical={false} />;
const tick = { fontSize: 12 };
const gwAxis = (
  <YAxis
    tick={tick}
    tickFormatter={(v: number) => (v / 1000).toFixed(1)}
    width={40}
    label={{ value: "GW", angle: -90, position: "insideLeft", fontSize: 12 }}
  />
);
const mwTip = <Tooltip formatter={(v, name) => [signedMw(Number(v)), name]} />;
const zero = <ReferenceLine y={0} stroke="#64748b" />;
// itemSorter null: keep series order (Recharts sorts by name by default).
const legend = <Legend wrapperStyle={{ fontSize: 12 }} itemSorter={null} />;

/** MAE and bias vs lead time, h = 1..40 (DECISIONS #25). Same data in every mode. */
export function LeadTimeChart({ points }: { points: Accuracy["lead_time"] }) {
  return (
    <ResponsiveContainer width="100%" height={260}>
      <LineChart data={points} margin={{ top: 8, right: 16, left: 0 }}>
        {grid}
        <XAxis
          dataKey="horizon_h"
          type="number"
          domain={[1, "dataMax"]}
          ticks={[1, 6, 12, 18, 24, 30, 36, 40]}
          tick={tick}
          tickFormatter={(h: number) => `${h} h`}
        />
        {gwAxis}
        {zero}
        <Tooltip
          labelFormatter={(h) => `${h} h ahead`}
          formatter={(v, name) => [signedMw(Number(v)), name]}
        />
        {legend}
        <Line
          dataKey="mae"
          name="Typical miss (MAE)"
          stroke={C.mae}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          dataKey="bias"
          name="Bias (actual − forecast)"
          stroke={C.short}
          strokeWidth={2}
          dot={false}
          isAnimationActive={false}
        />
      </LineChart>
    </ResponsiveContainer>
  );
}

/** MAE and bias side by side per group (hour of day, wind level). */
export function MaeBiasBars({ rows }: { rows: BreakdownRow[] }) {
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={rows} margin={{ top: 8, right: 16, left: 0 }} barGap={2}>
        {grid}
        <XAxis dataKey="key" tick={tick} />
        {gwAxis}
        {zero}
        {mwTip}
        {legend}
        <Bar
          dataKey="mae"
          name="Typical miss (MAE)"
          fill={C.mae}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
        <Bar
          dataKey="bias"
          name="Bias"
          fill={C.short}
          radius={[0, 0, 4, 4]}
          isAnimationActive={false}
        />
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Error histogram (500 MW bins). Short side red, long side grey; P10 and P90 marked. */
export function ErrorHistogram({
  bins,
  p10,
  p90,
}: {
  bins: Accuracy["histogram"];
  p10: number;
  p90: number;
}) {
  const data = bins.map((b) => ({
    ...b,
    mid: (b.lo_mw + b.hi_mw) / 2,
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart
        data={data}
        margin={{ top: 20, right: 16, left: 0, bottom: 12 }}
      >
        {grid}
        <XAxis
          dataKey="mid"
          type="number"
          domain={[bins[0].lo_mw, bins[bins.length - 1].hi_mw]}
          tick={tick}
          tickFormatter={(v: number) => (v / 1000).toFixed(0)}
          label={{
            value: "error (GW)",
            position: "insideBottomRight",
            offset: -4,
            fontSize: 12,
          }}
        />
        <YAxis tick={tick} width={40} allowDecimals={false} />
        <Tooltip
          labelFormatter={(m) =>
            `${signedMw(Number(m) - 250)} to ${signedMw(Number(m) + 250)}`
          }
          formatter={(v) => [`${v} hours`, "Count"]}
        />
        <Bar
          dataKey="count"
          isAnimationActive={false}
          radius={[4, 4, 0, 0]}
          shape={(props: {
            x?: number;
            y?: number;
            width?: number;
            height?: number;
            payload?: { mid: number };
          }) => (
            <rect
              x={(props.x ?? 0) + 1}
              y={props.y}
              width={Math.max(0, (props.width ?? 0) - 2)}
              height={props.height}
              rx={2}
              fill={(props.payload?.mid ?? 0) < 0 ? C.short : C.muted}
              fillOpacity={0.75}
            />
          )}
        />
        <ReferenceLine x={0} stroke="#334155" />
        {[
          [p10, "P10"],
          [p90, "P90"],
        ].map(([v, name]) => (
          <ReferenceLine
            key={name}
            x={v}
            stroke="#334155"
            strokeDasharray="4 3"
            label={{
              value: `${name} ${signedMw(Number(v))}`,
              position: "top",
              fontSize: 11,
            }}
          />
        ))}
      </BarChart>
    </ResponsiveContainer>
  );
}

/** Nominal vs observed band coverage; test bars carry the by-day bootstrap range. */
export function CalibrationChart({
  levels,
}: {
  levels: Calibration["levels"];
}) {
  const data = levels.map((l) => ({
    key: `${Math.round(l.nominal * 100)}% band`,
    target: l.nominal * 100,
    train: l.train_picp * 100,
    test: l.test_picp * 100,
    range: [(l.test_picp - l.test_lo) * 100, (l.test_hi - l.test_picp) * 100],
  }));
  return (
    <ResponsiveContainer width="100%" height={240}>
      <BarChart data={data} margin={{ top: 8, right: 16, left: 0 }} barGap={2}>
        {grid}
        <XAxis dataKey="key" tick={tick} />
        <YAxis
          tick={tick}
          width={40}
          domain={[0, 100]}
          tickFormatter={(v: number) => `${v}%`}
        />
        <Tooltip formatter={(v, name) => [`${Math.round(Number(v))}%`, name]} />
        {legend}
        <Bar
          dataKey="target"
          name="Target"
          fill={C.forecast}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
        <Bar
          dataKey="train"
          name="Train (fitted on)"
          fill="#93c5fd"
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        />
        <Bar
          dataKey="test"
          name="Test (never seen)"
          fill={C.mae}
          radius={[4, 4, 0, 0]}
          isAnimationActive={false}
        >
          <ErrorBar
            dataKey="range"
            direction="y"
            isAnimationActive={false}
            width={8}
            strokeWidth={2}
            stroke="#0f172a"
          />
        </Bar>
      </BarChart>
    </ResponsiveContainer>
  );
}
