/**
 * 表级权限接口客户端
 * 封装后端 /api/permissions 下可申请表清单、我的权限、申请与审批接口
 */
import { getToken } from "./auth";

export type TableInfo = {
  id: string;
  name: string | null;
  role: string | null;
  description: string | null;
};

export type Permission = {
  id: number;
  table_name: string;
  status: string;
  requested_at: string | null;
  reviewed_at: string | null;
  username?: string | null;
};

export type MyPermissions = {
  grants: string[];
  requests: Permission[];
};

export type UserGrants = {
  user_id: number;
  username: string;
  role: string;
  nickname: string | null;
  grants: string[];
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

export function listTables(): Promise<TableInfo[]> {
  return request<TableInfo[]>("/api/permissions/tables", {
    headers: authHeaders(),
  });
}

export function myPermissions(): Promise<MyPermissions> {
  return request<MyPermissions>("/api/permissions/my", {
    headers: authHeaders(),
  });
}

export function applyTables(tables: string[]): Promise<{ created: string[] }> {
  return request<{ created: string[] }>("/api/permissions/apply", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ tables }),
  });
}

export function listRequests(): Promise<Permission[]> {
  return request<Permission[]>("/api/permissions/requests", {
    headers: authHeaders(),
  });
}

export function reviewPermission(
  id: number,
  status: "approved" | "rejected",
): Promise<Permission> {
  return request<Permission>(`/api/permissions/${id}/review`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
}

export function listUserGrants(search?: string): Promise<UserGrants[]> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return request<UserGrants[]>(`/api/permissions/users${qs}`, {
    headers: authHeaders(),
  });
}

export function revokeGrant(
  userId: number,
  tableName: string,
): Promise<{ ok: boolean }> {
  return request<{ ok: boolean }>(
    `/api/permissions/grants/${userId}/${encodeURIComponent(tableName)}`,
    {
      method: "DELETE",
      headers: authHeaders(),
    },
  );
}
