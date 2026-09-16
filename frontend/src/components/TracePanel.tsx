/**
 * 链路追踪可视化面板
 * 从 GET /api/sessions/{id}/traces 拉取当前会话的全部 trace，以右侧抽屉形式展示：
 * 每条 trace 折叠展示「节点时间线 + LLM 调用明细 + SQL 历史 + 自主循环诊断」。
 * 视觉风格与数据权限面板保持一致（浅绿底 + 黑字 + 白卡片）。
 */
import { useEffect, useMemo, useState, type ReactNode } from "react";
import {
  Activity,
  Check,
  ChevronDown,
  Clock,
  Coins,
  Cpu,
  Database,
  Loader2,
  RefreshCw,
  Route,
  Waypoints,
  X,
} from "lucide-react";
import { fetchSessionTraces } from "../lib/sessionApi";
import { cn } from "../lib/format";
import type { Trace } from "../types/agent";

function formatMs(ms: number | null | undefined) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function formatEpoch(seconds: number) {
  const date = new Date(seconds * 1000);
  const pad = (value: number) => String(value).padStart(2, "0");
  return `${date.getMonth() + 1}/${date.getDate()} ${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`;
}

function formatCost(usd: number | null | undefined) {
  if (usd == null) return "—";
  return `$${usd.toFixed(6)}`;
}

function formatTokens(value: number | null | undefined) {
  return value == null ? "—" : value.toLocaleString();
}

function StatusDot({ status }: { status: "success" | "error" }) {
  return (
    <span
      className={cn(
        "h-2 w-2 shrink-0 rounded-full",
        status === "success" ? "bg-moss" : "bg-tomato",
      )}
      aria-hidden="true"
    />
  );
}

function Metric({ label, value, icon }: { label: string; value: string; icon?: ReactNode }) {
  return (
    <div className="rounded bg-white/60 px-3 py-2">
      <div className="flex items-center gap-1.5 text-[11px] uppercase tracking-wide text-black/50">
        {icon}
        {label}
      </div>
      <div className="mt-0.5 truncate font-mono text-sm text-black">{value}</div>
    </div>
  );
}

function TraceDetail({ trace }: { trace: Trace }) {
  const maxNodeMs = useMemo(
    () => Math.max(1, ...trace.node_spans.map((span) => span.duration_ms || 0)),
    [trace.node_spans],
  );

  return (
    <div className="space-y-4 border-t border-black/10 px-4 pb-4 pt-3">
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        <Metric label="总耗时" value={formatMs(trace.duration_ms)} icon={<Clock className="h-3 w-3" />} />
        <Metric label="总 Token" value={formatTokens(trace.total_tokens)} icon={<Cpu className="h-3 w-3" />} />
        <Metric label="LLM 调用" value={`${trace.llm_call_count} 次`} icon={<Waypoints className="h-3 w-3" />} />
        <Metric label="估算成本" value={formatCost(trace.estimated_cost_usd)} icon={<Coins className="h-3 w-3" />} />
        <Metric label="SQL 重试" value={formatTokens(trace.sql_retry_count ?? 0)} />
        <Metric label="反思轮数" value={formatTokens(trace.iteration_count ?? 0)} />
        <Metric label="图表数" value={formatTokens(trace.chart_count ?? 0)} />
        <Metric label="最终动作" value={trace.next_action ? String(trace.next_action) : "—"} />
      </div>

      {trace.error && (
        <div className="border border-tomato/40 bg-tomato/25 px-3 py-2 text-sm text-black">
          {trace.error}
        </div>
      )}

      {trace.node_spans.length > 0 && (
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-black/60">
            <Activity className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
            节点时间线
          </div>
          <ol className="space-y-1.5">
            {trace.node_spans.map((span, index) => (
              <li key={`${span.step}-${index}`} className="flex items-center gap-3 text-sm">
                <Check
                  className={cn(
                    "h-3.5 w-3.5 shrink-0",
                    span.status === "success" ? "text-moss" : "text-tomato",
                  )}
                  aria-hidden="true"
                />
                <span className="w-28 shrink-0 truncate text-black/75">{span.step}</span>
                <div className="h-1.5 min-w-0 flex-1 overflow-hidden rounded-full bg-black/10">
                  <div
                    className={cn(
                      "h-full rounded-full",
                      span.status === "success" ? "bg-moss/70" : "bg-tomato/70",
                    )}
                    style={{ width: `${Math.max(4, ((span.duration_ms || 0) / maxNodeMs) * 100)}%` }}
                  />
                </div>
                <span className="w-16 shrink-0 text-right font-mono text-xs text-black/50">
                  {formatMs(span.duration_ms)}
                </span>
              </li>
            ))}
          </ol>
        </section>
      )}

      {trace.llm_calls.length > 0 && (
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-black/60">
            <Cpu className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
            LLM 调用明细
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="border-b border-black/10 text-black/50">
                  <th className="py-1.5 pr-3 font-medium">模型</th>
                  <th className="py-1.5 pr-3 font-medium">输入</th>
                  <th className="py-1.5 pr-3 font-medium">输出</th>
                  <th className="py-1.5 pr-3 font-medium">耗时</th>
                  <th className="py-1.5 font-medium">成本</th>
                </tr>
              </thead>
              <tbody>
                {trace.llm_calls.map((call, index) => (
                  <tr key={index} className="border-b border-black/5 font-mono text-black/75">
                    <td className="max-w-[120px] truncate py-1.5 pr-3">{call.model ?? "—"}</td>
                    <td className="py-1.5 pr-3">{formatTokens(call.prompt_tokens)}</td>
                    <td className="py-1.5 pr-3">{formatTokens(call.completion_tokens)}</td>
                    <td className="py-1.5 pr-3">{formatMs(call.duration_ms)}</td>
                    <td className="py-1.5">{formatCost(call.cost_usd)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      {(trace.sql_history?.length ?? 0) > 0 && (
        <section>
          <div className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-black/60">
            <Database className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
            SQL 历史（含重试）
          </div>
          <div className="space-y-2">
            {trace.sql_history?.map((sql, index) => (
              <pre
                key={index}
                className="overflow-x-auto whitespace-pre-wrap break-all rounded bg-black/[0.05] px-3 py-2 font-mono text-xs leading-5 text-black/80"
              >
                {sql}
              </pre>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

export function TracePanel({
  open,
  onClose,
  sessionId,
}: {
  open: boolean;
  onClose: () => void;
  sessionId: number | null;
}) {
  const [traces, setTraces] = useState<Trace[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    if (!open || sessionId == null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetchSessionTraces(sessionId)
      .then((data) => {
        if (cancelled) return;
        setTraces(data);
        // 默认展开最新一条 trace，方便直接查看链路细节
        setExpandedId((current) => current ?? data[0]?.trace_id ?? null);
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err instanceof Error ? err.message : String(err));
        }
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [open, sessionId, reloadKey]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50" role="dialog" aria-modal="true" aria-label="链路追踪">
      <div className="absolute inset-0 bg-black/50 backdrop-blur-sm" onClick={onClose} />
      <aside className="absolute right-0 top-0 flex h-full w-[440px] max-w-[94vw] flex-col border-l border-black/10 bg-[#dcfce7] shadow-panel">
        <div className="flex items-center justify-between border-b border-black/10 px-5 py-4">
          <div className="flex items-center gap-2 text-base font-semibold text-black">
            <Route className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            链路追踪
          </div>
          <div className="flex items-center gap-1">
            <button
              type="button"
              onClick={() => setReloadKey((key) => key + 1)}
              className="rounded-full p-1.5 text-black/60 transition hover:bg-black/5 hover:text-black"
              title="刷新"
              aria-label="刷新"
            >
              <RefreshCw className={cn("h-4 w-4", loading && "animate-spin")} aria-hidden="true" />
            </button>
            <button
              type="button"
              onClick={onClose}
              className="rounded-full p-1.5 text-black/60 transition hover:bg-black/5 hover:text-black"
              title="关闭"
              aria-label="关闭"
            >
              <X className="h-4 w-4" aria-hidden="true" />
            </button>
          </div>
        </div>

        <div className="min-h-0 flex-1 space-y-3 overflow-y-auto px-5 py-5">
          {loading ? (
            <div className="flex flex-col items-center justify-center gap-3 py-10 text-black/60">
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
              <span className="text-sm">加载链路记录...</span>
            </div>
          ) : error ? (
            <div className="border border-tomato/40 bg-tomato/25 px-3 py-2 text-sm text-black">
              {error}
            </div>
          ) : traces.length === 0 ? (
            <div className="flex flex-col items-center justify-center gap-2 px-6 py-10 text-center text-sm text-black/60">
              <Route className="h-6 w-6 text-black/40" aria-hidden="true" />
              <p>该会话还没有链路追踪记录。</p>
              <p className="text-xs text-black/40">发一条问数并等它跑完，再回来查看。</p>
            </div>
          ) : (
            <div className="space-y-3">
              {traces.map((trace) => {
                const isExpanded = expandedId === trace.trace_id;
                return (
                  <div
                    key={trace.trace_id}
                    className={cn(
                      "overflow-hidden border bg-white/60 transition",
                      trace.status === "success" ? "border-black/10" : "border-tomato/40",
                    )}
                  >
                    <button
                      type="button"
                      onClick={() => setExpandedId(isExpanded ? null : trace.trace_id)}
                      className="flex w-full items-center gap-3 px-4 py-3 text-left transition hover:bg-white/80"
                    >
                      <StatusDot status={trace.status} />
                      <div className="min-w-0 flex-1">
                        <div className="truncate text-sm font-medium text-black">{trace.query}</div>
                        <div className="mt-0.5 flex items-center gap-3 font-mono text-[11px] text-black/55">
                          <span>{formatEpoch(trace.started_at)}</span>
                          <span>{formatMs(trace.duration_ms)}</span>
                          <span>{formatTokens(trace.total_tokens)} tok</span>
                          <span>{formatCost(trace.estimated_cost_usd)}</span>
                        </div>
                      </div>
                      <ChevronDown
                        className={cn(
                          "h-4 w-4 shrink-0 text-black/40 transition",
                          isExpanded && "rotate-180",
                        )}
                        aria-hidden="true"
                      />
                    </button>
                    {isExpanded && <TraceDetail trace={trace} />}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </aside>
    </div>
  );
}
