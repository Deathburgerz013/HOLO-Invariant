"""Bind media claims to demonstrated perceptual capability.

Artifact integrity, signal measurement, content perception, and content
interpretation are distinct stages.  Success at one stage never implies a
later stage.  This module records which stage was actually demonstrated for
each modality and rejects claims that cross an unavailable capability boundary.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any, Mapping, Sequence

from .canonical import CanonicalValueError, stable_hash


RECEIPT_TYPE = "holo_perceptual_capability_receipt"
RECEIPT_VERSION = 1
SHA256 = re.compile(r"[0-9a-f]{64}")

STAGES = (
    "BYTES_VERIFIED",
    "SIGNAL_MEASURED",
    "CONTENT_PERCEIVED",
    "CONTENT_INTERPRETED",
)
STATUSES = {"VERIFIED", "UNSUPPORTED", "UNAVAILABLE", "NOT_TESTED"}
CAPABILITY_FIELDS = {"modality", "stage", "status", "evidence_reference"}
CLAIM_FIELDS = {"claim_id", "modality", "stage", "statement"}


class PerceptualCapabilityBoundaryError(ValueError):
    """Input or receipt violates the closed perceptual boundary contract."""


def _text(value: Any, field: str) -> str:
    if type(value) is not str or not value.strip():
        raise PerceptualCapabilityBoundaryError(
            f"{field} must be a nonempty plain string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _text(value, field)
    if SHA256.fullmatch(text) is None:
        raise PerceptualCapabilityBoundaryError(
            f"{field} must be 64 lowercase hexadecimal characters"
        )
    return text


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise PerceptualCapabilityBoundaryError(str(exc)) from exc


def _modalities(values: Sequence[str]) -> list[str]:
    if type(values) not in {list, tuple} or not values:
        raise PerceptualCapabilityBoundaryError(
            "declared_modalities must be a nonempty list or tuple"
        )
    result = [_text(value, "declared_modalities") for value in values]
    if len(result) != len(set(result)):
        raise PerceptualCapabilityBoundaryError(
            "declared_modalities must not contain duplicates"
        )
    return sorted(result)


def _capabilities(
    values: Sequence[Mapping[str, Any]],
    modalities: set[str],
) -> list[dict[str, str]]:
    if type(values) not in {list, tuple} or not values:
        raise PerceptualCapabilityBoundaryError(
            "capability_evidence must be a nonempty list or tuple"
        )
    result: list[dict[str, str]] = []
    identities: set[tuple[str, str]] = set()
    for index, value in enumerate(values):
        if type(value) is not dict or set(value) != CAPABILITY_FIELDS:
            raise PerceptualCapabilityBoundaryError(
                f"capability_evidence[{index}] fields do not match the schema"
            )
        item = deepcopy(value)
        modality = _text(item["modality"], f"capability_evidence[{index}].modality")
        if modality not in modalities:
            raise PerceptualCapabilityBoundaryError(
                f"capability modality is not declared: {modality}"
            )
        if item["stage"] not in STAGES:
            raise PerceptualCapabilityBoundaryError("capability stage is invalid")
        if item["status"] not in STATUSES:
            raise PerceptualCapabilityBoundaryError("capability status is invalid")
        _text(
            item["evidence_reference"],
            f"capability_evidence[{index}].evidence_reference",
        )
        identity = (modality, item["stage"])
        if identity in identities:
            raise PerceptualCapabilityBoundaryError(
                "capability modality and stage must be unique"
            )
        identities.add(identity)
        result.append(item)
    return sorted(result, key=lambda item: (item["modality"], STAGES.index(item["stage"])))


def _claims(
    values: Sequence[Mapping[str, Any]],
    modalities: set[str],
) -> list[dict[str, str]]:
    if type(values) not in {list, tuple} or not values:
        raise PerceptualCapabilityBoundaryError(
            "claims must be a nonempty list or tuple"
        )
    result: list[dict[str, str]] = []
    identities: set[str] = set()
    for index, value in enumerate(values):
        if type(value) is not dict or set(value) != CLAIM_FIELDS:
            raise PerceptualCapabilityBoundaryError(
                f"claims[{index}] fields do not match the schema"
            )
        item = deepcopy(value)
        claim_id = _text(item["claim_id"], f"claims[{index}].claim_id")
        modality = _text(item["modality"], f"claims[{index}].modality")
        if modality not in modalities:
            raise PerceptualCapabilityBoundaryError(
                f"claim modality is not declared: {modality}"
            )
        if item["stage"] not in STAGES:
            raise PerceptualCapabilityBoundaryError("claim stage is invalid")
        _text(item["statement"], f"claims[{index}].statement")
        if claim_id in identities:
            raise PerceptualCapabilityBoundaryError(f"duplicate claim_id: {claim_id}")
        identities.add(claim_id)
        result.append(item)
    return sorted(result, key=lambda item: item["claim_id"])


def _assessment(
    claim: Mapping[str, str],
    capability_index: Mapping[tuple[str, str], Mapping[str, str]],
) -> dict[str, Any]:
    stage_index = STAGES.index(claim["stage"])
    required = STAGES[: stage_index + 1]
    evidence_chain: list[dict[str, str | None]] = []
    blocking_status: str | None = None
    blocking_stage: str | None = None

    for stage in required:
        capability = capability_index.get((claim["modality"], stage))
        if capability is None:
            status = "NOT_TESTED"
            evidence_reference = None
        else:
            status = capability["status"]
            evidence_reference = capability["evidence_reference"]
        evidence_chain.append(
            {
                "stage": stage,
                "status": status,
                "evidence_reference": evidence_reference,
            }
        )
        if status != "VERIFIED" and blocking_status is None:
            blocking_status = status
            blocking_stage = stage

    if blocking_status is None:
        decision = "CLAIM_STAGE_VERIFIED"
        reason = "every required capability stage has direct verified evidence"
        stage_verified = True
    else:
        decision = f"CLAIM_REJECTED_{blocking_status}"
        reason = f"{blocking_stage} is {blocking_status} for modality {claim['modality']}"
        stage_verified = False

    return {
        "claim_id": claim["claim_id"],
        "modality": claim["modality"],
        "requested_stage": claim["stage"],
        "statement": claim["statement"],
        "required_capability_chain": evidence_chain,
        "decision": decision,
        "reason": reason,
        "stage_verified": stage_verified,
        "claim_truth_established": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }


def build_perceptual_capability_receipt(
    *,
    artifact_id: str,
    artifact_sha256: str,
    media_type: str,
    declared_modalities: Sequence[str],
    capability_evidence: Sequence[Mapping[str, Any]],
    claims: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
    """Assess claims without allowing integrity to impersonate perception."""
    modalities = _modalities(declared_modalities)
    capabilities = _capabilities(capability_evidence, set(modalities))
    normalized_claims = _claims(claims, set(modalities))
    capability_index = {
        (item["modality"], item["stage"]): item for item in capabilities
    }
    assessments = [
        _assessment(claim, capability_index) for claim in normalized_claims
    ]
    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "artifact_id": _text(artifact_id, "artifact_id"),
        "artifact_sha256": _sha256(artifact_sha256, "artifact_sha256"),
        "media_type": _text(media_type, "media_type"),
        "declared_modalities": modalities,
        "capability_evidence": capabilities,
        "claims": normalized_claims,
        "assessments": assessments,
        "all_claim_stages_verified": all(
            assessment["stage_verified"] for assessment in assessments
        ),
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "interpretation_notice": (
            "Artifact integrity and signal measurement do not imply content "
            "perception or interpretation. A verified stage establishes only "
            "that the declared capability stage was demonstrated, not that the "
            "claim is true."
        ),
    }
    return {**body, "receipt_hash": _hash(body)}


def validate_perceptual_capability_receipt(receipt: Mapping[str, Any]) -> bool:
    """Rebuild a receipt and require exact schema, identity, and boundaries."""
    if type(receipt) is not dict:
        raise PerceptualCapabilityBoundaryError("receipt must be a plain dictionary")
    expected_fields = {
        "type", "version", "artifact_id", "artifact_sha256", "media_type",
        "declared_modalities", "capability_evidence", "claims", "assessments",
        "all_claim_stages_verified", "truth_claimed", "accepted",
        "write_authority", "execution_authority", "interpretation_notice",
        "receipt_hash",
    }
    if set(receipt) != expected_fields:
        raise PerceptualCapabilityBoundaryError(
            "receipt fields do not match the versioned schema"
        )
    if receipt.get("type") != RECEIPT_TYPE or receipt.get("version") != RECEIPT_VERSION:
        raise PerceptualCapabilityBoundaryError("receipt type or version is invalid")
    if (
        receipt.get("truth_claimed") is not False
        or receipt.get("accepted") is not False
        or receipt.get("write_authority") != "NONE"
        or receipt.get("execution_authority") != "NONE"
    ):
        raise PerceptualCapabilityBoundaryError("receipt grants forbidden authority")
    try:
        rebuilt = build_perceptual_capability_receipt(
            artifact_id=receipt["artifact_id"],
            artifact_sha256=receipt["artifact_sha256"],
            media_type=receipt["media_type"],
            declared_modalities=receipt["declared_modalities"],
            capability_evidence=receipt["capability_evidence"],
            claims=receipt["claims"],
        )
    except (KeyError, TypeError) as exc:
        raise PerceptualCapabilityBoundaryError("receipt is malformed") from exc
    if rebuilt != receipt:
        raise PerceptualCapabilityBoundaryError(
            "receipt does not match its perceptual capability identity"
        )
    return True
