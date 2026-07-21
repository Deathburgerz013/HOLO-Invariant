from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping, Sequence


CHECK_IDENTITY_TYPE = "check_identity"
CHECK_IDENTITY_VERSION = 1


class CheckIdentityError(ValueError):
    """Raised when a check-identity record is invalid."""


def _canonical_json(value: Any) -> str:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
    except (TypeError, ValueError, OverflowError, RecursionError) as exc:
        raise CheckIdentityError(
            "check identity values must be finite, acyclic, JSON-compatible data"
        ) from exc


def _stable_hash(value: Any) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CheckIdentityError(f"{field} must be a non-empty string")
    return value


def _unique_texts(values: Sequence[str], field: str) -> list[str]:
    if isinstance(values, (str, bytes)) or not isinstance(values, Sequence):
        raise CheckIdentityError(f"{field} must be a sequence of strings")

    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = _required_text(value, field)
        if item in seen:
            raise CheckIdentityError(f"duplicate {field}: {item}")
        seen.add(item)
        normalized.append(item)
    return normalized


def build_check_identity(
    *,
    check_id: str,
    check_type: str,
    subject: Mapping[str, Any],
    reference_ids: Sequence[str],
    scope: Mapping[str, Any],
    evidence_references: Sequence[str],
    rule_references: Sequence[str],
    input_state_hash: str,
) -> dict[str, Any]:
    """
    Build one deterministic identity envelope for a check.

    The envelope identifies what is being checked, against which references,
    under what scope, evidence, and rules, and at which exact input state.
    It does not perform the check, judge truth, grant acceptance, or mutate state.
    """
    normalized_check_id = _required_text(check_id, "check_id")
    normalized_check_type = _required_text(check_type, "check_type")
    normalized_input_state_hash = _required_text(
        input_state_hash,
        "input_state_hash",
    )

    if not isinstance(subject, Mapping) or not subject:
        raise CheckIdentityError("subject must be a non-empty object")
    if not isinstance(scope, Mapping) or not scope:
        raise CheckIdentityError("scope must be a non-empty object")

    references = _unique_texts(reference_ids, "reference_id")
    evidence = _unique_texts(evidence_references, "evidence_reference")
    rules = _unique_texts(rule_references, "rule_reference")

    body = {
        "type": CHECK_IDENTITY_TYPE,
        "version": CHECK_IDENTITY_VERSION,
        "check_id": normalized_check_id,
        "check_type": normalized_check_type,
        "subject": deepcopy(dict(subject)),
        "reference_ids": references,
        "scope": deepcopy(dict(scope)),
        "evidence_references": evidence,
        "rule_references": rules,
        "input_state_hash": normalized_input_state_hash,
        "result_bound": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "check_identity_hash": _stable_hash(body)}


def bind_check_result(
    *,
    check_identity: Mapping[str, Any],
    result: Mapping[str, Any],
    output_state_hash: str,
    justifier_reference: str | None = None,
) -> dict[str, Any]:
    """
    Bind a supplied result to one exact check identity.

    This records provenance of the result only. It does not validate whether the
    result is correct, justified, accepted, or authorized.
    """
    if not isinstance(check_identity, Mapping):
        raise CheckIdentityError("check_identity must be an object")
    if check_identity.get("type") != CHECK_IDENTITY_TYPE:
        raise CheckIdentityError("invalid check_identity type")

    identity_hash = check_identity.get("check_identity_hash")
    if not isinstance(identity_hash, str) or not identity_hash:
        raise CheckIdentityError("check_identity requires check_identity_hash")

    identity_body = {
        key: deepcopy(value)
        for key, value in check_identity.items()
        if key != "check_identity_hash"
    }
    if _stable_hash(identity_body) != identity_hash:
        raise CheckIdentityError("check_identity hash does not match content")

    if not isinstance(result, Mapping) or not result:
        raise CheckIdentityError("result must be a non-empty object")

    normalized_output_state_hash = _required_text(
        output_state_hash,
        "output_state_hash",
    )
    if justifier_reference is not None:
        normalized_justifier = _required_text(
            justifier_reference,
            "justifier_reference",
        )
    else:
        normalized_justifier = None

    body = {
        "type": "check_result_binding",
        "version": 1,
        "check_id": check_identity["check_id"],
        "check_identity_hash": identity_hash,
        "input_state_hash": check_identity["input_state_hash"],
        "result": deepcopy(dict(result)),
        "result_hash": _stable_hash(result),
        "output_state_hash": normalized_output_state_hash,
        "justifier_reference": normalized_justifier,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "binding_hash": _stable_hash(body)}
