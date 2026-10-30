// A titled card: one chart, one generated takeaway, and a "Show as table" twin so no
// value is reachable by hover alone (accessibility: tooltips enhance, never gate).
import type { ReactNode } from "react";

export interface Table {
  cols: string[];
  rows: (string | number)[][];
}

export function DataTable({ cols, rows }: Table) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead className="text-xs text-slate-500">
          <tr>
            {cols.map((c, i) => (
              <th
                key={c}
                className={`px-2 py-1 font-normal whitespace-nowrap ${i ? "text-right" : "text-left"}`}
              >
                {c}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, j) => (
            <tr key={j} className="border-t">
              {r.map((v, i) => (
                <td
                  key={i}
                  className={`px-2 py-1 whitespace-nowrap tabular-nums ${i ? "text-right" : ""}`}
                >
                  {v}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export default function ChartCard({
  title,
  note,
  table,
  children,
}: {
  title: string;
  note?: ReactNode;
  table?: Table;
  children: ReactNode;
}) {
  return (
    <section className="rounded-lg border bg-white p-4">
      <h2 className="text-sm font-semibold text-slate-800">{title}</h2>
      {note && <p className="mt-1 text-sm text-slate-600">{note}</p>}
      <div className="mt-3">{children}</div>
      {table && (
        <details className="mt-2 text-sm">
          <summary className="cursor-pointer text-slate-500">
            Show as table
          </summary>
          <DataTable {...table} />
        </details>
      )}
    </section>
  );
}
