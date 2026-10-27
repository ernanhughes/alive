export type BrowserObservation = {
  image?: string;
  title?: string;
  url?: string;
  text?: string;
  observation_id?: string;
  source_kind?: string;
  trust_level?: string;
  observed_at?: string;
  selector?: string;
  text_sha256?: string;
  text_chars?: number;
  permission_scope?: string;
  permission_origin?: string;
  permission_read_only?: boolean;
};

export function BrowserProvenance({
  observation,
}: {
  observation: BrowserObservation;
}) {
  if (!observation.source_kind) return null;
  return (
    <div className="browser-provenance" data-testid="browser-provenance">
      <span>
        <b>Source</b>
        {observation.source_kind}
      </span>
      <span>
        <b>Trust</b>
        {(observation.trust_level || "unknown").replace(/_/g, " ")}
      </span>
      <span>
        <b>Permission origin</b>
        {observation.permission_origin || "unknown"}
      </span>
      <span>
        <b>Read-only</b>
        {observation.permission_read_only ? "yes" : "unknown"}
      </span>
      <span>
        <b>Observed</b>
        {observation.observed_at
          ? new Date(observation.observed_at).toLocaleString("en-GB")
          : "unknown"}
      </span>
      <span>
        <b>Text SHA-256</b>
        <code title={observation.text_sha256}>
          {observation.text_sha256
            ? observation.text_sha256.slice(0, 16) + "…"
            : "unknown"}
        </code>
      </span>
      <span>
        <b>Characters</b>
        {observation.text_chars ?? "unknown"}
      </span>
      <span>
        <b>Selector</b>
        {observation.selector || "body"}
      </span>
    </div>
  );
}
