// Global settings: cutoff, selection mode, confidence (or cost ratio). Writes to the URL.
import { useMeta } from "../api/client";
import { effectiveConfidence, useSettings } from "../state/settings";

const PRESET_LABELS: Record<string, string> = {
  "09:20": "09:20 · EPEX day-ahead",
  "09:50": "09:50 · N2EX",
  "15:30": "15:30 · EPEX 30-min",
};

const field = "rounded border border-slate-300 bg-white px-2 py-1 text-sm";
const toggle = (on: boolean) =>
  `px-3 py-1 text-sm ${on ? "bg-slate-800 text-white" : "bg-white text-slate-700 hover:bg-slate-100"}`;

export default function SettingsBar() {
  const [s, set] = useSettings();
  const meta = useMeta().data;
  const presets = meta?.cutoff_presets ?? Object.keys(PRESET_LABELS);
  const maxH = meta?.horizon_max_h ?? 40;
  const custom = !presets.includes(s.cutoff);
  const ratioMode = Boolean(s.costShort && s.costLong);

  return (
    <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-b bg-white px-6 py-2 text-sm text-slate-700">
      <div className="flex overflow-hidden rounded border border-slate-300">
        <button
          className={toggle(s.mode === "cutoff")}
          onClick={() => set({ mode: "cutoff" })}
        >
          At gate closure
        </button>
        <button
          className={toggle(s.mode === "horizon")}
          onClick={() => set({ mode: "horizon" })}
        >
          Fixed horizon
        </button>
      </div>

      {s.mode === "cutoff" ? (
        <label className="flex items-center gap-2">
          Cutoff (D-1)
          <select
            className={field}
            value={custom ? "custom" : s.cutoff}
            onChange={(e) =>
              set({
                cutoff: e.target.value === "custom" ? "12:00" : e.target.value,
              })
            }
          >
            {presets.map((p) => (
              <option key={p} value={p}>
                {PRESET_LABELS[p] ?? p}
              </option>
            ))}
            <option value="custom">Custom…</option>
          </select>
          {custom && (
            <input
              type="time"
              className={field}
              value={s.cutoff}
              onChange={(e) =>
                e.target.value && set({ cutoff: e.target.value })
              }
            />
          )}
        </label>
      ) : (
        <label className="flex items-center gap-2">
          Hours ahead
          <input
            type="range"
            min={0}
            max={maxH}
            step={1}
            value={s.horizonH}
            onChange={(e) => set({ horizonH: Number(e.target.value) })}
          />
          <span className="w-10 tabular-nums">{s.horizonH} h</span>
        </label>
      )}

      <div className="flex items-center gap-2">
        <select
          className={field}
          value={ratioMode ? "ratio" : "confidence"}
          onChange={(e) =>
            e.target.value === "ratio"
              ? set({ costShort: 3, costLong: 1 })
              : set({ costShort: null, costLong: null })
          }
        >
          <option value="confidence">Confidence</option>
          <option value="ratio">Cost ratio</option>
        </select>
        {ratioMode ? (
          <span className="flex items-center gap-1">
            short
            <input
              type="number"
              min={1}
              className={`${field} w-14`}
              value={s.costShort ?? 3}
              onChange={(e) =>
                set({ costShort: Math.max(1, Number(e.target.value)) })
              }
            />
            : long
            <input
              type="number"
              min={1}
              className={`${field} w-14`}
              value={s.costLong ?? 1}
              onChange={(e) =>
                set({ costLong: Math.max(1, Number(e.target.value)) })
              }
            />
            <span className="text-slate-500">
              → {Math.round(effectiveConfidence(s) * 100)}%
            </span>
          </span>
        ) : (
          <span className="flex items-center gap-2">
            <input
              type="range"
              min={0.5}
              max={0.95}
              step={0.05}
              value={s.confidence}
              onChange={(e) => set({ confidence: Number(e.target.value) })}
            />
            <span className="w-10 tabular-nums">
              {Math.round(s.confidence * 100)}%
            </span>
          </span>
        )}
      </div>

      <span className="ml-auto text-xs text-slate-500">All times UK local</span>
    </div>
  );
}
