/**
 * 问数聊天主界面
 * 负责聊天会话状态、SSE 事件消费、多轮会话管理和整体页面布局
 */
import {
  Activity,
  ArrowDown,
  BarChart3,
  Database,
  Eraser,
  History,
  Leaf,
  MessageSquarePlus,
  Route,
  Server,
  Shield,
  Users,
} from "lucide-react";
import { useEffect, useMemo, useRef, useState } from "react";
import { AccountSwitcher } from "../components/AccountSwitcher";
import { AdminPanel } from "../components/AdminPanel";
import { Composer } from "../components/Composer";
import { DataSourcePanel } from "../components/DataSourcePanel";
import { DeepSeekControls } from "../components/DeepSeekControls";
import { EmptyState } from "../components/EmptyState";
import { MessageBubble } from "../components/MessageBubble";
import { PermissionPanel } from "../components/PermissionPanel";
import { ProfileDialog } from "../components/ProfileDialog";
import { SessionList } from "../components/SessionList";
import { TracePanel } from "../components/TracePanel";
import { Watermark } from "../components/Watermark";
import { useAuth } from "../context/AuthContext";
import { streamQuery } from "../lib/agentApi";
import { cn, summarizeResult } from "../lib/format";
import {
  deleteSession,
  getSessionDetail,
  listSessions,
} from "../lib/sessionApi";
import type {
  AgentEvent,
  ChartSpec,
  ChatMessage,
  ChatSession,
  FlowStep,
  SessionMessage,
  StructuredResult,
} from "../types/agent";

const examples = [
  "统计 2025 年第一季度各大区的 GMV，并按 GMV 从高到低排序",
  "统计 2025 年 3 月各商品品类的销量和销售额",
  "查询华东地区 2025 年第一季度销售额最高的前 5 个商品",
  "按会员等级统计 2025 年第一季度的订单数和销售额",
];

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || "Vite /api proxy";

function makeId() {
  return crypto.randomUUID?.() ?? `${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

function upsertFlow(flow: FlowStep[] = [], event: Extract<AgentEvent, { type: "progress" }>) {
  const next = [...flow];
  // running 记录追加为新条目，success/error 则回溯更新最近一条同名 running 记录，
  // 使每个节点的“运行中→完成”在时间线上收敛为一条，同时保留反思循环里的重复执行
  if (event.status === "running") {
    next.push({ step: event.step, status: event.status, updatedAt: Date.now(), startedAt: Date.now() });
    return next;
  }
  for (let i = next.length - 1; i >= 0; i--) {
    if (next[i].step === event.step && next[i].status === "running") {
      next[i] = { step: event.step, status: event.status, updatedAt: Date.now(), startedAt: next[i].startedAt };
      return next;
    }
  }
  next.push({ step: event.step, status: event.status, updatedAt: Date.now() });
  return next;
}

function restoreMessage(message: SessionMessage): ChatMessage {
  if (message.role === "user") {
    return {
      id: `m${message.id}`,
      role: "user",
      content: message.content ?? "",
      createdAt: Date.parse(message.created_at),
    };
  }

  // 优先从 result_summary 恢复结构化结果、图表与报告，保证历史会话完整展示
  let report: string | undefined;
  let results: StructuredResult[] | undefined;
  let charts: ChartSpec[] | undefined;
  let hasPayload = false;
  if (message.result_summary) {
    try {
      const payload = JSON.parse(message.result_summary);
      if (payload && typeof payload === "object") {
        hasPayload = true;
        if (typeof payload.report === "string" && payload.report) report = payload.report;
        if (Array.isArray(payload.results) && payload.results.length) results = payload.results;
        if (Array.isArray(payload.charts) && payload.charts.length) charts = payload.charts;
      }
    } catch {
      // 异常 JSON 时退回 content 兜底
    }
  }

  // 兼容旧会话：没有结构化 payload 时把 content 当作报告展示
  if (!hasPayload && message.content) {
    report = message.content;
  }

  const totalRows = results?.reduce((sum, item) => sum + (item.rows?.length ?? 0), 0) ?? 0;
  return {
    id: `m${message.id}`,
    role: "assistant",
    content: report
      ? "分析完成。"
      : results
        ? `查询完成，共 ${totalRows} 行结果。`
        : "本次查询未返回结果。",
    report,
    results,
    charts,
    querySql: message.query_sql ?? undefined,
    messageId: message.id,
    status: "done",
    createdAt: Date.parse(message.created_at),
  };
}

export default function ChatPage() {
  const { user } = useAuth();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [activeSessionId, setActiveSessionId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [activeController, setActiveController] = useState<AbortController | null>(null);
  const [profileOpen, setProfileOpen] = useState(false);
  const [permissionOpen, setPermissionOpen] = useState(false);
  const [traceOpen, setTraceOpen] = useState(false);
  const [adminOpen, setAdminOpen] = useState(false);
  const [dataSourceOpen, setDataSourceOpen] = useState(false);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const isNearBottomRef = useRef(true);
  const [showJumpButton, setShowJumpButton] = useState(false);

  const isStreaming = Boolean(activeController);
  const canSubmit = draft.trim().length > 0 && !isStreaming;

  const completedCount = useMemo(
    () => messages.filter((message) => message.role === "assistant" && message.status === "done").length,
    [messages],
  );

  // 仅当用户停留在底部附近时才自动跟随新消息，避免翻阅历史时被强制拉回底部
  useEffect(() => {
    if (isNearBottomRef.current) {
      scrollRef.current?.scrollTo({
        top: scrollRef.current.scrollHeight,
        behavior: "smooth",
      });
    }
  }, [messages]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distance = el.scrollHeight - el.scrollTop - el.clientHeight;
    isNearBottomRef.current = distance < 120;
    setShowJumpButton(distance > 240);
  };

  const jumpToBottom = () => {
    isNearBottomRef.current = true;
    scrollRef.current?.scrollTo({
      top: scrollRef.current.scrollHeight,
      behavior: "smooth",
    });
  };

  const loadSessions = async () => {
    try {
      setSessions(await listSessions());
    } catch {
      // 会话列表加载失败时保持现状，不打断主流程
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const startNewSession = () => {
    if (isStreaming) return;
    setMessages([]);
    setDraft("");
    setActiveSessionId(null);
  };

  const selectSession = async (id: number) => {
    if (isStreaming) return;
    try {
      const detail = await getSessionDetail(id);
      setMessages(detail.messages.map(restoreMessage));
      setActiveSessionId(id);
      setDraft("");
    } catch {
      // 拉取失败不切换，保持当前会话
    }
  };

  const removeSession = async (id: number) => {
    if (isStreaming) return;
    try {
      await deleteSession(id);
      setSessions((current) => current.filter((session) => session.id !== id));
      if (activeSessionId === id) {
        startNewSession();
      }
    } catch {
      // 删除失败静默处理
    }
  };

  const startQuery = async (rawQuery = draft) => {
    const query = rawQuery.trim();
    if (!query || isStreaming) return;

    const userMessage: ChatMessage = {
      id: makeId(),
      role: "user",
      content: query,
      createdAt: Date.now(),
    };

    const assistantId = makeId();
    const assistantMessage: ChatMessage = {
      id: assistantId,
      role: "assistant",
      content: "正在连接问数智能体...",
      createdAt: Date.now(),
      status: "streaming",
      flow: [],
    };

    const controller = new AbortController();
    setActiveController(controller);
    setDraft("");
    setMessages((current) => [...current, userMessage, assistantMessage]);
    isNearBottomRef.current = true;
    requestAnimationFrame(() =>
      scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight }),
    );

    const onEvent = (event: AgentEvent) => {
      // 会话事件与具体消息无关：新建会话时后端回传会话编号
      if (event.type === "session") {
        setActiveSessionId(event.id);
        setSessions((current) => {
          if (current.some((session) => session.id === event.id)) return current;
          const now = new Date().toISOString();
          return [
            { id: event.id, title: event.title, created_at: now, updated_at: now },
            ...current,
          ];
        });
        return;
      }

      setMessages((current) =>
        current.map((message) => {
          if (message.id !== assistantId) return message;

          if (event.type === "progress") {
            return {
              ...message,
              content: event.status === "running" ? `正在执行：${event.step}` : message.content,
              flow: upsertFlow(message.flow, event),
            };
          }

          if (event.type === "plan") {
            return {
              ...message,
              intent: event.intent,
              plan: event.plan,
            };
          }

          if (event.type === "result") {
            return {
              ...message,
              status: "done",
              content: summarizeResult(event.data),
              results: [...(message.results ?? []), event.data],
            };
          }

          if (event.type === "chart") {
            return {
              ...message,
              charts: [...(message.charts ?? []), event.data],
            };
          }

          if (event.type === "report") {
            return {
              ...message,
              content: "分析完成，已生成报告。",
              report: event.markdown,
            };
          }

          if (event.type === "error") {
            return {
              ...message,
              status: "error",
              content: "这次查询没有成功。",
              error: event.message,
            };
          }

          if (event.type === "message_saved") {
            return { ...message, messageId: event.id };
          }

          // plan / insight / ask 等事件在后续阶段才会可视化，
          // 这里先原样忽略，避免被错误兜底分支当成失败处理
          return message;
        }),
      );
    };

    try {
      await streamQuery(query, {
        signal: controller.signal,
        onEvent,
        threadId: activeSessionId,
      });
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId && message.status === "streaming"
            ? { ...message, status: "done", content: "流程已结束，后端未返回查询结果。" }
            : message,
        ),
      );
    } catch (error) {
      const isAbort = error instanceof DOMException && error.name === "AbortError";
      setMessages((current) =>
        current.map((message) =>
          message.id === assistantId
            ? {
                ...message,
                status: isAbort ? "done" : "error",
                content: isAbort ? "已停止本次查询。" : "无法连接问数接口。",
                error: isAbort ? undefined : error instanceof Error ? error.message : String(error),
              }
            : message,
        ),
      );
    } finally {
      setActiveController(null);
      loadSessions();
    }
  };

  const stopQuery = () => {
    activeController?.abort();
  };

  return (
    <div className="h-dvh overflow-hidden bg-parchment text-ink">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,rgba(22,101,52,0.04)_1px,transparent_1px),linear-gradient(rgba(22,101,52,0.035)_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="pointer-events-none fixed inset-0 grain" />
      <Watermark text={user?.username ?? ""} />
      <ProfileDialog open={profileOpen} onClose={() => setProfileOpen(false)} />
      <PermissionPanel open={permissionOpen} onClose={() => setPermissionOpen(false)} />
      <TracePanel open={traceOpen} onClose={() => setTraceOpen(false)} sessionId={activeSessionId} />
      <AdminPanel open={adminOpen} onClose={() => setAdminOpen(false)} />
      <DataSourcePanel open={dataSourceOpen} onClose={() => setDataSourceOpen(false)} />

      <div className="relative grid h-full min-h-0 overflow-hidden lg:grid-cols-[300px_minmax(0,1fr)]">
        <aside className="hidden min-h-0 border-r border-white/10 bg-[#164a2c] backdrop-blur lg:flex lg:flex-col">
          <div className="border-b border-white/10 px-5 py-5">
            <div className="flex items-center gap-3">
              <div className="grid h-10 w-10 place-items-center bg-[linear-gradient(135deg,#38bdf8,#6366f1)] text-white shadow-glow">
                <BarChart3 className="h-5 w-5" aria-hidden="true" />
              </div>
              <div>
                <div className="text-base font-bold tracking-[0.02em] text-white">InsightPilot</div>
                <div className="text-xs text-white/75">智能数据分析 Agent</div>
              </div>
            </div>
          </div>

          <div className="min-h-0 flex-1 space-y-5 overflow-y-auto px-4 py-4">
            <button
              type="button"
              onClick={startNewSession}
              disabled={isStreaming}
              className="flex h-11 w-full items-center justify-center gap-2 bg-[linear-gradient(135deg,#38bdf8,#6366f1)] text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
            >
              <MessageSquarePlus className="h-4 w-4" aria-hidden="true" />
              新会话
            </button>

            <SessionList
              sessions={sessions}
              activeId={activeSessionId}
              disabled={isStreaming}
              onSelect={selectSession}
              onNew={startNewSession}
              onDelete={removeSession}
            />

            <section>
              <div className="mb-2 flex items-center gap-2 px-1 text-xs font-semibold uppercase tracking-[0.16em] text-white/85">
                <History className="h-3.5 w-3.5" aria-hidden="true" />
                样例
              </div>
              <div className="space-y-2">
                {examples.map((example) => (
                  <button
                    key={example}
                    type="button"
                    disabled={isStreaming}
                    onClick={() => startQuery(example)}
                    className="w-full border border-white/10 bg-white/5 px-3 py-3 text-left text-sm leading-5 text-white transition hover:border-white/30 hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-55"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </section>
          </div>

          {user?.role === "admin" && <DeepSeekControls />}

          <div className="border-t border-white/10 p-4">
            <div className="grid gap-2 text-xs text-white/85">
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-2">
                  <Server className="h-3.5 w-3.5" aria-hidden="true" />
                  API
                </span>
                <span className="truncate font-mono">{API_BASE_URL}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-2">
                  <Activity className="h-3.5 w-3.5" aria-hidden="true" />
                  完成
                </span>
                <span>{completedCount}</span>
              </div>
            </div>
          </div>
        </aside>

        <main className="relative flex min-h-0 min-w-0 flex-col overflow-hidden">
          <header className="relative z-30 flex h-16 shrink-0 items-center justify-between border-b border-black/10 bg-white/60 px-4 backdrop-blur lg:px-6">
            <div className="flex min-w-0 items-center gap-3">
              <div className="grid h-9 w-9 shrink-0 place-items-center bg-moss text-white lg:hidden">
                <BarChart3 className="h-4 w-4" aria-hidden="true" />
              </div>
              <div className="min-w-0">
                <div className="truncate text-sm font-bold text-gradient">智能数据分析 Agent</div>
                <div className="truncate text-xs text-ink/65">FastAPI SSE / LangGraph</div>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <button
                type="button"
                onClick={() => setTraceOpen(true)}
                disabled={activeSessionId == null}
                className="grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-35"
                title="链路追踪"
                aria-label="链路追踪"
              >
                <Route className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setPermissionOpen(true)}
                className="grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink"
                title="数据权限"
                aria-label="数据权限"
              >
                <Shield className="h-4 w-4" aria-hidden="true" />
              </button>
              <button
                type="button"
                onClick={() => setDataSourceOpen(true)}
                className="grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink"
                title="数据源"
                aria-label="数据源"
              >
                <Database className="h-4 w-4" aria-hidden="true" />
              </button>
              {user?.role === "admin" && (
                <button
                  type="button"
                  onClick={() => setAdminOpen(true)}
                  className="grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink"
                  title="用户管理"
                  aria-label="用户管理"
                >
                  <Users className="h-4 w-4" aria-hidden="true" />
                </button>
              )}
              <AccountSwitcher onOpenProfile={() => setProfileOpen(true)} />
              <button
                type="button"
                onClick={startNewSession}
                disabled={messages.length === 0 || isStreaming}
                className={cn(
                  "grid h-9 w-9 place-items-center rounded-full text-ink/55 transition hover:bg-ink/5 hover:text-ink disabled:cursor-not-allowed disabled:opacity-35",
                )}
                title="清空"
                aria-label="清空"
              >
                <Eraser className="h-4 w-4" aria-hidden="true" />
              </button>
            </div>
          </header>

          <div ref={scrollRef} onScroll={handleScroll} className="min-h-0 flex-1 overflow-y-auto overscroll-contain">
            {messages.length === 0 ? (
              <EmptyState examples={examples} onUseExample={(example) => setDraft(example)} />
            ) : (
              <div className="mx-auto flex max-w-6xl flex-col gap-6 px-4 py-6 lg:px-8">
                {messages.map((message) => (
                  <MessageBubble key={message.id} message={message} />
                ))}
              </div>
            )}
          </div>

          {showJumpButton && messages.length > 0 && (
            <button
              type="button"
              onClick={jumpToBottom}
              className="glass absolute bottom-32 right-6 z-20 flex items-center gap-1.5 rounded-full px-3 py-2 text-xs font-medium text-ink/80 transition hover:border-moss/40 hover:text-ink"
              aria-label="回到底部"
            >
              <ArrowDown className="h-3.5 w-3.5" aria-hidden="true" />
              回到底部
            </button>
          )}

          <div className="border-t border-black/10 bg-white/60 px-4 py-2 text-center text-xs text-ink/65">
            <span className="inline-flex items-center gap-2">
              <Leaf className="h-3.5 w-3.5 text-moss" aria-hidden="true" />
              {isStreaming ? "运行中" : "就绪"}
            </span>
          </div>
          <Composer
            value={draft}
            disabled={!canSubmit}
            isStreaming={isStreaming}
            onChange={setDraft}
            onSubmit={() => startQuery()}
            onStop={stopQuery}
          />
        </main>
      </div>
    </div>
  );
}
