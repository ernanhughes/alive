/* @vitest-environment jsdom */
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { BrowserProvenance } from "./BrowserProvenance";

afterEach(cleanup);

describe("BrowserProvenance", () => {
  it("shows the persisted source, trust, permission and integrity fields", () => {
    const hash = "a".repeat(64);
    render(
      <BrowserProvenance
        observation={{
          source_kind: "managed_chrome_dom",
          trust_level: "observed_page_text_not_verified_fact",
          permission_origin: "http://127.0.0.1:8000",
          permission_read_only: true,
          observed_at: "2026-10-27T09:00:00+00:00",
          text_sha256: hash,
          text_chars: 42,
          selector: "body",
        }}
      />,
    );

    const block = screen.getByTestId("browser-provenance");
    expect(block.textContent).toContain("managed_chrome_dom");
    expect(block.textContent).toContain("observed page text not verified fact");
    expect(block.textContent).toContain("http://127.0.0.1:8000");
    expect(block.textContent).toContain("yes");
    expect(block.textContent).toContain("a".repeat(16) + "…");
    expect(block.textContent).toContain("42");
    expect(block.textContent).toContain("body");
  });

  it("does not invent provenance for a legacy observation", () => {
    render(<BrowserProvenance observation={{ text: "legacy text" }} />);
    expect(screen.queryByTestId("browser-provenance")).toBeNull();
  });
});
