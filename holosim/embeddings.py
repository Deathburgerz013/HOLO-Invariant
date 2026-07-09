"""Similarity helpers for Holo/Sim ingestion.

Default behavior is offline-safe. The module will not load or download
sentence-transformer models unless HOLOSIM_ENABLE_EMBEDDINGS=1 is set.
"""

from __future__ import annotations

import os
import re
from typing import Any, Iterable, Mapping


DEFAULT_SIMILARITY_THRESHOLD = 0.85
DEFAULT_RECENT_WINDOW = 100
ENABLE_EMBEDDINGS_ENV = "HOLOSIM_ENABLE_EMBEDDINGS"

_MODEL = None
_NUMPY = None
_MODEL_LOAD_ATTEMPTED = False


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

        _MODEL = SentenceTransformer("all-MiniLM-L6-v2")
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


def compute_similarity(text1: str, text2: str) -> float:
    """Compute similarity between two text strings.

    Preference order:
    1. sentence-transformers only if HOLOSIM_ENABLE_EMBEDDINGS=1.
    2. sklearn TF-IDF cosine similarity, if installed.
    3. zero-dependency token-overlap similarity.
    """
    text1 = text1 or ""
    text2 = text2 or ""

    sentence_score = _sentence_similarity(text1, text2)
    if sentence_score is not None:
        return sentence_score

    sklearn_score = _sklearn_similarity(text1, text2)
    if sklearn_score is not None:
        return sklearn_score

    return _overlap_similarity(text1, text2)


def entry_text(entry: Any) -> str:
    """Extract comparable text from common chain entry shapes."""
    if isinstance(entry, str):
        return entry

    if isinstance(entry, Mapping):
        for key in ("text", "content", "summary", "thought", "message"):
            value = entry.get(key)
            if isinstance(value, str):
                return value

        try:
            return str(entry)
        except Exception:
            return ""

    return str(entry)


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

        if score > best_score:
            best_score = score
            best_entry = entry

    if best_entry is None:
        return {"score": 0.0, "entry": None, "text": ""}

    return {
        "score": float(best_score),
        "entry": best_entry,
        "text": entry_text(best_entry),
    }