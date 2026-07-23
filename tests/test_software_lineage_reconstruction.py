from __future__ import annotations

from copy import deepcopy

from holosim.canonical import stable_hash
from holosim.software_lineage_reconstruction import reconstruct_software_lineage
from holosim.software_lineage_reproduction import reproduce_stale_handoff_lineage


def _rehash(lineage: dict) -> dict:
    body = {key: value for key, value in lineage.items() if key != "reproduction_hash"}
    lineage["reproduction_hash"] = stable_hash(body)
    return lineage


def test_complete_external_evidence_reconstructs_lineage() -> None:
    result = reconstruct_software_lineage(reproduce_stale_handoff_lineage())

    assert result["status"] == "COMPLETE"
    assert result["reasons"] == []
    reconstruction = result["reconstruction"]
    assert reconstruction["prior_state"]["head_idx"] == 10
    assert reconstruction["prior_state"]["status"] == "CURRENT"
    assert reconstruction["prior_state"]["continuation"] == "ALLOW"
    assert reconstruction["triggering_difference"]["from_head_idx"] == 10
    assert reconstruction["triggering_difference"]["to_head_idx"] == 11
    assert reconstruction["transition"] == {
        "from_status": "CURRENT",
        "to_status": "STALE",
        "reason": "newer_verified_head_exists",
    }
    assert reconstruction["resulting_state"]["continuation_from_prior_handoff"] == "BLOCK"


def test_reconstruction_is_deterministic_and_hash_bound() -> None:
    lineage = reproduce_stale_handoff_lineage()
    first = reconstruct_software_lineage(lineage)
    second = reconstruct_software_lineage(lineage)

    assert first == second
    body = {key: value for key, value in first.items() if key != "receipt_hash"}
    assert first["receipt_hash"] == stable_hash(body)


def test_missing_top_level_evidence_fails_incomplete() -> None:
    lineage = reproduce_stale_handoff_lineage()
    del lineage["newer_verified_head"]

    result = reconstruct_software_lineage(lineage)

    assert result["status"] == "INCOMPLETE"
    assert result["reconstruction"] is None
    assert result["reasons"] == ["missing_required_evidence:newer_verified_head"]


def test_missing_nested_transition_evidence_fails_incomplete() -> None:
    lineage = reproduce_stale_handoff_lineage()
    del lineage["after_environment_change"]["head_check"]["status"]
    _rehash(lineage)

    result = reconstruct_software_lineage(lineage)

    assert result["status"] == "INCOMPLETE"
    assert result["reconstruction"] is None
    assert result["reasons"] == ["nested_required_evidence_missing"]


def test_tampered_external_evidence_fails_invalid() -> None:
    lineage = reproduce_stale_handoff_lineage()
    lineage["newer_verified_head"]["idx"] = 12

    result = reconstruct_software_lineage(lineage)

    assert result["status"] == "INVALID"
    assert result["reconstruction"] is None
    assert result["reasons"] == ["lineage_hash_mismatch"]


def test_rehashed_but_causally_inconsistent_lineage_fails_invalid() -> None:
    lineage = deepcopy(reproduce_stale_handoff_lineage())
    lineage["after_environment_change"]["head_check"]["status"] = "CURRENT"
    _rehash(lineage)

    result = reconstruct_software_lineage(lineage)

    assert result["status"] == "INVALID"
    assert result["reconstruction"] is None
    assert "resulting_state_not_stale" in result["reasons"]


def test_rehashed_lineage_without_preserved_transition_reason_fails_invalid() -> None:
    lineage = deepcopy(reproduce_stale_handoff_lineage())
    lineage["after_environment_change"]["head_check"]["reasons"] = []
    _rehash(lineage)

    result = reconstruct_software_lineage(lineage)

    assert result["status"] == "INVALID"
    assert result["reconstruction"] is None
    assert "transition_reason_not_preserved" in result["reasons"]


def test_reconstruction_preserves_authority_boundaries() -> None:
    result = reconstruct_software_lineage(reproduce_stale_handoff_lineage())

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
