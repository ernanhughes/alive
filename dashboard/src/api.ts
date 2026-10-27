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
  pgvector: { storage: boolean; search: boolean; reason: string };
  zeromq: { available: boolean; received: number };
  pi: { configured: boolean };
  providers: { meta: { configured: boolean } };
}
export const base = "http://127.0.0.1:8000";
export async function request<T>(
  path: string,
  token: string,
  body?: unknown,
  method?: string,
): Promise<T> {
  const response = await fetch(base + "/api/v1" + path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    },
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  const data = await response.json();
  if (!response.ok)
    throw new Error(
      data.error?.message || data.detail || `HTTP ${response.status}`,
    );
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
