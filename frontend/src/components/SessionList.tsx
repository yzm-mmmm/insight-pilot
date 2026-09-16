/**
 * 会话列表组件
 * 展示当前用户的历史会话，支持切换、新建和删除。
 */
import { History, MessageSquarePlus, Trash2 } from "lucide-react";
import { cn, formatShortDateTime } from "../lib/format";
import type { ChatSession } from "../types/agent";

type Props = {
  sessions: ChatSession[];
  activeId: number | null;
  disabled: boolean;
  onSelect: (id: number) => void;
  onNew: () => void;
  onDelete: (id: number) => void;
};

export function SessionList({
  sessions,
  activeId,
  disabled,
  onSelect,
  onNew,
  onDelete,
}: Props) {
  return (
    <section>
      <div className="mb-2 flex items-center justify-between px-1">
        <span className="inline-flex items-center gap-2 text-xs font-semibold uppercase tracking-[0.16em] text-white/85">
          <History className="h-3.5 w-3.5" aria-hidden="true" />
          历史会话
        </span>
        <button
          type="button"
          onClick={onNew}
          disabled={disabled}
          className="inline-flex items-center gap-1 text-xs text-white/85 transition hover:text-white disabled:cursor-not-allowed disabled:opacity-40"
        >
          <MessageSquarePlus className="h-3.5 w-3.5" aria-hidden="true" />
          新建
        </button>
      </div>

      {sessions.length === 0 ? (
        <p className="px-1 py-2 text-xs text-white/70">暂无历史会话</p>
      ) : (
        <div className="space-y-1">
          {sessions.map((session) => (
            <div
              key={session.id}
              className={cn(
                "group flex items-center gap-1 border border-transparent px-2 py-2 transition",
                session.id === activeId
                  ? "border-white/10 bg-white/[0.06]"
                  : "hover:bg-white/[0.06]",
              )}
            >
              <button
                type="button"
                onClick={() => onSelect(session.id)}
                disabled={disabled}
                className="min-w-0 flex-1 text-left disabled:cursor-not-allowed"
              >
                <div className="truncate text-sm leading-5 text-white">
                  {session.title}
                </div>
                <div className="text-xs text-white/70">
                  {formatShortDateTime(session.updated_at)}
                </div>
              </button>
              <button
                type="button"
                onClick={() => onDelete(session.id)}
                disabled={disabled}
                className="shrink-0 rounded p-1 text-white/70 opacity-0 transition hover:bg-tomato/10 hover:text-tomato focus:opacity-100 group-hover:opacity-100 disabled:cursor-not-allowed"
                title="删除会话"
                aria-label="删除会话"
              >
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
              </button>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
