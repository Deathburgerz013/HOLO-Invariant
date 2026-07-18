"""Similarity helpers and version-bound ingestion receipts for Holo/Sim.

Default behavior is offline-safe. The module will not load or download
sentence-transformer models unless HOLOSIM_ENABLE_EMBEDDINGS=1 is set.

Similarity is a retrieval and ingestion observation. It does not establish
truth, acceptance, authority, or permission to mutate a collection.
"""

from __future__ import annotations

import hashlib
from importlib import metadata
import json
import math
import os
import re
from typing import Any, Iterable, Mapping


DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_RECENT_WINDOW = 100
MAX_RECENT_WINDOW = 1_000_000
ENABLE_EMBEDDINGS_ENV = "HOLOSIM_ENABLE_EMBEDDINGS"
INGESTION_OBSERVATION_TYPE = "holo_ingestion_observation"
INGESTION_OBSERVATION_VERSION = 1
SENTENCE_MODEL_IDENTITY = "all-MiniLM-L6-v2"
MAX_RECEIPT_JSON_DEPTH = 8

_MODEL = None
_NUMPY = None
_MODEL_LOAD_ATTEMPTED = False


class IngestionReceiptError(ValueError):
    """Raised when an ingestion receipt or its inputs are malformed."""


def embeddings_enabled() -> bool:
    return os.getenv(ENABLE_EMBEDDINGS_ENV, "").strip() == "1"


def _load_sentence_model():
    """Lazy-load optional sentence-transformers model only when enabled."""
    global _MODEL, _NUMPY, _MODEL_LOAD_ATTEMPTED

    if not embeddings_enabled():
        return None, None

    if _MODEL_LOAD_ATTEMPTED:
        return (_MODEL if _MODEL is not False else None), _NUMPY

    _MODEL_LOAD_ATTEMPTED = True

    try:
        from sentence_transformers import SentenceTransformer
        import numpy as np

        _MODEL = SentenceTransformer(SENTENCE_MODEL_IDENTITY)
        _NUMPY = np
        return _MODEL, _NUMPY
    except Exception:
        _MODEL = False
        _NUMPY = None
        return None, None


def _tokenize(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z0-9_]+", text.lower()))


def _overlap_similarity(text1: str, text2: str) -> float:
    left = _tokenize(text1)
    right = _tokenize(text2)

    if not left and not right:
        return 1.0

    if not left or not right:
        return 0.0

    return len(left & right) / len(left | right)


def _sklearn_similarity(text1: str, text2: str) -> float | None:
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
        from sklearn.metrics.pairwise import cosine_similarity

        vec = TfidfVectorizer().fit_transform([text1, text2])
        return float(cosine_similarity(vec[0:1], vec[1:2])[0][0])
    except Exception:
        return None


def _sentence_similarity(text1: str, text2: str) -> float | None:
    model, np = _load_sentence_model()

    if model is None or np is None:
        return None

    try:
        emb1 = model.encode([text1])[0]
        emb2 = model.encode([text2])[0]

        denom = float(np.linalg.norm(emb1) * np.linalg.norm(emb2))
        if denom == 0:
            return 0.0

        return float(np.dot(emb1, emb2) / denom)
    except Exception:
        return None


def _package_version(distribution: str) -> str | None:
    try:
        return metadata.version(distribution)
    except metadata.PackageNotFoundError:
        return None


def compute_similarity_observation(text1: str, text2: str) -> dict[str, Any]:
    """Return one similarity score with the exact backend that produced it."""
    text1 = text1 or ""
    text2 = text2 or ""

    sentence_score = _sentence_similarity(text1, text2)
    if sentence_score is not None:
        return {
            "score": sentence_score,
            "backend": "sentence_transformers",
            "backend_version": _package_version("sentence-transformers"),
            "model_identity": SENTENCE_MODEL_IDENTITY,
        }

    sklearn_score = _sklearn_similarity(text1, text2)
    if sklearn_score is not None:
        return {
            "score": sklearn_score,
            "backend": "sklearn_tfidf",
            "backend_version": _package_version("scikit-learn"),
            "model_identity": None,
        }

    return {
        "score": _overlap_similarity(text1, text2),
        "backend": "token_overlap",
        "backend_version": "1",
        "model_identity": None,
    }


def compute_similarity(text1: str, text2: str) -> float:
    """Compute similarity while preserving the existing float API.

    Preference order:
    1. sentence-transformers only if HOLOSIM_ENABLE_EMBEDDINGS=1.
    2. sklearn TF-IDF cosine similarity, if installed.
    3. zero-dependency token-overlap similarity.
    """
    return float(compute_similarity_observation(text1, text2)["score"])


def entry_text(entry: Any) -> str:
    """Extract comparable text from common chain entry shapes."""
    if type(entry) is str:
        return entry
    if isinstance(entry, str):
        raise IngestionReceiptError("entry text must be a plain string")

    if isinstance(entry, Mapping):
        try:
            for key in ("text", "content", "summary", "thought", "message"):
                value = entry.get(key)
                if type(value) is str:
                    return value
                if isinstance(value, str):
                    raise IngestionReceiptError(
                        "entry text must be a plain string"
                    )
            return str(entry)
        except IngestionReceiptError:
            raise
        except Exception as exc:
            raise IngestionReceiptError("entry could not be converted to text") from exc

    try:
        return str(entry)
    except Exception as exc:
        raise IngestionReceiptError("entry could not be converted to text") from exc


def _text_sha256(text: str) -> str:
    try:
        encoded = text.encode("utf-8")
    except UnicodeError as exc:
        raise IngestionReceiptError("text must be valid UTF-8") from exc
    return hashlib.sha256(encoded).hexdigest()


def _require_threshold(value: float) -> float:
    if type(value) not in {int, float}:
        raise IngestionReceiptError("threshold must be a finite number from 0 to 1")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise IngestionReceiptError(
            "threshold must be a finite number from 0 to 1"
        ) from exc
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise IngestionReceiptError("threshold must be a finite number from 0 to 1")
    return result


def _require_recent_window(value: int) -> int:
    if type(value) is not int or not 1 <= value <= MAX_RECENT_WINDOW:
        raise IngestionReceiptError(
            "recent_window must be a positive integer from 1 to "
            f"{MAX_RECENT_WINDOW}"
        )
    return value


def _canonical_hash(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _finalize_ingestion_receipt(body: dict[str, Any]) -> dict[str, Any]:
    try:
        receipt_hash = _canonical_hash(body)
    except (
        TypeError,
        ValueError,
        OverflowError,
        RecursionError,
        UnicodeError,
    ) as exc:
        raise IngestionReceiptError("receipt could not be canonicalized") from exc
    return {**body, "receipt_hash": receipt_hash}


def _window_texts(
    existing_entries: Iterable[Any], recent_window: int
) -> list[str]:
    try:
        entries = list(existing_entries)
    except Exception as exc:
        raise IngestionReceiptError(
            "existing_entries must be an iterable that can be materialized"
        ) from exc
    return [entry_text(entry) for entry in entries[-recent_window:]]


def evaluate_ingestion(
    candidate: str,
    existing_entries: Iterable[Any],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    recent_window: int = DEFAULT_RECENT_WINDOW,
) -> dict[str, Any]:
    """Observe whether candidate text is novel enough to ingest.

    The result is read-only. Callers retain all mutation authority.
    """
    if type(candidate) is not str:
        raise IngestionReceiptError("candidate must be a plain string")
    checked_threshold = _require_threshold(threshold)
    checked_window = _require_recent_window(recent_window)
    texts = _window_texts(existing_entries, checked_window)

    comparisons: list[dict[str, Any]] = []
    best_index: int | None = None
    best_score = -1.0

    for index, text in enumerate(texts):
        observation = compute_similarity_observation(candidate, text)
        raw_score = observation.get("score")
        if type(raw_score) not in {int, float}:
            raise IngestionReceiptError("similarity score must be a finite number")
        try:
            score = float(raw_score)
        except (OverflowError, ValueError) as exc:
            raise IngestionReceiptError(
                "similarity score must be a finite number from -1 to 1"
            ) from exc
        if (
            not math.isfinite(score)
            or score < -1.0 - 1e-12
            or score > 1.0 + 1e-12
        ):
            raise IngestionReceiptError(
                "similarity score must be a finite number from -1 to 1"
            )
        score = min(1.0, max(-1.0, score))
        observation = {**observation, "score": score}
        comparison = {
            "window_index": index,
            "entry_sha256": _text_sha256(text),
            **observation,
        }
        comparisons.append(comparison)
        if best_index is None or score > best_score:
            best_score = score
            best_index = index

    should_keep = not any(
        comparison["score"] >= checked_threshold
        for comparison in comparisons
    )
    best = comparisons[best_index] if best_index is not None else None
    body = {
        "type": INGESTION_OBSERVATION_TYPE,
        "version": INGESTION_OBSERVATION_VERSION,
        "candidate_sha256": _text_sha256(candidate),
        "recent_entry_hashes": [_text_sha256(text) for text in texts],
        "threshold": checked_threshold,
        "recent_window": checked_window,
        "comparisons": comparisons,
        "best_match_sha256": None if best is None else best["entry_sha256"],
        "best_score": 0.0 if best is None else best["score"],
        "should_ingest": should_keep,
        "reason": "NOVEL" if should_keep else "SIMILAR_TO_EXISTING",
        "current": True,
        "stale_reason": None,
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "Similarity supports retrieval and ingestion selection only. "
            "It does not establish truth, acceptance, or authority."
        ),
    }
    return _finalize_ingestion_receipt(body)


def _validate_ingestion_receipt(receipt: Mapping[str, Any]) -> None:
    if type(receipt) is not dict:
        raise IngestionReceiptError("receipt must be a plain dictionary")
    _validate_closed_json(receipt)
    if receipt.get("type") != INGESTION_OBSERVATION_TYPE:
        raise IngestionReceiptError("receipt type is invalid")
    if (
        type(receipt.get("version")) is not int
        or receipt.get("version") != INGESTION_OBSERVATION_VERSION
    ):
        raise IngestionReceiptError("receipt version is invalid")
    if receipt.get("accepted") is not False:
        raise IngestionReceiptError("receipt cannot grant acceptance")
    if receipt.get("write_authority") != "NONE":
        raise IngestionReceiptError("receipt cannot grant write authority")
    receipt_hash = receipt.get("receipt_hash")
    if not isinstance(receipt_hash, str) or not re.fullmatch(
        r"[0-9a-f]{64}", receipt_hash
    ):
        raise IngestionReceiptError("receipt_hash must be 64 lowercase hex characters")
    body = dict(receipt)
    body.pop("receipt_hash")
    try:
        calculated_hash = _canonical_hash(body)
    except (TypeError, ValueError, RecursionError, UnicodeError) as exc:
        raise IngestionReceiptError("receipt is not canonical JSON") from exc
    if calculated_hash != receipt_hash:
        raise IngestionReceiptError("receipt hash mismatch")
    _validate_ingestion_receipt_semantics(receipt)


def _validate_closed_json(value: Any) -> None:
    active: set[int] = set()

    def visit(item: Any, depth: int) -> None:
        if depth > MAX_RECEIPT_JSON_DEPTH:
            raise IngestionReceiptError("receipt exceeds maximum JSON depth")
        if item is None or type(item) in {bool, int}:
            return
        if type(item) is str:
            try:
                item.encode("utf-8")
            except UnicodeError as exc:
                raise IngestionReceiptError(
                    "receipt strings must be valid UTF-8"
                ) from exc
            return
        if type(item) is float:
            if not math.isfinite(item):
                raise IngestionReceiptError("receipt numbers must be finite")
            return
        if type(item) not in {dict, list}:
            raise IngestionReceiptError("receipt must contain only plain JSON values")
        identity = id(item)
        if identity in active:
            raise IngestionReceiptError("receipt must not contain cycles")
        active.add(identity)
        try:
            if type(item) is dict:
                for key, child in item.items():
                    if type(key) is not str:
                        raise IngestionReceiptError("receipt object keys must be strings")
                    visit(child, depth + 1)
            else:
                for child in item:
                    visit(child, depth + 1)
        finally:
            active.remove(identity)

    visit(value, 0)


def _require_sha256(value: Any, field: str) -> str:
    if type(value) is not str or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise IngestionReceiptError(f"{field} must be 64 lowercase hex characters")
    return value


def _require_receipt_score(value: Any, field: str) -> float:
    if type(value) not in {int, float}:
        raise IngestionReceiptError(f"{field} must be a finite number from -1 to 1")
    try:
        score = float(value)
    except (OverflowError, ValueError) as exc:
        raise IngestionReceiptError(
            f"{field} must be a finite number from -1 to 1"
        ) from exc
    if not math.isfinite(score) or not -1.0 <= score <= 1.0:
        raise IngestionReceiptError(f"{field} must be a finite number from -1 to 1")
    return score


def _validate_ingestion_receipt_semantics(receipt: Mapping[str, Any]) -> None:
    expected_fields = {
        "type", "version", "candidate_sha256", "recent_entry_hashes",
        "threshold", "recent_window", "comparisons", "best_match_sha256",
        "best_score", "should_ingest", "reason", "current", "stale_reason",
        "accepted", "write_authority", "interpretation_notice", "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise IngestionReceiptError("receipt fields do not match the versioned schema")
    _require_sha256(receipt["candidate_sha256"], "candidate_sha256")
    threshold = _require_threshold(receipt["threshold"])
    recent_window = _require_recent_window(receipt["recent_window"])
    hashes = receipt["recent_entry_hashes"]
    comparisons = receipt["comparisons"]
    if type(hashes) is not list:
        raise IngestionReceiptError("recent_entry_hashes must be a list")
    if type(comparisons) is not list:
        raise IngestionReceiptError("receipt comparisons must be a list")
    if len(hashes) != len(comparisons):
        raise IngestionReceiptError("comparison count must match recent entry hashes")
    if len(comparisons) > recent_window:
        raise IngestionReceiptError("comparison count exceeds recent_window")
    for index, value in enumerate(hashes):
        _require_sha256(value, f"recent_entry_hashes[{index}]")

    scores: list[float] = []
    comparison_fields = {
        "window_index", "entry_sha256", "score", "backend",
        "backend_version", "model_identity",
    }
    for index, comparison in enumerate(comparisons):
        if type(comparison) is not dict or set(comparison) != comparison_fields:
            raise IngestionReceiptError("receipt comparison fields are invalid")
        if (
            type(comparison["window_index"]) is not int
            or comparison["window_index"] != index
        ):
            raise IngestionReceiptError("comparison indexes must be ordered")
        if comparison["entry_sha256"] != hashes[index]:
            raise IngestionReceiptError("comparison hash does not match its entry")
        scores.append(_require_receipt_score(comparison["score"], "comparison score"))
        if type(comparison["backend"]) is not str or not comparison["backend"]:
            raise IngestionReceiptError("comparison backend must be a nonempty string")
        for field in ("backend_version", "model_identity"):
            if comparison[field] is not None and type(comparison[field]) is not str:
                raise IngestionReceiptError(f"comparison {field} must be a string or null")

    best_score = _require_receipt_score(receipt["best_score"], "best_score")
    if scores:
        best_index = max(range(len(scores)), key=scores.__getitem__)
        if best_score != scores[best_index]:
            raise IngestionReceiptError("best_score is inconsistent with comparisons")
        if receipt["best_match_sha256"] != hashes[best_index]:
            raise IngestionReceiptError("best match is inconsistent with comparisons")
    elif best_score != 0.0 or receipt["best_match_sha256"] is not None:
        raise IngestionReceiptError("empty comparisons require an empty best match")

    should_ingest = receipt["should_ingest"]
    if type(should_ingest) is not bool:
        raise IngestionReceiptError("should_ingest must be boolean")
    expected_decision = not any(score >= threshold for score in scores)
    if should_ingest != expected_decision:
        raise IngestionReceiptError("ingestion decision is inconsistent with comparisons")
    expected_reason = "NOVEL" if should_ingest else "SIMILAR_TO_EXISTING"
    if receipt["reason"] != expected_reason:
        raise IngestionReceiptError("receipt reason is inconsistent with its decision")
    if receipt["current"] is not True or receipt["stale_reason"] is not None:
        raise IngestionReceiptError("stored observation must begin current and unstaled")
    if type(receipt["interpretation_notice"]) is not str:
        raise IngestionReceiptError("interpretation_notice must be a string")


def _backend_trace(receipt: Mapping[str, Any]) -> list[dict[str, Any]]:
    comparisons = receipt.get("comparisons")
    if not isinstance(comparisons, list):
        raise IngestionReceiptError("receipt comparisons must be a list")
    trace: list[dict[str, Any]] = []
    for comparison in comparisons:
        if not isinstance(comparison, Mapping):
            raise IngestionReceiptError("receipt comparison must be an object")
        trace.append({
            "backend": comparison.get("backend"),
            "backend_version": comparison.get("backend_version"),
            "model_identity": comparison.get("model_identity"),
        })
    return trace


def check_ingestion_receipt_current(
    receipt: Mapping[str, Any],
    candidate: str,
    existing_entries: Iterable[Any],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    recent_window: int = DEFAULT_RECENT_WINDOW,
) -> dict[str, Any]:
    """Check whether a prior ingestion observation still binds current inputs."""
    _validate_ingestion_receipt(receipt)
    if type(candidate) is not str:
        raise IngestionReceiptError("candidate must be a plain string")
    checked_threshold = _require_threshold(threshold)
    checked_window = _require_recent_window(recent_window)
    texts = _window_texts(existing_entries, checked_window)

    if receipt.get("candidate_sha256") != _text_sha256(candidate):
        return {"current": False, "stale_reason": "CANDIDATE_CHANGED"}
    if (
        receipt.get("threshold") != checked_threshold
        or receipt.get("recent_window") != checked_window
    ):
        return {"current": False, "stale_reason": "CONFIG_CHANGED"}
    if receipt.get("recent_entry_hashes") != [
        _text_sha256(text) for text in texts
    ]:
        return {"current": False, "stale_reason": "COMPARISON_WINDOW_CHANGED"}

    expected = evaluate_ingestion(
        candidate,
        texts,
        threshold=checked_threshold,
        recent_window=checked_window,
    )
    if _backend_trace(receipt) != _backend_trace(expected):
        return {"current": False, "stale_reason": "ENVIRONMENT_CHANGED"}
    if dict(receipt) != expected:
        return {"current": False, "stale_reason": "OBSERVATION_CHANGED"}
    return {"current": True, "stale_reason": None}


def should_ingest(
    text: str,
    existing_entries: Iterable[Any],
    threshold: float = DEFAULT_SIMILARITY_THRESHOLD,
    recent_window: int = DEFAULT_RECENT_WINDOW,
) -> bool:
    """Return False when text is too similar to recent entries."""
    entries = list(existing_entries)[-recent_window:]

    for entry in entries:
        candidate = entry_text(entry)
        if compute_similarity(text, candidate) >= threshold:
            return False

    return True


def best_match(
    text: str,
    existing_entries: Iterable[Any],
    recent_window: int = DEFAULT_RECENT_WINDOW,
) -> dict[str, Any]:
    """Return the most similar recent entry and score."""
    entries = list(existing_entries)[-recent_window:]

    best_score = -1.0
    best_entry: Any = None

    for entry in entries:
        candidate = entry_text(entry)
        score = compute_similarity(text, candidate)

        if best_entry is None or score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is None:
        return {"score": 0.0, "entry": None, "text": ""}

    return {
        "score": float(best_score),
        "entry": best_entry,
        "text": entry_text(best_entry),
    }
