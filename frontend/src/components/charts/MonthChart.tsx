// Overview chart: the forecast the trader had vs what happened, for the whole month.
// Shortfalls (actual below forecast = desk short) are shaded in the warning colour.
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
import type { Point } from "../../api/types";
import { C } from "../../lib/colors";
import { dayLabel, gw, gwTicks, ukDate, ukTime } from "../../lib/format";
import useNarrow from "../../lib/useNarrow";

export default function MonthChart({ points }: { points: Point[] }) {
  const narrow = useNarrow();
  const data = points.map((p) => ({
    t: p.start_time,
    forecast: p.forecast_mw,
    actual: p.actual_mw,
    // Range area from actual up to forecast, only where the desk was short.
    short: p.actual_mw < p.forecast_mw ? [p.actual_mw, p.forecast_mw] : null,
  }));
  const ticks = gwTicks(
    points.flatMap((p) => [p.forecast_mw, p.actual_mw]),
    true,
  );
  return (
    <ResponsiveContainer width="100%" height={300}>
      <ComposedChart
        data={data}
        margin={{ top: 8, right: 16, bottom: 0, left: 0 }}
      >
        <CartesianGrid stroke="#e2e8f0" vertical={false} />
        <XAxis
          dataKey="t"
          tick={{ fontSize: 12 }}
          interval={narrow ? 335 : 167} // a label every 7 days; 14 on phones
          tickFormatter={(t: string) => dayLabel(ukDate(t))}
        />
        <YAxis
          tick={{ fontSize: 12 }}
          tickFormatter={(v: number) => `${(v / 1000).toFixed(0)}`}
          label={{
            value: "GW",
            angle: -90,
            position: "insideLeft",
            fontSize: 12,
          }}
          domain={[0, ticks[ticks.length - 1]]}
          ticks={ticks}
        />
        <Tooltip
          labelFormatter={(t) =>
            `${dayLabel(ukDate(String(t)))} ${ukTime(String(t))}`
          }
          formatter={(v, name) => [gw(Number(v)), name]}
        />
        <Area
          dataKey="short"
          stroke="none"
          fill={C.short}
          fillOpacity={0.25}
          isAnimationActive={false}
          tooltipType="none"
        />
        <Line
          dataKey="forecast"
          name="Forecast at the gate"
          stroke={C.forecast}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
        <Line
          dataKey="actual"
          name="Actual"
          stroke={C.actual}
          strokeWidth={1.5}
          dot={false}
          isAnimationActive={false}
        />
      </ComposedChart>
    </ResponsiveContainer>
  );
}
