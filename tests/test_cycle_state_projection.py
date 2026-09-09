import json
from pathlib import Path


FIXTURE = (
    Path(__file__).parent
    / "fixtures"
    / "cycle_state_projection"
    / "snapshot_coherence.json"
)


def test_snapshot_coherence_fixture_is_self_consistent():
    fixture = json.loads(FIXTURE.read_text(encoding="utf-8"))

    assert fixture["projection_version"] == "0.1"

    snapshot = fixture["snapshot"]
    receipts = fixture["receipts"]
    expected = fixture["expected"]

    assert len(receipts) == 2
    assert {
        receipt["receipt_hash"]
        for receipt in receipts
    } == set(snapshot["receipt_hashes"])

    assert all(receipt["valid"] is True for receipt in receipts)

    receipt_idx_identities = {
        receipt["idx_identity"]
        for receipt in receipts
    }

    assert snapshot["idx_identity"] in receipt_idx_identities
    assert len(receipt_idx_identities) > 1

    assert expected["state"] == "BLOCKED_INVARIANT"
    assert "IDX_IDENTITY_MISMATCH" in expected["reason_codes"]
    assert expected["state"] not in expected["must_not_return"]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"