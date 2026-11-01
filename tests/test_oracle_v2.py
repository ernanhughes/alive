"""Oracle v2 measures observable behaviour. Fixtures here are tiny, author-owned and offline."""

import json
from pathlib import Path

import pytest

from alive.adaptation import oracle, oracle_v2
from alive.adaptation.oracle_v2 import grade
from alive.workflows.context import Refused, digest


def fixture(code, reference, cases, **extra):
    return {
        "id": "t",
        "family": "errors",
        "split": "heldout",
        "contract": "x",
        "code": code,
        "reference": reference,
        "cases": [
            {"id": f"c{i}", "input": value, "expected": expected}
            for i, (value, expected) in enumerate(cases, 1)
        ],
    } | extra


def answer(task, observed, required=None, issue=None):
    """A structured model answer; ``observed``/``required`` are JSON text per case."""
    required = required or observed
    ids = [c["id"] for c in task["cases"]]
    return {
        "answer": "prose",
        "predictions": [
            {"case_id": i, "observed": o, "required": r}
            for i, o, r in zip(ids, observed, required, strict=True)
        ],
        "issue_present": issue,
    }


POP = "def solve(p):\n    return p.pop()\n"
PEEK = "def solve(p):\n    return p[-1]\n"


def test_return_only_check_misses_what_v2_sees():
    # The AI-FIRST-03 errors-4 defect: the return value is right, the input is destroyed.
    task = fixture(POP, PEEK, [([1], {"value": 1})])
    v1 = oracle.grade(
        {"code": POP, "reference": PEEK, "cases": [{"id": "c1", "input": [1]}]},
        {
            "predictions": [{"case_id": "c1", "observed": "1", "required": "1"}],
            "issue_present": False,
        },
    )
    assert v1["issue_present"] is False  # v1 cannot see mutation
    graded = grade(task, answer(task, ["1"], issue=True))
    assert graded["issue_present"] is True
    assert graded["cases"][0]["return_conforms"] and not graded["cases"][0]["state_conforms"]
    assert graded["cases"][0]["state_changed"] and graded["end_to_end"]
    # A model that predicts the return correctly but misses the side effect is wrong, not unscored.
    missed = grade(task, answer(task, ["1"], issue=False))
    assert missed["issue_flag"] == "incorrect" and missed["dimensions"]["semantic"] == "incorrect"


def test_nested_mutation_and_pure_function():
    nested = "def solve(p):\n    p['a']['b'].append(1)\n    return len(p['a']['b'])\n"
    pure = "def solve(p):\n    return len(p['a']['b']) + 1\n"
    task = fixture(nested, pure, [({"a": {"b": []}}, {"value": 1})])
    assert grade(task, answer(task, ["1"], issue=True))["issue_present"] is True
    clean = fixture(pure, pure, [({"a": {"b": []}}, {"value": 1})])
    result = grade(clean, answer(clean, ["1"], issue=False))
    assert result["issue_present"] is False and result["end_to_end"]


def test_correct_return_incorrect_side_effect_and_inverse():
    sort_in_place = "def solve(p):\n    p.sort()\n    return p[0]\n"
    pure_min = "def solve(p):\n    return min(p)\n"
    state_bug = fixture(sort_in_place, pure_min, [([3, 1], {"value": 1})])
    seen = grade(state_bug, answer(state_bug, ["1"], issue=True))
    assert seen["cases"][0]["return_conforms"] and not seen["cases"][0]["state_conforms"]
    wrong_return = "def solve(p):\n    return max(p)\n"
    value_bug = fixture(wrong_return, pure_min, [([3, 1], {"value": 1})])
    seen = grade(value_bug, answer(value_bug, ["3"], ["1"], issue=True))
    assert not seen["cases"][0]["return_conforms"] and seen["cases"][0]["state_conforms"]
    assert seen["end_to_end"]


def test_required_mutation_is_a_contract_not_a_defect():
    in_place = "def solve(p):\n    p.append(0)\n"
    task = fixture(
        in_place,
        in_place,
        [([1], {"value": None, "input_after": [1, 0]})],
        input_state="per_case",
    )
    result = grade(task, answer(task, ["null"], issue=False))
    assert result["issue_present"] is False and result["end_to_end"]
    # The same behaviour violates a contract that forbids mutation.
    forbidden = fixture(in_place, "def solve(p):\n    return None\n", [([1], {"value": None})])
    assert grade(forbidden, answer(forbidden, ["null"], issue=True))["issue_present"] is True


def test_exceptions_and_error_names():
    raiser = "def solve(p):\n    return p[5]\n"
    task = fixture(raiser, raiser, [([1], {"error": "IndexError"})])
    assert grade(task, answer(task, ["ERROR:IndexError"], issue=False))["end_to_end"]
    wrong = grade(task, answer(task, ["ERROR:KeyError"], ["ERROR:IndexError"], issue=False))
    assert wrong["cases"][0]["observed_prediction"] == "incorrect"
    assert wrong["dimensions"]["semantic"] == "incorrect"


def test_bool_is_not_a_number_and_int_equals_float():
    one = "def solve(p):\n    return 1\n"
    task = fixture(one, one, [(0, {"value": 1})])
    assert grade(task, answer(task, ["1.0"], issue=False))["end_to_end"]
    boolean = grade(task, answer(task, ["true"], ["1"], issue=False))
    assert boolean["cases"][0]["observed_prediction"] == "incorrect"
    truthy = "def solve(p):\n    return [True]\n"
    nested = fixture(truthy, truthy, [(0, {"value": [True]})])
    seen = grade(nested, answer(nested, ["[1]"], ["[true]"], issue=False))
    assert seen["cases"][0]["observed_prediction"] == "incorrect"


def test_json_null_is_a_value_and_missing_is_not():
    none = "def solve(p):\n    return None\n"
    task = fixture(none, none, [([], {"value": None})])
    assert grade(task, answer(task, ["null"], issue=False))["end_to_end"]
    assert not oracle_v2.same({"value": None}, {"error": "X"})
    missing = grade(task, {"answer": "prose", "issue_present": False})
    assert missing["cases"][0]["observed_prediction"] == "missing"
    assert missing["dimensions"]["semantic"] == "undetermined"
    assert missing["dimensions"]["contract_compliance"]["missing_cases"] == ["c1"]
    malformed = grade(task, answer(task, ["None"], ["None"], issue=False))
    assert malformed["cases"][0]["observed_prediction"] == "malformed"
    assert not malformed["end_to_end"]


def test_float_tolerance_is_declared_by_the_contract():
    third = "def solve(p):\n    return 1 / 3\n"
    exact = fixture(third, third, [(0, {"value": 1 / 3})])
    assert not grade(exact, answer(exact, ["0.333"], ["0.333"], issue=False))["end_to_end"]
    loose = fixture(third, third, [(0, {"value": 1 / 3})], tolerance=0.001)
    assert grade(loose, answer(loose, ["0.333"], ["0.333"], issue=False))["end_to_end"]
    nan = "def solve(p):\n    return float('nan')\n"
    seen = oracle_v2.execute(nan, [{"id": "c1", "input": 0}])[0]
    assert seen["value"] == {"$nonfinite": "nan"}


def test_structural_failure_is_not_semantic_failure():
    task = fixture(PEEK, PEEK, [([1], {"value": 1})])
    prose_only = grade(task, {"answer": "No defect.", "predictions": []})
    assert prose_only["dimensions"]["semantic"] == "undetermined"
    assert not prose_only["dimensions"]["contract_compliance"]["ok"]
    assert not prose_only["end_to_end"] and prose_only["dimensions"]["task_completion"]
    absent = grade(task, None, run_failure="output_truncated")
    assert absent["dimensions"]["semantic"] == "undetermined"
    assert absent["dimensions"]["run_failure"] == "output_truncated"
    wrong = grade(task, answer(task, ["2"], ["1"], issue=False))
    assert wrong["dimensions"]["semantic"] == "incorrect"
    invalid = grade(task, answer(task, ["1"], issue=False), reference_valid=False)
    assert invalid["dimensions"]["semantic"] == "correct" and not invalid["end_to_end"]


def test_duplicate_predictions_and_missing_flag_fail_compliance_only():
    task = fixture(PEEK, PEEK, [([1], {"value": 1})])
    doubled = answer(task, ["1"], issue=False)
    doubled["predictions"].append(doubled["predictions"][0])
    assert grade(task, doubled)["dimensions"]["contract_compliance"]["duplicate_cases"] == ["c1"]
    unflagged = grade(task, answer(task, ["1"], issue=None))
    assert unflagged["dimensions"]["contract_compliance"]["issue_flag"] is False
    assert unflagged["dimensions"]["semantic"] == "undetermined"


def test_multi_file_fixture_and_reference_self_check():
    helper = {"helpers.py": "def twice(x):\n    return x * 2\n"}
    code = "from helpers import twice\n\ndef solve(p):\n    return twice(p) + 1\n"
    task = fixture(code, code, [(2, {"value": 5})], files=helper)
    assert grade(task, answer(task, ["5"], issue=False))["end_to_end"]
    assert set(oracle_v2.source_files(task)) == {"README.md", "implementation.py", "helpers.py"}
    assert "expected" not in oracle_v2.source_files(task)["README.md"]
    broken = fixture(PEEK, PEEK, [([1], {"value": 99})])
    with pytest.raises(Refused, match="fixture_reference_disagrees_with_expectation"):
        grade(broken, answer(broken, ["1"], issue=False))
    assert grade(broken, answer(broken, ["1"], issue=False), check_reference=False)


def test_v1_evidence_is_immutable():
    # Oracle v1, its corpus and its lock are the AI-FIRST-03 measurement instrument.
    data, lock = oracle.frozen_corpus()
    assert lock["corpus_sha256"] == digest(data)
    assert lock["oracle_sha256"] == (
        "7b58b1746d3d28f857adc5a80408d65a779268bf90aad04c246f9ccbd8ee4b4c"
    )
    assert data["schema"] == "adaptation-corpus/v1"
    ledger_path = Path(oracle.CORPUS).parent / "evidence/adaptation-live-ledger.json"
    ledger = json.loads(ledger_path.read_text("utf-8"))
    assert ledger["corpus_lock"] == lock
    scores = [(e["task_id"], e["arm"], e["grade"]["score"]) for e in ledger["evaluation"]]
    assert ("errors-4", "A", 0.8) in scores
