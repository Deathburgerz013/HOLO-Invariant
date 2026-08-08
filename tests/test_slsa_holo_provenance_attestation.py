from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.letta_memory_proposal_boundary import (
    create_memory_edit_proposal,
    verify_memory_edit_proposal,
)
from holosim.slsa_holo_provenance_attestation import (
    SlsaHoloAttestationError,
    create_slsa_holo_attestation,
    verify_slsa_holo_attestation,
)


CURRENT_VALUE = "User prefers exact, falsifiable checks."


def _receipt():
    edit_body = {
        "type": "letta_memory_edit",
        "version": 1,
        "agent_id": "agent:holo-build",
        "block_id": "block:project",
        "block_label": "project",
        "operation": "replace",
        "prior_value_sha256": stable_hash(CURRENT_VALUE),
        "proposed_value": "The artifact passed its declared checks.",
        "observed_at": "2026-08-08T21:00:00Z",
        "provenance": {"source_id": "build:invocation-7"},
    }
    edit = {**edit_body, "edit_id": stable_hash(edit_body)}
    return create_memory_edit_proposal(
        edit=edit,
        current_value=CURRENT_VALUE,
    )


def _statement():
    return create_slsa_holo_attestation(
        artifact_name="dist/holo_adapter.whl",
        artifact_sha256="a" * 64,
        source_uri="git+https://github.com/example/project@main",
        source_digest="b" * 64,
        builder_id="https://holo-invariant.dev/builders/local/v1",
        builder_version="1.0.0",
        invocation_id="build:invocation-7",
        started_on="2026-08-08T21:00:00Z",
        finished_on="2026-08-08T21:00:03Z",
        receipt=_receipt(),
        receipt_id_field="proposal_id",
        receipt_verifier=verify_memory_edit_proposal,
    )


def _rehash(statement):
    statement["holo_statementId"] = stable_hash(
        {
            key: value
            for key, value in statement.items()
            if key != "holo_statementId"
        }
    )


def test_verified_receipt_exports_as_non_authoritative_slsa_statement():
    receipt = _receipt()
    before = deepcopy(receipt)

    statement = create_slsa_holo_attestation(
        artifact_name="dist/holo_adapter.whl",
        artifact_sha256="a" * 64,
        source_uri="git+https://github.com/example/project@main",
        source_digest="b" * 64,
        builder_id="https://holo-invariant.dev/builders/local/v1",
        builder_version="1.0.0",
        invocation_id="build:invocation-7",
        started_on="2026-08-08T21:00:00Z",
        finished_on="2026-08-08T21:00:03Z",
        receipt=receipt,
        receipt_id_field="proposal_id",
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert receipt == before
    assert statement["_type"] == "https://in-toto.io/Statement/v1"
    assert statement["predicateType"] == "https://slsa.dev/provenance/v1"
    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )
    assert result["valid"] is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["signed"] is False
    assert result["slsa_level_claimed"] is False


def test_invalid_holo_receipt_cannot_be_exported():
    receipt = _receipt()
    receipt["accepted"] = True
    receipt["proposal_id"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "proposal_id"
        }
    )

    with pytest.raises(
        SlsaHoloAttestationError,
        match="verification failed",
    ):
        create_slsa_holo_attestation(
            artifact_name="dist/holo_adapter.whl",
            artifact_sha256="a" * 64,
            source_uri="git+https://github.com/example/project@main",
            source_digest="b" * 64,
            builder_id="https://holo-invariant.dev/builders/local/v1",
            builder_version="1.0.0",
            invocation_id="build:invocation-7",
            started_on="2026-08-08T21:00:00Z",
            finished_on="2026-08-08T21:00:03Z",
            receipt=receipt,
            receipt_id_field="proposal_id",
            receipt_verifier=verify_memory_edit_proposal,
        )


def test_rehashed_undeclared_statement_field_is_rejected():
    statement = _statement()
    statement["approval"] = "GRANTED"
    _rehash(statement)

    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


def test_rehashed_undeclared_holo_extension_field_is_rejected():
    statement = _statement()
    statement["predicate"]["holo_receipt"]["approval"] = "GRANTED"
    _rehash(statement)

    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truthClaimed", True),
        ("writeAuthority", "GRANTED"),
        ("executionAuthority", "GRANTED"),
    ],
)
def test_rehashed_authority_escalation_is_rejected(field, value):
    statement = _statement()
    statement["predicate"]["holo_receipt"][field] = value
    _rehash(statement)

    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_receipt_dependency_cannot_be_rebound_and_rehashed():
    statement = _statement()
    statement["predicate"]["buildDefinition"]["resolvedDependencies"][0][
        "digest"
    ]["sha256"] = "c" * 64
    _rehash(statement)

    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert result["valid"] is False
    assert "resolved dependencies" in result["violations"][0]


def test_artifact_subject_tampering_fails_without_statement_rehash():
    statement = _statement()
    statement["subject"][0]["digest"]["sha256"] = "d" * 64

    result = verify_slsa_holo_attestation(
        statement,
        receipt_verifier=verify_memory_edit_proposal,
    )

    assert result["valid"] is False
    assert "statement identity mismatch" in result["violations"][0]