/**
 * 反馈接口客户端
 * 封装对单条智能体消息提交反馈（赞/踩/纠错）的请求。
 */
import { getToken } from "./auth";

export type FeedbackKind = "like" | "dislike" | "correct";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ?? "";

export async function submitFeedback(
  messageId: number,
  payload: { kind: FeedbackKind; comment?: string | null; corrected_sql?: string | null },
): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/api/messages/${messageId}/feedback`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      ...(getToken() ? { Authorization: `Bearer ${getToken()}` } : {}),
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    let message = `反馈提交失败：HTTP ${response.status}`;
    try {
      const body = await response.json();
      if (body?.detail) message = body.detail;
    } catch {
      // 错误体不是 JSON 时保留默认提示
    }
    throw new Error(message);
  }
}
