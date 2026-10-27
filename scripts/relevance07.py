"""Frozen ALIVE-07 relevance evaluation. Candidate code never reads labels."""

import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from alive.relevance import default_config, evaluate_relevance

ROOT = Path(__file__).resolve().parents[1]
CORPUS = ROOT / "benchmarks" / "relevance" / "alive07.jsonl"
ARCHIVE = ROOT / "archives" / "ALIVE-07"


def load_corpus(path=CORPUS):
    items = [
        json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines() if line
    ]
    ids = {item["id"] for item in items}
    assert len(ids) == len(items), "corpus IDs must be unique"
    assert all(item["label"] in {"relevant", "irrelevant", "uncertain"} for item in items)
    assert all(item["split"] in {"dev", "calibration", "heldout"} for item in items)
    return items


def legacy_v1(goal, excerpt, config):
    """Frozen ALIVE-06 English exact-overlap baseline using external stopwords."""

    stopwords = set(config.languages["en"].stopwords)

    def terms(text):
        return {
            term
            for term in re.findall(r"[a-z0-9_]+", text.lower())
            if len(term) >= 4 and term not in stopwords
        }

    return "relevant" if terms(goal) & terms(excerpt) else "irrelevant"


def simple_overlap(goal, excerpt):
    """No-stop-word, whitespace/punctuation baseline."""

    def terms(text):
        return {term for term in re.findall(r"\w+", text.casefold()) if len(term) >= 2}

    return "relevant" if terms(goal) & terms(excerpt) else "irrelevant"


def policy_v2(item, config):
    return evaluate_relevance(item["goal"], item["excerpt"], item.get("language", "auto"), config)


def v2_prediction(item, config):
    result = policy_v2(item, config)
    if result["status"] == "uncertain":
        return "uncertain", result
    return ("relevant" if result["relevant"] else "irrelevant"), result


def conservative_prediction(item, config):
    prediction, result = v2_prediction(item, config)
    if prediction in {"relevant", "uncertain"}:
        return prediction, result
    return "uncertain", result


def blank_metrics():
    return {
        "n": 0,
        "relevant": 0,
        "irrelevant": 0,
        "uncertain": 0,
        "tp": 0,
        "fp": 0,
        "tn": 0,
        "fn_abstain": 0,
        "fn_uncertain": 0,
        "correct_uncertain": 0,
        "unnecessary_uncertain": 0,
        "uncertain_as_relevant": 0,
        "uncertain_as_irrelevant": 0,
    }


def score(rows):
    result = blank_metrics()
    for item, prediction, _ in rows:
        result["n"] += 1
        label = item["label"]
        result[label] += 1
        if label == "relevant":
            if prediction == "relevant":
                result["tp"] += 1
            elif prediction == "irrelevant":
                result["fn_abstain"] += 1
            else:
                result["fn_uncertain"] += 1
        elif label == "irrelevant":
            if prediction == "relevant":
                result["fp"] += 1
            elif prediction == "irrelevant":
                result["tn"] += 1
            else:
                result["unnecessary_uncertain"] += 1
        else:
            if prediction == "uncertain":
                result["correct_uncertain"] += 1
            elif prediction == "relevant":
                result["uncertain_as_relevant"] += 1
            else:
                result["uncertain_as_irrelevant"] += 1

    relevant_total = result["tp"] + result["fn_abstain"] + result["fn_uncertain"]
    irrelevant_total = result["tn"] + result["fp"] + result["unnecessary_uncertain"]
    uncertain_total = (
        result["correct_uncertain"]
        + result["uncertain_as_relevant"]
        + result["uncertain_as_irrelevant"]
    )
    predicted_uncertain = (
        result["fn_uncertain"] + result["unnecessary_uncertain"] + result["correct_uncertain"]
    )
    result.update(
        {
            "predicted_uncertain": predicted_uncertain,
            "precision": result["tp"] / (result["tp"] + result["fp"])
            if result["tp"] + result["fp"]
            else None,
            "recall": result["tp"] / relevant_total if relevant_total else None,
            "false_abstention_rate": result["fn_abstain"] / relevant_total
            if relevant_total
            else None,
            "false_investigation_rate": result["fp"] / irrelevant_total
            if irrelevant_total
            else None,
            "uncertainty_rate": predicted_uncertain / result["n"] if result["n"] else None,
            "uncertain_recall": result["correct_uncertain"] / uncertain_total
            if uncertain_total
            else None,
            "model_calls_avoided": result["n"]
            - result["tp"]
            - result["fp"]
            - result["uncertain_as_relevant"],
            "owner_intervention": predicted_uncertain,
        }
    )
    return result


def _group(rows, key):
    grouped = defaultdict(list)
    for row in rows:
        grouped[row[0][key]].append(row)
    return {name: score(items) for name, items in sorted(grouped.items())}


def evaluate(corpus, config=None):
    config = config or default_config()
    baselines = {
        "alive06_exact_overlap": lambda item: (
            legacy_v1(item["goal"], item["excerpt"], config),
            None,
        ),
        "simple_no_stopwords": lambda item: (simple_overlap(item["goal"], item["excerpt"]), None),
        "alive07_multilingual_v2": lambda item: v2_prediction(item, config),
        "conservative_uncertainty": lambda item: conservative_prediction(item, config),
    }
    report = {}
    for name, predictor in baselines.items():
        rows = [(item, *predictor(item)) for item in corpus]
        by_split = {}
        for split, split_rows in sorted(
            (
                (split, [row for row in rows if row[0]["split"] == split])
                for split in {item["split"] for item in corpus}
            )
        ):
            by_split[split] = {
                "overall": score(split_rows),
                "by_language": _group(split_rows, "language"),
            }
        report[name] = {
            "overall": score(rows),
            "by_split": by_split,
            "by_language": _group(rows, "language"),
        }
    return {
        "policy": config.policy,
        "config_fingerprint": config.fingerprint,
        "corpus_sha256": hashlib.sha256(Path(CORPUS).read_bytes()).hexdigest(),
        "corpus_size": len(corpus),
        "baselines": report,
    }


def _percent(value):
    return "n/a" if value is None else f"{value * 100:.1f}%"


def markdown(report):
    lines = [
        "# ALIVE-07 relevance evaluation",
        "",
        f"Policy: `{report['policy']}`  ",
        f"Config fingerprint: `{report['config_fingerprint']}`  ",
        f"Corpus SHA-256: `{report['corpus_sha256']}`  ",
        f"Cases: {report['corpus_size']}",
        "",
        "## Overall baselines",
        "",
        "| Baseline | Precision | Recall | False abstention | "
        "False investigation | Uncertainty | Calls avoided | Owner intervention |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for name, result in report["baselines"].items():
        metric = result["overall"]
        lines.append(
            f"| {name} | {_percent(metric['precision'])} | {_percent(metric['recall'])} | "
            f"{_percent(metric['false_abstention_rate'])} | "
            f"{_percent(metric['false_investigation_rate'])} | "
            f"{_percent(metric['uncertainty_rate'])} | {metric['model_calls_avoided']} | "
            f"{metric['owner_intervention']} |"
        )
    lines += [
        "",
        "## ALIVE-07 v2 held-out by language",
        "",
        "| Language | N | Precision | Recall | False abstention | Uncertainty |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    heldout = report["baselines"]["alive07_multilingual_v2"]["by_split"]["heldout"]["by_language"]
    for language, metric in heldout.items():
        lines.append(
            f"| {language} | {metric['n']} | {_percent(metric['precision'])} | "
            f"{_percent(metric['recall'])} | {_percent(metric['false_abstention_rate'])} | "
            f"{_percent(metric['uncertainty_rate'])} |"
        )
    lines += [
        "",
        "See `relevance-metrics.json` for per-language, per-split "
        "confusion counts and all baselines.",
        "",
        "## Interpretation",
        "",
        "- Relevant recall counts an uncertain decision as not recalled, so a "
        "conservative policy cannot hide behind abstention.",
        "- False abstention counts a relevant label predicted irrelevant; "
        "uncertainty is reported separately.",
        "- Calls avoided counts every non-relevant prediction; it is not evidence "
        "of correct abstention.",
        "- The corpus is controlled and small. It is not a general multilingual benchmark.",
    ]
    return "\n".join(lines) + "\n"


def main():
    corpus = load_corpus()
    report = evaluate(corpus)
    output = ARCHIVE / "evaluation"
    output.mkdir(parents=True, exist_ok=True)
    (output / "relevance-metrics.json").write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    (output / "relevance-metrics.md").write_text(markdown(report), encoding="utf-8")
    corpus_out = ARCHIVE / "corpus"
    corpus_out.mkdir(parents=True, exist_ok=True)
    (corpus_out / "relevance.jsonl").write_bytes(CORPUS.read_bytes())
    print(markdown(report))


if __name__ == "__main__":
    main()
