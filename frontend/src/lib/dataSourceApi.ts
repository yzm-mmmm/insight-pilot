/**
 * 数据源接口客户端
 * 封装后端 /api/data-sources 下的数据源列表、接入申请、审批、重同步与删除接口
 */
import { getToken } from "./auth";

export type DataSource = {
  id: number;
  name: string;
  description: string | null;
  host: string;
  port: number;
  database: string;
  username: string;
  table_prefix: string;
  status: string;
  binlog_file: string | null;
  binlog_pos: number | null;
  sync_error: string | null;
  last_sync_at: string | null;
  created_by: number | null;
  created_at: string | null;
  reviewed_by: number | null;
  reviewed_at: string | null;
};

export type DataSourceCreateRequest = {
  name: string;
  description?: string | null;
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
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

export function listDataSources(): Promise<DataSource[]> {
  return request<DataSource[]>("/api/data-sources", {
    headers: authHeaders(),
  });
}

export function applyDataSource(
  payload: DataSourceCreateRequest,
): Promise<DataSource> {
  return request<DataSource>("/api/data-sources/apply", {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify(payload),
  });
}

export function reviewDataSource(
  id: number,
  status: "approved" | "rejected",
): Promise<DataSource> {
  return request<DataSource>(`/api/data-sources/${id}/review`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
}

export function resyncDataSource(id: number): Promise<{ ok: boolean; status: string }> {
  return request<{ ok: boolean; status: string }>(`/api/data-sources/${id}/resync`, {
    method: "POST",
    headers: authHeaders(),
  });
}

export function deleteDataSource(id: number): Promise<{ ok: boolean; status: string }> {
  return request<{ ok: boolean; status: string }>(`/api/data-sources/${id}`, {
    method: "DELETE",
    headers: authHeaders(),
  });
}
