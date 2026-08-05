from holosim.auditable_residue_verifier import (
    build_auditable_residue_verifier,
)


def test_reconstruction_fails_when_recorded_contradiction_is_omitted():
    verifier = build_auditable_residue_verifier()

    result = verifier(
        preserved_record={
            "state": {
                "status": "ready",
            },
            "contradictions": [
                {
                    "id": "status-conflict",
                    "field": "status",
                    "observed_values": [
                        "ready",
                        "blocked",
                    ],
                }
            ],
        },
        reconstructed_state={
            "state": {
                "status": "ready",
            },
            "contradictions": [],
        },
    )

    assert result["verified"] is False
    assert result["continuity_claimed"] is False
    assert result["reason"] == "RECORDED_CONTRADICTION_OMITTED"
    assert result["omitted_contradiction_ids"] == [
        "status-conflict"
    ]
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"


def test_reconstruction_fails_when_contradiction_content_is_rewritten():
    verifier = build_auditable_residue_verifier()

    result = verifier(
        preserved_record={
            "state": {
                "status": "ready",
            },
            "contradictions": [
                {
                    "id": "status-conflict",
                    "field": "status",
                    "observed_values": [
                        "ready",
                        "blocked",
                    ],
                }
            ],
        },
        reconstructed_state={
            "state": {
                "status": "ready",
            },
            "contradictions": [
                {
                    "id": "status-conflict",
                    "field": "status",
                    "observed_values": [
                        "ready",
                    ],
                }
            ],
        },
    )

    assert result["verified"] is False
    assert result["continuity_claimed"] is False
    assert result["reason"] == "RECORDED_CONTRADICTION_REWRITTEN"
    assert result["rewritten_contradiction_ids"] == [
        "status-conflict"
    ]


def test_reconstruction_verifies_when_contradictions_survive_unchanged():
    verifier = build_auditable_residue_verifier()

    contradiction = {
        "id": "status-conflict",
        "field": "status",
        "observed_values": [
            "ready",
            "blocked",
        ],
    }

    result = verifier(
        preserved_record={
            "state": {
                "status": "ready",
            },
            "contradictions": [contradiction],
        },
        reconstructed_state={
            "state": {
                "status": "ready",
            },
            "contradictions": [contradiction],
        },
    )

    assert result["verified"] is True
    assert result["continuity_claimed"] is False
    assert result["reason"] == "AUDITABLE_RESIDUE_VERIFIED"
    assert result["omitted_contradiction_ids"] == []
    assert result["rewritten_contradiction_ids"] == []
