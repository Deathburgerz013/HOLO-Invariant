from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.signed_occurrence import (
    SignedOccurrenceError,
    build_signed_occurrence,
    verify_signed_occurrence,
)


SECRET = b"a" * 32


def _occurrence() -> dict:
    return build_signed_occurrence(
        source_id="source:proteus-node-1",
        occurrence_id="occurrence:0001",
        payload={"claim": "pulse observed", "value": 0.863853},
        observed_at="2026-08-02T12:00:00Z",
        sequence=1,
        nonce="nonce:0000000000000001",
        secret=SECRET,
    )


def test_registered_source_verifies_without_gaining_authority():
    result = verify_signed_occurrence(
        occurrence=_occurrence(),
        source_secrets={"source:proteus-node-1": SECRET},
        seen_occurrence_ids=set(),
    )

    assert result["status"] == "VERIFIED"
    assert result["verified"] is True
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_tampered_payload_is_rejected():
    occurrence = _occurrence()
    occurrence["payload"]["value"] = 1.0

    result = verify_signed_occurrence(
        occurrence=occurrence,
        source_secrets={"source:proteus-node-1": SECRET},
        seen_occurrence_ids=set(),
    )

    assert result["status"] == "REJECTED_TAMPERED"
    assert result["verified"] is False


def test_unknown_source_is_rejected():
    result = verify_signed_occurrence(
        occurrence=_occurrence(),
        source_secrets={},
        seen_occurrence_ids=set(),
    )

    assert result["status"] == "REJECTED_UNKNOWN_SOURCE"
    assert result["verified"] is False


def test_seen_occurrence_is_rejected_as_replay():
    occurrence = _occurrence()

    result = verify_signed_occurrence(
        occurrence=occurrence,
        source_secrets={"source:proteus-node-1": SECRET},
        seen_occurrence_ids={occurrence["occurrence_id"]},
    )

    assert result["status"] == "REJECTED_REPLAY"
    assert result["verified"] is False


def test_signature_and_secret_are_not_interchangeable_or_exported():
    occurrence = _occurrence()

    assert SECRET.hex() not in occurrence["signature"]
    assert "secret" not in occurrence

    wrong_secret_result = verify_signed_occurrence(
        occurrence=occurrence,
        source_secrets={"source:proteus-node-1": b"b" * 32},
        seen_occurrence_ids=set(),
    )
    assert wrong_secret_result["status"] == "REJECTED_TAMPERED"


def test_short_secret_and_noncanonical_payload_are_rejected():
    with pytest.raises(SignedOccurrenceError, match="at least 32 bytes"):
        build_signed_occurrence(
            source_id="source:test",
            occurrence_id="occurrence:test",
            payload={"claim": "test"},
            observed_at="2026-08-02T12:00:00Z",
            sequence=1,
            nonce="nonce:0000000000000001",
            secret=b"short",
        )

    with pytest.raises(SignedOccurrenceError, match="unsupported type"):
        build_signed_occurrence(
            source_id="source:test",
            occurrence_id="occurrence:test",
            payload={"claim": {"not", "canonical"}},
            observed_at="2026-08-02T12:00:00Z",
            sequence=1,
            nonce="nonce:0000000000000001",
            secret=SECRET,
        )


def test_authority_field_injection_is_rejected_by_schema():
    occurrence = deepcopy(_occurrence())
    occurrence["accepted"] = True

    with pytest.raises(
        SignedOccurrenceError,
        match="fields do not match",
    ):
        verify_signed_occurrence(
            occurrence=occurrence,
            source_secrets={"source:proteus-node-1": SECRET},
            seen_occurrence_ids=set(),
        )
