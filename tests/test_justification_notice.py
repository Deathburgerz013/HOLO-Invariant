from copy import deepcopy

import pytest

from holosim.justification_notice import (
    JustificationNoticeError,
    build_justification_notice,
    validate_justification_notice,
)


HASH_A = "a" * 64
HASH_B = "b" * 64


def kwargs():
    return {
        "notice_id": "notice:rule-1:v1",
        "parent_notice_hash": None,
        "target": {
            "target_id": "rule-1",
            "target_type": "evidence_bound_rule",
            "target_sha256": HASH_A,
        },
        "observed_failure": {
            "failure_id": "why-loss",
            "observation": "The rule survives while its selection rationale is absent.",
        },
        "evidence_bindings": [
            {"evidence_id": "test:why-loss", "evidence_sha256": HASH_B},
        ],
        "selected_change": {
            "operation": "add justification notice",
            "changes_target": False,
        },
        "why_selected": "Preserve the reason without rewriting the target or prior notice.",
        "rejected_alternatives": [
            {
                "alternative_id": "embed-free-text-only",
                "description": "Store an unbound explanation.",
                "rejection_reason": "It can drift away from its evidence and target version.",
                "evidence_ids": ["test:why-loss"],
            }
        ],
        "declared_scope": {"repository": "HOLO-Invariant", "rule_id": "rule-1"},
        "established_findings": [
            {"finding": "The current rule schema has one justification string."}
        ],
        "unknowns": [
            {
                "unknown_id": "future-evidence",
                "statement": "Whether later evidence changes the selected rationale.",
                "status": "NOT_YET_KNOWN",
                "method_boundary": None,
                "resolution_condition": "A contradictory verified receipt is added.",
            },
            {
                "unknown_id": "private-intent",
                "statement": "A contributor's unexpressed private intent.",
                "status": "UNDETERMINABLE_UNDER_DECLARED_METHOD",
                "method_boundary": "The method observes records, not private mental state.",
                "resolution_condition": None,
            },
        ],
        "reopen_conditions": [
            "The target hash changes.",
            "New evidence contradicts the rationale.",
        ],
        "contributors": [
            {"contributor_id": "Canyon", "role": "observed failure"},
            {"contributor_id": "Sim", "role": "encoded bounded contract"},
        ],
    }


def test_notice_preserves_why_unknowns_alternatives_and_reopening():
    notice = build_justification_notice(**kwargs())
    assert notice["epistemic_status"] == "SUPPORTED_WITH_DECLARED_UNKNOWNS"
    assert notice["why_selected"]
    assert notice["rejected_alternatives"][0]["rejection_reason"]
    assert {item["status"] for item in notice["unknowns"]} == {
        "NOT_YET_KNOWN",
        "UNDETERMINABLE_UNDER_DECLARED_METHOD",
    }
    assert notice["truth_claimed"] is False
    assert notice["change_approved"] is False
    assert notice["write_authority"] == "NONE"
    assert validate_justification_notice(notice) is True


def test_changed_target_version_changes_notice_identity():
    first = build_justification_notice(**kwargs())
    changed = kwargs()
    changed["target"]["target_sha256"] = HASH_B
    second = build_justification_notice(**changed)
    assert first["notice_hash"] != second["notice_hash"]


def test_successor_notice_preserves_parent_hash():
    first = build_justification_notice(**kwargs())
    successor = kwargs()
    successor["notice_id"] = "notice:rule-1:v2"
    successor["parent_notice_hash"] = first["notice_hash"]
    second = build_justification_notice(**successor)
    assert second["parent_notice_hash"] == first["notice_hash"]


def test_duplicate_evidence_binding_fails_closed():
    values = kwargs()
    values["evidence_bindings"].append(deepcopy(values["evidence_bindings"][0]))
    with pytest.raises(JustificationNoticeError, match="duplicate evidence_id"):
        build_justification_notice(**values)


def test_not_yet_known_requires_resolution_condition():
    values = kwargs()
    values["unknowns"][0]["resolution_condition"] = None
    with pytest.raises(JustificationNoticeError, match="requires a resolution_condition"):
        build_justification_notice(**values)


def test_undeterminable_requires_declared_method_boundary():
    values = kwargs()
    values["unknowns"][1]["method_boundary"] = None
    with pytest.raises(JustificationNoticeError, match="requires a method_boundary"):
        build_justification_notice(**values)


def test_absolute_unknowability_cannot_be_declared():
    values = kwargs()
    values["unknowns"][1]["status"] = "ABSOLUTELY_UNKNOWABLE"
    with pytest.raises(JustificationNoticeError, match="status must be one of"):
        build_justification_notice(**values)


def test_unbound_alternative_evidence_fails_closed():
    values = kwargs()
    values["rejected_alternatives"][0]["evidence_ids"] = ["missing:evidence"]
    with pytest.raises(JustificationNoticeError, match="unbound evidence"):
        build_justification_notice(**values)


def test_tampered_notice_fails_closed():
    notice = build_justification_notice(**kwargs())
    notice["why_selected"] = "Rewritten after hashing."
    with pytest.raises(JustificationNoticeError, match="canonical identity"):
        validate_justification_notice(notice)
