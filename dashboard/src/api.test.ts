import { describe, it, expect, vi, afterEach } from "vitest";
import { ApiError, isAuthenticationError, mergeEvents, request } from "./api";
import type { AliveEvent } from "./api";
const event = (id: string, seq: number) =>
  ({
    event_id: id,
    sequence_number: seq,
    event_type: "alive.heartbeat",
    source: "kernel",
    timestamp: "2026-10-26T20:00:00Z",
    correlation_id: "correlation",
    payload: {},
  }) as AliveEvent;
afterEach(() => vi.unstubAllGlobals());
describe("durable timeline", () => {
  it("orders and deduplicates replayed events", () => {
    expect(
      mergeEvents([event("a", 1)], [event("a", 1), event("b", 2)]).map(
        (e) => e.event_id,
      ),
    ).toEqual(["b", "a"]);
  });
  it("bounds retained events", () => {
    expect(
      mergeEvents(
        [],
        Array.from({ length: 400 }, (_, i) => event(String(i), i)),
      ),
    ).toHaveLength(300);
  });
});
describe("API client", () => {
  it.each([401, 403])(
    "retains HTTP %i even when the rejection body is unreadable",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            new Response("<html>unauthorized</html>", { status }),
          ),
      );
      const error = await request("/capabilities", "private-token").catch(
        (error) => error,
      );
      expect(error).toBeInstanceOf(ApiError);
      if (!(error instanceof ApiError)) throw error;
      expect(error.status).toBe(status);
      expect(isAuthenticationError(error)).toBe(true);
      expect(error.message).toBe("Invalid token — try again.");
      expect(String(error)).not.toContain("private-token");
    },
  );
  it.each([200, 502, 503])(
    "retains HTTP %i for malformed JSON without calling it an auth rejection",
    async (status) => {
      vi.stubGlobal(
        "fetch",
        vi
          .fn()
          .mockResolvedValue(
            new Response("<html>unavailable</html>", { status }),
          ),
      );
      const error = await request("/alive", "token").catch((error) => error);
      expect(error).toBeInstanceOf(ApiError);
      if (!(error instanceof ApiError)) throw error;
      expect(error.status).toBe(status);
      expect(isAuthenticationError(error)).toBe(false);
    },
  );
  it("reports network failures without exposing fetch errors or confusing their text with auth status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockRejectedValue(new Error("401 private-token")),
    );
    const error = await request("/alive", "private-token").catch(
      (error) => error,
    );
    expect(error).toBeInstanceOf(ApiError);
    if (!(error instanceof ApiError)) throw error;
    expect(error.status).toBeNull();
    expect(isAuthenticationError(error)).toBe(false);
    expect(error.message).toBe("Unable to connect to ALIVE.");
  });
  it("redacts credentials reflected in a backend error", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValue(
          new Response(
            JSON.stringify({ detail: "failed private-token private-token" }),
            { status: 500 },
          ),
        ),
    );
    await expect(request("/alive", "private-token")).rejects.toMatchObject({
      status: 500,
      message: "failed [redacted] [redacted]",
    });
  });
  it("passes cancellation to fetch and preserves AbortError", async () => {
    const controller = new AbortController();
    const error = new DOMException("Aborted", "AbortError");
    const fetch = vi.fn().mockRejectedValue(error);
    vi.stubGlobal("fetch", fetch);
    await expect(
      request("/capabilities", "token", undefined, "GET", controller.signal),
    ).rejects.toBe(error);
    expect(fetch.mock.calls[0][1].signal).toBe(controller.signal);
    expect(fetch.mock.calls[0][0]).not.toContain("token");
  });
  it("authenticates writes", async () => {
    const fetch = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({ status: "running" }),
    });
    vi.stubGlobal("fetch", fetch);
    await request("/alive/start", "token", {});
    expect(fetch.mock.calls[0][1].headers.Authorization).toBe("Bearer token");
    expect(fetch.mock.calls[0][1].method).toBe("POST");
  });
  it("surfaces backend failure states", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        json: async () => ({ error: { message: "Database unavailable" } }),
      }),
    );
    await expect(request("/alive", "token")).rejects.toThrow(
      "Database unavailable",
    );
  });
});
