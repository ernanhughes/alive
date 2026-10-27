"""ALIVE-08 controlled experience-learning experiment.

Commands:
  generate   Create frozen development/calibration/training/evaluation corpora.
  calibrate  Select the source backoff from calibration episodes; freeze protocol.
  evaluate   Run held-out paired evaluation; write archive evidence and report.
"""

import argparse
import hashlib
import json
from pathlib import Path

from alive.experience_lab import (
    ACTION_COST,
    ACTIONS,
    AGE_FACTOR,
    AGE_VALUES,
    AGE_WEIGHTS,
    FEEDBACK_NOISE,
    MISS_PENALTY,
    OBSERVATION_KEYS,
    POLICY_VERSION,
    RETRIEVE_GAIN,
    SEEDS,
    SOURCE_CLASSES,
    SPLIT_SIZES,
    FixedHeuristic,
    FlatEmpirical,
    HierarchicalEmpirical,
    HistoryProxy,
    StatelessPrior,
    classify,
    group_metrics,
    observation,
    paired_bootstrap,
    run_arm,
    summarize,
    train_agent,
    utility,
    write_corpora,
)

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "benchmarks" / "alive08"
ARCHIVE = ROOT / "archives" / "ALIVE-08"
PROTOCOL_VERSION = "alive08-v1"
PRIMARY_COMPARISON = ("alive_hierarchical", "flat_empirical")
SECONDARY_COMPARISONS = [
    ("alive_hierarchical", "stateless_prior"),
    ("alive_hierarchical", "fixed_heuristic"),
    ("alive_hierarchical", "alive_no_history"),
    ("alive_hierarchical", "alive_shuffled"),
    ("alive_hierarchical", "history_proxy_not_meta"),
]
CALIBRATION_GRID = {
    "min_source_observations": [2, 3, 4],
    "source_margin": [0.0, 0.05, 0.10, 0.20],
}


def _hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_hash(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode()
    ).hexdigest()


def load_jsonl(path):
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def protocol_document(corpus_hashes):
    return {
        "protocol_version": PROTOCOL_VERSION,
        "status": "generated",
        "policy_version": POLICY_VERSION,
        "seeds": SEEDS,
        "split_sizes": SPLIT_SIZES,
        "actions": list(ACTIONS),
        "action_cost": ACTION_COST,
        "primary_metric": "mean independent task utility per held-out episode",
        "primary_comparison": list(PRIMARY_COMPARISON),
        "secondary_comparisons": [list(pair) for pair in SECONDARY_COMPARISONS],
        "calibration_grid": CALIBRATION_GRID,
        "selected_min_source_observations": None,
        "selected_source_margin": None,
        "corpus_hashes": corpus_hashes,
        "acceptance": {
            "advantage": (
                "paired 95% cluster-bootstrap CI lower bound > 0 for "
                "alive_hierarchical minus flat_empirical, and mean difference >= 0.01"
            ),
            "strong_advantage": (
                "advantage plus CI lower bound > 0 versus no-history and shuffled-history"
            ),
            "negative": "valid experiment with primary criterion not met",
        },
        "hypotheses": {
            "H1": "Source-specific experience improves held-out utility over a flat context table.",
            "H2": "Correct history improves utility over no history.",
            "H3": "Correct history improves utility over shuffled history.",
            "H4": (
                "Simple empirical learning is comparable to fixed heuristics only when the "
                "hidden structure is not learnable."
            ),
        },
        "reward": {
            "retrieve_changed": RETRIEVE_GAIN - ACTION_COST["retrieve"],
            "retrieve_unchanged": -ACTION_COST["retrieve"],
            "monitor_changed": -MISS_PENALTY,
            "monitor_unchanged": 0.0,
        },
        "hidden_parameters": {
            "source_classes": SOURCE_CLASSES,
            "age_factor": AGE_FACTOR,
            "feedback_noise": FEEDBACK_NOISE,
            "age_values": AGE_VALUES,
            "age_weights": AGE_WEIGHTS,
        },
    }


def command_generate(_args):
    if (BENCH / "protocol.json").exists():
        raise SystemExit("ALIVE-08 corpus already exists; refusing to regenerate")
    corpus, environment, seeds_data = write_corpora(BENCH)
    protocol = protocol_document(seeds_data["corpus_hashes"])
    protocol["protocol_sha256"] = _json_hash(
        {key: value for key, value in protocol.items() if key != "protocol_sha256"}
    )
    write_json(BENCH / "protocol.json", protocol)
    write_json(BENCH / "environment.json", environment)
    write_json(BENCH / "seeds.json", seeds_data)
    print(
        json.dumps(
            {
                "splits": {split: len(rows) for split, rows in corpus.items()},
                "protocol_sha256": protocol["protocol_sha256"],
            },
            indent=2,
        )
    )


def _rows_for(rows, seed=None, split=None):
    selected = rows
    if seed is not None:
        selected = [row for row in selected if row["seed"] == seed]
    if split is not None:
        selected = [row for row in selected if row["split"] == split]
    return selected


def _train_and_eval(agent, train_rows, eval_rows, learn=False):
    train_agent(agent, train_rows)
    return run_arm(agent, eval_rows, learn=learn)


def command_calibrate(_args):
    protocol = json.loads((BENCH / "protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] == "frozen":
        raise SystemExit("Protocol is already frozen; refusing calibration")
    training = load_jsonl(BENCH / "training.jsonl")
    calibration = load_jsonl(BENCH / "calibration.jsonl")
    table = []
    for min_source in CALIBRATION_GRID["min_source_observations"]:
        for source_margin in CALIBRATION_GRID["source_margin"]:
            per_seed = []
            for seed in protocol["seeds"]:
                train_rows = _rows_for(training, seed=seed)
                eval_rows = _rows_for(calibration, seed=seed)
                agent = HierarchicalEmpirical(
                    min_source_observations=min_source,
                    source_margin=source_margin,
                )
                transitions = _train_and_eval(agent, train_rows, eval_rows)
                per_seed.append(summarize(transitions)["mean_utility"])
            table.append(
                {
                    "min_source_observations": min_source,
                    "source_margin": source_margin,
                    "mean_utility": sum(per_seed) / len(per_seed),
                    "per_seed": per_seed,
                }
            )
    selected = max(
        table,
        key=lambda row: (
            row["mean_utility"],
            -row["min_source_observations"],
            -row["source_margin"],
        ),
    )
    protocol["status"] = "frozen"
    protocol["selected_min_source_observations"] = selected["min_source_observations"]
    protocol["selected_source_margin"] = selected["source_margin"]
    protocol["calibration"] = table
    protocol["calibration_selected"] = selected
    protocol["protocol_sha256"] = _json_hash(
        {key: value for key, value in protocol.items() if key != "protocol_sha256"}
    )
    write_json(BENCH / "protocol.json", protocol)
    write_json(BENCH / "calibration-selection.json", {"table": table, "selected": selected})
    print(json.dumps({"table": table, "selected": selected}, indent=2))


def _make_agents(seed, training_rows, protocol):
    min_source = protocol["selected_min_source_observations"]
    source_margin = protocol["selected_source_margin"]
    agents = {
        "stateless_prior": (StatelessPrior(), None),
        "fixed_heuristic": (FixedHeuristic(), None),
        "flat_empirical": (FlatEmpirical(), training_rows),
        "alive_hierarchical": (
            HierarchicalEmpirical(min_source_observations=min_source, source_margin=source_margin),
            training_rows,
        ),
        "alive_no_history": (
            HierarchicalEmpirical(min_source_observations=min_source, source_margin=source_margin),
            None,
        ),
        "alive_shuffled": (
            HierarchicalEmpirical(min_source_observations=min_source, source_margin=source_margin),
            "shuffled",
        ),
        "history_proxy_not_meta": (HistoryProxy(), training_rows),
    }
    return agents


def _evaluate_seed(seed, training, evaluation, protocol):
    train_rows = _rows_for(training, seed=seed)
    eval_rows = _rows_for(evaluation, seed=seed)
    agents = _make_agents(seed, train_rows, protocol)
    transitions = {}
    for name, (agent, training_mode) in agents.items():
        if training_mode == "shuffled":
            train_agent(agent, train_rows, shuffle_rewards=True)
        elif training_mode is not None:
            train_agent(agent, train_rows)
        transitions[name] = run_arm(agent, eval_rows, learn=False)
    online = HierarchicalEmpirical(
        min_source_observations=protocol["selected_min_source_observations"],
        source_margin=protocol["selected_source_margin"],
    )
    train_agent(online, train_rows)
    transitions["alive_online_ablation"] = run_arm(online, eval_rows, learn=True)
    return transitions, agents["alive_hierarchical"][0], eval_rows


def _validity(protocol, all_transitions):
    corpus_hashes = protocol.get("corpus_hashes", {})
    hashes_match = all(
        corpus_hashes.get(split) == _hash_file(BENCH / f"{split}.jsonl")
        for split in ("development", "calibration", "training", "evaluation")
    )
    observations_clean = all(
        set(row["observation"]) <= OBSERVATION_KEYS
        for rows in all_transitions.values()
        for row in rows
    )
    scenario_sets = [{row["scenario_id"] for row in rows} for rows in all_transitions.values()]
    same_scenarios = all(scenarios == scenario_sets[0] for scenarios in scenario_sets[1:])
    no_calls = all(
        row["provider_calls"] == 0 and row["tokens"] == 0
        for rows in all_transitions.values()
        for row in rows
    )
    all_allowed = all(row["governor_allowed"] for rows in all_transitions.values() for row in rows)
    return {
        "protocol_frozen": protocol.get("status") == "frozen",
        "selected_parameter_present": protocol.get("selected_min_source_observations") is not None
        and protocol.get("selected_source_margin") is not None,
        "corpus_hashes_match": hashes_match,
        "observations_exclude_hidden_fields": observations_clean,
        "all_arms_use_same_scenarios": same_scenarios,
        "zero_provider_calls_and_tokens": no_calls,
        "all_actions_governor_allowed": all_allowed,
    }


def _cumulative_svg(all_transitions):
    arms = list(all_transitions)
    width, height = 900, 420
    colors = [
        "#2f6f4e",
        "#a36b2c",
        "#6d5aa8",
        "#b04a4a",
        "#2c6f9c",
        "#7d7d7d",
        "#b78a1e",
        "#3f8d89",
    ]
    series = {}
    for arm in arms:
        ordered = sorted(all_transitions[arm], key=lambda row: (row["seed"], row["scenario_id"]))
        total, points = 0.0, []
        for index, row in enumerate(ordered, 1):
            total += row["utility"]
            points.append((index, total / index))
        series[arm] = points
    max_x = max(len(points) for points in series.values())
    values = [value for points in series.values() for _, value in points]
    low, high = min(values), max(values)
    span = high - low or 1.0

    def xy(x, y):
        return 45 + (x / max_x) * (width - 80), 25 + (1 - (y - low) / span) * (height - 85)

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        'viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfcf8"/>',
        '<text x="45" y="18" font-size="13" fill="#333">Cumulative mean held-out utility</text>',
        f'<line x1="45" y1="{height - 60}" x2="{width - 35}" y2="{height - 60}" stroke="#888"/>',
        f'<line x1="45" y1="25" x2="45" y2="{height - 60}" stroke="#888"/>',
    ]
    for index, arm in enumerate(arms):
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in (xy(x, y) for x, y in series[arm]))
        lines.append(
            f'<polyline fill="none" stroke="{colors[index % len(colors)]}" stroke-width="2" '
            f'points="{points}"/>'
        )
        lines.append(
            f'<text x="{width - 260}" y="{40 + index * 16}" font-size="11" '
            f'fill="{colors[index % len(colors)]}">{arm}</text>'
        )
    lines.append("</svg>")
    return "\n".join(lines)


def _report(results):
    primary = results["paired"][f"{PRIMARY_COMPARISON[0]}_vs_{PRIMARY_COMPARISON[1]}"]
    lines = [
        "# ALIVE-08 results",
        "",
        f"Status: **{results['classification']}**",
        "",
        f"Protocol SHA-256: `{results['protocol_sha256']}`  ",
        f"Corpus SHA-256: `{results['corpus_hashes']['evaluation']}`  ",
        f"Seeds: {', '.join(str(seed) for seed in results['seeds'])}",
        "",
        "## Primary comparison",
        "",
        "| Comparison | Mean difference | 95% cluster bootstrap CI | Clusters | Episodes |",
        "|---|---:|---|---:|---:|",
        f"| alive_hierarchical - flat_empirical | {primary['mean_difference']:.4f} | "
        f"[{primary['ci95'][0]:.4f}, {primary['ci95'][1]:.4f}] | "
        f"{primary['clusters']} | {primary['episodes']} |",
        "",
        "## Arm means",
        "",
        "| Arm | Mean utility | Success | Missed changes | Unnecessary retrievals | "
        "Retrieval rate | Memory coverage |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for arm, metric in results["arms"].items():
        lines.append(
            f"| {arm} | {metric['mean_utility']:.4f} | {metric['success_rate']:.3f} | "
            f"{metric['missed_changes']} | {metric['unnecessary_retrievals']} | "
            f"{metric['retrieval_rate']:.3f} | {metric['memory_coverage']:.3f} |"
        )
    lines += [
        "",
        "## Paired comparisons",
        "",
        "| A vs B | Mean difference | 95% CI | Clusters |",
        "|---|---:|---|---:|",
    ]
    for name, metric in results["paired"].items():
        lines.append(
            f"| {name} | {metric['mean_difference']:.4f} | "
            f"[{metric['ci95'][0]:.4f}, {metric['ci95'][1]:.4f}] | {metric['clusters']} |"
        )
    lines += [
        "",
        "## Held-out utility by source status",
        "",
        "| Arm | seen | unseen | novel |",
        "|---|---:|---:|---:|",
    ]
    for arm, groups in results["by_status"].items():
        lines.append(
            f"| {arm} | "
            + " | ".join(
                f"{groups.get(status, {}).get('mean_utility', float('nan')):.4f}"
                for status in ("seen", "unseen", "novel")
            )
            + " |"
        )
    lines += [
        "",
        "## Ablations",
        "",
        "| Ablation | Mean utility | Difference vs correct | 95% CI |",
        "|---|---:|---:|---|",
    ]
    for name, metric in results["ablations"].items():
        lines.append(
            f"| {name} | {metric['mean_utility']:.4f} | {metric['difference']:.4f} | "
            f"[{metric['ci95'][0]:.4f}, {metric['ci95'][1]:.4f}] |"
        )
    lines += [
        "",
        "## Validity and resources",
        "",
        f"- Validity checks: `{results['validity']}`",
        f"- Provider calls: {results['resource']['provider_calls']}",
        f"- Tokens: {results['resource']['tokens']}",
        f"- Estimated provider cost: ${results['resource']['estimated_usd']:.6f}",
        f"- Mean decision latency: {results['resource']['latency_ms']:.3f} ms",
        "",
        "## Counterfactual example",
        "",
        "```json",
        json.dumps(results["counterfactual"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## Interpretation boundary",
        "",
        "The counterfactual utilities are simulator-defined, not real-world outcomes. "
        "The history proxy is not a Meta model. No paid inference or native Chrome was used. "
        "A positive result applies to this frozen, controlled environment only.",
    ]
    return "\n".join(lines) + "\n"


def command_evaluate(_args):
    protocol = json.loads((BENCH / "protocol.json").read_text(encoding="utf-8"))
    if protocol["status"] != "frozen":
        raise SystemExit("Protocol is not frozen; run calibrate first")
    if (ARCHIVE / "reports" / "results.json").exists():
        raise SystemExit("Held-out results already exist; refusing a second evaluation")
    training = load_jsonl(BENCH / "training.jsonl")
    evaluation = load_jsonl(BENCH / "evaluation.jsonl")
    all_transitions = {}
    agents_for_restart = {}
    eval_rows_for_restart = {}
    for seed in protocol["seeds"]:
        transitions, agent, eval_rows = _evaluate_seed(seed, training, evaluation, protocol)
        for arm, rows in transitions.items():
            all_transitions.setdefault(arm, []).extend(rows)
        agents_for_restart[seed] = agent
        eval_rows_for_restart[seed] = eval_rows
    arms = {arm: summarize(rows) for arm, rows in all_transitions.items()}
    paired = {
        f"{a}_vs_{b}": paired_bootstrap(all_transitions[a], all_transitions[b])
        for a, b in [PRIMARY_COMPARISON, *SECONDARY_COMPARISONS]
    }
    by_status = {arm: group_metrics(rows, "source_status") for arm, rows in all_transitions.items()}
    by_class = {arm: group_metrics(rows, "source_class") for arm, rows in all_transitions.items()}
    per_seed = {
        arm: {
            str(seed): summarize([r for r in rows if r["seed"] == seed])
            for seed in protocol["seeds"]
        }
        for arm, rows in all_transitions.items()
    }
    correct = all_transitions["alive_hierarchical"]
    d_rows = all_transitions["flat_empirical"]
    d_by_scenario = {row["scenario_id"]: row["action"] for row in d_rows}
    decision_change_rate = sum(
        row["action"] != d_by_scenario[row["scenario_id"]] for row in correct
    ) / len(correct)
    no_history = all_transitions["alive_no_history"]
    validity = _validity(protocol, all_transitions)
    classification = classify(
        paired["alive_hierarchical_vs_flat_empirical"],
        paired["alive_hierarchical_vs_alive_no_history"],
        paired["alive_hierarchical_vs_alive_shuffled"],
        all(validity.values()),
    )
    # Simulated counterfactual: first scenario where trained and untrained policies differ.
    c_by_scenario = {row["scenario_id"]: row for row in correct}
    n_by_scenario = {row["scenario_id"]: row for row in no_history}
    chosen = next(
        (
            c_by_scenario[sid]
            for sid in sorted(c_by_scenario)
            if c_by_scenario[sid]["source_status"] == "seen"
            and c_by_scenario[sid]["action"] != n_by_scenario[sid]["action"]
        ),
        correct[0],
    )
    counterfactual = {
        "scenario_id": chosen["scenario_id"],
        "source_status": chosen["source_status"],
        "source_class": chosen["hidden"]["source_class"],
        "observation": chosen["observation"],
        "true_changed": chosen["changed"],
        "alive_action": chosen["action"],
        "no_history_action": n_by_scenario[chosen["scenario_id"]]["action"],
        "alive_utility": chosen["utility"],
        "no_history_utility": n_by_scenario[chosen["scenario_id"]]["utility"],
        "counterfactual_utilities": {
            action: utility(action, chosen["changed"]) for action in ACTIONS
        },
        "alive_context": chosen.get("context"),
        "alive_recalled_ids": chosen.get("recalled_ids", []),
        "policy_hash_before": chosen.get("policy_hash_before"),
        "policy_hash_after": chosen.get("policy_hash_after"),
        "note": "Simulator-defined counterfactual; not a real-world outcome.",
    }
    restart_seed = protocol["seeds"][0]
    restart_agent = agents_for_restart[restart_seed]
    loaded = HierarchicalEmpirical(
        min_source_observations=protocol["selected_min_source_observations"],
        source_margin=protocol["selected_source_margin"],
    )
    loaded.policy = json.loads(json.dumps(restart_agent.policy))
    restart_rows = eval_rows_for_restart[restart_seed][:20]
    original_decisions = [restart_agent.decide(observation(row))[0] for row in restart_rows]
    loaded_decisions = [loaded.decide(observation(row))[0] for row in restart_rows]
    restart = {
        "scope": "simulator policy JSON round-trip, not a live runtime restart",
        "policy_sha256_before": restart_agent.state_hash(),
        "policy_sha256_after": loaded.state_hash(),
        "decisions_match": original_decisions == loaded_decisions,
        "sample_size": len(restart_rows),
        "paid_work_replayed": False,
    }
    resource = {
        "provider_calls": sum(
            row["provider_calls"] for rows in all_transitions.values() for row in rows
        ),
        "tokens": sum(row["tokens"] for rows in all_transitions.values() for row in rows),
        "estimated_usd": sum(
            row["estimated_usd"] for rows in all_transitions.values() for row in rows
        ),
        "latency_ms": sum(row["latency_ms"] for rows in all_transitions.values() for row in rows)
        / sum(len(rows) for rows in all_transitions.values()),
    }
    results = {
        "classification": classification,
        "protocol_sha256": protocol.get("protocol_sha256"),
        "protocol": protocol,
        "corpus_hashes": protocol["corpus_hashes"],
        "seeds": protocol["seeds"],
        "arms": arms,
        "per_seed": per_seed,
        "by_status": by_status,
        "by_class": by_class,
        "paired": paired,
        "ablations": {
            "correct_history": {
                "mean_utility": arms["alive_hierarchical"]["mean_utility"],
                "difference": 0.0,
                "ci95": [0.0, 0.0],
            },
            "no_history": {
                "mean_utility": arms["alive_no_history"]["mean_utility"],
                "difference": paired["alive_hierarchical_vs_alive_no_history"]["mean_difference"],
                "ci95": paired["alive_hierarchical_vs_alive_no_history"]["ci95"],
            },
            "shuffled_history": {
                "mean_utility": arms["alive_shuffled"]["mean_utility"],
                "difference": paired["alive_hierarchical_vs_alive_shuffled"]["mean_difference"],
                "ci95": paired["alive_hierarchical_vs_alive_shuffled"]["ci95"],
            },
            "fixed_heuristic": {
                "mean_utility": arms["fixed_heuristic"]["mean_utility"],
                "difference": paired["alive_hierarchical_vs_fixed_heuristic"]["mean_difference"],
                "ci95": paired["alive_hierarchical_vs_fixed_heuristic"]["ci95"],
            },
        },
        "decision_change_rate_vs_flat": decision_change_rate,
        "counterfactual": counterfactual,
        "restart_proof": restart,
        "validity": validity,
        "resource": resource,
    }
    report = _report(results)
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    for split in ("development", "calibration", "training", "evaluation"):
        target = ARCHIVE / "corpus" / f"{split}.jsonl"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((BENCH / f"{split}.jsonl").read_bytes())
    write_json(ARCHIVE / "protocol.json", protocol)
    write_json(ARCHIVE / "environment.json", json.loads((BENCH / "environment.json").read_text()))
    write_json(ARCHIVE / "seeds.json", json.loads((BENCH / "seeds.json").read_text()))
    write_json(ARCHIVE / "calibration.json", protocol.get("calibration_selected"))
    for name in ("paired", "by_status", "by_class", "per_seed", "validity"):
        write_json(ARCHIVE / "evidence" / f"{name}.json", results[name])
    write_json(ARCHIVE / "evidence" / "ablations.json", results["ablations"])
    write_json(ARCHIVE / "evidence" / "counterfactual_examples.json", counterfactual)
    write_json(ARCHIVE / "evidence" / "restart_proof.json", restart)
    with (ARCHIVE / "evidence" / "transitions.jsonl").open("w", encoding="utf-8") as handle:
        for arm in sorted(all_transitions):
            for row in all_transitions[arm]:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    write_json(ARCHIVE / "reports" / "results.json", results)
    (ARCHIVE / "reports" / "results.md").write_text(report, encoding="utf-8")
    (ARCHIVE / "reports" / "cumulative-utility.svg").write_text(
        _cumulative_svg(all_transitions), encoding="utf-8"
    )
    write_json(ARCHIVE / "reports" / "summary.json", {"classification": classification, **arms})
    print(report)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["generate", "calibrate", "evaluate"])
    args = parser.parse_args()
    if args.command == "generate":
        command_generate(args)
    elif args.command == "calibrate":
        command_calibrate(args)
    else:
        command_evaluate(args)


if __name__ == "__main__":
    main()
