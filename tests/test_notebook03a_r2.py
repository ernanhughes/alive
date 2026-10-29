"""ALIVE-NOTEBOOK-03A-R2 regression tests. Fixtures are offline only, never model results."""

import copy
import json
import sys

import pytest

from scripts import notebook03a_protocol as p14
from scripts import notebook03a_r1_protocol as p15
from scripts import notebook03a_r2 as cli_r2
from scripts import notebook03a_r2_protocol as p
from scripts import notebook03a_r2_shortcut as v2


@pytest.fixture
def corpus():
    tasks, labels, origins = p.load_corpus_r2()
    return tasks, labels, origins


@pytest.fixture
def contract():
    return p.load_threshold_contract(p.CORPUS_R2 / "decision_thresholds.json")


@pytest.fixture
def corpus_v14():
    return p14.load_corpus()


@pytest.fixture
def corpus_v15():
    return p15.load_corpus_r1()


def passing_d_metrics(**over):
    base = {
        "scored_tasks": 40,
        "useful_findings": 25,
        "gated_useful_finding_retention": 0.70,
        "gated_misleading_advance_rate": 0.02,
        "citation_gate": {"pass_rate": 1.0},
    }
    base.update(over)
    return base


def blind_ready_context(**over):
    ctx = {
        "scope": "blind",
        "holdout_available": True,
        "gold_adjudicated": True,
        "exposure_events": [],
        "n_families": 39,
        "freeze_ok": True,
    }
    ctx.update(over)
    return ctx


def full_metrics(**arms):
    out = {
        "A": {"scored_tasks": 50},
        "B0": {"scored_tasks": 64},
        "S": {
            "scored_tasks": 64,
            "gated_useful_finding_retention": 0.45,
            "gated_misleading_advance_rate": 0.20,
        },
        "C": {
            "scored_tasks": 40,
            "useful_findings": 25,
            "gated_useful_finding_retention": 0.56,
            "gated_misleading_advance_rate": 0.08,
            "citation_gate": {"pass_rate": 1.0},
        },
    }
    out.update(arms)
    return out


def test_r2_freeze_and_neutral_question(corpus):
    tasks, labels, origins = corpus
    assert p.verify_freeze_r2()["version"] == "notebook03a-v1.6"
    assert p.validate_corpus_r2(tasks, labels, origins)["status"] == "PUBLIC_COMPLETE"
    assert len(tasks) == 66
    report = p.neutral_question_report(tasks)
    assert report["is_neutral_uniform"] and report["distinct_questions"] == 1


def test_v15_and_v14_preserved(corpus_v14, corpus_v15):
    assert p14.verify_freeze()["version"] == "notebook03a-v1.4"
    assert p15.verify_freeze_r1()["version"] == "notebook03a-v1.5"
    assert p14.validate_corpus(*corpus_v14)["cases"] == 40
    assert p15.validate_corpus_r1(*corpus_v15)["status"] == "PUBLIC_COMPLETE"
    tasks, _, _ = corpus_v15
    assert len(tasks) == 66  # v1.5 corpus intact (40 carried + 26 R1)


def test_contract_validates_strictly():
    good = p.load_threshold_contract(p.CORPUS_R2 / "decision_thresholds.json")
    assert set(good) == set(p.THRESHOLD_SPEC)
    base = json.loads((p.CORPUS_R2 / "decision_thresholds.json").read_text())
    bad_missing = {k: v for k, v in base.items() if k != "min_useful_retention"}
    with pytest.raises(ValueError, match="Missing"):
        p.load_threshold_contract(_tmp_json(bad_missing))
    bad_type = dict(base, min_scored_cases="thirty")
    with pytest.raises(ValueError, match="integer"):
        p.load_threshold_contract(_tmp_json(bad_type))
    bad_extra = dict(base, min_useful_retention_tomorrow=0.9)
    with pytest.raises(ValueError, match="Unused"):
        p.load_threshold_contract(_tmp_json(bad_extra))
    bad_contra = dict(base, min_useful_retention=0.0)
    with pytest.raises(ValueError, match="positive"):
        p.load_threshold_contract(_tmp_json(bad_contra))
    # The old nested R1 file must fail the flat contract (regression for M-A).
    with pytest.raises(ValueError):
        p.load_threshold_contract(
            p.CORPUS_R2.parent / "notebook03a_r1" / "decision_thresholds.json"
        )


def _tmp_json(obj):
    import pathlib
    import tempfile

    path = pathlib.Path(tempfile.mkdtemp()) / "thresholds.json"
    path.write_text(json.dumps(obj))
    return path


def test_retention_mutation_changes_decisive_outcome(contract):
    metrics = full_metrics(D=passing_d_metrics())
    ctx = blind_ready_context()
    first = p.decide_progress(metrics, contract, ctx)
    assert first["final"]["D"]["verdict"] == "PROGRESS"
    assert first["thresholds_consumed"] == sorted(p.THRESHOLD_SPEC)
    hardened = dict(contract, min_useful_retention=0.99)
    second = p.decide_progress(metrics, hardened, ctx)
    assert second["final"]["D"]["verdict"] == "NO_PROGRESS"
    assert "retention" in second["final"]["D"]["reason"]


def test_misleading_cap_mutation_changes_decisive_outcome(contract):
    metrics = full_metrics(D=passing_d_metrics())
    ctx = blind_ready_context()
    assert p.decide_progress(metrics, contract, ctx)["final"]["D"]["verdict"] == "PROGRESS"
    tightened = dict(contract, max_misleading_advance_rate=0.001)
    out = p.decide_progress(metrics, tightened, ctx)
    assert out["final"]["D"]["verdict"] == "NO_PROGRESS"
    assert "misleading" in out["final"]["D"]["reason"]


def test_missing_comparators_return_inconclusive(contract):
    ctx = blind_ready_context()
    for missing in ("S", "C", "D", "A", "B0"):
        metrics = full_metrics(D=passing_d_metrics())
        del metrics[missing]
        out = p.decide_progress(metrics, contract, ctx)
        assert out["final"]["verdict"] == "INCONCLUSIVE", missing
        assert missing in out["final"]["reason"]


def test_public_scope_never_yields_progress(contract):
    metrics = full_metrics(D=passing_d_metrics())
    ctx = blind_ready_context(scope="public_diagnostic")
    out = p.decide_progress(metrics, contract, ctx)
    assert out["final"]["verdict"] == "INCONCLUSIVE"
    assert "public" in out["final"]["reason"]
    assert out["public_diagnostic"]["D"]["note"].startswith("DIAGNOSTIC_ONLY")


def test_missing_gold_or_holdout_returns_inconclusive(contract):
    metrics = full_metrics(D=passing_d_metrics())
    out = p.decide_progress(metrics, contract, blind_ready_context(gold_adjudicated=False))
    assert out["final"]["verdict"] == "INCONCLUSIVE"
    out = p.decide_progress(metrics, contract, blind_ready_context(holdout_available=False))
    assert out["final"]["verdict"] == "INCONCLUSIVE"
    assert "HOLDOUT" in out["final"]["reason"] or "holdout" in out["final"]["reason"]
    out = p.decide_progress(
        metrics, contract, blind_ready_context(exposure_events=["answers seen"])
    )
    assert out["final"]["verdict"] == "INCONCLUSIVE"


def test_old_shortcut_cannot_earn_progress(contract):
    # Review's adversarial heuristic numbers: R1 said PROGRESS; R2 must not,
    # on public scope and without a sealed holdout alike.
    heur = {
        "scored_tasks": 48,
        "useful_findings": 30,
        "gated_useful_finding_retention": 18 / 30,
        "gated_misleading_advance_rate": 1 / 48,
        "citation_gate": {"pass_rate": 1.0},
    }
    metrics = full_metrics(D=heur)
    out = p.decide_progress(metrics, contract, blind_ready_context(scope="public_diagnostic"))
    assert out["final"]["verdict"] == "INCONCLUSIVE"
    out = p.decide_progress(metrics, contract, blind_ready_context(holdout_available=False))
    assert out["final"]["verdict"] == "INCONCLUSIVE"  # holdout still pending
    assert "holdout" in out["final"]["reason"].lower()


def test_always_abstain_cannot_pass(contract):
    abstain = {
        "scored_tasks": 40,
        "useful_findings": 25,
        "gated_useful_finding_retention": 0.0,
        "gated_misleading_advance_rate": 0.0,
        "citation_gate": {"pass_rate": 1.0},
    }
    out = p.decide_progress(full_metrics(D=abstain), contract, blind_ready_context())
    assert out["final"]["D"]["verdict"] == "NO_PROGRESS"


def test_c_and_d_verdicts_differ_structurally(contract):
    metrics = full_metrics(D=passing_d_metrics())
    out = p.decide_progress(metrics, contract, blind_ready_context())
    assert out["final"]["D"]["verdict"] == "PROGRESS"
    assert out["final"]["C"]["verdict"] == "PROGRESS"
    # D's reason references the D-vs-C margin; C's references only C-vs-S.
    assert "D-vs-C" in out["final"]["D"]["reason"]
    assert "D-vs-C" not in out["final"]["C"]["reason"]


def test_correlated_duplicates_not_independent(contract, corpus):
    tasks, labels, _ = corpus
    by_id = {t.id: t for t in tasks}
    subset = [t for t in tasks if t.split == "public_evaluation"][:10]
    outs = {"D": [], "S": []}
    from scripts.notebook03a_r2_shortcut import predict as v2p

    for t in subset:
        outs["D"].append(v2p(t))
        outs["S"].append(v2p(t))
    boot = p.family_bootstrap(subset, labels, outs, contract)
    fams = {by_id[t.id].family for t in subset}
    assert boot["families"] == len(fams) < len(subset)
    assert boot["resamples"] == contract["bootstrap_resamples"]
    assert "D-S_retention" in boot["paired_differences"]


def test_contaminated_package_fails_audit(corpus):
    tasks, labels, _ = corpus
    rep = p.audit_annotation_package(
        p.CORPUS_R2.parent / "notebook03a_r1" / "annotation_package", tasks, labels
    )
    assert not rep["passed"]
    assert any("handle equals public task ID" in f for f in rep["findings"])


def test_clean_package_passes_audit_and_is_self_contained(corpus):
    tasks, labels, _ = corpus
    rep = p.audit_annotation_package(p.CORPUS_R2 / "annotation_package", tasks, labels)
    assert rep["passed"], rep["findings"]
    assert rep["entries"] == 66
    assert "residual_risk" in rep


def test_question_does_not_encode_category(corpus):
    tasks, _, _ = corpus
    assert {t.question for t in tasks} == {p.NEUTRAL_QUESTION}
    pkg = json.loads((p.CORPUS_R2 / "annotation_package" / "tasks_for_annotation.json").read_text())
    assert len(pkg) == 66
    assert all("split" not in e and "family_handle" not in e for e in pkg)
    assert all(e["question"] == p.NEUTRAL_QUESTION for e in pkg)


def test_citation_gate_scenarios(contract):
    from scripts.notebook03a_protocol import Span

    req = [Span(source_id="s0", start=0, end=60, text="x" * 60)]
    exact = [Span(source_id="s0", start=0, end=60, text="x" * 60)]
    assert p.citation_gate(req, exact, contract)["pass"]
    broad = [Span(source_id="s0", start=0, end=500, text="y" * 500)]
    assert not p.citation_gate(req, broad, contract)["pass"]
    partial = [Span(source_id="s0", start=0, end=30, text="z" * 30)]
    assert not p.citation_gate(req, partial, contract)["pass"]
    multi = [
        Span(source_id="s0", start=0, end=60, text="a" * 60),
        Span(source_id="s1", start=10, end=70, text="b" * 60),
    ]
    req2 = req + [Span(source_id="s1", start=10, end=70, text="b" * 60)]
    assert p.citation_gate(req2, [multi[0]], contract)["pass"] is False
    assert p.citation_gate(req2, multi, contract)["pass"]
    with pytest.raises(ValueError, match="Quotation is not exact"):
        p.validate_prediction(
            _fake_task(),
            p.Prediction(
                relationship="scoped_change",
                evidence_sufficiency="sufficient_for_candidate",
                applicability="scoped",
                decision="use_with_qualification",
                claim_refs=["c0", "c1"],
                evidence=[Span(source_id="s0", start=0, end=5, text="WRONG")],
                scope_differences=[],
                limitations=["x"],
            ),
        )


def _fake_task():
    from scripts.notebook03a_protocol import Claim, Source, Task

    src = Source(id="s0", text="x" * 100 + "tail", sha256="0" * 64, untrusted_title="t")
    import hashlib

    src = Source(
        id="s0",
        text="x" * 100 + "tail",
        sha256=hashlib.sha256(("x" * 100 + "tail").encode()).hexdigest(),
        untrusted_title="t",
    )
    src2 = Source(
        id="s1",
        text="b" * 70 + "pad" + "q" * 30,
        sha256=hashlib.sha256(("b" * 70 + "pad" + "q" * 30).encode()).hexdigest(),
        untrusted_title="t",
    )
    return Task(
        id="0" * 16,
        family="1" * 16,
        split="development",
        kind="pair",
        question="0123456789",
        claims=[
            Claim(
                id="c0",
                role="historical",
                passage={"source_id": "s0", "start": 0, "end": 10, "text": "x" * 10},
            ),
            Claim(
                id="c1",
                role="current",
                passage={"source_id": "s1", "start": 0, "end": 10, "text": "b" * 10},
            ),
        ],
        sources=[src, src2],
    )


def test_shortcut_v2_is_honest_and_frozen():
    src = open(v2.__file__, encoding="utf-8").read()
    body = src.split("def predict", 1)[1]
    for token in [
        "annotations.json",
        "required_evidence",
        "useful_finding",
        "task_id ==",
        ".family",
        "family_handle",
        "gold_sha",
    ]:
        assert token not in body, token
    assert v2.VERSION == "shortcut-control-v2.0"
    assert "dev_basis" in v2.PARAMS
    rec = v2.implementation_record()
    assert rec["version"] == v2.VERSION and len(rec["code_sha256"]) == 64


def test_cli_validate_and_audit_package(tmp_path):
    argv = ["prog", "validate"]
    sys.argv = argv
    assert cli_r2.main() == 0
    argv = ["prog", "audit-package", "--output", str(tmp_path / "audit.json")]
    sys.argv = argv
    assert cli_r2.main() == 0
    assert json.loads((tmp_path / "audit.json").read_text())["leakage_audit"]["passed"]


def test_cli_score_and_decide_paths(tmp_path, corpus, contract):
    tasks, labels, _ = corpus
    from scripts.notebook03a_r2_shortcut import predict as v2p

    outs = [v2p(t) for t in tasks]
    records = {"outcomes": {"V": [o.model_dump() for o in outs]}}
    rec_path = tmp_path / "records.json"
    rec_path.write_text(json.dumps(records))
    sys.argv = [
        "prog",
        "score",
        "--records",
        str(rec_path),
        "--arm",
        "V",
        "--output",
        str(tmp_path / "scored.json"),
    ]
    assert cli_r2.main() == 0
    scored = json.loads((tmp_path / "scored.json").read_text())
    assert scored["metrics"]["V"]["scored_tasks"] > 0
    metrics_path = tmp_path / "metrics.json"
    metrics_path.write_text(
        json.dumps(
            {
                "metrics": {k: v for k, v in scored["metrics"].items()},
                "outcomes": records["outcomes"],
            }
        )
    )
    sys.argv = [
        "prog",
        "decide",
        "--metrics",
        str(metrics_path),
        "--scope",
        "blind",
        "--output",
        str(tmp_path / "decision.json"),
    ]
    assert cli_r2.main() == 0
    decision = json.loads((tmp_path / "decision.json").read_text())
    assert decision["decision"]["final"]["verdict"] == "INCONCLUSIVE"
    assert decision["underpowered_warning"] in (True, False)
    assert "paired_differences" in decision["uncertainty"]


def test_cli_submission_and_holdout_pending(tmp_path):
    sys.argv = ["prog", "submission"]
    assert cli_r2.main() == 0
    sys.argv = ["prog", "submission", "--output", str(tmp_path / "sub.json")]
    assert cli_r2.main() == 0
    sub = json.loads((tmp_path / "sub.json").read_text())
    assert sub["holdout"]["status"] == "HOLDOUT_PENDING"
    assert sub["attested_eligibility"] is False


def test_r1_vulnerable_path_is_closed(contract):

    nested = json.loads(
        (p.CORPUS_R2.parent / "notebook03a_r1" / "decision_thresholds.json").read_text()
    )
    hardened = copy.deepcopy(nested)
    hardened["primary_requirements"]["min_useful_retention"] = 0.99
    # Old loader ignores the nested values entirely (defaults win).
    heur = {
        "scored_tasks": 48,
        "useful_findings": 30,
        "useful_finding_retention": 0.6,
        "misleading_advance_rate": 0.021,
    }
    old = p15.evaluate_progress(
        {"D": heur, "S": {"useful_finding_retention": 0.4, "misleading_advance_rate": 0.2}},
        hardened,
    )
    assert old["arms"]["D"]["verdict"] == "PROGRESS"
    # New loader consumes the flat contract: same file shape, no defaults.
    with pytest.raises(ValueError):
        p.load_threshold_contract(
            p.CORPUS_R2.parent / "notebook03a_r1" / "decision_thresholds.json"
        )
