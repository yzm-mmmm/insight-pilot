/**
 * 登录状态上下文
 * 启动时用本地 token 拉取当前用户，登录/注册/登出/切换账号后同步更新全局状态。
 * 支持多账号：把登录过的账号都记录在本地，切换账号时复用已保存的 token。
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
} from "react";
import type { ReactNode } from "react";
import {
  clearAll,
  getAccounts,
  getActiveAccount,
  getToken,
  removeAccount,
  saveAccount,
  setActiveAccount,
} from "../lib/auth";
import type { StoredAccount } from "../lib/auth";
import {
  changePassword as apiChangePassword,
  fetchMe,
  login as apiLogin,
  register as apiRegister,
  updateProfile as apiUpdateProfile,
} from "../lib/authApi";
import type { AuthUser } from "../lib/authApi";

type AuthContextValue = {
  user: AuthUser | null;
  accounts: StoredAccount[];
  loading: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (username: string, password: string) => Promise<void>;
  logout: () => void;
  switchAccount: (username: string) => Promise<boolean>;
  updateProfile: (nickname: string, avatar: string | null) => Promise<void>;
  changePassword: (oldPassword: string, newPassword: string) => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [accounts, setAccounts] = useState<StoredAccount[]>(() => getAccounts());
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    // 首次加载时校验当前激活账号的 token 是否仍有效
    const active = getActiveAccount();
    if (!active) {
      setLoading(false);
      return;
    }
    fetchMe()
      .then(setUser)
      .catch(() => {
        // token 失效则移除该账号，避免下次启动反复失败
        removeAccount(active.username);
        setAccounts(getAccounts());
      })
      .finally(() => setLoading(false));
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const response = await apiLogin(username, password);
    saveAccount(response.user, response.access_token);
    setUser(response.user);
    setAccounts(getAccounts());
  }, []);

  const register = useCallback(async (username: string, password: string) => {
    const response = await apiRegister(username, password);
    saveAccount(response.user, response.access_token);
    setUser(response.user);
    setAccounts(getAccounts());
  }, []);

  const logout = useCallback(() => {
    clearAll();
    setUser(null);
    setAccounts([]);
  }, []);

  const switchAccount = useCallback(
    async (username: string) => {
      if (username === user?.username) return true;
      const previous = user?.username ?? null;
      const account = setActiveAccount(username);
      if (!account) return false;
      try {
        const me = await fetchMe();
        setUser(me);
        saveAccount(me, account.token);
        setAccounts(getAccounts());
        return true;
      } catch {
        // token 失效：移除该账号并回退到原账号
        removeAccount(username);
        if (previous) setActiveAccount(previous);
        setAccounts(getAccounts());
        return false;
      }
    },
    [user?.username],
  );

  const updateProfile = useCallback(
    async (nickname: string, avatar: string | null) => {
      const updated = await apiUpdateProfile(nickname, avatar);
      setUser(updated);
      const token = getToken();
      if (token) saveAccount(updated, token);
      setAccounts(getAccounts());
    },
    [],
  );

  const changePassword = useCallback(
    async (oldPassword: string, newPassword: string) => {
      await apiChangePassword(oldPassword, newPassword);
    },
    [],
  );

  return (
    <AuthContext.Provider
      value={{
        user,
        accounts,
        loading,
        login,
        register,
        logout,
        switchAccount,
        updateProfile,
        changePassword,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error("useAuth 必须在 AuthProvider 内部使用");
  }
  return context;
}
