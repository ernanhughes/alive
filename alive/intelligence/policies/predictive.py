"""Optional hash-bound Controller snapshot. No load, random initialization, training or save."""

import copy
import hashlib

from pydantic import Field, StrictBool

from ..contracts import ID, Contract, Number, ShadowResult

ORDER_VERSION = "alive.learning.environment/18x6/v1"


class SimulationState(Contract):
    ordering: ID
    features: tuple[ID, ...] = Field(min_length=18, max_length=18)
    actions: tuple[ID, ...] = Field(min_length=6, max_length=6)
    values: tuple[Number, ...] = Field(min_length=18, max_length=18)
    mask: tuple[StrictBool, ...] = Field(min_length=6, max_length=6)


def controller_hash(controller):
    """Canonical parameter identity, distinct from an on-disk NPZ container hash."""
    import numpy as np

    shapes = {
        "E": (18, 32),
        "Eb": (32,),
        "Q": (32, 6),
        "Qb": (6,),
        "T": (38, 32),
        "Tb": (32,),
        "R": (38, 1),
        "Rb": (1,),
        "O": (38, 18),
        "Ob": (18,),
    }
    hasher = hashlib.sha256(ORDER_VERSION.encode())
    for group in (controller.p, controller.target):
        if set(group) != set(shapes):
            raise ValueError("Checkpoint parameter keys")
        for key, shape in sorted(shapes.items()):
            value = np.asarray(group[key])
            if value.shape != shape or not np.isfinite(value).all():
                raise ValueError("Checkpoint shape or numerical mismatch")
            hasher.update(key.encode())
            hasher.update(np.asarray(value, dtype="<f8").tobytes(order="C"))
    return hasher.hexdigest()


class PredictiveShadow:
    def __init__(self, *, controller=None, checkpoint_hash=None, verifier=None):
        self._snapshot = None
        self._hash = checkpoint_hash
        self._verifier = verifier
        if controller is None or verifier is None or checkpoint_hash is None:
            return
        try:
            from alive.learning.controller import Controller

            if type(controller) is not Controller or controller_hash(controller) != checkpoint_hash:
                return
            if verifier.qualified(checkpoint_hash) is not True:
                return
            self._snapshot = copy.deepcopy(controller)
        except Exception:
            self._snapshot = None

    def compare(self, state):
        unavailable = ShadowResult(
            status="unavailable", explanation="Qualified checkpoint/state unavailable."
        )
        try:
            if self._snapshot is None or self._verifier.qualified(self._hash) is not True:
                return unavailable
            import numpy as np

            from alive.learning.environment import ACTIONS, FEATURES

            state = SimulationState.model_validate(state)
            if (
                state.ordering != ORDER_VERSION
                or state.features != FEATURES
                or state.actions != ACTIONS
                or not any(state.mask)
                or controller_hash(self._snapshot) != self._hash
            ):
                return unavailable
            x, mask = np.array(state.values), np.array(state.mask)
            q = self._snapshot.q(x)
            action = self._snapshot.choose(x, mask)
            predicted = self._snapshot.predict(x, action)
            return ShadowResult(
                status="available",
                explanation="Simulation-only probe; no demonstrated predictive advantage.",
                checkpoint_hash=self._hash,
                action=ACTIONS[action],
                q_values=tuple(q),
                permitted=state.mask,
                predicted_reward=predicted["reward"],
                predicted_next_state=tuple(predicted["next_state"]),
            )
        except Exception:
            return unavailable
