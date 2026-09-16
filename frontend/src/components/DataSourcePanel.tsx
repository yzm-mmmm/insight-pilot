/**
 * 数据源面板
 * 普通用户可提交「接入数据库」申请并查看自己申请的状态；
 * 管理员可查看全部数据源、通过/拒绝申请、手动重同步或删除数据源。
 */
import { useEffect, useState } from "react";
import { Ban, Check, Database, Loader2, RefreshCw, Trash2, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  applyDataSource,
  deleteDataSource,
  listDataSources,
  resyncDataSource,
  reviewDataSource,
} from "../lib/dataSourceApi";
import type { DataSource } from "../lib/dataSourceApi";
import { cn, formatDateTime } from "../lib/format";

const STATUS_LABEL: Record<string, string> = {
  pending: "待审批",
  approved: "已通过",
  rejected: "已拒绝",
  syncing: "同步中",
  active: "已同步",
  error: "同步失败",
  disabled: "已停用",
};

function StatusBadge({ status }: { status: string }) {
  const color =
    status === "active" || status === "approved"
      ? "bg-moss/30 text-black"
      : status === "pending" || status === "syncing"
        ? "bg-brass/30 text-black"
        : status === "error" || status === "rejected"
          ? "bg-tomato/30 text-black"
          : "bg-black/10 text-black/70";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", color)}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

type FormState = {
  name: string;
  description: string;
  host: string;
  port: string;
  database: string;
  username: string;
  password: string;
};

const EMPTY_FORM: FormState = {
  name: "",
  description: "",
  host: "",
  port: "3306",
  database: "",
  username: "",
  password: "",
};

export function DataSourcePanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [sources, setSources] = useState<DataSource[]>([]);
  const [form, setForm] = useState<FormState>(EMPTY_FORM);
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      setSources(await listDataSources());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setForm(EMPTY_FORM);
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isAdmin]);

  if (!open) return null;

  const setField = (key: keyof FormState, value: string) =>
    setForm((current) => ({ ...current, [key]: value }));

  const pending = sources.filter((source) => source.status === "pending");

  const submitApply = async () => {
    if (!form.name.trim() || !form.host.trim() || !form.database.trim() || !form.username.trim() || !form.password.trim()) {
      setError("请填写数据源名称、主机、数据库、账号与密码");
      return;
    }
    const port = Number(form.port);
    if (!Number.isInteger(port) || port <= 0 || port > 65535) {
      setError("端口号不合法");
      return;
    }
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await applyDataSource({
        name: form.name.trim(),
        description: form.description.trim() || null,
        host: form.host.trim(),
        port,
        database: form.database.trim(),
        username: form.username.trim(),
        password: form.password,
      });
      setForm(EMPTY_FORM);
      setMessage("接入申请已提交，等待管理员审批");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const review = async (id: number, status: "approved" | "rejected") => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await reviewDataSource(id, status);
      setMessage(status === "approved" ? "已通过，正在后台全量同步" : "已拒绝该申请");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const resync = async (id: number) => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await resyncDataSource(id);
      setMessage("已触发重同步，正在后台执行");
      await load();
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const remove = async (id: number, name: string) => {
    if (!window.confirm(`确定删除数据源「${name}」？其镜像表与元数据将一并清除。`)) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await deleteDataSource(id);
      setMessage("数据源已删除");
      setSources((current) => current.filter((source) => source.id !== id));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[82vh] w-full max-w-lg flex-col border border-black/10 bg-[#dcfce7] shadow-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-black/10 px-5 py-4">
          <div className="flex items-center gap-2 text-base font-semibold text-black">
            <Database className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            数据源
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-black/60 transition hover:bg-black/5 hover:text-black"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-5">
          {loading ? (
            <div className="flex items-center justify-center py-10 text-black/60">
              <Loader2 className="h-5 w-5 animate-spin" aria-hidden="true" />
            </div>
          ) : isAdmin ? (
            <div className="space-y-3">
              {pending.length > 0 && (
                <div className="space-y-2">
                  <div className="text-sm font-medium text-black">待审批</div>
                  {pending.map((source) => (
                    <div key={source.id} className="flex items-center justify-between gap-3 border border-black/10 bg-white/60 px-3 py-2.5">
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-black">{source.name}</div>
                        <div className="truncate font-mono text-xs text-black/60">
                          {source.host}:{source.port}/{source.database}
                        </div>
                      </div>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => review(source.id, "approved")}
                          className="inline-flex h-8 items-center gap-1 bg-moss px-2.5 text-xs font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Check className="h-3.5 w-3.5" aria-hidden="true" />
                          通过
                        </button>
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => review(source.id, "rejected")}
                          className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                        >
                          <Ban className="h-3.5 w-3.5" aria-hidden="true" />
                          拒绝
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}

              <div className="text-sm font-medium text-black">全部数据源</div>
              {sources.length === 0 ? (
                <div className="py-8 text-center text-sm text-black/60">暂无数据源</div>
              ) : (
                <div className="space-y-2">
                  {sources.map((source) => (
                    <div key={source.id} className="border border-black/10 bg-white/60 px-3 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="flex items-center gap-2">
                            <span className="truncate text-sm font-medium text-black">{source.name}</span>
                            <StatusBadge status={source.status} />
                          </div>
                          <div className="mt-0.5 truncate font-mono text-xs text-black/60">
                            {source.host}:{source.port}/{source.database} · {source.table_prefix}
                          </div>
                          {source.last_sync_at && (
                            <div className="text-xs text-black/60">最近同步 {formatDateTime(source.last_sync_at)}</div>
                          )}
                          {source.sync_error && (
                            <div className="mt-1 border border-tomato/30 bg-tomato/15 px-2 py-1 text-xs text-black/80">
                              {source.sync_error}
                            </div>
                          )}
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {source.status !== "pending" && source.status !== "rejected" && (
                            <button
                              type="button"
                              disabled={busy}
                              onClick={() => resync(source.id)}
                              className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                              title="重同步"
                              aria-label="重同步"
                            >
                              <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />
                              重同步
                            </button>
                          )}
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => remove(source.id, source.name)}
                            className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:border-tomato/40 hover:bg-tomato/15 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                            title="删除"
                            aria-label="删除"
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            删除
                          </button>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="space-y-3">
              <div className="text-sm text-black/70">
                填写要接入的数据库连接信息并提交，管理员审批通过后会自动全量同步，并订阅源库 binlog 实时更新。
              </div>

              <div className="space-y-2">
                <input
                  type="text"
                  value={form.name}
                  onChange={(event) => setField("name", event.target.value)}
                  placeholder="数据源名称"
                  className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
                <input
                  type="text"
                  value={form.description}
                  onChange={(event) => setField("description", event.target.value)}
                  placeholder="说明（可选）"
                  className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
                <div className="grid grid-cols-[1fr_80px] gap-2">
                  <input
                    type="text"
                    value={form.host}
                    onChange={(event) => setField("host", event.target.value)}
                    placeholder="源库主机"
                    className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                  />
                  <input
                    type="text"
                    value={form.port}
                    onChange={(event) => setField("port", event.target.value)}
                    placeholder="端口"
                    className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                  />
                </div>
                <input
                  type="text"
                  value={form.database}
                  onChange={(event) => setField("database", event.target.value)}
                  placeholder="源库名"
                  className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
                <input
                  type="text"
                  value={form.username}
                  onChange={(event) => setField("username", event.target.value)}
                  placeholder="源库账号"
                  className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
                <input
                  type="password"
                  value={form.password}
                  onChange={(event) => setField("password", event.target.value)}
                  placeholder="源库密码"
                  className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
                <div className="flex justify-end">
                  <button
                    type="button"
                    disabled={busy}
                    onClick={submitApply}
                    className="inline-flex h-10 items-center gap-2 bg-moss px-4 text-sm font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-moss/40"
                  >
                    {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                    提交接入申请
                  </button>
                </div>
              </div>

              <div className="text-sm font-medium text-black">我的申请</div>
              {sources.length === 0 ? (
                <div className="py-4 text-center text-sm text-black/60">暂无申请记录</div>
              ) : (
                <div className="space-y-2">
                  {sources.map((source) => (
                    <div key={source.id} className="border border-black/10 bg-white/60 px-3 py-2.5">
                      <div className="flex items-center justify-between gap-3">
                        <div className="min-w-0">
                          <div className="truncate text-sm font-medium text-black">{source.name}</div>
                          <div className="truncate font-mono text-xs text-black/60">
                            {source.host}:{source.port}/{source.database}
                          </div>
                          {source.sync_error && (
                            <div className="mt-1 truncate text-xs text-tomato">{source.sync_error}</div>
                          )}
                        </div>
                        <StatusBadge status={source.status} />
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {message && (
            <div className="border border-moss/40 bg-moss/20 px-3 py-2 text-sm text-black">{message}</div>
          )}
          {error && (
            <div className="border border-tomato/40 bg-tomato/25 px-3 py-2 text-sm text-black">{error}</div>
          )}
        </div>
      </div>
    </div>
  );
}
