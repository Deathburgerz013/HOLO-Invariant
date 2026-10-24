import pytest

from holosim.bounded_evidence_origins import (
    EvidenceOriginError,
    classify_evidence_origins,
)

A, B, C, D = ("a" * 64, "b" * 64, "c" * 64, "d" * 64)


def receipt(identity, *dependencies):
    return {
        "receipt_hash": identity,
        "evidence_receipt_hashes": list(dependencies),
    }


def test_shared_missing_origin():
    result = classify_evidence_origins(
        [receipt(B, A), receipt(C, A)], B, C
    )
    assert result["status"] == "SHARED_DEPENDENCY"
    assert result["shared_dependency_hashes"] == [A]
    assert result["missing_dependency_hashes"] == [A]


def test_undeclared_origins_remain_unknown():
    result = classify_evidence_origins(
        [receipt(B), receipt(C)], B, C
    )
    assert result["status"] == "UNKNOWN"
    assert result["independence_established"] is False


def test_distinct_origins_do_not_prove_independence():
    result = classify_evidence_origins(
        [receipt(B, A), receipt(C, D)], B, C
    )
    assert result["status"] == "UNKNOWN"
    assert result["missing_dependency_hashes"] == [A, D]


def test_transitive_shared_origin():
    result = classify_evidence_origins(
        [receipt(A), receipt(D, A), receipt(B, D), receipt(C, A)],
        B, C,
    )
    assert result["status"] == "SHARED_DEPENDENCY"
    assert result["shared_dependency_hashes"] == [A]


def test_cycle_rejected():
    with pytest.raises(EvidenceOriginError, match="cycle"):
        classify_evidence_origins(
            [receipt(B, C), receipt(C, B)], B, C
        )


def test_missing_report_rejected():
    with pytest.raises(EvidenceOriginError, match="report receipt missing"):
        classify_evidence_origins([receipt(B)], B, C)


def test_duplicate_receipt_rejected():
    with pytest.raises(EvidenceOriginError):
        classify_evidence_origins(
            [receipt(B), receipt(B), receipt(C)], B, C
        )


def test_no_authority():
    result = classify_evidence_origins(
        [receipt(B, A), receipt(C, A)], B, C
    )
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

def test_unrelated_dependency_cycle_rejected():
    E = "e" * 64
    F = "f" * 64

    with pytest.raises(EvidenceOriginError, match="cycle"):
        classify_evidence_origins(
            [
                receipt(B),
                receipt(C),
                receipt(E, F),
                receipt(F, E),
            ],
            B,
            C,
        )


def test_transitive_missing_origin_detected():
    E = "e" * 64

    result = classify_evidence_origins(
        [
            receipt(B, D),
            receipt(C, E),
            receipt(D, A),
            receipt(E, A),
        ],
        B,
        C,
    )

    assert result["status"] == "SHARED_DEPENDENCY"
    assert result["shared_dependency_hashes"] == [A]
    assert result["missing_dependency_hashes"] == [A]


def test_boolean_receipt_hash_rejected():
    with pytest.raises(EvidenceOriginError):
        classify_evidence_origins(
            [receipt(B), receipt(C)],
            True,
            C,
        )


def test_empty_receipt_graph_rejected():
    with pytest.raises(EvidenceOriginError):
        classify_evidence_origins([], B, C)

@pytest.mark.parametrize(
    "dependencies",
    [
        {A: True},
        [A, A],
        [A] * 10001,
        (value for value in [A]),
    ],
)
def test_malformed_dependencies_rejected(dependencies):
    with pytest.raises(EvidenceOriginError):
        classify_evidence_origins(
            [
                {
                    "receipt_hash": B,
                    "evidence_receipt_hashes": dependencies,
                },
                receipt(C),
            ],
            B,
            C,
        )


def test_unknown_receipt_field_rejected():
    with pytest.raises(EvidenceOriginError, match="unknown"):
        classify_evidence_origins(
            [
                {
                    "receipt_hash": B,
                    "unexpected_dependencies": [A],
                },
                receipt(C),
            ],
            B,
            C,
        )


def test_raw_dependency_budget_enforced():
    with pytest.raises(EvidenceOriginError, match="budget"):
        classify_evidence_origins(
            [
                {
                    "receipt_hash": B,
                    "evidence_receipt_hashes": [A] * 10001,
                },
                receipt(C),
            ],
            B,
            C,
        )


def test_maximum_receipt_chain_without_recursion():
    def h(number):
        return f"{number:064x}"

    receipts = [
        {
            "receipt_hash": h(i),
            "evidence_receipt_hashes": [h(i - 1)] if i > 1 else [],
        }
        for i in range(1, 1001)
    ]

    result = classify_evidence_origins(
        receipts,
        h(1000),
        h(999),
    )

    assert result["status"] == "SHARED_DEPENDENCY"
    assert len(result["shared_dependency_hashes"]) == 998
    assert result["truth_claimed"] is False
    assert result["independence_established"] is False
