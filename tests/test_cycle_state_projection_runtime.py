import json
from copy import deepcopy
from pathlib import Path

from holosim.cycle_state_projection import check_idx_coherence


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cycle_state_projection"
    / "snapshot_coherence.json"
)


def load_fixture():
    return json.loads(FIXTURE.read_text(encoding="utf-8"))


def test_existing_idx_mismatch_fixture_blocks():
    fixture = load_fixture()
    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )
    assert result["state"] == "BLOCKED_INVARIANT"
    assert "IDX_IDENTITY_MISMATCH" in result["reason_codes"]


def test_matching_idx_does_not_claim_completion_or_verification():
    fixture = load_fixture()
    for receipt in fixture["receipts"]:
        receipt["idx_identity"] = fixture["snapshot"]["idx_identity"]

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )
    assert result["coherent"] is True
    assert result["state"] is None
    assert result["integrity_verified"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_missing_idx_fails_closed():
    fixture = load_fixture()
    del fixture["receipts"][0]["idx_identity"]

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )
    assert result["state"] == "BLOCKED_INVARIANT"
    assert "IDX_IDENTITY_REQUIRED" in result["reason_codes"]


def test_missing_receipt_fails_closed():
    fixture = load_fixture()
    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"][:1]
    )
    assert result["state"] == "BLOCKED_INVARIANT"
    assert "SNAPSHOT_RECEIPT_MISMATCH" in result["reason_codes"]


def test_input_unchanged_and_result_deterministic():
    fixture = load_fixture()
    original = deepcopy(fixture)

    first = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )
    second = check_idx_coherence(
        fixture["snapshot"], list(reversed(fixture["receipts"]))
    )

    assert fixture == original
    assert first == second
    assert first["execution_authorized"] is False
    assert first["state_change_authorized"] is False

def test_caller_valid_flag_does_not_establish_integrity():
    fixture = load_fixture()
    for receipt in fixture["receipts"]:
        receipt["valid"] = True
        receipt["idx_identity"] = fixture["snapshot"]["idx_identity"]

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )

    assert result["coherent"] is True
    assert result["integrity_verified"] is False
    assert result["truth_claimed"] is False
    assert result["execution_authorized"] is False


def test_missing_snapshot_idx_fails_closed():
    fixture = load_fixture()
    del fixture["snapshot"]["idx_identity"]

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )

    assert result["state"] == "BLOCKED_INVARIANT"
    assert "IDX_IDENTITY_REQUIRED" in result["reason_codes"]


def test_duplicate_manifest_hash_fails_closed():
    fixture = load_fixture()
    fixture["snapshot"]["receipt_hashes"][1] = (
        fixture["snapshot"]["receipt_hashes"][0]
    )

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )

    assert result["state"] == "BLOCKED_INVARIANT"
    assert "INVALID_RECEIPT_MANIFEST" in result["reason_codes"]


def test_duplicate_receipt_hash_fails_closed():
    fixture = load_fixture()
    fixture["receipts"][1]["receipt_hash"] = (
        fixture["receipts"][0]["receipt_hash"]
    )

    result = check_idx_coherence(
        fixture["snapshot"], fixture["receipts"]
    )

    assert result["state"] == "BLOCKED_INVARIANT"
    assert "DUPLICATE_RECEIPT" in result["reason_codes"]


def test_invalid_inputs_fail_closed():
    result = check_idx_coherence(None, None)

    assert result["state"] == "BLOCKED_INVARIANT"
    assert "INVALID_SNAPSHOT" in result["reason_codes"]
    assert "INVALID_RECEIPTS" in result["reason_codes"]
    assert result["write_authority"] == "NONE"
