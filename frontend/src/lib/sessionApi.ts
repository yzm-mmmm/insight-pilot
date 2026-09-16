/**
 * 多轮会话接口客户端
 * 封装会话列表、详情、重命名与删除等后端接口请求。
 */
import { getToken } from "./auth";
import type { ChatSession, SessionMessage, Trace } from "../types/agent";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

function authHeaders(): Record<string, string> {
  return {
    "Content-Type": "application/json",
    ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
  };
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    headers: { ...authHeaders(), ...(init?.headers ?? {}) },
  });
  if (!response.ok) {
    throw new Error(`会话接口请求失败：HTTP ${response.status}`);
  }
  return response.json() as Promise<T>;
}

export function listSessions() {
  return request<ChatSession[]>("/api/sessions");
}

export function getSessionDetail(id: number) {
  return request<{ session: ChatSession; messages: SessionMessage[] }>(
    `/api/sessions/${id}`,
  );
}

export function renameSession(id: number, title: string) {
  return request<ChatSession>(`/api/sessions/${id}`, {
    method: "PATCH",
    body: JSON.stringify({ title }),
  });
}

export function deleteSession(id: number) {
  return request<{ ok: boolean }>(`/api/sessions/${id}`, {
    method: "DELETE",
  });
}

export function fetchSessionTraces(id: number) {
  return request<Trace[]>(`/api/sessions/${id}/traces`);
}
