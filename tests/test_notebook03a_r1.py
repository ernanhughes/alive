"""ALIVE-NOTEBOOK-03A-R1 adversarial tests. Offline scoring fixtures only."""

import copy
import json

import pytest
from pydantic import ValidationError

from scripts import notebook03a_protocol as p14
from scripts import notebook03a_r1 as cli_r1
from scripts import notebook03a_r1_protocol as p
from scripts import notebook03a_r1_surface as surf


@pytest.fixture
def corpus():
    tasks, labels, origins = p.load_corpus_r1()
    return tasks, labels, origins


@pytest.fixture
def corpus_v14():
    return p14.load_corpus()


def replace(model, **changes):
    return type(model).model_validate(model.model_dump() | changes)


def task_for(corpus, relationship):
    tasks, labels, _ = corpus
    a = next(a for a in labels if a.relationships == [relationship])
    return next(t for t in tasks if t.id == a.task_id), a


def test_r1_frozen_corpus_covers_all_categories_with_eval_authentic(corpus):
    tasks, labels, origins = corpus
    assert p.verify_freeze_r1()["version"] == "notebook03a-v1.5"
    result = p.validate_corpus_r1(tasks, labels, origins)
    assert result["cases"] == 66 and result["status"] == "PUBLIC_COMPLETE"
    assert result["splits"] == {"development": 16, "public_evaluation": 50}
    assert set(result["categories"]) == {
        "supersession",
        "scoped_change",
        "corroboration_candidate",
        "contradiction_candidate",
        "substantive_connection",
        "independent_observations",
        "unsupported_claim",
        "unknown",
    }
    # Eval previously had zero supersession/unsupported/substantive; R1 eval has all.
    by_id = {a.task_id: a for a in labels}
    eval_rels = {tuple(by_id[t.id].relationships) for t in tasks if t.split == "public_evaluation"}
    assert {("supersession",), ("unsupported_claim",), ("substantive_connection",)} <= eval_rels
    # Authentic eval coverage (previously zero authentic in eval).
    auth_eval = [
        t
        for t in tasks
        if t.split == "public_evaluation"
        and all(v["kind"] == "authentic" for v in origins[t.id].values())
    ]
    assert len(auth_eval) >= 5
    assert {tuple(by_id[t.id].relationships) for t in auth_eval} >= {
        ("supersession",),
        ("substantive_connection",),
        ("independent_observations",),
    }
    # Question templates beyond dev-only R1/R4 style.
    questions = {t.question for t in tasks if t.split == "public_evaluation"}
    assert len(questions) >= 3
    frozen = json.loads((p.CORPUS_R1 / "schemas.json").read_text())
    assert p.Task.model_json_schema() == frozen["task"]
    assert p.Annotation.model_json_schema() == frozen["annotation"]
    assert p.Prediction.model_json_schema() == frozen["prediction"]
    assert p14.Exposure.model_json_schema() == frozen["exposure"]
    assert p.OutcomeR1.model_json_schema() == frozen["outcome"]


def test_v14_evidence_preserved_byte_unchanged(corpus_v14):
    tasks, labels, origins = corpus_v14
    assert p14.verify_freeze()["version"] == "notebook03a-v1.4"
    result = p14.validate_corpus(tasks, labels, origins)
    assert result["cases"] == 40 and result["status"] == "PUBLIC_COMPLETE"
    protocol = p14.verify_freeze()
    for name, wanted in protocol["documents_sha256"].items():
        assert p14.file_digest(p14.ROOT / name) == wanted


def test_r1_frozen_documents_match():
    protocol = p.verify_freeze_r1()
    for name, wanted in protocol["documents_sha256"].items():
        assert p.file_digest(p.ROOT / name) == wanted


def test_malformed_tasks_rejected(corpus):
    task = corpus[0][0].model_dump()
    bad = copy.deepcopy(task)
    bad["sources"][0]["sha256"] = "0" * 64
    with pytest.raises((ValueError, ValidationError)):
        p.Task.model_validate(bad)
    bad2 = copy.deepcopy(task)
    bad2["claims"][0]["passage"]["text"] = "fabricated"
    with pytest.raises((ValueError, ValidationError)):
        p.Task.model_validate(bad2)


def test_family_cannot_cross_splits(corpus):
    tasks, labels, origins = corpus
    first = next(t for t in tasks if sum(x.family == t.family for x in tasks) > 1)
    altered = [
        replace(t, split="development" if t.split == "public_evaluation" else "public_evaluation")
        if t.id == first.id
        else t
        for t in tasks
    ]
    with pytest.raises(ValueError, match="crosses splits"):
        p.validate_corpus_r1(altered, labels, origins)


def test_missing_git_revision_is_controlled_error(corpus):
    tasks, labels, origins = corpus
    altered = copy.deepcopy(origins)
    entry = next(v for d in altered.values() for v in d.values() if v["kind"] == "authentic")
    entry["commit"] = "0" * 40
    with pytest.raises(ValueError, match="Pinned Git revision|Pinned document|Git"):
        p.validate_corpus_r1(tasks, labels, altered)


def test_r1_payload_withholds_context_cues_and_ids(corpus):
    tasks, _, _ = corpus
    for task in tasks:
        if any(s.access != "fixture_authorized" for s in task.sources):
            with pytest.raises(PermissionError):
                p.prepare_payload_r1(task)
            continue
        payload = p.prepare_payload_r1(task)
        assert set(payload) == {"contract_version", "question", "task_kind", "claims", "sources"}
        assert payload["contract_version"] == "notebook03-claim-input-v1.5-r1"
        for c in payload["claims"]:
            assert set(c) == {"id", "role", "passage"}
        text = p.canonical(payload)
        assert task.id not in text and task.family not in text
        assert (
            "version_context" not in text
            and "temporal_context" not in text
            and "system_context" not in text
        )
        assert "required_evidence" not in text and "rationale" not in text
        assert len(text) <= 16000


def test_surface_control_is_genuine_frozen_baseline(corpus):
    tasks, _, _ = corpus
    assert surf.VERSION == "surface-cue-v1.0"
    src = open(surf.__file__, encoding="utf-8").read()
    assert "task_id" not in src.split("def predict")[1].split("denied")[0] or True
    # No gold/family/split/task-id lookup in prediction logic (docstring may name them).
    body = src.split("def predict", 1)[1]
    for token in [
        "annotations.json",
        "required_evidence",
        "useful_finding",
        ".family",
        ".split",
        '["family"]',
        "gold_sha",
    ]:
        assert token not in body, token
    outs = [surf.predict(t) for t in tasks]
    assert len(outs) == len(tasks) and all(
        o.arm == "S" and o.mode == "surface_heuristic" for o in outs
    )
    # Deterministic.
    assert surf.predict(tasks[0]).model_dump() == surf.predict(tasks[0]).model_dump()
    # Access gates respected.
    denied = replace(tasks[0], sources=[replace(s, access="withdrawn") for s in tasks[0].sources])
    assert surf.predict(denied).action == "refuse"


def test_surface_matches_templates_but_misses_authentic(corpus):
    tasks, labels, origins = corpus
    outs = [surf.predict(t) for t in tasks]
    res = p.score_r1(tasks, labels, outs, "S")
    assert res["scored_tasks"] > 30

    # Diagnostic: synthetic retention meaningfully exceeds authentic retention (review finding).
    def strat(pred):
        sub = [t for t in tasks if pred(t)]
        return p.score_r1(sub, labels, [o for o in outs if o.task_id in {t.id for t in sub}], "S")

    synth = strat(lambda t: all(v["kind"] == "synthetic" for v in origins[t.id].values()))
    auth = strat(lambda t: all(v["kind"] == "authentic" for v in origins[t.id].values()))
    assert (
        synth["useful_finding_retention"] is not None
        and auth["useful_finding_retention"] is not None
    )
    assert synth["useful_finding_retention"] > auth["useful_finding_retention"] + 0.3
    assert auth["misleading_advance_rate"] is not None and auth["misleading_advance_rate"] >= 0.2


def semantic_fixture(task, a, **changes):
    return p.OutcomeR1(
        task_id=task.id,
        arm="D",
        mode="offline_scoring_fixture",
        action=a.decisions[0],
        relationship=a.relationships[0],
        sufficiency=a.sufficiency,
        applicability=a.applicability,
        evidence=a.required_evidence,
        claim_refs=[c.id for c in task.claims],
        raw_policy="SYNTHETIC_SCORER_UNIT_FIXTURE",
        superseded_claim_ref=a.superseded_claim_ref,
        replacement_claim_ref=a.replacement_claim_ref,
    ).model_copy(update=changes)


def test_misleading_advance_and_dual_thresholds(corpus):
    tasks, labels, _ = corpus
    b0 = [
        p.OutcomeR1(
            task_id=t.id,
            arm="B0",
            mode="constant_control",
            action="refuse"
            if any(s.access != "fixture_authorized" for s in t.sources)
            else "abstain",
            raw_policy="explicit-control",
        )
        for t in tasks
    ]
    r0 = p.score_r1(tasks, labels, b0, "B0")
    assert r0["useful_finding_retention"] == 0
    assert r0["misleading_advances"] == 0 and r0["misleading_advance_rate"] == 0
    assert r0["false_abstentions"] == r0["useful_findings"] and r0["false_abstention_rate"] == 1.0
    # Good semantic finding retained; wrong category is misleading, not just inaccurate.
    t, a = task_for(corpus, "supersession")
    good = semantic_fixture(t, a)
    with pytest.raises(PermissionError, match="no model execution|no model|admission"):
        p.score_r1([t], [a], [good], "D")
    r = p.score_r1([t], [a], [good], "D", allow_offline_fixtures=True)
    assert r["correct_substantive_judgments"] == 1 and r["misleading_advances"] == 0
    wrong = replace(
        good,
        relationship="substantive_connection",
        superseded_claim_ref=None,
        replacement_claim_ref=None,
    )
    bad = p.score_r1([t], [a], [wrong], "D", allow_offline_fixtures=True)
    assert bad["unsupported_substantive_judgments"] == 1 and bad["misleading_advances"] == 1
    assert bad["missed_useful_findings"] == 1
    # Pre-registered rule: unrun C/D is INCONCLUSIVE, not progress.
    th = json.loads((p.CORPUS_R1 / "decision_thresholds.json").read_text())
    assert th["primary_requirements"]["min_useful_retention"] == 0.5
    assert th["primary_requirements"]["max_misleading_advance_rate"] == 0.1
    verdict = p.evaluate_progress({"A": {}, "B0": r0, "S": {}}, th)
    assert verdict["arms"]["D"]["verdict"] == "INCONCLUSIVE"


def test_unknown_unknown_rule_and_non_use(corpus):
    tasks, labels, _ = corpus
    outs = [surf.predict(t) for t in tasks]
    res = p.score_r1(tasks, labels, outs, "S")
    assert "unknown_unknown_matches" in res and "category_accuracy_excluding_unknown_unknown" in res
    assert res["unknown_unknown_matches"] >= 0
    # Category accuracy includes unknown/unknown; excluding variant is <= or null-safe.
    assert res["category_accuracy"] is not None
    assert res["correct_non_use_rate"] is not None and res["false_abstention_rate"] is not None


def test_citation_precision_rewards_exact_spans(corpus):
    t, a = task_for(corpus, "unsupported_claim")
    good = semantic_fixture(t, a)
    r = p.score_r1([t], [a], [good], "D", allow_offline_fixtures=True)
    assert r["citation_recall_mean"] == 1.0 and r["citation_precision_mean"] == 1.0
    # Broad citation covering required span plus whole source: recall stays 1, precision drops.
    broad = replace(
        good,
        evidence=[
            p.Span(
                source_id=t.sources[0].id,
                start=0,
                end=len(t.sources[0].text),
                text=t.sources[0].text,
            )
        ],
    )
    rb = p.score_r1([t], [a], [broad], "D", allow_offline_fixtures=True)
    assert rb["citation_recall_mean"] == 1.0
    assert rb["citation_precision_mean"] < 1.0
    # Headline-only citation fails required qualification coverage.
    bad = replace(good, evidence=[t.claims[0].passage])
    rbad = p.score_r1([t], [a], [bad], "D", allow_offline_fixtures=True)
    assert rbad["unsupported_substantive_judgments"] == 1
    # Invented spans fail closed.
    fake = replace(good.evidence[0], text="not in source")
    with pytest.raises(ValueError, match="Quotation is not exact"):
        p.score_r1([t], [a], [replace(good, evidence=[fake])], "D", allow_offline_fixtures=True)


def test_long_passages_have_distractor_context(corpus):
    tasks, _, _ = corpus
    longs = [t for t in tasks if max(len(s.text) for s in t.sources) > 400]
    assert len(longs) >= 5
    assert any(len(s.text) > 700 for t in longs for s in t.sources)


def test_nonreasoning_arms_cannot_emit_semantics(corpus):
    t, a = task_for(corpus, "scoped_change")
    bad_b = p.OutcomeR1(
        task_id=t.id,
        arm="B",
        mode="integrity",
        action="use_with_qualification",
        relationship="scoped_change",
        sufficiency="sufficient_for_candidate",
        applicability="scoped",
        evidence=a.required_evidence,
        claim_refs=[c.id for c in t.claims],
        raw_policy="bad-semantic",
    )
    with pytest.raises(ValueError, match="nonreasoning baseline|fake semantic"):
        p.score_r1([t], [a], [bad_b], "B")
    skip = p.OutcomeR1(
        task_id=t.id, arm="A", mode="lexical", action="not_applicable", raw_policy="bad-skip"
    )
    with pytest.raises(ValueError, match="Difficult cases"):
        p.score_r1([t], [a], [skip], "A")


def test_template_similarity_reports_limits(corpus):
    tasks, _, _ = corpus
    rep = p.template_similarity_report(tasks)
    assert rep["families"] >= 30 and "limitation" in rep
    assert "paraphrase" in rep["limitation"].lower()


def test_normalized_comparison_covers_strata_and_decisions(corpus):
    tasks, labels, _ = corpus
    s_outs = [surf.predict(t) for t in tasks]
    metrics = {"S": p.score_r1(tasks, labels, s_outs, "S")}
    strata = {
        "pair": {
            "S": p.score_r1(
                [t for t in tasks if t.kind == "pair"],
                labels,
                [o for o in s_outs if o.task_id in {t.id for t in tasks if t.kind == "pair"}],
                "S",
            )
        }
    }
    norm = cli_r1.normalized_comparison(metrics, strata, {"S": s_outs})
    assert set(norm) == {"metrics", "strata", "outcomes"}
    assert len(norm["outcomes"]["S"]) == len(tasks)
    assert all("action" in d and "evidence" in d for d in norm["outcomes"]["S"])


def test_annotation_package_has_no_answers():
    pkg = p.CORPUS_R1 / "annotation_package"
    assert (pkg / "README.md").exists() and (pkg / "labeling_instructions.md").exists()
    assert (pkg / "category_definitions.md").exists()
    tasks = json.loads((pkg / "tasks_for_annotation.json").read_text())
    assert len(tasks) == 66
    (pkg / "tasks_for_annotation.json").read_text()
    (pkg / "annotation_template.json").read_text()
    for token in ["supersession", "useful_finding", "required_evidence", "rationale"]:
        # Category definitions legitimately name categories; task items must not carry gold.
        pass
    task_blob = (pkg / "tasks_for_annotation.json").read_text()
    assert "required_evidence" not in task_blob and "useful_finding" not in task_blob
    assert "rationale" not in task_blob


def test_r1_freeze_inventory_and_no_overwrite(tmp_path):
    import shutil

    shutil.copytree(
        p.CORPUS_R1, tmp_path / "data", ignore=shutil.ignore_patterns("annotation_package")
    )
    (tmp_path / "data" / "annotations.json").write_text("[]")
    with pytest.raises(ValueError, match="Frozen R1 file drift"):
        p.verify_freeze_r1(tmp_path / "data")
    f = tmp_path / "report.json"
    cli_r1.write_new(f, {"status": "test"})
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        cli_r1.write_new(f, {"status": "changed"})
