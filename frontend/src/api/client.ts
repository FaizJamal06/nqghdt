// Typed fetch wrappers + TanStack Query hooks. Same origin: Vite proxies /api in dev.
import { useQuery } from "@tanstack/react-query";
import type { Accuracy, Decision, Meta, Timeseries } from "./types";
import {
  type Settings,
  effectiveConfidence,
  modeParams,
} from "../state/settings";

type Params = Record<string, string | number | undefined>;

export async function get<T>(path: string, params: Params = {}): Promise<T> {
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) qs.set(k, String(v));
  }
  const res = await fetch(`/api/${path}?${qs}`);
  if (!res.ok) {
    // FastAPI puts a readable reason in `detail` (string or validation list).
    const body = await res.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string" ? body.detail : res.statusText;
    throw new Error(`${res.status}: ${detail}`);
  }
  return res.json() as Promise<T>;
}

// The data never changes (January snapshot), so cached answers never go stale.
const forever = { staleTime: Infinity, gcTime: Infinity } as const;

export const useMeta = () =>
  useQuery({
    queryKey: ["meta"],
    queryFn: () => get<Meta>("meta"),
    ...forever,
  });

export const useDecision = (s: Settings, date: string) => {
  const params = { ...modeParams(s), confidence: effectiveConfidence(s), date };
  return useQuery({
    queryKey: ["decision", params],
    queryFn: () => get<Decision>("decision", params),
    ...forever,
  });
};

export const useAccuracy = (s: Settings) => {
  const params = modeParams(s);
  return useQuery({
    queryKey: ["accuracy", params],
    queryFn: () => get<Accuracy>("accuracy", params),
    ...forever,
  });
};

export const useTimeseries = (s: Settings) => {
  const params = modeParams(s);
  return useQuery({
    queryKey: ["timeseries", params],
    queryFn: () => get<Timeseries>("timeseries", params),
    ...forever,
  });
};
