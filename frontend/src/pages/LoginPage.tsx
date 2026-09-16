/**
 * 登录/注册页
 * 登录成功后写入 token 并跳转到主界面
 */
import { useState } from "react";
import type { FormEvent } from "react";
import { BarChart3, Loader2 } from "lucide-react";
import { useNavigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export default function LoginPage() {
  const { login, register } = useAuth();
  const navigate = useNavigate();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const canSubmit = username.trim().length > 0 && password.length > 0 && !submitting;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!canSubmit) return;

    setSubmitting(true);
    setError(null);
    try {
      if (mode === "login") {
        await login(username.trim(), password);
      } else {
        await register(username.trim(), password);
      }
      navigate("/", { replace: true });
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="grid h-dvh place-items-center overflow-hidden bg-parchment text-ink">
      <div className="pointer-events-none fixed inset-0 bg-[linear-gradient(90deg,rgba(22,101,52,0.04)_1px,transparent_1px),linear-gradient(rgba(22,101,52,0.035)_1px,transparent_1px)] bg-[size:48px_48px]" />
      <div className="pointer-events-none fixed inset-0 grain" />

      <div className="glass relative w-full max-w-sm px-8 py-10 shadow-panel">
        <div className="mb-8 flex items-center gap-3">
          <div className="grid h-11 w-11 place-items-center bg-accent-gradient text-white shadow-glow">
            <BarChart3 className="h-5 w-5" aria-hidden="true" />
          </div>
          <div>
            <div className="text-base font-semibold tracking-[0.02em]">InsightPilot</div>
            <div className="text-xs text-ink/50">智能数据分析 Agent</div>
          </div>
        </div>

        <div className="mb-6 grid grid-cols-2 border border-ink/10">
          <button
            type="button"
            onClick={() => {
              setMode("login");
              setError(null);
            }}
            className={mode === "login" ? "bg-moss py-2.5 text-sm font-semibold text-white" : "bg-transparent py-2.5 text-sm text-ink/60"}
          >
            登录
          </button>
          <button
            type="button"
            onClick={() => {
              setMode("register");
              setError(null);
            }}
            className={mode === "register" ? "bg-moss py-2.5 text-sm font-semibold text-white" : "bg-transparent py-2.5 text-sm text-ink/60"}
          >
            注册
          </button>
        </div>

        <form onSubmit={submit} className="space-y-4">
          <div className="space-y-1.5">
            <label htmlFor="username" className="block text-xs font-semibold text-ink/60">
              用户名
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              placeholder="请输入用户名"
              className="w-full border border-black/10 bg-white/70 px-3 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-moss/50 focus:ring-2 focus:ring-moss/25"
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="password" className="block text-xs font-semibold text-ink/60">
              密码
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete={mode === "login" ? "current-password" : "new-password"}
              placeholder="请输入密码"
              className="w-full border border-black/10 bg-white/70 px-3 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink/35 focus:border-moss/50 focus:ring-2 focus:ring-moss/25"
            />
          </div>

          {error && (
            <div className="border border-tomato/30 bg-tomato/10 px-3 py-2 text-sm text-tomato">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={!canSubmit}
            className="flex h-11 w-full items-center justify-center gap-2 bg-accent-gradient text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
          >
            {submitting && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
            {mode === "login" ? "登录" : "注册并登录"}
          </button>
        </form>
      </div>
    </div>
  );
}
