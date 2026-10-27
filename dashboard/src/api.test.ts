import { describe, it, expect, vi, afterEach } from "vitest";
import { mergeEvents, request } from "./api";
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
  it("authenticates writes", async () => {
    const fetch = vi
      .fn()
      .mockResolvedValue({
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
      vi
        .fn()
        .mockResolvedValue({
          ok: false,
          json: async () => ({ error: { message: "Database unavailable" } }),
        }),
    );
    await expect(request("/alive", "token")).rejects.toThrow(
      "Database unavailable",
    );
  });
});
