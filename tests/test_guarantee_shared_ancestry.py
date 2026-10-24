from holosim.signed_occurrence import build_signed_occurrence
from holosim.guarantee_evidence_binding import evaluate_bound_guarantee_evidence

A, B, SOURCE = "a" * 64, "b" * 64, "c" * 64


def test_shared_receipt_ancestry_is_reported_without_claiming_independence():
    secrets = {
        "source:a": b"a" * 32,
        "source:b": b"b" * 32,
    }

    receipts = [
        {"receipt_hash": A, "evidence_receipt_hashes": [SOURCE]},
        {"receipt_hash": B, "evidence_receipt_hashes": [SOURCE]},
    ]

    occurrences = []

    for n, (source_id, receipt_hash) in enumerate(
        [("source:a", A), ("source:b", B)],
        start=1,
    ):
        occurrences.append(
            build_signed_occurrence(
                source_id=source_id,
                occurrence_id=f"occurrence:{n}",
                payload={
                    "guarantee_id": "shared-ancestry",
                    "session_id": f"session:{n}",
                    "evidence_reference": receipt_hash,
                    "evidence_origin_id": f"origin:{n}",
                    "stance": "SUPPORT",
                },
                observed_at=f"2026-08-04T12:00:{n:02d}Z",
                sequence=n,
                nonce=f"nonce:{n:016d}",
                secret=secrets[source_id],
            )
        )

    result = evaluate_bound_guarantee_evidence(
        guarantee_id="shared-ancestry",
        occurrences=occurrences,
        source_secrets=secrets,
        evidence_receipts=receipts,
    )

    assert result["review"]["decision"] == "REVIEW_ELIGIBLE"
    assert result["ancestry_assessment"]["status"] == "SHARED_DEPENDENCY"
    assert result["ancestry_assessment"]["independent_corroboration_established"] is False
    assert result["ancestry_assessment"]["independence_established"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_unknown_ancestry_does_not_clear_independence_gate():
    secrets = {
        "source:a": b"a" * 32,
        "source:b": b"b" * 32,
    }

    receipts = [
        {"receipt_hash": A, "evidence_receipt_hashes": []},
        {"receipt_hash": B, "evidence_receipt_hashes": []},
    ]

    occurrences = []
    for n, (source_id, receipt_hash) in enumerate(
        [("source:a", A), ("source:b", B)],
        start=1,
    ):
        occurrences.append(
            build_signed_occurrence(
                source_id=source_id,
                occurrence_id=f"unknown-occurrence:{n}",
                payload={
                    "guarantee_id": "unknown-ancestry",
                    "session_id": f"unknown-session:{n}",
                    "evidence_reference": receipt_hash,
                    "evidence_origin_id": f"unknown-origin:{n}",
                    "stance": "SUPPORT",
                },
                observed_at=f"2026-08-04T12:01:{n:02d}Z",
                sequence=n,
                nonce=f"unknown-nonce:{n:016d}",
                secret=secrets[source_id],
            )
        )

    result = evaluate_bound_guarantee_evidence(
        guarantee_id="unknown-ancestry",
        occurrences=occurrences,
        source_secrets=secrets,
        evidence_receipts=receipts,
    )

    assert result["review"]["decision"] == "REVIEW_ELIGIBLE"
    assert result["ancestry_assessment"]["status"] == "UNKNOWN"
    assert result["ancestry_assessment"]["independence_established"] is False
    assert result["ancestry_assessment"]["independent_corroboration_established"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_ancestry_adversarial_boundaries():
    import pytest

    from holosim.canonical import stable_hash
    from holosim.guarantee_evidence_binding import GuaranteeEvidenceBindingError

    secrets = {
        "source:a": b"a" * 32,
        "source:b": b"b" * 32,
    }

    def make_occurrences(second_stance="SUPPORT"):
        result = []
        for n, (source_id, receipt_hash) in enumerate(
            [("source:a", A), ("source:b", B)], start=1
        ):
            result.append(
                build_signed_occurrence(
                    source_id=source_id,
                    occurrence_id=f"adversarial:{n}",
                    payload={
                        "guarantee_id": "adversarial",
                        "session_id": f"session:{n}",
                        "evidence_reference": receipt_hash,
                        "evidence_origin_id": f"origin:{n}",
                        "stance": (
                            "SUPPORT" if n == 1 else second_stance
                        ),
                    },
                    observed_at=f"2026-08-04T12:02:{n:02d}Z",
                    sequence=n,
                    nonce=f"adversarial-nonce:{n:016d}",
                    secret=secrets[source_id],
                )
            )
        return result

    valid = [
        {"receipt_hash": A, "evidence_receipt_hashes": []},
        {"receipt_hash": B, "evidence_receipt_hashes": []},
    ]

    def evaluate(receipts, stance="SUPPORT"):
        return evaluate_bound_guarantee_evidence(
            guarantee_id="adversarial",
            occurrences=make_occurrences(stance),
            source_secrets=secrets,
            evidence_receipts=receipts,
        )

    result = evaluate(valid)
    body = {k: v for k, v in result.items() if k != "binding_hash"}
    assert result["binding_hash"] == stable_hash(body)
    assert result["ancestry_assessment"]["independence_established"] is False

    with pytest.raises(GuaranteeEvidenceBindingError):
        evaluate([valid[0]])

    with pytest.raises(GuaranteeEvidenceBindingError):
        evaluate([
            {"receipt_hash": A, "evidence_receipt_hashes": [B]},
            {"receipt_hash": B, "evidence_receipt_hashes": [A]},
        ])

    with pytest.raises(GuaranteeEvidenceBindingError):
        evaluate([
            valid[0],
            valid[0],
            valid[1],
        ])

    # A contradictory occurrence still requires a declared evidence receipt.
    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="report receipt missing",
    ):
        evaluate([valid[0]], "CONTRADICT")

    # A disconnected cycle invalidates the entire supplied graph.
    C = "c" * 64
    D = "d" * 64
    with pytest.raises(
        GuaranteeEvidenceBindingError,
        match="cycle",
    ):
        evaluate([
            *valid,
            {"receipt_hash": C, "evidence_receipt_hashes": [D]},
            {"receipt_hash": D, "evidence_receipt_hashes": [C]},
        ], "CONTRADICT")

    contradicted = evaluate(valid, "CONTRADICT")
    assert contradicted["review"]["decision"] == "CONTRADICTED"
    assert contradicted["ancestry_assessment"]["status"] == "INSUFFICIENT_SUPPORT"

    # Even without two supporters, supplied ancestry must be validated.
    with pytest.raises(GuaranteeEvidenceBindingError):
        evaluate([
            {"receipt_hash": A, "evidence_receipt_hashes": [B]},
            {"receipt_hash": B, "evidence_receipt_hashes": [A]},
        ], "CONTRADICT")

    with pytest.raises(GuaranteeEvidenceBindingError):
        evaluate([valid[0], valid[0], valid[1]], "CONTRADICT")
    assert (
        contradicted["ancestry_assessment"]
        ["independent_corroboration_established"]
        is False
    )
