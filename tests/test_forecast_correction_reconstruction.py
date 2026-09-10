from holosim.correction import record_correction
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)
from holosim.theory import evaluate_theory_state


def test_failed_forecast_correction_survives_reconstruction():
    original_theory = {
        "theory_id": "transient-regularity-v1",
        "statement": "The observed regularity will persist.",
        "basis": ["initial-observation"],
        "predictions": [
            {
                "prediction_id": "regularity-persists",
                "statement": "The next observation will preserve the regularity.",
            }
        ],
    }

    falsifying_check = {
        "check_id": "observe-next-state",
        "prediction_id": "regularity-persists",
        "outcome": "CONTRADICTED",
        "evidence": "observation:regularity-broke",
        "method": "direct-observation",
    }

    falsified = evaluate_theory_state(
        original_theory,
        [falsifying_check],
    )

    assert falsified["state"] == "FALSIFIED"
    assert falsified["next_action"] == "REVISE_OR_REPLACE_THEORY"

    revised_theory = {
        "theory_id": "transient-regularity-v2",
        "statement": "The observed regularity was transient.",
        "basis": [
            "initial-observation",
            "observation:regularity-broke",
        ],
        "predictions": [
            {
                "prediction_id": "regularity-may-break",
                "statement": "A later observation may differ from the initial regularity.",
            }
        ],
    }

    revised = evaluate_theory_state(
        revised_theory,
        [],
    )

    correction = record_correction(
        previous_receipt_hash=falsified["receipt_hash"],
        proposed_receipt_hash=revised["receipt_hash"],
        resulting_receipt_hash=revised["receipt_hash"],
        reason="The forecast was contradicted by the next observation.",
        evidence_receipt_hashes=[falsified["receipt_hash"]],
    )

    source = [
        {
            "id": "forecast-original",
            "requires": [],
            "receipt": falsified,
        },
        {
            "id": "forecast-revised",
            "requires": ["forecast-original"],
            "receipt": revised,
        },
        {
            "id": "forecast-correction",
            "requires": [
                "forecast-original",
                "forecast-revised",
            ],
            "receipt": correction,
        },
    ]

    state = build_reconstructed_state(
        "failed forecast correction reconstruction",
        ["forecast-correction"],
        source,
    )

    assert validate_reconstructed_state(state, source) is True
    assert state["status"] == "COMPLETE"

    carried = {
        item["id"]: item
        for item in state["carried_items"]
    }

    assert set(carried) == {
        "forecast-original",
        "forecast-revised",
        "forecast-correction",
    }

    reconstructed_original = carried["forecast-original"]["receipt"]
    reconstructed_revised = carried["forecast-revised"]["receipt"]
    reconstructed_correction = carried["forecast-correction"]["receipt"]

    assert reconstructed_original == falsified
    assert reconstructed_original["state"] == "FALSIFIED"
    assert reconstructed_original["theory"] == original_theory

    assert reconstructed_revised == revised
    assert reconstructed_revised["receipt_hash"] != falsified["receipt_hash"]

    assert (
        reconstructed_correction["previous_receipt_hash"]
        == falsified["receipt_hash"]
    )
    assert (
        reconstructed_correction["resulting_receipt_hash"]
        == revised["receipt_hash"]
    )
    assert reconstructed_correction["changed"] is True
    assert reconstructed_correction["proposal_adopted"] is True

    assert reconstructed_correction["accepted"] is False
    assert reconstructed_correction["truth_claimed"] is False
    assert reconstructed_correction["write_authority"] == "NONE"