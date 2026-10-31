import { text } from "./model";
// Bounded plain React text. No HTML, markdown execution or source URL navigation.
export function StructuredRecord({
  value,
  depth = 0,
}: {
  value: unknown;
  depth?: number;
}) {
  if (value === null || value === undefined) return <span>Not recorded</span>;
  if (depth >= 4) return <pre>{text(value)}</pre>;
  if (Array.isArray(value))
    return value.length ? (
      <>
        <ol>
          {value.slice(0, 50).map((v, i) => (
            <li key={i}>
              <StructuredRecord value={v} depth={depth + 1} />
            </li>
          ))}
        </ol>
        {value.length > 50 && <p>Display truncated after 50 entries.</p>}
      </>
    ) : (
      <span>None recorded</span>
    );
  if (typeof value === "object") {
    const entries = Object.entries(value);
    return entries.length ? (
      <>
        <dl className="wf-structured">
          {entries.slice(0, 40).map(([k, v]) => (
            <div key={k}>
              <dt>{k.replaceAll("_", " ")}</dt>
              <dd>
                <StructuredRecord value={v} depth={depth + 1} />
              </dd>
            </div>
          ))}
        </dl>
        {entries.length > 40 && <p>Display truncated after 40 fields.</p>}
      </>
    ) : (
      <span>No fields recorded</span>
    );
  }
  return <span>{text(value)}</span>;
}
