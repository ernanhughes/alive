/* @vitest-environment jsdom */
import { StrictMode } from "react";
import {
  act,
  cleanup,
  fireEvent,
  render,
  renderHook,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, isAuthenticationError, request } from "./api";
import { useDashboardAuth } from "./useDashboardAuth";
import { App } from "./main";

const capabilities = {
  database: { available: true, backend: "sqlite", error: null },
  pgvector: { storage: false, search: false, reason: "disabled" },
  zeromq: { available: false, received: 0 },
  pi: { configured: false },
  providers: { meta: { configured: false } },
};
const response = (status = 200, body: unknown = capabilities) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>((r) => {
    resolve = r;
  });
  return { promise, resolve };
}
const fetchMock = vi.fn<typeof fetch>();
class Socket {
  static instances: Socket[] = [];
  onopen: (() => void) | null = null;
  onclose: (() => void) | null = null;
  onmessage: ((event: { data: string }) => void) | null = null;
  onerror: (() => void) | null = null;
  send = vi.fn();
  close = vi.fn();
  constructor(public url: string) {
    Socket.instances.push(this);
  }
}
beforeEach(() => {
  sessionStorage.clear();
  fetchMock.mockReset();
  Socket.instances = [];
  vi.stubGlobal("fetch", fetchMock);
  vi.stubGlobal("WebSocket", Socket);
});
afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  sessionStorage.clear();
});
function serveDashboard() {
  fetchMock.mockImplementation(async (url) => {
    const path = String(url);
    if (path.endsWith("/capabilities")) return response();
    if (path.endsWith("/alive"))
      return response(200, {
        identity: { id: "local", name: "ALIVE", lifecycle_state: "stopped" },
        runtime: { heartbeat_at: null, state_version: 0, active_goals: [] },
        drives: {},
      });
    if (path.endsWith("/agents")) return response(200, { runs: [] });
    return response(200, []);
  });
}

describe("recoverable authentication", () => {
  it.each([401, 403])(
    "rejects %i without persisting a newly entered credential",
    async (status) => {
      fetchMock.mockResolvedValue(response(status));
      const { result } = renderHook(useDashboardAuth);
      act(() => result.current.edit("wrong"));
      await act(() => result.current.validate("wrong"));
      expect(result.current.token).toBe("");
      expect(result.current.draft).toBe("wrong");
      expect(result.current.status).toBe("rejected");
      expect(result.current.message).toContain("Invalid token");
      expect(sessionStorage.getItem("alive-token")).toBeNull();
    },
  );
  it("only saves and accepts a credential after successful validation", async () => {
    const pending = deferred<Response>();
    fetchMock.mockReturnValue(pending.promise);
    const { result } = renderHook(useDashboardAuth);
    let attempt!: Promise<void>;
    act(() => {
      attempt = result.current.validate("valid");
    });
    expect(result.current.token).toBe("");
    expect(result.current.status).toBe("checking");
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    await act(async () => {
      pending.resolve(response());
      await attempt;
    });
    expect(result.current.token).toBe("valid");
    expect(sessionStorage.getItem("alive-token")).toBe("valid");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/capabilities");
    expect(fetchMock.mock.calls[0][1]?.headers).toMatchObject({
      Authorization: "Bearer valid",
    });
  });
  it("removes a previously stored invalid credential on reload and permits another attempt", async () => {
    sessionStorage.setItem("alive-token", "old");
    fetchMock.mockResolvedValue(response(401));
    const { result } = renderHook(useDashboardAuth);
    await waitFor(() => expect(result.current.status).toBe("rejected"));
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    expect(result.current.draft).toBe("old");
    fetchMock.mockResolvedValue(response());
    act(() => result.current.edit("correct"));
    await act(() => result.current.validate("correct"));
    expect(result.current.token).toBe("correct");
  });
  it.each(["network", "server", "malformed"])(
    "keeps a validated session during a %s failure",
    async (failure) => {
      fetchMock.mockResolvedValue(response());
      const { result } = renderHook(useDashboardAuth);
      act(() => result.current.edit("valid"));
      await act(() => result.current.validate("valid"));
      if (failure === "network")
        fetchMock.mockRejectedValue(new TypeError("offline"));
      else if (failure === "server")
        fetchMock.mockResolvedValue(response(503, { detail: "unavailable" }));
      else
        fetchMock.mockResolvedValue(
          new Response("<html>bad gateway</html>", { status: 502 }),
        );
      await act(() => result.current.retry());
      expect(result.current.token).toBe("valid");
      expect(sessionStorage.getItem("alive-token")).toBe("valid");
      expect(result.current.status).toBe("unavailable");
      expect(result.current.message).not.toContain("Invalid token");
      fetchMock.mockResolvedValue(response());
      await act(() => result.current.retry());
      expect(result.current.status).toBe("authenticated");
    },
  );
  it.each([new ApiError(null, "offline"), new ApiError(503, "down")])(
    "does not save new credentials during an outage",
    async (error) => {
      fetchMock.mockRejectedValue(error);
      const { result } = renderHook(useDashboardAuth);
      await act(() => result.current.validate("unverified"));
      expect(result.current.status).toBe("unavailable");
      expect(result.current.token).toBe("");
      expect(sessionStorage.getItem("alive-token")).toBeNull();
    },
  );
  it("does not authenticate a malformed success document", async () => {
    fetchMock.mockResolvedValue(response(200, {}));
    const { result } = renderHook(useDashboardAuth);
    await act(() => result.current.validate("unverified"));
    expect(result.current.status).toBe("unavailable");
    expect(result.current.token).toBe("");
    expect(sessionStorage.getItem("alive-token")).toBeNull();
  });
  it.each([200, 401])(
    "ignores a stale %i validation after credentials change, even if fetch ignores abort",
    async (status) => {
      const old = deferred<Response>();
      fetchMock.mockReturnValueOnce(old.promise).mockResolvedValue(response());
      const { result } = renderHook(useDashboardAuth);
      let attempt!: Promise<void>;
      act(() => {
        result.current.edit("old");
        attempt = result.current.validate("old");
      });
      act(() => result.current.change());
      act(() => result.current.edit("new"));
      await act(() => result.current.validate("new"));
      await act(async () => {
        old.resolve(response(status));
        await attempt;
      });
      expect(result.current.token).toBe("new");
      expect(result.current.status).toBe("authenticated");
      expect(sessionStorage.getItem("alive-token")).toBe("new");
    },
  );
  it("discards a pending validation when its form is edited", async () => {
    const pending = deferred<Response>();
    fetchMock.mockReturnValue(pending.promise);
    const { result } = renderHook(useDashboardAuth);
    let attempt!: Promise<void>;
    act(() => {
      attempt = result.current.validate("old");
    });
    act(() => result.current.edit("replacement"));
    await act(async () => {
      pending.resolve(response());
      await attempt;
    });
    expect(result.current.token).toBe("");
    expect(result.current.draft).toBe("replacement");
    expect(sessionStorage.getItem("alive-token")).toBeNull();
  });
});

describe("dashboard authentication lifecycle", () => {
  it("returns to the editable form when polling discovers an expired token", async () => {
    vi.useFakeTimers();
    sessionStorage.setItem("alive-token", "saved");
    serveDashboard();
    await act(async () => {
      render(<App />);
    });
    expect(screen.getByText("Backend connected")).toBeTruthy();
    fetchMock.mockResolvedValue(response(401));
    await act(() => vi.advanceTimersByTimeAsync(5000));
    expect(screen.getByLabelText("Local API token")).toBeTruthy();
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    expect(Socket.instances[0].close).toHaveBeenCalled();
    const count = fetchMock.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(fetchMock).toHaveBeenCalledTimes(count);
  });
  it("gates polling and sockets; retains an editable wrong-token form and permits correction", async () => {
    fetchMock.mockResolvedValue(response(401));
    render(
      <StrictMode>
        <App />
      </StrictMode>,
    );
    expect(fetchMock).not.toHaveBeenCalled();
    expect(Socket.instances).toHaveLength(0);
    const input = screen.getByLabelText("Local API token");
    fireEvent.change(input, { target: { value: "wrong" } });
    fireEvent.click(screen.getByRole("button", { name: /^Connect/ }));
    await screen.findByText("Invalid token — try again.");
    expect(screen.getByLabelText("Local API token")).toBe(input);
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    expect(Socket.instances).toHaveLength(0);
    serveDashboard();
    fireEvent.change(input, { target: { value: "correct" } });
    fireEvent.click(screen.getByRole("button", { name: /^Connect/ }));
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    expect(screen.queryByLabelText("Local API token")).toBeNull();
    act(() => Socket.instances[0].onopen?.());
    expect(Socket.instances[0].send).toHaveBeenCalledWith(
      JSON.stringify({ token: "correct", after: 0 }),
    );
    expect(Socket.instances[0].url).not.toContain("correct");
    expect(location.href).not.toContain("correct");
    fireEvent.click(screen.getByRole("button", { name: "Change token" }));
    expect(Socket.instances[0].close).toHaveBeenCalled();
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    expect(screen.getByLabelText("Local API token")).toBeTruthy();
  });
  it("restores saved tokens only after validation and invalidates even a rejection caught by a child pane", async () => {
    sessionStorage.setItem("alive-token", "saved");
    const pending = deferred<Response>();
    fetchMock.mockReturnValueOnce(pending.promise);
    render(<App />);
    expect(Socket.instances).toHaveLength(0);
    expect(fetchMock).toHaveBeenCalledTimes(1);
    serveDashboard();
    await act(async () => {
      pending.resolve(response());
    });
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    fetchMock.mockResolvedValue(response(403));
    await act(async () => {
      await request("/workflows", "saved").catch(() => undefined);
    });
    expect(screen.getByLabelText("Local API token")).toBeTruthy();
    expect(sessionStorage.getItem("alive-token")).toBeNull();
    expect(Socket.instances[0].close).toHaveBeenCalled();
    vi.useFakeTimers();
    const count = fetchMock.mock.calls.length;
    await act(() => vi.advanceTimersByTimeAsync(10000));
    expect(fetchMock).toHaveBeenCalledTimes(count);
  });
  it("retains recovery actions and authentication on a socket disconnect with an HTTP outage", async () => {
    sessionStorage.setItem("alive-token", "saved");
    serveDashboard();
    render(<App />);
    await waitFor(() => expect(Socket.instances).toHaveLength(1));
    fetchMock.mockResolvedValue(response(503));
    await act(async () => {
      Socket.instances[0].onclose?.();
    });
    expect(screen.getByRole("button", { name: "Change token" })).toBeTruthy();
    expect(
      screen.getByRole("button", { name: "Retry authentication" }),
    ).toBeTruthy();
    expect(sessionStorage.getItem("alive-token")).toBe("saved");
    expect(screen.queryByLabelText("Local API token")).toBeNull();
    expect(screen.getByRole("alert").textContent).not.toContain(
      "Invalid token",
    );
    fetchMock.mockResolvedValue(response(401));
    fireEvent.click(
      screen.getByRole("button", { name: "Retry authentication" }),
    );
    await screen.findByText("Invalid token — try again.");
    expect(sessionStorage.getItem("alive-token")).toBeNull();
  });
});
