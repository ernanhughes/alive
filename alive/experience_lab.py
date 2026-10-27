"""Controlled experience-learning lab for ALIVE-08.

The simulator is deliberately separate from the live browser runtime. It reuses ALIVE's existing
empirical action-value policy (`alive.living_policy.choose/update`) for the learned arm, while
keeping environment outcomes independent of any model self-assessment.
"""

import hashlib
import json
import random
import time
import uuid
from collections import defaultdict
from pathlib import Path

import numpy as np

from alive.living_policy import ACTIONS, choose, digest, update

POLICY_VERSION = "alive08-contextual-experience-v1"
ACTION_COST = {"monitor": 0.0, "retrieve": 0.20}
MISS_PENALTY = 1.0
RETRIEVE_GAIN = 1.0
FEEDBACK_NOISE = 0.10
AGE_FACTOR = {"recent": 0.5, "day": 0.8, "week": 1.2, "stale": 1.8}
SOURCE_CLASSES = {
    "stable": {
        "base_p": 0.04,
        "cadence": {"static": 0.60, "weekly": 0.30, "daily": 0.10},
    },
    "episodic": {
        "base_p": 0.22,
        "cadence": {"daily": 0.40, "weekly": 0.40, "hourly": 0.20},
    },
    "volatile": {
        "base_p": 0.45,
        "cadence": {"hourly": 0.50, "daily": 0.30, "weekly": 0.20},
    },
    "novel": {
        "base_p": 0.65,
        "cadence": {"daily": 0.50, "weekly": 0.30, "hourly": 0.20},
    },
}
AGE_VALUES = ["recent", "day", "week", "stale"]
AGE_WEIGHTS = [0.30, 0.30, 0.25, 0.15]
SEEDS = [17, 23, 31, 43, 59]
SPLIT_SIZES = {"development": 40, "calibration": 100, "training": 200, "evaluation": 300}
OBSERVATION_KEYS = {
    "source_id",
    "cadence",
    "claim_age",
    "claim",
    "goal",
    "permitted_actions",
}


def utility(action, changed):
    """Independent task utility. No model output is consulted."""

    if action not in ACTIONS:
        raise ValueError("Unknown action")
    if action == "retrieve":
        return RETRIEVE_GAIN - ACTION_COST[action] if changed else -ACTION_COST[action]
    return -MISS_PENALTY if changed else 0.0


def observation(scenario):
    return {key: scenario["observation"][key] for key in OBSERVATION_KEYS}


def weighted_choice(rng, values):
    return rng.choices(list(values), weights=list(values.values()), k=1)[0]


def _source(seed, split, index, source_class, rng):
    spec = SOURCE_CLASSES[source_class]
    source_id = "src-" + uuid.uuid5(uuid.NAMESPACE_URL, f"alive08:{seed}:{split}:{index}").hex[:12]
    return {
        "source_id": source_id,
        "source_class": source_class,
        "base_p": max(0.01, min(0.90, spec["base_p"] + rng.gauss(0, 0.08))),
        "cadence": spec["cadence"],
    }


def _episode(rng, seed, split, index, source, source_status):
    cadence = weighted_choice(rng, source["cadence"])
    claim_age = rng.choices(AGE_VALUES, weights=AGE_WEIGHTS, k=1)[0]
    p_change = max(0.01, min(0.90, source["base_p"] * AGE_FACTOR[claim_age]))
    changed = rng.random() < p_change
    feedback_noise = rng.random() < FEEDBACK_NOISE
    scenario = {
        "scenario_id": f"{split}-{seed}-{index:05d}",
        "seed": seed,
        "split": split,
        "source_status": source_status,
        "observation": {
            "source_id": source["source_id"],
            "cadence": cadence,
            "claim_age": claim_age,
            "claim": round(rng.uniform(20.0, 40.0), 1),
            "goal": "Keep the source's current measurement accurate.",
            "permitted_actions": list(ACTIONS),
        },
        "hidden": {
            "source_class": source["source_class"],
            "p_change": p_change,
            "changed": changed,
            "feedback_noise_bit": feedback_noise,
        },
    }
    return scenario


def generate_corpus(seeds=None):
    """Generate deterministic development, calibration, training and evaluation splits."""

    seeds = seeds or SEEDS
    corpus = {name: [] for name in SPLIT_SIZES}
    for seed in seeds:
        rng = random.Random(seed * 1009)
        dev_sources = [
            _source(seed, "development", index, cls, rng)
            for index, cls in enumerate(["stable", "episodic", "volatile"] * 6)
        ]
        training_sources = [
            _source(seed, "training", index, cls, rng)
            for index, cls in enumerate(["stable", "episodic", "volatile"] * 10)
        ]
        unseen_sources = [
            _source(seed, "evaluation-unseen", index, cls, rng)
            for index, cls in enumerate(["stable", "episodic", "volatile"] * 4)
        ]
        novel_sources = [
            _source(seed, "evaluation-novel", index, "novel", rng) for index in range(4)
        ]
        for index in range(SPLIT_SIZES["development"]):
            source = rng.choice(dev_sources)
            corpus["development"].append(
                _episode(rng, seed, "development", index, source, "development")
            )
        for index in range(SPLIT_SIZES["calibration"]):
            source = rng.choice(training_sources)
            corpus["calibration"].append(
                _episode(rng, seed, "calibration", index, source, "calibration_seen")
            )
        for index in range(SPLIT_SIZES["training"]):
            source = rng.choice(training_sources)
            corpus["training"].append(_episode(rng, seed, "training", index, source, "train"))
        for index in range(SPLIT_SIZES["evaluation"]):
            if index < 150:
                source, status = rng.choice(training_sources), "seen"
            elif index < 250:
                source, status = rng.choice(unseen_sources), "unseen"
            else:
                source, status = rng.choice(novel_sources), "novel"
            corpus["evaluation"].append(_episode(rng, seed, "evaluation", index, source, status))
    return corpus


def write_corpora(root, seeds=None):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    corpus = generate_corpus(seeds)
    for split, rows in corpus.items():
        path = root / f"{split}.jsonl"
        path.write_text(
            "\n".join(json.dumps(row, ensure_ascii=False) for row in rows) + "\n",
            encoding="utf-8",
        )
    hashes = {
        split: hashlib.sha256((root / f"{split}.jsonl").read_bytes()).hexdigest()
        for split in corpus
    }
    environment = {
        "policy_version": POLICY_VERSION,
        "actions": list(ACTIONS),
        "action_cost": ACTION_COST,
        "miss_penalty": MISS_PENALTY,
        "retrieve_gain": RETRIEVE_GAIN,
        "feedback_noise": FEEDBACK_NOISE,
        "age_factor": AGE_FACTOR,
        "age_values": AGE_VALUES,
        "age_weights": AGE_WEIGHTS,
        "source_classes": SOURCE_CLASSES,
        "observation_keys": sorted(OBSERVATION_KEYS),
        "source_identity": "Random UUID-derived IDs; class is never encoded in the ID.",
    }
    (root / "environment.json").write_text(
        json.dumps(environment, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    seeds_data = {
        "seeds": list(seeds or SEEDS),
        "split_sizes": SPLIT_SIZES,
        "corpus_hashes": hashes,
    }
    (root / "seeds.json").write_text(
        json.dumps(seeds_data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return corpus, environment, seeds_data


class ExperimentGovernor:
    """Controlled action envelope. It cannot grant new permissions or provider budget."""

    def __init__(self, allowed_actions=None, episode_budget=0.20):
        self.allowed_actions = frozenset(allowed_actions or ACTIONS)
        self.episode_budget = episode_budget
        self.spent = 0.0
        self.denied = []

    def reset(self):
        self.spent = 0.0

    def authorize(self, action):
        if action not in self.allowed_actions:
            self.denied.append({"action": action, "reason": "unsupported_action"})
            return False
        cost = ACTION_COST[action]
        if self.spent + cost > self.episode_budget:
            self.denied.append({"action": action, "reason": "episode_budget"})
            return False
        self.spent += cost
        return True


class BaseAgent:
    name = "base"

    def decide(self, obs):
        raise NotImplementedError

    def learn(self, transition, reward_override=None):
        return None

    def reset(self):
        return None

    def state_hash(self):
        return digest({"agent": self.name})


class StatelessPrior(BaseAgent):
    name = "stateless_prior"

    def decide(self, obs):
        action = "retrieve" if obs["cadence"] in {"hourly", "daily"} else "monitor"
        return action, {
            "context": "stateless_prior",
            "context_count": 0,
            "policy_version": 0,
            "policy_hash": digest({"policy": self.name}),
            "recalled_ids": [],
        }

    def state_hash(self):
        return digest({"policy": self.name})


class FixedHeuristic(BaseAgent):
    name = "fixed_heuristic"

    def decide(self, obs):
        retrieve = obs["cadence"] == "hourly" or (
            obs["cadence"] == "daily" and obs["claim_age"] in {"week", "stale"}
        )
        return ("retrieve" if retrieve else "monitor"), {
            "context": "fixed_heuristic",
            "context_count": 0,
            "policy_version": 0,
            "policy_hash": digest({"policy": self.name}),
            "recalled_ids": [],
        }

    def state_hash(self):
        return digest({"policy": self.name})


class _EmpiricalBase(BaseAgent):
    def __init__(self):
        self.policy = {"version": 0, "contexts": {}}
        self.history = []

    def reset(self):
        self.policy = {"version": 0, "contexts": {}}
        self.history = []

    def state_hash(self):
        return digest(self.policy)

    def _count(self, context):
        return sum(cell["n"] for cell in self.policy["contexts"].get(context, {}).values())

    def _recalled(self, contexts, limit=4):
        rows = [
            row["transition_id"]
            for row in self.history
            if any(context in row["contexts"] for context in contexts)
        ]
        return rows[-limit:]

    def learn(self, transition, reward_override=None):
        reward = transition["observed_reward"] if reward_override is None else reward_override
        for context in transition["contexts"]:
            self.policy = update(self.policy, transition["action"], reward, context)
        self.history.append(
            {
                "transition_id": transition["transition_id"],
                "contexts": list(transition["contexts"]),
                "action": transition["action"],
                "observed_reward": reward,
            }
        )
        if len(self.history) > 200:
            self.history = self.history[-200:]


class HierarchicalEmpirical(_EmpiricalBase):
    """ALIVE-style source-specific policy with class/global backoff."""

    name = "alive_hierarchical"

    def __init__(
        self,
        min_source_observations=2,
        min_class_observations=1,
        source_margin=0.0,
    ):
        super().__init__()
        self.min_source_observations = min_source_observations
        self.min_class_observations = min_class_observations
        self.source_margin = source_margin

    def decide(self, obs):
        source_context = f"source:{obs['source_id']}"
        class_context = f"class:{obs['cadence']}:{obs['claim_age']}"
        source_n = self._count(source_context)
        class_n = self._count(class_context)
        source_choice = choose(self.policy, source_context)
        class_choice = choose(self.policy, class_context)
        source_best = max(source_choice["predictions"][action]["mean"] for action in ACTIONS)
        class_best = max(class_choice["predictions"][action]["mean"] for action in ACTIONS)
        if (
            source_n >= self.min_source_observations
            and source_best - class_best >= self.source_margin
        ):
            context, choice = source_context, source_choice
        elif class_n >= self.min_class_observations:
            context, choice = class_context, class_choice
        else:
            context, choice = "global", choose(self.policy, "global")
        return choice["action"], {
            "context": context,
            "context_count": self._count(context),
            "source_observations": source_n,
            "class_observations": class_n,
            "policy_version": choice["policy_version"],
            "policy_hash": choice["policy_hash"],
            "recalled_ids": self._recalled([source_context, class_context, "global"]),
            "predictions": choice["predictions"],
        }

    def learn(self, transition, reward_override=None):
        obs = transition["observation"]
        contexts = [
            f"source:{obs['source_id']}",
            f"class:{obs['cadence']}:{obs['claim_age']}",
            "global",
        ]
        transition["contexts"] = contexts
        reward = transition["observed_reward"] if reward_override is None else reward_override
        for context in contexts:
            self.policy = update(self.policy, transition["action"], reward, context)
        self.history.append(
            {
                "transition_id": transition["transition_id"],
                "contexts": contexts,
                "action": transition["action"],
                "observed_reward": reward,
            }
        )


class FlatEmpirical(_EmpiricalBase):
    """Flat cadence/age contextual table; critical control for source-specific memory."""

    name = "flat_empirical"

    def decide(self, obs):
        class_context = f"class:{obs['cadence']}:{obs['claim_age']}"
        context = class_context if self._count(class_context) else "global"
        choice = choose(self.policy, context)
        return choice["action"], {
            "context": context,
            "context_count": self._count(context),
            "class_observations": self._count(class_context),
            "policy_version": choice["policy_version"],
            "policy_hash": choice["policy_hash"],
            "recalled_ids": self._recalled([class_context, "global"]),
            "predictions": choice["predictions"],
        }

    def learn(self, transition, reward_override=None):
        obs = transition["observation"]
        contexts = [f"class:{obs['cadence']}:{obs['claim_age']}", "global"]
        transition["contexts"] = contexts
        reward = transition["observed_reward"] if reward_override is None else reward_override
        for context in contexts:
            self.policy = update(self.policy, transition["action"], reward, context)
        self.history.append(
            {
                "transition_id": transition["transition_id"],
                "contexts": contexts,
                "action": transition["action"],
                "observed_reward": reward,
            }
        )


class HistoryProxy(BaseAgent):
    """Offline history-retrieval proxy. This is not a Meta or live-model baseline."""

    name = "history_proxy_not_meta"

    def __init__(self, window=8):
        self.window = window
        self.history = []

    def reset(self):
        self.history = []

    def state_hash(self):
        return digest({"n": len(self.history), "window": self.window})

    def decide(self, obs):
        source_context = f"source:{obs['source_id']}"
        class_context = f"class:{obs['cadence']}:{obs['claim_age']}"
        for context in [source_context, class_context]:
            rows = [row for row in self.history if context in row["contexts"]][-self.window :]
            if len(rows) >= 2:
                means = {}
                for action in ACTIONS:
                    values = [r["observed_reward"] for r in rows if r["action"] == action]
                    means[action] = sum(values) / len(values) if values else 0.0
                action = max(ACTIONS, key=lambda item: means[item])
                return action, {
                    "context": context,
                    "context_count": len(rows),
                    "policy_version": 0,
                    "policy_hash": self.state_hash(),
                    "recalled_ids": [r["transition_id"] for r in rows],
                    "predictions": means,
                }
        prior = StatelessPrior()
        action, trace = prior.decide(obs)
        trace["context"] = "history_proxy_fallback"
        return action, trace

    def learn(self, transition, reward_override=None):
        obs = transition["observation"]
        contexts = [
            f"source:{obs['source_id']}",
            f"class:{obs['cadence']}:{obs['claim_age']}",
        ]
        self.history.append(
            {
                "transition_id": transition["transition_id"],
                "contexts": contexts,
                "action": transition["action"],
                "observed_reward": transition["observed_reward"]
                if reward_override is None
                else reward_override,
            }
        )


def run_episode(agent, scenario, governor, learn=False):
    obs = observation(scenario)
    started = time.perf_counter()
    action, trace = agent.decide(obs)
    governor.reset()
    allowed = governor.authorize(action)
    if allowed:
        true_changed = scenario["hidden"]["changed"]
        noisy_changed = bool(true_changed) ^ bool(scenario["hidden"]["feedback_noise_bit"])
        feedback_changed = true_changed if action == "retrieve" else noisy_changed
        observed_reward = utility(action, feedback_changed)
        score = utility(action, true_changed)
        feedback = {
            "changed": feedback_changed,
            "source": "independent_environment",
            "noisy": action == "monitor" and bool(scenario["hidden"]["feedback_noise_bit"]),
        }
    else:
        true_changed = scenario["hidden"]["changed"]
        observed_reward = 0.0
        score = 0.0
        feedback = {"changed": None, "source": "governor_denied", "noisy": False}
    latency_ms = (time.perf_counter() - started) * 1000
    transition = {
        "transition_id": f"{agent.name}:{scenario['scenario_id']}",
        "scenario_id": scenario["scenario_id"],
        "seed": scenario["seed"],
        "split": scenario["split"],
        "arm": agent.name,
        "observation": obs,
        "hidden": scenario["hidden"],
        "source_status": scenario["source_status"],
        "source_class": scenario["hidden"]["source_class"],
        "action": action,
        "governor_allowed": allowed,
        "feedback": feedback,
        "observed_reward": observed_reward,
        "utility": score,
        "changed": true_changed,
        "cost": ACTION_COST[action] if allowed else 0.0,
        "policy_version_before": trace.get("policy_version", 0),
        "policy_hash_before": trace.get("policy_hash"),
        "context": trace.get("context"),
        "context_count": trace.get("context_count", 0),
        "recalled_ids": trace.get("recalled_ids", []),
        "latency_ms": latency_ms,
        "provider_calls": 0,
        "tokens": 0,
        "estimated_usd": 0.0,
    }
    if learn and allowed:
        agent.learn(transition)
    transition["policy_version_after"] = (
        getattr(agent, "policy", {}).get("version", 0)
        if learn and allowed
        else transition["policy_version_before"]
    )
    transition["policy_hash_after"] = (
        agent.state_hash() if learn and allowed else transition["policy_hash_before"]
    )
    return transition


def run_arm(agent, scenarios, learn=False, governor=None):
    governor = governor or ExperimentGovernor()
    return [run_episode(agent, scenario, governor, learn=learn) for scenario in scenarios]


def train_agent(agent, scenarios, shuffle_rewards=False):
    if not shuffle_rewards:
        return run_arm(agent, scenarios, learn=True)
    transitions = run_arm(agent, scenarios, learn=True)
    rewards = [row["observed_reward"] for row in transitions]
    random.Random(20261027).shuffle(rewards)
    agent.reset()
    for transition, reward in zip(transitions, rewards, strict=True):
        agent.learn(transition, reward_override=reward)
    return transitions


def summarize(transitions):
    n = len(transitions)
    if not n:
        return {}
    utilities = [row["utility"] for row in transitions]
    changed = sum(row["changed"] for row in transitions)
    return {
        "n": n,
        "mean_utility": sum(utilities) / n,
        "total_utility": sum(utilities),
        "success_rate": sum(
            (row["action"] == "retrieve" and row["changed"])
            or (row["action"] == "monitor" and not row["changed"])
            for row in transitions
        )
        / n,
        "missed_changes": sum(row["action"] == "monitor" and row["changed"] for row in transitions),
        "unnecessary_retrievals": sum(
            row["action"] == "retrieve" and not row["changed"] for row in transitions
        ),
        "correct_monitors": sum(
            row["action"] == "monitor" and not row["changed"] for row in transitions
        ),
        "retrieval_rate": sum(row["action"] == "retrieve" for row in transitions) / n,
        "mean_cost": sum(row["cost"] for row in transitions) / n,
        "changed_rate": changed / n,
        "memory_coverage": sum(
            row.get("context") not in {None, "global", "stateless_prior", "fixed_heuristic"}
            for row in transitions
        )
        / n,
        "latency_ms": sum(row["latency_ms"] for row in transitions) / n,
        "provider_calls": sum(row["provider_calls"] for row in transitions),
        "tokens": sum(row["tokens"] for row in transitions),
        "estimated_usd": sum(row["estimated_usd"] for row in transitions),
    }


def group_metrics(transitions, key):
    groups = defaultdict(list)
    for row in transitions:
        groups[row[key]].append(row)
    return {name: summarize(rows) for name, rows in sorted(groups.items())}


def _clusters(transitions):
    clusters = defaultdict(list)
    for row in transitions:
        clusters[(row["seed"], row["observation"]["source_id"])].append(row)
    return list(clusters.values())


def paired_bootstrap(a_rows, b_rows, reps=2000, seed=20261027):
    a = {row["scenario_id"]: row["utility"] for row in a_rows}
    b = {row["scenario_id"]: row["utility"] for row in b_rows}
    clusters = defaultdict(list)
    for scenario_id in sorted(set(a) & set(b)):
        row = next(r for r in a_rows if r["scenario_id"] == scenario_id)
        clusters[(row["seed"], row["observation"]["source_id"])].append(
            a[scenario_id] - b[scenario_id]
        )
    values = list(clusters.values())
    if not values:
        return {"mean_difference": None, "ci95": [None, None], "clusters": 0, "episodes": 0}
    rng = np.random.default_rng(seed)
    means = []
    for _ in range(reps):
        selected = rng.integers(0, len(values), len(values))
        sample = [value for index in selected for value in values[index]]
        means.append(sum(sample) / len(sample))
    means.sort()
    return {
        "mean_difference": sum(v for cluster in values for v in cluster)
        / sum(len(cluster) for cluster in values),
        "ci95": [means[int(0.025 * reps)], means[int(0.975 * reps) - 1]],
        "clusters": len(values),
        "episodes": sum(len(cluster) for cluster in values),
    }


def classify(primary, correct_vs_no_history, correct_vs_shuffled, validity):
    if not validity:
        return "FAIL_QUALIFICATION"
    if (
        primary["ci95"][0] is not None
        and primary["ci95"][0] > 0
        and primary["mean_difference"] >= 0.01
    ):
        if (
            correct_vs_no_history["ci95"][0] is not None
            and correct_vs_no_history["ci95"][0] > 0
            and correct_vs_shuffled["ci95"][0] is not None
            and correct_vs_shuffled["ci95"][0] > 0
        ):
            return "PASS_ADVANTAGE_DEMONSTRATED"
        return "PASS_WITH_LIMITATIONS"
    return "PASS_NO_ADVANTAGE_DEMONSTRATED"
