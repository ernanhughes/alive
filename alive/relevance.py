"""Deterministic, config-driven lexical relevance. No semantic or model inference."""

import hashlib
import json
import re
import tomllib
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DEFAULT_ROOT = Path(__file__).resolve().parents[1] / "config" / "relevance"
ALLOWED_STRATEGIES = {"words", "character_ngrams"}
ALLOWED_NORMALIZATIONS = {"nfkc", "nfkc_casefold", "nfkc_casefold_arabic"}

LATIN = re.compile(r"[A-Za-z\u00c0-\u024f]")
HAN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]")
ARABIC = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]")
CYRILLIC = re.compile(r"[\u0400-\u04ff]")
DEVANAGARI = re.compile(r"[\u0900-\u097f]")
HAN_RUN = re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff]+")
ARABIC_WORD = re.compile(r"[\u0600-\u06ff\u0750-\u077f\u08a0-\u08ff]+")
ENGLISH_WORD = re.compile(r"[a-z0-9]+")


class RelevanceConfigError(ValueError):
    """Raised when the external relevance configuration is missing or invalid."""


@dataclass(frozen=True)
class LanguageProfile:
    language: str
    strategy: str
    normalization: str
    minimum_token_length: int
    stopwords: tuple[str, ...]
    ngram_size: int = 1
    stop_characters: tuple[str, ...] = ()


@dataclass(frozen=True)
class RelevanceConfig:
    schema_version: int
    policy: str
    default_language: str
    supported_languages: tuple[str, ...]
    unsupported_behavior: str
    languages: dict[str, LanguageProfile]
    fingerprint: str
    root: str


def _read_toml(path):
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise RelevanceConfigError(f"Relevance configuration is missing: {path}") from exc
    except UnicodeDecodeError as exc:
        raise RelevanceConfigError(f"Relevance configuration is not UTF-8: {path}") from exc
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise RelevanceConfigError(f"Invalid TOML in {path}: {exc}") from exc


def _require_keys(data, allowed, path):
    extra = sorted(set(data) - set(allowed))
    if extra:
        raise RelevanceConfigError(f"Unknown keys in {path}: {', '.join(extra)}")
    missing = sorted(set(allowed) - set(data))
    if missing:
        raise RelevanceConfigError(f"Missing keys in {path}: {', '.join(missing)}")


def _string_list(value, path, key, allow_empty=True):
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise RelevanceConfigError(f"{path}: {key} must be a list of strings")
    if not allow_empty and not value:
        raise RelevanceConfigError(f"{path}: {key} must not be empty")
    return tuple(value)


def _positive_int(value, path, key, minimum=1, maximum=64):
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise RelevanceConfigError(f"{path}: {key} must be an integer in [{minimum}, {maximum}]")
    return value


def load_relevance_config(root=None):
    """Load and validate policy plus every declared language resource."""

    base = Path(root) if root is not None else DEFAULT_ROOT
    policy_path = base / "policy.toml"
    policy_data = _read_toml(policy_path)
    _require_keys(
        policy_data,
        {
            "schema_version",
            "policy",
            "default_language",
            "supported_languages",
            "unsupported_behavior",
        },
        policy_path,
    )
    schema_version = _positive_int(policy_data["schema_version"], policy_path, "schema_version")
    if schema_version != 1:
        raise RelevanceConfigError(f"{policy_path}: unsupported schema_version {schema_version}")
    policy = policy_data["policy"]
    if not isinstance(policy, str) or not policy:
        raise RelevanceConfigError(f"{policy_path}: policy must be a non-empty string")
    default_language = policy_data["default_language"]
    supported = _string_list(
        policy_data["supported_languages"], policy_path, "supported_languages", allow_empty=False
    )
    if default_language not in supported:
        raise RelevanceConfigError(f"{policy_path}: default language must be supported")
    if policy_data["unsupported_behavior"] != "uncertain":
        raise RelevanceConfigError(f"{policy_path}: unsupported_behavior must be 'uncertain'")

    languages = {}
    raw_config = {"policy": policy_data, "languages": {}}
    for language in supported:
        path = base / "languages" / f"{language}.toml"
        data = _read_toml(path)
        _require_keys(
            data,
            {
                "schema_version",
                "language",
                "strategy",
                "normalization",
                "minimum_token_length",
                "stopwords",
                "ngram_size",
                "stop_characters",
            },
            path,
        )
        version = _positive_int(data["schema_version"], path, "schema_version")
        if version != 1:
            raise RelevanceConfigError(f"{path}: unsupported schema_version {version}")
        if data["language"] != language:
            raise RelevanceConfigError(f"{path}: language must equal '{language}'")
        strategy = data["strategy"]
        if strategy not in ALLOWED_STRATEGIES:
            raise RelevanceConfigError(f"{path}: unsupported strategy '{strategy}'")
        normalization = data["normalization"]
        if normalization not in ALLOWED_NORMALIZATIONS:
            raise RelevanceConfigError(f"{path}: unsupported normalization '{normalization}'")
        minimum = _positive_int(data["minimum_token_length"], path, "minimum_token_length")
        stopwords = _string_list(data["stopwords"], path, "stopwords")
        ngram_size = _positive_int(data["ngram_size"], path, "ngram_size", maximum=4)
        stop_characters = _string_list(data["stop_characters"], path, "stop_characters")
        languages[language] = LanguageProfile(
            language=language,
            strategy=strategy,
            normalization=normalization,
            minimum_token_length=minimum,
            stopwords=stopwords,
            ngram_size=ngram_size,
            stop_characters=stop_characters,
        )
        raw_config["languages"][language] = data

    canonical = json.dumps(
        raw_config, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    ).encode("utf-8")
    return RelevanceConfig(
        schema_version=schema_version,
        policy=policy,
        default_language=default_language,
        supported_languages=tuple(supported),
        unsupported_behavior=policy_data["unsupported_behavior"],
        languages=languages,
        fingerprint=hashlib.sha256(canonical).hexdigest(),
        root=str(base),
    )


@lru_cache(maxsize=1)
def default_config():
    return load_relevance_config()


def _script_counts(text):
    return {
        "latin": len(LATIN.findall(text)),
        "han": len(HAN.findall(text)),
        "arabic": len(ARABIC.findall(text)),
        "cyrillic": len(CYRILLIC.findall(text)),
        "devanagari": len(DEVANAGARI.findall(text)),
    }


def _supported_script(language):
    return {"en": "latin", "zh": "han", "ar": "arabic"}.get(language)


def detect_language(text, config, requested="auto"):
    """Return an explicit, uncertain language decision. No model call is made."""

    counts = _script_counts(text)
    total = sum(counts.values())
    ratios = {script: (count / total if total else 0.0) for script, count in counts.items()}
    if total < 3:
        return {
            "language": "unknown",
            "language_source": "unknown",
            "language_supported": False,
            "status": "uncertain",
            "ratios": ratios,
            "reason": "Too little script-bearing text to select a language.",
        }
    if requested != "auto":
        if requested not in config.languages:
            return {
                "language": requested,
                "language_source": "explicit_unsupported",
                "language_supported": False,
                "status": "uncertain",
                "ratios": ratios,
                "reason": f"Selected language '{requested}' is not supported.",
            }
        expected = _supported_script(requested)
        if ratios.get(expected, 0.0) < 0.2:
            return {
                "language": requested,
                "language_source": "explicit_mismatch",
                "language_supported": True,
                "status": "uncertain",
                "ratios": ratios,
                "reason": f"Selected language '{requested}' does not match the text script.",
            }
        return {
            "language": requested,
            "language_source": "explicit",
            "language_supported": True,
            "status": "supported",
            "ratios": ratios,
            "reason": "Owner-selected language matched the text script.",
        }

    mixed = sum(1 for ratio in ratios.values() if ratio >= 0.25) >= 2
    if mixed:
        if ratios["han"] >= 0.4 and ratios["latin"] <= 0.6:
            return {
                "language": "zh",
                "language_source": "detected",
                "language_supported": True,
                "status": "supported",
                "ratios": ratios,
                "reason": "Han text with Latin technical terms; selected Chinese.",
            }
        if ratios["arabic"] >= 0.4 and ratios["latin"] <= 0.6:
            return {
                "language": "ar",
                "language_source": "detected",
                "language_supported": True,
                "status": "supported",
                "ratios": ratios,
                "reason": "Arabic text with Latin technical terms; selected Arabic.",
            }
        return {
            "language": "mixed",
            "language_source": "mixed",
            "language_supported": False,
            "status": "uncertain",
            "ratios": ratios,
            "reason": "Multiple scripts are materially present; relevance is uncertain.",
        }

    dominant_script, dominant_ratio = max(ratios.items(), key=lambda item: item[1])
    if dominant_ratio < 0.5:
        return {
            "language": "unknown",
            "language_source": "unknown",
            "language_supported": False,
            "status": "uncertain",
            "ratios": ratios,
            "reason": "No script has a clear majority.",
        }
    if dominant_script not in {"latin", "han", "arabic"}:
        return {
            "language": dominant_script,
            "language_source": "unsupported",
            "language_supported": False,
            "status": "uncertain",
            "ratios": ratios,
            "reason": f"Detected script '{dominant_script}' is not supported.",
        }
    language = {"latin": "en", "han": "zh", "arabic": "ar"}[dominant_script]
    if language not in config.languages:
        return {
            "language": language,
            "language_source": "detected_unsupported",
            "language_supported": False,
            "status": "uncertain",
            "ratios": ratios,
            "reason": f"Detected language '{language}' has no configured profile.",
        }
    return {
        "language": language,
        "language_source": "detected",
        "language_supported": True,
        "status": "supported",
        "ratios": ratios,
        "reason": f"Detected {language} from the {dominant_script} script.",
    }


def _normalize(text, mode):
    text = unicodedata.normalize("NFKC", text)
    if mode in {"nfkc_casefold", "nfkc_casefold_arabic"}:
        text = text.casefold()
    if mode == "nfkc_casefold_arabic":
        text = re.sub(r"[\u064b-\u065f\u0670\u0640]", "", text)
        text = text.translate(
            str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه"})
        )
    return text


def _word_tokens(text, profile, language):
    normalized = _normalize(text, profile.normalization)
    pattern = ENGLISH_WORD if language == "en" else ARABIC_WORD
    stopwords = {_normalize(term, profile.normalization) for term in profile.stopwords}
    return {
        token
        for token in pattern.findall(normalized)
        if len(token) >= profile.minimum_token_length and token not in stopwords
    }


def _han_ngrams(text, profile):
    normalized = _normalize(text, profile.normalization)
    result = set()
    for run in HAN_RUN.findall(normalized):
        if len(run) < profile.ngram_size:
            candidates = [run]
        else:
            candidates = [
                run[index : index + profile.ngram_size]
                for index in range(len(run) - profile.ngram_size + 1)
            ]
        for candidate in candidates:
            if len(candidate) < profile.minimum_token_length:
                continue
            if any(character in profile.stop_characters for character in candidate):
                continue
            result.add(candidate)
    return result


def tokens(text, profile):
    if profile.strategy == "character_ngrams":
        return _han_ngrams(text, profile)
    return _word_tokens(text, profile, profile.language)


def evaluate_relevance(goal, excerpt, language="auto", config=None):
    """Evaluate goal/excerpt overlap with explicit uncertainty and provenance."""

    config = config or default_config()
    excerpt_language = detect_language(excerpt, config, language)
    goal_language = detect_language(goal, config, language)
    base = {
        "policy": config.policy,
        "config_fingerprint": config.fingerprint,
        "language_requested": language,
        "language": excerpt_language["language"],
        "language_source": excerpt_language["language_source"],
        "language_supported": excerpt_language["language_supported"],
        "goal_language": goal_language["language"],
        "goal_language_source": goal_language["language_source"],
        "script_ratios": excerpt_language["ratios"],
        "status": "uncertain",
        "relevant": None,
        "matched_terms": [],
        "strategy": None,
        "normalization": None,
        "basis": "No relevance decision was made.",
        "uncertainty_reason": None,
    }
    if excerpt_language["status"] != "supported":
        return base | {
            "uncertainty_reason": excerpt_language["reason"],
            "basis": excerpt_language["reason"],
        }
    if goal_language["status"] != "supported":
        return base | {
            "language": goal_language["language"],
            "language_source": "goal_" + goal_language["language_source"],
            "language_supported": False,
            "uncertainty_reason": goal_language["reason"],
            "basis": goal_language["reason"],
        }
    if goal_language["language"] != excerpt_language["language"]:
        return base | {
            "language": "mixed",
            "language_source": "goal_excerpt_mismatch",
            "language_supported": False,
            "uncertainty_reason": "Goal and excerpt languages differ.",
            "basis": "Goal and excerpt languages differ; no automatic lexical decision.",
        }
    profile = config.languages[excerpt_language["language"]]
    goal_terms = tokens(goal, profile)
    excerpt_terms = tokens(excerpt, profile)
    matched = sorted(goal_terms & excerpt_terms)
    basis = (
        "Exact content-token overlap after configured normalization; "
        "no semantic or model inference."
        if profile.strategy == "words"
        else "Character n-gram overlap after configured normalization; "
        "no word segmentation or semantic inference."
    )
    return base | {
        "language": excerpt_language["language"],
        "language_source": excerpt_language["language_source"],
        "language_supported": True,
        "status": "supported",
        "relevant": bool(matched),
        "matched_terms": matched[:20],
        "strategy": profile.strategy,
        "normalization": profile.normalization,
        "basis": basis,
        "uncertainty_reason": None,
        "goal_term_count": len(goal_terms),
        "excerpt_term_count": len(excerpt_terms),
    }
