// Mirrors alive/capabilities/api.py. Everything is rendered as text; nothing here is trusted markup.
export const EFFECTS = ["none", "read", "model", "writes"] as const;
export const STATUSES = [
  "available",
  "deprecated",
  "unavailable",
  "incompatible",
  "disabled",
] as const;
export type Effect = (typeof EFFECTS)[number];
export type Status = (typeof STATUSES)[number];

export interface CapabilitySummary {
  id: string;
  version: string;
  name: string;
  description: string;
  category: string;
  icon: string;
  tags: string[];
  status: Status;
  workflow_available: boolean;
  unavailable_reason: string | null;
  deprecated: boolean;
  kind: string;
  side_effects: string;
  effect_class: Effect;
  permission_classes: string[];
  manifest_sha256: string;
  implementation_state: "installed" | "missing" | "fingerprint_mismatch";
}
export interface Schema {
  type: string;
  properties?: Record<string, Schema>;
  required?: string[];
  items?: Schema;
  [key: string]: unknown;
}
export interface CapabilityDetail extends CapabilitySummary {
  implementation: {
    id: string;
    provider: string;
    interface: string;
    sha256: string | null;
  };
  permissions: Record<string, unknown>;
  declared_limits: Record<string, unknown>;
  effective_limits: Record<string, unknown>;
  policy_sha256: string;
  inputs: Schema;
  outputs: Schema;
  supported_source_types: string[];
  examples: Record<string, unknown>[];
  authorization: string;
}
export interface Catalogue {
  catalog_sha256: string;
  capabilities: CapabilitySummary[];
}
export interface Detail {
  catalog_sha256: string;
  capability: CapabilityDetail;
  workflows: {
    name: string;
    version: number;
    status: string;
    stages: string[];
  }[];
}
export interface Selection {
  id: string;
  version: string;
  sha?: string; // the manifest hash the linking run retained
  impl?: string; // the implementation fingerprint the linking run retained
}

const ID = /^[a-z][a-z0-9_-]*(\.[a-z][a-z0-9_-]*)+$/,
  VERSION = /^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$/,
  SHA = /^[0-9a-f]{64}$/;

function fail(): never {
  throw new Error("Invalid capability response");
}
function str(value: unknown, max: number): string {
  if (typeof value !== "string" || value.length > max) fail();
  return value;
}
export function assertSummary(value: unknown): CapabilitySummary {
  const v = value as CapabilitySummary;
  if (!v || typeof v !== "object") fail();
  str(v.name, 100);
  str(v.description, 1000);
  str(v.category, 32);
  if (
    !ID.test(str(v.id, 64)) ||
    !VERSION.test(str(v.version, 32)) ||
    !SHA.test(str(v.manifest_sha256, 64)) ||
    !STATUSES.includes(v.status) ||
    !EFFECTS.includes(v.effect_class) ||
    !Array.isArray(v.tags) ||
    v.tags.length > 12 ||
    !Array.isArray(v.permission_classes) ||
    v.permission_classes.length > 8 ||
    typeof v.workflow_available !== "boolean"
  )
    fail();
  v.tags.forEach((t) => str(t, 32));
  v.permission_classes.forEach((t) => str(t, 200));
  return v;
}
export function assertCatalogue(value: unknown): Catalogue {
  const v = value as Catalogue;
  if (
    !v ||
    !SHA.test(str(v.catalog_sha256, 64)) ||
    !Array.isArray(v.capabilities) ||
    v.capabilities.length > 256
  )
    fail();
  v.capabilities.forEach(assertSummary);
  return v;
}
export function assertDetail(value: unknown, selected: Selection): Detail {
  const v = value as Detail;
  if (!v || !SHA.test(str(v.catalog_sha256, 64)) || !Array.isArray(v.workflows))
    fail();
  assertSummary(v.capability);
  // A response for some other identity must never be displayed under this selection.
  if (v.capability.id !== selected.id || v.capability.version !== selected.version)
    fail();
  if (v.workflows.length > 50) fail();
  return v;
}

// Deep link: #capabilities?id=…&version=…[&sha=…]. Anything else is ignored, not guessed at.
export function parseCapabilityLink(hash: string): Selection | null {
  if (!hash.startsWith("#capabilities?") || hash.length > 200) return null;
  const p = new URLSearchParams(hash.slice(14));
  const keys = [...p.keys()];
  if (
    keys.some((k) => !["id", "version", "sha", "impl"].includes(k)) ||
    keys.some((k) => p.getAll(k).length !== 1)
  )
    return null;
  const id = p.get("id") || "",
    version = p.get("version") || "",
    sha = p.get("sha") || undefined,
    impl = p.get("impl") || undefined;
  if (
    !ID.test(id) ||
    !VERSION.test(version) ||
    (sha && !SHA.test(sha)) ||
    (impl && !SHA.test(impl))
  )
    return null;
  return { id, version, sha, impl };
}
export function capabilityLink(s: Selection): string {
  const p = new URLSearchParams({ id: s.id, version: s.version });
  if (s.sha) p.set("sha", s.sha);
  if (s.impl) p.set("impl", s.impl);
  const hash = "#capabilities?" + p;
  if (!parseCapabilityLink(hash)) throw new Error("Invalid capability link");
  return hash;
}

export interface Row {
  path: string;
  type: string;
  required: boolean;
  constraints: string;
}
// A flat, bounded view of the closed JSON-schema subset the backend accepts.
export function schemaRows(schema: Schema, prefix = "", depth = 0): Row[] {
  if (depth > 8) return [];
  const rows: Row[] = [];
  const required = new Set(schema.required ?? []);
  for (const [name, child] of Object.entries(schema.properties ?? {})) {
    const path = prefix + name;
    const limits = ["maxLength", "maxItems", "minimum", "maximum", "enum"]
      .filter((k) => k in child)
      .map((k) => `${k}=${JSON.stringify(child[k])}`)
      .join(", ");
    rows.push({
      path,
      type: child.type,
      required: required.has(name),
      constraints: limits,
    });
    if (child.type === "object") rows.push(...schemaRows(child, path + ".", depth + 1));
    if (child.type === "array" && child.items)
      rows.push(...schemaRows(child.items, path + "[].", depth + 1));
  }
  return rows.slice(0, 200);
}
