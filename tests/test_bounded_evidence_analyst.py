from __future__ import annotations

from copy import deepcopy

import pytest

from holosim.bounded_evidence_analyst import (
    BoundedEvidenceAnalystError,
    build_evidence_analysis_receipt,
    verify_evidence_analysis_receipt,
)
from holosim.canonical import stable_hash


def _evidence(evidence_id, marker, availability="VERIFIED"):
    return {
        "evidence_id": evidence_id,
        "content_sha256": stable_hash({"marker": marker}),
        "source_reference": f"fixture:{evidence_id}",
        "availability": availability,
    }


def _assessment(evidence_id, relation, disposition="INCLUDED"):
    return {
        "evidence_id": evidence_id,
        "disposition": disposition,
        "relation": relation,
        "rationale": f"{disposition.lower()} as {relation.lower()}",
    }


def _inputs(relations=("SUPPORTS", "NEUTRAL")):
    return {
        "analysis_id": "analysis.v1",
        "scope": "bounded fixture",
        "method": {
            "method_id": "declared-relation-aggregation",
            "method_version": "v1",
            "description": "derive status from complete declared evidence relations",
        },
        "evidence": [_evidence("e1", "one"), _evidence("e2", "two")],
        "findings": [{
            "finding_id": "f1",
            "statement": "the fixture supports the bounded claim",
            "evidence_assessments": [
                _assessment("e1", relations[0]),
                _assessment("e2", relations[1]),
            ],
        }],
    }


def _receipt(relations=("SUPPORTS", "NEUTRAL")):
    return build_evidence_analysis_receipt(**_inputs(relations))


def _result(receipt):
    return receipt["finding_results"][0]


def test_support_without_contradiction_or_unknown_is_supported() -> None:
    receipt = _receipt()
    result = _result(receipt)
    assert result["status"] == "SUPPORTED"
    assert result["supporting_evidence_ids"] == ["e1"]
    assert result["neutral_evidence_ids"] == ["e2"]
    assert verify_evidence_analysis_receipt(receipt) is True


def test_contradiction_without_support_or_unknown_is_contradicted() -> None:
    result = _result(_receipt(("CONTRADICTS", "NEUTRAL")))
    assert result["status"] == "CONTRADICTED"
    assert result["contradicting_evidence_ids"] == ["e1"]


def test_conflicting_evidence_remains_unresolved() -> None:
    result = _result(_receipt(("SUPPORTS", "CONTRADICTS")))
    assert result["status"] == "UNRESOLVED"
    assert result["status_reason"] == "CONFLICTING_EVIDENCE"
    assert result["supporting_evidence_ids"] == ["e1"]
    assert result["contradicting_evidence_ids"] == ["e2"]


def test_unknown_evidence_prevents_supported_promotion() -> None:
    result = _result(_receipt(("SUPPORTS", "UNKNOWN")))
    assert result["status"] == "UNRESOLVED"
    assert result["status_reason"] == "UNKNOWN_EVIDENCE_REMAINS"


def test_neutral_only_evidence_is_unresolved() -> None:
    result = _result(_receipt(("NEUTRAL", "NEUTRAL")))
    assert result["status"] == "UNRESOLVED"
    assert result["status_reason"] == "NO_DIRECTIONAL_EVIDENCE"


def test_every_evidence_item_must_be_accounted_for() -> None:
    inputs = _inputs()
    inputs["findings"][0]["evidence_assessments"] = [
        _assessment("e1", "SUPPORTS")
    ]
    with pytest.raises(BoundedEvidenceAnalystError, match="exactly once"):
        build_evidence_analysis_receipt(**inputs)


def test_excluded_evidence_is_preserved_with_reason() -> None:
    inputs = _inputs()
    inputs["findings"][0]["evidence_assessments"][1] = _assessment(
        "e2", "NOT_APPLIED", "EXCLUDED"
    )
    receipt = build_evidence_analysis_receipt(**inputs)
    assert _result(receipt)["excluded_evidence_ids"] == ["e2"]
    assessment = receipt["findings"][0]["evidence_assessments"][1]
    assert assessment["rationale"]


def test_excluded_evidence_cannot_secretly_support() -> None:
    inputs = _inputs()
    inputs["findings"][0]["evidence_assessments"][1] = _assessment(
        "e2", "SUPPORTS", "EXCLUDED"
    )
    with pytest.raises(BoundedEvidenceAnalystError, match="NOT_APPLIED"):
        build_evidence_analysis_receipt(**inputs)


def test_unavailable_evidence_must_remain_visible_as_unknown() -> None:
    inputs = _inputs()
    inputs["evidence"][1]["availability"] = "UNAVAILABLE"
    inputs["findings"][0]["evidence_assessments"][1] = _assessment("e2", "UNKNOWN")
    receipt = build_evidence_analysis_receipt(**inputs)
    assert _result(receipt)["status"] == "UNRESOLVED"
    inputs["findings"][0]["evidence_assessments"][1] = _assessment(
        "e2", "NOT_APPLIED", "EXCLUDED"
    )
    with pytest.raises(BoundedEvidenceAnalystError, match="must remain included"):
        build_evidence_analysis_receipt(**inputs)


def test_duplicate_evidence_id_is_rejected() -> None:
    inputs = _inputs()
    inputs["evidence"][1]["evidence_id"] = "e1"
    with pytest.raises(BoundedEvidenceAnalystError, match="must be unique"):
        build_evidence_analysis_receipt(**inputs)


def test_receipt_is_deterministic_under_reordered_inputs() -> None:
    first = _inputs()
    second = deepcopy(first)
    second["evidence"].reverse()
    second["findings"][0]["evidence_assessments"].reverse()
    assert build_evidence_analysis_receipt(**first) == (
        build_evidence_analysis_receipt(**second)
    )


def test_inputs_are_isolated_from_later_mutation() -> None:
    inputs = _inputs()
    receipt = build_evidence_analysis_receipt(**inputs)
    inputs["method"]["description"] = "changed"
    inputs["evidence"][0]["source_reference"] = "changed"
    assert receipt == _receipt()


def test_analysis_never_claims_execution_truth_recommendation_or_authority() -> None:
    receipt = _receipt()
    assert receipt["analysis_status"] == "DERIVED_FROM_DECLARED_RELATIONS"
    assert receipt["method_executed"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["recommended_action"] is None
    assert receipt["accepted"] is False
    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"


def test_hash_tampering_is_rejected() -> None:
    receipt = _receipt()
    receipt["finding_results"][0]["status"] = "CONTRADICTED"
    with pytest.raises(BoundedEvidenceAnalystError, match="hash mismatch"):
        verify_evidence_analysis_receipt(receipt)


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("finding_results", 0, "status"), "CONTRADICTED"),
        (("method_executed",), True),
        (("truth_claimed",), True),
        (("recommended_action",), "ship it"),
        (("write_authority",), "ANALYST"),
    ],
)
def test_rehashed_semantic_forgery_is_rejected(path, value) -> None:
    receipt = _receipt()
    target = receipt
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value
    body = {key: item for key, item in receipt.items() if key != "receipt_hash"}
    receipt["receipt_hash"] = stable_hash(body)
    with pytest.raises(BoundedEvidenceAnalystError, match="internally inconsistent"):
        verify_evidence_analysis_receipt(receipt)


def test_extra_authority_field_is_rejected() -> None:
    receipt = _receipt()
    receipt["approval_authority"] = "ANALYST"
    with pytest.raises(BoundedEvidenceAnalystError, match="fields mismatch"):
        verify_evidence_analysis_receipt(receipt)
