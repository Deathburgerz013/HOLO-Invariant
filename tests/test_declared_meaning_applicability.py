from holosim.declared_meaning_applicability import (
    AMBIGUOUS,
    MULTI_APPLICABLE,
    RESOLVED,
    UNRESOLVED,
    evaluate_declared_meanings,
)


def _meanings():
    return [
        {
            "meaning_id": "heading.title",
            "conditions": ["document_context"],
            "function": "identify_title",
        },
        {
            "meaning_id": "heading.direction",
            "conditions": ["navigation_context"],
            "function": "identify_direction",
        },
    ]


def test_one_applicable_meaning_resolves_without_erasing_alternate():
    result = evaluate_declared_meanings(
        term="heading",
        meanings=_meanings(),
        satisfied_conditions=["document_context"],
    )

    assert result["status"] == RESOLVED
    assert result["applicable_meaning_ids"] == ["heading.title"]
    assert result["preserved_meaning_ids"] == [
        "heading.title",
        "heading.direction",
    ]


def test_multiple_applicable_meanings_are_preserved_together():
    result = evaluate_declared_meanings(
        term="heading",
        meanings=_meanings(),
        satisfied_conditions=[
            "document_context",
            "navigation_context",
        ],
    )

    assert result["status"] == MULTI_APPLICABLE
    assert result["applicable_meaning_ids"] == [
        "heading.title",
        "heading.direction",
    ]
    assert result["applicable_functions"] == [
        "identify_title",
        "identify_direction",
    ]


def test_no_applicable_meaning_is_unresolved_not_guessed():
    result = evaluate_declared_meanings(
        term="heading",
        meanings=_meanings(),
        satisfied_conditions=[],
    )

    assert result["status"] == UNRESOLVED
    assert result["applicable_meaning_ids"] == []
    assert result["preserved_meaning_ids"] == [
        "heading.title",
        "heading.direction",
    ]


def test_uncertain_context_preserves_ambiguity():
    result = evaluate_declared_meanings(
        term="heading",
        meanings=_meanings(),
        satisfied_conditions=["document_context"],
        uncertain_conditions=["navigation_context"],
    )

    assert result["status"] == AMBIGUOUS
    assert result["applicable_meaning_ids"] == ["heading.title"]
    assert result["uncertain_meaning_ids"] == ["heading.direction"]
    assert result["clarification_required"] is True


def test_result_has_no_authority():
    result = evaluate_declared_meanings(
        term="heading",
        meanings=_meanings(),
        satisfied_conditions=["document_context"],
    )

    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

import pytest

from holosim.declared_meaning_applicability import DeclaredMeaningApplicabilityError


def test_meaning_requires_at_least_one_applicability_condition():
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(
            term="heading",
            meanings=[{"meaning_id": "heading.title", "conditions": [], "function": "identify_title"}],
            satisfied_conditions=[],
        )


def test_condition_cannot_be_both_satisfied_and_uncertain():
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(
            term="heading",
            meanings=_meanings(),
            satisfied_conditions=["navigation_context"],
            uncertain_conditions=["navigation_context"],
        )


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_term_fails_closed(bad):
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term=bad, meanings=_meanings(), satisfied_conditions=[])


@pytest.mark.parametrize("field,bad", [("meaning_id", ""), ("meaning_id", " "), ("meaning_id", None), ("function", ""), ("function", " "), ("function", None)])
def test_invalid_meaning_identity_or_function_fails_closed(field, bad):
    meaning = {"meaning_id": "heading.title", "conditions": ["document_context"], "function": "identify_title"}
    meaning[field] = bad
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term="heading", meanings=[meaning], satisfied_conditions=[])


def test_meaning_schema_is_closed():
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term="heading", meanings=[{"meaning_id": "heading.title", "conditions": ["document_context"], "function": "identify_title", "preferred": True}], satisfied_conditions=[])


def test_duplicate_meaning_identity_fails_closed():
    meanings = _meanings()
    meanings[1]["meaning_id"] = meanings[0]["meaning_id"]
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term="heading", meanings=meanings, satisfied_conditions=[])


@pytest.mark.parametrize("bad", ["", " ", None, 1, True])
def test_invalid_declared_condition_fails_closed(bad):
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term="heading", meanings=[{"meaning_id": "heading.title", "conditions": [bad], "function": "identify_title"}], satisfied_conditions=[])


def test_duplicate_condition_within_meaning_fails_closed():
    with pytest.raises(DeclaredMeaningApplicabilityError):
        evaluate_declared_meanings(term="heading", meanings=[{"meaning_id": "heading.title", "conditions": ["document_context", "document_context"], "function": "identify_title"}], satisfied_conditions=[])



def test_all_declared_conditions_are_required_for_one_meaning():
    meanings = [{"meaning_id": "heading.combined", "conditions": ["document_context", "navigation_context"], "function": "identify_combined_heading"}]
    partial = evaluate_declared_meanings(term="heading", meanings=meanings, satisfied_conditions=["document_context"])
    complete = evaluate_declared_meanings(term="heading", meanings=meanings, satisfied_conditions=["document_context", "navigation_context"])
    assert partial["status"] == UNRESOLVED
    assert partial["applicable_meaning_ids"] == []
    assert complete["status"] == RESOLVED
    assert complete["applicable_meaning_ids"] == ["heading.combined"]
