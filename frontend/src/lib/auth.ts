/**
 * 多账号本地存储
 * 记录浏览器里登录过的账号（用户名 + token + 展示信息），
 * 支持在界面上自由切换账号，方便演示管理员与普通用户的不同权限。
 */
import type { AuthUser } from "./authApi";

export type StoredAccount = {
  username: string;
  token: string;
  role: string;
  nickname: string | null;
  avatar: string | null;
};

const ACCOUNTS_KEY = "insight-pilot.accounts";
const ACTIVE_KEY = "insight-pilot.active";

function readAccounts(): StoredAccount[] {
  try {
    const raw = localStorage.getItem(ACCOUNTS_KEY);
    return raw ? (JSON.parse(raw) as StoredAccount[]) : [];
  } catch {
    return [];
  }
}

function writeAccounts(accounts: StoredAccount[]) {
  localStorage.setItem(ACCOUNTS_KEY, JSON.stringify(accounts));
}

export function getAccounts(): StoredAccount[] {
  return readAccounts();
}

export function getActiveAccount(): StoredAccount | null {
  const username = localStorage.getItem(ACTIVE_KEY);
  if (!username) return null;
  return readAccounts().find((account) => account.username === username) ?? null;
}

export function getToken(): string | null {
  return getActiveAccount()?.token ?? null;
}

export function saveAccount(user: AuthUser, token: string) {
  const accounts = readAccounts();
  const entry: StoredAccount = {
    username: user.username,
    token,
    role: user.role,
    nickname: user.nickname ?? null,
    avatar: user.avatar ?? null,
  };
  const index = accounts.findIndex((account) => account.username === user.username);
  if (index >= 0) accounts[index] = entry;
  else accounts.push(entry);
  writeAccounts(accounts);
  localStorage.setItem(ACTIVE_KEY, user.username);
}

export function setActiveAccount(username: string): StoredAccount | null {
  const account = readAccounts().find((item) => item.username === username) ?? null;
  if (account) localStorage.setItem(ACTIVE_KEY, username);
  else localStorage.removeItem(ACTIVE_KEY);
  return account;
}

export function removeAccount(username: string) {
  writeAccounts(readAccounts().filter((account) => account.username !== username));
  if (localStorage.getItem(ACTIVE_KEY) === username) {
    localStorage.removeItem(ACTIVE_KEY);
  }
}

export function clearAll() {
  localStorage.removeItem(ACCOUNTS_KEY);
  localStorage.removeItem(ACTIVE_KEY);
}
