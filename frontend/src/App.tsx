/**
 * 前端应用根组件
 * 挂载登录态上下文并配置路由，登录页与问数主界面之间的跳转由路由守卫控制
 */
import { Navigate, Route, Routes } from "react-router-dom";
import { RequireAuth } from "./components/RequireAuth";
import { AuthProvider, useAuth } from "./context/AuthContext";
import ChatPage from "./pages/ChatPage";
import LoginPage from "./pages/LoginPage";

function AppRoutes() {
  const { user } = useAuth();
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route
        path="/"
        element={
          <RequireAuth>
            {/* 切换账号时用 user.id 作 key，让主界面整体重挂载以清空旧账号的会话/消息状态 */}
            <ChatPage key={user?.id ?? 0} />
          </RequireAuth>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
