"""Read-only delta generalization for Holo/Sim.

Normalizes raw deltas, detects structural patterns, and routes each delta
toward every relevant domain spine.

This module never writes to HoloChain. Persistence remains the responsibility
of Holo_Sim after invariant evaluation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Mapping

try:
    from holosim.hooks import normalize_event, normalize_text, stable_hash
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.hooks import normalize_event, normalize_text, stable_hash


GENERALIZER_TYPE = "holo_generalization"
GENERALIZER_VERSION = "0.2"


SPINE_ROUTES: Dict[str, tuple[str, ...]] = {
    "physics": (
        "physics",
        "force",
        "energy",
        "quantum",
        "gravity",
        "mass",
        "motion",
        "field",
        "entropy",
        "causality",
        "dimension",
        "compression",
        "stability",
        "state space",
    ),
    "biology": (
        "biology",
        "cell",
        "gene",
        "genetic",
        "organism",
        "evolution",
        "adaptation",
        "metabolism",
        "neural",
        "growth",
    ),
    "chemistry": (
        "chemistry",
        "atom",
        "molecule",
        "chemical",
        "reaction",
        "bond",
        "element",
        "compound",
        "catalyst",
    ),
    "mathematics": (
        "math",
        "mathematics",
        "equation",
        "formula",
        "theorem",
        "proof",
        "function",
        "integer",
        "geometry",
        "algebra",
        "calculus",
        "matrix",
        "recursive",
        "recurrence",
        "squared",
        "(c + i + e)",
        "(c+i+e)",
    ),
    "computation": (
        "computer",
        "computation",
        "software",
        "algorithm",
        "python",
        "model",
        "llm",
        "runtime",
        "chain",
        "hash",
        "merkle",
        "api",
        "compression",
        "persistence",
    ),
    "neuroscience_psychology": (
        "brain",
        "cognition",
        "memory",
        "psychology",
        "neuron",
        "conscious",
        "perception",
        "emotion",
        "attention",
    ),
    "philosophy_ontology": (
        "ontology",
        "existence",
        "being",
        "identity",
        "consciousness",
        "truth",
        "meaning",
        "reality",
        "fixed point",
    ),
    "logic_epistemology": (
        "logic",
        "knowledge",
        "evidence",
        "validity",
        "inference",
        "premise",
        "conclusion",
        "epistemology",
        "verified",
        "verification",
        "invariant",
    ),
}


def canonical_json(value: Any) -> str:
    """Serialize JSON-like content deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def full_hash(value: Any) -> str:
    """Return a complete SHA-256 digest."""
    return hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()


def extract_text(payload: Mapping[str, Any]) -> str:
    """Extract searchable text from a normalized payload."""
    parts: list[str] = []

    content = payload.get("content")
    if content is not None:
        parts.append(str(content))

    event = payload.get("event")
    if event is not None:
        parts.append(canonical_json(event))

    file_data = payload.get("file")
    if file_data is not None:
        parts.append(canonical_json(file_data))

    tags = payload.get("tags")
    if tags:
        parts.extend(str(tag) for tag in tags)

    return " ".join(parts).lower()


def phrase_present(text: str, phrase: str) -> bool:
    """Match phrases while reducing accidental partial-word matches."""
    phrase = phrase.lower()

    if any(character in phrase for character in "()^+"):
        return phrase in text

    if " " in phrase:
        return phrase in text

    return bool(
        re.search(
            rf"\b{re.escape(phrase)}\b",
            text,
            flags=re.IGNORECASE,
        )
    )


def detect_patterns(payload: Mapping[str, Any]) -> list[str]:
    """Detect structural characteristics without changing the payload."""
    patterns: list[str] = []

    payload_type = payload.get("type")

    if payload_type == "normalized_text":
        patterns.append("text_delta")

    if payload_type == "normalized_file":
        patterns.append("file_delta")

    event = payload.get("event")

    if isinstance(event, Mapping):
        patterns.append("mapping_event")

        if len(event) == 1:
            patterns.append("singleton_update")

        if any(isinstance(value, list) for value in event.values()):
            patterns.append("contains_list")

        if any(isinstance(value, Mapping) for value in event.values()):
            patterns.append("nested_mapping")

    text = extract_text(payload)

    if re.search(r"\([^)]*\)\s*(?:\^|\*\*)\s*2", text):
        patterns.append("squared_relation")

    if "²" in text:
        patterns.append("squared_relation")

    if re.search(r"\bg\s*\(\s*x\s*\+\s*1\s*\)", text):
        patterns.append("growth_recurrence")

    if re.search(r"\bg\s*\(\s*x\s*\)", text):
        patterns.append("growth_state")

    if any(
        term in text
        for term in (
            "sha-256",
            "sha256",
            "hash chain",
            "merkle",
            "tamper-evident",
        )
    ):
        patterns.append("integrity_structure")

    if any(
        term in text
        for term in (
            "anchor",
            "continuity",
            "persistence",
            "stability",
            "fixed point",
        )
    ):
        patterns.append("continuity_structure")

    if any(
        term in text
        for term in (
            "compression",
            "simplification",
            "remove redundancies",
            "redundancy",
        )
    ):
        patterns.append("compression_structure")

    if any(
        term in text
        for term in (
            "invariant",
            "preserve",
            "preservation",
            "verified",
        )
    ):
        patterns.append("invariant_structure")

    return sorted(set(patterns))


def route_spines(
    payload: Mapping[str, Any],
    *,
    minimum_score: int = 1,
) -> list[Dict[str, Any]]:
    """Return every matching spine candidate with evidence."""
    text = extract_text(payload)
    candidates: list[Dict[str, Any]] = []

    for spine, keywords in SPINE_ROUTES.items():
        matched = sorted(
            keyword
            for keyword in keywords
            if phrase_present(text, keyword)
        )

        score = len(matched)

        if score >= minimum_score:
            candidates.append(
                {
                    "spine": spine,
                    "score": score,
                    "evidence": matched,
                }
            )

    candidates.sort(
        key=lambda candidate: (
            -candidate["score"],
            candidate["spine"],
        )
    )

    if not candidates:
        return [
            {
                "spine": "general",
                "score": 0,
                "confidence": 0.0,
                "evidence": [],
            }
        ]

    total_score = sum(
        candidate["score"]
        for candidate in candidates
    )

    highest_score = max(
        candidate["score"]
        for candidate in candidates
    )

    for candidate in candidates:
        candidate["confidence"] = round(
            candidate["score"] / highest_score,
            4,
        )
        candidate["weight"] = round(
            candidate["score"] / total_score,
            4,
        )

    return candidates


class HoloGeneralizer:
    """Pluggable and read-only generalization pipeline."""

    def __init__(self) -> None:
        self.hooks: Dict[
            str,
            Callable[[Mapping[str, Any]], Any],
        ] = {}

        self.register_hook("patterns", detect_patterns)
        self.register_hook("routes", route_spines)

    def register_hook(
        self,
        name: str,
        function: Callable[[Mapping[str, Any]], Any],
    ) -> None:
        """Register or replace a generalization hook."""
        if not name.strip():
            raise ValueError("Hook name cannot be empty.")

        if not callable(function):
            raise TypeError("Hook must be callable.")

        self.hooks[name] = function

    def normalize(
        self,
        raw_delta: Any,
        *,
        source: str = "generalizer",
        thread_id: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Normalize text, mappings, or arbitrary values."""
        normalized_tags = list(tags or [])

        if isinstance(raw_delta, str):
            return normalize_text(
                raw_delta,
                source=source,
                thread_id=thread_id,
                tags=normalized_tags,
            )

        if isinstance(raw_delta, Mapping):
            return normalize_event(
                dict(raw_delta),
                source=source,
                thread_id=thread_id,
                tags=normalized_tags,
            )

        return normalize_event(
            {
                "value": raw_delta,
                "python_type": type(raw_delta).__name__,
            },
            source=source,
            thread_id=thread_id,
            tags=normalized_tags,
        )

    def process(
        self,
        raw_delta: Any,
        *,
        source: str = "generalizer",
        thread_id: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Normalize and generalize a delta without persistence."""
        normalized = self.normalize(
            raw_delta,
            source=source,
            thread_id=thread_id,
            tags=tags,
        )

        hook_results: Dict[str, Any] = {}

        for name, function in self.hooks.items():
            hook_results[name] = function(normalized)

        routes = hook_results.get("routes", [])
        patterns = hook_results.get("patterns", [])

        packet = {
            "type": GENERALIZER_TYPE,
            "version": GENERALIZER_VERSION,
            "source": source,
            "thread_id": thread_id,
            "normalized": normalized,
            "routes": routes,
            "primary_route": routes[0] if routes else None,
            "patterns": patterns,
            "hook_results": hook_results,
            "normalized_hash": full_hash(normalized),
        }

        packet["generalization_hash"] = stable_hash(packet)

        return packet

    def batch_process(
        self,
        deltas: Iterable[Any],
        *,
        source: str = "generalizer.batch",
        thread_id: str | None = None,
        tags: Iterable[str] | None = None,
    ) -> list[Dict[str, Any]]:
        """Generalize several deltas independently."""
        return [
            self.process(
                delta,
                source=source,
                thread_id=thread_id,
                tags=tags,
            )
            for delta in deltas
        ]


def get_generalizer() -> HoloGeneralizer:
    """Create a generalization engine."""
    return HoloGeneralizer()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generalize a Holo/Sim delta without appending it."
    )
    parser.add_argument(
        "delta",
        help="Text delta to normalize and route",
    )
    parser.add_argument(
        "--source",
        default="generalizer.cli",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
    )

    args = parser.parse_args()

    result = get_generalizer().process(
        args.delta,
        source=args.source,
        thread_id=args.thread_id,
    )

    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()