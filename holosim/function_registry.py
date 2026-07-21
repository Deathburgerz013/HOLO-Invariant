from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence


class FunctionRegistryError(ValueError):
    """Raised when a functional-registry record is invalid."""


VALID_COMPOSITIONS = {"STACK", "ADJACENT", "NESTED", "CONNECTED"}


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, RecursionError) as exc:
        raise FunctionRegistryError(
            "registry values must be finite, acyclic, JSON-compatible data"
        ) from exc


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _require_id(value: Mapping[str, Any], *, label: str) -> str:
    item_id = value.get("id")
    if not isinstance(item_id, str) or not item_id.strip():
        raise FunctionRegistryError(f"{label} requires a non-empty string id")
    return item_id


def register_function(
    *,
    function_id: str,
    description: str,
    contract: Mapping[str, Any],
    evidence_reference: str,
) -> dict[str, Any]:
    """
    Register one observed function.

    This does not claim that the function is universal, foundational,
    invariant, or required. It records only an explicit functional contract
    tied to an evidence reference.
    """
    if not isinstance(function_id, str) or not function_id.strip():
        raise FunctionRegistryError("function_id must be a non-empty string")
    if not isinstance(description, str) or not description.strip():
        raise FunctionRegistryError("description must be a non-empty string")
    if not isinstance(evidence_reference, str) or not evidence_reference.strip():
        raise FunctionRegistryError(
            "evidence_reference must be a non-empty string"
        )
    if not isinstance(contract, Mapping):
        raise FunctionRegistryError("contract must be an object")

    record = {
        "type": "function_registry_function",
        "function_id": function_id,
        "description": description,
        "contract": deepcopy(dict(contract)),
        "evidence_reference": evidence_reference,
        "accepted": False,
        "write_authority": "NONE",
    }
    record["function_hash"] = _stable_hash(record)
    return record


def relate_implementation(
    *,
    function_record: Mapping[str, Any],
    implementation: Mapping[str, Any],
    reproduction_reference: str,
) -> dict[str, Any]:
    """
    Relate an implementation to a registered function.

    The relation is only a proposal until external reproduction evidence
    establishes that the implementation satisfies the function contract.
    """
    if function_record.get("type") != "function_registry_function":
        raise FunctionRegistryError("invalid function_record")

    implementation_id = _require_id(
        implementation,
        label="implementation",
    )

    if not isinstance(reproduction_reference, str) or not reproduction_reference.strip():
        raise FunctionRegistryError(
            "reproduction_reference must be a non-empty string"
        )

    relation = {
        "type": "function_registry_implementation_relation",
        "function_id": function_record["function_id"],
        "function_hash": function_record["function_hash"],
        "implementation_id": implementation_id,
        "implementation": deepcopy(dict(implementation)),
        "reproduction_reference": reproduction_reference,
        "status": "PROPOSED",
        "accepted": False,
        "write_authority": "NONE",
    }
    relation["relation_hash"] = _stable_hash(relation)
    return relation


def build_composition(
    *,
    composition_id: str,
    mode: str,
    members: Sequence[Mapping[str, Any]],
    evidence_reference: str,
) -> dict[str, Any]:
    """
    Describe how bounded functions or subsystems are composed.

    Geometry is explicit:
    STACK      = output/dependency composition
    ADJACENT   = side-by-side / parallel composition
    NESTED     = bounded containment
    CONNECTED  = network/path relation

    This records structure only. It does not prove that the composition works.
    """
    if not isinstance(composition_id, str) or not composition_id.strip():
        raise FunctionRegistryError(
            "composition_id must be a non-empty string"
        )

    if mode not in VALID_COMPOSITIONS:
        raise FunctionRegistryError(
            f"mode must be one of {sorted(VALID_COMPOSITIONS)}"
        )

    if not isinstance(evidence_reference, str) or not evidence_reference.strip():
        raise FunctionRegistryError(
            "evidence_reference must be a non-empty string"
        )

    normalized_members: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    for member in members:
        if not isinstance(member, Mapping):
            raise FunctionRegistryError("composition members must be objects")

        member_id = _require_id(member, label="composition member")
        if member_id in seen_ids:
            raise FunctionRegistryError(
                f"duplicate composition member id: {member_id}"
            )

        seen_ids.add(member_id)
        normalized_members.append(deepcopy(dict(member)))

    if not normalized_members:
        raise FunctionRegistryError(
            "composition requires at least one member"
        )

    record = {
        "type": "function_registry_composition",
        "composition_id": composition_id,
        "mode": mode,
        "members": normalized_members,
        "evidence_reference": evidence_reference,
        "status": "OBSERVED_STRUCTURE",
        "accepted": False,
        "write_authority": "NONE",
    }
    record["composition_hash"] = _stable_hash(record)
    return record


def evaluate_functional_merge(
    *,
    function_id: str,
    implementation_ids: Sequence[str],
    reproduction_status: str,
    reproduction_reference: str,
) -> dict[str, Any]:
    """
    Evaluate whether multiple implementations may share one functional node.

    Only a successful external reproduction result permits SHARED_FUNCTION.
    This does not declare the implementations identical or obsolete.
    """
    if not isinstance(function_id, str) or not function_id.strip():
        raise FunctionRegistryError("function_id must be a non-empty string")

    if reproduction_status not in {
        "REPRODUCED",
        "NOT_REPRODUCED",
        "UNVALIDATED",
    }:
        raise FunctionRegistryError(
            "reproduction_status must be REPRODUCED, "
            "NOT_REPRODUCED, or UNVALIDATED"
        )

    if not isinstance(reproduction_reference, str) or not reproduction_reference.strip():
        raise FunctionRegistryError(
            "reproduction_reference must be a non-empty string"
        )

    normalized_ids: list[str] = []
    seen: set[str] = set()

    for implementation_id in implementation_ids:
        if not isinstance(implementation_id, str) or not implementation_id.strip():
            raise FunctionRegistryError(
                "implementation_ids must contain non-empty strings"
            )
        if implementation_id in seen:
            raise FunctionRegistryError(
                f"duplicate implementation id: {implementation_id}"
            )
        seen.add(implementation_id)
        normalized_ids.append(implementation_id)

    if len(normalized_ids) < 2:
        raise FunctionRegistryError(
            "functional merge requires at least two implementations"
        )

    if reproduction_status == "REPRODUCED":
        merge_status = "SHARED_FUNCTION"
    elif reproduction_status == "NOT_REPRODUCED":
        merge_status = "PRESERVE_DISTINCTION"
    else:
        merge_status = "UNVALIDATED"

    result = {
        "type": "function_registry_merge_evaluation",
        "function_id": function_id,
        "implementation_ids": normalized_ids,
        "reproduction_status": reproduction_status,
        "reproduction_reference": reproduction_reference,
        "merge_status": merge_status,
        "implementations_declared_identical": False,
        "obsolete_implementations": [],
        "accepted": False,
        "write_authority": "NONE",
    }
    result["evaluation_hash"] = _stable_hash(result)
    return result