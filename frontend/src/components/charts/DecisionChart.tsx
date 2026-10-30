// Decision View chart (the client-video screen). Layers, back to front:
// 80% range (soft fill) · raw WINDFOR (thin grey dashed) · expected/corrected (solid)
// · plan on (accent, boldest: the number the trader acts on) · actual (only if toggled).
import {
  Area,
  CartesianGrid,
  ComposedChart,
  Line,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import type { Period } from "../../api/types";
import { C } from "../../lib/colors";
import { gwTicks } from "../../lib/format";

interface Props {
  periods: Period[];
  showCentre: boolean;
  showActual: boolean;
  onHover: (localTime: string | null) => void;
}

export default function DecisionChart({
  periods,
  showCentre,
  showActual,
  onHover,
}: Props) {
  const data = periods.map((p) => ({
    t: p.local_time,
    band: [p.band_low_mw, p.band_high_mw],
    forecast: p.forecast_mw,
    centre: p.centre_mw,
    plan: p.planned_mw,
    actual: p.actual_mw,
  }));
  // Zoom to the data (with actuals only when shown) so the gaps between lines are visible.
  const ticks = gwTicks(
    periods.flatMap((p) => [
      p.band_low_mw,
      p.band_high_mw,
      p.forecast_mw,
      ...(showActual && p.actual_mw !== null ? [p.actual_mw] : []),
    ]),
  );
  return (
    <ResponsiveContainer width="100%" height={340}>
      <ComposedChart
        data={data}
        margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
        onMouseMove={(st) =>
          st.activeLabel !== undefined && onHover(String(st.activeLabel))
        }
        onMouseLeave={() => onHover(null)}
      >
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis dataKey="t" tick={{ fontSize: 12 }} interval={2} />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}`}
          label={{
            value: "GW",
            angle: -90,
            position: "insideLeft",
            fontSize: 12,
          }}
          domain={[ticks[0], ticks[ticks.length - 1]]}
          ticks={ticks}
        />
        {/* No tooltip box: the sentence above the chart is the tooltip. */}
        <Tooltip
          content={() => null}
          cursor={{ stroke: "#64748b", strokeDasharray: "3 3" }}
        />
        <Area
          dataKey="band"
          stroke="none"
          fill={C.band}
          fillOpacity={0.7}
          isAnimationActive={false}
        />
        <Line
          dataKey="forecast"
          stroke={C.forecast}
          strokeWidth={1.5}
          strokeDasharray="5 4"
          dot={false}
          isAnimationActive={false}
        />
        {showCentre && (
          <Line
            dataKey="centre"
            stroke={C.centre}
            strokeWidth={2}
            dot={false}
            isAnimationActive={false}
          />
        )}
        <Line
          dataKey="plan"
          stroke={C.plan}
          strokeWidth={3.5}
          dot={false}
          isAnimationActive={false}
        />
        {showActual && (
          <Line
            dataKey="actual"
            stroke={C.actual}
            strokeWidth={2}
            dot={{ r: 2 }}
            isAnimationActive={false}
          />
        )}
      </ComposedChart>
    </ResponsiveContainer>
  );
}

function Swatch({
  color,
  width,
  dash,
}: {
  color: string;
  width: number;
  dash?: string;
}) {
  return (
    <svg width="24" height="8" aria-hidden>
      <line
        x1="0"
        y1="4"
        x2="24"
        y2="4"
        stroke={color}
        strokeWidth={width}
        strokeDasharray={dash}
      />
    </svg>
  );
}

/** Plain-words legend (Faiz's M4 rule), matching the line styles above. */
export function DecisionLegend({
  showCentre,
  showActual,
  central,
}: {
  showCentre: boolean;
  showActual: boolean;
  central: number;
}) {
  const band = (
    <span
      className="inline-block h-3 w-6 rounded-sm"
      style={{ background: C.band }}
    />
  );
  const items: [string, React.ReactNode, boolean][] = [
    [
      "Forecast (WINDFOR)",
      <Swatch color={C.forecast} width={1.5} dash="5 4" />,
      true,
    ],
    ["Expected (corrected)", <Swatch color={C.centre} width={2} />, showCentre],
    ["Plan on", <Swatch color={C.plan} width={3.5} />, true],
    [`${Math.round(central * 100)}% range`, band, true],
    ["Actual", <Swatch color={C.actual} width={2} />, showActual],
  ];
  return (
    <ul className="flex flex-wrap gap-x-5 gap-y-1 text-sm text-slate-700">
      {items
        .filter(([, , show]) => show)
        .map(([label, swatch]) => (
          <li key={label} className="flex items-center gap-2">
            {swatch}
            {label}
          </li>
        ))}
    </ul>
  );
}
