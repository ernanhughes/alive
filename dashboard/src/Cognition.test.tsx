/* @vitest-environment jsdom */
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { request } from "./api";
import { CognitionPane } from "./Cognition";

vi.mock("./api", () => ({ base: "http://127.0.0.1:8000", request: vi.fn() }));

const mind = {
  control: {
    mode: "paused",
    provider: "meta",
    configuration: {},
    spent: {},
    reserved: {},
  },
  active: null,
  active_objective: null,
  current_uncertainty: [],
  active_role: null,
  embedding: { available: true, model: "test-model", revision: "test" },
  roles: [],
};

const mocked = vi.mocked(request);

beforeEach(() => {
  mocked.mockImplementation(async (path: string) => {
    if (path === "/cognition") return mind as never;
    if (
      path === "/cognition/observations" ||
      path === "/cognition/investigations" ||
      path === "/experiences" ||
      path === "/cognition/actions"
    ) {
      return [] as never;
    }
    if (path === "/learning") {
      return { available: false, reason: "not available", simulation_only: true } as never;
    }
    if (path === "/learning/demonstration") {
      return { available: false } as never;
    }
    throw new Error("unexpected " + path);
  });
});

afterEach(cleanup);

describe("CognitionPane", () => {
  it("shows the persisted provider instead of always defaulting to mock", async () => {
    render(<CognitionPane token="t" experimentsEnabled={false} />);
    const select = (await screen.findByLabelText("Cognitive provider")) as HTMLSelectElement;
    await waitFor(() => expect(select.value).toBe("meta"));
  });
});
