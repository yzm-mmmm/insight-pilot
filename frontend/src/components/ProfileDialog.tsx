/**
 * 个人资料编辑弹窗
 * 支持修改头像、昵称与密码，保存后同步全局登录态。
 * 视觉风格与数据权限面板保持一致（浅绿底 + 黑字 + 白卡片）。
 */
import { useEffect, useRef, useState } from "react";
import { Camera, KeyRound, Loader2, UserRound, X } from "lucide-react";
import { useAuth } from "../context/AuthContext";
import { fileToDataUrl } from "../lib/image";

const inputClass =
  "w-full border border-black/10 bg-white/80 px-3 py-2.5 text-sm text-black outline-none transition placeholder:text-black/40 focus:border-moss/60 focus:ring-2 focus:ring-moss/30";

export function ProfileDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const { user, updateProfile, changePassword } = useAuth();
  const [nickname, setNickname] = useState("");
  const [avatar, setAvatar] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [savingProfile, setSavingProfile] = useState(false);

  const [oldPassword, setOldPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [changingPassword, setChangingPassword] = useState(false);

  const fileRef = useRef<HTMLInputElement | null>(null);

  // 打开时用最新用户信息回填，并清空密码区与提示
  useEffect(() => {
    if (!open) return;
    setNickname(user?.nickname ?? "");
    setAvatar(user?.avatar ?? null);
    setMessage(null);
    setError(null);
    setOldPassword("");
    setNewPassword("");
    setConfirmPassword("");
  }, [open, user]);

  if (!open) return null;

  const displayName = user?.nickname || user?.username || "?";

  const onPickAvatar = async (file?: File) => {
    if (!file) return;
    try {
      setAvatar(await fileToDataUrl(file, 256));
      setError(null);
    } catch {
      setError("头像读取失败");
    }
  };

  const saveProfile = async () => {
    setSavingProfile(true);
    setMessage(null);
    setError(null);
    try {
      await updateProfile(nickname.trim(), avatar);
      setMessage("个人资料已保存");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSavingProfile(false);
    }
  };

  const submitPassword = async () => {
    setMessage(null);
    setError(null);
    if (!oldPassword || !newPassword) {
      setError("请填写原密码和新密码");
      return;
    }
    if (newPassword.length < 6) {
      setError("新密码至少 6 位");
      return;
    }
    if (newPassword !== confirmPassword) {
      setError("两次输入的新密码不一致");
      return;
    }
    setChangingPassword(true);
    try {
      await changePassword(oldPassword, newPassword);
      setOldPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("密码已修改");
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setChangingPassword(false);
    }
  };

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4 backdrop-blur-sm"
      onClick={onClose}
    >
      <div
        className="flex max-h-[82vh] w-full max-w-lg flex-col border border-black/10 bg-[#dcfce7] shadow-panel"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-center justify-between border-b border-black/10 px-5 py-4">
          <div className="flex items-center gap-2 text-base font-semibold text-black">
            <UserRound className="h-4 w-4 text-emerald-700" aria-hidden="true" />
            个人资料
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-full p-1.5 text-black/60 transition hover:bg-black/5 hover:text-black"
            aria-label="关闭"
          >
            <X className="h-4 w-4" aria-hidden="true" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-6 overflow-y-auto px-5 py-5">
          <div className="flex items-start gap-4">
            <button
              type="button"
              onClick={() => fileRef.current?.click()}
              className="group relative grid h-16 w-16 shrink-0 place-items-center overflow-hidden rounded-full bg-emerald-100 text-emerald-700"
              title="上传头像"
            >
              {avatar ? (
                <img src={avatar} alt="头像" className="h-full w-full object-cover" />
              ) : (
                <span className="text-xl font-semibold">{displayName.slice(0, 1).toUpperCase()}</span>
              )}
              <span className="absolute inset-0 grid place-items-center bg-black/50 text-white opacity-0 transition group-hover:opacity-100">
                <Camera className="h-5 w-5" aria-hidden="true" />
              </span>
            </button>
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              className="hidden"
              onChange={(event) => onPickAvatar(event.target.files?.[0])}
            />
            <div className="min-w-0 flex-1 space-y-1.5">
              <label htmlFor="nickname" className="block text-xs font-semibold text-black/60">
                昵称
              </label>
              <input
                id="nickname"
                type="text"
                value={nickname}
                onChange={(event) => setNickname(event.target.value)}
                placeholder={user?.username}
                className={inputClass}
              />
              <div className="text-xs text-black/50">登录名：{user?.username}（不可修改）</div>
            </div>
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              onClick={saveProfile}
              disabled={savingProfile}
              className="flex h-10 items-center justify-center gap-2 bg-moss px-4 text-sm font-semibold text-white transition hover:bg-soot disabled:cursor-not-allowed disabled:bg-moss/40"
            >
              {savingProfile && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
              保存资料
            </button>
          </div>

          <div className="border-t border-black/10 pt-5">
            <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-black">
              <KeyRound className="h-4 w-4 text-emerald-700" aria-hidden="true" />
              修改密码
            </div>
            <div className="space-y-3">
              <input
                type="password"
                value={oldPassword}
                onChange={(event) => setOldPassword(event.target.value)}
                placeholder="原密码"
                autoComplete="current-password"
                className={inputClass}
              />
              <input
                type="password"
                value={newPassword}
                onChange={(event) => setNewPassword(event.target.value)}
                placeholder="新密码（至少 6 位）"
                autoComplete="new-password"
                className={inputClass}
              />
              <input
                type="password"
                value={confirmPassword}
                onChange={(event) => setConfirmPassword(event.target.value)}
                placeholder="确认新密码"
                autoComplete="new-password"
                className={inputClass}
              />
            </div>
            <div className="mt-3 flex justify-end">
              <button
                type="button"
                onClick={submitPassword}
                disabled={changingPassword}
                className="flex h-10 items-center justify-center gap-2 border border-black/20 px-4 text-sm font-semibold text-black transition hover:bg-black/5 disabled:cursor-not-allowed disabled:bg-black/5"
              >
                {changingPassword && <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />}
                修改密码
              </button>
            </div>
          </div>

          {message && (
            <div className="border border-moss/40 bg-moss/20 px-3 py-2 text-sm text-black">{message}</div>
          )}
          {error && (
            <div className="border border-tomato/40 bg-tomato/25 px-3 py-2 text-sm text-black">{error}</div>
          )}
        </div>
      </div>
    </div>
  );
}
