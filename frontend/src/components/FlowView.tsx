/**
 * 动态执行流程视图组件
 * 反思循环会让同一个节点反复执行，固定拓扑已不成立，因此这里改成按
 * progress 事件增量追加的竖向时间线。为保持界面简洁：已完成步骤默认折叠，
 * 只突出展示当前正在执行的步骤，失败步骤单独标红。
 */
import { useState } from "react";
import { Check, ChevronDown, LoaderCircle, X } from "lucide-react";
import { cn } from "../lib/format";
import type { FlowStep } from "../types/agent";

function formatDuration(ms: number) {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

export function FlowView({ flow = [] }: { flow?: FlowStep[] }) {
  const [expanded, setExpanded] = useState(false);
  if (flow.length === 0) return null;

  const done = flow.filter((step) => step.status === "success");
  const active = flow.filter((step) => step.status === "running");
  const failed = flow.filter((step) => step.status === "error");

  return (
    <section className="mt-4 border border-white/10 bg-white/[0.03] px-4 py-3">
      <div className="mb-2 flex items-center justify-between gap-3">
        <span className="text-sm font-semibold text-ink">分析流程</span>
        <span className="text-xs text-ink/45">LangGraph</span>
      </div>

      {done.length > 0 && (
        <>
          <button
            type="button"
            onClick={() => setExpanded((value) => !value)}
            className="flex w-full items-center justify-between rounded px-1 py-1.5 text-sm text-ink/65 transition hover:bg-ink/5"
          >
            <span className="inline-flex items-center gap-2">
              <Check className="h-4 w-4 text-moss" aria-hidden="true" />
              已完成 {done.length} 步
            </span>
            <ChevronDown
              className={cn("h-4 w-4 text-ink/40 transition", expanded && "rotate-180")}
              aria-hidden="true"
            />
          </button>

          {expanded && (
            <ol className="relative ml-2 border-l border-ink/15">
              {done.map((step, index) => (
                <li
                  key={`done-${index}`}
                  className="relative flex items-center gap-3 py-1 pl-4 text-sm text-ink/60"
                >
                  <span className="absolute -left-[5px] h-2 w-2 rounded-full bg-moss" />
                  <span className="min-w-0 flex-1 truncate">{step.step}</span>
                  {step.startedAt != null && (
                    <span className="shrink-0 font-mono text-xs text-ink/35">
                      {formatDuration(step.updatedAt - step.startedAt)}
                    </span>
                  )}
                </li>
              ))}
            </ol>
          )}
        </>
      )}

      {active.map((step, index) => (
        <div
          key={`active-${index}`}
          className="mt-2 flex items-center gap-3 rounded bg-moss/10 px-3 py-2"
        >
          <LoaderCircle className="h-4 w-4 shrink-0 animate-spin text-moss" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-moss">
            {step.step}
          </span>
          <span className="shrink-0 text-xs text-moss/70">正在执行</span>
        </div>
      ))}

      {failed.map((step, index) => (
        <div
          key={`failed-${index}`}
          className="mt-2 flex items-center gap-3 rounded bg-tomato/10 px-3 py-2"
        >
          <X className="h-4 w-4 shrink-0 text-tomato" aria-hidden="true" />
          <span className="min-w-0 flex-1 truncate text-sm font-medium text-tomato">
            {step.step}
          </span>
        </div>
      ))}
    </section>
  );
}
