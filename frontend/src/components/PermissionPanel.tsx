/**
 * 数据权限面板
 * 普通用户可查看可申请表、提交申请、查看自己的授权/申请状态；
 * 管理员可查看全部申请并逐条通过/拒绝。
 */
import { useEffect, useState } from "react";
import { Ban, Check, Loader2, Search, Shield, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import {
  applyTables,
  listRequests,
  listTables,
  listUserGrants,
  myPermissions,
  reviewPermission,
  revokeGrant,
} from "../lib/permissionApi";
import type {
  MyPermissions,
  Permission,
  TableInfo,
  UserGrants,
} from "../lib/permissionApi";
import { cn, formatDateTime } from "../lib/format";

const STATUS_LABEL: Record<string, string> = {
  approved: "已授权",
  pending: "待审批",
  rejected: "已拒绝",
};

function StatusBadge({ status }: { status: string | null }) {
  if (!status) return <span className="text-xs text-black/60">未申请</span>;
  const color =
    status === "approved"
      ? "bg-moss/30 text-black"
      : status === "pending"
        ? "bg-brass/30 text-black"
        : "bg-tomato/30 text-black";
  return (
    <span className={cn("inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium", color)}>
      {STATUS_LABEL[status] ?? status}
    </span>
  );
}

export function PermissionPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const isAdmin = user?.role === "admin";

  const [tables, setTables] = useState<TableInfo[]>([]);
  const [my, setMy] = useState<MyPermissions | null>(null);
  const [requests, setRequests] = useState<Permission[]>([]);
  const [userGrants, setUserGrants] = useState<UserGrants[]>([]);
  const [adminTab, setAdminTab] = useState<"requests" | "users">("requests");
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [loading, setLoading] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    setMessage(null);
    setError(null);
    try {
      if (isAdmin) {
        const [reqs, grants] = await Promise.all([listRequests(), listUserGrants()]);
        setRequests(reqs);
        setUserGrants(grants);
      } else {
        const [tableList, mine] = await Promise.all([listTables(), myPermissions()]);
        setTables(tableList);
        setMy(mine);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (!open) return;
    setSelected(new Set());
    setAdminTab("requests");
    setSearch("");
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, isAdmin]);

  if (!open) return null;

  const grants = new Set(my?.grants ?? []);
  const requestByTable = new Map<string, string>();
  my?.requests.forEach((request) => requestByTable.set(request.table_name, request.status));

  const keyword = search.trim().toLowerCase();
  const filteredUsers = keyword
    ? userGrants.filter(
        (item) =>
          item.username.toLowerCase().includes(keyword) ||
          (item.nickname ?? "").toLowerCase().includes(keyword),
      )
    : userGrants;

  const toggle = (tableId: string) => {
    const next = new Set(selected);
    if (next.has(tableId)) next.delete(tableId);
    else next.add(tableId);
    setSelected(next);
  };

  const isSelectable = (tableId: string) => {
    const status = requestByTable.get(tableId);
    return !grants.has(tableId) && status !== "pending";
  };

  const submitApply = async () => {
    const targets = [...selected];
    if (targets.length === 0) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await applyTables(targets);
      setSelected(new Set());
      setMessage("申请已提交，等待管理员审批");
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
      await reviewPermission(id, status);
      setMessage(status === "approved" ? "已通过该申请" : "已拒绝该申请");
      setRequests(await listRequests());
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setBusy(false);
    }
  };

  const revoke = async (userId: number, tableName: string) => {
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      await revokeGrant(userId, tableName);
      setMessage(`已取消 ${tableName} 的授权`);
      const [reqs, grants] = await Promise.all([listRequests(), listUserGrants()]);
      setRequests(reqs);
      setUserGrants(grants);
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
            <Shield className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            数据权限
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
              <div className="grid grid-cols-2 border border-black/10">
                <button
                  type="button"
                  onClick={() => setAdminTab("requests")}
                  className={adminTab === "requests" ? "bg-moss py-2 text-sm font-semibold text-white" : "bg-transparent py-2 text-sm text-black/70"}
                >
                  审批申请
                </button>
                <button
                  type="button"
                  onClick={() => setAdminTab("users")}
                  className={adminTab === "users" ? "bg-moss py-2 text-sm font-semibold text-white" : "bg-transparent py-2 text-sm text-black/70"}
                >
                  用户权限
                </button>
              </div>

              {adminTab === "requests" ? (
                <div className="space-y-2">
                  {requests.length === 0 ? (
                    <div className="py-8 text-center text-sm text-black/60">暂无申请记录</div>
                  ) : (
                    requests.map((request) => (
                      <div
                        key={request.id}
                        className="flex items-center justify-between gap-3 border border-black/10 bg-white/60 px-3 py-2.5"
                      >
                        <div className="min-w-0">
                          <div className="truncate font-mono text-sm text-black">{request.table_name}</div>
                          <div className="text-xs text-black/60">
                            {request.username ?? `用户 #${request.id}`} · {formatDateTime(request.requested_at)}
                          </div>
                        </div>
                        <div className="flex shrink-0 items-center gap-2">
                          {request.status === "pending" ? (
                            <>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => review(request.id, "approved")}
                                className="inline-flex h-8 items-center gap-1 bg-moss px-2.5 text-xs font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                <Check className="h-3.5 w-3.5" aria-hidden="true" />
                                通过
                              </button>
                              <button
                                type="button"
                                disabled={busy}
                                onClick={() => review(request.id, "rejected")}
                                className="inline-flex h-8 items-center gap-1 border border-black/20 px-2.5 text-xs font-semibold text-black transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-50"
                              >
                                <Ban className="h-3.5 w-3.5" aria-hidden="true" />
                                拒绝
                              </button>
                            </>
                          ) : (
                            <StatusBadge status={request.status} />
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
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
                      <div key={item.user_id} className="border border-black/10 bg-white/60 px-3 py-2.5">
                        <div className="flex items-center gap-2">
                          <span className="truncate text-sm font-medium text-black">{item.nickname || item.username}</span>
                          <span className="truncate text-xs text-black/60">@{item.username}</span>
                          {item.role === "admin" && (
                            <span className="rounded-full bg-brass/30 px-1.5 py-0.5 text-[10px] font-medium text-black">管理员</span>
                          )}
                        </div>
                        <div className="mt-1.5 flex flex-wrap gap-1.5">
                          {item.grants.length === 0 ? (
                            <span className="text-xs text-black/60">暂无授权表</span>
                          ) : (
                            item.grants.map((table) => (
                              <span
                                key={table}
                                className="inline-flex items-center gap-1.5 rounded-full border border-moss/30 bg-moss/20 py-0.5 pl-2 pr-1 font-mono text-xs text-black/80"
                              >
                                {table}
                                <button
                                  type="button"
                                  disabled={busy}
                                  onClick={() => revoke(item.user_id, table)}
                                  className="grid h-4 w-4 place-items-center rounded-full text-black/50 transition hover:bg-tomato/15 hover:text-black disabled:cursor-not-allowed disabled:opacity-40"
                                  title={`取消 ${table} 的授权`}
                                  aria-label={`取消 ${table} 的授权`}
                                >
                                  <X className="h-3 w-3" aria-hidden="true" />
                                </button>
                              </span>
                            ))
                          )}
                        </div>
                      </div>
                    ))
                  )}
                </div>
              )}
            </div>
          ) : (
            <>
              <div className="flex items-center justify-between gap-3 border border-moss/30 bg-moss/10 px-3 py-2.5">
                <span className="text-sm font-medium text-black">已授权的表</span>
                <span className="min-w-0 truncate text-right font-mono text-sm text-black/80">
                  {my?.grants.length ? my.grants.join("、") : "暂无"}
                </span>
              </div>
              <div className="text-sm text-black/70">
                勾选需要访问的数据表并提交申请，管理员审批通过后即可查询。
              </div>
              <div className="space-y-1.5">
                {tables.map((table) => {
                  const status = grants.has(table.id) ? "approved" : (requestByTable.get(table.id) ?? null);
                  const selectable = isSelectable(table.id);
                  return (
                    <button
                      key={table.id}
                      type="button"
                      disabled={!selectable}
                      onClick={() => selectable && toggle(table.id)}
                      className={cn(
                        "flex w-full items-center justify-between gap-3 border border-black/10 bg-white/60 px-3 py-2.5 text-left transition",
                        selectable && "hover:border-moss/40 hover:bg-white",
                        !selectable && "cursor-not-allowed opacity-60",
                      )}
                    >
                      <div className="flex min-w-0 items-center gap-2">
                        {selectable && (
                          <span
                            className={cn(
                              "grid h-4 w-4 shrink-0 place-items-center border",
                              selected.has(table.id)
                                ? "border-moss bg-moss text-white"
                                : "border-black/30 bg-transparent",
                            )}
                          >
                            {selected.has(table.id) && <Check className="h-3 w-3" aria-hidden="true" />}
                          </span>
                        )}
                        <div className="min-w-0">
                          <div className="truncate font-mono text-sm text-black">{table.name ?? table.id}</div>
                          {table.description && (
                            <div className="truncate text-xs text-black/60">{table.description}</div>
                          )}
                        </div>
                      </div>
                      <StatusBadge status={status} />
                    </button>
                  );
                })}
              </div>
              <div className="flex justify-end">
                <button
                  type="button"
                  disabled={selected.size === 0 || busy}
                  onClick={submitApply}
                  className="inline-flex h-10 items-center gap-2 bg-moss px-4 text-sm font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-moss/40"
                >
                  {busy && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                  申请选中表（{selected.size}）
                </button>
              </div>
            </>
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
