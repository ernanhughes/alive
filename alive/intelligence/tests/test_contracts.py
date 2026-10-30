import subprocess
import sys

import pytest
from pydantic import ValidationError

from alive.intelligence.contracts import CandidateAction, Context, DecisionProposal, Observation
from alive.intelligence.example import inputs


def test_fresh_import_has_no_effects():
    script = """
import sys, socket, subprocess, sqlite3, os, builtins, io
sys.dont_write_bytecode = True
def forbidden(*args, **kwargs):
    raise AssertionError("forbidden import side effect")
real_open, io_open = builtins.open, io.open
def guarded(base):
    def call(file, mode="r", *args, **kwargs):
        if any(x in mode for x in "wax+"):
            forbidden()
        return base(file, mode, *args, **kwargs)
    return call
builtins.open, io.open = guarded(real_open), guarded(io_open)
socket.socket.connect = forbidden
socket.create_connection = forbidden
subprocess.Popen.__init__ = forbidden
sqlite3.connect = forbidden
os.mkdir = os.remove = os.rename = os.replace = forbidden
import alive.intelligence
assert not any(n.startswith("alive.pi") for n in sys.modules)
assert "alive.model_gateway" not in sys.modules
assert "alive.providers" not in sys.modules
assert "alive.db" not in sys.modules
assert "alive.learning.controller" not in sys.modules
"""
    result = subprocess.run([sys.executable, "-B", "-c", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


@pytest.mark.parametrize(
    "field,value",
    [
        ("id", "bad id"),
        ("expected_cost", float("nan")),
        ("expected_risk", float("inf")),
        ("action", "execute_shell"),
        ("proposal", False),
    ],
)
def test_bad_candidates(field, value):
    data = inputs()[1].candidates[0].model_dump()
    data[field] = value
    with pytest.raises(ValidationError):
        CandidateAction.model_validate(data)


def test_immutable_bounded_versioned_serialization():
    observation, context = inputs()
    assert Observation.model_validate_json(observation.model_dump_json()) == observation
    with pytest.raises(ValidationError):
        observation.safe_text = "changed"
    for update in ({"version": 2}, {"safe_text": "x" * 1501}, {"observed_at": "2026-10-30"}):
        with pytest.raises(ValidationError):
            Observation.model_validate(observation.model_dump() | update)
    with pytest.raises(ValidationError):
        Context.model_validate(context.model_dump() | {"candidates": [context.candidates[0]] * 2})
    assert DecisionProposal.model_fields["executed"].annotation.__args__ == (False,)
