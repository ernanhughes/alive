"""Scoring regressions use varied recorded outcomes, not an always-abstain fixture."""

import sys

import pytest

from scripts import notebook02_evaluation as runner


def records():
    return [
        {
            "case_id": k,
            "outputs": {
                "A": {"abstained": False, "data": {"status": "candidate"}},
                "B": {"outcome": "abstain"},
                "D": {"outcome": "abstain"},
            },
            "latency_ms": {"A": 1.0, "B": 2.0},
        }
        for k in ("001", "003")  # frozen useful / negative labels
    ]


def test_retention_and_false_abstention_change_with_actual_decisions():
    before = runner.score(records())
    changed = records()
    changed[0]["outputs"]["B"]["outcome"] = "candidate_connection"
    after = runner.score(changed)
    assert before["A"]["useful_candidate_recall"] == 1.0
    assert before["A"]["unsupported_candidate_rate"] == 0.5
    assert before["B"]["useful_candidate_recall"] == 0.0
    assert before["B"]["false_abstention"] == 1
    assert after["B"]["useful_candidate_recall"] == 1.0
    assert after["B"]["useful_candidates_lost"] == 0
    assert after["B"]["false_abstention"] == 0
    assert after["B"]["correct_abstention"] == 1


@pytest.mark.parametrize("index", [0, 1])
def test_integrity_rejection_is_separate_from_abstention(index):
    rows = records()
    rows[index]["outputs"]["B"]["outcome"] = "qualified_non_use"
    result = runner.score(rows)["B"]
    assert result["integrity_rejection"] == 1
    assert result["useful_integrity_rejection"] == (index == 0)
    assert result["negative_integrity_rejection"] == (index == 1)
    assert result["false_abstention"] == (index == 1)
    assert result["correct_abstention"] == (index == 0)
    assert result["useful_candidates_lost"] == 1


def test_unsupported_rate_and_unknown_outcome_are_not_silently_accepted():
    rows = records()
    rows[1]["outputs"]["B"]["outcome"] = "candidate_connection"
    result = runner.score(rows)["B"]
    assert result["unsupported_candidate_rate"] == 1.0
    assert result["negative_candidate_rate"] == 1.0
    rows[1]["outputs"]["B"]["outcome"] = "unknown_action"
    with pytest.raises(ValueError, match="Unrecognized"):
        runner.score(rows)


def test_historical_derivation_preserves_original_and_records_provenance():
    path = runner.ROOT / "docs/validation/alive-notebook-02/evaluation.json"
    original = path.read_bytes()
    report = runner.derive_historical(path, runner.verify_freeze())
    assert path.read_bytes() == original
    assert report["derived_from"]["sha256_lf_normalized"] == runner.sha(original)
    assert report["metrics"]["heldout"]["A"]["useful_candidate_recall"] == 1.0
    assert report["metrics"]["heldout"]["B"]["useful_candidate_recall"] == 0.0
    assert report["metrics"]["heldout"]["B"]["false_abstention"] == 5
    assert report["metrics"]["heldout"]["B"]["integrity_rejection"] == 1


def test_portable_output_names_and_archive_overwrite_guard(tmp_path, monkeypatch):
    external = tmp_path / "result.json"
    assert runner.portable_path(external) == "external-output/result.json"
    original = runner.ROOT / "docs/validation/alive-notebook-02/evaluation.json"
    before = original.read_bytes()
    monkeypatch.setattr(sys, "argv", ["runner", "--output", str(original)])
    with pytest.raises(ValueError, match="Original Notebook-02 evidence is preserved"):
        runner.main()
    assert original.read_bytes() == before
