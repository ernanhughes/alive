import React, { useCallback, useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  Activity,
  ArrowUpRight,
  BrainCircuit,
  ChevronRight,
  Command,
  Globe2,
  Layers3,
  Leaf,
  Pause,
  Play,
  Radio,
  Search,
  Terminal,
  Waypoints,
  X,
} from "lucide-react";
import { base, mergeEvents, request } from "./api";
import type {
  AliveEvent,
  Capabilities,
  Goal,
  Memory,
  Run,
  Session,
  State,
} from "./api";
import "./style.css";
import { CognitionPane } from "./Cognition";
import { LivingPane } from "./Living";

const tabs = [
  "Overview",
  "Living",
  "Live events",
  "Memory",
  "Agents",
  "Browser",
  "Runtime",
  "Cognition",
] as const;
type Tab = (typeof tabs)[number];
const icons = [
  Layers3,
  Leaf,
  Radio,
  BrainCircuit,
  Terminal,
  Globe2,
  Waypoints,
  BrainCircuit,
];
const time = (s: string | null | undefined) =>
  s ? new Date(s).toLocaleTimeString("en-GB") : "Awaiting heartbeat";
export function EventList({ events }: { events: AliveEvent[] }) {
  return (
    <div className="events">
      {events.length ? (
        events.map((e) => (
          <details key={e.event_id}>
            <summary>
              <span
                className={
                  "event-dot " +
                  (e.event_type.startsWith("browser") ? "blue" : "")
                }
              />
              <span className="event-name">
                {e.event_type}
                <small>
                  {e.source} · {e.correlation_id.slice(0, 8)}
                </small>
              </span>
              <time>{time(e.timestamp)}</time>
              <ChevronRight size={14} />
            </summary>
            <pre>{JSON.stringify(e.payload, null, 2)}</pre>
          </details>
        ))
      ) : (
        <p className="empty">
          No observations yet. Start the runtime and explore the habitat.
        </p>
      )}
    </div>
  );
}
export function App() {
  const [tab, setTab] = useState<Tab>("Overview");
  const [token, setToken] = useState(
    () => sessionStorage.getItem("alive-token") || "",
  );
  const [draftToken, setDraftToken] = useState(token);
  const [state, setState] = useState<State | null>(null),
    [caps, setCaps] = useState<Capabilities | null>(null);
  const [events, setEvents] = useState<AliveEvent[]>([]),
    [memories, setMemories] = useState<Memory[]>([]),
    [goals, setGoals] = useState<Goal[]>([]),
    [runs, setRuns] = useState<Run[]>([]),
    [sessions, setSessions] = useState<Session[]>([]);
  const [error, setError] = useState(""),
    [online, setOnline] = useState(false),
    [busy, setBusy] = useState(false),
    [live, setLive] = useState(false);
  const [searchResults, setSearchResults] = useState<Memory[]>([]);
  const [retrievalMode, setRetrievalMode] = useState("text");
  const [query, setQuery] = useState(""),
    [searchMode, setSearchMode] = useState(""),
    [objective, setObjective] = useState(""),
    [runner, setRunner] = useState("mock");
  const [url, setUrl] = useState(base + "/demo"),
    [sessionId, setSessionId] = useState(""),
    [selector, setSelector] = useState("#change"),
    [value, setValue] = useState("A green light appeared in the habitat."),
    [page, setPage] = useState<Record<string, string> | null>(null);
  const [goalTitle, setGoalTitle] = useState("");
  const cursor = useRef(0);
  const refresh = useCallback(async () => {
    if (!token) return;
    const c = await request<Capabilities>("/capabilities", token);
    setCaps(c);
    const [s, m, g, a, b] = await Promise.all([
      request<State>("/alive", token),
      request<Memory[]>("/memories", token),
      request<Goal[]>("/goals", token),
      request<{ runs: Run[] }>("/agents", token),
      request<Session[]>("/browser/sessions", token),
    ]);
    setState(s);
    setMemories(m);
    setGoals(g);
    setRuns(a.runs);
    setSessions(b);
    setOnline(true);
  }, [token]);
  useEffect(() => {
    if (!token) return;
    refresh().catch((e) => {
      setError(e.message);
      setOnline(false);
    });
    const timer = setInterval(
      () => refresh().catch(() => setOnline(false)),
      5000,
    );
    return () => clearInterval(timer);
  }, [token, refresh]);
  useEffect(() => {
    if (!token) return;
    let socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout>,
      disposed = false;
    function connect() {
      socket = new WebSocket(
        base.replace("http", "ws") + "/api/v1/events/stream",
      );
      socket.onopen = () =>
        socket?.send(JSON.stringify({ token, after: cursor.current }));
      socket.onmessage = (e) => {
        const event = JSON.parse(e.data) as AliveEvent;
        cursor.current = Math.max(cursor.current, event.sequence_number);
        setEvents((old) => mergeEvents(old, [event]));
        setLive(true);
      };
      socket.onclose = () => {
        setLive(false);
        if (!disposed) timer = setTimeout(connect, 2000);
      };
      socket.onerror = () => socket?.close();
    }
    connect();
    return () => {
      disposed = true;
      clearTimeout(timer);
      socket?.close();
    };
  }, [token]);
  async function act(fn: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await fn();
      await refresh();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }
  const running = state?.identity.lifecycle_state === "running";
  async function browserAction(operation: string) {
    if (!sessionId) throw new Error("Open or select a managed session first");
    setPage(
      await request("/browser/sessions/" + sessionId + "/actions", token, {
        operation,
        selector,
        value,
      }),
    );
  }
  return (
    <div className="shell">
      <aside>
        <a
          className="brand"
          href="#"
          onClick={(e) => {
            e.preventDefault();
            setTab("Overview");
          }}
        >
          <span className="brand-icon">
            a<span>•</span>
          </span>
          ALIVE<span className="version">01</span>
        </a>
        <div className="sidebar-label">OBSERVATORY</div>
        <nav>
          {tabs.map((t, i) => {
            const Icon = icons[i];
            return (
              <button
                className={tab === t ? "selected" : ""}
                onClick={() => setTab(t)}
                key={t}
              >
                <Icon size={18} />
                {t}
                {t === "Live events" && (
                  <span className="count">{events.length}</span>
                )}
              </button>
            );
          })}
        </nav>
        <div className="sidebar-bottom">
          <div className="habitat">
            <span className="dot" />
            Local habitat<small>127.0.0.1 · Development</small>
          </div>
          <p>Adaptive Living Intelligence</p>
          <span className="muted">A continuing internal life.</span>
        </div>
      </aside>
      <main>
        <header>
          <div className="breadcrumb">
            Workspace <ChevronRight size={13} /> ALIVE-01{" "}
            <ChevronRight size={13} />
            <strong>{tab}</strong>
          </div>
          <div className="connection">
            <span className={"dot " + (!online ? "off" : "")} />
            {online ? "Backend connected" : "Backend disconnected"}
            <button
              className="keycap"
              onClick={() => {
                sessionStorage.removeItem("alive-token");
                setToken("");
                setState(null);
                setOnline(false);
                setEvents([]);
                cursor.current = 0;
              }}
              title="Change local connection token"
            >
              <Command size={12} /> local
            </button>
          </div>
        </header>
        <div className="content">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                {tab === "Living" ? "ALIVE-04 / CONTINUING EXPERIENCE" : tab === "Cognition"
                  ? "ALIVE-02 / COGNITIVE SOCIETY"
                  : "ALIVE-01 / FIRST CONTACT"}
              </div>
              <h1>
                {tab === "Overview"
                  ? "Something is becoming."
                  : tab === "Living" ? "The living experience." : tab === "Live events"
                    ? "The stream of experience."
                    : tab === "Memory"
                      ? "Experience, remembered."
                      : tab === "Agents"
                        ? "Thought into action."
                        : tab === "Browser"
                          ? "A window to the world."
                          : tab === "Cognition"
                            ? "Evidence becomes intention."
                            : "A persistent presence."}
              </h1>
              <p>
                {tab === "Overview"
                  ? "Observe the runtime. Follow its attention. See what stays."
                  : "Inspect the real state of your local ALIVE runtime."}
              </p>
            </div>
            <button
              disabled={busy || !state}
              className="primary"
              onClick={() =>
                act(() =>
                  request("/alive/" + (running ? "stop" : "start"), token, {}),
                )
              }
            >
              {running ? <Pause size={15} /> : <Play size={15} />}{" "}
              {running ? "Suspend runtime" : "Start runtime"}
            </button>
          </div>
          {!token && (
            <form
              className="panel connect-form"
              onSubmit={(e) => {
                e.preventDefault();
                sessionStorage.setItem("alive-token", draftToken);
                setToken(draftToken);
                setError("");
              }}
            >
              <h2>Connect to your habitat</h2>
              <p>
                Enter the local token from <code>.alive/token</code> or your
                environment configuration.
              </p>
              <label>
                Local API token
                <input
                  type="password"
                  value={draftToken}
                  onChange={(e) => setDraftToken(e.target.value)}
                  required
                />
              </label>
              <button className="primary">
                Connect <ArrowUpRight size={15} />
              </button>
            </form>
          )}
          {error && (
            <div className="error" role="alert">
              {error}
              <button aria-label="Dismiss error" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {(tab === "Overview" || tab === "Runtime") && (
            <>
              <div className="metrics">
                <div className="metric">
                  <span>
                    Runtime state <Activity size={16} />
                  </span>
                  <strong>
                    <i className={"dot " + (!running ? "off" : "")} />
                    {state?.identity.lifecycle_state || "Not connected"}
                  </strong>
                  <small>
                    {state ? state.identity.name : "Waiting for local identity"}
                  </small>
                </div>
                <div className="metric">
                  <span>
                    Last heartbeat <Radio size={16} />
                  </span>
                  <strong>{time(state?.runtime.heartbeat_at)}</strong>
                  <small>Lightweight scheduler · no model calls</small>
                </div>
                <div className="metric">
                  <span>
                    Persistent memories <BrainCircuit size={16} />
                  </span>
                  <strong>{memories.length.toString().padStart(2, "0")}</strong>
                  <small>
                    {caps?.database.backend === "postgresql"
                      ? "PostgreSQL full-text search"
                      : "Local development storage"}
                  </small>
                </div>
                <div className="metric">
                  <span>
                    Unfinished goals <Waypoints size={16} />
                  </span>
                  <strong>
                    {goals
                      .filter(
                        (g) => !["completed", "cancelled"].includes(g.status),
                      )
                      .length.toString()
                      .padStart(2, "0")}
                  </strong>
                  <small>
                    {goals.filter((g) => g.status === "proposed").length}{" "}
                    awaiting acceptance
                  </small>
                </div>
              </div>
              <div className="overview-grid">
                <section className="panel habitat-panel">
                  <div className="panel-top">
                    <span className="eyebrow">PERSISTENT ENTITY</span>
                    <span className="tag">
                      {running ? "ACTIVE" : "SUSPENDED"}
                    </span>
                  </div>
                  <div className={"organism " + (running ? "breathing" : "")}>
                    <div className="orbit o1" />
                    <div className="orbit o2" />
                    <div className="orbit o3" />
                    <div className="core">
                      <Activity size={33} />
                    </div>
                    <span className="satellite s1" />
                    <span className="satellite s2" />
                  </div>
                  <h2>{state?.identity.name || "ALIVE-01"}</h2>
                  <p>Perceive. Remember. Initiate. Continue.</p>
                  <div className="identity">
                    <span>IDENTITY</span>
                    <code>{state?.identity.id || "Awaiting connection"}</code>
                    <span>
                      STATE VERSION <b>{state?.runtime.state_version || "—"}</b>
                    </span>
                  </div>
                </section>
                <section className="panel timeline-panel">
                  <div className="panel-top">
                    <h2>
                      Live event stream{" "}
                      <span className="tag subtle">
                        {live ? "LIVE" : "WAITING"}
                      </span>
                    </h2>
                    <button
                      className="text-button"
                      onClick={() => setTab("Live events")}
                    >
                      View all <ArrowUpRight size={14} />
                    </button>
                  </div>
                  <EventList events={events.slice(0, 6)} />
                  <div className="panel-foot">
                    <span className="dot" />
                    {caps?.zeromq.received || 0} received through ZeroMQ ·
                    persisted history recovers gaps
                  </div>
                </section>
              </div>
              <div className="bottom-grid">
                <section className="panel">
                  <div className="panel-top">
                    <h2>Internal drives</h2>
                    <span className="muted">DETERMINISTIC POLICIES</span>
                  </div>
                  {Object.entries(state?.drives || {}).map(
                    ([name, description], i) => (
                      <div className="drive" key={name}>
                        <span className="drive-number">0{i + 1}</span>
                        <div>
                          <strong>{name}</strong>
                          <p>{description}</p>
                        </div>
                        <span className="dot" />
                      </div>
                    ),
                  )}
                </section>
                <section className="panel">
                  <div className="panel-top">
                    <h2>Infrastructure</h2>
                    <span className="tag subtle">LOCAL</span>
                  </div>
                  {[
                    [
                      "Persistence",
                      caps?.database.available
                        ? caps.database.backend
                        : "Unavailable",
                    ],
                    [
                      "Event transport",
                      caps?.zeromq.available
                        ? "ZeroMQ · connected"
                        : "Unavailable",
                    ],
                    [
                      "Semantic search",
                      caps?.pgvector.search
                        ? "Available"
                        : "No embedding model",
                    ],
                    [
                      "Pi agent",
                      caps?.pi.configured
                        ? "Configured · tools disabled"
                        : "Needs model configuration",
                    ],
                  ].map(([name, status]) => (
                    <div className="infra" key={name}>
                      <span>{name}</span>
                      <span>{status}</span>
                    </div>
                  ))}
                </section>
              </div>
            </>
          )}
          {tab === "Live events" && (
            <section className="panel">
              <div className="panel-top">
                <h2>Persisted event timeline</h2>
                <span className="tag">{events.length} EVENTS</span>
              </div>
              <EventList events={events} />
            </section>
          )}
          {tab === "Memory" && (
            <section className="panel">
              <div className="panel-top">
                <h2>Memory explorer</h2>
                <span className="tag subtle">
                  {caps?.pgvector.search
                    ? "SEMANTIC SEARCH AVAILABLE"
                    : "FULL-TEXT MODE"}
                </span>
              </div>
              <form
                className="form-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    const data = await request<{
                      mode: string;
                      results: Memory[];
                    }>("/memories/search", token, {
                      query,
                      mode: retrievalMode,
                    });
                    setSearchResults(data.results);
                    setSearchMode(data.mode);
                  });
                }}
              >
                <Search size={18} />
                <select
                  aria-label="Retrieval mode"
                  value={retrievalMode}
                  onChange={(e) => setRetrievalMode(e.target.value)}
                >
                  <option value="text">Full text</option>
                  <option value="vector">Vector similarity</option>
                  <option value="hybrid">Hybrid</option>
                </select>
                <input
                  aria-label="Search memories"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search persistent experiences…"
                  required
                />
                <button disabled={busy}>Search</button>
              </form>
              <p className="muted">{searchMode || caps?.pgvector.reason}</p>
              {(searchMode ? searchResults : memories).length ? (
                (searchMode ? searchResults : memories).map((m) => (
                  <article className="memory" key={m.id}>
                    <span className="eyebrow">
                      {m.memory_type} · {time(m.created_at)}
                    </span>
                    <p>{m.content}</p>
                    <small>Source event: {m.source_event_id}</small>
                  </article>
                ))
              ) : (
                <p className="empty">
                  No matching memories. Observe a page or try another search.
                </p>
              )}
            </section>
          )}
          {tab === "Agents" && (
            <div className="two-columns">
              <section className="panel">
                <div className="panel-top">
                  <h2>Agent console</h2>
                  <Terminal size={18} />
                </div>
                <form
                  onSubmit={(e) => {
                    e.preventDefault();
                    act(() =>
                      request("/agents/runs", token, { runner, objective }),
                    );
                  }}
                >
                  <label>
                    Runner
                    <select
                      aria-label="Runner"
                      value={runner}
                      onChange={(e) => setRunner(e.target.value)}
                    >
                      <option value="mock">Deterministic mock</option>
                      <option value="pi">Pi · live RPC</option>
                    </select>
                  </label>
                  <label>
                    Objective
                    <textarea
                      value={objective}
                      onChange={(e) => setObjective(e.target.value)}
                      placeholder="Examine an observation and propose a follow-up…"
                      required
                    />
                  </label>
                  <p className="muted">
                    Pi operates in an isolated workspace with all tools
                    disabled.
                  </p>
                  <button className="primary" disabled={busy}>
                    <Play size={15} />
                    Run agent
                  </button>
                </form>
                <EventList
                  events={events
                    .filter((e) => e.event_type.startsWith("agent."))
                    .slice(0, 12)}
                />
              </section>
              <section className="panel">
                <div className="panel-top">
                  <h2>Execution history</h2>
                  <span className="tag subtle">{runs.length} RUNS</span>
                </div>
                {runs.length ? (
                  runs.map((r) => (
                    <article className="memory" key={r.id} data-run-id={r.id}>
                      <span className="eyebrow">
                        {r.runner} / {r.status}
                      </span>
                      <p>{r.objective}</p>
                      <pre>{r.result || r.error || "Executing…"}</pre>
                      {r.status === "running" && (
                        <button
                          onClick={() =>
                            act(() =>
                              request(
                                "/agents/runs/" + r.id + "/cancel",
                                token,
                                {},
                              ),
                            )
                          }
                        >
                          Cancel
                        </button>
                      )}
                    </article>
                  ))
                ) : (
                  <p className="empty">
                    No runs yet. Give an agent a controlled objective.
                  </p>
                )}
              </section>
            </div>
          )}
          {tab === "Browser" && (
            <div className="two-columns">
              <section className="panel">
                <div className="panel-top">
                  <h2>Managed Chrome</h2>
                  <Globe2 size={18} />
                </div>
                <button
                  disabled={busy}
                  className="primary"
                  onClick={() =>
                    act(async () => {
                      const s = await request<Session>(
                        "/browser/sessions",
                        token,
                        {},
                      );
                      setSessionId(s.id);
                    })
                  }
                >
                  Open managed session <ArrowUpRight size={15} />
                </button>
                <label>
                  Session
                  <select
                    value={sessionId}
                    onChange={(e) => setSessionId(e.target.value)}
                  >
                    <option value="">Select a session</option>
                    {sessions
                      .filter((s) => s.status === "open")
                      .map((s) => (
                        <option key={s.id} value={s.id}>
                          {s.id.slice(0, 8)} · {s.current_url}
                        </option>
                      ))}
                  </select>
                </label>
                <label>
                  Authorised URL
                  <input value={url} onChange={(e) => setUrl(e.target.value)} />
                </label>
                <button
                  disabled={busy || !sessionId}
                  onClick={() =>
                    act(async () =>
                      setPage(
                        await request(
                          "/browser/sessions/" + sessionId + "/navigate",
                          token,
                          { url },
                        ),
                      ),
                    )
                  }
                >
                  Navigate
                </button>
                <hr />
                <label>
                  Permitted selector
                  <input
                    value={selector}
                    onChange={(e) => setSelector(e.target.value)}
                  />
                </label>
                <label>
                  Field value
                  <input
                    value={value}
                    onChange={(e) => setValue(e.target.value)}
                  />
                </label>
                <div className="button-row">
                  {["inspect", "click", "fill", "screenshot"].map((op) => (
                    <button
                      disabled={busy || !sessionId}
                      key={op}
                      onClick={() => act(() => browserAction(op))}
                    >
                      {op}
                    </button>
                  ))}
                </div>
                <button
                  disabled={busy || !sessionId}
                  onClick={() =>
                    act(async () => {
                      await request(
                        "/browser/sessions/" + sessionId,
                        token,
                        undefined,
                        "DELETE",
                      );
                      setSessionId("");
                      setPage(null);
                    })
                  }
                >
                  Close session
                </button>
              </section>
              <section className="panel">
                <div className="panel-top">
                  <h2>Page observation</h2>
                  <span className="tag subtle">CONTROLLED</span>
                </div>
                {page ? (
                  <>
                    {page.image ? (
                      <img
                        className="screenshot"
                        src={page.image}
                        alt="Managed browser screenshot"
                      />
                    ) : (
                      <>
                        <h3>{page.title}</h3>
                        <small>{page.url}</small>
                        <pre>{page.text}</pre>
                      </>
                    )}
                  </>
                ) : (
                  <p className="empty">
                    Open a session and navigate to the First Contact habitat.
                  </p>
                )}
                <p className="muted">
                  Actions require explicit page permissions. Destinations are
                  restricted by the backend origin allowlist.
                </p>
              </section>
            </div>
          )}
          {tab === "Runtime" && (
            <section className="panel">
              <div className="panel-top">
                <h2>Goals & commitments</h2>
                <span className="tag subtle">HUMAN ACCEPTANCE</span>
              </div>
              <form
                className="form-row"
                onSubmit={(e) => {
                  e.preventDefault();
                  act(async () => {
                    await request("/goals", token, { title: goalTitle });
                    setGoalTitle("");
                  });
                }}
              >
                <input
                  aria-label="Goal title"
                  value={goalTitle}
                  onChange={(e) => setGoalTitle(e.target.value)}
                  placeholder="Propose an objective"
                  required
                />
                <button disabled={busy}>Create goal</button>
              </form>
              {goals.map((g) => (
                <article className="memory" key={g.id}>
                  <span className="eyebrow">
                    {g.origin} · {g.status}
                  </span>
                  <h3>{g.title}</h3>
                  <p>{g.description}</p>
                  <div className="button-row">
                    {(g.status === "proposed"
                      ? ["accepted", "cancelled"]
                      : g.status === "accepted"
                        ? ["active", "cancelled"]
                        : g.status === "active"
                          ? ["completed", "cancelled"]
                          : []
                    ).map((status) => (
                      <button
                        disabled={busy}
                        key={status}
                        onClick={() =>
                          act(() =>
                            request("/goals/" + g.id + "/transition", token, {
                              status,
                            }),
                          )
                        }
                      >
                        {status}
                      </button>
                    ))}
                  </div>
                </article>
              ))}
            </section>
          )}
          {tab === "Cognition" && token && <CognitionPane token={token} />}
          {tab === "Living" && token && <LivingPane token={token} />}
          <footer>
            <span>
              <span className="dot" /> ALIVE / ADAPTIVE LIVING INTELLIGENCE
            </span>
            <span>Persistence is the beginning.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}
createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
