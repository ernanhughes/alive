"""In-memory mutations only; run each in a fresh subprocess."""
import ast
import inspect
import sys
import textwrap

import pytest

mode = sys.argv[1]
if mode == "references":
    import alive.society as module
    module.validate_references = lambda output, context: None
    targets = ["tests/test_cognition.py::test_attention_protocol_and_evidence_integrity"]
elif mode == "capture-hash":
    import alive.web_experience as module
    tree = ast.parse(textwrap.dedent(inspect.getsource(module.WebCompanion.snapshot)))
    function = tree.body[0]
    assert isinstance(function.body[0], ast.If)
    function.body[0].test = ast.Constant(False)
    ast.fix_missing_locations(tree)
    scope = {}
    exec(compile(tree, "<audit-in-memory-hash-mutation>", "exec"), module.__dict__, scope)
    module.WebCompanion.snapshot = scope["snapshot"]
    targets = ["tests/test_web_experience.py::test_exact_consent_hash_and_owner_goal_isolation"]
else:
    raise SystemExit("unknown mutation")

code = pytest.main(["-q", "--tb=short", *targets])
print("MUTATION", mode, "KILLED" if code == 1 else "UNRESOLVED", "pytest_exit", code)
raise SystemExit(0 if code == 1 else 1)
