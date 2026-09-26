from copy import deepcopy

import pytest

from holosim.bounded_contributor_attribution import (
    BoundedContributorAttributionError,
    build_bounded_contributor_attribution,
    validate_bounded_contributor_attribution,
)


def _contribution():
    return {
        "kind": "observed_failure",
        "claim": "priority derivation rejected intact applicability",
        "source_ref": "test://bounded-priority-derivation",
    }


def test_attribution_preserves_contributor_role_and_exact_contribution():
    receipt = build_bounded_contributor_attribution(
        contributor_id="Canyon",
        role="observed failure",
        contribution=_contribution(),
    )

    assert receipt["contributor_id"] == "Canyon"
    assert receipt["role"] == "observed failure"
    assert receipt["contribution"] == _contribution()
    assert len(receipt["contribution_hash"]) == 64
    assert len(receipt["attribution_hash"]) == 64
    assert receipt["attribution_claimed"] is True

    validate_bounded_contributor_attribution(receipt)


def test_attribution_grants_no_broader_claims_or_authority():
    receipt = build_bounded_contributor_attribution(
        contributor_id="Sim",
        role="encoded bounded contract",
        contribution=_contribution(),
    )

    assert receipt["truth_claimed"] is False
    assert receipt["authorship_claimed"] is False
    assert receipt["ownership_claimed"] is False
    assert receipt["currentness_claimed"] is False
    assert receipt["accepted"] is False

    assert receipt["selection_authority"] == "NONE"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["promotion_authority"] == "NONE"


def test_same_contribution_can_credit_different_declared_roles_without_ownership():
    observation = build_bounded_contributor_attribution(
        contributor_id="Canyon",
        role="observed failure",
        contribution=_contribution(),
    )
    encoding = build_bounded_contributor_attribution(
        contributor_id="Sim",
        role="encoded bounded contract",
        contribution=_contribution(),
    )

    assert observation["contribution_hash"] == encoding["contribution_hash"]
    assert observation["attribution_hash"] != encoding["attribution_hash"]

    assert observation["ownership_claimed"] is False
    assert encoding["ownership_claimed"] is False


def test_tampered_contribution_breaks_attribution_identity():
    receipt = build_bounded_contributor_attribution(
        contributor_id="Canyon",
        role="observed failure",
        contribution=_contribution(),
    )
    tampered = deepcopy(receipt)
    tampered["contribution"]["claim"] = "different claim"

    with pytest.raises(
        BoundedContributorAttributionError,
        match="bounded attribution",
    ):
        validate_bounded_contributor_attribution(tampered)


def test_tampered_contributor_breaks_attribution_identity():
    receipt = build_bounded_contributor_attribution(
        contributor_id="Canyon",
        role="observed failure",
        contribution=_contribution(),
    )
    tampered = deepcopy(receipt)
    tampered["contributor_id"] = "SomeoneElse"

    with pytest.raises(
        BoundedContributorAttributionError,
        match="bounded attribution",
    ):
        validate_bounded_contributor_attribution(tampered)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("truth_claimed", True),
        ("authorship_claimed", True),
        ("ownership_claimed", True),
        ("currentness_claimed", True),
        ("accepted", True),
        ("selection_authority", "GRANTED"),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
        ("promotion_authority", "GRANTED"),
    ],
)
def test_attribution_cannot_be_mutated_into_claim_or_authority(field, value):
    receipt = build_bounded_contributor_attribution(
        contributor_id="Canyon",
        role="observed failure",
        contribution=_contribution(),
    )
    tampered = deepcopy(receipt)
    tampered[field] = value

    with pytest.raises(
        BoundedContributorAttributionError,
        match="bounded attribution",
    ):
        validate_bounded_contributor_attribution(tampered)


@pytest.mark.parametrize(
    ("contributor_id", "role"),
    [
        ("", "observed failure"),
        ("   ", "observed failure"),
        ("Canyon", ""),
        ("Canyon", "   "),
    ],
)
def test_empty_identity_or_role_is_rejected(contributor_id, role):
    with pytest.raises(
        BoundedContributorAttributionError,
        match="must be nonempty text",
    ):
        build_bounded_contributor_attribution(
            contributor_id=contributor_id,
            role=role,
            contribution=_contribution(),
        )