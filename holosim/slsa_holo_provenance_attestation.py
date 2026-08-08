"""Exact-schema HOLO binding for in-toto/SLSA provenance statements.

The adapter emits an in-toto Statement v1 using the SLSA provenance v1
predicate.  A namespaced HOLO extension preserves the complete verified
receipt and its canonical envelope identity.  The statement is observational:
it does not sign itself, establish artifact truth, or grant authority.
"""

from __future__ import annotations

import re
from copy import deepcopy
from datetime import datetime
from typing import Any, Callable, Mapping

from holosim.canonical import CanonicalValueError, stable_hash


STATEMENT_TYPE = "https://in-toto.io/Statement/v1"
PREDICATE_TYPE = "https://slsa.dev/provenance/v1"
BUILD_TYPE = "https://holo-invariant.dev/buildtypes/verified-receipt/v1"
STATEMENT_FIELDS = {
    "_type",
    "subject",
    "predicateType",
    "predicate",
    "holo_statementId",
}
PREDICATE_FIELDS = {"buildDefinition", "runDetails", "holo_receipt"}
BUILD_DEFINITION_FIELDS = {
    "buildType",
    "externalParameters",
    "internalParameters",
    "resolvedDependencies",
}
EXTERNAL_PARAMETER_FIELDS = {"sourceUri", "sourceDigest"}
RUN_DETAILS_FIELDS = {"builder", "metadata", "byproducts"}
BUILDER_FIELDS = {"id", "version", "builderDependencies"}
METADATA_FIELDS = {"invocationId", "startedOn", "finishedOn"}
HOLO_RECEIPT_FIELDS = {
    "receiptIdField",
    "receiptId",
    "receiptEnvelopeSha256",
    "receipt",
    "verification",
    "accepted",
    "truthClaimed",
    "writeAuthority",
    "executionAuthority",
    "interpretationNotice",
}
VERIFICATION_FIELDS = {
    "valid",
    "accepted",
    "truthClaimed",
    "writeAuthority",
    "executionAuthority",
}


class SlsaHoloAttestationError(ValueError):
    """Raised when provenance crosses the HOLO attestation boundary."""


def _hash(value: Any) -> str:
    try:
        return stable_hash(value)
    except CanonicalValueError as exc:
        raise SlsaHoloAttestationError(str(exc)) from exc


def _required_text(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SlsaHoloAttestationError(
            f"{field} must be a non-empty string"
        )
    return value


def _sha256(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if not re.fullmatch(r"[0-9a-f]{64}", text):
        raise SlsaHoloAttestationError(
            f"{field} must be lowercase SHA-256 hex"
        )
    return text


def _timestamp(value: Any, field: str) -> str:
    text = _required_text(value, field)
    if not text.endswith("Z"):
        raise SlsaHoloAttestationError(
            f"{field} must be a UTC RFC-3339 timestamp ending in Z"
        )
    try:
        parsed = datetime.fromisoformat(text[:-1] + "+00:00")
    except ValueError as exc:
        raise SlsaHoloAttestationError(
            f"{field} must be a valid RFC-3339 timestamp"
        ) from exc
    if parsed.utcoffset() is None:
        raise SlsaHoloAttestationError(
            f"{field} must include a timezone"
        )
    return text


def _exact_fields(
    value: Any,
    expected: set[str],
    field: str,
) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SlsaHoloAttestationError(f"{field} must be an object")
    normalized = deepcopy(dict(value))
    missing = sorted(expected - set(normalized))
    extra = sorted(set(normalized) - expected)
    if missing:
        raise SlsaHoloAttestationError(
            f"{field} is missing fields: " + ", ".join(missing)
        )
    if extra:
        raise SlsaHoloAttestationError(
            f"{field} has unsupported fields: " + ", ".join(extra)
        )
    return normalized


def _verify_receipt(
    receipt: Mapping[str, Any],
    receipt_id_field: str,
    receipt_verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> tuple[dict[str, Any], str]:
    if not isinstance(receipt, Mapping):
        raise SlsaHoloAttestationError("receipt must be an object")
    normalized = deepcopy(dict(receipt))
    _hash(normalized)
    field = _required_text(receipt_id_field, "receipt_id_field")
    if field not in normalized:
        raise SlsaHoloAttestationError(
            "receipt does not contain the declared identity field"
        )
    receipt_id = _sha256(normalized[field], f"receipt.{field}")
    if not callable(receipt_verifier):
        raise SlsaHoloAttestationError("receipt_verifier must be callable")
    result = receipt_verifier(deepcopy(normalized))
    if not isinstance(result, Mapping):
        raise SlsaHoloAttestationError(
            "receipt verifier must return an object"
        )
    if result.get("valid") is not True:
        raise SlsaHoloAttestationError("HOLO receipt verification failed")
    if result.get(field) != receipt_id:
        raise SlsaHoloAttestationError(
            "receipt verifier did not bind the declared identity"
        )
    boundaries = {
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }
    for key, expected in boundaries.items():
        if key in result and result[key] != expected:
            raise SlsaHoloAttestationError(
                f"receipt verifier crossed authority boundary: {key}"
            )
    return normalized, receipt_id


def create_slsa_holo_attestation(
    *,
    artifact_name: str,
    artifact_sha256: str,
    source_uri: str,
    source_digest: str,
    builder_id: str,
    builder_version: str,
    invocation_id: str,
    started_on: str,
    finished_on: str,
    receipt: Mapping[str, Any],
    receipt_id_field: str,
    receipt_verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    """Export one verified HOLO receipt into SLSA provenance."""
    normalized_receipt, receipt_id = _verify_receipt(
        receipt,
        receipt_id_field,
        receipt_verifier,
    )
    name = _required_text(artifact_name, "artifact_name")
    artifact_digest = _sha256(artifact_sha256, "artifact_sha256")
    normalized_source_uri = _required_text(source_uri, "source_uri")
    normalized_source_digest = _sha256(source_digest, "source_digest")
    normalized_builder_id = _required_text(builder_id, "builder_id")
    normalized_builder_version = _required_text(
        builder_version,
        "builder_version",
    )
    normalized_invocation_id = _required_text(
        invocation_id,
        "invocation_id",
    )
    started = _timestamp(started_on, "started_on")
    finished = _timestamp(finished_on, "finished_on")
    if datetime.fromisoformat(finished[:-1] + "+00:00") < (
        datetime.fromisoformat(started[:-1] + "+00:00")
    ):
        raise SlsaHoloAttestationError(
            "finished_on cannot be earlier than started_on"
        )

    receipt_envelope_hash = _hash(normalized_receipt)
    body: dict[str, Any] = {
        "_type": STATEMENT_TYPE,
        "subject": [
            {"name": name, "digest": {"sha256": artifact_digest}}
        ],
        "predicateType": PREDICATE_TYPE,
        "predicate": {
            "buildDefinition": {
                "buildType": BUILD_TYPE,
                "externalParameters": {
                    "sourceUri": normalized_source_uri,
                    "sourceDigest": normalized_source_digest,
                },
                "internalParameters": {},
                "resolvedDependencies": [
                    {
                        "uri": f"urn:holo:receipt:{receipt_id}",
                        "digest": {"sha256": receipt_envelope_hash},
                    },
                    {
                        "uri": normalized_source_uri,
                        "digest": {"sha256": normalized_source_digest},
                    },
                ],
            },
            "runDetails": {
                "builder": {
                    "id": normalized_builder_id,
                    "version": {"adapter": normalized_builder_version},
                    "builderDependencies": [],
                },
                "metadata": {
                    "invocationId": normalized_invocation_id,
                    "startedOn": started,
                    "finishedOn": finished,
                },
                "byproducts": [],
            },
            "holo_receipt": {
                "receiptIdField": receipt_id_field,
                "receiptId": receipt_id,
                "receiptEnvelopeSha256": receipt_envelope_hash,
                "receipt": normalized_receipt,
                "verification": {
                    "valid": True,
                    "accepted": False,
                    "truthClaimed": False,
                    "writeAuthority": "NONE",
                    "executionAuthority": "NONE",
                },
                "accepted": False,
                "truthClaimed": False,
                "writeAuthority": "NONE",
                "executionAuthority": "NONE",
                "interpretationNotice": (
                    "This statement binds artifact and receipt identities "
                    "only. It is unsigned, establishes no truth or SLSA "
                    "level, and grants no acceptance, write authority, or "
                    "execution authority."
                ),
            },
        },
    }
    return {**body, "holo_statementId": _hash(body)}


def verify_slsa_holo_attestation(
    statement: Mapping[str, Any],
    *,
    receipt_verifier: Callable[[Mapping[str, Any]], Mapping[str, Any]],
) -> dict[str, Any]:
    """Verify exact statement shape, identities, and receipt boundaries."""
    violations: list[str] = []
    actual_id = (
        statement.get("holo_statementId")
        if isinstance(statement, Mapping)
        else None
    )
    expected_id: str | None = None
    try:
        root = _exact_fields(statement, STATEMENT_FIELDS, "statement")
        if root["_type"] != STATEMENT_TYPE:
            raise SlsaHoloAttestationError("statement type is invalid")
        if root["predicateType"] != PREDICATE_TYPE:
            raise SlsaHoloAttestationError("predicate type is invalid")
        if not isinstance(root["subject"], list) or len(root["subject"]) != 1:
            raise SlsaHoloAttestationError(
                "statement must contain exactly one subject"
            )
        subject = _exact_fields(
            root["subject"][0],
            {"name", "digest"},
            "subject",
        )
        _required_text(subject["name"], "subject.name")
        digest = _exact_fields(
            subject["digest"], {"sha256"}, "subject.digest"
        )
        _sha256(digest["sha256"], "subject.digest.sha256")

        predicate = _exact_fields(
            root["predicate"], PREDICATE_FIELDS, "predicate"
        )
        definition = _exact_fields(
            predicate["buildDefinition"],
            BUILD_DEFINITION_FIELDS,
            "buildDefinition",
        )
        if definition["buildType"] != BUILD_TYPE:
            raise SlsaHoloAttestationError("build type is invalid")
        parameters = _exact_fields(
            definition["externalParameters"],
            EXTERNAL_PARAMETER_FIELDS,
            "externalParameters",
        )
        _required_text(parameters["sourceUri"], "sourceUri")
        _sha256(parameters["sourceDigest"], "sourceDigest")
        if definition["internalParameters"] != {}:
            raise SlsaHoloAttestationError(
                "internalParameters must remain empty"
            )

        run_details = _exact_fields(
            predicate["runDetails"], RUN_DETAILS_FIELDS, "runDetails"
        )
        builder = _exact_fields(
            run_details["builder"], BUILDER_FIELDS, "builder"
        )
        _required_text(builder["id"], "builder.id")
        if (
            not isinstance(builder["version"], Mapping)
            or set(builder["version"]) != {"adapter"}
        ):
            raise SlsaHoloAttestationError(
                "builder.version must contain only adapter"
            )
        _required_text(builder["version"]["adapter"], "builder.version.adapter")
        if builder["builderDependencies"] != []:
            raise SlsaHoloAttestationError(
                "builderDependencies must be empty"
            )
        metadata = _exact_fields(
            run_details["metadata"], METADATA_FIELDS, "metadata"
        )
        _required_text(metadata["invocationId"], "invocationId")
        started = _timestamp(metadata["startedOn"], "startedOn")
        finished = _timestamp(metadata["finishedOn"], "finishedOn")
        if datetime.fromisoformat(finished[:-1] + "+00:00") < (
            datetime.fromisoformat(started[:-1] + "+00:00")
        ):
            raise SlsaHoloAttestationError(
                "finishedOn cannot be earlier than startedOn"
            )
        if run_details["byproducts"] != []:
            raise SlsaHoloAttestationError("byproducts must be empty")

        holo = _exact_fields(
            predicate["holo_receipt"],
            HOLO_RECEIPT_FIELDS,
            "holo_receipt",
        )
        verification = _exact_fields(
            holo["verification"],
            VERIFICATION_FIELDS,
            "holo_receipt.verification",
        )
        expected_boundaries = {
            "valid": True,
            "accepted": False,
            "truthClaimed": False,
            "writeAuthority": "NONE",
            "executionAuthority": "NONE",
        }
        if verification != expected_boundaries:
            raise SlsaHoloAttestationError(
                "embedded verification crossed authority boundaries"
            )
        for field, expected in (
            ("accepted", False),
            ("truthClaimed", False),
            ("writeAuthority", "NONE"),
            ("executionAuthority", "NONE"),
        ):
            if holo[field] != expected:
                raise SlsaHoloAttestationError(
                    f"HOLO extension crossed authority boundary: {field}"
                )
        receipt, receipt_id = _verify_receipt(
            holo["receipt"],
            holo["receiptIdField"],
            receipt_verifier,
        )
        if holo["receiptId"] != receipt_id:
            raise SlsaHoloAttestationError("receipt identity mismatch")
        envelope_hash = _hash(receipt)
        if holo["receiptEnvelopeSha256"] != envelope_hash:
            raise SlsaHoloAttestationError(
                "receipt envelope identity mismatch"
            )

        dependencies = definition["resolvedDependencies"]
        if not isinstance(dependencies, list) or len(dependencies) != 2:
            raise SlsaHoloAttestationError(
                "resolvedDependencies must contain receipt and source"
            )
        expected_dependencies = [
            {
                "uri": f"urn:holo:receipt:{receipt_id}",
                "digest": {"sha256": envelope_hash},
            },
            {
                "uri": parameters["sourceUri"],
                "digest": {"sha256": parameters["sourceDigest"]},
            },
        ]
        if dependencies != expected_dependencies:
            raise SlsaHoloAttestationError(
                "resolved dependencies do not match bound identities"
            )

        body = {
            key: deepcopy(root[key])
            for key in STATEMENT_FIELDS
            if key != "holo_statementId"
        }
        expected_id = _hash(body)
        _sha256(actual_id, "holo_statementId")
        if actual_id != expected_id:
            raise SlsaHoloAttestationError("statement identity mismatch")
    except (SlsaHoloAttestationError, CanonicalValueError) as exc:
        violations.append(str(exc))

    return {
        "valid": not violations,
        "statement_id": actual_id,
        "expected_statement_id": expected_id,
        "violations": violations,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
        "signed": False,
        "slsa_level_claimed": False,
    }