from __future__ import annotations

from holosim.canonical import stable_hash
from holosim.software_lineage_reproduction import reproduce_stale_handoff_lineage


def test_reproduction_is_deterministic() -> None:
    first = reproduce_stale_handoff_lineage()
    second = reproduce_stale_handoff_lineage()

    assert first == second
    body = {key: value for key, value in first.items() if key != "reproduction_hash"}
    assert first["reproduction_hash"] == stable_hash(body)


def test_handoff_is_current_before_newer_head_exists() -> None:
    result = reproduce_stale_handoff_lineage()
    before = result["before_environment_change"]

    assert before["head_check"]["status"] == "CURRENT"
    assert before["gate"]["decision"] == "ALLOW"


def test_same_intact_handoff_becomes_stale_after_newer_verified_head() -> None:
    result = reproduce_stale_handoff_lineage()
    before = result["before_environment_change"]["head_check"]
    after = result["after_environment_change"]["head_check"]

    assert before["binding_hash"] == after["binding_hash"]
    assert before["contract_hash"] == after["contract_hash"]
    assert after["status"] == "STALE"
    assert after["reasons"] == ["newer_verified_head_exists"]


def test_stale_handoff_is_blocked() -> None:
    result = reproduce_stale_handoff_lineage()
    after = result["after_environment_change"]

    assert after["gate"]["head_status"] == "STALE"
    assert after["gate"]["decision"] == "BLOCK"
    assert after["gate"]["reasons"] == ["continuity_head_status_stale"]


def test_environment_change_advances_verified_head_identity() -> None:
    result = reproduce_stale_handoff_lineage()
    original = result["original_verified_head"]
    newer = result["newer_verified_head"]

    assert original["idx"] == 10
    assert newer["idx"] == 11
    assert original["head_hash"] != newer["head_hash"]
    assert original["state"]["release"] == "S0"
    assert newer["state"]["release"] == "S1"


def test_fixture_preserves_authority_boundaries() -> None:
    result = reproduce_stale_handoff_lineage()

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["contract"]["write_authority"] == "NONE"
    assert result["binding"]["write_authority"] == "NONE"


def test_fixture_names_atomic_fracture_without_claiming_truth() -> None:
    result = reproduce_stale_handoff_lineage()

    assert result["scenario"] == "valid_prior_handoff_survives_newer_verified_head"
    assert (
        result["observed_fracture"]
        == "stored_handoff_remains_intact_but_is_no_longer_applicable_for_continuation"
    )
    assert result["reproduction_passes"] is True
