/**
 * 鉴权接口客户端
 * 封装后端 /api/auth 下注册、登录、查询当前用户三个接口
 */
import { getToken } from "./auth";

export type AuthUser = {
  id: number;
  username: string;
  role: string;
  disabled: boolean;
  nickname?: string | null;
  avatar?: string | null;
};

export type TokenResponse = {
  access_token: string;
  token_type: string;
  user: AuthUser;
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

export async function login(username: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function register(username: string, password: string): Promise<TokenResponse> {
  return request<TokenResponse>("/api/auth/register", {
    method: "POST",
    body: JSON.stringify({ username, password }),
  });
}

export async function fetchMe(): Promise<AuthUser> {
  return request<AuthUser>("/api/auth/me", {
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
  });
}

export async function updateProfile(
  nickname: string,
  avatar: string | null,
): Promise<AuthUser> {
  return request<AuthUser>("/api/auth/profile", {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ nickname, avatar }),
  });
}

export async function changePassword(
  oldPassword: string,
  newPassword: string,
): Promise<void> {
  await request<{ ok: boolean }>("/api/auth/password", {
    method: "PATCH",
    headers: {
      Authorization: `Bearer ${getToken()}`,
    },
    body: JSON.stringify({ old_password: oldPassword, new_password: newPassword }),
  });
}
