import json

import pytest

from alive.experience_lab import (
    ACTIONS,
    ExperimentGovernor,
    FlatEmpirical,
    HierarchicalEmpirical,
    StatelessPrior,
    generate_corpus,
    observation,
    paired_bootstrap,
    run_episode,
    summarize,
    train_agent,
    utility,
)


def _transition(index, source_id, action, reward, cadence="hourly", age="day"):
    return {
        "transition_id": f"training-{index}",
        "observation": {
            "source_id": source_id,
            "cadence": cadence,
            "claim_age": age,
        },
        "action": action,
        "observed_reward": reward,
    }


def test_utility_and_action_costs_are_predeclared():
    assert utility("retrieve", True) == pytest.approx(0.80)
    assert utility("retrieve", False) == pytest.approx(-0.20)
    assert utility("monitor", True) == pytest.approx(-1.0)
    assert utility("monitor", False) == 0.0
    with pytest.raises(ValueError):
        utility("send_message", True)


def test_observation_never_contains_hidden_fields():
    corpus = generate_corpus([17])
    row = corpus["evaluation"][0]
    visible = observation(row)
    assert set(visible) <= {
        "source_id",
        "cadence",
        "claim_age",
        "claim",
        "goal",
        "permitted_actions",
    }
    for hidden in ("changed", "source_class", "p_change", "feedback_noise_bit"):
        assert hidden not in visible


def test_governor_denies_invalid_action_and_budget_exhaustion():
    governor = ExperimentGovernor(episode_budget=0.10)
    assert governor.authorize("send_message") is False
    assert governor.authorize("retrieve") is False
    assert governor.authorize("monitor") is True
    assert len(governor.denied) == 2


def test_hierarchical_agent_uses_source_history_after_threshold():
    agent = HierarchicalEmpirical(
        min_source_observations=1, min_class_observations=1, source_margin=0.0
    )
    agent.learn(_transition(0, "src-a", "retrieve", 0.8))
    obs = {
        "source_id": "src-a",
        "cadence": "hourly",
        "claim_age": "day",
        "claim": 30,
        "goal": "keep current",
        "permitted_actions": list(ACTIONS),
    }
    action, trace = agent.decide(obs)
    assert action == "retrieve"
    assert trace["context"] == "source:src-a"
    assert trace["recalled_ids"] == ["training-0"]


def test_source_margin_falls_back_to_class_context():
    agent = HierarchicalEmpirical(
        min_source_observations=1, min_class_observations=1, source_margin=0.5
    )
    agent.learn(_transition(0, "src-other", "retrieve", 0.8, cadence="hourly"))
    agent.learn(_transition(1, "src-target", "monitor", 0.0, cadence="hourly"))
    obs = {
        "source_id": "src-target",
        "cadence": "hourly",
        "claim_age": "day",
        "claim": 30,
        "goal": "keep current",
        "permitted_actions": list(ACTIONS),
    }
    action, trace = agent.decide(obs)
    assert trace["context"] == "class:hourly:day"
    assert action == "retrieve"


def test_flat_empirical_learns_class_context_without_source_key():
    agent = FlatEmpirical()
    agent.learn(_transition(0, "src-a", "retrieve", 0.8))
    obs = {
        "source_id": "src-a",
        "cadence": "hourly",
        "claim_age": "day",
        "claim": 30,
        "goal": "keep current",
        "permitted_actions": list(ACTIONS),
    }
    action, trace = agent.decide(obs)
    assert action == "retrieve"
    assert trace["context"] == "class:hourly:day"


def test_run_episode_records_causal_order_and_independent_utility():
    corpus = generate_corpus([17])
    row = corpus["development"][0]
    agent = StatelessPrior()
    transition = run_episode(agent, row, ExperimentGovernor(), learn=False)
    assert transition["observation"] == observation(row)
    assert transition["action"] in ACTIONS
    assert transition["utility"] == utility(transition["action"], row["hidden"]["changed"])
    assert transition["provider_calls"] == 0 and transition["tokens"] == 0
    assert "changed" not in transition["observation"]


def test_paired_bootstrap_is_deterministic_and_cluster_aware():
    def rows(arm, offset):
        return [
            {
                "scenario_id": f"s{index}",
                "seed": 17,
                "observation": {"source_id": "src-a"},
                "utility": offset + index,
            }
            for index in range(5)
        ]

    first = paired_bootstrap(rows("a", 1.0), rows("b", 0.0), reps=100)
    second = paired_bootstrap(rows("a", 1.0), rows("b", 0.0), reps=100)
    assert first == second
    assert first["clusters"] == 1
    assert first["episodes"] == 5
    assert first["mean_difference"] == pytest.approx(1.0)


def test_policy_roundtrip_preserves_decisions():
    agent = HierarchicalEmpirical(min_source_observations=1, source_margin=0.0)
    agent.learn(_transition(0, "src-a", "retrieve", 0.8))
    loaded = HierarchicalEmpirical(min_source_observations=1, source_margin=0.0)
    loaded.policy = json.loads(json.dumps(agent.policy))
    obs = {
        "source_id": "src-a",
        "cadence": "hourly",
        "claim_age": "day",
        "claim": 30,
        "goal": "keep current",
        "permitted_actions": list(ACTIONS),
    }
    assert agent.state_hash() == loaded.state_hash()
    assert agent.decide(obs)[0] == loaded.decide(obs)[0]


def test_generated_corpus_is_deterministic_and_has_frozen_roles():
    first = generate_corpus([17])
    second = generate_corpus([17])
    assert [json.dumps(row, sort_keys=True) for row in first["development"]] == [
        json.dumps(row, sort_keys=True) for row in second["development"]
    ]
    assert len(first["development"]) == 40
    assert len(first["calibration"]) == 100
    assert len(first["training"]) == 200
    assert len(first["evaluation"]) == 300
    assert {row["source_status"] for row in first["evaluation"]} == {"seen", "unseen", "novel"}


def test_shuffled_training_runs_and_summary_is_finite():
    corpus = generate_corpus([17])
    agent = HierarchicalEmpirical(min_source_observations=1)
    train_agent(agent, corpus["training"][:8], shuffle_rewards=True)
    transitions = [
        run_episode(agent, row, ExperimentGovernor(), learn=False)
        for row in corpus["development"][:8]
    ]
    metric = summarize(transitions)
    assert metric["n"] == 8
    assert metric["mean_utility"] is not None
    assert metric["provider_calls"] == 0
