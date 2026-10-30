import pytest
from pydantic import ValidationError

from alive import living_policy
from alive.intelligence.example import inputs
from alive.intelligence.policies.empirical import Cell, EmpiricalPolicy
from alive.intelligence.policies.predictive import (
    ORDER_VERSION,
    PredictiveShadow,
    SimulationState,
    controller_hash,
)


def test_actual_empirical_policy_parity_unknown_samples_ties_and_update():
    p = EmpiricalPolicy(origin="fixture")
    candidates = inputs()[1].candidates
    action, raw = p.rank(candidates)
    assert action.action == "monitor"
    assert raw == living_policy.choose(p.data(), p.context_key)
    assert raw["predictions"]["retrieve"]["n"] == 0
    assert raw["predictions"]["retrieve"]["status"] == "unknown; zero prior"
    updated = p.updated("monitor", -0.5)
    assert updated.data() == living_policy.update(p.data(), "monitor", -0.5, p.context_key)
    assert updated.rank(candidates)[0].action == "retrieve"
    assert p.monitor.n == 0 and updated.monitor.n == 1
    assert EmpiricalPolicy.model_validate_json(updated.snapshot_json()) == updated


def test_policy_origin_and_sample_validation():
    live, fixture = EmpiricalPolicy(origin="live"), EmpiricalPolicy(origin="fixture")
    assert live.context_key == living_policy.CONTEXT
    assert fixture.context_key.endswith("/controlled-fixture")
    assert live.hash != fixture.hash
    with pytest.raises(ValidationError):
        Cell(n=0, total=1)
    with pytest.raises(ValidationError):
        EmpiricalPolicy(origin="fixture", revision=1)
    with pytest.raises(ValidationError):
        EmpiricalPolicy(origin="simulator")


def test_predictive_unavailable_without_qualified_existing_checkpoint():
    # No qualified saved checkpoint supplied in this checkout. Never synthesize trained weights.
    assert PredictiveShadow().compare(None).status == "unavailable"
    assert (
        PredictiveShadow(controller=object(), checkpoint_hash="a" * 64, verifier=object())
        .compare(None)
        .status
        == "unavailable"
    )


def test_predictive_parameter_integrity_and_qualification_rejects_random_controller():
    from alive.learning.controller import Controller

    class Unqualified:
        def qualified(self, identity):
            return False

    # Existing Controller's random initialization is explicitly NOT a trained checkpoint.
    controller = Controller()
    identity = controller_hash(controller)
    original = {k: v.copy() for k, v in controller.p.items()}
    adapter = PredictiveShadow(
        controller=controller, checkpoint_hash=identity, verifier=Unqualified()
    )
    assert adapter.compare(None).status == "unavailable"
    assert controller.updates == 0
    assert all((controller.p[k] == value).all() for k, value in original.items())
    controller.p["E"] = controller.p["E"][:1]
    with pytest.raises(ValueError):
        controller_hash(controller)


def test_explicit_exact_simulation_state_and_mask():
    from alive.learning.environment import ACTIONS, FEATURES

    data = dict(
        ordering=ORDER_VERSION,
        features=FEATURES,
        actions=ACTIONS,
        values=(0.0,) * 18,
        mask=(False,) * 5 + (True,),
    )
    state = SimulationState(**data)
    assert state.features == FEATURES and state.actions == ACTIONS
    for update in ({"values": (0,) * 17}, {"values": (float("nan"),) * 18}, {"mask": (1,) * 6}):
        with pytest.raises(ValidationError):
            SimulationState.model_validate(data | update)
    for update in (
        {"ordering": "unknown"},
        {"features": tuple(reversed(FEATURES))},
        {"actions": tuple(reversed(ACTIONS))},
        {"mask": (False,) * 6},
    ):
        assert PredictiveShadow().compare(data | update).status == "unavailable"
