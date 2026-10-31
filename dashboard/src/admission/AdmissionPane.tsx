import { useEffect, useRef, useState } from "react";
import { ApiError, request } from "../api";
import type { Goal } from "../api";
import { WorkflowGraph } from "../workflows/WorkflowGraph";
import { PROFILE_LIMITS, admissionRef, checkedAdmission } from "./contracts";
import type {
  Admission,
  Profile,
  ProfileName,
  Report,
  Source,
} from "./contracts";
import "../workflows/workflows.css";
import "./admission.css";

export function AdmissionPane({ token }: { token: string }) {
  return <OwnerAdmission key={token} token={token} />;
}

function OwnerAdmission({ token }: { token: string }) {
  const [sources, setSources] = useState<Source[]>([]);
  const [goals, setGoals] = useState<Goal[]>([]);
  const [profile, setProfile] = useState<Profile | null>(null);
  const [profileName, setProfileName] = useState<ProfileName>(
    "approved-repository-inspection",
  );
  const [report, setReport] = useState<Report | null>(null);
  const [profileError, setProfileError] = useState("");
  const [history, setHistory] = useState<Admission[]>([]);
  const [sourceRef, setSourceRef] = useState("");
  const [goalRef, setGoalRef] = useState("");
  const [paths, setPaths] = useState<string[]>([]);
  const [outcome, setOutcome] = useState("");
  const [selectedId, setSelectedId] = useState<string | null>(() =>
    admissionRef(window.location.hash),
  );
  const [selected, setSelected] = useState<Admission | null>(null);
  const [selectedStage, setSelectedStage] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [creating, setCreating] = useState(false);
  const [starting, setStarting] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [revision, setRevision] = useState(0);
  const generation = useRef(0);
  const draftGeneration = useRef(0);
  const controllers = useRef(new Set<AbortController>());
  const identity = useRef<{ id: string; hash: string } | null>(null);
  const retry = useRef<{ signature: string; key: string } | null>(null);

  useEffect(() => {
    const change = () => {
      generation.current++;
      setSelectedId(admissionRef(window.location.hash));
    };
    window.addEventListener("hashchange", change);
    return () => {
      window.removeEventListener("hashchange", change);
      generation.current++;
      for (const controller of controllers.current) controller.abort();
    };
  }, []);

  function controller() {
    const c = new AbortController();
    controllers.current.add(c);
    return c;
  }
  function display(value: Admission, id: string) {
    const current = checkedAdmission(value, id);
    if (
      identity.current?.id === id &&
      identity.current.hash !== current.review_sha256
    ) {
      setSelected(null);
      throw new Error(
        "The retained review identity changed. Start is unavailable.",
      );
    }
    identity.current = { id, hash: current.review_sha256 };
    setSelected(current);
    if (current.run?.terminal) {
      setStarting(false);
      setCancelling(false);
    }
    setHistory((previous) => [
      current,
      ...previous.filter((row) => row.id !== current.id),
    ]);
  }
  function failed(e: unknown) {
    if (e instanceof Error && e.name !== "AbortError") setError(e.message);
  }

  useEffect(() => {
    const c = controller();
    let active = true;
    setLoading(true);
    setError("");
    setProfile(null);
    setProfileError("");
    Promise.allSettled([
      request<{ sources: Source[] }>(
        "/admissions/sources?profile=" + profileName,
        token,
        undefined,
        "GET",
        c.signal,
      ),
      request<Goal[]>("/goals", token, undefined, "GET", c.signal),
      request<Profile>(
        "/admissions/profile?profile=" + profileName,
        token,
        undefined,
        "GET",
        c.signal,
      ),
      request<{ admissions: Admission[] }>(
        "/admissions",
        token,
        undefined,
        "GET",
        c.signal,
      ),
    ]).then(([sourceResult, goalResult, profileResult, historyResult]) => {
      if (!active) return;
      if (sourceResult.status === "fulfilled")
        setSources(sourceResult.value.sources);
      else {
        setSources([]);
        failed(sourceResult.reason);
      }
      if (goalResult.status === "fulfilled")
        setGoals(
          goalResult.value.filter((g) =>
            ["accepted", "active"].includes(g.status),
          ),
        );
      else {
        setGoals([]);
        failed(goalResult.reason);
      }
      if (profileResult.status === "fulfilled") setProfile(profileResult.value);
      else
        setProfileError(
          profileResult.reason instanceof ApiError &&
            profileResult.reason.status === 409
            ? "Install the reviewed inspection profile on the owner machine: python -m alive.admission install"
            : "Admission profile unavailable. Check the connection and owner installation.",
        );
      if (historyResult.status === "fulfilled")
        setHistory(historyResult.value.admissions);
      else {
        setHistory([]);
        failed(historyResult.reason);
      }
      setLoading(false);
    });
    return () => {
      active = false;
      c.abort();
      controllers.current.delete(c);
    };
  }, [token, revision, profileName]);

  useEffect(() => {
    const version = ++generation.current;
    setSelected(null);
    setSelectedStage("");
    setCreating(false);
    setStarting(false);
    setCancelling(false);
    identity.current = null;
    if (!selectedId) return;
    const c = controller();
    request<Admission>(
      "/admissions/" + encodeURIComponent(selectedId),
      token,
      undefined,
      "GET",
      c.signal,
    )
      .then((value) => {
        if (generation.current === version && !c.signal.aborted)
          display(value, selectedId);
      })
      .catch((e) => {
        if (generation.current === version) failed(e);
      });
    return () => {
      c.abort();
      controllers.current.delete(c);
    };
  }, [selectedId, token, revision]);

  useEffect(() => {
    if (
      !selectedId ||
      !(starting || cancelling || (selected?.run && !selected.run.terminal))
    )
      return;
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    const c = controller();
    const version = generation.current;
    async function poll() {
      try {
        const value = await request<Admission>(
          "/admissions/" + encodeURIComponent(selectedId!),
          token,
          undefined,
          "GET",
          c.signal,
        );
        if (active && generation.current === version && !c.signal.aborted)
          display(value, selectedId!);
      } catch (e) {
        if (active && generation.current === version) failed(e);
      }
      if (active) timer = setTimeout(poll, 1000);
    }
    timer = setTimeout(poll, 1000);
    return () => {
      active = false;
      clearTimeout(timer);
      c.abort();
      controllers.current.delete(c);
    };
  }, [selectedId, starting, cancelling, selected?.run?.terminal, token]);

  useEffect(() => {
    setReport(null);
    if (
      !selectedId ||
      selected?.id !== selectedId ||
      selected.terms.profile !== "approved-repository-analysis" ||
      selected.run?.status !== "COMPLETED"
    )
      return;
    const c = controller();
    request<Report>(
      `/admissions/${encodeURIComponent(selectedId)}/report`,
      token,
      undefined,
      "GET",
      c.signal,
    )
      .then((value) => {
        if (!c.signal.aborted && value.admission_id === selectedId)
          setReport(value);
      })
      .catch(failed);
    return () => {
      c.abort();
      controllers.current.delete(c);
    };
  }, [selectedId, selected?.id, selected?.run?.status, token]);

  const source = sources.find((s) => s.approval_ref === sourceRef);
  const allowed =
    source?.inventory.items.filter(
      (item) => source.scope.all || source.scope.items?.includes(item.item),
    ) || [];
  const sourceBytes = allowed.reduce(
    (total, item) => total + (item.bytes || 0),
    0,
  );
  const limits = PROFILE_LIMITS[profileName];
  const canPrepare =
    !!profile &&
    !!source &&
    Date.parse(source.expires_at) > Date.now() &&
    goals.some((g) => g.id === goalRef) &&
    !!outcome.trim() &&
    paths.length > 0 &&
    paths.length <= limits.files &&
    paths.length === allowed.length &&
    sourceBytes <= limits.bytes &&
    !starting &&
    !cancelling &&
    paths.every((path) => allowed.some((item) => item.item === path)) &&
    !loading &&
    !creating;

  async function prepare() {
    if (!canPrepare || !profile) return;
    const body = {
      profile: profileName,
      goal_ref: goalRef,
      approval_ref: sourceRef,
      recipe_sha256: profile.recipe_sha256,
      objective: { kind: "inspect_implementation", requested_outcome: outcome },
      paths: [...paths].sort(),
      ttl_seconds: 300,
    };
    const signature = JSON.stringify(body);
    if (retry.current?.signature !== signature)
      retry.current = { signature, key: crypto.randomUUID() };
    const version = ++draftGeneration.current;
    const viewVersion = generation.current;
    const c = controller();
    setCreating(true);
    setError("");
    try {
      const value = checkedAdmission(
        await request<Admission>(
          "/admissions",
          token,
          { ...body, idempotency_key: retry.current.key },
          "POST",
          c.signal,
        ),
      );
      if (
        draftGeneration.current !== version ||
        generation.current !== viewVersion ||
        c.signal.aborted
      )
        return;
      window.location.hash = "#admission?id=" + encodeURIComponent(value.id);
      setSelectedId(value.id);
      display(value, value.id);
    } catch (e) {
      if (
        draftGeneration.current === version &&
        generation.current === viewVersion
      )
        failed(e);
    } finally {
      controllers.current.delete(c);
      if (draftGeneration.current === version) setCreating(false);
    }
  }

  async function action(kind: "start" | "cancel") {
    if (!selected) return;
    const id = selected.id;
    const version = ++generation.current;
    const c = controller();
    setError("");
    if (kind === "start") setStarting(true);
    else setCancelling(true);
    try {
      const value = await request<Admission>(
        `/admissions/${encodeURIComponent(id)}/${kind}`,
        token,
        kind === "start" ? { review_sha256: selected.review_sha256 } : {},
        "POST",
        c.signal,
      );
      if (generation.current !== version || c.signal.aborted) return;
      display(value, id);
      generation.current++;
      setStarting(false);
      setCancelling(false);
    } catch (e) {
      if (generation.current === version) failed(e);
    } finally {
      controllers.current.delete(c);
      if (generation.current === version) {
        setStarting(false);
        setCancelling(false);
      }
    }
  }

  function newReview() {
    generation.current++;
    draftGeneration.current++;
    retry.current = null;
    setCreating(false);
    setStarting(false);
    setCancelling(false);
    setSelectedId(null);
    setSelected(null);
    identity.current = null;
    window.location.hash = "#admission?";
  }
  const grant = selected?.terms.proposed_grant_data;
  const disclosure = selected?.terms.model_disclosure;
  const readPaths = grant?.inputs?.paths || selected?.terms.paths || [];
  const canStart =
    selected?.authorization_state === "approved" &&
    !selected.run &&
    !starting &&
    !cancelling &&
    !!grant &&
    Date.parse(grant.expires_at) > Date.now();
  return (
    <section className="owner-admission" aria-label="Owner admission">
      <div className="admission-heading">
        <div>
          <p className="eyebrow">LEVEL 1 · GOVERNED INTELLIGENCE</p>
          <h2>Owner admission</h2>
          <p>
            Review an exact captured source and inspection procedure before
            authorizing it on your machine.
          </p>
        </div>
        <button
          onClick={() => setRevision((r) => r + 1)}
          disabled={starting || cancelling}
        >
          Refresh admission
        </button>
      </div>
      {error && <p role="alert">{error}</p>}
      {profileError && <p role="alert">{profileError}</p>}
      {loading && (
        <p role="status">Loading approved sources and admission history…</p>
      )}
      <div className="admission-layout">
        <div className="admission-form">
          <h3>Prepare an owner review</h3>
          <p>
            Install the reviewed profile on the owner machine with{" "}
            <code>python -m alive.admission install</code>.
          </p>
          <p>
            Capture and approve source content with the existing local{" "}
            <code>python -m alive.sources</code> commands. Preparing this review
            grants no execution authority.
          </p>
          {!loading && !sources.length && (
            <p>
              No current approved repository captures. Prepare and approve a
              source on the owner machine, then refresh.
            </p>
          )}
          <label>
            Procedure
            <select
              value={profileName}
              onChange={(e) => {
                draftGeneration.current++;
                setCreating(false);
                setSourceRef("");
                setPaths([]);
                setProfileName(e.target.value as ProfileName);
              }}
            >
              <option value="approved-repository-inspection">
                Inspect captured files (no model)
              </option>
              <option value="approved-repository-analysis">
                Analyze with one model call (sends code to the model provider)
              </option>
            </select>
          </label>
          <label>
            Approved repository capture
            <select
              value={sourceRef}
              onChange={(e) => {
                draftGeneration.current++;
                setCreating(false);
                setSourceRef(e.target.value);
                setPaths([]);
              }}
            >
              <option value="">Choose an approved capture</option>
              {sources.map((s) => (
                <option key={s.approval_ref} value={s.approval_ref}>
                  {s.label} · {s.capture_ref.slice(0, 8)}
                </option>
              ))}
            </select>
          </label>
          {source && (
            <>
              <p className="admission-digest">
                Captured digest: {source.content_sha256}
              </p>
              <p>Source approval expires: {source.expires_at}</p>
              <p>
                Select every file in this source approval. To inspect fewer
                files, narrow the approval locally first. Maximum:{" "}
                {limits.files} files and {limits.bytes.toLocaleString("en-US")}{" "}
                bytes.
                {limits.model &&
                  " This capture must also be approved locally for disclosure to the model (operation repository.analyze)."}
              </p>
              {sourceBytes > limits.bytes && (
                <p role="alert">
                  This approved capture exceeds the inspection byte ceiling.
                  Prepare a narrower source approval.
                </p>
              )}
              <fieldset>
                <legend>
                  Exact files to read ({paths.length}/{limits.files})
                </legend>
                {allowed.map((item) => (
                  <label className="admission-file" key={item.item}>
                    <input
                      type="checkbox"
                      checked={paths.includes(item.item)}
                      disabled={
                        !paths.includes(item.item) &&
                        paths.length >= limits.files
                      }
                      onChange={(e) => {
                        draftGeneration.current++;
                        setCreating(false);
                        setPaths((previous) =>
                          e.target.checked
                            ? [...previous, item.item]
                            : previous.filter((p) => p !== item.item),
                        );
                      }}
                    />
                    <span>
                      {item.item}
                      {item.bytes !== undefined && (
                        <small> · {item.bytes} bytes</small>
                      )}
                    </span>
                  </label>
                ))}
              </fieldset>
            </>
          )}
          <label>
            Approved goal
            <select
              value={goalRef}
              onChange={(e) => {
                draftGeneration.current++;
                setCreating(false);
                setGoalRef(e.target.value);
              }}
            >
              <option value="">Choose an active or accepted goal</option>
              {goals.map((g) => (
                <option key={g.id} value={g.id}>
                  {g.title}
                </option>
              ))}
            </select>
          </label>
          <label>
            Requested inspection outcome
            <textarea
              maxLength={1000}
              value={outcome}
              onChange={(e) => {
                draftGeneration.current++;
                setCreating(false);
                setOutcome(e.target.value);
              }}
            />
          </label>
          {limits.model ? (
            <p role="note">
              This procedure makes one model call. The exact files you select
              are sent, as text, to the model provider shown in the review, and
              the prompt and response are retained in clear text in the local
              database. Cost is not estimated. It needs a started Meta
              cognition. Review expiry: 5 minutes.
            </p>
          ) : (
            <p>
              This profile reads captured files only. It requests no model
              inference, no outbound calls, and at most 30 seconds of execution.
              Review expiry: 5 minutes.
            </p>
          )}
          <button onClick={prepare} disabled={!canPrepare}>
            Prepare exact review
          </button>
          <button onClick={newReview} disabled={starting || cancelling}>
            New review
          </button>
          <h3>Admission history</h3>
          {!history.length && !loading && <p>No admission history.</p>}
          <ul>
            {history.map((row) => (
              <li key={row.id}>
                <a href={"#admission?id=" + encodeURIComponent(row.id)}>
                  {row.id.slice(0, 8)} · {row.authorization_state} · {row.state}
                </a>
              </li>
            ))}
          </ul>
        </div>
        <div className="admission-review">
          {!selected && (
            <p>
              Select a recorded admission or prepare a review to inspect its
              exact scope.
            </p>
          )}
          {selected && grant && (
            <>
              <h3>Exact owner review</h3>
              <p>
                Admission state: <strong>{selected.state}</strong> · Owner
                authorization: <strong>{selected.authorization_state}</strong>
              </p>
              <WorkflowGraph
                graph={selected.terms.candidate.graph!}
                states={{}}
                selected={selectedStage}
                onSelect={setSelectedStage}
              />
              <div className="admission-facts">
                <h4>Source and purpose</h4>
                <dl>
                  <div>
                    <dt>Goal</dt>
                    <dd>
                      {selected.terms.goal.title} · {selected.terms.goal.id}
                    </dd>
                  </div>
                  <div>
                    <dt>Objective</dt>
                    <dd>{selected.terms.objective.requested_outcome}</dd>
                  </div>
                  <div>
                    <dt>Source</dt>
                    <dd>
                      {selected.terms.source.label} ·{" "}
                      {selected.terms.source.resources.source_ref}
                    </dd>
                  </div>
                  <div>
                    <dt>Content digest</dt>
                    <dd>{selected.terms.source.resources.content_sha256}</dd>
                  </div>
                  <div>
                    <dt>Source approval</dt>
                    <dd>{selected.terms.source.resources.approval_id}</dd>
                  </div>
                  <div>
                    <dt>Scope digest</dt>
                    <dd>{selected.terms.source.resources.scope_sha256}</dd>
                  </div>
                  <div>
                    <dt>Approved source scope</dt>
                    <dd>
                      {selected.terms.source.scope.all
                        ? "All captured items"
                        : selected.terms.source.scope.items?.join(", ")}
                    </dd>
                  </div>
                  <div>
                    <dt>Files this procedure reads</dt>
                    <dd>
                      {readPaths.length
                        ? readPaths.join(", ")
                        : "See the exact workflow input scope in the local owner review."}
                    </dd>
                  </div>
                </dl>
                <h4>Procedure and limits</h4>
                <p>
                  {selected.terms.candidate.recipe.name}:{" "}
                  {selected.terms.candidate.recipe.description}
                </p>
                <p className="admission-digest">
                  Recipe {selected.terms.candidate.recipe.id} v
                  {selected.terms.candidate.recipe.version} ·{" "}
                  {selected.terms.candidate.recipe_sha256}
                </p>
                <p className="admission-digest">
                  Workflow {selected.terms.candidate.recipe.workflow.name} v
                  {selected.terms.candidate.recipe.workflow.version} ·{" "}
                  {selected.terms.candidate.recipe.workflow.definition_sha256}
                </p>
                <ul>
                  {selected.terms.candidate.recipe.capabilities.map((cap) => (
                    <li key={cap.stage_id}>
                      {cap.id} v{cap.version} ·{" "}
                      <span className="admission-digest">
                        {cap.manifest_sha256}
                      </span>
                    </li>
                  ))}
                </ul>
                <p>
                  Required permissions:{" "}
                  {selected.terms.candidate.recipe.limits.permissions.join(
                    ", ",
                  )}
                  .
                </p>
                <p className="admission-digest">
                  Capability binding: {selected.terms.candidate.binding_sha256}
                </p>
                {disclosure ? (
                  <>
                    <h4>Disclosure to the model provider</h4>
                    <dl>
                      <div>
                        <dt>Destination</dt>
                        <dd>
                          {disclosure.destination.provider} (
                          {disclosure.destination.host ?? "host unknown"}) ·
                          model {disclosure.destination.model} · via{" "}
                          {disclosure.destination.transport}
                        </dd>
                      </div>
                      <div>
                        <dt>Leaves this machine</dt>
                        <dd>
                          Yes: {disclosure.files.map((f) => f.path).join(", ")}{" "}
                          ({disclosure.source_bytes} bytes)
                        </dd>
                      </div>
                      <div>
                        <dt>Limits</dt>
                        <dd>
                          {disclosure.max_model_calls} model call, at most{" "}
                          {disclosure.max_output_tokens} output tokens, request
                          reservation {disclosure.reserved_request_bytes}
                        </dd>
                      </div>
                      <div>
                        <dt>Cost</dt>
                        <dd>{disclosure.cost}</dd>
                      </div>
                      <div>
                        <dt>Cancellation</dt>
                        <dd>{disclosure.cancellation}</dd>
                      </div>
                      <div>
                        <dt>Retention</dt>
                        <dd>{disclosure.retention}</dd>
                      </div>
                    </dl>
                    <p>
                      Execution ceiling: {grant.wall_seconds} seconds. Expires:{" "}
                      {grant.expires_at}. Findings are model assessments; cited
                      lines are checked for existence only, and nothing is
                      verified.
                    </p>
                  </>
                ) : (
                  <>
                    <p>
                      Model calls: 0. Model output tokens: 0. Outbound calls:
                      none. Execution ceiling: {grant.wall_seconds} seconds.
                    </p>
                    <p>
                      Expires: {grant.expires_at}. Expected output: captured
                      files with source identity and provenance. Capture and
                      reference identity do not establish semantic truth or
                      implementation quality.
                    </p>
                  </>
                )}
              </div>
              <h4>Confirm on the owner machine</h4>
              <p>
                Inspect the exact review and run this local command only if you
                approve its scope. This dashboard cannot approve it.
              </p>
              <p className="admission-digest">
                Review digest: {selected.review_sha256}
              </p>
              <pre>{`python -m alive.admission approve ${selected.id} --confirm-sha256 ${selected.review_sha256}`}</pre>
              <p>
                Refresh after local approval. Revocation remains available
                through the local owner command.
              </p>
              <div className="admission-actions">
                <button disabled={!canStart} onClick={() => action("start")}>
                  {starting
                    ? "Inspection in progress…"
                    : "Start approved inspection"}
                </button>
                {(starting || (selected.run && !selected.run.terminal)) && (
                  <button
                    disabled={cancelling}
                    onClick={() => action("cancel")}
                  >
                    {cancelling ? "Cancelling…" : "Cancel this inspection"}
                  </button>
                )}
              </div>
              {selected.run && (
                <p>
                  Execution: <strong>{selected.run.status}</strong> ·{" "}
                  <a
                    href={
                      "#workflows?" +
                      new URLSearchParams({
                        workflow: selected.run.workflow.name,
                        version: String(selected.run.workflow.version),
                        run: selected.run.id,
                      })
                    }
                  >
                    Inspect actual run in Workflow Observatory
                  </a>
                  . Task quality remains unverified.
                </p>
              )}
              {report && (
                <section aria-label="Analysis report">
                  <h4>Analysis report</h4>
                  <p>
                    Citations that match the captured files:{" "}
                    {report.assessment.findings_with_valid_references} of{" "}
                    {report.assessment.findings_total}. Independent
                    verification: none. Model {report.usage.model} ·{" "}
                    {report.usage.model_calls} call · status{" "}
                    {report.usage.status} · {report.usage.cost}
                  </p>
                  <pre className="admission-report">
                    {report.result.report_markdown}
                  </pre>
                </section>
              )}
            </>
          )}
        </div>
      </div>
    </section>
  );
}
