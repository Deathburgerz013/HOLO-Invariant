"""Bounded comparison of observed functional transition traces.

This module compares evidence records; it does not execute supplied code or
infer semantics from labels.  Equivalence means only that every declared case
under one shared observer contract produced the same bounded observable motion.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import CanonicalValueError, stable_hash


TRACE_TYPE = "holo_functional_motion_trace"
TRACE_VERSION = 1
RECEIPT_TYPE = "holo_functional_motion_equivalence_receipt"
RECEIPT_VERSION = 1

EQUIVALENT_MOTION = "EQUIVALENT_MOTION"
DIVERGENT_MOTION = "DIVERGENT_MOTION"
INCOMPARABLE = "INCOMPARABLE"

CASE_FIELDS = {
    "case_id", "input", "constraints", "before_observable",
    "after_observable", "output_observable", "effects", "evidence_reference",
}
TRACE_FIELDS = {
    "type", "version", "implementation_id", "implementation_label",
    "function_id", "observer_contract_id", "cases", "provenance",
    "accepted", "truth_claimed", "write_authority", "execution_authority",
    "trace_hash",
}


class FunctionalMotionEquivalenceError(ValueError):
    """Trace or comparison receipt violates the bounded contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise FunctionalMotionEquivalenceError(
            f"{field} must be a nonempty plain string"
        )
    return value


def _closed(value: Any, field: str) -> Any:
    try:
        stable_hash(value)
    except CanonicalValueError as exc:
        raise FunctionalMotionEquivalenceError(
            f"{field} must contain strict canonical JSON values"
        ) from exc
    return deepcopy(value)


def _case(value: Mapping[str, Any], index: int) -> dict[str, Any]:
    if type(value) is not dict or set(value) != CASE_FIELDS:
        raise FunctionalMotionEquivalenceError(
            f"cases[{index}] fields do not match the versioned schema"
        )
    item = _closed(value, f"cases[{index}]")
    _text(item["case_id"], f"cases[{index}].case_id")
    _text(item["evidence_reference"], f"cases[{index}].evidence_reference")
    if type(item["constraints"]) is not dict:
        raise FunctionalMotionEquivalenceError(
            f"cases[{index}].constraints must be a plain dictionary"
        )
    if type(item["effects"]) is not list:
        raise FunctionalMotionEquivalenceError(
            f"cases[{index}].effects must be a list"
        )
    return item


def build_functional_motion_trace(
    *,
    implementation_id: str,
    implementation_label: str,
    function_id: str,
    observer_contract_id: str,
    cases: Sequence[Mapping[str, Any]],
    provenance: Mapping[str, Any],
) -> dict[str, Any]:
    """Build one deterministic, non-authoritative transition evidence trace."""
    values = list(cases) if type(cases) in {list, tuple} else None
    if not values:
        raise FunctionalMotionEquivalenceError("cases must be a nonempty list or tuple")
    normalized = [_case(value, index) for index, value in enumerate(values)]
    ids = [item["case_id"] for item in normalized]
    if len(ids) != len(set(ids)):
        raise FunctionalMotionEquivalenceError("case_id values must be unique")
    normalized.sort(key=lambda item: item["case_id"])
    if type(provenance) is not dict or not provenance:
        raise FunctionalMotionEquivalenceError("provenance must be a nonempty dictionary")
    body: dict[str, Any] = {
        "type": TRACE_TYPE,
        "version": TRACE_VERSION,
        "implementation_id": _text(implementation_id, "implementation_id"),
        "implementation_label": _text(implementation_label, "implementation_label"),
        "function_id": _text(function_id, "function_id"),
        "observer_contract_id": _text(observer_contract_id, "observer_contract_id"),
        "cases": normalized,
        "provenance": _closed(provenance, "provenance"),
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    return {**body, "trace_hash": stable_hash(body)}


def validate_functional_motion_trace(trace: Mapping[str, Any]) -> bool:
    """Fail closed when a transition trace is malformed or altered."""
    if type(trace) is not dict or set(trace) != TRACE_FIELDS:
        raise FunctionalMotionEquivalenceError(
            "trace fields do not match the versioned schema"
        )
    if trace["type"] != TRACE_TYPE or trace["version"] != TRACE_VERSION:
        raise FunctionalMotionEquivalenceError("trace type or version is invalid")
    for field in (
        "implementation_id", "implementation_label", "function_id",
        "observer_contract_id",
    ):
        _text(trace[field], field)
    cases = trace["cases"]
    if type(cases) is not list or not cases:
        raise FunctionalMotionEquivalenceError("trace cases must be a nonempty list")
    normalized = [_case(item, index) for index, item in enumerate(cases)]
    ids = [item["case_id"] for item in normalized]
    if ids != sorted(set(ids)):
        raise FunctionalMotionEquivalenceError(
            "trace cases must be sorted with unique case_id values"
        )
    if type(trace["provenance"]) is not dict or not trace["provenance"]:
        raise FunctionalMotionEquivalenceError("trace provenance is invalid")
    _closed(trace["provenance"], "provenance")
    if (trace["accepted"] is not False or trace["truth_claimed"] is not False or
            trace["write_authority"] != "NONE" or
            trace["execution_authority"] != "NONE"):
        raise FunctionalMotionEquivalenceError("trace grants forbidden authority")
    body = dict(trace)
    supplied = body.pop("trace_hash")
    if supplied != stable_hash(body):
        raise FunctionalMotionEquivalenceError("trace hash mismatch")
    return True


def compare_functional_motion(
    left: Mapping[str, Any],
    right: Mapping[str, Any],
) -> dict[str, Any]:
    """Compare bounded observable transitions without comparing labels as meaning."""
    validate_functional_motion_trace(left)
    validate_functional_motion_trace(right)
    left_copy, right_copy = deepcopy(dict(left)), deepcopy(dict(right))
    incompatibilities: list[str] = []
    if left_copy["function_id"] != right_copy["function_id"]:
        incompatibilities.append("function_id")
    if left_copy["observer_contract_id"] != right_copy["observer_contract_id"]:
        incompatibilities.append("observer_contract_id")
    left_cases = {item["case_id"]: item for item in left_copy["cases"]}
    right_cases = {item["case_id"]: item for item in right_copy["cases"]}
    if set(left_cases) != set(right_cases):
        incompatibilities.append("case_ids")

    divergent: list[dict[str, Any]] = []
    comparable_ids = sorted(set(left_cases) & set(right_cases))
    for case_id in comparable_ids:
        before, after = left_cases[case_id], right_cases[case_id]
        stimulus_fields = ("input", "constraints", "before_observable")
        mismatch = [field for field in stimulus_fields if before[field] != after[field]]
        if mismatch:
            incompatibilities.extend(f"{case_id}:{field}" for field in mismatch)
            continue
        observation_fields = (
            "after_observable", "output_observable", "effects",
        )
        changed = [field for field in observation_fields if before[field] != after[field]]
        if changed:
            divergent.append({
                "case_id": case_id,
                "changed_observables": changed,
                "left": {field: deepcopy(before[field]) for field in changed},
                "right": {field: deepcopy(after[field]) for field in changed},
            })

    incompatibilities = sorted(set(incompatibilities))
    if incompatibilities:
        classification = INCOMPARABLE
    elif divergent:
        classification = DIVERGENT_MOTION
    else:
        classification = EQUIVALENT_MOTION
    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "left_trace_hash": left_copy["trace_hash"],
        "right_trace_hash": right_copy["trace_hash"],
        "function_id": (
            left_copy["function_id"]
            if left_copy["function_id"] == right_copy["function_id"] else None
        ),
        "observer_contract_id": (
            left_copy["observer_contract_id"]
            if left_copy["observer_contract_id"] == right_copy["observer_contract_id"] else None
        ),
        "labels_changed": (
            left_copy["implementation_label"] != right_copy["implementation_label"]
        ),
        "case_ids_compared": comparable_ids,
        "incompatibilities": incompatibilities,
        "divergent_cases": divergent,
        "classification": classification,
        "equivalent_within_declared_cases": classification == EQUIVALENT_MOTION,
        "implementations_declared_identical": False,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Equivalence is bounded to the declared cases and shared observer "
            "contract. It does not prove equivalence for untested inputs, hidden "
            "state, timing, resource use, or external effects not recorded here."
        ),
    }
    return {**body, "receipt_hash": stable_hash(body)}


def validate_functional_motion_receipt(receipt: Mapping[str, Any]) -> bool:
    """Verify comparison identity and fail-closed classification relationships."""
    fields = {
        "type", "version", "left_trace_hash", "right_trace_hash", "function_id",
        "observer_contract_id", "labels_changed", "case_ids_compared",
        "incompatibilities", "divergent_cases", "classification",
        "equivalent_within_declared_cases", "implementations_declared_identical",
        "accepted", "truth_claimed", "write_authority", "execution_authority",
        "interpretation_notice", "receipt_hash",
    }
    if type(receipt) is not dict or set(receipt) != fields:
        raise FunctionalMotionEquivalenceError(
            "receipt fields do not match the versioned schema"
        )
    if receipt["type"] != RECEIPT_TYPE or receipt["version"] != RECEIPT_VERSION:
        raise FunctionalMotionEquivalenceError("receipt type or version is invalid")
    expected_class = (
        INCOMPARABLE if receipt["incompatibilities"] else
        DIVERGENT_MOTION if receipt["divergent_cases"] else EQUIVALENT_MOTION
    )
    if receipt["classification"] != expected_class:
        raise FunctionalMotionEquivalenceError("receipt classification is inconsistent")
    if receipt["equivalent_within_declared_cases"] is not (
        expected_class == EQUIVALENT_MOTION
    ):
        raise FunctionalMotionEquivalenceError("receipt equivalence claim is inconsistent")
    if (receipt["implementations_declared_identical"] is not False or
            receipt["accepted"] is not False or receipt["truth_claimed"] is not False or
            receipt["write_authority"] != "NONE" or
            receipt["execution_authority"] != "NONE"):
        raise FunctionalMotionEquivalenceError("receipt grants forbidden authority")
    body = dict(receipt)
    supplied = body.pop("receipt_hash")
    if supplied != stable_hash(body):
        raise FunctionalMotionEquivalenceError("receipt hash mismatch")
    return True
