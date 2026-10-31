"""BESPOKE behavioral mutations using the existing isolated PI-03A mutation runner.

These are implementation-authored receipts. Independent review must add its own mutations.
No syntax, collection, setup or unrelated failures count as a behavioral kill.
"""

from scripts import capability_mutations as campaign

SEL = "alive/bespoke/selector.py"
CTX = "alive/bespoke/context.py"
HAND = "alive/bespoke/handoff.py"
STORE = "alive/bespoke/store.py"
TEST = "tests/test_bespoke.py::"

campaign.CASES = [
    (
        "B12",
        "model workflow needs configured provider",
        SEL,
        "or not await kernel.model_provider_ready()",
        "or False",
        TEST + "test_model_workflow_without_configured_provider_is_ineligible",
    ),
    (
        "B1",
        "request cannot substitute a goal",
        CTX,
        "grant.goal_id == request.goal_ref",
        "True",
        TEST + "test_context_substitution_is_refused[goal_ref]",
    ),
    (
        "B2",
        "permissions gate",
        SEL,
        "if not set(limits.permissions) <= set(ceiling.permissions):",
        "if False:",
        TEST + "test_abstention_has_typed_reasons[permissions-permission_not_grantable]",
    ),
    (
        "B3",
        "request wall ceiling",
        SEL,
        "or limits.max_wall_seconds > ceiling.max_wall_seconds",
        "or False",
        TEST + "test_abstention_has_typed_reasons[budget-resource_limit_exceeded]",
    ),
    (
        "B4",
        "exact workflow pin",
        SEL,
        'reasons.append("workflow_identity_changed")',
        "pass",
        TEST + "test_recipe_exact_pins_are_mandatory[workflow]",
    ),
    (
        "B5",
        "exact capability pins at both checks (compound)",
        [SEL, SEL],
        [
            'reasons.append("capability_identity_changed")\n        except KeyError:',
            'reasons.append("capability_identity_changed")\n                effective =',
        ],
        ["pass\n        except KeyError:", "pass\n                effective ="],
        TEST + "test_recipe_exact_pins_are_mandatory[capability]",
    ),
    (
        "B6",
        "future status remains unavailable",
        SEL,
        'if recipe.status != "active":',
        "if False:",
        TEST + "test_future_recipe_with_real_dependencies_still_cannot_be_selected",
    ),
    (
        "B7",
        "suitability sorting is descending",
        SEL,
        "-c.suitability",
        "c.suitability",
        TEST + "test_suitability_precedes_lexical_tie_break",
    ),
    (
        "B8",
        "retained record digest",
        STORE,
        'require(digest(row.selection) == row.selection_sha256, "recommendation_integrity")',
        'require(True, "recommendation_integrity")',
        TEST + "test_record_tampering_and_orm_mutations_are_refused",
    ),
    (
        "B9",
        "removed recipe cannot hand off",
        HAND,
        "(r for r in catalogue if recipe_hash(r) == retained.recipe_sha256), None",
        "(r for r in catalogue if recipe_hash(r) == retained.recipe_sha256), retained.recipe",
        TEST + "test_changed_selection_cannot_be_handed_off[recipe]",
    ),
    (
        "B10",
        "handoff budget cannot widen",
        HAND,
        "and grant.wall_seconds <= limits.max_wall_seconds",
        "and True",
        TEST + "test_changed_selection_cannot_be_handed_off[budget]",
    ),
    (
        "B11",
        "policy identity cannot upgrade",
        HAND,
        'require(selected.policy_sha256 == digest(POLICY), "selection_policy_changed")',
        'require(True, "selection_policy_changed")',
        TEST + "test_changed_selection_policy_is_not_silently_used_for_handoff",
    ),
]


if __name__ == "__main__":
    campaign.main()
