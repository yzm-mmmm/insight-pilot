/**
 * 聊天消息气泡组件
 * 组合展示用户问题、智能体回复、执行流程、结果表格、图表和分析报告
 */
import { BarChart3, Bot, Copy, UserRound } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { ChartRenderer } from "./ChartRenderer";
import { FeedbackBar } from "./FeedbackBar";
import { FlowView } from "./FlowView";
import { MarkdownReport } from "./MarkdownReport";
import { PlanView } from "./PlanView";
import { ResultTable } from "./ResultTable";
import { cn, formatTime, toClipboardText } from "../lib/format";
import type { ChatMessage } from "../types/agent";

export function MessageBubble({ message }: { message: ChatMessage }) {
  const { user } = useAuth();
  const isUser = message.role === "user";

  const copy = async () => {
    const text = message.report
      ? message.report
      : message.results?.length
        ? toClipboardText(message.results)
        : message.content;
    await navigator.clipboard.writeText(text);
  };

  return (
    <article className={cn("group flex gap-3", isUser && "justify-end")}>
      {!isUser && (
        <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full border border-black/10 bg-white/70 text-moss">
          <Bot className="h-4 w-4" aria-hidden="true" />
        </div>
      )}

      <div className={cn("max-w-[920px] flex-1", isUser && "flex max-w-[760px] justify-end")}>
        <div
          className={cn(
            "relative px-5 py-4",
            isUser
              ? "bg-accent-gradient text-white shadow-glow"
              : "glass text-ink",
          )}
        >
          <div className="flex items-start justify-between gap-3">
            <p className="whitespace-pre-wrap text-[15px] leading-7">
              {message.content}
              {!isUser && message.status === "streaming" && (
                <span className="typing-dots ml-2 inline-flex items-center gap-1 align-middle" aria-hidden="true">
                  <span className="h-1.5 w-1.5 rounded-full bg-moss" />
                  <span className="h-1.5 w-1.5 rounded-full bg-moss" />
                  <span className="h-1.5 w-1.5 rounded-full bg-moss" />
                </span>
              )}
            </p>
            {!isUser && message.status !== "streaming" && (
              <button
                type="button"
                onClick={copy}
                className="shrink-0 rounded-full p-1.5 text-ink/45 opacity-0 outline-none transition hover:bg-ink/5 hover:text-ink focus:opacity-100 focus:ring-2 focus:ring-moss/40 group-hover:opacity-100"
                title="复制"
                aria-label="复制"
              >
                <Copy className="h-4 w-4" aria-hidden="true" />
              </button>
            )}
          </div>

          {message.error && (
            <div className="mt-3 border border-tomato/30 bg-tomato/10 px-3 py-2 text-sm text-tomato">
              {message.error}
            </div>
          )}

          {!isUser && <PlanView intent={message.intent} plan={message.plan} />}

          {!isUser && <FlowView flow={message.flow} />}

          {!isUser &&
            message.results?.map((result, index) => (
              <ResultTable key={index} result={result} />
            ))}

          {!isUser && (message.charts ?? []).length > 0 && (
            <section className="glass-strong mt-4 px-4 py-3">
              <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
                <BarChart3 className="h-4 w-4 text-moss" aria-hidden="true" />
                可视化图表
              </div>
              {(message.charts ?? []).map((chart) => (
                <ChartRenderer key={chart.id} spec={chart} />
              ))}
            </section>
          )}

          {!isUser && message.report !== undefined && (
            <MarkdownReport markdown={message.report} charts={message.charts ?? []} />
          )}

          {!isUser && message.messageId != null && (
            <FeedbackBar messageId={message.messageId} />
          )}

          <div
            className={cn(
              "mt-3 text-xs",
              isUser ? "text-white/60" : "text-ink/45",
            )}
          >
            {formatTime(message.createdAt)}
          </div>
        </div>
      </div>

      {isUser &&
        (user?.avatar ? (
          <img
            src={user.avatar}
            alt="我的头像"
            className="mt-1 h-9 w-9 shrink-0 rounded-full object-cover shadow-glow"
          />
        ) : (
          <div className="mt-1 grid h-9 w-9 shrink-0 place-items-center rounded-full bg-accent-gradient text-white shadow-glow">
            <UserRound className="h-4 w-4" aria-hidden="true" />
          </div>
        ))}
    </article>
  );
}
