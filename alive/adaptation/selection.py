"""Relevance-aware lesson selection with an explicit "no lesson" outcome (AI-FIRST-04).

AI-FIRST-03 chose ``detected family -> latest eligible lesson``. This module decides, per task,
whether any owner-approved lesson is applicable, using existing lesson metadata and independently
measured outcomes only:

1. authorization eligibility (active, owner-approved export, same principal and destination);
2. mechanism applicability: the lesson's declared mechanisms must overlap the task's, and none of
   the lesson's excluded mechanisms may be present;
3. empirical standing: a lesson that was demoted on verified counterevidence is never selected;
   a lesson without demonstrated benefit needs an exact mechanism match and is labelled unproven;
4. a small cap, preferring demonstrated utility, then specificity, then support.

"Select nothing" is a normal result and is recorded with its reasons. No model confidence value
participates: the model only supplies the mechanism vocabulary tags (at intent time and when it
proposes a lesson). The decision itself is deterministic and costs no extra model call.

Utility evidence comes from ``adaptation.application`` events: independently measured outcomes of
turns in which a lesson was supplied, optionally paired with a stateless baseline on the same
task. Only train/dev measurements count; held-out outcomes can never update a lesson. Empirical
demotion is a separate durable event from the owner's withdrawal of consent.
"""

import json

from sqlalchemy import select

from alive.adaptation import service
from alive.admission.models import Admission
from alive.cognitive_models import ModelInvocation
from alive.models import Event
from alive.workflows.context import digest, require

POLICY = "selective-adaptation/v1"
MAX_SELECTED = 2
# Frozen per experiment and recorded in every selection. True: a lesson with no demonstrated
# benefit may be supplied on an exact mechanism match (it is labelled "unproven"). False:
# only lessons with measured paired gains are supplied.
ALLOW_UNPROVEN = True
AUTHORIZATION = {"owner_changed", "destination_changed", "not_active_or_withdrawn"}
APPLICATION = "adaptation.application"
DEMOTION = "adaptation.demotion"
SELECTION = "adaptation.selection"
COUNTED_SPLITS = ("train", "dev")

# Evaluation-only intervention (relevance/quantity ablations). It is a process-local object that
# no API request can set, it never bypasses authorization eligibility, and every record that used
# it says so. It is not a production behaviour.
_override = {"lessons": None, "reason": None}


class evaluation_override:  # noqa: N801 - used as a context manager
    def __init__(self, lesson_ids, reason):
        self.new = {"lessons": list(lesson_ids), "reason": reason}

    def __enter__(self):
        self.old = dict(_override)
        _override.update(self.new)

    def __exit__(self, *exc):
        _override.update(self.old)


def utility(applications, demoted):
    """Empirical standing of one lesson from its train/dev applications."""
    gains = losses = passed = failed = 0
    for body in applications:
        if body["split"] not in COUNTED_SPLITS:
            continue
        passed += body["passed"]
        failed += not body["passed"]
        baseline = body.get("baseline_passed")
        if baseline is None:
            continue
        gains += body["passed"] and not baseline
        losses += baseline and not body["passed"]
    contradicted = (losses >= 1 and losses > gains) or (failed >= 2 and passed == 0)
    state = (
        "demoted"
        if demoted
        else "contradicted"
        if contradicted
        else "useful"
        if gains >= 1 and gains > losses
        else "unproven"
    )
    return {
        "state": state,
        "applications": passed + failed,
        "applied_passed": passed,
        "applied_failed": failed,
        "paired_gains": gains,
        "paired_losses": losses,
    }


async def standing(session, kernel):
    """Per-lesson utility projection and the application refs behind it."""
    by_lesson, refs = {}, {}
    for row in await service.rows(session, kernel, APPLICATION):
        body = service.value(row)
        by_lesson.setdefault(body["lesson_id"], []).append(body)
        refs.setdefault(body["lesson_id"], []).append(row.id)
    demoted = {service.value(r)["lesson_id"] for r in await service.rows(session, kernel, DEMOTION)}
    lessons = set(by_lesson) | demoted
    return {
        lesson: (utility(by_lesson.get(lesson, []), lesson in demoted), refs.get(lesson, []))
        for lesson in lessons
    }


async def support(session, proposal):
    found = []
    for ref in proposal["supporting_experience_ids"]:
        row = await session.scalar(select(Event).where(Event.id == ref))
        if row is not None and row.source == service.SOURCE:
            body = service.value(row)
            found.append(
                {"experience_id": ref, "task_id": body["task_id"], "passed": body["passed"]}
            )
    return found


def authorized(body, principal, destination):
    """Do not expose another owner's or destination's lesson metadata."""
    return body["principal"] == principal and body["destination"] == destination


def rationale(body, task_mechanisms, tier, principal, destination):
    """(overlap, reasons) for one lesson. Empty reasons means selectable."""
    proposal = body["proposal"]
    mechanisms = set(proposal.get("mechanisms", []))
    excluded = set(proposal.get("excluded_mechanisms", []))
    task = set(task_mechanisms)
    reasons = []
    if body["state"] != "active" or not body["export"]:
        reasons.append("not_active_or_withdrawn")
    if body["principal"] != principal:
        reasons.append("owner_changed")
    if body["destination"] != destination:
        reasons.append("destination_changed")
    overlap = sorted(mechanisms & task)
    if not mechanisms:
        reasons.append("unscoped_lesson_without_mechanisms")
    elif not overlap:
        reasons.append("no_mechanism_overlap")
    hit = sorted(excluded & task)
    if hit:
        reasons.append("excluded_mechanism_present:" + ",".join(hit))
    if tier in ("demoted", "contradicted"):
        reasons.append("empirically_" + tier)
    if tier == "unproven" and not ALLOW_UNPROVEN:
        reasons.append("no_demonstrated_benefit")
    return overlap, reasons


def pick(ready):
    """Prefer demonstrated utility, then specificity, then support; cap and avoid redundancy."""
    ready.sort(
        key=lambda c: (
            c["utility"]["state"] == "useful",
            len(c["overlap"]),
            len(c["supporting_outcomes"]),
            c["version"],
        ),
        reverse=True,
    )
    chosen, covered = [], set()
    for c in ready:
        if len(chosen) == MAX_SELECTED or not set(c["overlap"]) - covered:
            c["reasons"].append("dominated_by_selected_lesson")
            continue
        chosen.append(c)
        covered |= set(c["overlap"])
    return chosen


async def choose(session, kernel, principal, destination, families, task_mechanisms):
    """Return (items, record). ``items`` is empty when no lesson is applicable."""
    eligible = []
    for row in (await service.latest(session, kernel)).values():
        body = service.value(row)
        if authorized(body, principal, destination):
            eligible.append((row, body))
    # Out-of-scope lessons must never enter the candidate record or support projection.
    states = await standing(session, kernel)
    candidates, rows = [], {}
    for row, body in eligible:
        lesson_id = body["lesson_id"]
        record, refs = states.get(lesson_id, (utility([], False), []))
        overlap, reasons = rationale(body, task_mechanisms, record["state"], principal, destination)
        rows[lesson_id] = (row, body)
        candidates.append(
            {
                "lesson_id": lesson_id,
                "row_id": row.id,
                "version": body["version"],
                "family": body["proposal"]["family"],
                "mechanisms": body["proposal"].get("mechanisms", []),
                "excluded_mechanisms": body["proposal"].get("excluded_mechanisms", []),
                "overlap": overlap,
                "utility": record,
                "application_refs": refs,
                "supporting_outcomes": await support(session, body["proposal"]),
                "reasons": reasons,
            }
        )
    forced = _override["lessons"]
    if forced is None:
        chosen = pick([c for c in candidates if not c["reasons"]])
    else:
        by_id = {c["lesson_id"]: c for c in candidates}
        require(
            all(i in by_id and not AUTHORIZATION & set(by_id[i]["reasons"]) for i in forced),
            "override_lesson_not_authorized",
        )
        chosen = [by_id[i] for i in forced]
        for c in candidates:
            if c not in chosen and not c["reasons"]:
                c["reasons"].append("evaluation_override_not_listed")
    items = []
    for c in chosen:
        row, body = rows[c["lesson_id"]]
        content = body["export"]["strategy"] | {
            "lesson_id": row.id,
            "version": body["version"],
            "qualification": body["qualification"],
        }
        items.append(service.item(row, "learned_strategy", content))
    picked = {c["lesson_id"] for c in chosen}
    for c in candidates:
        c["status"] = "selected" if c["lesson_id"] in picked else "excluded"
        c["tier"] = "demonstrated" if c["utility"]["state"] == "useful" else "unproven"
    if chosen:
        decision, why = "selected", None
    elif not task_mechanisms and not families:
        decision, why = "abstained", "task_mechanisms_unavailable"
    elif not candidates:
        decision, why = "none", "no_lessons_available"
    else:
        decision, why = "none", "no_applicable_lesson"
    record = {
        "policy": POLICY,
        "policy_parameters": {"allow_unproven": ALLOW_UNPROVEN, "max_selected": MAX_SELECTED},
        "decision": decision,
        "no_lesson_reason": why,
        "families": families,
        "task_mechanisms": task_mechanisms,
        "candidates": candidates,
        "selected": [
            {
                "item_id": c["row_id"],
                "lesson_id": c["lesson_id"],
                "version": c["version"],
                "content_sha256": i["content_sha256"],
                "tier": c["tier"],
            }
            for c, i in zip(chosen, items, strict=True)
        ],
        "context_bytes": len(json.dumps(items, ensure_ascii=False).encode()),
        "items_sha256": digest(items),
        "override": _override["reason"] if forced is not None else None,
    }
    return items, record


def legacy_record(mode, items, families, task_mechanisms):
    """Selection record for the non-selective arms, so every arm is auditable the same way."""
    names = {
        "stateless": "no-experience-control/v1",
        "contextual": "historical-context-control/v1",
        "learned": "family-latest-control/v1",
    }
    return {
        "policy": names[mode],
        "decision": "selected" if items else "none",
        "no_lesson_reason": None if items else "control_supplies_no_experience",
        "families": families,
        "task_mechanisms": task_mechanisms,
        "candidates": [],
        "selected": [
            {
                "item_id": i["id"],
                "lesson_id": i["admission_id"],
                "version": i["content"].get("version"),
                "content_sha256": i["content_sha256"],
                "tier": "control",
            }
            for i in items
        ],
        "context_bytes": len(json.dumps(items, ensure_ascii=False).encode()),
        "items_sha256": digest(items),
        "override": None,
    }


async def record_selection(session, kernel, key, record):
    return await service.put(session, kernel, SELECTION, key, record)


async def _validated_measurement(session, kernel, admission_id, measurement_ref):
    """Bind a measurement to a completed admission, its source, model and frozen context."""
    from alive.continuity import service as continuity

    admission = await session.get(Admission, admission_id)
    require(
        admission is not None and admission.instance_id == kernel.instance_id,
        "application_admission_scope_changed",
    )
    measured = await session.scalar(select(Event).where(Event.id == measurement_ref))
    require(
        measured is not None
        and measured.instance_id == kernel.instance_id
        and measured.source == service.ORACLE
        and measured.event_type == service.MEASURED,
        "independent_measurement_required",
    )
    outcome = service.value(measured)
    artifact = await continuity.artifact(session, kernel, admission)
    require(
        artifact is not None
        and outcome.get("admission_id") == admission_id
        and outcome.get("artifact_sha256") == artifact["sha256"]
        and outcome.get("source_sha256") == digest(admission.terms["source"])
        and not outcome.get("no_validated_artifact"),
        "measurement_binding_changed",
    )
    grant = admission.terms["proposed_grant_data"]
    snapshot_row = await continuity.event(
        session, kernel, grant["inputs"]["context_ref"], continuity.SNAPSHOT
    )
    snapshot = snapshot_row.payload["snapshot"]
    require(
        snapshot_row.payload["sha256"] == digest(snapshot)
        and grant["inputs"]["context_sha256"] == digest(snapshot),
        "application_context_binding_changed",
    )
    calls = (
        await session.scalars(
            select(ModelInvocation).where(
                ModelInvocation.investigation_id == grant["investigation_id"]
            )
        )
    ).all()
    models = {(c.provider, c.model, c.role) for c in calls}
    require(
        bool(calls) and len(models) == 1 and all(c.status == "validated" for c in calls),
        "measurement_model_identity_unavailable",
    )
    return admission, outcome, snapshot, models


async def record_application(
    kernel, admission_id, measurement_ref, *, baseline_measurement_ref=None, key=None
):
    """Attach an independently measured outcome to the lessons that were actually supplied.

    Held-out and unmeasured outcomes are refused so evaluation can never train the policy.
    Duplicate application is idempotent; a conflicting duplicate fails closed.
    """
    async with kernel.lock, kernel.db.sessions.begin() as session:
        admission, outcome, snapshot, models = await _validated_measurement(
            session, kernel, admission_id, measurement_ref
        )
        require(outcome["split"] in COUNTED_SPLITS, "evaluation_outcome_cannot_update_lessons")
        baseline = None
        if baseline_measurement_ref:
            other_admission_id = None
            other = await session.scalar(select(Event).where(Event.id == baseline_measurement_ref))
            require(
                other is not None
                and other.instance_id == kernel.instance_id
                and other.source == service.ORACLE
                and other.event_type == service.MEASURED,
                "independent_measurement_required",
            )
            other_admission_id = service.value(other).get("admission_id")
            require(
                other_admission_id and other_admission_id != admission_id,
                "baseline_must_be_same_task_other_run",
            )
            (
                other_admission,
                baseline,
                baseline_snapshot,
                baseline_models,
            ) = await _validated_measurement(
                session, kernel, other_admission_id, baseline_measurement_ref
            )
            require(
                all(
                    outcome.get(name) is not None and outcome[name] == baseline.get(name)
                    for name in (
                        "task_id",
                        "split",
                        "family",
                        "verifier",
                        "corpus_sha256",
                        "oracle_sha256",
                    )
                )
                and admission.principal == other_admission.principal
                and admission.terms["source"] == other_admission.terms["source"]
                and admission.terms.get("profile") == other_admission.terms.get("profile")
                and all(
                    admission.terms["model_disclosure"].get(name)
                    == other_admission.terms["model_disclosure"].get(name)
                    for name in (
                        "operation",
                        "destination",
                        "role",
                        "role_contract_sha256",
                        "context_policy",
                        "max_output_tokens",
                    )
                )
                and models == baseline_models,
                "baseline_identity_mismatch",
            )
            require(
                baseline_snapshot.get("strategy_mode") == "stateless"
                and baseline_snapshot.get("selection") == "no-experience-control/v1"
                and baseline_snapshot.get("decision") == "none"
                and baseline_snapshot.get("items") == [],
                "baseline_must_be_stateless",
            )
        supplied = [i for i in snapshot["items"] if i["source_type"] == "learned_strategy"]
        written = []
        for item in supplied:
            row = await session.scalar(select(Event).where(Event.id == item["id"]))
            require(
                row is not None
                and row.instance_id == kernel.instance_id
                and row.source == service.SOURCE
                and row.event_type == service.LESSON,
                "lesson_application_identity_changed",
            )
            lesson = service.value(row)
            require(
                authorized(
                    lesson,
                    admission.principal,
                    admission.terms["model_disclosure"]["destination"],
                ),
                "lesson_application_scope_changed",
            )
            body = {
                "lesson_id": lesson["lesson_id"],
                "lesson_row": row.id,
                "version": lesson["version"],
                "admission_id": admission_id,
                "selection_ref": snapshot.get("selection_ref"),
                "measurement_ref": measurement_ref,
                "baseline_measurement_ref": baseline_measurement_ref,
                "task_id": outcome["task_id"],
                "split": outcome["split"],
                "passed": outcome["passed"],
                "semantic": outcome.get("dimensions", {}).get("semantic"),
                "baseline_passed": baseline["passed"] if baseline else None,
            }
            written.append(
                await service.put(
                    session, kernel, APPLICATION, f"{key or measurement_ref}:{row.id}", body
                )
            )
        await session.flush()
        await demote_if_contradicted(session, kernel)
        return written


async def demote_if_contradicted(session, kernel):
    """Append one durable, evidence-linked demotion per lesson whose own record contradicts it."""
    for lesson_id, (record, refs) in (await standing(session, kernel)).items():
        if record["state"] == "contradicted":
            await service.put(
                session,
                kernel,
                DEMOTION,
                lesson_id,
                {
                    "lesson_id": lesson_id,
                    "reason": "verified_counterevidence_from_applications",
                    "evidence": sorted(refs),
                    "counts": {k: v for k, v in record.items() if k != "state"},
                    "withdrawal": False,
                },
            )


async def view(session, kernel, snapshot, answer, admission_id):
    """Owner-facing projection of one selection. Read-only: it can never dispatch anything."""
    ref = snapshot.get("selection_ref")
    row = await session.scalar(select(Event).where(Event.id == ref)) if ref else None
    if row is None or row.source != service.SOURCE:
        return None
    body = service.value(row)
    admission = await session.get(Admission, admission_id)
    require(
        admission is not None and admission.instance_id == kernel.instance_id,
        "selection_view_admission_unavailable",
    )
    destination = admission.terms["model_disclosure"]["destination"]
    visible = {
        service.value(lesson)["lesson_id"]
        for lesson in (await service.latest(session, kernel)).values()
        if authorized(service.value(lesson), admission.principal, destination)
    }
    # Reproject historical selection records as well: old records may contain foreign candidates.
    candidates = [c for c in body["candidates"] if c["lesson_id"] in visible]
    selected = [c for c in body["selected"] if c["lesson_id"] in visible]
    legacy_foreign_only = (
        body["decision"] == "refused"
        and body["no_lesson_reason"] == "authorization_scope"
        and not candidates
    )
    supplied = [i["id"] for i in snapshot["items"] if i["source_type"] == "learned_strategy"]
    measured = None
    for event in await service.rows(session, kernel, service.MEASURED, source=service.ORACLE):
        outcome = service.value(event)
        if outcome["admission_id"] == admission_id:
            measured = {
                "passed": outcome["passed"],
                "score": outcome["score"],
                "verifier": outcome["verifier"],
                "semantic": outcome.get("dimensions", {}).get("semantic"),
                "measurement_ref": event.id,
            }
    return {
        "ref": ref,
        "policy": body["policy"],
        "decision": "none" if legacy_foreign_only else body["decision"],
        "no_lesson_reason": (
            "no_lessons_available" if legacy_foreign_only else body["no_lesson_reason"]
        ),
        "task_mechanisms": body["task_mechanisms"],
        "override": body["override"],
        "received": supplied,
        "reported_used": [i for i in (answer or {}).get("lesson_ids_used", []) if i in supplied],
        "selected": selected,
        "candidates": [
            {
                k: c[k]
                for k in (
                    "lesson_id",
                    "status",
                    "reasons",
                    "overlap",
                    "tier",
                    "supporting_outcomes",
                )
            }
            for c in candidates
        ],
        "context_bytes": body["context_bytes"],
        "items_sha256": body["items_sha256"],
        "independent_outcome": measured,
    }
