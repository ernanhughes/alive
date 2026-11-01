"""Deterministic resolution of a model's proposals. Eligibility, not relevance, decides."""

from types import SimpleNamespace

from alive.bespoke.contracts import Constraints, Objective
from alive.bespoke.selector import evaluate
from alive.intent.contracts import INTERPRETER_RECIPE, IntentInterpretation
from alive.workflows.context import digest

SCHEMA = "alive-intent-recommendation/v1"
# The most the owner could later grant. Eligibility asks "could this be offered for admission?";
# whether it needs a model or a disclosure is reported separately and is never assumed granted.
CEILING = Constraints(
    max_model_calls=1,
    max_wall_seconds=3600,
    max_output_tokens=16384,
    outbound_allowed=True,
    permissions=[
        "repository.read",
        "evidence.read",
        "model.infer",
        "workflow.write",
        "source.read",
    ],
)


async def eligibility(session, kernel, recipes, goal, kind, source_ref, paths):
    """Existing deterministic selector, per recipe, for the intent kind and the approved source."""
    inputs = {"source_ref": source_ref, "paths": sorted(paths), "objective": goal}
    context = {
        "surface": "repository",
        "claims_count": 0,
        "sources_count": 1,
        "inputs_sha256": digest(inputs),
    }
    objective = Objective(kind=None if kind == "unclear" else kind, requested_outcome=goal)
    found = {}
    for recipe in recipes:
        if recipe.id == INTERPRETER_RECIPE:
            continue
        found[(recipe.id, recipe.version)] = await evaluate(
            session,
            kernel,
            recipe,
            SimpleNamespace(objective=objective, constraints=CEILING),
            SimpleNamespace(inputs=inputs),
            context,
        )
    return found


def admission_profile(recipe_id):
    from alive.admission.profiles import PROFILES

    return recipe_id if recipe_id in PROFILES and recipe_id != "intent-interpretation" else None


def assemble(*, goal, interpretation, goal_preserved, rows, eligible, source, meta):
    """Pure. `eligible` maps (id, version) to the deterministic Candidate for the intent kind."""
    index = {(r["recipe_id"], r["recipe_version"]): r for r in rows}
    known_ids = {r["recipe_id"] for r in rows}
    parsed = IntentInterpretation.model_validate(interpretation) if interpretation else None
    usable = parsed is not None and goal_preserved
    proposals, seen = [], set()
    for position, item in enumerate(parsed.candidates if usable else []):
        key = (item.recipe_id, item.recipe_version)
        if key in seen:
            continue
        seen.add(key)
        entry = {
            "recipe_id": item.recipe_id,
            "recipe_version": item.recipe_version,
            "addresses": item.addresses,
            "relevance": item.relevance,
            "order": position,
        }
        if key not in index:
            wrong = item.recipe_id in known_ids
            entry |= {
                "resolution": "wrong_version" if wrong else "unknown_recipe",
                "reasons": ["recipe_version_not_in_catalogue" if wrong else "not_in_catalogue"],
            }
        else:
            cand = eligible[key]
            entry |= {
                "resolution": "eligible" if cand.eligible else "ineligible",
                "reasons": list(cand.reasons),
                "suitability": cand.suitability,
                "factors": dict(cand.factors),
                "recipe_sha256": cand.recipe_sha256,
                "needs_model": index[key]["needs_model"],
                "sends_data_to_model_provider": index[key]["sends_data_to_model_provider"],
            }
        proposals.append(entry)
    fit = {"fully": 0, "partly": 1, "tangential": 2}
    ok = sorted(
        (p for p in proposals if p["resolution"] == "eligible"),
        key=lambda p: (fit[p["addresses"]], -p["suitability"], p["order"]),
    )
    unavailable = [p for p in proposals if p["resolution"] != "eligible"]
    proposed = {(p["recipe_id"], p["recipe_version"]) for p in proposals}
    also = sorted(
        (
            {
                "recipe_id": rid,
                "recipe_version": ver,
                "suitability": c.suitability,
                "needs_model": index[(rid, ver)]["needs_model"],
            }
            for (rid, ver), c in eligible.items()
            if c.eligible and (rid, ver) in index and (rid, ver) not in proposed
        ),
        key=lambda p: (-p["suitability"], p["recipe_id"]),
    )
    recommended = ok[0] if ok else None
    if not usable:
        status = "rejected_interpretation"
    elif recommended:
        status = "recommended"
    elif parsed.needs_clarification:
        status = "clarification_needed"
    else:
        status = "no_executable_recommendation"
    return {
        "schema": SCHEMA,
        "status": status,
        "original_goal": goal,
        "goal_preservation": {
            "preserved": bool(goal_preserved),
            "model_goal": parsed.explicit_goal if parsed else None,
        },
        "source": source,
        "catalogue_sha256": meta["catalogue_sha256"],
        "interpreter": meta["interpreter"],
        "interpretation": {"origin": "model_inference", "value": interpretation},
        "resolution": {
            "origin": "trusted_system",
            "intent_kind_used": None if not usable else parsed.intent_kind,
            "proposals": proposals,
        },
        "recommendation": None
        if recommended is None
        else {
            **{k: recommended[k] for k in ("recipe_id", "recipe_version", "suitability")},
            "chosen_by": "eligible, best model-judged fit; deterministic suitability breaks ties",
            "needs_model": recommended["needs_model"],
            "sends_data_to_model_provider": recommended["sends_data_to_model_provider"],
        },
        "alternatives": ok[1:],
        "unavailable": unavailable,
        "also_eligible_not_proposed": also,
        "uncertainty": None
        if not usable
        else {
            "ambiguities": parsed.ambiguities,
            "missing_information": parsed.missing_information,
            "assumptions": parsed.assumptions,
            "alternative_interpretations": parsed.alternative_interpretations,
            "limits_of_available_procedures": parsed.limits_of_available_procedures,
            "needs_clarification": parsed.needs_clarification,
            "clarification_question": parsed.clarification_question,
        },
        "authorization": {
            "execution": "not_authorized",
            "this_recommendation_grants": "nothing",
            "next_step": "a separate owner admission review and local approval"
            if recommended
            else "none",
            "admission_profile": admission_profile(recommended["recipe_id"])
            if recommended
            else None,
            "needs_model_authorization": bool(recommended and recommended["needs_model"]),
        },
    }
