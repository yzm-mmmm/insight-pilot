/**
 * 查询结果表格组件
 * 将后端返回的结构化结果 { columns, rows, sql } 归一化为可滚动表格，
 * 并附带可折叠的执行 SQL，方便追溯数据来源。
 */
import { ChevronRight, Database, FileJson } from "lucide-react";
import type { StructuredResult } from "../types/agent";

function formatCell(value: unknown) {
  if (value === null || value === undefined) return "-";
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
}

export function ResultTable({ result }: { result: StructuredResult }) {
  const columns = result.columns ?? [];
  const rows = result.rows ?? [];

  if (columns.length === 0) {
    return null;
  }

  return (
    <section className="glass-strong mt-4 overflow-hidden">
      <div className="flex items-center justify-between border-b border-black/10 px-4 py-3">
        <div className="flex items-center gap-2 text-sm font-semibold text-ink">
          <Database className="h-4 w-4 text-moss" aria-hidden="true" />
          查询结果
        </div>
        <div className="flex items-center gap-2 text-xs text-ink/55">
          <FileJson className="h-3.5 w-3.5" aria-hidden="true" />
          {rows.length} 行
        </div>
      </div>

      {result.sql && (
        <details className="group border-b border-black/10 bg-white/50">
          <summary className="flex cursor-pointer list-none items-center gap-2 px-4 py-2 text-xs font-medium text-ink/55 transition hover:text-moss [&::-webkit-details-marker]:hidden">
            <ChevronRight className="h-3.5 w-3.5 transition group-open:rotate-90" aria-hidden="true" />
            执行 SQL
          </summary>
          <pre className="overflow-x-auto px-4 pb-3 font-mono text-xs leading-6 text-ink/75">
            <code>{result.sql}</code>
          </pre>
        </details>
      )}

      <div className="max-h-[360px] overflow-auto">
        <table className="min-w-full border-separate border-spacing-0 text-left text-sm">
          <thead className="sticky top-0 z-10 bg-surface">
            <tr>
              {columns.map((column) => (
                <th
                  key={column}
                  scope="col"
                  className="border-b border-black/10 px-4 py-3 font-semibold text-ink/70"
                >
                  {column}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {rows.map((row, rowIndex) => (
              <tr key={rowIndex} className="odd:bg-black/[0.03] even:bg-transparent">
                {columns.map((column) => (
                  <td key={column} className="border-b border-black/5 px-4 py-3 text-ink/80">
                    {formatCell(row[column])}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}
