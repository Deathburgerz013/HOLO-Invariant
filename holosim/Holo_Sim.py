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
ENGINE_VERSION = "1.4"

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

    def _committed_assertions(self) -> list[Mapping[str, Any]]:
        """Return structured assertions preserved in verified commits."""
        assertions: list[Mapping[str, Any]] = []

        for item in self.replay.state():
            if not isinstance(item, Mapping):
                continue

            state = item.get("next_state", item)
            if not isinstance(state, Mapping):
                continue

            stored = state.get("assertions", [])
            if isinstance(stored, list):
                assertions.extend(
                    assertion
                    for assertion in stored
                    if isinstance(assertion, Mapping)
                )

        return assertions

    def _check_non_contradiction(
        self,
        normalized_delta: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Check structured claims under matching scope and evidence state.

        This deliberately does not infer meaning from free text. A structured
        assertion has four fields: claim, polarity, scope, and evidence_state.
        Only ``affirmed`` and ``negated`` are valid polarity values.
        """
        event = normalized_delta.get("event")
        incoming_raw = event.get("assertions", []) if isinstance(event, Mapping) else []

        uncertainty: list[Dict[str, Any]] = []
        incoming: list[Mapping[str, Any]] = []

        if not isinstance(incoming_raw, list):
            uncertainty.append(
                {
                    "kind": "invalid_assertions_container",
                    "message": "assertions must be a list",
                }
            )
        else:
            for index, assertion in enumerate(incoming_raw):
                if not isinstance(assertion, Mapping):
                    uncertainty.append(
                        {
                            "kind": "invalid_assertion",
                            "index": index,
                            "message": "assertion must be an object",
                        }
                    )
                    continue

                claim = assertion.get("claim")
                polarity = assertion.get("polarity")
                missing = [
                    field
                    for field in ("claim", "polarity", "scope", "evidence_state")
                    if field not in assertion
                ]

                if missing or not isinstance(claim, str) or not claim.strip():
                    uncertainty.append(
                        {
                            "kind": "invalid_assertion",
                            "index": index,
                            "message": "structured assertion fields are incomplete",
                            "missing_fields": missing,
                        }
                    )
                    continue

                if polarity not in {"affirmed", "negated"}:
                    uncertainty.append(
                        {
                            "kind": "invalid_polarity",
                            "index": index,
                            "message": "polarity must be affirmed or negated",
                        }
                    )
                    continue

                incoming.append(assertion)

        historical = self._committed_assertions()
        indexed: Dict[str, Dict[str, list[Dict[str, Any]]]] = {}

        def add_assertion(
            assertion: Mapping[str, Any],
            *,
            origin: str,
            index: int,
        ) -> None:
            claim = assertion.get("claim")
            polarity = assertion.get("polarity")
            if (
                not isinstance(claim, str)
                or not claim.strip()
                or polarity not in {"affirmed", "negated"}
                or "scope" not in assertion
                or "evidence_state" not in assertion
            ):
                return

            identity = {
                "claim": " ".join(claim.casefold().split()),
                "scope": assertion["scope"],
                "evidence_state": assertion["evidence_state"],
            }
            key = stable_hash(identity)
            indexed.setdefault(
                key,
                {"affirmed": [], "negated": []},
            )[polarity].append(
                {
                    "origin": origin,
                    "index": index,
                    "assertion_sha256": stable_hash(assertion),
                }
            )

        for index, assertion in enumerate(historical):
            add_assertion(assertion, origin="committed", index=index)
        for index, assertion in enumerate(incoming):
            add_assertion(assertion, origin="incoming", index=index)

        contradictions = []
        for key, polarities in sorted(indexed.items()):
            if polarities["affirmed"] and polarities["negated"]:
                contradictions.append(
                    {
                        "claim_scope_evidence_sha256": key,
                        "affirmed": polarities["affirmed"],
                        "negated": polarities["negated"],
                    }
                )

        return {
            "type": "structured_non_contradiction_check",
            "version": 1,
            "valid": not contradictions and not uncertainty,
            "checked_assertion_count": len(historical) + len(incoming),
            "historical_assertion_count": len(historical),
            "incoming_assertion_count": len(incoming),
            "contradiction_count": len(contradictions),
            "contradictions": contradictions,
            "uncertainty": uncertainty,
            "interpretation_notice": (
                "This check compares explicit structured assertions only; "
                "it does not infer contradiction from free text."
            ),
            "write_authority": "NONE",
        }

    def _committed_causal_events(self) -> Dict[str, Dict[str, Any]]:
        """Return structured causal events preserved in verified commits."""
        events: Dict[str, Dict[str, Any]] = {}

        for item in self.replay.state():
            if not isinstance(item, Mapping):
                continue

            state = item.get("next_state", item)
            if not isinstance(state, Mapping):
                continue

            causal = state.get("causal")
            if not isinstance(causal, Mapping):
                continue

            event_id = causal.get("event_id")
            if isinstance(event_id, str) and event_id.strip():
                events[event_id.strip()] = {
                    "event_id": event_id.strip(),
                    "predecessors": causal.get("predecessors", []),
                }

        return events

    def _check_causal_order(
        self,
        normalized_delta: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Validate explicit predecessor references against approved history."""
        event = normalized_delta.get("event")
        causal = event.get("causal") if isinstance(event, Mapping) else None
        historical = self._committed_causal_events()

        if causal is None:
            return {
                "type": "structured_causal_order_check",
                "version": 1,
                "applicable": False,
                "valid": True,
                "event_id": None,
                "predecessors": [],
                "historical_event_count": len(historical),
                "violations": [],
                "uncertainty": [],
                "interpretation_notice": (
                    "No causal ordering claim was supplied; no order was inferred."
                ),
                "write_authority": "NONE",
            }

        uncertainty: list[Dict[str, Any]] = []
        violations: list[Dict[str, Any]] = []
        event_id: str | None = None
        predecessors: list[str] = []

        if not isinstance(causal, Mapping):
            uncertainty.append(
                {
                    "kind": "invalid_causal_container",
                    "message": "causal must be an object",
                }
            )
        else:
            raw_event_id = causal.get("event_id")
            raw_predecessors = causal.get("predecessors")

            if not isinstance(raw_event_id, str) or not raw_event_id.strip():
                uncertainty.append(
                    {
                        "kind": "invalid_event_id",
                        "message": "causal.event_id must be a nonempty string",
                    }
                )
            else:
                event_id = raw_event_id.strip()

            if not isinstance(raw_predecessors, list):
                uncertainty.append(
                    {
                        "kind": "invalid_predecessors",
                        "message": "causal.predecessors must be a list",
                    }
                )
            elif any(
                not isinstance(value, str) or not value.strip()
                for value in raw_predecessors
            ):
                uncertainty.append(
                    {
                        "kind": "invalid_predecessor_id",
                        "message": "every predecessor must be a nonempty string",
                    }
                )
            else:
                predecessors = [value.strip() for value in raw_predecessors]

        if event_id is not None:
            if event_id in historical:
                violations.append(
                    {
                        "kind": "duplicate_event_id",
                        "event_id": event_id,
                    }
                )

            if event_id in predecessors:
                violations.append(
                    {
                        "kind": "self_predecessor",
                        "event_id": event_id,
                    }
                )

            duplicates = sorted(
                predecessor
                for predecessor in set(predecessors)
                if predecessors.count(predecessor) > 1
            )
            if duplicates:
                violations.append(
                    {
                        "kind": "duplicate_predecessor",
                        "predecessors": duplicates,
                    }
                )

            unknown = sorted(
                predecessor
                for predecessor in set(predecessors)
                if predecessor not in historical and predecessor != event_id
            )
            if unknown:
                violations.append(
                    {
                        "kind": "unknown_predecessor",
                        "predecessors": unknown,
                    }
                )

        return {
            "type": "structured_causal_order_check",
            "version": 1,
            "applicable": True,
            "valid": not violations and not uncertainty,
            "event_id": event_id,
            "predecessors": predecessors,
            "historical_event_count": len(historical),
            "violations": violations,
            "uncertainty": uncertainty,
            "interpretation_notice": (
                "Only explicit event identifiers and predecessor references are "
                "checked; no temporal or causal relation is inferred."
            ),
            "write_authority": "NONE",
        }

    def _check_source_binding(
        self,
        normalized_delta: Mapping[str, Any],
    ) -> Dict[str, Any]:
        """Validate explicit source identity and evidence hash bindings."""
        event = normalized_delta.get("event")
        structured_claim = isinstance(event, Mapping) and (
            "assertions" in event or "causal" in event
        )
        binding = event.get("source_binding") if isinstance(event, Mapping) else None

        if binding is None and not structured_claim:
            return {
                "type": "structured_source_binding_check",
                "version": 1,
                "applicable": False,
                "required": False,
                "valid": True,
                "source_id": None,
                "evidence_sha256": [],
                "binding_sha256": None,
                "violations": [],
                "uncertainty": [],
                "write_authority": "NONE",
            }

        uncertainty: list[Dict[str, Any]] = []
        violations: list[Dict[str, Any]] = []
        source_id: str | None = None
        evidence_hashes: list[str] = []

        if binding is None:
            uncertainty.append(
                {
                    "kind": "missing_source_binding",
                    "message": (
                        "structured assertions and causal claims require "
                        "source_binding"
                    ),
                }
            )
        elif not isinstance(binding, Mapping):
            uncertainty.append(
                {
                    "kind": "invalid_source_binding",
                    "message": "source_binding must be an object",
                }
            )
        else:
            raw_source_id = binding.get("source_id")
            raw_hashes = binding.get("evidence_sha256")

            if not isinstance(raw_source_id, str) or not raw_source_id.strip():
                uncertainty.append(
                    {
                        "kind": "invalid_source_id",
                        "message": "source_id must be a nonempty string",
                    }
                )
            else:
                source_id = raw_source_id.strip()

            if not isinstance(raw_hashes, list) or not raw_hashes:
                uncertainty.append(
                    {
                        "kind": "invalid_evidence_hashes",
                        "message": "evidence_sha256 must be a nonempty list",
                    }
                )
            elif any(
                not isinstance(value, str)
                or len(value) != 64
                or any(character not in "0123456789abcdef" for character in value)
                for value in raw_hashes
            ):
                uncertainty.append(
                    {
                        "kind": "invalid_evidence_sha256",
                        "message": (
                            "every evidence hash must be lowercase SHA-256 hex"
                        ),
                    }
                )
            else:
                evidence_hashes = list(raw_hashes)
                duplicates = sorted(
                    value
                    for value in set(evidence_hashes)
                    if evidence_hashes.count(value) > 1
                )
                if duplicates:
                    violations.append(
                        {
                            "kind": "duplicate_evidence_hash",
                            "evidence_sha256": duplicates,
                        }
                    )

        canonical_binding = (
            {
                "source_id": source_id,
                "evidence_sha256": evidence_hashes,
            }
            if source_id is not None and evidence_hashes
            else None
        )

        return {
            "type": "structured_source_binding_check",
            "version": 1,
            "applicable": binding is not None or structured_claim,
            "required": structured_claim,
            "valid": not violations and not uncertainty,
            "source_id": source_id,
            "evidence_sha256": evidence_hashes,
            "binding_sha256": (
                stable_hash(canonical_binding)
                if canonical_binding is not None
                else None
            ),
            "violations": violations,
            "uncertainty": uncertainty,
            "interpretation_notice": (
                "Hashes bind supplied evidence bytes by identity; they do not "
                "prove that the evidence is true or sufficient."
            ),
            "write_authority": "NONE",
        }

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

        non_contradiction = self._check_non_contradiction(normalized_delta)
        if non_contradiction["contradictions"]:
            violations.append(
                "Contradictory structured assertions share claim, scope, "
                "and evidence state."
            )

        causal_order = self._check_causal_order(normalized_delta)
        if causal_order["violations"]:
            violations.append(
                "Structured causal ordering contains invalid predecessor references."
            )

        source_binding = self._check_source_binding(normalized_delta)
        if source_binding["violations"]:
            violations.append(
                "Structured source binding contains invalid evidence references."
            )

        uncertainty = [
            *non_contradiction["uncertainty"],
            *causal_order["uncertainty"],
            *source_binding["uncertainty"],
        ]
        preserved = not violations and not uncertainty

        provenance = get_provenance(
            thread_id=self.thread_id,
            source=source,
        ).packet()

        verified_checks = []
        if before_protected == after_protected:
            verified_checks.append("protected_fields_preserved")
        if stable_hash(self.specification) == self.fixed_point_hash:
            verified_checks.append("fixed_point_specification_stable")
        if not invalid_factors:
            verified_checks.append("contextual_factors_numeric")
        if non_contradiction["valid"]:
            verified_checks.append("structured_non_contradiction")
        if causal_order["applicable"] and causal_order["valid"]:
            verified_checks.append("structured_causal_order")
        if source_binding["applicable"] and source_binding["valid"]:
            verified_checks.append("structured_source_binding")

        evidence = [
            {"kind": "state_before", "sha256": stable_hash(current)},
            {"kind": "proposed_delta", "sha256": stable_hash(normalized_delta)},
            {"kind": "candidate_state", "sha256": stable_hash(candidate)},
            {
                "kind": "provenance",
                "source": provenance.get("source"),
                "commit": provenance.get("git", {}).get("commit"),
            },
            {
                "kind": "non_contradiction_report",
                "sha256": stable_hash(non_contradiction),
            },
            {
                "kind": "causal_order_report",
                "sha256": stable_hash(causal_order),
            },
            {
                "kind": "source_binding_report",
                "sha256": stable_hash(source_binding),
            },
        ]

        return {
            "type": "holo_invariant_evaluation",
            "version": ENGINE_VERSION,
            "status": "PASS" if preserved else "FLAGGED",
            "preserved": preserved,
            "verified_checks": verified_checks,
            "violations": violations,
            "uncertainty": uncertainty,
            "evidence": evidence,
            "accepted": False,
            "write_authority": "NONE",
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
            "current_state": current,
            "normalized_delta": normalized_delta,
            "next_state": candidate if preserved else None,
            "non_contradiction": non_contradiction,
            "causal_order": causal_order,
            "source_binding": source_binding,
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
        reviewer: str | None = None,
        approval_reference: str | None = None,
    ) -> Dict[str, Any]:
        """Append only after explicit external acceptance is supplied.

        Evaluation never accepts its own result. Mutation requires both a
        reviewer identity and an external approval reference.
        """
        decision = self.evaluate(
            delta,
            source=source,
            factors=factors,
            tags=tags,
        )

        if not decision["preserved"]:
            return {
                **decision,
                "commit_performed": False,
                "mutation": None,
            }

        reviewer_value = reviewer.strip() if isinstance(reviewer, str) else ""
        approval_value = (
            approval_reference.strip()
            if isinstance(approval_reference, str)
            else ""
        )

        if not reviewer_value or not approval_value:
            return {
                **decision,
                "status": "BLOCKED",
                "commit_performed": False,
                "mutation": None,
                "authority": {
                    "accepted": False,
                    "source": "external_human_required",
                    "reviewer": reviewer_value or None,
                    "approval_reference": approval_value or None,
                },
                "violations": [
                    *decision["violations"],
                    (
                        "Commit requires an external reviewer and "
                        "approval reference."
                    ),
                ],
            }

        authority = {
            "accepted": True,
            "source": "external_human",
            "reviewer": reviewer_value,
            "approval_reference": approval_value,
        }

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
            "source_binding": decision["source_binding"],
            "timestamp": decision["timestamp"],
            "authority": authority,
        }

        entry = self.chain.append(
            canonical_json(append_payload)
        )

        return {
            **decision,
            "status": "COMMITTED",
            "commit_performed": True,
            "mutation": {
                "append": entry,
                "verify": self.verify_fixed_point(),
            },
            "authority": authority,
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
        help="Append only with explicit external acceptance",
    )
    commit_parser.add_argument("delta")
    commit_parser.add_argument("--reviewer", required=True)
    commit_parser.add_argument("--approval-reference", required=True)

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
        result = engine.commit(
            args.delta,
            reviewer=args.reviewer,
            approval_reference=args.approval_reference,
        )
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
