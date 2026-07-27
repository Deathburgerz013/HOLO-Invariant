from holosim.canonical import stable_hash
from holosim.recall_trial import evaluate_reconstruction


def _receipt(value: int) -> dict[str, object]:
    body = {
        "type": "state_receipt",
        "claim_id": "project.test_count",
        "value": value,
    }
    return {
        **body,
        "receipt_hash": stable_hash(body),
    }


def test_recall_trial_distinguishes_current_stale_and_unsupported_claims() -> None:
    receipt_734 = _receipt(734)
    receipt_736 = _receipt(736)
    receipt_738 = _receipt(738)

    correction_body = {
        "type": "correction_receipt",
        "version": 1,
        "previous_receipt_hash": receipt_736["receipt_hash"],
        "proposed_receipt_hash": receipt_738["receipt_hash"],
        "resulting_receipt_hash": receipt_738["receipt_hash"],
        "reason": "738 supersedes the earlier observed test count",
        "evidence_receipt_hashes": [receipt_738["receipt_hash"]],
        "metadata": {},
        "changed": True,
        "proposal_adopted": True,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }
    correction = {
        **correction_body,
        "receipt_hash": stable_hash(correction_body),
    }

    result = evaluate_reconstruction(
        evidence_receipts=[
            receipt_734,
            receipt_736,
            receipt_738,
            correction,
        ],
        required_claim_ids=["project.test_count"],
        candidate_claims=[
            {
                "claim_id": "project.test_count",
                "value": 736,
                "evidence_receipt_hashes": [receipt_736["receipt_hash"]],
            },
            {
                "claim_id": "project.test_count",
                "value": 738,
                "evidence_receipt_hashes": [
                    receipt_738["receipt_hash"],
                    correction["receipt_hash"],
                ],
            },
            {
                "claim_id": "project.imaginary_count",
                "value": 800,
                "evidence_receipt_hashes": [],
            },
        ],
    )

    assert result["supported_claim_indexes"] == [1]
    assert result["stale_claim_indexes"] == [0]
    assert result["unsupported_claim_indexes"] == [2]
    assert result["missing_required_claim_ids"] == []
    assert result["correction_survived"] is True
    assert result["valid"] is False
def test_recall_trial_supports_uncorrected_evidence() -> None:
    receipt = _receipt(749)

    result = evaluate_reconstruction(
        evidence_receipts=[receipt],
        required_claim_ids=["project.test_count"],
        candidate_claims=[
            {
                "claim_id": "project.test_count",
                "value": 749,
                "evidence_receipt_hashes": [receipt["receipt_hash"]],
            },
        ],
    )

    assert result["supported_claim_indexes"] == [0]
    assert result["stale_claim_indexes"] == []
    assert result["unsupported_claim_indexes"] == []
    assert result["missing_required_claim_ids"] == []
    assert result["correction_survived"] is True
    assert result["valid"] is True