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
def test_permutation_invariance_fixture_preserves_projection_result():
    fixture = json.loads(
        (
            Path(__file__).parent
            / "fixtures"
            / "cycle_state_projection"
            / "permutation_invariance.json"
        ).read_text(encoding="utf-8")
    )

    assert fixture["projection_version"] == "0.1"
    assert fixture["ordering_rule"]["receipt_order_semantic"] is False

    snapshot = fixture["snapshot"]
    receipts = fixture["receipts"]
    permutations = fixture["permutations"]
    expected = fixture["expected"]

    known_hashes = {
        receipt["receipt_hash"]
        for receipt in receipts.values()
    }

    assert known_hashes == set(snapshot["receipt_hashes"])
    assert len(permutations) == 2

    for permutation in permutations:
        assert set(permutation) == known_hashes

    assert permutations[0] == list(reversed(permutations[1]))

    plan = receipts["dependency_recheck_plan"]
    certificate = receipts["completion_certificate"]

    assert plan["type"] == "dependency_recheck_plan"
    assert plan["plan_hash"] == plan["receipt_hash"]
    assert plan["recheck_required_count"] == 1
    assert any(
        result["status"] == "RECHECK_REQUIRED"
        for result in plan["results"]
    )

    assert certificate["type"] == "environment_completion_certificate"
    assert certificate["certificate_id"] == certificate["receipt_hash"]
    assert certificate["status"] == "COMPLETE_ELIGIBLE"

    assert expected["state"] == "RECHECK_REQUIRED"
    assert "DEPENDENCY_RECHECK_REQUIRED" in expected["reason_codes"]

    assert expected["source_receipt_identities"] == [
        {
            "type": "dependency_recheck_plan",
            "hash": plan["receipt_hash"],
        }
    ]

    assert expected["scope"]["frame_identity"] == certificate["frame_identity"]
    assert expected["scope"]["episode_identity"] == certificate["episode_id"]
    assert expected["scope"]["environment_id"] == certificate["environment_id"]

    assert expected["truth_claimed"] is False
    assert expected["accepted"] is False
    assert expected["execution_authorized"] is False
    assert expected["state_change_authorized"] is False
    assert expected["write_authority"] == "NONE"