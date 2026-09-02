"""Separate bounded evidentiary support from authority to produce effects.

A valid proof can support one declared conclusion under one declared method,
scope, and set of assumptions.  It cannot authorize its own use as permission,
nor can it grant write, execution, promotion, or trust-root authority.  A
separate authorization reference is identified only for referral to the
appropriate authority gate; this module never validates that authorization.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import CanonicalValueError, stable_hash


PROOF_TYPE = "holo_bounded_proof"
ASSESSMENT_TYPE = "holo_proof_authority_assessment"
VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")

NO_EFFECT = "NONE"
EFFECT_AUTHORITIES = {"WRITE", "EXECUTE", "PROMOTE", "ALTER_TRUST_ROOT"}

PROOF_FIELDS = {
    "type", "version", "proof_id", "claim_id", "claim", "assumptions",
    "method", "scope", "evidence_bindings", "conclusion", "limitations",
    "truth_claimed", "accepted", "write_authority", "execution_authority",
    "promotion_authority", "trust_root_authority", "interpretation_notice",
    "proof_hash",
}
EVIDENCE_FIELDS = {"evidence_id", "evidence_sha256"}


class ProofAuthorityBoundaryError(ValueError):
    """A proof or requested use violates the closed boundary contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise ProofAuthorityBoundaryError(f"{field} must be a nonempty plain string")
    return value


def _closed(value: Any, field: str) -> Any:
    try:
        stable_hash(value)
    except CanonicalValueError as exc:
        raise ProofAuthorityBoundaryError(
            f"{field} must contain strict canonical JSON values"
        ) from exc
    return deepcopy(value)


def _strings(values: Sequence[str], field: str, *, required: bool) -> list[str]:
    if type(values) not in {list, tuple}:
        raise ProofAuthorityBoundaryError(f"{field} must be a list or tuple")
    result = list(values)
    if required and not result:
        raise ProofAuthorityBoundaryError(f"{field} must not be empty")
    if any(type(item) is not str or not item.strip() for item in result):
        raise ProofAuthorityBoundaryError(f"{field} must contain nonempty strings")
    if len(result) != len(set(result)):
        raise ProofAuthorityBoundaryError(f"{field} must not contain duplicates")
    return sorted(result)


def _evidence(values: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
    if type(values) not in {list, tuple} or not values:
        raise ProofAuthorityBoundaryError("evidence_bindings must not be empty")
    result: list[dict[str, str]] = []
    ids: set[str] = set()
    for index, value in enumerate(values):
        if type(value) is not dict or set(value) != EVIDENCE_FIELDS:
            raise ProofAuthorityBoundaryError(
                f"evidence_bindings[{index}] fields do not match the schema"
            )
        item = deepcopy(value)
        identity = _text(item["evidence_id"], f"evidence_bindings[{index}].evidence_id")
        digest = _text(
            item["evidence_sha256"],
            f"evidence_bindings[{index}].evidence_sha256",
        )
        if SHA256.fullmatch(digest) is None:
            raise ProofAuthorityBoundaryError("evidence_sha256 must be lowercase SHA-256")
        if identity in ids:
            raise ProofAuthorityBoundaryError(f"duplicate evidence_id: {identity}")
        ids.add(identity)
        result.append(item)
    return sorted(result, key=lambda item: item["evidence_id"])


def build_bounded_proof(
    *,
    proof_id: str,
    claim_id: str,
    claim: str,
    assumptions: Sequence[str],
    method: Mapping[str, Any],
    scope: Mapping[str, Any],
    evidence_bindings: Sequence[Mapping[str, Any]],
    conclusion: str,
    limitations: Sequence[str],
) -> dict[str, Any]:
    """Build an immutable proof that carries no operational authority."""
    if type(method) is not dict or not method:
        raise ProofAuthorityBoundaryError("method must be a nonempty dictionary")
    if type(scope) is not dict or not scope:
        raise ProofAuthorityBoundaryError("scope must be a nonempty dictionary")
    body = {
        "type": PROOF_TYPE,
        "version": VERSION,
        "proof_id": _text(proof_id, "proof_id"),
        "claim_id": _text(claim_id, "claim_id"),
        "claim": _text(claim, "claim"),
        "assumptions": _strings(assumptions, "assumptions", required=True),
        "method": _closed(method, "method"),
        "scope": _closed(scope, "scope"),
        "evidence_bindings": _evidence(evidence_bindings),
        "conclusion": _text(conclusion, "conclusion"),
        "limitations": _strings(limitations, "limitations", required=False),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "trust_root_authority": "NONE",
        "interpretation_notice": (
            "This proof supports only its bounded conclusion under its declared "
            "assumptions, method, evidence, and scope. It grants no authority."
        ),
    }
    return {**body, "proof_hash": stable_hash(body)}


def validate_bounded_proof(proof: Mapping[str, Any]) -> bool:
    """Rebuild a proof and require its exact schema, identity, and non-authority."""
    if type(proof) is not dict or set(proof) != PROOF_FIELDS:
        raise ProofAuthorityBoundaryError("proof fields do not match the versioned schema")
    if proof.get("type") != PROOF_TYPE or proof.get("version") != VERSION:
        raise ProofAuthorityBoundaryError("proof type or version is invalid")
    if any(
        proof.get(field) != expected
        for field, expected in {
            "truth_claimed": False,
            "accepted": False,
            "write_authority": "NONE",
            "execution_authority": "NONE",
            "promotion_authority": "NONE",
            "trust_root_authority": "NONE",
        }.items()
    ):
        raise ProofAuthorityBoundaryError("proof cannot grant authority or acceptance")
    try:
        rebuilt = build_bounded_proof(
            proof_id=proof["proof_id"],
            claim_id=proof["claim_id"],
            claim=proof["claim"],
            assumptions=proof["assumptions"],
            method=proof["method"],
            scope=proof["scope"],
            evidence_bindings=proof["evidence_bindings"],
            conclusion=proof["conclusion"],
            limitations=proof["limitations"],
        )
    except (KeyError, TypeError) as exc:
        raise ProofAuthorityBoundaryError("proof is malformed") from exc
    if rebuilt != proof:
        raise ProofAuthorityBoundaryError("proof does not match its bounded identity")
    return True


def assess_proof_use(
    *,
    proof: Mapping[str, Any],
    requested_claim_id: str,
    requested_scope: Mapping[str, Any],
    requested_authority: str = NO_EFFECT,
    authorization_reference: str | None = None,
) -> dict[str, Any]:
    """Classify proof use without validating or granting operational authority."""
    validate_bounded_proof(proof)
    claim_id = _text(requested_claim_id, "requested_claim_id")
    if type(requested_scope) is not dict or not requested_scope:
        raise ProofAuthorityBoundaryError("requested_scope must be a nonempty dictionary")
    scope = _closed(requested_scope, "requested_scope")
    if requested_authority not in {NO_EFFECT, *EFFECT_AUTHORITIES}:
        raise ProofAuthorityBoundaryError("requested_authority is invalid")
    if authorization_reference is not None:
        authorization_reference = _text(
            authorization_reference, "authorization_reference"
        )

    claim_matches = claim_id == proof["claim_id"]
    scope_matches = scope == proof["scope"]
    substitution_attempted = authorization_reference == proof["proof_hash"]

    if requested_authority == NO_EFFECT:
        if claim_matches and scope_matches:
            decision = "BOUNDED_CONCLUSION_SUPPORTED"
            reason = "proof identity, claim, and scope match the requested conclusion"
        else:
            decision = "OUTSIDE_PROOF_BOUNDARY"
            reason = "requested claim or scope is outside the proof boundary"
    elif substitution_attempted:
        decision = "REJECTED_PROOF_AS_AUTHORITY"
        reason = "a proof hash cannot authorize use of the proof"
    elif authorization_reference is None:
        decision = "SEPARATE_AUTHORITY_REQUIRED"
        reason = "operational effects require an independent authorization"
    else:
        decision = "REFER_TO_AUTHORITY_GATE"
        reason = "the separate reference must be verified by an authority gate"

    body = {
        "type": ASSESSMENT_TYPE,
        "version": VERSION,
        "proof_hash": proof["proof_hash"],
        "requested_claim_id": claim_id,
        "requested_scope": scope,
        "requested_authority": requested_authority,
        "authorization_reference": authorization_reference,
        "claim_matches": claim_matches,
        "scope_matches": scope_matches,
        "proof_substitution_attempted": substitution_attempted,
        "decision": decision,
        "reason": reason,
        "conclusion_supported": (
            requested_authority == NO_EFFECT and claim_matches and scope_matches
        ),
        "effect_permitted": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "promotion_authority": "NONE",
        "trust_root_authority": "NONE",
    }
    return {**body, "assessment_hash": stable_hash(body)}
