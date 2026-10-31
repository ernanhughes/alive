/* @vitest-environment jsdom */
import { afterEach, describe, expect, it } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import recordings from "./fixtures/recorded-timelines.json";
import type { Timeline } from "./contracts";
import { replayRunOutcome, replayStates } from "./model";
import { RunTimeline } from "./RunTimeline";

afterEach(cleanup);
const timelines = Object.fromEntries(
  Object.entries(recordings.runs).map(([key, r]) => [
    key,
    r.timeline as Timeline,
  ]),
);
describe("replay of real persisted demo histories", () => {
  it.each([
    [
      "ambiguous",
      { prepare: "COMPLETED", analyze: "UNKNOWN (Pi run)" },
      "ended UNKNOWN",
    ],
    [
      "partial",
      {
        prepare: "COMPLETED",
        analyze: "COMPLETED",
        validate: "COMPLETED",
        record: "COMPLETED",
      },
      "ended FAILED",
    ],
    ["goal_cancel", {}, "ended FAILED"],
    [
      "research",
      {
        prepare: "COMPLETED",
        analyze: "COMPLETED",
        validate: "COMPLETED",
        record: "COMPLETED",
      },
      "completed",
    ],
  ] as const)(
    "shows the recorded final frame for %s",
    (label, states, outcome) => {
      const timeline = timelines[label];
      expect(timeline.has_more).toBe(false);
      expect(replayStates(timeline.events)).toEqual(states);
      expect(replayRunOutcome(timeline.events)).toBe(outcome);
    },
  );
  it.each(Object.keys(timelines))(
    "introduces no future state at any cursor in %s",
    (label) => {
      const events = timelines[label].events;
      for (let cursor = 0; cursor <= events.length; cursor++) {
        const visible = events.slice(0, cursor),
          states = replayStates(visible);
        for (const stage of ["prepare", "analyze", "validate", "record"]) {
          const own = visible.filter((e) => e.stage_id === stage);
          if (!own.length) expect(states).not.toHaveProperty(stage);
          if (states[stage] === "COMPLETED")
            expect(
              own.some((e) => e.event_type === "workflow.stage.result"),
            ).toBe(true);
          if (states[stage] === "UNKNOWN (Pi run)")
            expect(own.some((e) => e.event_type === "pi.run.unknown")).toBe(
              true,
            );
          if (states[stage] === "RUNNING")
            expect(
              own.some((e) => e.event_type === "workflow.stage.claimed"),
            ).toBe(true);
        }
        if (
          !visible.some((e) =>
            [
              "workflow.execution.ended",
              "workflow.execution.completed",
            ].includes(e.event_type),
          )
        )
          expect(replayRunOutcome(visible)).toBeNull();
        if (label === "ambiguous") {
          const unknown = events.findIndex(
            (e) => e.event_type === "pi.run.unknown",
          );
          if (cursor <= unknown)
            expect(states.analyze).not.toBe("UNKNOWN (Pi run)");
        }
      }
    },
  );
  it("shows the run outcome only after its recorded event is played", () => {
    const timeline = timelines.ambiguous,
      last = timeline.events.length;
    const props = {
      timeline,
      onCursor: () => {},
      onMore: () => {},
      onStage: () => {},
    };
    const view = render(<RunTimeline {...props} cursor={last - 1} />);
    expect(screen.queryByText(/Recorded run outcome/)).toBeNull();
    view.rerender(<RunTimeline {...props} cursor={last} />);
    expect(
      screen.getByText("Recorded run outcome: ended UNKNOWN"),
    ).toBeTruthy();
    view.rerender(<RunTimeline {...props} cursor={0} />);
    expect(screen.queryByText(/Recorded run outcome/)).toBeNull();
    view.rerender(<RunTimeline {...props} cursor={null} />);
    expect(screen.queryByText(/Recorded run outcome/)).toBeNull();
  });
});
