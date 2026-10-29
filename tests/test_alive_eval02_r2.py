"""ALIVE-EVAL-02 R2 trust-boundary regression tests.

R1 demonstrated that caller-controlled --sealed-root (and friends) let a
submitter manufacture QUALIFIED / PROGRESS / ESTABLISHED without touching
application code. Every test here must fail closed; none may produce a
qualified verdict, with or without a cooperating submitter.
"""

import json

import pytest

from scripts import alive_eval01_custodian as cust
from scripts import alive_eval02_custodian as c2
from tests.test_alive_eval01 import _outputs, _package, _real_request_good, _weaken_c

CONTRACT = "evaluations/notebook03a_r2/decision_thresholds.json"


def _paths(tmp_path, out="receipt.json"):
    return {
        "policy_path": cust.CUSTODIAN_POLICY_PATH,
        "contract_path": CONTRACT,
    }


def _run(tmp_path, out="receipt.json", **kw):
    pkg_kwargs = {
        k: kw.pop(k)
        for k in (
            "n_tasks",
            "n_families",
            "split",
            "adjudicated",
            "custodian",
            "submitter",
            "tweak",
        )
        if k in kw
    }
    perfect = kw.pop("perfect", ("C", "D"))
    arms = kw.pop("arms", None)
    scope = kw.pop("scope", "blind")
    weaken = kw.pop("weaken", True)
    policy_path = kw.pop("policy_path", None)
    contract_path = kw.pop("contract_path", None)
    assert not kw, kw
    pkg, gold, custdir, tasks, labels = _package(tmp_path, **pkg_kwargs)
    outs = _outputs(tasks, perfect=perfect)
    if weaken:
        outs = _weaken_c(outs)
    if arms is not None:
        outs = {"outcomes": {a: outs["outcomes"][a] for a in arms}}
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good(submitter=pkg_kwargs.get("submitter", "impl-author"), scope=scope)
    rec = c2.evaluate_v2(
        req,
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / out,
            "policy_path": policy_path or cust.CUSTODIAN_POLICY_PATH,
            "contract_path": contract_path or CONTRACT,
        },
    )
    return rec, {"pkg": pkg, "gold": gold, "custdir": custdir, "op": op, "req": req}


def test_r1_exploit_sealed_root_flag_rejected_by_cli(tmp_path, monkeypatch, capsys):
    import sys

    from scripts import alive_eval02

    sealed = tmp_path / "sealed"
    sealed.mkdir()
    monkeypatch.setattr(sys, "argv", ["alive_eval02", "evaluate", "--sealed-root", str(sealed)])
    with pytest.raises(SystemExit) as exit_code:
        alive_eval02.main()
    assert exit_code.value.code == 2
    assert not list(tmp_path.glob("receipt*.json"))


def test_self_created_sealed_dir_cannot_qualify(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(
        tmp_path,
        n_tasks=30,
        n_families=20,
        custodian="totally-independent-party",
        submitter="impl-author",
    )
    record = json.loads((custdir / "custody.json").read_text())
    record["human_boundary_confirmed"] = {
        "confirmed": True,
        "confirmer": "dr-trustworthy",
        "confirmed_at": "2026-10-29",
    }
    (custdir / "custody.json").write_text(json.dumps(record))
    stray = tmp_path / "stray-sealed"
    stray.mkdir()
    (stray / "record.json").write_bytes((custdir / "custody.json").read_bytes())
    outs = _weaken_c(_outputs(tasks, perfect=("C", "D")))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = c2.evaluate_v2(
        _real_request_good(submitter="impl-author"),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "r.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": CONTRACT,
        },
    )
    assert rec["verdict"] != "PROGRESS"
    assert rec["custody_state"] != "QUALIFIED"
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"
    assert c2.is_qualified_progress(rec) is False


def test_forged_signature_rejected(tmp_path, monkeypatch):
    pkg, gold, custdir, tasks, labels = _package(
        tmp_path, n_tasks=10, n_families=5, custodian="mallory", submitter="impl-author"
    )
    record = json.loads((custdir / "custody.json").read_text())
    record["human_boundary_confirmed"] = {"confirmed": True, "confirmer": "mallory"}
    (custdir / "custody.json").write_text(json.dumps(record))
    sealed = tmp_path / "fake-sealed"
    sealed.mkdir()
    (sealed / "custody.json").write_bytes((custdir / "custody.json").read_bytes())
    monkeypatch.setattr(c2, "SEALED_ROOT", sealed)
    assert c2.assess_sealed_custody(custdir, tasks, labels)["qualified_ready"] is False
    (sealed / "custody.json.sig").write_text(
        json.dumps(
            {
                "custodian": "mallory",
                "signed_package_identity": "0" * 64,
                "signature": "forged",
            }
        )
    )
    assert c2.assess_sealed_custody(custdir, tasks, labels)["qualified_ready"] is False


def test_substituted_trusted_key_rejected(tmp_path, monkeypatch):
    anchors = tmp_path / "anchors.json"
    anchors.write_text(
        json.dumps(
            {
                "version": 1,
                "independent_custodians": ["someone-else"],
                "custodians": {
                    "someone-else": {
                        "key_fingerprint": "ab" * 32,
                        "algorithm": "ed25519",
                        "status": "revoked",
                        "expires": None,
                    }
                },
            }
        )
    )
    monkeypatch.setattr(c2, "TRUST_ANCHORS_PATH", anchors)
    loaded = c2.load_trust_anchors()
    assert loaded["custodians"]["someone-else"]["status"] == "revoked"
    assert "someone-else" not in [
        n for n, e in loaded["custodians"].items() if e["status"] == "active"
    ]


def test_caller_modified_policy_blocks_qualification(tmp_path):
    base = json.loads((cust.CUSTODIAN_POLICY_PATH).read_text())
    evil = dict(
        base,
        min_holdout_cases=1,
        min_independent_families=1,
        min_useful_cases=1,
        min_scored_cases=1,
    )
    pol = tmp_path / "evil-policy.json"
    pol.write_text(json.dumps(evil))
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, policy_path=pol)
    assert rec["canonical_policy_match"] is False
    assert rec["custody_state"] != "QUALIFIED"
    assert rec["verdict"] != "PROGRESS"
    assert c2.is_qualified_progress(rec) is False


def test_swapped_contract_blocks_qualification(tmp_path):
    base = json.loads(open(CONTRACT, encoding="utf-8").read())
    evil = dict(base, min_useful_retention=0.99, max_misleading_advance_rate=0.99)
    con = tmp_path / "evil-contract.json"
    con.write_text(json.dumps(evil))
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, contract_path=con)
    assert rec["canonical_contract_match"] is False
    assert rec["custody_state"] != "QUALIFIED"
    assert rec["verdict"] != "PROGRESS"
    assert c2.is_qualified_progress(rec) is False


def test_handwritten_model_outputs_are_unqualified(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20)
    assert rec["fingerprints"]["execution_provenance"] == "offline_fixture_unprovenanced"
    assert rec["fingerprints"]["governed_execution"] is False
    assert rec["custody_state"] != "QUALIFIED"
    assert c2.is_qualified_progress(rec) is False


def test_missing_governed_run_receipts(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20)
    assert rec["fingerprints"]["governed_execution"] is False
    assert rec["fingerprints"]["controls_verified"] is False
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"


def test_v_records_cannot_be_reused_across_arms(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=10, n_families=5)
    outs = _outputs(tasks, perfect=("C", "D"))
    outs["outcomes"]["V"] = [dict(r, arm="V") for r in outs["outcomes"]["D"]]
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    with pytest.raises(ValueError, match="mode does not match"):
        c2.evaluate_v2(
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "r.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_near_duplicate_family_casefold_detected(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        import copy

        data = json.loads((pkg / "tasks.json").read_text())
        src0 = copy.deepcopy(data[0]["sources"][0])
        upper = dict(
            src0, text=src0["text"].upper(), sha256=cust.hash_bytes(src0["text"].upper().encode())
        )
        data[1]["sources"][0] = upper
        for claim in data[1]["claims"]:
            passage = claim.get("passage")
            if passage and passage.get("source_id") == "s0":
                passage.update(start=0, end=len(upper["text"]), text=upper["text"])
        (pkg / "tasks.json").write_text(json.dumps(data))
        tasks[1]["sources"][0] = dict(upper)
        for claim in tasks[1]["claims"]:
            passage = claim.get("passage")
            if passage and passage.get("source_id") == "s0":
                passage.update(start=0, end=len(upper["text"]), text=upper["text"])
        gold_data = json.loads((gold / "annotations.json").read_text())
        for annotation in gold_data:
            if annotation.get("task_id") == data[1]["id"]:
                for span in annotation.get("required_evidence", []):
                    if span.get("source_id") == "s0":
                        span.update(start=0, end=len(upper["text"]), text=upper["text"])
        (gold / "annotations.json").write_text(json.dumps(gold_data))
        for label in labels:
            if label.get("task_id") == data[1]["id"]:
                for span in label.get("required_evidence", []):
                    if span.get("source_id") == "s0":
                        span.update(start=0, end=len(upper["text"]), text=upper["text"])
        task_bytes = json.dumps(data, sort_keys=True).encode()
        gold_bytes = json.dumps(gold_data, sort_keys=True).encode()
        record = json.loads((custdir / "custody.json").read_text())
        record["package_sha256"] = cust.hash_bytes(task_bytes)
        record["gold_sha256"] = cust.hash_bytes(gold_bytes)
        (custdir / "custody.json").write_text(json.dumps(record))

    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, tweak=tweak)
    assert rec["verdict"] == "INCONCLUSIVE"
    assert any("duplicate" in r for r in rec["reasons"])


def test_valid_arm_specific_applicability_counts(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        data = json.loads((pkg / "tasks.json").read_text())
        gold_data = json.loads((gold / "annotations.json").read_text())
        for annotation in gold_data[:5]:
            annotation["status"] = "pending"
        (gold / "annotations.json").write_text(json.dumps(gold_data))
        for label in labels[:5]:
            label["status"] = "pending"
        task_bytes = json.dumps(data, sort_keys=True).encode()
        gold_bytes = json.dumps(gold_data, sort_keys=True).encode()
        record = json.loads((custdir / "custody.json").read_text())
        record["package_sha256"] = cust.hash_bytes(task_bytes)
        record["gold_sha256"] = cust.hash_bytes(gold_bytes)
        record["independent_annotation_status"] = "draft"
        (custdir / "custody.json").write_text(json.dumps(record))

    pkg, gold, custdir, tasks, labels = _package(
        tmp_path, n_tasks=40, n_families=20, adjudicated=False, tweak=tweak
    )
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    rec = c2.evaluate_v2(
        _real_request_good(),
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "r.json",
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": CONTRACT,
        },
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["custody_state"] == "CUSTODY_NOT_ESTABLISHED"
    assert c2.is_qualified_progress(rec) is False


def test_hand_typed_qualified_receipt_rejected(tmp_path):
    forged = {
        "evaluator": "alive-eval-02-v1",
        "custody_state": "QUALIFIED",
        "evaluation_mode": "qualified",
        "verdict": "PROGRESS",
        "diagnostic_result": "IMPROVEMENT_OBSERVED",
        "scientific_qualification": "ESTABLISHED",
        "scope_determined": {"scope": "blind"},
        "fingerprints": {},
    }
    assert c2.is_qualified_progress(forged) is False
    assert c2.is_qualified_progress(None) is False
    assert c2.is_qualified_progress("QUALIFIED") is False
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=10, n_families=5)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    with pytest.raises(ValueError, match="fingerprint|mismatch"):
        c2.verify_receipt(
            forged,
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_substituted_outputs_file_rejected(tmp_path):
    rec, ctx = _run(tmp_path)
    op2 = tmp_path / "outs2.json"
    op2.write_text(json.dumps({"outcomes": {"D": []}}))
    with pytest.raises(ValueError, match="fingerprint|mismatch|task set|map"):
        c2.verify_receipt(
            rec,
            ctx["req"],
            {
                "package_dir": ctx["pkg"],
                "gold_dir": ctx["gold"],
                "outputs_path": op2,
                "custody_dir": ctx["custdir"],
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_legacy_receipts_never_qualify(tmp_path):
    assert (
        c2.is_qualified_progress({"evaluator": "alive-eval-01-v1", "verdict": "PROGRESS"}) is False
    )
    demo = json.loads(
        open("docs/validation/alive-eval-01/demo-receipt.json", encoding="utf-8").read()
    )
    assert c2.is_qualified_progress(demo) is False
    rec, _ = _run(tmp_path)
    assert c2.is_qualified_progress(rec) is False


def test_verify_command_reports_real_enforcement(tmp_path, monkeypatch, capsys):
    import sys

    from scripts import alive_eval02

    monkeypatch.setattr(sys, "argv", ["alive_eval02", "verify"])
    assert alive_eval02.main() == 0
    out = json.loads(capsys.readouterr().out)
    assert out["qualified_reachable"] is False
    assert out["qualified_blockers"]
    assert out["independent_custodians"] == []
