from copy import deepcopy

import pytest

from holosim.bounded_invariant_breaker import (
    CONTRADICTION,
    DOWNGRADE,
    EQUIVALENT_EXPRESSION,
    IDENTICAL,
    UNKNOWN,
    BoundedInvariantBreakerError,
    build_invariant_artifact,
    compare_invariant_artifacts,
    verify_breaker_receipt,
    verify_invariant_artifact,
)
from holosim.canonical import stable_hash


BASE_CLAIMS = {
    "authority.none": {
        "accepted": False,
        "write_authority": "NONE",
    },
    "lineage.parent_preserved": True,
}


def _artifact(label, expression, claims=None, source=None):
    return build_invariant_artifact(
        artifact_label=label,
        contract_id="contract:compression-ratchet",
        contract_version=1,
        claims=BASE_CLAIMS if claims is None else claims,
        expression=expression,
        provenance={"source": source or label},
    )


def _compare(anchor=None, parent=None, candidate=None):
    return compare_invariant_artifacts(
        anchor=anchor or _artifact("anchor", "Preserve the parent."),
        parent=parent or _artifact("parent", "Preserve the parent."),
        candidate=candidate or _artifact(
            "candidate",
            "Keep the parent.",
        ),
    )


def _rehash_artifact(artifact):
    artifact["artifact_id"] = stable_hash(
        {
            key: value
            for key, value in artifact.items()
            if key != "artifact_id"
        }
    )


def _rehash_receipt(receipt):
    receipt["receipt_id"] = stable_hash(
        {
            key: value
            for key, value in receipt.items()
            if key != "receipt_id"
        }
    )


def test_identical_candidate_is_identical():
    anchor = _artifact("anchor", "Preserve the parent.")
    parent = _artifact("parent", "Preserve the parent.")
    candidate = deepcopy(parent)

    receipt = _compare(anchor, parent, candidate)

    assert receipt["classification"] == IDENTICAL
    assert receipt["promotion_eligible"] is True
    assert receipt["counterexample"] is None


def test_different_expression_with_same_claims_is_equivalent():
    receipt = _compare()

    assert receipt["classification"] == EQUIVALENT_EXPRESSION
    assert receipt["expression_changed"] is True
    assert receipt["candidate_smaller"] is True
    assert receipt["promotion_eligible"] is True


def test_missing_anchor_claim_is_downgrade():
    candidate = _artifact(
        "candidate",
        "No authority.",
        claims={"authority.none": BASE_CLAIMS["authority.none"]},
    )

    receipt = _compare(candidate=candidate)

    assert receipt["classification"] == DOWNGRADE
    assert receipt["missing_claim_ids"] == [
        "lineage.parent_preserved"
    ]
    assert receipt["counterexample"]["kind"] == "MISSING_CLAIM"
    assert receipt["promotion_eligible"] is False


def test_parent_added_claim_cannot_disappear_later():
    parent_claims = {
        **BASE_CLAIMS,
        "replay.protected": True,
    }
    parent = _artifact("parent", "Parent plus replay.", parent_claims)
    candidate = _artifact("candidate", "Original claims.")

    receipt = _compare(parent=parent, candidate=candidate)

    assert receipt["classification"] == DOWNGRADE
    assert receipt["missing_claim_ids"] == ["replay.protected"]


def test_changed_claim_is_contradiction():
    claims = deepcopy(BASE_CLAIMS)
    claims["lineage.parent_preserved"] = False
    candidate = _artifact("candidate", "Rewrite the parent.", claims)

    receipt = _compare(candidate=candidate)

    assert receipt["classification"] == CONTRADICTION
    assert receipt["contradictory_claim_ids"] == [
        "lineage.parent_preserved"
    ]
    assert receipt["counterexample"]["kind"] == "CONTRADICTION"


def test_unverified_added_claim_is_unknown():
    claims = {**BASE_CLAIMS, "new.claim": "unverified"}
    candidate = _artifact("candidate", "Adds a claim.", claims)

    receipt = _compare(candidate=candidate)

    assert receipt["classification"] == UNKNOWN
    assert receipt["added_claim_ids"] == ["new.claim"]
    assert receipt["counterexample"]["kind"] == "UNVERIFIED_ADDITION"


def test_conflicting_baselines_are_unknown():
    parent_claims = deepcopy(BASE_CLAIMS)
    parent_claims["lineage.parent_preserved"] = False
    parent = _artifact("parent", "Conflicting parent.", parent_claims)

    receipt = _compare(parent=parent)

    assert receipt["classification"] == UNKNOWN
    assert receipt["baseline_conflict_ids"] == [
        "lineage.parent_preserved"
    ]
    assert receipt["counterexample"]["kind"] == "BASELINE_CONFLICT"


def test_comparison_does_not_mutate_inputs():
    anchor = _artifact("anchor", "Anchor expression.")
    parent = _artifact("parent", "Parent expression.")
    candidate = _artifact("candidate", "Candidate expression.")
    before = deepcopy((anchor, parent, candidate))

    _compare(anchor, parent, candidate)

    assert (anchor, parent, candidate) == before


def test_rehashed_undeclared_artifact_field_is_rejected():
    artifact = _artifact("candidate", "Candidate expression.")
    artifact["approval"] = "GRANTED"
    _rehash_artifact(artifact)

    result = verify_invariant_artifact(artifact)

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ],
)
def test_rehashed_artifact_authority_escalation_is_rejected(field, value):
    artifact = _artifact("candidate", "Candidate expression.")
    artifact[field] = value
    _rehash_artifact(artifact)

    result = verify_invariant_artifact(artifact)

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("classification", IDENTICAL),
        ("promotion_eligible", True),
    ],
)
def test_rehashed_breaker_receipt_tampering_is_rejected(field, value):
    receipt = _compare(
        candidate=_artifact(
            "candidate",
            "No authority.",
            claims={"authority.none": BASE_CLAIMS["authority.none"]},
        )
    )
    receipt[field] = value
    _rehash_receipt(receipt)

    result = verify_breaker_receipt(receipt)

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_rehashed_undeclared_receipt_field_is_rejected():
    receipt = _compare()
    receipt["approval"] = "GRANTED"
    _rehash_receipt(receipt)

    result = verify_breaker_receipt(receipt)

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]


def test_contract_version_mismatch_fails_closed():
    candidate = build_invariant_artifact(
        artifact_label="candidate",
        contract_id="contract:compression-ratchet",
        contract_version=2,
        claims=BASE_CLAIMS,
        expression="Candidate expression.",
        provenance={"source": "candidate"},
    )

    with pytest.raises(
        BoundedInvariantBreakerError,
        match="share one contract version",
    ):
        _compare(candidate=candidate)
