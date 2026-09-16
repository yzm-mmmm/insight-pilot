/**
 * 用户管理面板
 * 仅管理员可见：可搜索并查看全部用户，对单个用户执行重置密码或删除
 * （删除会连带清理其会话、消息、反馈与权限）。
 */
import { useEffect, useState } from "react";
import { KeyRound, Loader2, Search, Trash2, Users, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { deleteUser, listUsers, resetPassword } from "../lib/adminApi";
import type { AdminUser } from "../lib/adminApi";
import { formatDateTime } from "../lib/format";

export function AdminPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [users, setUsers] = useState<AdminUser[]>([]);
  const [search, setSearch] = useState("");
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [resettingId, setResettingId] = useState<number | null>(null);
  const [newPassword, setNewPassword] = useState("");

  const load = async () => {
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      setUsers(await listUsers());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setSearch("");
    setResettingId(null);
    setNewPassword("");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isAdmin]);

  if (!open) return null;

  const keyword = search.trim().toLowerCase();
  const filteredUsers = keyword
    ? users.filter(
        (item) =>
          item.username.toLowerCase().includes(keyword) ||
          (item.nickname ?? "").toLowerCase().includes(keyword),
      )
    : users;

  const submitReset = async (id: number) => {
    if (!newPassword.trim()) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await resetPassword(id, newPassword.trim());
      setMessage("密码已重置");
      setResettingId(null);
      setNewPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const removeUser = async (id: number) => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await deleteUser(id);
      setUsers((current) => current.filter((item) => item.id !== id));
      setMessage("用户已删除");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const confirmDelete = (id: number, name: string) => {
    if (window.confirm(`确定删除用户「${name}」？其会话、消息与权限将一并清除。`)) {
      removeUser(id);
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
            <Users className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            用户管理
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
          ) : !isAdmin ? (
            <div className="py-8 text-center text-sm text-black/60">需要管理员权限</div>
          ) : (
            <div className="space-y-3">
              <div className="relative">
                <Search className="pointer-events-none absolute left-2.5 top-1/2 h-4 w-4 -translate-y-1/2 text-black/50" aria-hidden="true" />
                <input
                  type="text"
                  value={search}
                  onChange={(event) => setSearch(event.target.value)}
                  placeholder="按用户名或昵称搜索"
                  className="w-full border border-black/10 bg-white/80 py-2 pl-9 pr-3 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                />
              </div>

              {filteredUsers.length === 0 ? (
                <div className="py-8 text-center text-sm text-black/60">未找到匹配用户</div>
              ) : (
                filteredUsers.map((item) => (
                  <div key={item.id} className="border border-black/10 bg-white/60 px-3 py-2.5">
                    <div className="flex items-center gap-2">
                      <span className="truncate text-sm font-medium text-black">{item.nickname || item.username}</span>
                      <span className="truncate text-xs text-black/60">@{item.username}</span>
                      {item.role === "admin" && (
                        <span className="rounded-full bg-brass/30 px-1.5 py-0.5 text-[10px] font-medium text-black">管理员</span>
                      )}
                      {item.disabled && (
                        <span className="rounded-full bg-tomato/25 px-1.5 py-0.5 text-[10px] font-medium text-black">已禁用</span>
                      )}
                    </div>
                    <div className="mt-1 flex items-center justify-between gap-3">
                      <span className="text-xs text-black/60">
                        {item.created_at ? `注册于 ${formatDateTime(item.created_at)}` : "注册时间未知"}
                      </span>
                      <div className="flex shrink-0 items-center gap-2">
                        <button
                          type="button"
                          disabled={busy}
                          onClick={() => {
                            setResettingId(resettingId === item.id ? null : item.id);
                            setNewPassword("");
                            setMessage(null);
                            setError(null);
                          }}
                          className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                          title="重置密码"
                          aria-label="重置密码"
                        >
                          <KeyRound className="h-3.5 w-3.5" aria-hidden="true" />
                          重置密码
                        </button>
                        {item.id !== user?.id && (
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => confirmDelete(item.id, item.nickname || item.username)}
                            className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:border-tomato/40 hover:bg-tomato/15 hover:text-black disabled:cursor-not-allowed disabled:opacity-50"
                            title="删除用户"
                            aria-label="删除用户"
                          >
                            <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                            删除
                          </button>
                        )}
                      </div>
                    </div>

                    {resettingId === item.id && (
                      <div className="mt-2 space-y-2 border-t border-black/10 pt-2">
                        <input
                          type="password"
                          value={newPassword}
                          onChange={(event) => setNewPassword(event.target.value)}
                          placeholder="输入新密码"
                          className="w-full border border-black/10 bg-white/80 px-3 py-2 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30"
                        />
                        <div className="flex items-center justify-end gap-2">
                          <button
                            type="button"
                            disabled={busy}
                            onClick={() => {
                              setResettingId(null);
                              setNewPassword("");
                            }}
                            className="h-8 border border-black/15 px-3 text-xs font-medium text-black/70 transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            取消
                          </button>
                          <button
                            type="button"
                            disabled={busy || !newPassword.trim()}
                            onClick={() => submitReset(item.id)}
                            className="inline-flex h-8 items-center gap-1.5 bg-moss px-3 text-xs font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:opacity-50"
                          >
                            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />}
                            确认重置
                          </button>
                        </div>
                      </div>
                    )}
                  </div>
                ))
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
