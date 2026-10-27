"""First-party synthetic evidence-control environment with action-dependent transitions."""

import hashlib
from dataclasses import dataclass

import numpy as np

ACTIONS = ("retrieve", "investigate", "critic", "accept", "reject", "monitor")
FAMILIES = ("history", "reasoning", "misleading", "routine")
FEATURES = (
    "belief",
    "uncertainty",
    "memory_hint",
    "complexity_hint",
    "source_warning",
    "importance",
    "error_risk",
    "cost_multiplier",
    "budget",
    "time_remaining",
    "retrieved",
    "investigated",
    "reviewed",
    "evidence_coverage",
    "topic_0",
    "topic_1",
    "topic_2",
    "topic_3",
)
COSTS = np.array([0.045, 0.13, 0.075, 0.20, 0.20, 0.0])


def rng_for(*parts):
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return np.random.default_rng(int.from_bytes(digest[:8], "little"))


@dataclass(frozen=True)
class Scenario:
    split: str
    index: int
    family: str

    @property
    def id(self):
        return hashlib.sha256(f"alive-p2-v1|{self.split}|{self.index}".encode()).hexdigest()[:24]


def scenarios(split, n):
    if split not in {"train", "development", "test"} or n % 4:
        raise ValueError("Named split and balanced four-family count required")
    return [Scenario(split, i, FAMILIES[i % 4]) for i in range(n)]


class EvidenceWorld:
    """Four-step episodic simulator. Hidden truth is never part of observation()."""

    def __init__(self, scenario):
        self.scenario = scenario
        rng = rng_for(scenario.id)
        self.truth = bool(rng.integers(2))
        self.importance = float(rng.uniform(0.08, 1))
        self.risk = float(rng.uniform(0.4, 1.4))
        self.multiplier = float(rng.uniform(0.65, 1.5))
        self.budget = float(rng.uniform(0.5, 0.9))
        self.topic = rng.uniform(-1, 1, 4)
        family = scenario.family
        hints = np.array([family == "history", family == "reasoning", family == "misleading"])
        self.hints = np.clip(0.15 + 0.65 * hints + rng.normal(0, 0.12, 3), 0, 1)
        accuracy = 0.94 if family == "routine" else 0.3 if family == "misleading" else 0.67
        initial = self.truth if rng.random() < accuracy else not self.truth
        # Misleading evidence is overconfident; review can repair the unsupported prior.
        declared = 0.88 if family == "misleading" else accuracy
        self.log_odds = (1 if initial else -1) * np.log(declared / (1 - declared))
        self.used = np.zeros(3, dtype=bool)
        self.step_number = 0
        self.done = False
        self.total_cost = 0.0
        self.total_reward = 0.0

    def observation(self):
        p = 1 / (1 + np.exp(-self.log_odds))
        return np.array(
            [
                p,
                1 - abs(2 * p - 1),
                *self.hints,
                self.importance,
                self.risk,
                self.multiplier / 1.5,
                self.budget,
                (4 - self.step_number) / 4,
                *self.used.astype(float),
                float(self.used.mean()),
                *self.topic,
            ],
            dtype=np.float64,
        )

    def valid_actions(self):
        if self.done:
            return np.zeros(6, dtype=bool)
        valid = COSTS * self.multiplier <= self.budget + 1e-12
        valid[:3] &= ~self.used
        if self.step_number == 3:
            valid[:3] = False  # Must decide by the last step; monitor always remains available.
        valid[5] = True
        return valid

    def step(self, action):
        if not isinstance(action, (int, np.integer)) or not 0 <= action < 6:
            raise ValueError("Unknown simulator action")
        if not self.valid_actions()[action]:
            raise ValueError("Simulator Governor rejected exhausted, repeated or terminal action")
        before = self.observation()
        before_mask = self.valid_actions()
        cost = float(COSTS[action] * self.multiplier)
        self.budget -= cost
        self.total_cost += cost
        self.step_number += 1
        reward = -cost
        event = {"kind": ACTIONS[action], "source": "synthetic simulator"}
        if action < 3:
            self.used[action] = True
            family = self.scenario.family
            quality = [
                0.96 if family == "history" else 0.58,
                0.96 if family == "reasoning" else 0.75,
                0.96 if family == "misleading" else 0.56,
            ][action]
            draw = rng_for(self.scenario.id, ACTIONS[action]).random()
            signal = self.truth if draw < quality else not self.truth
            if action == 2 and family == "misleading":
                self.log_odds = 0.0
            self.log_odds = float(
                np.clip(
                    self.log_odds + (1 if signal else -1) * np.log(quality / (1 - quality)), -8, 8
                )
            )
            event |= {"observed_signal": bool(signal), "declared_reliability": quality}
        else:
            self.done = True
            if action != 5:
                correct = (action == 3) == self.truth
                reward += self.importance if correct else -self.risk
        self.total_reward += reward
        after = self.observation()
        return {
            "scenario_id": self.scenario.id,
            "split": self.scenario.split,
            "state": before.tolist(),
            "valid_actions": before_mask.tolist(),
            "action": int(action),
            "reward": reward,
            "next_state": after.tolist(),
            "done": self.done,
            "next_valid_actions": self.valid_actions().tolist(),
            "cost": cost,
            "observation": event,
        }

    def outcome(self, terminal_action):
        if not self.done:
            raise ValueError("An incomplete episode has no outcome")
        factual = (self.observation()[0] >= 0.5) == self.truth
        # Privileged full-information decision reference; not a training input or policy feature.
        oracle = 5 if self.importance <= 0.20 * self.multiplier else 3 if self.truth else 4
        return {
            "factual_correct": bool(factual),
            "decision_correct": terminal_action == oracle,
            "monitor": terminal_action == 5,
            "return": self.total_reward,
            "cost": self.total_cost,
            "terminal_action": ACTIONS[terminal_action],
            "oracle_terminal_action": ACTIONS[oracle],
        }


def heuristic(state, mask):
    p, uncertainty, memory, complexity, warning = state[:5]
    if state[5] > 0.3 and uncertainty > 0.3:
        ranked = sorted([(memory, 0), (complexity, 1), (warning, 2)], reverse=True)
        for hint, action in ranked:
            if hint > 0.55 and mask[action]:
                return action
    values = [p * state[5] - (1 - p) * state[6], (1 - p) * state[5] - p * state[6]]
    for i in range(2):
        values[i] -= 0.20 * (state[7] * 1.5)
        if not mask[3 + i]:
            values[i] = -np.inf
    return 3 + int(np.argmax(values)) if max(values) > 0 else 5


def collect(items):
    transitions = []
    for scenario in items:
        world = EvidenceWorld(scenario)
        rng = rng_for("behavior", scenario.id)
        while not world.done:
            mask = world.valid_actions()
            action = (
                heuristic(world.observation(), mask)
                if rng.random() < 0.5
                else int(rng.choice(np.flatnonzero(mask)))
            )
            transitions.append(world.step(action))
    return transitions
