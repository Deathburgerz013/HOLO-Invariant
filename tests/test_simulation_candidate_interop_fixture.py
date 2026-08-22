"""Consume Simulation's exact published portable candidate fixture."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from holosim.simulation_candidate_evidence_bridge import (
    SimulationCandidateEvidenceBridgeError,
    create_simulation_candidate_environment_receipt,
    verify_simulation_candidate_environment_receipt,
    verify_simulation_candidate_evidence_bundle,
)


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "interop" / "simulation-portable-candidate-evidence-bundle-v1.json"
FIXTURE_SHA256 = "bf0067544143da208069c5a83250d77f809fd2aeedce4c6d67b23e7dd898ec99"


def _fixture_bytes() -> bytes:
    data = FIXTURE.read_bytes()
    assert hashlib.sha256(data).hexdigest() == FIXTURE_SHA256
    return data


def _bundle():
    import json

    return json.loads(_fixture_bytes().decode("utf-8"))


def test_exact_simulation_fixture_verifies_in_holo() -> None:
    bundle = _bundle()
    assert verify_simulation_candidate_evidence_bundle(bundle) is True
    assert bundle["write_authority"] == "NONE"
    assert bundle["promotion_authority"] == "NONE"


def test_exact_fixture_binds_only_to_matching_current_source() -> None:
    bundle = _bundle()
    source_manifest = bundle["validation_packet"]["source_manifest_hash"]
    receipt = create_simulation_candidate_environment_receipt(
        bundle=bundle,
        source_manifest_probe=lambda: source_manifest,
        observed_at="2026-08-22T19:00:00Z",
    )
    assert receipt["status"] == "HELD"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["accepted"] is False
    assert verify_simulation_candidate_environment_receipt(receipt) is True


def test_one_byte_fixture_change_cannot_verify() -> None:
    changed = bytearray(_fixture_bytes())
    index = changed.index(b"VALIDATED_CANDIDATE")
    changed[index] = ord("X")
    assert hashlib.sha256(changed).hexdigest() != FIXTURE_SHA256
    import json

    value = json.loads(bytes(changed).decode("utf-8"))
    with pytest.raises(
        SimulationCandidateEvidenceBridgeError,
        match="bundle hash mismatch",
    ):
        verify_simulation_candidate_evidence_bundle(value)
