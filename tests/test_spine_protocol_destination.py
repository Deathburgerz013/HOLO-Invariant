from copy import deepcopy
import hashlib
import json

import pytest

from holosim.spine_protocol import (
    SpineStructureError,
    check_destination_finding_current,
    evaluate_destination_compatibility,
)


def rehash_finding(finding):
    body = dict(finding)
    body.pop("finding_hash", None)
    canonical = json.dumps(
        body, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    finding["finding_hash"] = hashlib.sha256(canonical).hexdigest()


@pytest.fixture
def source():
    return {
        "source_id": "source-spine-alpha",
        "source_version": 1,
        "source_hash": "fixture-source-hash-alpha-v1",
        "fields": {
            "document_type": "HOLO_CONTINUITY_SPINE",
            "protocol_version": 1,
            "identity": {"anchor_id": "CANYON_OVERRIDE"},
            "sections": {
                "IDENTITY": {"present": True},
                "EVIDENCE": {"present": True},
            },
            "evidence": {"content_support": "UNAVAILABLE"},
        },
    }


@pytest.fixture
def mixed_profile():
    return {
        "destination_id": "destination-beta",
        "profile_version": 1,
        "profile_hash": "fixture-profile-hash-beta-v1",
        "requirements": [
            {
                "id": "R1",
                "comparator": "EXISTS",
                "source_path": "sections.IDENTITY.present",
                "required": True,
            },
            {
                "id": "R2",
                "comparator": "EXACT_VALUE",
                "source_path": "document_type",
                "expected": "HOLO_CONTINUITY_SPINE",
            },
            {
                "id": "R3",
                "comparator": "EXISTS",
                "source_path": "sections.AUTHORITY.present",
                "required": True,
            },
            {
                "id": "R4",
                "comparator": "EXACT_VALUE",
                "source_path": "protocol_version",
                "expected": 2,
            },
            {
                "id": "R5",
                "comparator": "EXACT_VALUE",
                "source_path": "evidence.content_support",
                "expected": "VERIFIED",
                "unavailable_as": "UNCERTAIN",
            },
        ],
    }


def test_mixed_fixture_produces_exact_ordered_partition(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)

    assert finding["verified_requirements"] == ["R1", "R2"]
    assert finding["missing_requirements"] == ["R3"]
    assert finding["conflicts"] == ["R4"]
    assert finding["uncertain"] == ["R5"]
    assert finding["invalid_requirements"] == []
    assert finding["compatible"] is False
    assert finding["accepted"] is False
    assert finding["write_authority"] == "NONE"


def test_compatible_control_never_grants_acceptance_or_authority(
    source, mixed_profile
):
    profile = deepcopy(mixed_profile)
    profile["destination_id"] = "destination-gamma-compatible"
    profile["profile_hash"] = "fixture-profile-hash-gamma-v1"
    profile["requirements"] = profile["requirements"][:2]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["verified_requirements"] == ["R1", "R2"]
    assert finding["missing_requirements"] == []
    assert finding["conflicts"] == []
    assert finding["uncertain"] == []
    assert finding["compatible"] is True
    assert finding["accepted"] is False
    assert finding["write_authority"] == "NONE"


def test_missing_path_is_not_collapsed_into_uncertain_or_conflict(
    source, mixed_profile
):
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [profile["requirements"][2]]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["missing_requirements"] == ["R3"]
    assert finding["conflicts"] == []
    assert finding["uncertain"] == []


def test_present_unequal_value_is_conflict_not_missing(source, mixed_profile):
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [profile["requirements"][3]]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["conflicts"] == ["R4"]
    assert finding["missing_requirements"] == []


@pytest.mark.parametrize(
    ("actual", "expected"),
    [
        (True, 1),
        (False, 0),
        (1, 1.0),
        ({"nested": True}, {"nested": 1}),
        ([True], [1]),
    ],
)
def test_exact_value_rejects_python_cross_type_equality(
    source, mixed_profile, actual, expected
):
    source = deepcopy(source)
    source["fields"]["typed_value"] = actual
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [{
        "id": "TYPE",
        "comparator": "EXACT_VALUE",
        "source_path": "typed_value",
        "expected": expected,
    }]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["verified_requirements"] == []
    assert finding["conflicts"] == ["TYPE"]
    assert finding["compatible"] is False


@pytest.mark.parametrize(
    "value",
    [
        {True: "x"},
        {1: "x"},
        {1.0: "x"},
        (True, 1),
        {"not", "json"},
    ],
)
def test_exact_value_rejects_non_json_values_and_object_keys(
    source, mixed_profile, value
):
    source = deepcopy(source)
    source["fields"]["typed_value"] = value
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [{
        "id": "TYPE",
        "comparator": "EXACT_VALUE",
        "source_path": "typed_value",
        "expected": "anything",
    }]

    with pytest.raises(SpineStructureError, match="non-JSON|keys must be strings"):
        evaluate_destination_compatibility(source, profile)


@pytest.mark.parametrize("container_type", ["dict", "list"])
def test_cyclic_json_values_fail_as_spine_structure_errors(
    source, mixed_profile, container_type
):
    source = deepcopy(source)
    if container_type == "dict":
        cyclic = {}
        cyclic["self"] = cyclic
    else:
        cyclic = []
        cyclic.append(cyclic)
    source["fields"]["cyclic"] = cyclic

    with pytest.raises(SpineStructureError, match="cyclic JSON value"):
        evaluate_destination_compatibility(source, mixed_profile)


def test_excessive_json_depth_fails_as_spine_structure_error(
    source, mixed_profile
):
    source = deepcopy(source)
    nested = current = {}
    for _ in range(102):
        child = {}
        current["next"] = child
        current = child
    source["fields"]["deep"] = nested

    with pytest.raises(SpineStructureError, match="maximum JSON depth"):
        evaluate_destination_compatibility(source, mixed_profile)


def test_explicit_unavailable_value_is_uncertain_when_declared(
    source, mixed_profile
):
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [profile["requirements"][4]]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["uncertain"] == ["R5"]
    assert finding["verified_requirements"] == []
    assert finding["conflicts"] == []


def test_unsupported_comparator_returns_fail_closed_invalid_profile(
    source, mixed_profile
):
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [{
        "id": "MX1",
        "comparator": "MODEL_JUDGED_SIMILARITY",
        "source_path": "document_type",
        "expected": "approximately a continuity document",
    }]

    finding = evaluate_destination_compatibility(source, profile)

    assert finding["profile_status"] == "INVALID_PROFILE"
    assert finding["invalid_requirements"] == ["MX1"]
    assert finding["verified_requirements"] == []
    assert finding["compatible"] is False
    assert finding["accepted"] is False
    assert finding["write_authority"] == "NONE"

    assert check_destination_finding_current(
        finding, source, profile
    ) == {"finding_current": True, "stale_reason": None}


def test_unsupported_comparator_does_not_mask_other_contract_errors(
    source, mixed_profile
):
    duplicate = deepcopy(mixed_profile)
    unsupported = {
        "id": "MX1",
        "comparator": "MODEL_JUDGED_SIMILARITY",
        "source_path": "document_type",
    }
    duplicate["requirements"] = [unsupported, deepcopy(unsupported)]
    with pytest.raises(SpineStructureError, match="duplicate requirement id"):
        evaluate_destination_compatibility(source, duplicate)

    missing_path = deepcopy(mixed_profile)
    missing_path["requirements"] = [{
        "id": "MX1",
        "comparator": "MODEL_JUDGED_SIMILARITY",
    }]
    with pytest.raises(SpineStructureError, match="source_path"):
        evaluate_destination_compatibility(source, missing_path)

    broken_source = deepcopy(source)
    broken_source["fields"] = None
    invalid_profile = deepcopy(mixed_profile)
    invalid_profile["requirements"] = [unsupported]
    with pytest.raises(SpineStructureError, match="source.fields"):
        evaluate_destination_compatibility(broken_source, invalid_profile)


def test_duplicate_requirement_ids_fail_closed(source, mixed_profile):
    profile = deepcopy(mixed_profile)
    profile["requirements"] = [
        profile["requirements"][0],
        deepcopy(profile["requirements"][0]),
    ]

    with pytest.raises(SpineStructureError, match="duplicate requirement id"):
        evaluate_destination_compatibility(source, profile)


def test_malformed_contract_fields_fail_closed(source, mixed_profile):
    broken_source = deepcopy(source)
    broken_source["source_version"] = 0
    with pytest.raises(SpineStructureError, match="source_version"):
        evaluate_destination_compatibility(broken_source, mixed_profile)

    broken_profile = deepcopy(mixed_profile)
    broken_profile["requirements"] = []
    with pytest.raises(SpineStructureError, match="non-empty list"):
        evaluate_destination_compatibility(source, broken_profile)


def test_source_binding_change_stales_prior_finding(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    changed = deepcopy(source)
    changed["source_hash"] = "fixture-source-hash-alpha-v2"

    status = check_destination_finding_current(finding, changed, mixed_profile)

    assert status == {
        "finding_current": False,
        "stale_reason": "SOURCE_CHANGED",
    }


def test_profile_binding_change_stales_prior_finding(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    changed = deepcopy(mixed_profile)
    changed["profile_hash"] = "fixture-profile-hash-beta-v2"

    status = check_destination_finding_current(finding, source, changed)

    assert status == {
        "finding_current": False,
        "stale_reason": "DESTINATION_PROFILE_CHANGED",
    }


@pytest.mark.parametrize(
    ("target", "field"),
    [
        ("source", "source_id"),
        ("source", "source_hash"),
        ("profile", "destination_id"),
        ("profile", "profile_hash"),
    ],
)
def test_opaque_bindings_reject_surrounding_whitespace(
    source, mixed_profile, target, field
):
    changed_source = deepcopy(source)
    changed_profile = deepcopy(mixed_profile)
    container = changed_source if target == "source" else changed_profile
    container[field] = f" {container[field]} "

    with pytest.raises(SpineStructureError, match="surrounding whitespace"):
        evaluate_destination_compatibility(changed_source, changed_profile)


def test_currentness_rejects_whitespace_modified_binding(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    changed = deepcopy(source)
    changed["source_hash"] = f" {changed['source_hash']} "

    with pytest.raises(SpineStructureError, match="surrounding whitespace"):
        check_destination_finding_current(finding, changed, mixed_profile)


def test_unchanged_bindings_remain_current(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)

    status = check_destination_finding_current(finding, source, mixed_profile)

    assert status == {"finding_current": True, "stale_reason": None}


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("accepted", True, "cannot grant acceptance"),
        ("write_authority", "ALL", "cannot grant write authority"),
        ("compatible", True, "contradicts partitions"),
        ("version", True, "positive integer"),
    ],
)
def test_rehashed_tampered_finding_fails_integrity_validation(
    source, mixed_profile, field, value, message
):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    finding[field] = value
    rehash_finding(finding)

    with pytest.raises(SpineStructureError, match=message):
        check_destination_finding_current(finding, source, mixed_profile)


def test_unrehased_tampered_finding_fails_hash_validation(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    finding["accepted"] = True

    with pytest.raises(SpineStructureError, match="hash mismatch"):
        check_destination_finding_current(finding, source, mixed_profile)


@pytest.mark.parametrize("forgery", ["omit", "move", "unknown", "invalid", "extra"])
def test_rehashed_semantic_forgery_fails_current_evaluation(
    source, mixed_profile, forgery
):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    if forgery == "omit":
        finding["conflicts"] = []
        finding["compatible"] = False
    elif forgery == "move":
        finding["conflicts"] = []
        finding["missing_requirements"].append("R4")
    elif forgery == "unknown":
        finding["conflicts"] = ["NOT_IN_PROFILE"]
    elif forgery == "invalid":
        finding["conflicts"] = []
        finding["invalid_requirements"] = ["R4"]
        finding["profile_status"] = "INVALID_PROFILE"
    else:
        finding["unexpected_field"] = "not permitted by canonical evaluation"
    rehash_finding(finding)

    with pytest.raises(SpineStructureError, match="current evaluation"):
        check_destination_finding_current(finding, source, mixed_profile)


def test_non_ascii_or_malformed_finding_hash_fails_closed(source, mixed_profile):
    for invalid_hash in ("é" * 64, "g" * 64, "0" * 63):
        finding = evaluate_destination_compatibility(source, mixed_profile)
        finding["finding_hash"] = invalid_hash

        with pytest.raises(SpineStructureError, match="64 lowercase hex"):
            check_destination_finding_current(finding, source, mixed_profile)


def test_finding_hash_rejects_surrounding_whitespace(source, mixed_profile):
    finding = evaluate_destination_compatibility(source, mixed_profile)
    finding["finding_hash"] = f" {finding['finding_hash']} "

    with pytest.raises(SpineStructureError, match="surrounding whitespace"):
        check_destination_finding_current(finding, source, mixed_profile)


def test_repeated_evaluation_is_deterministic(source, mixed_profile):
    first = evaluate_destination_compatibility(source, mixed_profile)
    second = evaluate_destination_compatibility(
        deepcopy(source), deepcopy(mixed_profile)
    )

    assert first == second
    assert len(first["finding_hash"]) == 64
