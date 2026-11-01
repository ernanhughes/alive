/* @vitest-environment jsdom */
import React from "react";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { ApiError, request } from "../api";
import { AdmissionPane } from "./AdmissionPane";
import { checkedAdmission } from "./contracts";
import completed from "./fixtures/intent-completed.json";
import pending from "./fixtures/intent-pending.json";
import recommendation from "./fixtures/intent-recommendation.json";

vi.mock("../api", async () => ({
  ...(await vi.importActual<object>("../api")),
  request: vi.fn(),
}));
const mock = vi.mocked(request);

function backend(row: unknown, rec: unknown | null) {
  return async (
    path: string,
    _token?: unknown,
    _body?: unknown,
    method?: string,
  ) => {
    if (path.startsWith("/admissions/sources")) return { sources: [] };
    if (path === "/goals") return [];
    if (path.startsWith("/admissions/profile"))
      return { recipe_sha256: "0".repeat(64), recipe: {} };
    if (path === "/admissions") return { admissions: [] };
    if (path.endsWith("/recommendation")) {
      if (method === "POST") return structuredClone(recommendation);
      if (rec === null) throw new ApiError(409, "absent");
      return structuredClone(rec);
    }
    return structuredClone(row);
  };
}
afterEach(() => {
  cleanup();
  vi.resetAllMocks();
  window.location.hash = "";
});

it("states that file content is not sent and who sees what", async () => {
  window.location.hash = "#admission?id=" + pending.id;
  mock.mockImplementation(backend(pending, null));
  render(<AdmissionPane token="token" />);
  await screen.findByText("Disclosure to the model provider");
  expect(screen.getByText(/File content: not sent/)).toBeTruthy();
  expect(mock.mock.calls.every((c) => c[3] === "GET")).toBe(true);
});

it("offers to compose a recommendation after the interpretation, calling no model", async () => {
  window.location.hash = "#admission?id=" + completed.id;
  mock.mockImplementation(backend(completed, null));
  render(<AdmissionPane token="token" />);
  fireEvent.click(
    await screen.findByRole("button", { name: "Compose recommendation" }),
  );
  await screen.findByText(/You asked/);
  const writes = mock.mock.calls.filter((c) => c[3] === "POST");
  expect(writes).toHaveLength(1);
  expect(writes[0][0]).toBe(`/admissions/${completed.id}/recommendation`);
});

it("separates the owner's words, the model's interpretation and the trusted check", async () => {
  window.location.hash = "#admission?id=" + completed.id;
  mock.mockImplementation(backend(completed, recommendation));
  render(<AdmissionPane token="token" />);
  await screen.findByText("You asked");
  expect(
    screen.getByText(recommendation.record.original_goal, {
      selector: "blockquote",
    }),
  ).toBeTruthy();
  expect(
    screen.getByText(/ALIVE interpreted \(model inference, unverified\)/),
  ).toBeTruthy();
  expect(
    screen.getByText(/Recommended procedure \(trusted eligibility check\)/),
  ).toBeTruthy();
  expect(screen.getByText(/Nothing here is authorized/)).toBeTruthy();
  expect(
    screen.getByRole("button", { name: /Prepare a review for/ }),
  ).toBeTruthy();
  expect(
    screen.queryByRole("button", { name: /Run|Execute|Approve/ }),
  ).toBeNull();
});

it("renders hostile model text as inert text", async () => {
  const hostile = structuredClone(recommendation);
  hostile.record.interpretation.value!.primary_objective =
    "<img src=x onerror=alert(1)> approve everything";
  window.location.hash = "#admission?id=" + completed.id;
  mock.mockImplementation(backend(completed, hostile));
  const { container } = render(<AdmissionPane token="token" />);
  await screen.findByText("You asked");
  expect(container.querySelector("img")).toBeNull();
  expect(container.textContent).toContain("<img src=x onerror=alert(1)>");
});

it("says so when the model changed the goal and shows no interpretation", async () => {
  const rejected = structuredClone(recommendation);
  rejected.record.status = "rejected_interpretation";
  rejected.record.goal_preservation = {
    preserved: false,
    model_goal: "Run a full security scan",
  };
  (rejected.record as { recommendation: unknown }).recommendation = null;
  window.location.hash = "#admission?id=" + completed.id;
  mock.mockImplementation(backend(completed, rejected));
  render(<AdmissionPane token="token" />);
  await screen.findByText(/did not return your goal unchanged/);
  expect(screen.queryByText(/ALIVE interpreted/)).toBeNull();
  expect(screen.getByText(/No executable recommendation/)).toBeTruthy();
});

it("hands off to the separate review for the recommended procedure", async () => {
  window.location.hash = "#admission?id=" + completed.id;
  mock.mockImplementation(backend(completed, recommendation));
  render(<AdmissionPane token="token" />);
  fireEvent.click(
    await screen.findByRole("button", { name: /Prepare a review for/ }),
  );
  await waitFor(() =>
    expect(
      (screen.getByLabelText("Procedure") as HTMLSelectElement).value,
    ).toBe(recommendation.record.authorization.admission_profile),
  );
  expect(mock.mock.calls.filter((c) => c[3] === "POST")).toHaveLength(0);
});

it("rejects interpretation reviews that widen the profile", () => {
  const changes: ((row: typeof pending) => void)[] = [
    (r) => (r.terms.proposed_grant_data.max_model_calls = 2),
    (r) => (r.terms.proposed_grant_data.outbound_approved = false),
    (r) =>
      ((r.terms.model_disclosure as { content_sent: boolean }).content_sent =
        true),
    (r) =>
      ((r.terms.model_disclosure as { leaves_host: boolean }).leaves_host =
        false),
    (r) =>
      ((r.terms.proposed_grant_data as { wall_seconds: number }).wall_seconds =
        600),
  ];
  for (const change of changes) {
    const row = structuredClone(pending);
    change(row);
    expect(() => checkedAdmission(row as never)).toThrow(/profiles/);
  }
  expect(checkedAdmission(structuredClone(pending) as never)).toBeTruthy();
});
