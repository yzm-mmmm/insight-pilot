/**
 * 用户管理接口客户端
 * 封装后端 /api/admin 下管理员视角的用户列表、重置密码与删除接口
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
