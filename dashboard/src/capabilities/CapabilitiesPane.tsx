import { useEffect, useMemo, useState } from "react";
import { read } from "../workflows/client";
import { text } from "../workflows/model";
import {
  assertCatalogue,
  assertDetail,
  parseCapabilityLink,
  schemaRows,
} from "./contracts";
import type {
  Catalogue,
  CapabilitySummary,
  Detail,
  Schema,
  Selection,
} from "./contracts";
import "../workflows/workflows.css";
import "./capabilities.css";

const EFFECT_LABEL = {
  none: "No side effects",
  read: "Read-only",
  model: "Model inference",
  writes: "Writes a result",
} as const;
const STATUS_LABEL = {
  available: "Available",
  deprecated: "Deprecated",
  unavailable: "Unavailable",
  incompatible: "Incompatible",
  disabled: "Disabled",
} as const;
const IMPLEMENTATION_LABEL = {
  installed: "Trusted implementation installed",
  missing: "Requires implementation",
  fingerprint_mismatch: "Implementation fingerprint mismatch",
} as const;

export function CapabilitiesPane({ token }: { token: string }) {
  // Remount all read state on credential changes; stale data cannot cross identities.
  return <CapabilityCatalogue key={token} token={token} />;
}

function Badges({ cap }: { cap: CapabilitySummary }) {
  // Deliberately no "safe" colouring: installed is not authorized, read is not harmless.
  return (
    <span className="cap-badges">
      <span className={"cap-badge cap-status-" + cap.status}>
        {STATUS_LABEL[cap.status]}
      </span>
      <span className={"cap-badge cap-effect-" + cap.effect_class}>
        {EFFECT_LABEL[cap.effect_class]}
      </span>
    </span>
  );
}

function CapabilityCatalogue({ token }: { token: string }) {
  const [catalogue, setCatalogue] = useState<Catalogue | null>(null),
    [error, setError] = useState(""),
    [refresh, setRefresh] = useState(0);
  const [query, setQuery] = useState(""),
    [category, setCategory] = useState(""),
    [status, setStatus] = useState("");
  const [selected, setSelected] = useState<Selection | null>(() =>
    parseCapabilityLink(window.location.hash),
  );
  const [detail, setDetail] = useState<Detail | null>(null),
    [detailError, setDetailError] = useState("");

  useEffect(() => {
    const onHash = () => {
      const next = parseCapabilityLink(window.location.hash);
      if (next) setSelected(next);
    };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  useEffect(() => {
    const c = new AbortController();
    let active = true;
    setError("");
    read<unknown>("/capabilities/catalog", token, c.signal)
      .then((body) => {
        if (active) setCatalogue(assertCatalogue(body));
      })
      .catch((e) => {
        if (active && e?.name !== "AbortError")
          setError(
            "Capability catalogue unavailable. Check authentication and connection.",
          );
      });
    return () => {
      active = false;
      c.abort();
    };
  }, [token, refresh]);

  useEffect(() => {
    setDetail(null);
    setDetailError("");
    if (!selected) return;
    const c = new AbortController();
    let active = true;
    read<unknown>(
      `/capabilities/catalog/${encodeURIComponent(selected.id)}/versions/${encodeURIComponent(selected.version)}`,
      token,
      c.signal,
    )
      .then((body) => {
        if (active) setDetail(assertDetail(body, selected));
      })
      .catch((e) => {
        if (active && e?.name !== "AbortError")
          setDetailError(
            "This capability version is not in the installed catalogue.",
          );
      });
    return () => {
      active = false;
      c.abort();
    };
  }, [selected?.id, selected?.version, token, refresh]);

  const categories = useMemo(
    () => [...new Set(catalogue?.capabilities.map((c) => c.category))].sort(),
    [catalogue],
  );
  const shown = (catalogue?.capabilities ?? []).filter(
    (c) =>
      (!category || c.category === category) &&
      (!status || c.status === status) &&
      `${c.id} ${c.name} ${c.description} ${c.tags.join(" ")}`
        .toLowerCase()
        .includes(query.toLowerCase()),
  );
  const versions = (catalogue?.capabilities ?? []).filter(
    (c) => c.id === selected?.id,
  );
  const stale =
    detail && catalogue && detail.catalog_sha256 !== catalogue.catalog_sha256;
  const mismatch =
    detail &&
    ((selected?.sha && selected.sha !== detail.capability.manifest_sha256) ||
      (selected?.impl &&
        selected.impl !== detail.capability.implementation.sha256));

  return (
    <div className="workflow-observatory cap-catalogue">
      <div className="wf-heading">
        <div>
          <h2>Capabilities</h2>
          <p>
            Installed and declared operations. Discovery is not execution
            authorization: every run needs an exact owner grant.
          </p>
        </div>
        <button onClick={() => setRefresh((n) => n + 1)}>Refresh</button>
      </div>
      {error && <p role="alert">{error}</p>}
      <div className="wf-controls">
        <label>
          Search capabilities
          <input value={query} onChange={(e) => setQuery(e.target.value)} />
        </label>
        <label>
          Category
          <select
            aria-label="Category"
            value={category}
            onChange={(e) => setCategory(e.target.value)}
          >
            <option value="">All categories</option>
            {categories.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
        </label>
        <label>
          Status
          <select
            aria-label="Status"
            value={status}
            onChange={(e) => setStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            {Object.entries(STATUS_LABEL).map(([k, v]) => (
              <option key={k} value={k}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="cap-layout">
        <nav aria-label="Capability list">
          {catalogue && !shown.length && <p>No capabilities match.</p>}
          <ul className="cap-list">
            {shown.map((c) => {
              const current =
                selected?.id === c.id && selected.version === c.version;
              return (
                <li key={c.id + "@" + c.version}>
                  <button
                    className={current ? "cap-item selected" : "cap-item"}
                    aria-current={current ? "true" : undefined}
                    onClick={() =>
                      setSelected({ id: c.id, version: c.version })
                    }
                  >
                    <strong>{c.name}</strong>
                    <small>
                      {c.id} · v{c.version}
                    </small>
                    <span className="cap-summary">{c.description}</span>
                    <Badges cap={c} />
                    <small>{IMPLEMENTATION_LABEL[c.implementation_state]}</small>
                  </button>
                </li>
              );
            })}
          </ul>
        </nav>
        <section className="wf-panel" aria-label="Capability detail">
          {!selected && <p>Select a capability to see its contract.</p>}
          {selected && detailError && <p role="alert">{detailError}</p>}
          {selected && !detail && !detailError && <p>Loading capability…</p>}
          {detail && (
            <DetailView
              detail={detail}
              versions={versions}
              onVersion={(v) =>
                setSelected({ id: detail.capability.id, version: v })
              }
            />
          )}
          {stale && (
            <p role="status">
              The catalogue changed after it was listed. Refresh before relying
              on this view.
            </p>
          )}
          {mismatch && (
            <p role="alert">
              The run that linked here retained a different manifest hash or
              implementation fingerprint. The installed version shown is not the
              capability that run used.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function DetailView({
  detail,
  versions,
  onVersion,
}: {
  detail: Detail;
  versions: CapabilitySummary[];
  onVersion: (v: string) => void;
}) {
  const cap = detail.capability;
  return (
    <>
      <h3>
        {cap.name} <small>v{cap.version}</small>
      </h3>
      <Badges cap={cap} />
      <p className="cap-description">{cap.description}</p>
      {cap.unavailable_reason && <p role="status">{cap.unavailable_reason}</p>}
      {versions.length > 1 && (
        <label>
          Capability version
          <select
            aria-label="Capability version"
            value={cap.version}
            onChange={(e) => onVersion(e.target.value)}
          >
            {versions.map((v) => (
              <option key={v.version} value={v.version}>
                v{v.version} · {STATUS_LABEL[v.status]}
              </option>
            ))}
          </select>
        </label>
      )}
      <dl className="wf-facts">
        <Fact name="Capability ID" value={cap.id} />
        <Fact name="Execution kind" value={cap.kind} />
        <Fact name="Side effects" value={cap.side_effects} />
        <Fact name="Manifest hash" value={cap.manifest_sha256} code />
        <Fact name="Configuration hash" value={cap.policy_sha256} code />
        <Fact name="Implementation" value={cap.implementation.id} />
        <Fact
          name="Implementation fingerprint"
          value={cap.implementation.sha256 ?? "Not available"}
          code
        />
        <Fact
          name="Implementation state"
          value={IMPLEMENTATION_LABEL[cap.implementation_state]}
        />
        <Fact name="Source types" value={cap.supported_source_types.join(", ") || "None"} />
        <Fact name="Tags" value={cap.tags.join(", ") || "None"} />
      </dl>
      <h4>Declared permissions</h4>
      <ul>
        {cap.permission_classes.length ? (
          cap.permission_classes.map((p) => <li key={p}>{p}</li>)
        ) : (
          <li>None. No ambient authority.</li>
        )}
      </ul>
      <p>{cap.authorization}</p>
      <h4>Limits (effective configuration)</h4>
      <dl className="wf-facts">
        {Object.entries(cap.effective_limits).map(([k, v]) => (
          <Fact
            key={k}
            name={k}
            value={
              cap.declared_limits[k] !== v
                ? `${text(v)} (manifest ${text(cap.declared_limits[k])})`
                : text(v)
            }
          />
        ))}
      </dl>
      <SchemaTable title="Inputs" schema={cap.inputs} />
      <SchemaTable title="Outputs" schema={cap.outputs} />
      {!!cap.examples.length && (
        <>
          <h4>Examples</h4>
          {cap.examples.map((e, i) => (
            <pre key={i}>{text(e)}</pre>
          ))}
        </>
      )}
      <h4>Workflows pinned to this exact version</h4>
      {detail.workflows.length ? (
        <ul>
          {detail.workflows.map((w) => (
            <li key={w.name + w.version}>
              {w.name} v{w.version} · {w.status} · stages {w.stages.join(", ")}
            </li>
          ))}
        </ul>
      ) : (
        <p>None registered with this version and manifest hash.</p>
      )}
    </>
  );
}

function Fact({
  name,
  value,
  code,
}: {
  name: string;
  value: string;
  code?: boolean;
}) {
  return (
    <div>
      <dt>{name}</dt>
      <dd>{code ? <code>{value}</code> : value}</dd>
    </div>
  );
}

function SchemaTable({ title, schema }: { title: string; schema: Schema }) {
  const rows = schemaRows(schema);
  return (
    <>
      <h4>{title}</h4>
      {rows.length ? (
        <table className="cap-schema">
          <caption className="sr-only">{title} contract</caption>
          <thead>
            <tr>
              <th scope="col">Field</th>
              <th scope="col">Type</th>
              <th scope="col">Required</th>
              <th scope="col">Bounds</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.path}>
                <td>{r.path}</td>
                <td>{r.type}</td>
                <td>{r.required ? "Yes" : "No"}</td>
                <td>{r.constraints}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No fields.</p>
      )}
    </>
  );
}
