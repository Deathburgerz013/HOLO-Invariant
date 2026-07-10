"""Holo/Sim fixed-point continuity engine.

Canonicalizes Canyon Brock Haney's stabilization lineage:

    B = (C + I + E)^2
    S = K + sum(F) + B
    G(x + 1) = stabilize(G(x), delta)

Where:
    C = Concept
    I = Integration
    E = Evolution
    K = Stability factor
    F = contextual influences
    G(x) = current verified state
    G(x + 1) = next candidate state

Version 1 treats the mathematics as an invariant contract, not as fake
precision derived from string length. Candidate transitions are normalized,
hashed, evaluated, and only appended through an explicit commit operation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, Mapping

try:
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
    )
    from holosim.core import HoloChain
    from holosim.hooks import normalize_event, normalize_text
    from holosim.provenance import get_provenance
    from holosim.replay import ReplayEngine
except ImportError:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from holosim.config import (
        ACTIVE_HASH,
        ANCHOR,
        DEFAULT_CHAIN_FILE,
        HOLOSIM_VERSION,
    )
    from holosim.core import HoloChain
    from holosim.hooks import normalize_event, normalize_text
    from holosim.provenance import get_provenance
    from holosim.replay import ReplayEngine


ENGINE_TYPE = "holo_sim_fixed_point"
ENGINE_VERSION = "1.0"

BASE_RELATION = "(C + I + E)^2"
STABILITY_RELATION = "S = K + ΣF + (C + I + E)^2"
GROWTH_RELATION = "G(x + 1) = stabilize(G(x), Δx)"

DEFAULT_STABILITY_FACTOR = 1.0

PROTECTED_FIELDS = {
    "anchor",
    "active_hash",
    "base_relation",
    "engine_type",
    "engine_version",
    "fixed_point_hash",
}


def utc_now() -> str:
    """Return an ISO-8601 UTC timestamp."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> str:
    """Serialize JSON-like data deterministically."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    )


def stable_hash(value: Any) -> str:
    """Return a deterministic SHA-256 hash."""
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def deep_merge(
    current: Mapping[str, Any],
    delta: Mapping[str, Any],
) -> Dict[str, Any]:
    """Merge nested dictionaries without silently replacing whole subtrees."""
    merged: Dict[str, Any] = deepcopy(dict(current))

    for key, value in delta.items():
        existing = merged.get(key)

        if isinstance(existing, Mapping) and isinstance(value, Mapping):
            merged[key] = deep_merge(existing, value)
        else:
            merged[key] = deepcopy(value)

    return merged


class HoloSim:
    """Fixed-point transition evaluator for Holo/Sim continuity."""

    def __init__(
        self,
        chain_path: str | Path = DEFAULT_CHAIN_FILE,
        *,
        thread_id: str | None = None,
        stability_factor: float = DEFAULT_STABILITY_FACTOR,
    ) -> None:
        if stability_factor <= 0:
            raise ValueError("stability_factor must be greater than zero")

        self.chain_path = Path(chain_path)
        self.thread_id = thread_id
        self.stability_factor = float(stability_factor)

        self.chain = HoloChain(str(self.chain_path))
        self.replay = ReplayEngine(self.chain_path)

        self.specification = self._build_specification()
        self.fixed_point_hash = stable_hash(self.specification)

    def _build_specification(self) -> Dict[str, Any]:
        """Return the canonical fixed-point specification."""
        return {
            "engine_type": ENGINE_TYPE,
            "engine_version": ENGINE_VERSION,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "holosim_version": HOLOSIM_VERSION,
            "base_relation": BASE_RELATION,
            "stability_relation": STABILITY_RELATION,
            "growth_relation": GROWTH_RELATION,
            "terms": {
                "C": "Concept",
                "I": "Integration",
                "E": "Evolution",
                "K": "Stability factor",
                "F": "Environmental and internal influences",
                "G(x)": "Current verified state",
                "G(x + 1)": "Next candidate state",
                "Δx": "Incoming delta",
            },
            "supporting_factors": (
                "clarity",
                "process",
                "simplification",
                "redundancy_removal",
                "persistence",
                "feedback_loop",
                "source_strength",
            ),
        }

    def identity(self) -> Dict[str, Any]:
        """Return engine identity and canonical fixed-point hash."""
        return {
            "engine": "HoloSim",
            "type": ENGINE_TYPE,
            "version": ENGINE_VERSION,
            "anchor": ANCHOR,
            "active_hash": ACTIVE_HASH,
            "chain_file": str(self.chain_path),
            "thread_id": self.thread_id,
            "fixed_point_hash": self.fixed_point_hash,
        }

    def current_state(self) -> Dict[str, Any]:
        """Return the latest verified chain entry as the current state."""
        latest = self.replay.latest()

        if not latest:
            return {
                "type": "holo_sim_genesis",
                "anchor": ANCHOR,
                "active_hash": ACTIVE_HASH,
                "base_relation": BASE_RELATION,
                "fixed_point_hash": self.fixed_point_hash,
            }

        return deepcopy(latest)

    def normalize_delta(
        self,
        delta: Any,
        *,
        source: str = "holo_sim",
        tags: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Normalize text or dictionary input into a consistent delta shape."""
        normalized_tags = list(tags or [])

        if isinstance(delta, str):
            return normalize_text(
                delta,
                source=source,
                thread_id=self.thread_id,
                tags=normalized_tags,
            )

        if isinstance(delta, Mapping):
            return normalize_event(
                dict(delta),
                source=source,
                thread_id=self.thread_id,
                tags=normalized_tags,
            )

        return normalize_event(
            {"value": delta, "python_type": type(delta).__name__},
            source=source,
            thread_id=self.thread_id,
            tags=normalized_tags,
        )

    def _protected_snapshot(self, state: Mapping[str, Any]) -> Dict[str, Any]:
        """Extract fixed-point fields that may not drift."""
        return {
            "anchor": state.get("anchor", ANCHOR),
            "active_hash": state.get("active_hash", ACTIVE_HASH),
            "base_relation": state.get("base_relation", BASE_RELATION),
            "engine_type": state.get("engine_type", ENGINE_TYPE),
            "engine_version": state.get("engine_version", ENGINE_VERSION),
            "fixed_point_hash": state.get(
                "fixed_point_hash",
                self.fixed_point_hash,
            ),
        }

    def _candidate_state(
        self,
        current: Mapping[str, Any],
        normalized_delta: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Construct a candidate next state using protected deep merge rules."""
        protected = self._protected_snapshot(current)

        delta_payload = normalized_delta.get("event")
        if not isinstance(delta_payload, Mapping):
            delta_payload = {
                "content": normalized_delta.get(
                    "content",
                    normalized_delta,
                )
            }

        safe_delta = dict(delta_payload)

        for field in PROTECTED_FIELDS:
            safe_delta.pop(field, None)

        merged = deep_merge(dict(current), safe_delta)
        merged.update(protected)

        merged["engine_type"] = ENGINE_TYPE
        merged["engine_version"] = ENGINE_VERSION
        merged["anchor"] = ANCHOR
        merged["active_hash"] = ACTIVE_HASH
        merged["base_relation"] = BASE_RELATION
        merged["fixed_point_hash"] = self.fixed_point_hash

        return merged

    def evaluate(
        self,
        delta: Any,
        *,
        source: str = "holo_sim",
        factors: Mapping[str, float] | None = None,
        tags: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Evaluate a candidate transition without modifying the chain."""
        current = self.current_state()
        normalized_delta = self.normalize_delta(
            delta,
            source=source,
            tags=tags,
        )
        candidate = self._candidate_state(current, normalized_delta)

        before_protected = self._protected_snapshot(current)
        after_protected = self._protected_snapshot(candidate)

        violations: list[str] = []

        for field in sorted(PROTECTED_FIELDS):
            before_value = before_protected.get(field)
            after_value = after_protected.get(field)

            if before_value != after_value:
                violations.append(
                    f"Protected field changed: {field}"
                )

        if stable_hash(self.specification) != self.fixed_point_hash:
            violations.append("Canonical fixed-point specification changed.")

        factor_values = dict(factors or {})
        invalid_factors = {
            name: value
            for name, value in factor_values.items()
            if not isinstance(value, (int, float))
        }

        if invalid_factors:
            violations.append(
                "All contextual factors must be numeric."
            )

        factor_sum = (
            sum(float(value) for value in factor_values.values())
            if not invalid_factors
            else 0.0
        )

        preserved = not violations

        provenance = get_provenance(
            thread_id=self.thread_id,
            source=source,
        ).packet()

        return {
            "type": "holo_sim_transition",
            "version": ENGINE_VERSION,
            "status": "accepted" if preserved else "rejected",
            "preserved": preserved,
            "relations": {
                "base": BASE_RELATION,
                "stability": STABILITY_RELATION,
                "growth": GROWTH_RELATION,
            },
            "stability": {
                "K": self.stability_factor,
                "factors": factor_values,
                "factor_sum": factor_sum,
                "symbolic_result": (
                    f"{self.stability_factor} + "
                    f"{factor_sum} + {BASE_RELATION}"
                ),
                "note": (
                    "Symbolic contract only. No empirical C, I, or E values "
                    "are invented."
                ),
            },
            "fixed_point_hash": self.fixed_point_hash,
            "before_hash": stable_hash(current),
            "delta_hash": stable_hash(normalized_delta),
            "after_hash": stable_hash(candidate),
            "violations": violations,
            "current_state": current,
            "normalized_delta": normalized_delta,
            "next_state": candidate if preserved else None,
            "provenance": provenance,
            "timestamp": utc_now(),
        }

    def commit(
        self,
        delta: Any,
        *,
        source: str = "holo_sim",
        factors: Mapping[str, float] | None = None,
        tags: Iterable[str] | None = None,
    ) -> Dict[str, Any]:
        """Evaluate and explicitly append an accepted transition."""
        decision = self.evaluate(
            delta,
            source=source,
            factors=factors,
            tags=tags,
        )

        if not decision["preserved"]:
            return decision

        append_payload = {
            "type": "holo_sim_commit",
            "engine": self.identity(),
            "relations": decision["relations"],
            "stability": decision["stability"],
            "fixed_point_hash": decision["fixed_point_hash"],
            "before_hash": decision["before_hash"],
            "delta_hash": decision["delta_hash"],
            "after_hash": decision["after_hash"],
            "next_state": decision["next_state"],
            "provenance": decision["provenance"],
            "timestamp": decision["timestamp"],
        }

        entry = self.chain.append(
            canonical_json(append_payload)
        )

        return {
            **decision,
            "status": "committed",
            "append": entry,
            "verify": self.verify_fixed_point(),
        }

    def verify_fixed_point(self) -> Dict[str, Any]:
        """Verify the canonical specification and chain integrity."""
        specification_hash = stable_hash(self.specification)

        try:
            entries = self.chain.load_and_verify()
            chain_valid = True
            chain_error = None
        except Exception as exc:
            entries = []
            chain_valid = False
            chain_error = str(exc)

        fixed_point_valid = (
            specification_hash == self.fixed_point_hash
        )

        return {
            "status": (
                "PASS"
                if fixed_point_valid and chain_valid
                else "FAIL"
            ),
            "fixed_point_valid": fixed_point_valid,
            "chain_valid": chain_valid,
            "entries": len(entries),
            "expected_hash": self.fixed_point_hash,
            "computed_hash": specification_hash,
            "chain_error": chain_error,
        }


def get_holo_sim(
    chain_path: str | Path = DEFAULT_CHAIN_FILE,
    *,
    thread_id: str | None = None,
    stability_factor: float = DEFAULT_STABILITY_FACTOR,
) -> HoloSim:
    """Create the Holo/Sim fixed-point engine."""
    return HoloSim(
        chain_path,
        thread_id=thread_id,
        stability_factor=stability_factor,
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the Holo/Sim fixed-point continuity engine."
    )
    parser.add_argument(
        "--file",
        "-f",
        default=str(DEFAULT_CHAIN_FILE),
        help="HoloChain JSONL path",
    )
    parser.add_argument(
        "--thread-id",
        default=None,
        help="Optional continuity thread identifier",
    )

    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    subparsers.add_parser(
        "identity",
        help="Show fixed-point identity",
    )
    subparsers.add_parser(
        "verify",
        help="Verify fixed point and chain",
    )

    evaluate_parser = subparsers.add_parser(
        "evaluate",
        help="Evaluate a text delta without appending",
    )
    evaluate_parser.add_argument("delta")

    commit_parser = subparsers.add_parser(
        "commit",
        help="Evaluate and append a text delta",
    )
    commit_parser.add_argument("delta")

    args = parser.parse_args()

    engine = get_holo_sim(
        args.file,
        thread_id=args.thread_id,
    )

    if args.command == "identity":
        result = engine.identity()
    elif args.command == "verify":
        result = engine.verify_fixed_point()
    elif args.command == "evaluate":
        result = engine.evaluate(args.delta)
    elif args.command == "commit":
        result = engine.commit(args.delta)
    else:
        raise SystemExit(
            f"Unknown Holo/Sim command: {args.command}"
        )

    print(json.dumps(result, indent=2, ensure_ascii=False))

    if args.command == "verify":
        raise SystemExit(
            0 if result["status"] == "PASS" else 1
        )


if __name__ == "__main__":
    main()