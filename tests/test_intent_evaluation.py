# ruff: noqa: F811  (pytest fixtures are imported by name)
"""L2-01 evaluation harness: three strategies on the same tasks, scored against fixed labels.

Offline and scripted. These tests prove the harness can tell a real interpretation from a fake one
and that eligibility stays authoritative. They do not measure how well any real model interprets.
"""

import json

import pytest

from alive.bespoke.recipes import load_catalogue
from alive.intent import context as intent_context
from alive.intent.recommend import assemble, eligibility
from tests.intent_benchmark import (
    ANALYSIS,
    INSPECTION,
    TASKS,
    always_analysis,
    invents_a_recipe,
    replaces_the_goal,
)
from tests.test_intent_interpretation import (  # noqa: F401  (fixtures that boot the app)
    case,
    quick_settle,
    ready,
    settings,
)
from tests.test_owner_admission import call

FIXED_DEFAULT = INSPECTION


async def run_task(kernel, task, interpret):
    """Returns the recommendation (recipe id or None) for each strategy on one task."""
    recipes = getattr(kernel, "bespoke_recipes", None) or load_catalogue()
    rows = intent_context.project_catalogue(recipes)
    paths = task["files"]

    async def ready_flag():
        return task["provider_ready"]

    original = getattr(kernel, "model_provider_ready", None)
    kernel.model_provider_ready = ready_flag
    try:
        async with kernel.db.sessions() as session:
            kinds = {}

            async def eligible_for(kind):
                if kind not in kinds:
                    kinds[kind] = await eligibility(
                        session, kernel, recipes, task["goal"], kind, "src", paths
                    )
                return kinds[kind]

            base = await eligible_for(task["explicit_kind"] or "unclear")
            # A: one fixed recipe, whatever the goal
            fixed_pool = await eligible_for("inspect_implementation")  # ignores the intent
            fixed = FIXED_DEFAULT if fixed_pool[(FIXED_DEFAULT, "1.0.0")].eligible else None
            # B: BESPOKE-01 selector semantics: highest suitability among eligible, else abstain
            ranked = sorted(
                (c for c in base.values() if c.eligible),
                key=lambda c: (-c.suitability, c.recipe.id),
            )
            deterministic = ranked[0].recipe.id if ranked else None
            # C: model interpretation, then the same eligibility
            model = interpret(task["goal"])
            kind = model["intent_kind"]
            record = assemble(
                goal=task["goal"],
                interpretation=model,
                goal_preserved=model["explicit_goal"] == task["goal"],
                rows=rows,
                eligible=await eligible_for(kind),
                source={},
                meta={"catalogue_sha256": "x", "interpreter": {}},
            )
            hybrid = record["recommendation"]["recipe_id"] if record["recommendation"] else None
            return {"A": fixed, "B": deterministic, "C": hybrid, "record": record}
    finally:
        if original is not None:
            kernel.model_provider_ready = original


def judge(task, recommended):
    if recommended is None:
        return "correct_abstention" if task["abstain"] else "missed"
    return "correct" if recommended in task["suitable"] else "unsupported"


def evaluate_all(client, interpret_for):
    tally = {
        s: {"correct": 0, "correct_abstention": 0, "missed": 0, "unsupported": 0} for s in "ABC"
    }
    rows = {}
    for item in TASKS:
        outcome = call(client, run_task, item, interpret_for(item))
        rows[item["id"]] = outcome
        for strategy in "ABC":
            tally[strategy][judge(item, outcome[strategy])] += 1
    return tally, rows


def test_the_faithful_scripted_model_is_better_than_fixed_and_deterministic_on_these_labels(ready):
    client = ready[0]
    tally, rows = evaluate_all(client, lambda item: item["scripted"])
    total = len(TASKS)
    appropriate = {s: tally[s]["correct"] + tally[s]["correct_abstention"] for s in "ABC"}
    print("\nSCRIPTED hybrid / deterministic / fixed:", json.dumps(tally))
    assert appropriate["C"] == total, (tally["C"], {k: v["C"] for k, v in rows.items()})
    # The deterministic selector cannot choose without an explicit intent, and it cannot tell a
    # request to list files from a request to review them.
    assert tally["B"]["missed"] >= 2 and tally["B"]["unsupported"] >= 1
    assert appropriate["B"] < appropriate["C"]
    assert tally["A"]["unsupported"] >= 5 and appropriate["A"] < appropriate["C"]
    # Eligibility is authoritative: with the provider down the hybrid does not recommend the model.
    assert rows["model-unavailable"]["C"] == INSPECTION
    reasons = {
        p["recipe_id"]: p["reasons"] for p in rows["model-unavailable"]["record"]["unavailable"]
    }
    assert reasons[ANALYSIS] and "deployment_policy_conflict" in reasons[ANALYSIS]


@pytest.mark.parametrize(
    "control,why",
    [
        (always_analysis, "recommends the same workflow whatever is asked"),
        (invents_a_recipe, "names a procedure that does not exist"),
        (replaces_the_goal, "quietly substitutes a different task"),
    ],
    ids=["always_analysis", "invented_recipe", "goal_replaced"],
)
def test_negative_controls_do_not_qualify(ready, control, why):
    """A fake 'intelligence' must score worse than the faithful model on the same labels."""
    client = ready[0]
    good, _ = evaluate_all(client, lambda item: item["scripted"])
    bad, rows = evaluate_all(client, lambda item: control)
    score = lambda t: t["C"]["correct"] + t["C"]["correct_abstention"]  # noqa: E731
    assert score(bad) < score(good), (why, bad["C"])
    if control is invents_a_recipe:
        assert bad["C"]["unsupported"] == 0, "an invented recipe is rejected, never recommended"
        assert all(r["record"]["recommendation"] is None for r in rows.values())
    if control is replaces_the_goal:
        assert all(r["record"]["status"] == "rejected_interpretation" for r in rows.values())
    if control is always_analysis:
        assert bad["C"]["unsupported"] >= 2, "relevance errors survive eligibility: measured"


def test_ablation_costs_are_measured_exactly_and_quality_is_not_claimed(ready):
    """Request size per context condition. Which condition interprets best needs a live model."""
    client = ready[0]
    recipes = getattr(client.app.state.kernel, "bespoke_recipes", None) or load_catalogue()
    rows = intent_context.project_catalogue(recipes)
    goal = TASKS[2]["goal"]
    files = [{"path": p, "bytes": 100} for p in TASKS[2]["files"]]
    source = {
        "type": "repository",
        "label": "Owner repository",
        "classification": "x",
        "inventory": files,
    }
    conditions = {
        "goal_only": {"user_goal": goal, "source": {**source, "inventory": []}, "catalogue": []},
        "goal_and_context": {"user_goal": goal, "source": source, "catalogue": []},
        "goal_and_catalogue": {
            "user_goal": goal,
            "source": {**source, "inventory": []},
            "catalogue": rows,
        },
        "full": {"user_goal": goal, "source": source, "catalogue": rows},
    }
    sizes = {k: intent_context.request_bytes(v, 1536) for k, v in conditions.items()}
    print("\nREQUEST BYTES", json.dumps(sizes))
    assert sizes["goal_only"] < sizes["goal_and_context"] < sizes["full"]
    assert sizes["goal_only"] < sizes["goal_and_catalogue"] < sizes["full"]
    assert max(sizes.values()) <= 18000, "every condition fits the default Governor request ceiling"
