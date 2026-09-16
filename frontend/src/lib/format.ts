/**
 * 通用格式化工具
 * 提供 className 合并、时间格式化和查询结果文本化等通用工具函数
 */
export function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

export function formatTime(timestamp: number) {
  return new Intl.DateTimeFormat("zh-CN", {
    hour: "2-digit",
    minute: "2-digit",
  }).format(timestamp);
}

/**
 * 解析后端返回的时间字符串。
 * 后端统一存 UTC 并带 ``Z`` 后缀；个别旧数据可能无时区，这里兜底按 UTC 解析，
 * 避免被浏览器当成本地时间而差出时区偏移。
 */
export function parseServerDate(value: string | null | undefined): Date | null {
  if (!value) return null;
  const text = value.trim();
  const hasZone = /(?:Z|[+-]\d{2}:?\d{2})$/.test(text);
  const date = new Date(hasZone ? text : `${text}Z`);
  return Number.isNaN(date.getTime()) ? null : date;
}

export function formatDateTime(value: string | null | undefined): string {
  const date = parseServerDate(value);
  return date ? date.toLocaleString() : "";
}

export function formatShortDateTime(value: string | null | undefined): string {
  const date = parseServerDate(value);
  if (!date) return "";
  return `${date.getMonth() + 1}/${date.getDate()} ${String(date.getHours()).padStart(2, "0")}:${String(date.getMinutes()).padStart(2, "0")}`;
}

export function summarizeResult(data: unknown) {
  // 结构化结果：{ columns, rows }
  if (data && typeof data === "object" && !Array.isArray(data) && "rows" in data) {
    const rows = (data as { rows?: unknown[] }).rows ?? [];
    return rows.length > 0 ? `查询完成，共 ${rows.length} 行结果。` : "查询完成，结果为空。";
  }

  if (Array.isArray(data)) {
    return data.length > 0 ? `查询完成，共 ${data.length} 行结果。` : "查询完成，结果为空。";
  }

  if (data && typeof data === "object") {
    return "查询完成，已返回结构化结果。";
  }

  if (data === null || data === undefined || data === "") {
    return "查询完成，结果为空。";
  }

  return `查询完成：${String(data)}`;
}

export function toClipboardText(value: unknown) {
  if (typeof value === "string") return value;
  return JSON.stringify(value, null, 2);
}
