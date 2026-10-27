from alive.relevance import default_config
from scripts.relevance07 import evaluate, legacy_v1, load_corpus, policy_v2, simple_overlap


def test_frozen_corpus_has_independent_splits_and_labels():
    corpus = load_corpus()
    assert len(corpus) == 27
    assert {item["split"] for item in corpus} == {"dev", "calibration", "heldout"}
    assert {item["label"] for item in corpus} == {"relevant", "irrelevant", "uncertain"}
    assert {item["language"] for item in corpus} == {"en", "zh", "ar", "auto"}
    assert len({item["id"] for item in corpus}) == len(corpus)


def test_v2_evaluation_reports_per_language_and_beats_v1_recall():
    report = evaluate(load_corpus())
    v1 = report["baselines"]["alive06_exact_overlap"]["overall"]
    v2 = report["baselines"]["alive07_multilingual_v2"]["overall"]
    assert v2["recall"] > v1["recall"]
    assert v2["false_abstention_rate"] < v1["false_abstention_rate"]
    assert report["baselines"]["alive07_multilingual_v2"]["by_language"].keys() >= {
        "en",
        "zh",
        "ar",
        "auto",
    }
    heldout = report["baselines"]["alive07_multilingual_v2"]["by_split"]["heldout"]
    assert heldout["by_language"]["ar"]["recall"] == 1.0
    assert heldout["by_language"]["zh"]["false_abstention_rate"] > 0
    assert v2["owner_intervention"] > 0


def test_baselines_are_distinct_and_deterministic():
    config = default_config()
    assert legacy_v1("Learn Python", "Python is a language", config) == "relevant"
    assert legacy_v1("Check coolant", "Python is a language", config) == "irrelevant"
    assert simple_overlap("Learn Python", "Python is a language") == "relevant"
    chinese = policy_v2(
        {
            "goal": "学习 Python 编程",
            "excerpt": "Python 是一种易于学习、功能强大的编程语言。",
            "language": "zh",
        },
        config,
    )
    assert chinese["status"] == "supported" and chinese["relevant"] is True
