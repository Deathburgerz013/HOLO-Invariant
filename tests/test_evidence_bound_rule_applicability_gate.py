from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.evidence_bound_rule_applicability_gate import (
    APPLICABLE,
    CONFLICT,
    MISSING_BINDING,
    STALE_LINEAGE,
    UNJUSTIFIED,
    WRONG_SCOPE,
    EvidenceBoundRuleError,
    build_evidence_bound_rule,
    evaluate_rule_applicability,
    validate_evidence_bound_rule,
)


def _evidence():
    return {
        "type": "test_observation_receipt",
        "version": 1,
        "observation": "tests passed",
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }


def _rule(**overrides):
    values = {
        "rule_id": "rule-project-a-tests",
        "scope_type": "project",
        "scope_id": "project-a",
        "source_evidence": _evidence(),
        "parent_rule_id": None,
        "justification": "The retained test evidence supports this bounded rule.",
        "applicability_conditions": ["working_tree_matches_evidence"],
    }
    values.update(overrides)
    return build_evidence_bound_rule(**values)


def _evaluate(rule, **overrides):
    values = {
        "rule": rule,
        "subject_type": "project",
        "subject_id": "project-a",
        "current_rule_id": rule["rule_id"],
        "satisfied_conditions": ["working_tree_matches_evidence"],
        "unresolved_conflict_ids": [],
    }
    values.update(overrides)
    return evaluate_rule_applicability(**values)


def _assert_observational(result, expected):
    assert result["result"] == expected
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"
    assert result["effect_permitted"] is False


def test_matching_evidence_bound_rule_is_observed_as_applicable():
    _assert_observational(_evaluate(_rule()), APPLICABLE)


def test_project_rule_cannot_cross_project_boundary():
    _assert_observational(
        _evaluate(_rule(), subject_id="project-b"),
        WRONG_SCOPE,
    )


def test_session_rule_requires_the_exact_session_subject():
    rule = _rule(
        rule_id="rule-session-a",
        scope_type="session",
        scope_id="session-a",
    )
    _assert_observational(
        _evaluate(rule, subject_type="session", subject_id="session-b"),
        WRONG_SCOPE,
    )


def test_missing_source_evidence_fails_closed():
    rule = _rule(source_evidence=None)
    _assert_observational(_evaluate(rule), MISSING_BINDING)


def test_rehashed_rule_with_modified_evidence_is_rejected():
    forged = deepcopy(_rule())
    forged["source_evidence"]["observation"] = "untested claim"
    body = {key: value for key, value in forged.items() if key != "rule_hash"}
    forged["rule_hash"] = stable_hash(body)
    with pytest.raises(EvidenceBoundRuleError, match="evidence"):
        validate_evidence_bound_rule(forged)


def test_rehashed_rule_with_undeclared_authority_field_is_rejected():
    forged = deepcopy(_rule())
    forged["approval"] = "GRANTED"
    body = {key: value for key, value in forged.items() if key != "rule_hash"}
    forged["rule_hash"] = stable_hash(body)
    with pytest.raises(EvidenceBoundRuleError, match="schema"):
        validate_evidence_bound_rule(forged)


def test_stale_rule_lineage_does_not_apply():
    _assert_observational(
        _evaluate(_rule(), current_rule_id="rule-project-a-successor"),
        STALE_LINEAGE,
    )


def test_unresolved_conflict_stops_application():
    rule = _rule(conflict_ids=["conflict-a"])
    _assert_observational(
        _evaluate(rule, unresolved_conflict_ids=["conflict-a"]),
        CONFLICT,
    )


def test_empty_justification_is_not_applicable():
    _assert_observational(_evaluate(_rule(justification="")), UNJUSTIFIED)


def test_unsatisfied_condition_is_not_applicable():
    _assert_observational(
        _evaluate(_rule(), satisfied_conditions=[]),
        UNJUSTIFIED,
    )


def test_global_scope_is_explicit_but_still_non_authoritative():
    rule = _rule(
        rule_id="rule-global",
        scope_type="global",
        scope_id=None,
        applicability_conditions=[],
    )
    _assert_observational(
        _evaluate(
            rule,
            subject_type="project",
            subject_id="project-b",
            satisfied_conditions=[],
        ),
        APPLICABLE,
    )