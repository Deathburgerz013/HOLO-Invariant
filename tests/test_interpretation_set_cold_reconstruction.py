from holosim.interpretation_set_receipt import InterpretationSetReceipt
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


def test_rank_only_interpretation_set_survives_cold_reconstruction():
    source = [
        {
            "id": "interpretation-set",
            "requires": [],
            "observation_id": "obs-001",
            "prior_set": ["A", "B"],
            "ranks": {
                "A": 0.9,
                "B": 0.1,
            },
            "subtract_receipts": [],
            "evidence_receipt_hashes": [],
            "justification_notices": [],
        }
    ]

    state = build_reconstructed_state(
        "cold interpretation reconstruction",
        ["interpretation-set"],
        source,
    )

    assert validate_reconstructed_state(state, source) is True
    assert state["status"] == "COMPLETE"

    carried = state["carried_items"][0]

    receipt = InterpretationSetReceipt(
        observation_id=carried["observation_id"],
        prior_set=carried["prior_set"],
        ranks=carried["ranks"],
        subtract_receipts=carried["subtract_receipts"],
        evidence_receipt_hashes=carried["evidence_receipt_hashes"],
        justification_notices=carried["justification_notices"],
    )

    assert tuple(carried["prior_set"]) == ("A", "B")
    assert receipt.current_set == ("A", "B")