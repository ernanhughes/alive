import { describe, expect, it } from "vitest";
import type { RecordedEvent } from "./contracts";
import { replayStates } from "./model";

const event = (
  sequence: number,
  event_type: string,
  stage_id: string | null = null,
  status: string | null = null,
): RecordedEvent => ({
  sequence,
  event_type,
  stage_id,
  status,
  occurred_at: "2026-10-31T02:07:19Z",
  run_id: "recorded-run",
  attempt_id: stage_id ? "attempt-" + stage_id : null,
  pi_run_id: null,
  output_ref: null,
});
const endedUnrecorded = "Ended — outcome not recorded";
const prefix = () => [
  event(21, "workflow.stage.claimed", "prepare"),
  event(22, "workflow.stage.result", "prepare"),
  event(23, "workflow.stage.claimed", "analyze"),
];

describe("historical terminal execution projection", () => {
  it("does not leave Analyze running after the recorded UNKNOWN execution end", () => {
    const events = [
      ...prefix(),
      event(101, "pi.run.unknown", "analyze"),
      event(102, "workflow.execution.ended", null, "UNKNOWN"),
    ];
    expect(replayStates(events.slice(0, -1))).toEqual({
      prepare: "COMPLETED",
      analyze: "RUNNING",
    });
    expect(replayStates(events)).toEqual({
      prepare: "COMPLETED",
      analyze: endedUnrecorded,
    });
    expect(events.map((e) => e.sequence)).toEqual([21, 22, 23, 101, 102]);
    expect(
      events.filter((e) => e.event_type === "workflow.stage.result"),
    ).toHaveLength(1);
  });
  it.each(["COMPLETED", "FAILED", "CANCELLED", "UNKNOWN"])(
    "reports an unrecorded stage outcome when execution ends %s",
    (status) => {
      expect(
        replayStates([
          ...prefix(),
          event(102, "workflow.execution.ended", null, status),
        ]),
      ).toEqual({ prepare: "COMPLETED", analyze: endedUnrecorded });
    },
  );
  it.each([
    "workflow.execution.completed",
    "workflow.run.completed",
    "workflow.run.failed",
    "workflow.run.cancelled",
    "workflow.run.unknown",
  ])(
    "recognizes %s without borrowing a final snapshot or requiring a status payload",
    (type) => {
      expect(replayStates([...prefix(), event(102, type)])).toEqual({
        prepare: "COMPLETED",
        analyze: endedUnrecorded,
      });
      expect(replayStates([event(102, type)])).toEqual({});
    },
  );
  it("preserves independently recorded stage results at a completed execution", () => {
    expect(
      replayStates([
        ...prefix(),
        event(101, "workflow.stage.result", "analyze"),
        event(102, "workflow.execution.completed"),
      ]),
    ).toEqual({ prepare: "COMPLETED", analyze: "COMPLETED" });
  });
  it("does not invent terminal workflow stage states from Pi or unrelated status fields", () => {
    for (const type of [
      "pi.run.unknown",
      "pi.run.failed",
      "pi.run.cancelled",
      "pi.run.settled",
      "workflow.execution.claimed",
      "workflow.run.running",
    ])
      expect(
        replayStates([...prefix(), event(101, type, "analyze", "FAILED")]),
      ).toEqual({ prepare: "COMPLETED", analyze: "RUNNING" });
  });
  it("leaves stages with no recorded claim absent at every replay position", () => {
    const events = [
      ...prefix(),
      event(102, "workflow.execution.ended", null, "CANCELLED"),
    ];
    for (let i = 0; i <= events.length; i++)
      expect(replayStates(events.slice(0, i))).not.toHaveProperty("validate");
  });
});
