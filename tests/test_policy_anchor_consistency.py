"""Regression tests for bounded policy-anchor consistency."""

import pytest

from holosim.policy_anchor_consistency import compare_policy_anchor


ORIGINAL = "a" * 64
ATTACKER = "b" * 64


def assert_no_authority(result):
    assert result.provenance_authenticated is False
    assert result.accepted is False
    assert result.truth_claimed is False
    assert result.write_authority == "NONE"
    assert result.execution_authority == "NONE"
    assert result.trust_root_authority == "NONE"


def test_matching_provisioned_reference():
    result = compare_policy_anchor(
        proposed_sha256=ORIGINAL,
        provisioned_sha256=ORIGINAL,
    )
    assert result.status == "MATCHED"
    assert result.reference_available is True
    assert_no_authority(result)


def test_substituted_policy_against_original_reference():
    result = compare_policy_anchor(
        proposed_sha256=ATTACKER,
        provisioned_sha256=ORIGINAL,
    )
    assert result.status == "MISMATCH"
    assert result.reference_available is True
    assert_no_authority(result)


def test_unavailable_reference_remains_unknown():
    result = compare_policy_anchor(
        proposed_sha256=ORIGINAL,
        provisioned_sha256=None,
    )
    assert result.status == "UNKNOWN"
    assert result.reference_available is False
    assert_no_authority(result)


def test_attacker_controls_both_values():
    result = compare_policy_anchor(
        proposed_sha256=ATTACKER,
        provisioned_sha256=ATTACKER,
    )
    assert result.status == "MATCHED"
    assert result.reference_available is True
    assert_no_authority(result)


@pytest.mark.parametrize(
    "invalid",
    ["", "ABC", "A" * 64, "g" * 64, "a" * 63, 123, True],
)
def test_malformed_proposed_digest_rejected(invalid):
    with pytest.raises(ValueError):
        compare_policy_anchor(
            proposed_sha256=invalid,
            provisioned_sha256=ORIGINAL,
        )


@pytest.mark.parametrize(
    "invalid",
    ["", "ABC", "A" * 64, "g" * 64, "a" * 65, 123, False],
)
def test_malformed_provisioned_digest_rejected(invalid):
    with pytest.raises(ValueError):
        compare_policy_anchor(
            proposed_sha256=ORIGINAL,
            provisioned_sha256=invalid,
        )
