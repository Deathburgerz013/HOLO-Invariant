"""Bounded, deterministic validation of propositional inference form.

The verifier exhaustively searches a small propositional state space.  It can
show that a conclusion follows conditionally from supplied formal premises,
or return one exact counterexample.  It does not establish that any atomic
premise is true in the environment and grants no operational authority.
"""

from __future__ import annotations

import itertools
import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import CanonicalValueError, stable_hash


INFERENCE_TYPE = "holo_bounded_propositional_inference"
INFERENCE_VERSION = 1
METHOD = "EXHAUSTIVE_TRUTH_TABLE"

STATUS_VALID = "VALID"
STATUS_INVALID = "INVALID"
STATUS_INCONSISTENT_PREMISES = "INCONSISTENT_PREMISES"

MAX_ATOMS = 10
MAX_EXPRESSION_DEPTH = 16
MAX_EXPRESSION_NODES = 256

ATOM_NAME = re.compile(r"[A-Za-z][A-Za-z0-9_.:-]{0,63}")
BINARY_OPERATORS = {"AND", "OR", "IMPLIES", "IFF"}

RECEIPT_FIELDS = {
    "type",
    "version",
    "inference_id",
    "method",
    "premises",
    "conclusion",
    "declared_scope",
    "atom_names",
    "assignment_count",
    "satisfying_assignment_count",
    "premises_satisfiable",
    "counterexample_search_complete",
    "counterexample",
    "status",
    "inference_valid",
    "conclusion_conditionally_supported",
    "premise_support_status",
    "truth_claimed",
    "accepted",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "interpretation_notice",
    "inference_hash",
}


class BoundedPropositionalInferenceError(ValueError):
    """A propositional expression or receipt violates the closed contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedPropositionalInferenceError(
            f"{field} must be nonempty plain text"
        )
    return value.strip()


def _scope(value: Any) -> dict[str, Any]:
    if type(value) is not dict or not value:
        raise BoundedPropositionalInferenceError(
            "declared_scope must be a nonempty plain object"
        )
    try:
        stable_hash(value)
    except CanonicalValueError as exc:
        raise BoundedPropositionalInferenceError(
            "declared_scope must contain strict canonical JSON values"
        ) from exc
    return {key: deepcopy(value[key]) for key in sorted(value)}


def _normalize_expression(
    value: Any,
    *,
    path: str,
    depth: int,
    node_count: list[int],
    atoms: set[str],
) -> dict[str, Any]:
    if depth > MAX_EXPRESSION_DEPTH:
        raise BoundedPropositionalInferenceError(
            f"{path} exceeds the expression depth limit"
        )
    node_count[0] += 1
    if node_count[0] > MAX_EXPRESSION_NODES:
        raise BoundedPropositionalInferenceError(
            "inference exceeds the expression node limit"
        )
    if type(value) is not dict:
        raise BoundedPropositionalInferenceError(f"{path} must be a plain object")

    operator = value.get("op")
    if operator == "ATOM":
        if set(value) != {"op", "name"}:
            raise BoundedPropositionalInferenceError(
                f"{path} ATOM fields do not match the versioned grammar"
            )
        name = _text(value["name"], f"{path}.name")
        if ATOM_NAME.fullmatch(name) is None:
            raise BoundedPropositionalInferenceError(
                f"{path}.name is not a valid atom identifier"
            )
        atoms.add(name)
        if len(atoms) > MAX_ATOMS:
            raise BoundedPropositionalInferenceError(
                f"inference exceeds the {MAX_ATOMS}-atom limit"
            )
        return {"op": "ATOM", "name": name}

    if operator == "NOT":
        if set(value) != {"op", "arg"}:
            raise BoundedPropositionalInferenceError(
                f"{path} NOT fields do not match the versioned grammar"
            )
        return {
            "op": "NOT",
            "arg": _normalize_expression(
                value["arg"],
                path=f"{path}.arg",
                depth=depth + 1,
                node_count=node_count,
                atoms=atoms,
            ),
        }

    if operator in BINARY_OPERATORS:
        if set(value) != {"op", "left", "right"}:
            raise BoundedPropositionalInferenceError(
                f"{path} {operator} fields do not match the versioned grammar"
            )
        return {
            "op": operator,
            "left": _normalize_expression(
                value["left"],
                path=f"{path}.left",
                depth=depth + 1,
                node_count=node_count,
                atoms=atoms,
            ),
            "right": _normalize_expression(
                value["right"],
                path=f"{path}.right",
                depth=depth + 1,
                node_count=node_count,
                atoms=atoms,
            ),
        }

    raise BoundedPropositionalInferenceError(
        f"{path}.op must be ATOM, NOT, or one of {sorted(BINARY_OPERATORS)}"
    )


def _evaluate(expression: Mapping[str, Any], assignment: Mapping[str, bool]) -> bool:
    operator = expression["op"]
    if operator == "ATOM":
        return assignment[expression["name"]]
    if operator == "NOT":
        return not _evaluate(expression["arg"], assignment)

    left = _evaluate(expression["left"], assignment)
    right = _evaluate(expression["right"], assignment)
    if operator == "AND":
        return left and right
    if operator == "OR":
        return left or right
    if operator == "IMPLIES":
        return (not left) or right
    if operator == "IFF":
        return left == right
    raise AssertionError(f"normalized operator is unsupported: {operator}")


def _normalize_inputs(
    premises: Sequence[Mapping[str, Any]],
    conclusion: Mapping[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], list[str]]:
    if type(premises) not in {list, tuple}:
        raise BoundedPropositionalInferenceError(
            "premises must be a list or tuple"
        )

    atoms: set[str] = set()
    node_count = [0]
    normalized_premises = [
        _normalize_expression(
            premise,
            path=f"premises[{index}]",
            depth=1,
            node_count=node_count,
            atoms=atoms,
        )
        for index, premise in enumerate(premises)
    ]
    normalized_conclusion = _normalize_expression(
        conclusion,
        path="conclusion",
        depth=1,
        node_count=node_count,
        atoms=atoms,
    )

    premise_hashes = [stable_hash(item) for item in normalized_premises]
    if len(premise_hashes) != len(set(premise_hashes)):
        raise BoundedPropositionalInferenceError("premises must not contain duplicates")
    normalized_premises = [
        item
        for _, item in sorted(
            zip(premise_hashes, normalized_premises), key=lambda pair: pair[0]
        )
    ]
    return normalized_premises, normalized_conclusion, sorted(atoms)


def build_bounded_propositional_inference(
    *,
    inference_id: str,
    premises: Sequence[Mapping[str, Any]],
    conclusion: Mapping[str, Any],
    declared_scope: Mapping[str, Any],
) -> dict[str, Any]:
    """Exhaustively validate one conditional propositional inference."""
    normalized_premises, normalized_conclusion, atom_names = _normalize_inputs(
        premises, conclusion
    )

    satisfying_count = 0
    counterexample: dict[str, Any] | None = None
    for values in itertools.product((False, True), repeat=len(atom_names)):
        assignment = dict(zip(atom_names, values))
        premise_values = [
            _evaluate(premise, assignment) for premise in normalized_premises
        ]
        premises_hold = all(premise_values)
        conclusion_value = _evaluate(normalized_conclusion, assignment)
        if premises_hold:
            satisfying_count += 1
            if not conclusion_value and counterexample is None:
                counterexample = {
                    "assignment": assignment,
                    "premise_values": premise_values,
                    "conclusion_value": conclusion_value,
                }

    premises_satisfiable = satisfying_count > 0
    if not premises_satisfiable:
        status = STATUS_INCONSISTENT_PREMISES
    elif counterexample is not None:
        status = STATUS_INVALID
    else:
        status = STATUS_VALID

    inference_valid = status == STATUS_VALID
    body: dict[str, Any] = {
        "type": INFERENCE_TYPE,
        "version": INFERENCE_VERSION,
        "inference_id": _text(inference_id, "inference_id"),
        "method": METHOD,
        "premises": normalized_premises,
        "conclusion": normalized_conclusion,
        "declared_scope": _scope(declared_scope),
        "atom_names": atom_names,
        "assignment_count": 2 ** len(atom_names),
        "satisfying_assignment_count": satisfying_count,
        "premises_satisfiable": premises_satisfiable,
        "counterexample_search_complete": True,
        "counterexample": counterexample,
        "status": status,
        "inference_valid": inference_valid,
        "conclusion_conditionally_supported": inference_valid,
        "premise_support_status": "NOT_VALIDATED",
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "interpretation_notice": (
            "This receipt exhaustively checks only whether the formal conclusion "
            "follows from the supplied formal premises in bounded propositional "
            "logic. It does not establish that any premise or conclusion is true, "
            "accept a claim, or grant operational authority."
        ),
    }
    return {**body, "inference_hash": stable_hash(body)}


def validate_bounded_propositional_inference(receipt: Mapping[str, Any]) -> bool:
    """Rebuild a receipt and require exact schema, result, and identity."""
    if type(receipt) is not dict or set(receipt) != RECEIPT_FIELDS:
        raise BoundedPropositionalInferenceError(
            "receipt fields do not match the versioned schema"
        )
    if (
        receipt.get("type") != INFERENCE_TYPE
        or receipt.get("version") != INFERENCE_VERSION
    ):
        raise BoundedPropositionalInferenceError("receipt type or version is invalid")
    if any(
        receipt.get(field) != expected
        for field, expected in {
            "premise_support_status": "NOT_VALIDATED",
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "promotion_authority": "NONE",
        }.items()
    ):
        raise BoundedPropositionalInferenceError(
            "receipt claims unsupported truth, acceptance, or authority"
        )
    rebuilt = build_bounded_propositional_inference(
        inference_id=receipt["inference_id"],
        premises=receipt["premises"],
        conclusion=receipt["conclusion"],
        declared_scope=receipt["declared_scope"],
    )
    if rebuilt != receipt:
        raise BoundedPropositionalInferenceError(
            "receipt does not match its deterministic inference"
        )
    return True
