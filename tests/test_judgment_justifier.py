from __future__ import annotations

import pytest

from holosim.judgment_justifier import (
    JudgmentJustifierError,
    evaluate_judgment_justification,
)


def _base_kwargs() -> dict[str, object]:
    return {
        "judgment_id": "gap-001",
        "conclusion": {"gap": "missing validated function"},
        "reference_state": "repo@main",
        "evidence_references": ["test@coverage"],
        "rule_references": ["rule@find-unresolved-gap"],
        "comparison_status": "SUPPORTED",
        "uncertainty": "LOW",
        "unresolved_conflicts": [],
    }


def test_supported_judgment_is_justified_without_claiming_truth() -> None:
    result = evaluate_judgment_justification(**_base_kwargs())

    assert result["status"] == "JUSTIFIED"
    assert result["truth_claimed"] is False
    assert result["acceptance_granted"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"


def test_missing_evidence_is_unjustified() -> None:
    kwargs = _base_kwargs()
    kwargs["evidence_references"] = []

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "UNJUSTIFIED"
    assert result["missing_support"] == ["evidence"]


def test_missing_rule_reference_is_unjustified() -> None:
    kwargs = _base_kwargs()
    kwargs["rule_references"] = []

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "UNJUSTIFIED"
    assert result["missing_support"] == ["rule_or_invariant"]


def test_unresolved_comparison_does_not_become_justified() -> None:
    kwargs = _base_kwargs()
    kwargs["comparison_status"] = "UNRESOLVED"

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "UNRESOLVED"


def test_declared_conflict_stabilizes_as_conflicted() -> None:
    kwargs = _base_kwargs()
    kwargs["unresolved_conflicts"] = [
        {"id": "conflict-1", "reference": "evidence@opposed"}
    ]

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "CONFLICTED"


def test_high_uncertainty_does_not_become_justified() -> None:
    kwargs = _base_kwargs()
    kwargs["uncertainty"] = "HIGH"

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "UNCERTAIN"


def test_medium_uncertainty_can_remain_justified_when_support_is_explicit() -> None:
    kwargs = _base_kwargs()
    kwargs["uncertainty"] = "MEDIUM"

    result = evaluate_judgment_justification(**kwargs)

    assert result["status"] == "JUSTIFIED"


def test_duplicate_evidence_reference_fails_closed() -> None:
    kwargs = _base_kwargs()
    kwargs["evidence_references"] = ["evidence@1", "evidence@1"]

    with pytest.raises(JudgmentJustifierError, match="duplicate evidence_reference"):
        evaluate_judgment_justification(**kwargs)


def test_duplicate_conflict_id_fails_closed() -> None:
    kwargs = _base_kwargs()
    kwargs["unresolved_conflicts"] = [
        {"id": "conflict-1"},
        {"id": "conflict-1"},
    ]

    with pytest.raises(JudgmentJustifierError, match="duplicate unresolved conflict id"):
        evaluate_judgment_justification(**kwargs)


def test_nonfinite_conclusion_fails_closed() -> None:
    kwargs = _base_kwargs()
    kwargs["conclusion"] = {"score": float("inf")}

    with pytest.raises(JudgmentJustifierError, match="finite, acyclic"):
        evaluate_judgment_justification(**kwargs)


def test_hash_is_deterministic() -> None:
    first = evaluate_judgment_justification(**_base_kwargs())
    second = evaluate_judgment_justification(**_base_kwargs())

    assert first == second
    assert len(first["justification_hash"]) == 64
