# ruff: noqa: E501  (recorded hashes are long literals)
"""The shared seam changes behind the source capabilities leave every earlier identity intact."""

import pytest
import yaml

from alive.capabilities.manifest import ManifestError, manifest_sha256, parse
from alive.capabilities.registry import default_registry
from alive.capabilities.trusted import permission_bits
from tests.conftest import MANIFESTS_DIR

# Recorded from main before the `sources` permission existed. A change here is a change to a
# historical identity: pinned workflows, grants and retained executions all name these hashes.
PRE_EXISTING = {
    "approval.request@1.0.0": "da7e5d473ad14116b29a6c814d67f25928848846d40d2dc219193a6b673121e0",
    "cognition.role@1.0.0": "02346040dfcaaf223dfc355c6bdecb5934069ca5e69ecd671f34f3d14c1c28c5",
    "context.prepare@1.0.0": "f512a8c3e783be751cef5755c27c5980f3ee595fe2032aeecc2cc1a291d64bed",
    "evidence.evaluate@1.0.0": "ae3b17d36c23e592a203d4319cf2296a966e752b1c818d4236b5d48dfada8032",
    "evidence.qualify@1.0.0": "a818afe1b79cc04628ec71de5f7b7d3106e836647d12e9d0d76d3f9b05cdb781",
    "evidence.record@1.0.0": "70cb4dde2e073272aa4c4a1de2d05e6500d0ea66bf1209141fb1a5cf03b50a21",
    "evidence.validate_references@1.0.0": "dcc2ca1d88f925f13bd81e8c39235834e94652aecb127aeccdd29bd3c6e9bd3d",
    "memory.retrieve@1.0.0": "bbc478cfd8f6fafce8619be0b06fbcb711ebc571ea8bfd06933586d80dcdeeb8",
    "repository.inspect@1.0.0": "9c5af82970cf5a9b9b3f77af66c55517f3767f8250042ba89ed30d30ba2844fe",
    "result.record@1.0.0": "9eb884e56453645356940304b4177f135ba34ae0ba242546aba6ef5b045216ca",
}
SOURCE_CAPABILITIES = {
    "repository.inspect@1.1.0",
    "document.extract@1.0.0",
    "browser.prepare-source@1.0.0",
    "retrieval.approved-collection@1.0.0",
}
# L1-02 adds new identities; it changes none of the above.
ANALYSIS_CAPABILITIES = {"repository.analyze@1.0.0", "repository.validate_findings@1.0.0"}
# PI-03C added these four; they change none of the earlier identities.
PI03C_CAPABILITIES = {
    "evidence.verify-locators@1.0.0",
    "evidence.validate_references@1.1.0",
    "evidence.compare-claims@1.0.0",
    "report.compose@1.0.0",
}
# L2-01 adds two more identities and changes none of the above.
INTENT_CAPABILITIES = {"intent.interpret@1.0.0", "intent.validate@1.0.0"}


def test_every_earlier_manifest_keeps_its_exact_hash():
    found = {f"{c.identity['id']}@{c.identity['version']}": c for c in default_registry().list()}
    assert {k: found[k].manifest_sha256 for k in PRE_EXISTING} == PRE_EXISTING
    assert (
        set(found)
        == set(PRE_EXISTING)
        | SOURCE_CAPABILITIES
        | ANALYSIS_CAPABILITIES
        | PI03C_CAPABILITIES
        | INTENT_CAPABILITIES
    )


def declared(path="context.prepare@1.0.0.yaml", **permissions):
    value = yaml.safe_load((MANIFESTS_DIR / path).read_text("utf-8"))
    value["permissions"].update(permissions)
    return value


def test_the_sources_permission_is_canonical_when_unset_and_distinct_when_set():
    omitted = parse(yaml.safe_dump(declared()))
    explicit_none = parse(yaml.safe_dump(declared(sources="none")))
    assert (
        manifest_sha256(omitted)
        == manifest_sha256(explicit_none)
        == PRE_EXISTING["context.prepare@1.0.0"]
    )
    with pytest.raises(ManifestError):  # also refused by the implementation ceiling check
        from alive.capabilities.registry import CapabilityRegistry

        CapabilityRegistry([parse(yaml.safe_dump(declared(sources="approved_capture")))])
    with pytest.raises(ManifestError):
        parse(yaml.safe_dump(declared(sources="anything")))


def test_source_read_is_a_distinct_permission_bit_with_no_other_authority():
    cap = default_registry().get("document.extract")
    permissions = cap.manifest["permissions"]
    assert permissions["sources"] == "approved_capture"
    assert permission_bits(permissions) == {"source.read"}
    assert permissions["filesystem"]["mode"] == "none" and permissions["network"]["mode"] == "none"
    assert permissions["process"]["mode"] == "none" and permissions["persistence"] == "none"
