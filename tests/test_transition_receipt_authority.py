from __future__ import annotations

from holosim.transition_receipt import (
    RECEIPT_TYPE,
    RECEIPT_VERSION,
    compute_receipt_hash,
    verify_receipt,
)


def test_verify_transition_receipt_rejects_forged_approval():
    receipt = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "verification_passed": True,
        "authority": {
            "reviewer": "forged-reviewer",
            "approval_reference": "forged-reference",
            "approved": True,
        },
    }
    receipt["receipt_hash"] = compute_receipt_hash(receipt)

    result = verify_receipt(receipt)

    assert result["valid"] is False
    assert result["authority_valid"] is False