from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.compression_observer_coverage import (
    evaluate_compression_observer_coverage,
)
from holosim.evidence_bound_reproduction import (
    build_evidence_bound_reproduction,
)
from holosim.bounded_obsolescence_researcher import (
    BoundedObsolescenceResearchError,
    build_bounded_obsolescence_research,
    validate_bounded_obsolescence_research,
)


def reproduction(*, preserved=True, removed=True):
    return build_evidence_bound_reproduction(
        reference="bounded-obsolescence-test",
        baseline_substrate=[{"id": "legacy"}] if removed else [],
        candidate_substrate=[],
        baseline_outcomes=[{"id": "result", "value": True}],
        candidate_outcomes=[
            {"id": "result", "value": preserved}
        ],
    )


def coverage(*, complete=True):
    return evaluate_compression_observer_coverage(
        required_observations=["result"],
        declared_observers=["result"] if complete else ["other"],
        observer_identities={
            ("result" if complete else "other"): "a" * 64
        },
        requirement_basis_ref="test-requirements",
    )


def research(*, preserved=True, removed=True, complete=True):
    return build_bounded_obsolescence_research(
        reproduction_receipt=reproduction(
            preserved=preserved, removed=removed
        ),
        coverage_receipt=coverage(complete=complete),
    )


def test_supported_is_bounded_and_read_only():
    receipt = research()
    assert receipt["status"] == "SUPPORTED"
    assert receipt["observed_redundancy_candidates"] == ["legacy"]
    assert receipt["dependency_freshness"] == "UNVERIFIED"
    assert receipt["obsolete_claimed"] is False
    assert receipt["deletion_authorized"] is False
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert validate_bounded_obsolescence_research(receipt) is True


def test_regression_is_contradicted():
    receipt = research(preserved=False)
    assert receipt["status"] == "CONTRADICTED"
    assert receipt["observed_redundancy_candidates"] == []
    assert validate_bounded_obsolescence_research(receipt)


def test_incomplete_coverage_is_unavailable():
    receipt = research(complete=False)
    assert receipt["status"] == "UNAVAILABLE"
    assert "OBSERVER_COVERAGE_INCOMPLETE" in receipt["limitations"]


def test_missing_coverage_is_unavailable():
    receipt = build_bounded_obsolescence_research(
        reproduction_receipt=reproduction(),
        coverage_receipt=None,
    )
    assert receipt["status"] == "UNAVAILABLE"
    assert validate_bounded_obsolescence_research(receipt)


def test_no_removed_substrate_is_unavailable():
    receipt = research(removed=False)
    assert receipt["status"] == "UNAVAILABLE"
    assert receipt["observed_redundancy_candidates"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("status", "SUPPORTED"),
        ("accepted", True),
        ("truth_claimed", True),
        ("obsolete_claimed", True),
        ("deletion_authorized", True),
        ("write_authority", "GRANTED"),
        ("dependency_freshness", "VERIFIED"),
    ],
)
def test_forged_fields_fail_even_with_new_hash(field, value):
    receipt = research(preserved=False)
    receipt[field] = value
    receipt["research_hash"] = stable_hash({
        k: v for k, v in receipt.items() if k != "research_hash"
    })
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_missing_or_extra_fields_fail():
    receipt = research()
    missing = deepcopy(receipt)
    del missing["limitations"]
    extra = deepcopy(receipt)
    extra["permission"] = "DELETE"
    for forged in (missing, extra):
        with pytest.raises(BoundedObsolescenceResearchError):
            validate_bounded_obsolescence_research(forged)


def test_changed_reproduction_evidence_fails():
    receipt = research()
    receipt["reproduction_receipt"]["inputs"]["candidate_outcomes"][0][
        "value"
    ] = False
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_changed_coverage_evidence_fails():
    receipt = research()
    receipt["coverage_receipt"]["coverage_complete"] = False
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_coverage_bool_integer_confusion_fails():
    receipt = research()
    receipt["coverage_receipt"]["coverage_complete"] = 1
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_invalid_nested_json_fails():
    receipt = research()
    receipt["limitations"] = [{"invalid": {1}}]
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_cyclic_nested_evidence_fails():
    receipt = research()
    cycle = {}
    cycle["self"] = cycle
    receipt["reproduction_receipt"]["reproduction"]["status"] = cycle
    with pytest.raises(BoundedObsolescenceResearchError):
        validate_bounded_obsolescence_research(receipt)


def test_unrelated_complete_coverage_cannot_support_redundancy():
    repro = reproduction()
    unrelated_coverage = evaluate_compression_observer_coverage(
        required_observations=["unrelated"],
        declared_observers=["unrelated"],
        observer_identities={"unrelated": "a" * 64},
        requirement_basis_ref="unrelated-requirements",
    )

    assert unrelated_coverage["coverage_complete"] is True

    receipt = build_bounded_obsolescence_research(
        reproduction_receipt=repro,
        coverage_receipt=unrelated_coverage,
    )

    assert receipt["status"] == "UNAVAILABLE"
    assert "COVERAGE_OUTCOME_MISMATCH" in receipt["limitations"]
    assert receipt["obsolete_claimed"] is False
    assert receipt["deletion_authorized"] is False
    assert validate_bounded_obsolescence_research(receipt) is True
