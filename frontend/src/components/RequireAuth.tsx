/**
 * 登录守卫
 * 未登录时重定向到登录页，登录态校验完成前显示占位，避免闪跳
 */
import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";
import { useAuth } from "../context/AuthContext";

export function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();

  if (loading) {
    return (
      <div className="grid h-dvh place-items-center bg-parchment text-ink">
        <span className="text-sm text-ink/55">正在验证登录状态…</span>
      </div>
    );
  }

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  return <>{children}</>;
}
