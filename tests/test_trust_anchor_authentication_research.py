"""Research tests for verifier-held policy reference binding."""

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


@pytest.mark.parametrize(
    ("proposed", "expected"),
    [
        (ORIGINAL, "MATCHED"),
        (ATTACKER, "MISMATCH"),
    ],
)
def test_verifier_held_reference(proposed, expected):
    reference = ORIGINAL

    result = compare_policy_anchor(
        proposed_sha256=proposed,
        provisioned_sha256=reference,
    )

    assert result.status == expected
    assert_no_authority(result)


def test_attacker_supplied_replacement_matches_but_is_not_authenticated():
    result = compare_policy_anchor(
        proposed_sha256=ATTACKER,
        provisioned_sha256=ATTACKER,
    )

    assert result.status == "MATCHED"
    assert_no_authority(result)


def test_missing_reference_fails_closed():
    result = compare_policy_anchor(
        proposed_sha256=ORIGINAL,
        provisioned_sha256=None,
    )

    assert result.status == "UNKNOWN"
    assert_no_authority(result)