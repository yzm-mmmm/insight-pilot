/**
 * 消息反馈条
 * 在智能体回答下方提供赞/踩与纠错入口；纠错会连同正确 SQL 一起提交，
 * 供后端作为后续 SQL 生成的 few-shot 示例，形成在线进化闭环。
 */
import { useState } from "react";
import { Loader2, ThumbsDown, ThumbsUp } from "lucide-react";
import { cn } from "../lib/format";
import { submitFeedback } from "../lib/feedbackApi";

export function FeedbackBar({ messageId }: { messageId: number }) {
  const [choice, setChoice] = useState<"like" | "dislike" | null>(null);
  const [submitted, setSubmitted] = useState(false);
  const [comment, setComment] = useState("");
  const [correctedSql, setCorrectedSql] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (submitted) {
    return (
      <div className="mt-3 border-t border-ink/10 pt-3 text-xs text-ink/45">
        已记录反馈，感谢帮助模型改进。
      </div>
    );
  }

  const sendLike = async () => {
    setBusy(true);
    setError(null);
    try {
      await submitFeedback(messageId, { kind: "like" });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const sendDislike = async () => {
    const kind = correctedSql.trim() ? "correct" : "dislike";
    setBusy(true);
    setError(null);
    try {
      await submitFeedback(messageId, {
        kind,
        comment: comment.trim() || null,
        corrected_sql: correctedSql.trim() || null,
      });
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="mt-3 border-t border-ink/10 pt-3">
      <div className="flex items-center gap-2">
        <span className="text-xs text-ink/45">这个回答有帮助吗？</span>
        <button
          type="button"
          disabled={busy}
          onClick={sendLike}
          className={cn(
            "grid h-7 w-7 place-items-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50",
            choice === "like"
              ? "border-moss/40 bg-moss/15 text-moss"
              : "border-ink/15 text-ink/55 hover:border-moss/40 hover:text-moss",
          )}
          title="赞"
          aria-label="赞"
        >
          <ThumbsUp className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setChoice((current) => (current === "dislike" ? null : "dislike"))}
          className={cn(
            "grid h-7 w-7 place-items-center rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50",
            choice === "dislike"
              ? "border-tomato/40 bg-tomato/15 text-tomato"
              : "border-ink/15 text-ink/55 hover:border-tomato/40 hover:text-tomato",
          )}
          title="踩"
          aria-label="踩"
        >
          <ThumbsDown className="h-3.5 w-3.5" aria-hidden="true" />
        </button>
        {error && <span className="text-xs text-tomato">{error}</span>}
      </div>

      {choice === "dislike" && (
        <div className="mt-3 space-y-2">
          <textarea
            value={comment}
            onChange={(event) => setComment(event.target.value)}
            placeholder="哪里不对？补充说明（可选）"
            rows={2}
            className="w-full resize-none border border-ink/15 bg-white/70 px-3 py-2 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-moss/50 focus:ring-2 focus:ring-moss/25"
          />
          <textarea
            value={correctedSql}
            onChange={(event) => setCorrectedSql(event.target.value)}
            placeholder="正确的 SQL（可选，帮助模型学习）"
            rows={3}
            className="w-full resize-none border border-ink/15 bg-white/70 px-3 py-2 font-mono text-xs leading-5 text-ink outline-none transition placeholder:text-ink/35 focus:border-moss/50 focus:ring-2 focus:ring-moss/25"
          />
          <div className="flex items-center justify-end gap-2">
            <button
              type="button"
              onClick={() => setChoice(null)}
              disabled={busy}
              className="h-8 border border-ink/15 px-3 text-xs font-medium text-ink/70 transition hover:bg-ink/5 disabled:cursor-not-allowed disabled:opacity-50"
            >
              取消
            </button>
            <button
              type="button"
              onClick={sendDislike}
              disabled={busy}
              className="flex h-8 items-center gap-1.5 bg-moss px-3 text-xs font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:opacity-50"
            >
              {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
              提交反馈
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
