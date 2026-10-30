// Number and time formatting. Power in MW (GW for big headline numbers), energy in MWh.
// All clock times are shown in UK local time (Europe/London).

import type { CorrectionInfo, Meta } from "../api/types";

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

/** Whole percent, but never a false "0%" or "100%": 99.7 -> "99.7%". */
export const pct = (v: number) => {
  const r = Math.round(v);
  return (r === 100 || r === 0) && r !== v ? `${v.toFixed(1)}%` : `${r}%`;
};

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

/** "2–20 Jan" or "21 Jan – 1 Feb" from two ISO dates. */
export function dayRange(first: string, last: string) {
  const f = (d: string, opts: Intl.DateTimeFormatOptions) =>
    new Date(`${d}T12:00:00Z`).toLocaleDateString("en-GB", opts);
  const sameMonth = first.slice(0, 7) === last.slice(0, 7);
  return sameMonth
    ? `${f(first, { day: "numeric" })}–${f(last, { day: "numeric", month: "short" })}`
    : `${f(first, { day: "numeric", month: "short" })} – ${f(last, { day: "numeric", month: "short" })}`;
}

/** Train (fit) and test day ranges from /api/meta, e.g. "2–20 Jan" and "21 Jan – 1 Feb". */
export function splitLabels(meta: Meta) {
  const days = meta.delivery_days;
  const i = days.indexOf(meta.band_train_end);
  return {
    train: dayRange(days[0], days[i]),
    test: dayRange(days[i + 1], days[days.length - 1]),
  };
}

/** The correction in words: "0.865 × forecast", "forecast − 1,345 MW", "1,460 MW + 0.756 × forecast". */
export function formula(c: Pick<CorrectionInfo, "kind" | "a" | "b">) {
  if (c.kind === "raw") return "forecast";
  if (c.kind === "constant") return `forecast ${signedMw(c.a)}`;
  if (c.kind === "proportional") return `${c.b.toFixed(3)} × forecast`;
  return `${mw(c.a)} + ${c.b.toFixed(3)} × forecast`;
}

/** Net energy with its direction: "1,234 MWh short" (negative, R7) or "567 MWh long". */
export const shortLong = (v: number) =>
  v < 0 ? `${mwh(-v)} short` : `${mwh(v)} long`;

/** UK calendar date "2026-01-20" of a UTC ISO string. */
export const ukDate = (iso: string) =>
  new Date(iso).toLocaleDateString("en-CA", { timeZone: UK });
