import shutil
from pathlib import Path

import pytest

from alive.relevance import (
    RelevanceConfigError,
    default_config,
    detect_language,
    evaluate_relevance,
    load_relevance_config,
)

ROOT = Path(__file__).parents[1] / "config" / "relevance"
EN_TEXT = "Python is an easy to learn, powerful programming language."
ZH_TEXT = "Python 是一种易于学习、功能强大的编程语言。"
AR_TEXT = "البرمجة سهلة التعلم."


def test_default_config_is_external_versioned_and_stable():
    config = default_config()
    assert config.policy == "deterministic-multilingual-relevance-v2"
    assert config.supported_languages == ("en", "zh", "ar")
    assert config.default_language == "en"
    assert config.unsupported_behavior == "uncertain"
    assert config.fingerprint == load_relevance_config(ROOT).fingerprint
    assert config.languages["en"].strategy == "words"
    assert config.languages["zh"].strategy == "character_ngrams"
    assert config.languages["ar"].normalization == "nfkc_casefold_arabic"


def test_english_relevance_preserves_alive06_style_decisions():
    config = load_relevance_config(ROOT)
    relevant = evaluate_relevance("Learn Python", EN_TEXT, "auto", config)
    assert relevant["status"] == "supported"
    assert relevant["language"] == "en"
    assert relevant["relevant"] is True
    assert "python" in relevant["matched_terms"]

    irrelevant = evaluate_relevance("Check coolant temperature", EN_TEXT, "auto", config)
    assert irrelevant["status"] == "supported"
    assert irrelevant["relevant"] is False
    assert irrelevant["matched_terms"] == []


def test_chinese_uses_character_ngrams_not_whitespace_words():
    config = load_relevance_config(ROOT)
    relevant = evaluate_relevance("学习 Python 编程", ZH_TEXT, "zh", config)
    assert relevant["status"] == "supported"
    assert relevant["strategy"] == "character_ngrams"
    assert relevant["relevant"] is True
    assert {"学习", "编程"} <= set(relevant["matched_terms"])

    irrelevant = evaluate_relevance("天气预报", ZH_TEXT, "zh", config)
    assert irrelevant["relevant"] is False


def test_arabic_normalizes_diacritics_and_orthographic_variants():
    config = load_relevance_config(ROOT)
    relevant = evaluate_relevance("تُعَلّم البرمجة", AR_TEXT, "ar", config)
    assert relevant["status"] == "supported"
    assert relevant["relevant"] is True
    assert "البرمجه" in relevant["matched_terms"]

    irrelevant = evaluate_relevance("حالة الطقس", AR_TEXT, "ar", config)
    assert irrelevant["relevant"] is False


def test_language_detection_and_uncertainty_are_explicit():
    config = load_relevance_config(ROOT)
    assert detect_language(ZH_TEXT, config)["language"] == "zh"
    assert detect_language(AR_TEXT, config)["language"] == "ar"
    assert detect_language("Hello 你好", config)["status"] == "uncertain"
    unsupported = detect_language("Привет мир", config)
    assert unsupported["status"] == "uncertain"
    assert unsupported["language_source"] == "unsupported"

    mismatch = evaluate_relevance("Learn Python", EN_TEXT, "zh", config)
    assert mismatch["status"] == "uncertain"
    assert mismatch["language_source"] == "explicit_mismatch"
    assert mismatch["relevant"] is None


def test_missing_language_resource_fails_clearly(tmp_path):
    target = tmp_path / "relevance"
    shutil.copytree(ROOT, target)
    (target / "languages" / "ar.toml").unlink()
    with pytest.raises(RelevanceConfigError, match="missing"):
        load_relevance_config(target)


def test_invalid_toml_and_unknown_keys_fail_closed(tmp_path):
    target = tmp_path / "relevance"
    shutil.copytree(ROOT, target)
    (target / "languages" / "zh.toml").write_text("not = [", encoding="utf-8")
    with pytest.raises(RelevanceConfigError, match="Invalid TOML"):
        load_relevance_config(target)

    shutil.rmtree(target)
    shutil.copytree(ROOT, target)
    text = (target / "languages" / "en.toml").read_text(encoding="utf-8")
    (target / "languages" / "en.toml").write_text(
        text.replace("minimum_token_length = 4", "minimum_token_length = 4\nexecutable = true"),
        encoding="utf-8",
    )
    with pytest.raises(RelevanceConfigError, match="Unknown keys"):
        load_relevance_config(target)
