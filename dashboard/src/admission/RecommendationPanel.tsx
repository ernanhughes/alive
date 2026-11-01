import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "../api";
import type { Recommendation } from "./contracts";

const PROFILE_LABEL: Record<string, string> = {
  "approved-repository-inspection": "Inspect captured files (no model)",
  "approved-repository-analysis": "Analyze with one model call",
};

function List({ items }: { items: string[] }) {
  return items.length ? (
    <ul>
      {items.map((item, index) => (
        <li key={index}>{item}</li>
      ))}
    </ul>
  ) : (
    <p>None stated.</p>
  );
}

export function RecommendationPanel({
  admissionId,
  token,
  onPrepare,
}: {
  admissionId: string;
  token: string;
  onPrepare: (profile: string) => void;
}) {
  const [value, setValue] = useState<Recommendation | null>(null);
  const [absent, setAbsent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const generation = useRef(0);
  const path = `/admissions/${encodeURIComponent(admissionId)}/recommendation`;

  useEffect(() => {
    const version = ++generation.current;
    const c = new AbortController();
    setValue(null);
    setAbsent(false);
    setError("");
    request<Recommendation>(path, token, undefined, "GET", c.signal)
      .then((v) => {
        if (generation.current === version && v.admission_id === admissionId)
          setValue(v);
      })
      .catch((e) => {
        if (generation.current !== version || e?.name === "AbortError") return;
        if (e instanceof ApiError && e.status === 409) setAbsent(true);
        else setError(e instanceof Error ? e.message : "Unavailable");
      });
    return () => c.abort();
  }, [admissionId, token, path]);

  async function compose() {
    const version = ++generation.current;
    setBusy(true);
    setError("");
    try {
      const v = await request<Recommendation>(path, token, {}, "POST");
      if (generation.current === version && v.admission_id === admissionId) {
        setValue(v);
        setAbsent(false);
      }
    } catch (e) {
      if (generation.current === version)
        setError(
          e instanceof Error
            ? "Could not compose the recommendation: " + e.message
            : "Could not compose the recommendation.",
        );
    } finally {
      if (generation.current === version) setBusy(false);
    }
  }

  if (error)
    return (
      <p role="alert" aria-label="Recommendation error">
        {error}
      </p>
    );
  if (!value)
    return absent ? (
      <section aria-label="Recommendation">
        <h4>Recommendation</h4>
        <p>
          The interpretation finished. Composing the recommendation re-checks
          which procedures are eligible now. It calls no model and grants
          nothing.
        </p>
        <button onClick={compose} disabled={busy}>
          {busy ? "Composing…" : "Compose recommendation"}
        </button>
      </section>
    ) : null;

  const r = value.record;
  const interpretation = r.interpretation.value;
  const rec = r.recommendation;
  return (
    <section aria-label="Recommendation" className="admission-recommendation">
      <h4>Recommendation</h4>
      <p>
        Status: <strong>{r.status.replaceAll("_", " ")}</strong>. Nothing here
        is authorized: {r.authorization.this_recommendation_grants}.
      </p>
      <h5>You asked</h5>
      <blockquote>{r.original_goal}</blockquote>
      {!r.goal_preservation.preserved && (
        <p role="alert">
          The model did not return your goal unchanged, so its interpretation
          was rejected.
        </p>
      )}
      {interpretation && r.goal_preservation.preserved && (
        <>
          <h5>ALIVE interpreted (model inference, unverified)</h5>
          <p>{interpretation.primary_objective}</p>
          <List
            items={interpretation.subordinate_objectives.map(
              (s) => `${s.objective}: ${s.rationale}`,
            )}
          />
          <h5>Evidence needed</h5>
          <List
            items={interpretation.evidence_requirements.map(
              (e) => `${e.requirement} (${e.importance}, ${e.status})`,
            )}
          />
        </>
      )}
      <h5>Recommended procedure (trusted eligibility check)</h5>
      {rec ? (
        <>
          <p>
            <strong>
              {rec.recipe_id} v{rec.recipe_version}
            </strong>{" "}
            · {rec.chosen_by}
            {rec.needs_model
              ? ". It needs its own model authorization and sends data to the model provider."
              : ". It makes no model call."}
          </p>
          {r.authorization.admission_profile && (
            <button
              onClick={() => onPrepare(r.authorization.admission_profile!)}
            >
              Prepare a review for{" "}
              {PROFILE_LABEL[r.authorization.admission_profile] ??
                r.authorization.admission_profile}
            </button>
          )}
        </>
      ) : (
        <p>No executable recommendation.</p>
      )}
      {r.alternatives.length > 0 && (
        <>
          <h5>Alternatives</h5>
          <List
            items={r.alternatives.map(
              (a) => `${a.recipe_id} v${a.recipe_version} (${a.addresses})`,
            )}
          />
        </>
      )}
      {r.resolution.proposals.some((p) => p.resolution !== "eligible") && (
        <>
          <h5>Relevant but unavailable</h5>
          <List
            items={r.unavailable.map(
              (p) =>
                `${p.recipe_id} v${p.recipe_version}: ${p.resolution.replaceAll("_", " ")} (${p.reasons.join(", ")})`,
            )}
          />
        </>
      )}
      {r.uncertainty && (
        <>
          <h5>Uncertainty</h5>
          <List
            items={[
              ...r.uncertainty.ambiguities.map((x) => "Ambiguity: " + x),
              ...r.uncertainty.missing_information.map((x) => "Missing: " + x),
              ...r.uncertainty.assumptions.map((x) => "Assumed: " + x),
              ...r.uncertainty.alternative_interpretations.map(
                (x) => "Could also mean: " + x,
              ),
              ...r.uncertainty.limits_of_available_procedures.map(
                (x) => "Procedures cannot: " + x,
              ),
            ]}
          />
          {r.uncertainty.needs_clarification && (
            <p>
              <strong>Clarification:</strong>{" "}
              {r.uncertainty.clarification_question}
            </p>
          )}
        </>
      )}
      <p className="admission-digest">
        Interpreter {r.interpreter.model} · {r.interpreter.model_calls} model
        call · catalogue {r.catalogue_sha256}
      </p>
    </section>
  );
}
