/**
 * 智能体类型定义
 * 定义问数智能体前端使用的 SSE 事件、流程步骤、结构化结果、图表规格和聊天消息类型
 */
export type ProgressStatus = "running" | "success" | "error";

export type ProgressEvent = {
  type: "progress";
  step: string;
  status: ProgressStatus;
};

export type StructuredResult = {
  columns: string[];
  rows: Array<Record<string, unknown>>;
  sql?: string;
};

export type ResultEvent = {
  type: "result";
  data: StructuredResult;
};

export type ErrorEvent = {
  type: "error";
  message: string;
};

export type PlanItem = {
  id: number;
  question: string;
  intent: string;
};

export type PlanEvent = {
  type: "plan";
  intent: string;
  plan: PlanItem[];
};

export type InsightEvent = {
  type: "insight";
  content: string;
  next_action: string;
};

export type AskEvent = {
  type: "ask";
  question: string;
};

export type ChartSpec = {
  id: string;
  type: "bar" | "line" | "pie" | "scatter";
  title: string;
  xField?: string;
  yFields?: string[];
  series?: string[];
  rows: Array<Record<string, unknown>>;
};

export type ChartEvent = {
  type: "chart";
  data: ChartSpec;
};

export type ReportEvent = {
  type: "report";
  markdown: string;
};

export type SessionEvent = {
  type: "session";
  id: number;
  title: string;
};

export type MessageSavedEvent = {
  type: "message_saved";
  id: number;
};

export type AgentEvent =
  | ProgressEvent
  | ResultEvent
  | ErrorEvent
  | PlanEvent
  | InsightEvent
  | AskEvent
  | ChartEvent
  | ReportEvent
  | SessionEvent
  | MessageSavedEvent;

export type ChatSession = {
  id: number;
  title: string;
  created_at: string;
  updated_at: string;
};

export type SessionMessage = {
  id: number;
  role: "user" | "assistant";
  content: string | null;
  query_sql: string | null;
  result_summary: string | null;
  created_at: string;
};

export type FlowStep = {
  step: string;
  status: ProgressStatus;
  updatedAt: number;
  startedAt?: number;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  content: string;
  createdAt: number;
  status?: "streaming" | "done" | "error";
  intent?: string;
  plan?: PlanItem[];
  flow?: FlowStep[];
  results?: StructuredResult[];
  charts?: ChartSpec[];
  report?: string;
  querySql?: string;
  error?: string;
  messageId?: number;
};

/**
 * 链路追踪类型
 * 对应后端 TraceCollector.to_dict() 落盘到 logs/traces.jsonl 的结构。
 */
export type TraceNodeSpan = {
  step: string;
  status: ProgressStatus;
  started_at: number;
  duration_ms: number;
};

export type TraceLLMCall = {
  model: string | null;
  duration_ms: number | null;
  step?: string | null;
  prompt_tokens?: number | null;
  completion_tokens?: number | null;
  total_tokens?: number | null;
};

export type Trace = {
  trace_id: string;
  query: string;
  session_id: number;
  user_id: number;
  status: "success" | "error";
  error: string | null;
  started_at: number;
  duration_ms: number;
  total_tokens: number;
  total_cost_cny?: number | null;
  estimated_cost_usd?: number | null;
  llm_call_count: number;
  node_spans: TraceNodeSpan[];
  llm_calls: TraceLLMCall[];
  message_id?: number | null;
  sql_history?: string[];
  sql_retry_count?: number;
  iteration_count?: number;
  next_action?: string | null;
  chart_count?: number;
};
