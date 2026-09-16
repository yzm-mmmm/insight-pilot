/**
 * 分析计划视图组件
 * 展示理解规划节点拆解出的整体意图与子问题清单，让用户看到 Agent
 * 打算按什么步骤回答当前问题。
 */
import { ListChecks } from "lucide-react";
import type { PlanItem } from "../types/agent";

export function PlanView({
  intent,
  plan,
}: {
  intent?: string;
  plan?: PlanItem[];
}) {
  if (!plan || plan.length === 0) return null;

  return (
    <section className="mt-4 border border-black/10 bg-white/60 px-4 py-3">
      <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
        <ListChecks className="h-4 w-4 text-moss" aria-hidden="true" />
        分析计划
      </div>
      {intent && <p className="mb-2 text-sm text-ink/65">{intent}</p>}
      <ol className="space-y-1">
        {plan.map((item, index) => (
          <li key={item.id} className="flex items-start gap-2 text-sm text-ink/75">
            <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded-full bg-moss/15 text-xs font-semibold text-moss">
              {index + 1}
            </span>
            <span className="min-w-0 flex-1 leading-6">{item.question}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
