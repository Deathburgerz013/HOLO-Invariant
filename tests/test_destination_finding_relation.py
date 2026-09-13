import pytest

from holosim.spine_protocol import (
    SpineStructureError,
    compare_destination_findings,
    evaluate_destination_compatibility,
)


def test_same_profile_findings_expose_requirement_level_difference():
    profile = {
        "destination_id": "observer-reconstruction-contract",
        "profile_version": 1,
        "profile_hash": "fixture-observer-contract-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXACT_VALUE",
                "source_path": "claim",
                "expected": "SUPPORTED",
            }
        ],
    }

    observer_a = {
        "source_id": "observer-a",
        "source_version": 1,
        "source_hash": "observer-a-v1",
        "fields": {"claim": "SUPPORTED"},
    }
    observer_b = {
        "source_id": "observer-b",
        "source_version": 1,
        "source_hash": "observer-b-v1",
        "fields": {"claim": "REJECTED"},
    }

    finding_a = evaluate_destination_compatibility(observer_a, profile)
    finding_b = evaluate_destination_compatibility(observer_b, profile)

    relation = compare_destination_findings(finding_a, observer_a, finding_b, observer_b, profile)

    assert relation["different_requirements"] == ["R1"]
    assert relation["same_partition_state"] is False


def test_different_destination_profiles_fail_closed():
    profile_a = {
        "destination_id": "observer-contract-a",
        "profile_version": 1,
        "profile_hash": "profile-a-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXACT_VALUE",
                "source_path": "claim",
                "expected": "SUPPORTED",
            }
        ],
    }
    profile_b = {
        "destination_id": "observer-contract-b",
        "profile_version": 1,
        "profile_hash": "profile-b-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXACT_VALUE",
                "source_path": "claim",
                "expected": "SUPPORTED",
            }
        ],
    }
    source = {
        "source_id": "observer-a",
        "source_version": 1,
        "source_hash": "observer-a-v1",
        "fields": {"claim": "SUPPORTED"},
    }

    left = evaluate_destination_compatibility(source, profile_a)
    right = evaluate_destination_compatibility(source, profile_b)

    with pytest.raises(SpineStructureError):
        compare_destination_findings(
            left, source, right, source, profile_a
        )


def test_same_partition_state_does_not_imply_compatibility():
    profile = {
        "destination_id": "observer-contract",
        "profile_version": 1,
        "profile_hash": "observer-contract-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXACT_VALUE",
                "source_path": "claim",
                "expected": "SUPPORTED",
            }
        ],
    }
    observer_a = {
        "source_id": "observer-a",
        "source_version": 1,
        "source_hash": "observer-a-v1",
        "fields": {"claim": "REJECTED"},
    }
    observer_b = {
        "source_id": "observer-b",
        "source_version": 1,
        "source_hash": "observer-b-v1",
        "fields": {"claim": "REJECTED"},
    }

    finding_a = evaluate_destination_compatibility(observer_a, profile)
    finding_b = evaluate_destination_compatibility(observer_b, profile)
    relation = compare_destination_findings(finding_a, observer_a, finding_b, observer_b, profile)

    assert finding_a["compatible"] is False
    assert finding_b["compatible"] is False
    assert relation["same_requirements"] == ["R1"]
    assert relation["different_requirements"] == []
    assert relation["same_partition_state"] is True
    assert relation["accepted"] is False
    assert relation["write_authority"] == "NONE"


def test_rehashed_semantic_forgery_cannot_be_compared():
    import hashlib
    import json

    profile = {
        "destination_id": "observer-contract",
        "profile_version": 1,
        "profile_hash": "observer-contract-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXACT_VALUE",
                "source_path": "claim",
                "expected": "SUPPORTED",
            }
        ],
    }
    observer_a = {
        "source_id": "observer-a",
        "source_version": 1,
        "source_hash": "observer-a-v1",
        "fields": {"claim": "SUPPORTED"},
    }
    observer_b = {
        "source_id": "observer-b",
        "source_version": 1,
        "source_hash": "observer-b-v1",
        "fields": {"claim": "SUPPORTED"},
    }

    finding_a = evaluate_destination_compatibility(observer_a, profile)
    finding_b = evaluate_destination_compatibility(observer_b, profile)

    finding_a["verified_requirements"] = []
    finding_a["conflicts"] = ["R1"]
    finding_a["compatible"] = False
    body = dict(finding_a)
    body.pop("finding_hash", None)
    canonical = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    finding_a["finding_hash"] = hashlib.sha256(canonical).hexdigest()

    with pytest.raises(SpineStructureError, match="current evaluation"):
        compare_destination_findings(
            finding_a, observer_a, finding_b, observer_b, profile
        )
