"""Bound exact contributor attribution without granting broader claims.

Attribution records who is declared to have contributed one exact contribution
in one declared role. It does not establish truth, general authorship,
ownership, currentness, acceptance, selection, write, execution, or promotion
authority.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Mapping


RECEIPT_TYPE = "bounded_contributor_attribution"
RECEIPT_VERSION = 1

RECEIPT_FIELDS = {
    "type",
    "version",
    "contributor_id",
    "role",
    "contribution",
    "contribution_hash",
    "attribution_claimed",
    "truth_claimed",
    "authorship_claimed",
    "ownership_claimed",
    "currentness_claimed",
    "accepted",
    "selection_authority",
    "write_authority",
    "execution_authority",
    "promotion_authority",
    "interpretation_notice",
    "attribution_hash",
}


class BoundedContributorAttributionError(ValueError):
    """Raised when contributor attribution is malformed or overclaims."""


def _hash(value: Any) -> str:
    try:
        encoded = json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise BoundedContributorAttributionError(
            "value must be canonical JSON"
        ) from exc
    return hashlib.sha256(encoded).hexdigest()


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise BoundedContributorAttributionError(
            f"{field} must be nonempty text"
        )
    return value


def _contribution(value: Any) -> dict[str, Any]:
    if type(value) is not dict or not value:
        raise BoundedContributorAttributionError(
            "contribution must be a nonempty plain dictionary"
        )

    checked = deepcopy(value)

    # Force canonical-JSON validation before anything can be attributed.
    _hash(checked)
    return checked


def build_bounded_contributor_attribution(
    *,
    contributor_id: str,
    role: str,
    contribution: Mapping[str, Any],
) -> dict[str, Any]:
    """Attribute one exact contribution without deriving broader authority."""

    contributor = _text(contributor_id, "contributor_id")
    declared_role = _text(role, "role")
    checked_contribution = _contribution(contribution)

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "contributor_id": contributor,
        "role": declared_role,
        "contribution": checked_contribution,
        "contribution_hash": _hash(checked_contribution),
        "attribution_claimed": True,
        "truth_claimed": False,
        "authorship_claimed": False,
        "ownership_claimed": False,
        "currentness_claimed": False,
        "accepted": False,
        "selection_authority": "NONE",
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "interpretation_notice": (
            "This receipt attributes only the exact declared contribution "
            "to the declared contributor in the declared role. Attribution "
            "does not establish truth, general authorship, ownership, "
            "currentness, acceptance, selection authority, write authority, "
            "execution authority, or promotion authority."
        ),
    }

    return {**body, "attribution_hash": _hash(body)}


def validate_bounded_contributor_attribution(
    receipt: Mapping[str, Any],
) -> None:
    """Verify exact attribution identity and its non-authority boundary."""

    if type(receipt) is not dict:
        raise BoundedContributorAttributionError(
            "receipt must be a plain dictionary"
        )

    if set(receipt) != RECEIPT_FIELDS:
        raise BoundedContributorAttributionError(
            "receipt fields do not match bounded attribution schema"
        )

    if (
        receipt.get("type") != RECEIPT_TYPE
        or receipt.get("version") != RECEIPT_VERSION
    ):
        raise BoundedContributorAttributionError(
            "receipt type or version is invalid"
        )

    try:
        rebuilt = build_bounded_contributor_attribution(
            contributor_id=receipt["contributor_id"],
            role=receipt["role"],
            contribution=receipt["contribution"],
        )
    except BoundedContributorAttributionError:
        raise
    except (KeyError, TypeError, ValueError) as exc:
        raise BoundedContributorAttributionError(
            "receipt cannot be reconstructed"
        ) from exc

    if receipt != rebuilt:
        raise BoundedContributorAttributionError(
            "receipt does not match its bounded attribution"
        )

    if receipt["attribution_claimed"] is not True:
        raise BoundedContributorAttributionError(
            "receipt must claim only bounded attribution"
        )

    forbidden_claims = (
        "truth_claimed",
        "authorship_claimed",
        "ownership_claimed",
        "currentness_claimed",
        "accepted",
    )
    if any(receipt[field] is not False for field in forbidden_claims):
        raise BoundedContributorAttributionError(
            "attribution cannot grant broader claims"
        )

    authority_fields = (
        "selection_authority",
        "write_authority",
        "execution_authority",
        "promotion_authority",
    )
    if any(receipt[field] != "NONE" for field in authority_fields):
        raise BoundedContributorAttributionError(
            "attribution cannot grant authority"
        )