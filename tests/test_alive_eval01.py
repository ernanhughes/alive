"""ALIVE-EVAL-01 custodian tests. Synthetic dummy gold/outputs test the
mechanism only; never a real blinded semantic experiment."""

import hashlib
import json

import pytest

from scripts import alive_eval01_custodian as cust
from scripts import notebook03a_r1_protocol as r15
from scripts import notebook03a_r2_protocol as r2


def _h(text):
    return hashlib.sha256(text.encode()).hexdigest()


def _task(i, fam, split="independent_heldout"):
    s0 = f"Archive record {i} notes receiver loss at 3 units in chamber R."
    s1 = f"Follow-up {i} confirms receiver loss at 3 units in chamber R."
    return {
        "id": f"{i:016x}",
        "family": f"{fam:016x}",
        "split": split,
        "kind": "pair",
        "question": "Assess the relationship between the supplied claims and evidence. "
        "State what is supported, what remains uncertain, and whether the "
        "evidence should influence the current conclusion.",
        "claims": [
            {
                "id": "c0",
                "role": "historical",
                "proposition": None,
                "qualifiers": [],
                "version_context": None,
                "temporal_context": None,
                "system_context": None,
                "passage": {"source_id": "s0", "start": 0, "end": len(s0), "text": s0},
            },
            {
                "id": "c1",
                "role": "current",
                "proposition": None,
                "qualifiers": [],
                "version_context": None,
                "temporal_context": None,
                "system_context": None,
                "passage": {"source_id": "s1", "start": 0, "end": len(s1), "text": s1},
            },
        ],
        "sources": [
            {
                "id": "s0",
                "text": s0,
                "sha256": _h(s0),
                "access": "fixture_authorized",
                "untrusted_title": "t",
            },
            {
                "id": "s1",
                "text": s1,
                "sha256": _h(s1),
                "access": "fixture_authorized",
                "untrusted_title": "t",
            },
        ],
        "supporting_passages": [],
    }


def _label(task, adjudicated=True):
    s0 = task["sources"][0]["text"]
    return {
        "task_id": task["id"],
        "status": "adjudicated" if adjudicated else "draft",
        "author": "author-1",
        "independence": "external_attested" if adjudicated else "implementer_authored",
        "reviewers": ["reviewer-1", "reviewer-2"] if adjudicated else [],
        "relationships": ["substantive_connection"],
        "sufficiency": "sufficient_for_candidate",
        "applicability": "scoped",
        "decisions": ["use_with_qualification"],
        "useful_finding": True,
        "rationale": f"Both passages for {task['id']} describe matching receiver loss.",
        "required_evidence": [{"source_id": "s0", "start": 0, "end": len(s0), "text": s0}],
        "forbidden_conclusions": ["Treat the match as verified factual truth."],
        "ambiguity_notes": None,
        "superseded_claim_ref": None,
        "replacement_claim_ref": None,
    }


def _out(
    task,
    arm,
    mode,
    rel="substantive_connection",
    action="use_with_qualification",
    suff="sufficient_for_candidate",
    appl="scoped",
):
    req = []
    if rel != "unknown":
        req = [
            {
                "source_id": "s0",
                "start": 0,
                "end": len(task["sources"][0]["text"]),
                "text": task["sources"][0]["text"],
            }
        ]
    return {
        "task_id": task["id"],
        "arm": arm,
        "mode": mode,
        "action": action,
        "relationship": rel,
        "sufficiency": suff,
        "applicability": appl,
        "evidence": req,
        "claim_refs": ["c0", "c1"],
        "raw_policy": "SYNTHETIC_MECHANISM_FIXTURE",
    }


def _package(
    tmp_path,
    n_tasks=10,
    n_families=5,
    split="independent_heldout",
    adjudicated=True,
    custodian="custodian-1",
    submitter="impl-author",
    tweak=None,
):
    pkg = tmp_path / "pkg"
    gold = tmp_path / "gold"
    custdir = tmp_path / "custody"
    pkg.mkdir(exist_ok=True)
    gold.mkdir(exist_ok=True)
    custdir.mkdir(exist_ok=True)
    tasks = [_task(i, i % n_families, split) for i in range(n_tasks)]
    labels = [_label(t, adjudicated) for t in tasks]
    (pkg / "tasks.json").write_text(json.dumps(tasks))
    origins = {
        t["id"]: {
            s["id"]: {
                "kind": "synthetic",
                "document": None,
                "commit": None,
                "document_sha256": None,
                "quote": None,
                "start": None,
                "note": "synthetic mechanism fixture",
            }
            for s in t["sources"]
        }
        for t in tasks
    }
    (pkg / "origins.json").write_text(json.dumps(origins))
    (gold / "annotations.json").write_text(json.dumps(labels))
    (gold / "origins.json").write_text(json.dumps(origins))
    task_bytes = json.dumps([t for t in tasks], sort_keys=True).encode()
    gold_bytes = json.dumps([a for a in labels], sort_keys=True).encode()
    record = {
        "custodian": custodian,
        "created_host": "custodian-machine",
        "created_at": "2026-10-29",
        "package_sha256": cust.hash_bytes(task_bytes),
        "gold_sha256": cust.hash_bytes(gold_bytes),
        "independent_annotation_status": "ADJUDICATED" if adjudicated else "draft",
        "access_restricted_attested": True,
        "exposure_events": [],
    }
    (custdir / "custody.json").write_text(json.dumps(record))
    if tweak:
        tweak(pkg, gold, custdir, tasks, labels)
    return pkg, gold, custdir, tasks, labels


def _real_request_good(submitter="impl-author", summary=None, scope="blind"):
    import pathlib

    import scripts.notebook03a_r2_protocol as scorer

    proto = (
        pathlib.Path("evaluations/notebook03a_r2/protocol.json")
        .read_bytes()
        .replace(b"\r\n", b"\n")
    )
    return {
        "protocol_dir": "evaluations/notebook03a_r2",
        "claimed_protocol_sha256": hashlib.sha256(proto).hexdigest(),
        "claimed_scorer_version": scorer.R2_VERSION,
        "claimed_scorer_sha256": hashlib.sha256(
            pathlib.Path(scorer.__file__).read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest(),
        "requested_scope": scope,
        "submitter": submitter,
        "submitted_summary": summary,
    }


def _outputs(tasks, arms=("A", "B0", "S", "V", "C", "D"), perfect=()):
    modes = {
        "A": "lexical",
        "B0": "constant_control",
        "S": "surface_heuristic",
        "V": "shortcut_v2",
        "C": "offline_scoring_fixture",
        "D": "offline_scoring_fixture",
    }
    out = {}
    for arm in arms:
        recs = []
        for t in tasks:
            if arm in ("A",):
                recs.append(
                    _out(
                        t,
                        arm,
                        modes[arm],
                        rel="unknown",
                        action="retain_candidate",
                        suff="unknown",
                        appl="unknown",
                    )
                )
            elif arm in ("B0",):
                recs.append(
                    _out(
                        t,
                        arm,
                        modes[arm],
                        rel="unknown",
                        action="abstain",
                        suff="unknown",
                        appl="unknown",
                    )
                )
            elif arm in perfect:
                recs.append(_out(t, arm, modes[arm]))
            else:
                recs.append(
                    _out(
                        t,
                        arm,
                        modes[arm],
                        rel="unknown",
                        action="abstain",
                        suff="insufficient",
                        appl="unknown",
                    )
                )
        out[arm] = recs
    return {"outcomes": out}


def _weaken_c(outs, n=10):
    """Make C strong but strictly weaker than a perfect D (abstain on n useful)."""
    for rec in outs["outcomes"]["C"][:n]:
        rec.update(
            relationship="unknown",
            sufficiency="insufficient",
            applicability="unknown",
            action="abstain",
            evidence=[],
        )
    return outs


@pytest.fixture
def policy():
    return cust.load_custodian_policy()


@pytest.fixture
def contract():
    return r2.load_threshold_contract(r2.CORPUS_R2 / "decision_thresholds.json")


def test_honest_receipt_recomputes_and_ignores_summary(policy, contract, tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _weaken_c(_outputs(tasks, perfect=("C", "D")))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    summary = {"D": {"gated_useful_finding_retention": 0.0, "gated_misleading_advance_rate": 0.99}}
    rec = cust.evaluate(
        _real_request_good(summary=summary),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "PROGRESS"
    assert rec["summary_authoritative"] is False
    assert rec["submitted_summary_echo"] == summary
    assert rec["metrics"]["D"]["gated_useful_finding_retention"] == 1.0
    assert rec["scope_determined"]["scope"] == "blind"
    assert rec["uncertainty"]["families"] == 20
    assert rec["custody"]["custody_valid"] is True


def test_fabricated_metrics_cannot_pass(policy, contract, tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=())
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    summary = {"D": {"gated_useful_finding_retention": 0.95, "gated_misleading_advance_rate": 0.01}}
    rec = cust.evaluate(
        _real_request_good(summary=summary),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] in ("NO_PROGRESS", "INCONCLUSIVE")
    assert rec["verdict"] != "PROGRESS"
    assert rec["metrics"]["D"]["gated_useful_finding_retention"] == 0.0


def test_one_case_fake_holdout_fails(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=1, n_families=1)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert any("holdout" in r for r in rec["reasons"])


def test_forged_adjudicated_flag_fails(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        rec = json.loads((custdir / "custody.json").read_text())
        rec["independent_annotation_status"] = "ADJUDICATED"
        (custdir / "custody.json").write_text(json.dumps(rec))

    pkg, gold, custdir, tasks, labels = _package(
        tmp_path, n_tasks=10, n_families=10, adjudicated=False, tweak=tweak
    )
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["custody"]["custody_valid"] is False


def test_modified_gold_hash_fails_closed(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        rec = json.loads((custdir / "custody.json").read_text())
        rec["gold_sha256"] = "0" * 64
        (custdir / "custody.json").write_text(json.dumps(rec))

    pkg, gold, custdir, tasks, labels = _package(tmp_path, tweak=tweak)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["custody"]["custody_valid"] is False
    assert "gold hash" in rec["custody"]["reason"]


def test_modified_protocol_hash_fails_closed(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good()
    req["claimed_protocol_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="protocol hash"):
        cust.evaluate(
            req,
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "receipt.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
            },
        )


def test_wrong_scope_flag_downgrades_to_public(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, split="public_evaluation")
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(scope="blind"),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["scope_determined"]["scope"] == "public_diagnostic"
    assert rec["verdict"] == "INCONCLUSIVE"


def test_changed_task_set_after_evaluation_fails(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path)
    other = [_task(100 + i, i) for i in range(len(tasks))]
    outs = _outputs(other, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    with pytest.raises(ValueError, match="task set"):
        cust.evaluate(
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "receipt.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
            },
        )


def test_same_id_changed_source_fails(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        data = json.loads((pkg / "tasks.json").read_text())
        data[0]["sources"][0]["text"] += " tampered"
        (pkg / "tasks.json").write_text(json.dumps(data))

    pkg, gold, custdir, tasks, labels = _package(tmp_path, tweak=tweak)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    with pytest.raises(ValueError, match="hash|citation|binding"):
        cust.evaluate(
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "receipt.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
            },
        )


def test_missing_source_hash_fails(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        data = json.loads((pkg / "tasks.json").read_text())
        del data[0]["sources"][0]["sha256"]
        (pkg / "tasks.json").write_text(json.dumps(data))

    pkg, gold, custdir, tasks, labels = _package(tmp_path, tweak=tweak)
    with pytest.raises(ValueError):
        cust.load_package_tasks(pkg)


def test_tampered_scorer_identity_fails(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good()
    req["claimed_scorer_version"] = "notebook03a-v9.9"
    with pytest.raises(ValueError, match="scorer"):
        cust.evaluate(
            req,
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "receipt.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
            },
        )


def test_missing_comparator_outputs_inconclusive(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=("D",))
    del outs["outcomes"]["C"]
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert any("C" in r for r in rec["reasons"])


def test_self_issued_custody_rejected(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(
        tmp_path, custodian="impl-author", submitter="impl-author"
    )
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(submitter="impl-author"),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["custody"]["custody_valid"] is False


def test_policy_rejects_nan_inf_zero_unknown(tmp_path):
    base = json.loads((cust.CUSTODIAN_POLICY_PATH).read_text())
    for bad_key, bad_val in [
        ("min_holdout_cases", 0),
        ("min_useful_cases", 0),
        ("required_arms", []),
    ]:
        bad = dict(base, **{bad_key: bad_val})
        p = tmp_path / "pol.json"
        p.write_text(json.dumps(bad))
        with pytest.raises(ValueError):
            cust.load_custodian_policy(p)
    bad = dict(base, surprise_key=1)
    p = tmp_path / "pol.json"
    p.write_text(json.dumps(bad))
    with pytest.raises(ValueError, match="unknown"):
        cust.load_custodian_policy(p)
    p.write_text('{"min_holdout_cases": NaN}')
    with pytest.raises(ValueError, match="non-finite"):
        cust.load_custodian_policy(p)
    p.write_text('{"min_holdout_cases": Infinity}')
    with pytest.raises(ValueError, match="non-finite"):
        cust.load_custodian_policy(p)


def test_threshold_nan_inf_ci_bounds_rejected(tmp_path, contract):
    for text in ('{"x": NaN}', '{"x": Infinity}'):
        p = tmp_path / "t.json"
        p.write_text(text)
        with pytest.raises(ValueError, match="non-finite"):
            cust.strict_json_load(p)
    base = json.loads((r2.CORPUS_R2 / "decision_thresholds.json").read_text())
    for key, val in [
        ("ci_level", 0.0),
        ("ci_level", 1.0),
        ("min_citation_precision", 0.0),
        ("require_full_citation_recall", False),
        ("min_useful_retention", 0.0),
        ("max_misleading_advance_rate", 1.0),
    ]:
        bad = dict(base, **{key: val})
        with pytest.raises(ValueError):
            cust.validate_decision_contract_strict(bad)
    cust.validate_decision_contract_strict(base)


def test_every_policy_param_genuinely_consumed(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _weaken_c(_outputs(tasks, perfect=("C", "D")))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))

    def run_with(policy_path, out_name):
        return cust.evaluate(
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / out_name,
                "policy_path": policy_path,
                "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
            },
        )

    first = run_with(cust.CUSTODIAN_POLICY_PATH, "r1.json")
    assert first["verdict"] == "PROGRESS"
    assert first["uncertainty"]["resamples"] == 1000
    base = json.loads(cust.CUSTODIAN_POLICY_PATH.read_text())

    def tweaked(**over):
        nxt = dict(base, **over)
        p = tmp_path / f"pol-{len(list(tmp_path.glob('pol-*.json')))}.json"
        p.write_text(json.dumps(nxt))
        return p

    # min_holdout_cases genuinely gates: raising it above the package size blocks PROGRESS.
    out = run_with(tweaked(min_holdout_cases=999), "r2.json")
    assert out["verdict"] == "INCONCLUSIVE"
    assert any("holdout" in r for r in out["reasons"])
    # required_arms genuinely gates: requiring an absent arm invalidates the verdict.
    out = run_with(tweaked(required_arms=["A", "B0", "S", "V", "C", "D", "X"]), "r3.json")
    assert out["verdict"] == "INCONCLUSIVE"
    assert any("X" in r for r in out["reasons"])


def test_intervals_nested_and_counts_reported(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["uncertainty"]["draws_per_arm"]["D"] == 1000
    assert rec["uncertainty"]["families"] == 20
    assert rec["uncertainty"]["level"] == 0.95


def test_identical_systems_cannot_progress(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=("C", "D"))
    outs["outcomes"]["D"] = [
        dict(r, arm="D", mode="offline_scoring_fixture", raw_policy="copy")
        for r in outs["outcomes"]["C"]
    ]
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["verdict"] != "PROGRESS"
    assert rec["uncertainty"]["paired_differences"]["D-C_retention"] == [0.0, 0.0]


def test_imbalanced_families_warn(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=2)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = cust.evaluate(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": r2.CORPUS_R2 / "decision_thresholds.json",
        },
    )
    assert rec["uncertainty"]["imbalance_warning"] is True
    assert rec["imbalance_warning"] is True
    assert rec["verdict"] == "INCONCLUSIVE"


def test_gated_flags_match_scorer(contract):
    from scripts.notebook03a_r2_protocol import load_corpus_r2, score_r2
    from scripts.notebook03a_r2_shortcut import predict as v2p

    tasks, labels, _ = load_corpus_r2()
    outs = {"V": [v2p(t) for t in tasks]}
    scored = score_r2(tasks, labels, outs["V"], "V", contract)
    flags = cust.gated_flags(tasks, labels, outs, contract)
    retained = sum(
        1 for v in flags["V"].values() if v is not None and v["retained"] and v["useful"]
    )
    misleading = sum(
        1 for v in flags["V"].values() if v is not None and v["misleading"] and v["scored"]
    )
    assert retained == scored["gated_useful_findings_retained"]
    assert misleading == scored["gated_misleading_advances"]


def test_controls_registry_marks_contamination():
    reg = json.loads((cust.ROOT / "evaluations/alive-eval-01/controls_registry.json").read_text())
    assert reg["S-surface-cue-v1.0"]["independence"] == "template-informed"
    assert reg["V-shortcut-control-v2.0"]["independence"] == "evaluation-informed"
    assert "code_sha256" in reg["V-shortcut-control-v2.0"]
    import hashlib
    import pathlib

    actual = hashlib.sha256(
        pathlib.Path("scripts/notebook03a_r2_shortcut.py").read_bytes().replace(b"\r\n", b"\n")
    ).hexdigest()
    assert reg["V-shortcut-control-v2.0"]["code_sha256"] == actual


def test_annotation_package_v17_clean():
    from scripts import notebook03a_r2_protocol as r2p

    tasks, labels, _ = r2p.load_corpus_r2()
    # Frozen R2 package still passes its own frozen audit (preservation).
    frozen = r2p.audit_annotation_package(r2p.CORPUS_R2 / "annotation_package", tasks, labels)
    assert frozen["passed"], frozen["findings"]
    # The v1.7 package passes the stricter v1.7 audit.
    v17 = cust.ROOT / "evaluations/alive-eval-01/annotation_package"
    rep = cust.audit_package_v17(v17, tasks, labels)
    assert rep["passed"], rep["findings"]
    assert rep["entries"] == 66
    pkg = json.loads((v17 / "tasks_for_annotation.json").read_text())
    for entry in pkg:
        for source in entry["sources"]:
            assert "sha256" not in source and "access" not in source
    text = (v17 / "labeling_instructions.md").read_text()
    assert "Open adjudication questions" in text
    # The frozen R2 package fails the stricter v1.7 audit (hashes present):
    # this is why the revision was required.
    strict_on_old = cust.audit_package_v17(r2p.CORPUS_R2 / "annotation_package", tasks, labels)
    assert not strict_on_old["passed"]
    assert any("content hash" in f for f in strict_on_old["findings"])


def test_tampered_package_with_mapping_fails(tmp_path):
    import shutil

    from scripts import notebook03a_r2_protocol as r2p

    tasks, labels, _ = r2p.load_corpus_r2()
    dest = tmp_path / "pkg"
    shutil.copytree(cust.ROOT / "evaluations/alive-eval-01/annotation_package", dest)
    (dest / "handle_mapping.json").write_text("{}")
    rep = cust.audit_package_v17(dest, tasks, labels)
    assert not rep["passed"]
    assert any("mapping" in f for f in rep["findings"])


def test_r1_vulnerable_path_closed_by_custodian(contract, tmp_path):
    heur = {
        "scored_tasks": 48,
        "useful_findings": 30,
        "useful_finding_retention": 0.6,
        "misleading_advance_rate": 0.021,
    }
    old = r15.evaluate_progress(
        {"D": heur, "S": {"useful_finding_retention": 0.4, "misleading_advance_rate": 0.2}},
        json.loads((r15.CORPUS_R1 / "decision_thresholds.json").read_text()),
    )
    assert old["arms"]["D"]["verdict"] == "PROGRESS"
    pkg, gold, custdir, tasks, labels = _package(tmp_path, split="public_evaluation")
    assert pkg is not None


def test_cli_evaluate_paths(tmp_path):
    import sys

    from scripts import alive_eval01 as cli

    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=10, n_families=10)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good()
    rp = tmp_path / "request.json"
    rp.write_text(json.dumps(req))
    sys.argv = [
        "prog",
        "evaluate",
        "--package",
        str(pkg),
        "--gold",
        str(gold),
        "--outputs",
        str(op),
        "--custody",
        str(custdir),
        "--contract",
        str(r2.CORPUS_R2 / "decision_thresholds.json"),
        "--protocol-dir",
        "evaluations/notebook03a_r2",
        "--request",
        str(rp),
        "--output",
        str(tmp_path / "receipt.json"),
    ]
    assert cli.main() == 0
    receipt = json.loads((tmp_path / "receipt.json").read_text())
    assert receipt["verdict"] in ("PROGRESS", "NO_PROGRESS", "INCONCLUSIVE")
    assert receipt["summary_authoritative"] is False
    sys.argv = ["prog", "verify"]
    assert cli.main() == 0
