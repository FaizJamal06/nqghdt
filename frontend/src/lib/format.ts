// Number and time formatting. Power in MW (GW for big headline numbers), energy in MWh.
// All clock times are shown in UK local time (Europe/London).

const UK = "Europe/London";

export const mw = (v: number) => `${Math.round(v).toLocaleString("en-GB")} MW`;

export const gw = (v: number, digits = 1) => `${(v / 1000).toFixed(digits)} GW`;

export const mwh = (v: number) =>
  `${Math.round(v).toLocaleString("en-GB")} MWh`;

/** Signed MW, with a real minus sign: "−735 MW", "+266 MW". */
export const signedMw = (v: number) =>
  `${v < 0 ? "−" : "+"}${Math.abs(Math.round(v)).toLocaleString("en-GB")} MW`;

/**
 * Y-axis ticks (MW) on round GW steps covering every value: 2 GW steps for a day,
 * 5 GW for wider ranges. Never below 0 (R10: wind can't be negative).
 */
export function gwTicks(values: number[], fromZero = false): number[] {
  const lo = Math.min(...values);
  const hi = Math.max(...values);
  const step = hi - lo > 12000 ? 5000 : 2000;
  const start = fromZero ? 0 : Math.max(0, Math.floor(lo / step) * step);
  const ticks = [];
  for (let t = start; t <= Math.ceil(hi / step) * step; t += step)
    ticks.push(t);
  return ticks;
}

export const pct = (v: number) => `${Math.round(v)}%`;

/** "07:30" from a UTC ISO string, in UK time. */
export const ukTime = (iso: string) =>
  new Date(iso).toLocaleTimeString("en-GB", {
    timeZone: UK,
    hour: "2-digit",
    minute: "2-digit",
  });

/** "Wed 21 Jan" from "2026-01-21". */
export const dayLabel = (isoDate: string) =>
  new Date(`${isoDate}T12:00:00Z`).toLocaleDateString("en-GB", {
    timeZone: UK,
    weekday: "short",
    day: "numeric",
    month: "short",
  });

/** UK calendar date "2026-01-20" of a UTC ISO string. */
export const ukDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-CA", { timeZone: UK });
