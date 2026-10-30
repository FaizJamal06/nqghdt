// Global settings live in the URL query string, so every view is shareable and
// survives a refresh, and every page reads the same values (PRD §9).
import { useSearchParams } from "react-router";
import type { Mode } from "../api/types";

/** Decision View opens on the first out-of-sample day (DECISIONS #52). */
export const DEFAULT_DAY = "2026-01-21";

export interface Settings {
  cutoff: string; // HH:MM UK, D-1
  mode: Mode;
  horizonH: number; // 0-40, horizon mode only
  confidence: number; // 0.5-0.95: "plan on" covers wind this often
  costShort: number | null; // cost-ratio mode: short:long, e.g. 3:1
  costLong: number | null;
}

export const DEFAULTS: Settings = {
  cutoff: "09:20",
  mode: "cutoff",
  horizonH: 24,
  confidence: 0.8,
  costShort: null,
  costLong: null,
};

const num = (v: string | null) => (v === null || v === "" ? null : Number(v));

export function useSettings(): [Settings, (patch: Partial<Settings>) => void] {
  const [params, setParams] = useSearchParams();
  const settings: Settings = {
    cutoff: params.get("cutoff") ?? DEFAULTS.cutoff,
    mode: params.get("mode") === "horizon" ? "horizon" : "cutoff",
    horizonH: num(params.get("h")) ?? DEFAULTS.horizonH,
    confidence: num(params.get("conf")) ?? DEFAULTS.confidence,
    costShort: num(params.get("cs")),
    costLong: num(params.get("cl")),
  };
  const update = (patch: Partial<Settings>) => {
    const next = { ...settings, ...patch };
    const p = new URLSearchParams();
    // Only non-defaults go in the URL, to keep links short.
    if (next.cutoff !== DEFAULTS.cutoff) p.set("cutoff", next.cutoff);
    if (next.mode !== DEFAULTS.mode) p.set("mode", next.mode);
    if (next.mode === "horizon") p.set("h", String(next.horizonH));
    if (next.costShort && next.costLong) {
      p.set("cs", String(next.costShort));
      p.set("cl", String(next.costLong));
    } else if (next.confidence !== DEFAULTS.confidence) {
      p.set("conf", String(next.confidence));
    }
    setParams(p, { replace: true });
  };
  return [settings, update];
}

/** Query params every analytics endpoint takes. */
export const modeParams = (s: Settings) =>
  s.mode === "cutoff"
    ? { mode: s.mode, cutoff: s.cutoff }
    : { mode: s.mode, horizon_h: s.horizonH };

/**
 * Confidence actually used for "plan on". In cost-ratio mode R9 gives
 * alpha = long / (short + long), so confidence = short / (short + long),
 * clamped to the API's 0.5-0.95 range (DECISIONS #3, #47).
 */
export function effectiveConfidence(s: Settings): number {
  if (s.costShort && s.costLong) {
    const c = s.costShort / (s.costShort + s.costLong);
    return Math.min(0.95, Math.max(0.5, Math.round(c * 100) / 100));
  }
  return s.confidence;
}
