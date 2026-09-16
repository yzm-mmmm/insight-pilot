/**
 * 账号切换器
 * 点击当前用户头像/昵称展开下拉，列出浏览器里保存的账号一键切换，
 * 并支持登录其他账号、编辑个人资料与退出登录。
 */
import { useEffect, useRef, useState } from "react";
import { Check, ChevronsUpDown, LogOut, Pencil, Plus } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";
import type { StoredAccount } from "../lib/auth";
import { cn } from "../lib/format";

function Avatar({
  account,
  size = "h-8 w-8 text-sm",
}: {
  account: StoredAccount;
  size?: string;
}) {
  if (account.avatar) {
    return <img src={account.avatar} alt="" className={cn("shrink-0 rounded-full object-cover", size)} />;
  }
  const label = (account.nickname || account.username || "?").slice(0, 1).toUpperCase();
  return (
    <span className={cn("grid shrink-0 place-items-center rounded-full bg-moss font-semibold text-white", size)}>
      {label}
    </span>
  );
}

export function AccountSwitcher({ onOpenProfile }: { onOpenProfile: () => void }) {
  const { user, accounts, switchAccount, logout } = useAuth();
  const navigate = useNavigate();
  const [open, setOpen] = useState(false);
  const [switching, setSwitching] = useState<string | null>(null);
  const ref = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    if (!open) return;
    const onMouseDown = (event: MouseEvent) => {
      if (ref.current && !ref.current.contains(event.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", onMouseDown);
    return () => document.removeEventListener("mousedown", onMouseDown);
  }, [open]);

  const active: StoredAccount =
    accounts.find((account) => account.username === user?.username) ?? {
      username: user?.username ?? "",
      token: "",
      role: user?.role ?? "user",
      nickname: user?.nickname ?? null,
      avatar: user?.avatar ?? null,
    };

  const onSwitch = async (username: string) => {
    if (username === user?.username) {
      setOpen(false);
      return;
    }
    setSwitching(username);
    const ok = await switchAccount(username);
    setSwitching(null);
    if (ok) setOpen(false);
  };

  const loginOther = () => {
    setOpen(false);
    navigate("/login");
  };

  const editProfile = () => {
    setOpen(false);
    onOpenProfile();
  };

  const doLogout = () => {
    setOpen(false);
    logout();
  };

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="flex items-center gap-2 rounded-full py-1 pl-1 pr-2 transition hover:bg-ink/5"
        title="切换账号"
        aria-label="切换账号"
        aria-haspopup="menu"
        aria-expanded={open}
      >
        <Avatar account={active} />
        <span className="hidden items-center gap-2 text-sm text-ink/70 sm:inline-flex">
          {user?.nickname || user?.username}
          {user?.role === "admin" && (
            <span className="rounded-full bg-brass/20 px-2 py-0.5 text-xs font-medium text-soot">
              管理员
            </span>
          )}
        </span>
        <ChevronsUpDown className="hidden h-3.5 w-3.5 text-ink/40 sm:block" aria-hidden="true" />
      </button>

      {open && (
        <div className="absolute right-0 top-full z-50 mt-2 w-64 border border-black/10 bg-[#dcfce7] shadow-panel">
          <div className="px-3 py-2 text-xs font-semibold uppercase tracking-[0.14em] text-black/70">
            切换账号
          </div>
          <div className="max-h-64 overflow-y-auto">
            {accounts.map((account) => (
              <button
                key={account.username}
                type="button"
                disabled={switching !== null}
                onClick={() => onSwitch(account.username)}
                className={cn(
                  "flex w-full items-center gap-2.5 px-3 py-2 text-left transition hover:bg-black/5 disabled:cursor-not-allowed disabled:opacity-60",
                  account.username === user?.username && "bg-moss/25",
                )}
              >
                <Avatar account={account} size="h-7 w-7 text-xs" />
                <span className="min-w-0 flex-1">
                  <span className="flex items-center gap-1.5 truncate text-sm text-black">
                    {account.nickname || account.username}
                    {account.role === "admin" && (
                      <span className="rounded-full bg-brass/30 px-1.5 py-0.5 text-[10px] font-medium text-black">
                        管理员
                      </span>
                    )}
                  </span>
                  <span className="block truncate text-xs text-black/60">@{account.username}</span>
                </span>
                {account.username === user?.username && (
                  <Check className="h-4 w-4 shrink-0 text-emerald-600" aria-hidden="true" />
                )}
              </button>
            ))}
          </div>
          <div className="border-t border-black/10">
            <button
              type="button"
              onClick={loginOther}
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-black/80 transition hover:bg-black/5"
            >
              <Plus className="h-4 w-4 text-black/50" aria-hidden="true" />
              登录其他账号
            </button>
            <button
              type="button"
              onClick={editProfile}
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-black/80 transition hover:bg-black/5"
            >
              <Pencil className="h-4 w-4 text-black/50" aria-hidden="true" />
              编辑个人资料
            </button>
            <button
              type="button"
              onClick={doLogout}
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-left text-sm text-red-600 transition hover:bg-red-50"
            >
              <LogOut className="h-4 w-4" aria-hidden="true" />
              退出登录
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
