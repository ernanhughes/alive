import type { RecordedEvent, Timeline } from "./contracts";
import { timestamp } from "./model";
export function RunTimeline({
  timeline,
  cursor,
  onCursor,
  onMore,
  onStage,
}: {
  timeline: Timeline;
  cursor: number | null;
  onCursor: (n: number | null) => void;
  onMore: () => void;
  onStage: (id: string) => void;
}) {
  const events =
    cursor === null ? timeline.events : timeline.events.slice(0, cursor);
  return (
    <section className="wf-panel" aria-label="Recorded events">
      <h3>
        {cursor === null ? "Recorded events" : "Recorded execution replay"}
      </h3>
      <p>{timeline.history_note}</p>
      {cursor === null ? (
        <button onClick={() => onCursor(0)}>Replay recorded events</button>
      ) : (
        <>
          <label>
            Event position{" "}
            <input
              aria-label="Event position"
              type="range"
              min="0"
              max={timeline.events.length}
              value={cursor}
              onChange={(e) => onCursor(+e.target.value)}
            />
          </label>
          <span>
            {cursor} / {timeline.events.length}
          </span>
          <button disabled={cursor === 0} onClick={() => onCursor(cursor - 1)}>
            Previous event
          </button>
          <button
            disabled={cursor === timeline.events.length}
            onClick={() => onCursor(cursor + 1)}
          >
            Next event
          </button>
          <button onClick={() => onCursor(null)}>
            Return to current snapshot
          </button>
          <p>
            Read-only local replay. No operation is re-executed. Snapshot-only
            transitions are unavailable.
          </p>
        </>
      )}
      <ol className="wf-timeline">
        {events.map((e: RecordedEvent) => (
          <li key={e.sequence}>
            <time>{timestamp(e.occurred_at)}</time>
            <strong>
              #{e.sequence} {e.event_type}
            </strong>
            {e.stage_id && (
              <button onClick={() => onStage(e.stage_id!)}>{e.stage_id}</button>
            )}
            {e.status && <span>{e.status}</span>}
            {e.output_ref && <small>{e.output_ref}</small>}
          </li>
        ))}
      </ol>
      {!events.length && <p>No recorded events at this position.</p>}
      {timeline.has_more && (
        <button onClick={onMore}>Load next event page</button>
      )}
    </section>
  );
}
