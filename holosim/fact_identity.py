from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from holosim.canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "verified_fact_identity_receipt"
RECEIPT_VERSION = 1
MAX_ITEMS = 10_000

_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,255}")
_MEMBER_FIELDS = {"analysis_id", "finding_id"}
_RECEIPT_FIELDS = {
    "type",
    "version",
    "fact_id",
    "members",
    "accepted",
    "write_authority",
    "interpretation_notice",
    "receipt_hash",
}


class VerifiedFactIdentityError(ValueError):
    """Raised when a fact-identity receipt violates its bounded contract."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise VerifiedFactIdentityError(str(exc)) from exc


def _identifier(value: Any, label: str) -> str:
    if type(value) is not str or _ID.fullmatch(value) is None:
        raise VerifiedFactIdentityError(f"{label} is invalid")
    return value


def _sequence(value: Any, label: str) -> list[Any]:
    if isinstance(value, (str, bytes, bytearray)) or not isinstance(value, Sequence):
        raise VerifiedFactIdentityError(f"{label} must be a sequence")
    if len(value) > MAX_ITEMS:
        raise VerifiedFactIdentityError(f"{label} exceeds item limit")
    return list(value)


def _normalize_members(values: Any) -> list[dict[str, str]]:
    members: list[dict[str, str]] = []
    seen: set[tuple[str, str]] = set()

    for raw in _sequence(values, "members"):
        if type(raw) is not dict or set(raw) != _MEMBER_FIELDS:
            raise VerifiedFactIdentityError("fact identity member fields mismatch")

        analysis_id = _identifier(raw["analysis_id"], "analysis_id")
        finding_id = _identifier(raw["finding_id"], "finding_id")
        key = (analysis_id, finding_id)

        if key in seen:
            raise VerifiedFactIdentityError("fact identity member is duplicated")

        seen.add(key)
        members.append(
            {
                "analysis_id": analysis_id,
                "finding_id": finding_id,
            }
        )

    if not members:
        raise VerifiedFactIdentityError(
            "fact identity receipt requires at least one member"
        )

    return sorted(
        members,
        key=lambda item: (item["analysis_id"], item["finding_id"]),
    )


def build_verified_fact_identity_receipt(
    *,
    fact_id: str,
    members: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    normalized_members = _normalize_members(members)

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "fact_id": _identifier(fact_id, "fact_id"),
        "members": deepcopy(normalized_members),
        "accepted": False,
        "write_authority": "NONE",
        "interpretation_notice": (
            "This receipt records an explicit fact-identity relation between "
            "declared analysis findings. It does not infer identity from wording, "
            "prove the underlying fact true, admit state, or grant write authority."
        ),
    }

    return {
        **body,
        "receipt_hash": _hash(body),
    }


def verify_fact_identity_receipt(receipt: Mapping[str, Any]) -> bool:
    if type(receipt) is not dict or set(receipt) != _RECEIPT_FIELDS:
        raise VerifiedFactIdentityError("receipt fields mismatch")

    if (
        receipt["type"] != RECEIPT_TYPE
        or receipt["version"] != RECEIPT_VERSION
    ):
        raise VerifiedFactIdentityError("receipt schema mismatch")

    supplied_hash = receipt["receipt_hash"]
    if (
        type(supplied_hash) is not str
        or re.fullmatch(r"[0-9a-f]{64}", supplied_hash) is None
    ):
        raise VerifiedFactIdentityError("receipt_hash is invalid")

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }

    if _hash(body) != supplied_hash:
        raise VerifiedFactIdentityError("receipt hash mismatch")

    expected = build_verified_fact_identity_receipt(
        fact_id=receipt["fact_id"],
        members=receipt["members"],
    )

    if expected != receipt:
        raise VerifiedFactIdentityError("receipt is internally inconsistent")

    return True
