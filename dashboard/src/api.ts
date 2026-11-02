export interface AliveEvent {
  event_id: string;
  sequence_number: number;
  event_type: string;
  source: string;
  timestamp: string;
  correlation_id: string;
  payload: Record<string, unknown>;
}
export interface Memory {
  id: string;
  content: string;
  source_event_id: string;
  memory_type: string;
  created_at: string;
}
export interface Goal {
  id: string;
  title: string;
  description: string;
  status: string;
  origin: string;
}
export interface Run {
  id: string;
  runner: string;
  status: string;
  objective: string;
  result: string | null;
  error: string | null;
}
export interface Session {
  id: string;
  status: string;
  current_url: string;
}
export interface State {
  identity: { id: string; name: string; lifecycle_state: string };
  runtime: {
    heartbeat_at: string | null;
    state_version: number;
    active_goals: string[];
  };
  drives: Record<string, string>;
}
export interface Capabilities {
  database: { available: boolean; backend: string; error: string | null };
  pgvector: {
    storage: boolean;
    search: boolean;
    reason: string;
    provider?: string;
    model?: string;
    dimension?: number;
  };
  zeromq: { available: boolean; received: number };
  pi: {
    configured: boolean;
    installed?: boolean;
    command_configured?: boolean;
    command_source?: string;
    provider?: string;
    model?: string;
    reason?: string;
    next_action?: string;
  };
  ollama?: {
    available: boolean;
    url: string;
    models: string[];
    chat_model: string | null;
    embedding_model: string | null;
    reason: string;
  };
  providers: { meta: { configured: boolean } };
}
export function resolveApiBase(): string {
  const configured = (
    (import.meta.env.VITE_ALIVE_API_BASE as string | undefined) || ""
  ).trim();
  if (configured) return configured.replace(/\/$/, "");
  if (
    typeof window !== "undefined" &&
    (window.location.port === "5173" || window.location.port === "5174")
  )
    return "http://127.0.0.1:8000";
  return "";
}
export const base = resolveApiBase();
export function wsBase(): string {
  if (base.startsWith("http"))
    return base.replace("http", "ws") + "/api/v1/events/stream";
  if (typeof window !== "undefined")
    return (
      window.location.protocol.replace("http", "ws") +
      "//" +
      window.location.host +
      "/api/v1/events/stream"
    );
  return "ws://127.0.0.1:8000/api/v1/events/stream";
}
export class ApiError extends Error {
  constructor(
    public readonly status: number | null,
    message: string,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
export function isAuthenticationError(error: unknown): error is ApiError {
  return (
    error instanceof ApiError && (error.status === 401 || error.status === 403)
  );
}
const authenticationListeners = new Set<(token: string) => void>();
export function subscribeAuthenticationRejection(
  listener: (token: string) => void,
) {
  authenticationListeners.add(listener);
  return () => {
    authenticationListeners.delete(listener);
  };
}
export async function request<T>(
  path: string,
  token: string,
  body?: unknown,
  method?: string,
  signal?: AbortSignal,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(base + "/api/v1" + path, {
      signal,
      method: method || (body === undefined ? "GET" : "POST"),
      headers: {
        Authorization: "Bearer " + token,
        "Content-Type": "application/json",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch (error) {
    if (error instanceof Error && error.name === "AbortError") throw error;
    throw new ApiError(null, "Unable to connect to ALIVE.");
  }
  const status = response.status ?? null;
  // Authentication status wins even if an intermediary supplied HTML or invalid JSON.
  if (status === 401 || status === 403) {
    authenticationListeners.forEach((listener) => listener(token));
    throw new ApiError(status, "Invalid token — try again.");
  }
  let data;
  try {
    data = await response.json();
  } catch {
    throw new ApiError(status, "ALIVE returned an unreadable response.");
  }
  if (!response.ok) {
    const detail = data?.error?.message || data?.detail;
    const message =
      typeof detail === "string" ? detail : `HTTP ${status ?? "error"}`;
    const safeMessage = token
      ? message.replaceAll(token, "[redacted]")
      : message;
    throw new ApiError(status, safeMessage.slice(0, 512));
  }
  return data;
}
export function mergeEvents(
  old: AliveEvent[],
  incoming: AliveEvent[],
): AliveEvent[] {
  const map = new Map(old.map((e) => [e.event_id, e]));
  incoming.forEach((e) => map.set(e.event_id, e));
  return [...map.values()]
    .sort((a, b) => b.sequence_number - a.sequence_number)
    .slice(0, 300);
}
