/**
 * 管理员接口客户端
 * 封装后端 /api/admin 下两类接口：用户管理（列表、重置密码、删除）
 * 与系统设置（运行时模型切换、DeepSeek 余额查询）。
 */
import { getToken } from "./auth";

export type AdminUser = {
  id: number;
  username: string;
  role: string;
  disabled: boolean;
  nickname: string | null;
  created_at: string | null;
};

export type ModelSetting = {
  current: string;
  available: string[];
};

export type DeepSeekBalance = {
  is_available: boolean;
  currency?: string | null;
  total_balance?: string | null;
  granted_balance?: string | null;
  topped_up_balance?: string | null;
  message?: string | null;
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers ?? {}),
    },
  });

  if (!response.ok) {
    let message = `请求失败：HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      // 错误体不是 JSON 时保留默认提示
    }
    throw new Error(message);
  }

  return response.json() as Promise<T>;
}

const authHeaders = () => ({ Authorization: `Bearer ${getToken()}` });

// —— 用户管理 ——

export function listUsers(search?: string): Promise<AdminUser[]> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return request<AdminUser[]>(`/api/admin/users${qs}`, {
    headers: authHeaders(),
  });
}

export function resetPassword(userId: number, newPassword: string): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/admin/users/${userId}/password`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ new_password: newPassword }),
  });
}

export function deleteUser(userId: number): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(`/api/admin/users/${userId}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}

// —— 系统设置 ——

export function fetchModelSetting(): Promise<ModelSetting> {
  return request<ModelSetting>("/api/admin/model", {
    headers: authHeaders(),
  });
}

export function updateModel(model: string): Promise<ModelSetting> {
  return request<ModelSetting>("/api/admin/model", {
    method: "PUT",
    headers: authHeaders(),
    body: JSON.stringify({ model }),
  });
}

export function fetchDeepSeekBalance(): Promise<DeepSeekBalance> {
  return request<DeepSeekBalance>("/api/admin/deepseek/balance", {
    headers: authHeaders(),
  });
}
