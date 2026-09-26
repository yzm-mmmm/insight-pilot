/**
 * DeepSeek 账户控件（仅管理员）
 * 在左下角 API 完成指示上方展示：账户余额、去充值入口与运行时模型切换。
 * 余额通过后端代理查询，前端不直接接触 API Key。
 */
import { Coins, ExternalLink, RefreshCw } from "lucide-react";
import { useCallback, useEffect, useState } from "react";
import {
  fetchDeepSeekBalance,
  fetchModelSetting,
  updateModel,
  type DeepSeekBalance,
  type ModelSetting,
} from "../lib/adminApi";
import { cn } from "../lib/format";

const TOP_UP_URL = "https://platform.deepseek.com/top_up";

function formatBalance(balance: DeepSeekBalance | null, loading: boolean) {
  if (loading) return "…";
  if (balance?.is_available && balance.total_balance != null) {
    const symbol = balance.currency === "USD" ? "$" : "¥";
    return `${symbol}${balance.total_balance}`;
  }
  return "—";
}

export function DeepSeekControls() {
  const [setting, setSetting] = useState<ModelSetting | null>(null);
  const [balance, setBalance] = useState<DeepSeekBalance | null>(null);
  const [loadingBalance, setLoadingBalance] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const reloadBalance = useCallback(async () => {
    setLoadingBalance(true);
    try {
      setBalance(await fetchDeepSeekBalance());
    } catch (err) {
      setBalance({
        is_available: false,
        message: err instanceof Error ? err.message : String(err),
      });
    } finally {
      setLoadingBalance(false);
    }
  }, []);

  useEffect(() => {
    fetchModelSetting()
      .then(setSetting)
      .catch((err) =>
        setError(err instanceof Error ? err.message : String(err)),
      );
    reloadBalance();
  }, [reloadBalance]);

  const handleModelChange = async (model: string) => {
    if (!model || model === setting?.current) return;
    setSaving(true);
    setError(null);
    try {
      setSetting(await updateModel(model));
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="border-t border-white/10 px-4 py-3 text-xs text-white/85">
      <div className="mb-2 flex items-center gap-2 font-semibold uppercase tracking-[0.16em] text-white/75">
        <Coins className="h-3.5 w-3.5" aria-hidden="true" />
        DeepSeek
      </div>

      <div className="space-y-2">
        <div className="flex items-center justify-between gap-2">
          <span className="text-white/60">余额</span>
          <span className="flex items-center gap-1.5">
            <span
              className="font-mono text-white"
              title={balance?.is_available ? balance.message ?? undefined : balance?.message ?? undefined}
            >
              {formatBalance(balance, loadingBalance)}
            </span>
            <button
              type="button"
              onClick={reloadBalance}
              disabled={loadingBalance}
              className="rounded p-0.5 text-white/60 transition hover:bg-white/10 hover:text-white disabled:opacity-50"
              title="刷新余额"
              aria-label="刷新余额"
            >
              <RefreshCw
                className={cn("h-3 w-3", loadingBalance && "animate-spin")}
                aria-hidden="true"
              />
            </button>
          </span>
        </div>

        <div className="flex items-center justify-between gap-2">
          <span className="text-white/60">模型</span>
          <select
            value={setting?.current ?? ""}
            onChange={(event) => handleModelChange(event.target.value)}
            disabled={saving || !setting}
            className="max-w-[150px] truncate rounded border border-white/15 bg-white/10 px-1.5 py-1 font-mono text-white outline-none transition focus:border-white/40 disabled:opacity-50 [&>option]:text-black"
            title="切换运行时模型（对后续查询生效）"
          >
            {setting
              ? setting.available.map((model) => (
                  <option key={model} value={model}>
                    {model}
                  </option>
                ))
              : (
                  <option value="">加载中…</option>
                )}
          </select>
        </div>

        <a
          href={TOP_UP_URL}
          target="_blank"
          rel="noreferrer"
          className="flex items-center justify-center gap-1.5 rounded border border-white/15 bg-white/5 py-1.5 text-white/85 transition hover:border-white/30 hover:bg-white/10"
        >
          去充值
          <ExternalLink className="h-3 w-3" aria-hidden="true" />
        </a>
      </div>

      {error && <div className="mt-1.5 text-white/60">{error}</div>}
    </div>
  );
}
