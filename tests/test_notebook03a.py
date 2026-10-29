"""Adversarial protocol/scoring tests. Synthetic scoring fixtures are never model results."""

import copy
import json

import pytest
from pydantic import ValidationError

from scripts import notebook03a as cli
from scripts import notebook03a_protocol as p


@pytest.fixture
def corpus():
    tasks, labels, origins = p.load_corpus()
    return tasks, labels, origins


def replace(model, **changes):
    return type(model).model_validate(model.model_dump() | changes)


def task_for(corpus, relationship):
    tasks, labels, _ = corpus
    a = next(a for a in labels if a.relationships == [relationship])
    return next(t for t in tasks if t.id == a.task_id), a


def test_frozen_public_corpus_and_schemas_are_complete(corpus):
    tasks, labels, origins = corpus
    assert p.verify_freeze()["version"] == "notebook03a-v1.4"
    result = p.validate_corpus(tasks, labels, origins)
    assert result["cases"] == 40 and result["status"] == "PUBLIC_COMPLETE"
    assert result["splits"] == {"development": 16, "public_evaluation": 24}
    frozen = json.loads((p.CORPUS / "schemas.json").read_text())
    for name, model in {
        "task": p.Task,
        "annotation": p.Annotation,
        "prediction": p.Prediction,
        "exposure": p.Exposure,
        "outcome": p.Outcome,
    }.items():
        assert model.model_json_schema() == frozen[name]


@pytest.mark.parametrize("mutation", ["hash", "quote", "source", "extra_label"])
def test_malformed_or_label_leaking_tasks_rejected(corpus, mutation):
    task = corpus[0][0].model_dump()
    if mutation == "hash":
        task["sources"][0]["sha256"] = "0" * 64
    elif mutation == "quote":
        task["claims"][0]["passage"]["text"] = "fabricated source quotation"
    elif mutation == "source":
        task["claims"][0]["passage"]["source_id"] = "unknown-source"
    else:
        task["expected_relationship"] = "supersession"
    with pytest.raises((ValueError, ValidationError)):
        p.Task.model_validate(task)


def test_missing_qualifier_invalidates_existing_quote_bindings(corpus):
    task, _ = task_for(corpus, "unsupported_claim")
    data = task.model_dump()
    data["sources"][0]["text"] = data["sources"][0]["text"].split("\n")[0]
    data["sources"][0]["sha256"] = p.digest(data["sources"][0]["text"])
    with pytest.raises(ValueError):
        p.Task.model_validate(data)


def test_pinned_authentic_provenance_cannot_be_self_certified(corpus):
    tasks, labels, origins = corpus
    altered = copy.deepcopy(origins)
    entry = next(v for d in altered.values() for v in d.values() if v["kind"] == "authentic")
    entry["document_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="Pinned document hash"):
        p.validate_corpus(tasks, labels, altered)


def test_family_or_duplicate_source_cannot_cross_splits(corpus):
    tasks, labels, origins = corpus
    first = next(t for t in tasks if sum(x.family == t.family for x in tasks) > 1)
    altered = [
        replace(t, split="public_evaluation" if t.split == "development" else "development")
        if t.id == first.id
        else t
        for t in tasks
    ]
    with pytest.raises(ValueError, match="crosses splits"):
        p.validate_corpus(altered, labels, origins)


def test_missing_or_unsupported_labels_are_not_filled_in(corpus):
    tasks, labels, origins = corpus
    result = p.validate_corpus(tasks, labels[1:], origins)
    assert result["status"] == "INCOMPLETE" and result["missing_or_pending_annotations"] == [
        labels[0].task_id
    ]
    with pytest.raises(ValueError, match="unsupported annotation"):
        p.validate_corpus(tasks, labels + [replace(labels[0], task_id="not-a-task")], origins)


@pytest.mark.parametrize(
    "change",
    [
        {"sufficiency": "insufficient"},
        {"relationships": ["unknown", "supersession"]},
        {"independence": "external_attested"},
        {"required_evidence": []},
    ],
)
def test_annotation_contract_rejects_incoherent_metadata(corpus, change):
    _, a = task_for(corpus, "supersession")
    with pytest.raises(ValueError):
        replace(a, **change)


def test_payload_excludes_labels_case_ids_and_annotation_metadata(corpus):
    tasks, _, _ = corpus
    for task in tasks:
        if any(s.access != "fixture_authorized" for s in task.sources):
            with pytest.raises(PermissionError):
                p.prepare_payload(task)
            continue
        payload = p.prepare_payload(task)
        assert set(payload) == {
            "contract_version",
            "question",
            "task_kind",
            "claims",
            "sources",
        }
        text = p.canonical(payload)
        assert task.id not in text and task.family not in text
        assert (
            "required_evidence" not in text
            and "independence" not in text
            and "rationale" not in text
        )
        assert len(text) <= 16000


def test_repository_holdout_is_not_hidden_and_exposure_invalidates_attestation(corpus):
    manifest = p.Exposure.model_validate(
        json.loads((p.CORPUS / "independent_submission.json").read_text())
    )
    assert not manifest.blind_eligible
    attested = replace(
        manifest,
        access_restricted_attested=True,
        independent_annotation_status="ADJUDICATED",
        inputs_sha256="a" * 64,
        gold_sha256="b" * 64,
    )
    assert attested.blind_eligible
    assert not replace(
        attested, implementer_exposure_events=["answers read during tuning"]
    ).blind_eligible
    tasks, labels, origins = corpus
    with pytest.raises(ValueError, match="repo-accessible"):
        p.validate_corpus([replace(t, split="independent_heldout") for t in tasks], labels, origins)


def semantic_fixture(task, a, **changes):
    # Unit-test scoring input only; production CLI disallows this mode entirely.
    return p.Outcome(
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


def test_always_abstain_cannot_hide_all_missed_useful_findings(corpus):
    tasks, labels, _ = corpus
    outcomes = [
        p.Outcome(
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
    result = p.score(tasks, labels, outcomes, "B0")
    assert result["useful_findings"] == 27
    assert result["useful_finding_retention"] == 0
    assert result["missed_useful_findings"] == 27
    assert result["correct_insufficient_abstention_rate"] == 1
    assert result["substantive_precision"] is None


@pytest.mark.parametrize(
    "relation",
    [
        "supersession",
        "contradiction_candidate",
        "scoped_change",
        "corroboration_candidate",
        "unsupported_claim",
    ],
)
def test_supported_finding_is_rewarded_and_wrong_category_penalized(corpus, relation):
    t, a = task_for(corpus, relation)
    good = semantic_fixture(t, a)
    with pytest.raises(PermissionError, match="03A has no model"):
        p.score([t], [a], [good], "D")
    result = p.score([t], [a], [good], "D", allow_offline_fixtures=True)
    assert result["correct_substantive_judgments"] == 1
    assert result["useful_findings_retained"] == 1
    wrong = replace(
        good,
        relationship="substantive_connection",
        superseded_claim_ref=None,
        replacement_claim_ref=None,
    )
    bad = p.score([t], [a], [wrong], "D", allow_offline_fixtures=True)
    assert bad["unsupported_substantive_judgments"] == 1
    assert bad["missed_useful_findings"] == 1


def test_citation_integrity_alone_does_not_prove_unsupported_headline(corpus):
    t, a = task_for(corpus, "unsupported_claim")
    output = replace(semantic_fixture(t, a), evidence=[t.claims[0].passage])
    result = p.score([t], [a], [output], "D", allow_offline_fixtures=True)
    assert result["unsupported_substantive_judgments"] == 1


def test_reversed_supersession_direction_is_not_credited(corpus):
    t, a = task_for(corpus, "supersession")
    output = replace(
        semantic_fixture(t, a),
        superseded_claim_ref=a.replacement_claim_ref,
        replacement_claim_ref=a.superseded_claim_ref,
    )
    result = p.score([t], [a], [output], "D", allow_offline_fixtures=True)
    assert result["correct_substantive_judgments"] == 0


def test_fabricated_quotes_unsupported_refs_and_authorization_fail_closed(corpus):
    t, a = task_for(corpus, "scoped_change")
    out = semantic_fixture(t, a)
    bad_quote = replace(out.evidence[0], text="not in source")
    with pytest.raises(ValueError, match="Quotation is not exact"):
        p.score([t], [a], [replace(out, evidence=[bad_quote])], "D", allow_offline_fixtures=True)
    with pytest.raises(ValueError, match="claim reference"):
        p.score(
            [t], [a], [replace(out, claim_refs=["fabricated"])], "D", allow_offline_fixtures=True
        )
    denied = replace(t, sources=[replace(s, access="withdrawn") for s in t.sources])
    with pytest.raises(PermissionError, match="hard gate"):
        p.score([denied], [a], [out], "D", allow_offline_fixtures=True)


def test_missing_duplicate_and_inapplicable_results_cannot_hide_difficult_cases(corpus):
    t, a = task_for(corpus, "scoped_change")
    out = semantic_fixture(t, a)
    for records in ([], [out, out]):
        with pytest.raises(ValueError, match="one recorded outcome"):
            p.score([t], [a], records, "D", allow_offline_fixtures=True)
    wrong = p.Outcome(
        task_id=t.id, arm="A", mode="lexical", action="not_applicable", raw_policy="bad-skip"
    )
    with pytest.raises(ValueError, match="Difficult cases"):
        p.score([t], [a], [wrong], "A")


def test_frozen_inputs_and_evidence_are_not_overwritten(tmp_path, monkeypatch):
    import shutil

    shutil.copytree(p.CORPUS, tmp_path / "data")
    target = tmp_path / "data" / "annotations.json"
    target.write_text("[]")
    with pytest.raises(ValueError, match="Frozen file drift"):
        p.verify_freeze(tmp_path / "data")
    f = tmp_path / "report.json"
    cli.write_new(f, {"status": "test"})
    with pytest.raises(ValueError, match="Refusing to overwrite"):
        cli.write_new(f, {"status": "silently changed"})


def test_external_submission_gate_is_not_satisfied_by_a_directory(tmp_path, monkeypatch):
    import sys

    manifest = json.loads((p.CORPUS / "independent_submission.json").read_text())
    (tmp_path / "independent_submission.json").write_text(json.dumps(manifest))
    monkeypatch.setattr(sys, "argv", ["runner", "submission", "--package", str(tmp_path)])
    with pytest.raises(ValueError, match="labeling/access/exposure gate"):
        cli.main()
    monkeypatch.setattr(sys, "argv", ["runner", "submission", "--package", str(p.CORPUS)])
    with pytest.raises(ValueError, match="implementer repo"):
        cli.main()


def test_unknown_relationship_cannot_authorize_use():
    with pytest.raises(ValueError, match="unknown relation"):
        p.Prediction(
            relationship="unknown",
            evidence_sufficiency="sufficient_for_candidate",
            applicability="unknown",
            decision="use_with_qualification",
            claim_refs=["c0"],
            evidence=[],
            scope_differences=[],
            limitations=["Unknown means no established relation"],
        )


def test_frozen_protocol_document_fingerprints():
    protocol = p.verify_freeze()
    for name, wanted in protocol["documents_sha256"].items():
        assert p.file_digest(p.ROOT / name) == wanted


def test_scoped_result_requires_comparator_and_generalization_limits(corpus):
    tasks, labels, _ = corpus
    task = next(
        t for t in tasks if any("strong history-access control" in s.text for s in t.sources)
    )
    label = next(a for a in labels if a.task_id == task.id)
    good = semantic_fixture(task, label)
    assert (
        p.score([task], [label], [good], "D", allow_offline_fixtures=True)[
            "correct_substantive_judgments"
        ]
        == 1
    )
    # Category and exact quotations alone are not enough when scope qualifications are omitted.
    reduced = replace(good, evidence=[label.required_evidence[-1]])
    result = p.score([task], [label], [reduced], "D", allow_offline_fixtures=True)
    assert result["correct_substantive_judgments"] == 0
    assert result["unsupported_substantive_judgments"] == 1
