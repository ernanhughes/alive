"""ALIVE-EVAL-02 qualification-gate tests. Every attack must fail closed.

v1 (`test_alive_eval01.py`) documents the historical mechanism, including two
tests that enshrine self-attested custody as PROGRESS. Those scenarios are
superseded here: the same forgeries run against the v2 evaluator must never
yield a qualified verdict. v1 files are intentionally left untouched.
"""

import hashlib
import json

import pytest

from scripts import alive_eval01_custodian as cust
from scripts import alive_eval02_custodian as c2
from tests.test_alive_eval01 import (
    _outputs,
    _package,
    _real_request_good,
    _task,
    _weaken_c,
)

POLICY = "evaluations/alive-eval-01/custodian_policy.json"
CONTRACT = "evaluations/notebook03a_r2/decision_thresholds.json"


def _run(tmp_path, out="receipt.json", request_tweak=None, **kw):
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
    assert not kw, kw
    pkg, gold, custdir, tasks, labels = _package(tmp_path, **pkg_kwargs)
    outs = _outputs(tasks, perfect=perfect)
    if weaken:
        outs = _weaken_c(outs)
    if arms is not None:
        outs = {"outcomes": {a: outs["outcomes"][a] for a in arms}}
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    submitter = pkg_kwargs.get("submitter", "impl-author")
    req = _real_request_good(submitter=submitter, scope=scope)
    if request_tweak:
        request_tweak(req)
    rec = c2.evaluate_v2(
        req,
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / out,
            "policy_path": cust.CUSTODIAN_POLICY_PATH,
            "contract_path": CONTRACT,
        },
    )
    return rec, {"pkg": pkg, "gold": gold, "custdir": custdir, "op": op, "req": req}


def test_distinct_string_custodian_cannot_progress(tmp_path):
    """Supersedes v1 test_honest_receipt: self-attested custody is unqualified."""
    rec, _ = _run(
        tmp_path,
        n_tasks=30,
        n_families=20,
        custodian="totally-independent-party",
        submitter="impl-author",
    )
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["verdict"] != "PROGRESS"
    assert rec["custody_state"] == "IMPLEMENTED_UNQUALIFIED"
    assert rec["evaluation_mode"] == "diagnostic"
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"
    assert rec["diagnostic_result"] == "IMPROVEMENT_OBSERVED"
    assert c2.is_qualified_progress(rec) is False


def test_public_relabelled_holdout_stays_diagnostic(tmp_path):
    rec, _ = _run(tmp_path, split="public_evaluation")
    assert rec["scope_determined"]["scope"] == "public_diagnostic"
    assert rec["verdict"] == "INCONCLUSIVE"
    assert c2.is_qualified_progress(rec) is False


def test_self_declared_adjudicator_forgery_fails(tmp_path):
    rec, _ = _run(
        tmp_path,
        n_tasks=30,
        n_families=20,
        custodian="independent-review-board",
        submitter="impl-author",
    )
    assert rec["verdict"] != "PROGRESS"
    assert rec["custody_state"] != "QUALIFIED"
    assert c2.is_qualified_progress(rec) is False


def test_evil_protocol_with_recomputed_hash_and_permissive_policy(tmp_path):
    import shutil

    proto_dir = tmp_path / "proto"
    proto_dir.mkdir()
    shutil.copy("evaluations/notebook03a_r2/protocol.json", proto_dir / "protocol.json")
    protocol = json.loads((proto_dir / "protocol.json").read_text())
    protocol["version"] = "evil-v1"
    (proto_dir / "protocol.json").write_text(json.dumps(protocol))
    claimed = hashlib.sha256((proto_dir / "protocol.json").read_bytes()).hexdigest()
    base = json.loads((cust.CUSTODIAN_POLICY_PATH).read_text())
    evil_policy = dict(base, allowed_protocols=[{"version": "evil-v1", "use": "forgery"}])
    pol_path = tmp_path / "evil-policy.json"
    pol_path.write_text(json.dumps(evil_policy))

    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good()
    req["protocol_dir"] = str(proto_dir)
    req["claimed_protocol_sha256"] = claimed
    rec = c2.evaluate_v2(
        req,
        {
            "package_dir": pkg,
            "gold_dir": gold,
            "outputs_path": op,
            "custody_dir": custdir,
            "output_path": tmp_path / "receipt.json",
            "policy_path": pol_path,
            "contract_path": CONTRACT,
        },
    )
    assert rec["verdict"] != "PROGRESS"
    assert rec["custody_state"] != "QUALIFIED"
    assert c2.is_qualified_progress(rec) is False


def test_scorer_substitution_blocked(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req = _real_request_good()
    req["claimed_scorer_version"] = "notebook03a-v9.9"
    with pytest.raises(ValueError, match="scorer"):
        c2.evaluate_v2(
            req,
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "receipt.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_synthetic_outputs_are_diagnostic_only(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20)
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["diagnostic_result"] == "IMPROVEMENT_OBSERVED"
    assert rec["fingerprints"]["execution_provenance"] == "offline_fixture_unprovenanced"
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"


def test_replayed_outputs_from_another_package_fail(tmp_path):
    first, ctx1 = _run(tmp_path, out="r1.json", n_tasks=30, n_families=20)
    other_tasks = [_task(100 + i, i) for i in range(10)]
    outs = _outputs(other_tasks, perfect=("C", "D"))
    (tmp_path / "outs2.json").write_text(json.dumps({"outcomes": outs["outcomes"]}))
    with pytest.raises(ValueError, match="task set"):
        c2.evaluate_v2(
            ctx1["req"],
            {
                "package_dir": ctx1["pkg"],
                "gold_dir": ctx1["gold"],
                "outputs_path": tmp_path / "outs2.json",
                "custody_dir": ctx1["custdir"],
                "output_path": tmp_path / "r2.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )
    second, ctx2 = _run(tmp_path, out="r3.json", n_tasks=10, n_families=5)
    assert first["fingerprints"]["package_identity"] != second["fingerprints"]["package_identity"]
    with pytest.raises(ValueError, match="package identity|fingerprint"):
        c2.verify_receipt(
            first,
            ctx1["req"],
            {
                "package_dir": ctx2["pkg"],
                "gold_dir": ctx2["gold"],
                "outputs_path": ctx2["op"],
                "custody_dir": ctx2["custdir"],
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_rewritten_gold_invalidates_receipt(tmp_path):
    rec, ctx = _run(tmp_path)
    assert (
        c2.verify_receipt(
            rec,
            ctx["req"],
            {
                "package_dir": ctx["pkg"],
                "gold_dir": ctx["gold"],
                "outputs_path": ctx["op"],
                "custody_dir": ctx["custdir"],
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )
        is True
    )
    annotations = json.loads((ctx["gold"] / "annotations.json").read_text())
    annotations[0]["useful_finding"] = False
    (ctx["gold"] / "annotations.json").write_text(json.dumps(annotations))
    with pytest.raises(ValueError, match="fingerprint|mismatch"):
        c2.verify_receipt(
            rec,
            ctx["req"],
            {
                "package_dir": ctx["pkg"],
                "gold_dir": ctx["gold"],
                "outputs_path": ctx["op"],
                "custody_dir": ctx["custdir"],
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_fabricated_controls_cannot_qualify(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, perfect=("C", "D", "S", "V"), weaken=False)
    assert rec["verdict"] == "NO_PROGRESS"
    assert rec["diagnostic_result"] == "NO_IMPROVEMENT_OBSERVED"
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"
    assert c2.is_qualified_progress(rec) is False


def test_family_label_manipulation_is_detected(tmp_path):
    def tweak(pkg, gold, custdir, tasks, labels):
        import copy

        data = json.loads((pkg / "tasks.json").read_text())
        src0 = copy.deepcopy(data[0]["sources"][0])
        data[1]["sources"][0] = src0
        for claim in data[1]["claims"]:
            passage = claim.get("passage")
            if passage and passage.get("source_id") == "s0":
                passage["start"] = 0
                passage["end"] = len(src0["text"])
                passage["text"] = src0["text"]
        (pkg / "tasks.json").write_text(json.dumps(data))
        tasks[1]["sources"][0]["text"] = src0["text"]
        tasks[1]["sources"][0]["sha256"] = src0["sha256"]
        for claim in tasks[1]["claims"]:
            passage = claim.get("passage")
            if passage and passage.get("source_id") == "s0":
                passage["start"] = 0
                passage["end"] = len(src0["text"])
                passage["text"] = src0["text"]
        gold_data = json.loads((gold / "annotations.json").read_text())
        for annotation in gold_data:
            if annotation.get("task_id") == data[1]["id"]:
                for span in annotation.get("required_evidence", []):
                    if span.get("source_id") == "s0":
                        span["start"] = 0
                        span["end"] = len(src0["text"])
                        span["text"] = src0["text"]
        (gold / "annotations.json").write_text(json.dumps(gold_data))
        for label in labels:
            if label.get("task_id") == data[1]["id"]:
                for span in label.get("required_evidence", []):
                    if span.get("source_id") == "s0":
                        span["start"] = 0
                        span["end"] = len(src0["text"])
                        span["text"] = src0["text"]
        task_bytes = json.dumps([t for t in data], sort_keys=True).encode()
        gold_data = json.loads((gold / "annotations.json").read_text())
        gold_bytes = json.dumps(gold_data, sort_keys=True).encode()
        record = json.loads((custdir / "custody.json").read_text())
        record["package_sha256"] = cust.hash_bytes(task_bytes)
        record["gold_sha256"] = cust.hash_bytes(gold_bytes)
        (custdir / "custody.json").write_text(json.dumps(record))

    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, tweak=tweak)
    assert rec["verdict"] == "INCONCLUSIVE"
    assert any("duplicate" in r for r in rec["reasons"])
    assert c2.is_qualified_progress(rec) is False


def test_bootstrap_seed_pinned(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _weaken_c(_outputs(tasks, perfect=("C", "D")))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    bad_contract = dict(json.loads(open(CONTRACT, encoding="utf-8").read()))
    bad_contract["bootstrap_seed"] = 1
    bad_path = tmp_path / "contract.json"
    bad_path.write_text(json.dumps(bad_contract))
    with pytest.raises(ValueError, match="not caller-tunable"):
        c2.evaluate_v2(
            _real_request_good(),
            {
                "package_dir": pkg,
                "gold_dir": gold,
                "outputs_path": op,
                "custody_dir": custdir,
                "output_path": tmp_path / "r.json",
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": bad_path,
            },
        )
    first, _ = _run(tmp_path, out="a.json")
    second, _ = _run(tmp_path, out="b.json")
    assert first["uncertainty"] == second["uncertainty"]
    assert first["fingerprints"]["outputs_sha256"] == second["fingerprints"]["outputs_sha256"]


def test_receipt_tampering_rejected(tmp_path):
    rec, ctx = _run(tmp_path)
    paths = {
        "package_dir": ctx["pkg"],
        "gold_dir": ctx["gold"],
        "outputs_path": ctx["op"],
        "custody_dir": ctx["custdir"],
        "policy_path": cust.CUSTODIAN_POLICY_PATH,
        "contract_path": CONTRACT,
    }
    forged = dict(rec, verdict="PROGRESS", custody_state="QUALIFIED")
    with pytest.raises(ValueError, match="mismatch"):
        c2.verify_receipt(forged, ctx["req"], paths)
    stripped = {k: v for k, v in rec.items() if k != "fingerprints"}
    with pytest.raises(ValueError, match="required field"):
        c2.verify_receipt(stripped, ctx["req"], paths)
    assert c2.is_qualified_progress({"verdict": "PROGRESS"}) is False
    assert c2.is_qualified_progress(rec) is False


def test_valid_diagnostic_evaluation_reports_improvement(tmp_path):
    rec, ctx = _run(tmp_path, n_tasks=30, n_families=20)
    assert rec["verdict"] == "INCONCLUSIVE"
    assert rec["custody_state"] == "IMPLEMENTED_UNQUALIFIED"
    assert rec["evaluation_mode"] == "diagnostic"
    assert rec["diagnostic_result"] == "IMPROVEMENT_OBSERVED"
    assert rec["scientific_qualification"] == "NOT_ESTABLISHED"
    assert rec["scope_determined"]["scope"] == "blind"
    assert c2.is_qualified_progress(rec) is False
    assert (
        c2.verify_receipt(
            rec,
            ctx["req"],
            {
                "package_dir": ctx["pkg"],
                "gold_dir": ctx["gold"],
                "outputs_path": ctx["op"],
                "custody_dir": ctx["custdir"],
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )
        is True
    )


def test_qualified_unreachable_without_anchor(tmp_path):
    import json as _json

    anchors = _json.loads((c2.EVAL02_ROOT / "trust_anchors.json").read_text())
    assert anchors["independent_custodians"] == []
    sealed = list((c2.EVAL02_ROOT / "sealed").glob("*.json"))
    assert sealed == []
    rec, _ = _run(tmp_path)
    assert rec["custody_state"] != "QUALIFIED"
    assert "no sealed custody artifact" in rec["custody_reason"]


def test_v1_receipts_rejected_as_qualified(tmp_path):
    assert (
        c2.is_qualified_progress({"evaluator": "alive-eval-01-v1", "verdict": "PROGRESS"}) is False
    )
    demo = json.loads(
        open("docs/validation/alive-eval-01/demo-receipt.json", encoding="utf-8").read()
    )
    assert c2.is_qualified_progress(demo) is False
    with pytest.raises(ValueError, match="not a v2 receipt"):
        c2.verify_receipt(
            demo,
            _real_request_good(),
            {
                "package_dir": tmp_path,
                "gold_dir": tmp_path,
                "outputs_path": tmp_path / "missing.json",
                "custody_dir": None,
                "policy_path": cust.CUSTODIAN_POLICY_PATH,
                "contract_path": CONTRACT,
            },
        )


def test_structural_invalid_inputs_fail_closed(tmp_path):
    rec, _ = _run(tmp_path, custodian="impl-author", submitter="impl-author")
    assert rec["custody_state"] == "CUSTODY_NOT_ESTABLISHED"
    assert rec["verdict"] == "INCONCLUSIVE"
    assert c2.is_qualified_progress(rec) is False


def test_counts_must_agree_across_arms():
    good = {
        "D": {"useful_findings": 20, "scored_tasks": 30},
        "C": {"useful_findings": 20, "scored_tasks": 30},
        "S": {"useful_findings": 20, "scored_tasks": 30},
        "V": {"useful_findings": 20, "scored_tasks": 30},
    }
    assert c2.require_consistent_counts(good, ["A", "B0", "S", "V", "C", "D"]) == {
        "useful": 20,
        "scored": 30,
    }
    bad = dict(good, D={"useful_findings": 19, "scored_tasks": 30})
    with pytest.raises(ValueError, match="inconsistent arm counts"):
        c2.require_consistent_counts(bad, ["A", "B0", "S", "V", "C", "D"])


def test_intervals_deterministic(tmp_path):
    first, _ = _run(tmp_path, n_tasks=30, n_families=20, out="a.json")
    second, _ = _run(tmp_path, n_tasks=30, n_families=20, out="b.json")
    assert first["uncertainty"] == second["uncertainty"]
    assert first["decision_diagnostics"]["paired"] == second["decision_diagnostics"]["paired"]


def test_v_gate_blocks_regression_vs_shortcut(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, perfect=("S", "V", "C"))
    assert rec["verdict"] == "NO_PROGRESS"
    assert rec["diagnostic_result"] == "NO_IMPROVEMENT_OBSERVED"
    assert any("V control" in r for r in rec["reasons"])


def test_c_gate_does_not_veto(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, perfect=("D",))
    assert rec["diagnostic_result"] == "IMPROVEMENT_OBSERVED"
    assert rec["decision_diagnostics"]["comparator_diagnostics"]["C_absolute"]["vetoes_D"] is False


def test_straddling_intervals_are_inconclusive_not_failure(tmp_path):
    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=30, n_families=20)
    outs = _outputs(tasks, perfect=("D",))
    for rec_item in outs["outcomes"]["D"][:14]:
        rec_item.update(
            relationship="unknown",
            sufficiency="insufficient",
            applicability="unknown",
            action="abstain",
            evidence=[],
        )
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
    assert rec["diagnostic_result"] == "INDETERMINATE"


def test_missing_arm_is_indeterminate(tmp_path):
    rec, _ = _run(tmp_path, n_tasks=30, n_families=20, arms=("A", "B0", "S", "V", "D"))
    assert rec["verdict"] == "INCONCLUSIVE"
    assert any("C" in r for r in rec["reasons"])


def test_cli_verify_evaluate_verify_receipt(tmp_path, monkeypatch, capsys):
    import sys

    from scripts import alive_eval02

    pkg, gold, custdir, tasks, labels = _package(tmp_path, n_tasks=10, n_families=5)
    outs = _outputs(tasks, perfect=("C", "D"))
    op = tmp_path / "outs.json"
    op.write_text(json.dumps(outs))
    req_path = tmp_path / "request.json"
    req_path.write_text(json.dumps(_real_request_good()))
    monkeypatch.setattr(sys, "argv", ["alive_eval02", "verify"])
    assert alive_eval02.main() == 0
    assert "POLICY_VALID" in capsys.readouterr().out
    out_path = tmp_path / "receipt.json"
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alive_eval02",
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
            CONTRACT,
            "--protocol-dir",
            "evaluations/notebook03a_r2",
            "--request",
            str(req_path),
            "--output",
            str(out_path),
        ],
    )
    assert alive_eval02.main() == 0
    assert out_path.exists()
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "alive_eval02",
            "verify-receipt",
            "--receipt",
            str(out_path),
            "--package",
            str(pkg),
            "--gold",
            str(gold),
            "--outputs",
            str(op),
            "--custody",
            str(custdir),
            "--contract",
            CONTRACT,
            "--protocol-dir",
            "evaluations/notebook03a_r2",
            "--request",
            str(req_path),
        ],
    )
    assert alive_eval02.main() == 0
    assert '"valid": true' in capsys.readouterr().out
