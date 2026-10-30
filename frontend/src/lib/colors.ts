// One palette for every chart and badge (PRD §9 UI rules).
// "short" (negative error: wind below forecast) uses one warning colour everywhere.
export const C = {
  forecast: "#94a3b8", // raw WINDFOR: thin grey dashed
  centre: "#1e293b", // expected (corrected): solid dark
  plan: "#7c3aed", // "plan on": accent, boldest line
  band: "#bae6fd", // 80% range: soft fill
  actual: "#0f766e", // what happened
  short: "#dc2626", // shortfall / desk short
} as const;
