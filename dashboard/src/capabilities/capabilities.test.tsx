/* @vitest-environment jsdom */
import React from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { request } from "../api";
import { CapabilitiesPane } from "./CapabilitiesPane";
import {
  capabilityLink,
  parseCapabilityLink,
  schemaRows,
} from "./contracts";
import type { CapabilityDetail, CapabilitySummary } from "./contracts";

vi.mock("../api", () => ({ request: vi.fn() }));
const get = vi.mocked(request);
const H1 = "a".repeat(64),
  H2 = "b".repeat(64),
  CAT = "c".repeat(64);

function summary(over: Partial<CapabilitySummary> = {}): CapabilitySummary {
  return {
    id: "repository.inspect",
    version: "1.0.0",
    name: "Repository Inspection",
    description: "Inspect an approved capture.",
    category: "development",
    icon: "folder-search",
    tags: ["repository"],
    status: "available",
    workflow_available: true,
    unavailable_reason: null,
    deprecated: false,
    kind: "deterministic",
    side_effects: "read",
    effect_class: "read",
    permission_classes: ["Bounded read of an owner-approved repository capture"],
    manifest_sha256: H1,
    implementation_state: "installed",
    ...over,
  };
}
function detail(over: Partial<CapabilityDetail> = {}): CapabilityDetail {
  return {
    ...summary(),
    implementation: {
      id: "repository-inspector-v1",
      provider: "builtin",
      interface: "stage-context/v1",
      sha256: H2,
    },
    permissions: {},
    declared_limits: { max_files: 20, timeout_seconds: 30 },
    effective_limits: { max_files: 10, timeout_seconds: 30 },
    policy_sha256: H2,
    inputs: {
      type: "object",
      required: ["paths"],
      properties: {
        paths: { type: "array", maxItems: 20, items: { type: "string" } },
      },
    },
    outputs: {
      type: "object",
      required: ["files"],
      properties: { files: { type: "array", maxItems: 20 } },
    },
    supported_source_types: ["repository_snapshot"],
    examples: [],
    authorization: "Requires an exact owner grant; availability is not permission",
    ...over,
  };
}
const LIST = [
  summary(),
  summary({
    id: "memory.retrieve",
    name: "Memory Retrieval",
    category: "memory",
    status: "unavailable",
    workflow_available: false,
    implementation_state: "missing",
    unavailable_reason: "Trusted workflow implementation is not installed",
  }),
];

function serve(
  list: CapabilitySummary[] = LIST,
  details: Record<string, unknown> = {},
  catalog = CAT,
) {
  get.mockImplementation(async (path: string) => {
    if (path === "/capabilities/catalog")
      return { catalog_sha256: catalog, capabilities: list };
    if (path in details) return details[path];
    const m = /\/capabilities\/catalog\/(.+)\/versions\/(.+)$/.exec(path);
    if (m)
      return {
        catalog_sha256: catalog,
        capability: detail({ id: m[1], version: m[2] }),
        workflows: [],
      };
    throw new Error("unexpected " + path);
  });
}
beforeEach(() => {
  window.location.hash = "";
  get.mockReset();
});
afterEach(cleanup);

describe("capability catalogue", () => {
  it("lists capabilities with honest, non-reassuring status", async () => {
    serve();
    render(<CapabilitiesPane token="t" />);
    expect(await screen.findByText("Repository Inspection")).toBeTruthy();
    expect(screen.getByText("Requires implementation")).toBeTruthy();
    expect(screen.getAllByText("Unavailable").length).toBeGreaterThan(0);
    expect(document.body.textContent).not.toMatch(/\bsafe\b/i);
    expect(document.body.textContent).toMatch(/not execution authorization/);
  });

  it("filters by search text and status", async () => {
    serve();
    render(<CapabilitiesPane token="t" />);
    await screen.findByText("Repository Inspection");
    fireEvent.change(screen.getByLabelText("Search capabilities"), {
      target: { value: "memory" },
    });
    expect(screen.queryByText("Repository Inspection")).toBeNull();
    fireEvent.change(screen.getByLabelText("Search capabilities"), {
      target: { value: "" },
    });
    fireEvent.change(screen.getByLabelText("Status"), {
      target: { value: "available" },
    });
    expect(screen.queryByText("Memory Retrieval")).toBeNull();
    expect(screen.getByText("Repository Inspection")).toBeTruthy();
  });

  it("renders hostile and very long strings as inert text", async () => {
    const hostile = summary({
      id: "evil.thing",
      name: "<img src=x onerror=alert(1)>",
      description: "x".repeat(1000),
      tags: ["<script>"],
    });
    serve([hostile]);
    const { container } = render(<CapabilitiesPane token="t" />);
    expect(await screen.findByText("<img src=x onerror=alert(1)>")).toBeTruthy();
    expect(container.querySelector("img, script")).toBeNull();
  });

  it("shows contract, limits and the unconfigured-authorization notice on selection", async () => {
    serve();
    render(<CapabilitiesPane token="t" />);
    fireEvent.click(await screen.findByText("Repository Inspection"));
    expect(await screen.findByText("Declared permissions")).toBeTruthy();
    expect(screen.getByText(/Requires an exact owner grant/)).toBeTruthy();
    expect(screen.getByText("paths")).toBeTruthy();
    expect(screen.getByText("10 (manifest 20)")).toBeTruthy(); // configuration narrowed it
    expect(screen.getByText(/None registered with this version/)).toBeTruthy();
  });

  it("switches versions by identity, never by name", async () => {
    const v2 = summary({ version: "2.0.0", manifest_sha256: H2 });
    serve([summary(), v2]);
    render(<CapabilitiesPane token="t" />);
    fireEvent.click((await screen.findAllByText("Repository Inspection"))[0]);
    const select = await screen.findByLabelText("Capability version");
    fireEvent.change(select, { target: { value: "2.0.0" } });
    await waitFor(() =>
      expect(get.mock.calls.map((c) => c[0])).toContain(
        "/capabilities/catalog/repository.inspect/versions/2.0.0",
      ),
    );
  });

  it("ignores malformed deep links and does not guess an identity", async () => {
    for (const hash of [
      "#capabilities?id=../etc&version=1.0.0",
      "#capabilities?id=repository.inspect&version=1.0.0&extra=1",
      "#capabilities?id=repository.inspect&id=x.y&version=1.0.0",
      "#capabilities?id=repository.inspect&version=latest",
    ]) {
      cleanup();
      window.location.hash = hash;
      serve();
      render(<CapabilitiesPane token="t" />);
      expect(await screen.findByText(/Select a capability/)).toBeTruthy();
    }
    expect(
      get.mock.calls.some((c) => String(c[0]).includes("/versions/")),
    ).toBe(false);
  });

  it("warns when a run's retained hash is not the installed manifest", async () => {
    window.location.hash = capabilityLink({
      id: "repository.inspect",
      version: "1.0.0",
      sha: H2, // the run retained H2; the installed manifest is H1
    });
    serve();
    render(<CapabilitiesPane token="t" />);
    expect(
      await screen.findByText(/retained a different manifest hash or implementation/),
    ).toBeTruthy();
  });

  it("warns when only the implementation fingerprint differs from the run's", async () => {
    window.location.hash = capabilityLink({
      id: "repository.inspect",
      version: "1.0.0",
      sha: H1, // the manifest still matches the installed one
      impl: "e".repeat(64), // but the run retained a different implementation fingerprint
    });
    serve();
    render(<CapabilitiesPane token="t" />);
    expect(
      await screen.findByText(/retained a different manifest hash or implementation/),
    ).toBeTruthy();
  });

  it("does not warn when the retained manifest and implementation both match", async () => {
    window.location.hash = capabilityLink({
      id: "repository.inspect",
      version: "1.0.0",
      sha: H1,
      impl: H2, // detail() installs implementation sha H2
    });
    serve();
    render(<CapabilitiesPane token="t" />);
    await screen.findByText("Declared permissions");
    expect(screen.queryByText(/retained a different manifest hash/)).toBeNull();
  });

  it("flags a catalogue that changed after the list was loaded", async () => {
    window.location.hash = capabilityLink({
      id: "repository.inspect",
      version: "1.0.0",
    });
    serve(LIST, {
      "/capabilities/catalog/repository.inspect/versions/1.0.0": {
        catalog_sha256: "d".repeat(64),
        capability: detail(),
        workflows: [],
      },
    });
    render(<CapabilitiesPane token="t" />);
    expect(await screen.findByText(/catalogue changed after it was listed/)).toBeTruthy();
  });

  it("refuses a detail response for a different identity", async () => {
    window.location.hash = capabilityLink({
      id: "repository.inspect",
      version: "1.0.0",
    });
    serve(LIST, {
      "/capabilities/catalog/repository.inspect/versions/1.0.0": {
        catalog_sha256: CAT,
        capability: detail({ id: "other.thing" }),
        workflows: [],
      },
    });
    render(<CapabilitiesPane token="t" />);
    expect(await screen.findByText(/not in the installed catalogue/)).toBeTruthy();
    expect(screen.queryByText("Declared permissions")).toBeNull();
  });

  it("rejects an invalid list response instead of rendering it", async () => {
    serve([summary({ status: "trusted" as never })]);
    render(<CapabilitiesPane token="t" />);
    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(screen.queryByText("Repository Inspection")).toBeNull();
  });

  it("exposes accessible list navigation and detail regions", async () => {
    serve();
    render(<CapabilitiesPane token="t" />);
    await screen.findByText("Repository Inspection");
    expect(screen.getByRole("navigation", { name: "Capability list" })).toBeTruthy();
    expect(screen.getByRole("region", { name: "Capability detail" })).toBeTruthy();
    fireEvent.click(screen.getByText("Repository Inspection"));
    await screen.findByText("Declared permissions");
    expect(
      screen.getByText("Repository Inspection", { selector: "strong" }).closest("button")
        ?.getAttribute("aria-current"),
    ).toBe("true");
  });
});

describe("capability contracts", () => {
  it("round-trips only well-formed links", () => {
    const link = capabilityLink({ id: "a.b", version: "1.2.3", sha: H1 });
    expect(parseCapabilityLink(link)).toEqual({
      id: "a.b",
      version: "1.2.3",
      sha: H1,
      impl: undefined,
    });
    const both = capabilityLink({ id: "a.b", version: "1.2.3", sha: H1, impl: H2 });
    expect(parseCapabilityLink(both)?.impl).toBe(H2);
    expect(parseCapabilityLink(both + "&impl=" + H1)).toBeNull(); // duplicate keys refused
    expect(parseCapabilityLink("#capabilities?id=a.b&version=1.2.3&impl=zz")).toBeNull();
    expect(parseCapabilityLink("#capabilities?id=a.b")).toBeNull();
    expect(() => capabilityLink({ id: "A..b", version: "1.0.0" })).toThrow();
  });
  it("flattens nested schemas with bounds", () => {
    const rows = schemaRows({
      type: "object",
      required: ["files"],
      properties: {
        files: {
          type: "array",
          maxItems: 3,
          items: { type: "object", properties: { path: { type: "string", maxLength: 9 } } },
        },
      },
    });
    expect(rows.map((r) => r.path)).toEqual(["files", "files[].path"]);
    expect(rows[0].required).toBe(true);
    expect(rows[1].constraints).toBe("maxLength=9");
  });
});
