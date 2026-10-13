"""Research tests for condition evidence derived from permitted observations."""

from __future__ import annotations

import hashlib
import pytest

from holosim.hook_contract import build_hook_request, validate_hook_result
from holosim.observation_permit import (
    observation_root_sha256,
    run_permitted_aligned_observation,
)
from holosim.signed_occurrence import build_signed_occurrence


SECRET = b"p" * 32


def test_matching_measured_file_condition_uses_permitted_observation(tmp_path):
    from holosim.measured_condition_evidence import (
        derive_measured_condition_evidence,
    )

    content = b"current state"
    (tmp_path / "state.txt").write_bytes(content)

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="measured-condition-permit-1",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:measured-condition-permit-1",
        secret=SECRET,
    )

    run = run_permitted_aligned_observation(
        goal_reference="goal:measure-file-condition",
        reference_state="state:before-observation",
        candidates=[
            {
                "candidate_id": "read-current-state",
                "request": request,
                "evidence_references": ["evidence:current-environment"],
                "rule_references": ["invariant:bounded-observation"],
                "comparison_status": "SUPPORTED",
                "uncertainty": "LOW",
                "unresolved_conflicts": [],
                "value": 5,
                "cost": 1,
                "urgency": 0,
                "dependency_impact": 0,
            }
        ],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    assert run["decision"] == "OBSERVED"
    assert run["permit_verification"]["status"] == "VERIFIED"

    expected_hash = hashlib.sha256(content).hexdigest()

    receipt = derive_measured_condition_evidence(
        permitted_run=run,
        condition_id="condition:file-content",
        claim_set_hash="a" * 64,
        expected_content_sha256=expected_hash,
    )

    bundle = receipt["condition_evidence"]

    assert bundle["request"]["action"] == "verify-claim-condition"
    assert bundle["request"]["reference"] == "condition:file-content"
    assert bundle["request"]["payload"] == {
        "condition_id": "condition:file-content",
        "claim_set_hash": "a" * 64,
    }

    assert validate_hook_result(
        bundle["result"],
        request=bundle["request"],
    )
    assert bundle["result"]["status"] == "OBSERVED"
    assert bundle["result"]["evidence"] == {
        "condition_satisfied": True,
    }

    assert receipt["source_observation_result_hash"] == (
        run["observation_result"]["result_hash"]
    )
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"

def test_mismatched_measured_file_condition_is_false(tmp_path):
    from holosim.measured_condition_evidence import (
        derive_measured_condition_evidence,
    )

    content = b"current state"
    (tmp_path / "state.txt").write_bytes(content)

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="measured-condition-permit-mismatch",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:measured-condition-permit-mismatch",
        secret=SECRET,
    )

    run = run_permitted_aligned_observation(
        goal_reference="goal:measure-file-condition",
        reference_state="state:before-observation",
        candidates=[{
            "candidate_id": "read-current-state",
            "request": request,
            "evidence_references": ["evidence:current-environment"],
            "rule_references": ["invariant:bounded-observation"],
            "comparison_status": "SUPPORTED",
            "uncertainty": "LOW",
            "unresolved_conflicts": [],
            "value": 5,
            "cost": 1,
            "urgency": 0,
            "dependency_impact": 0,
        }],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    receipt = derive_measured_condition_evidence(
        permitted_run=run,
        condition_id="condition:file-content",
        claim_set_hash="a" * 64,
        expected_content_sha256=hashlib.sha256(b"different state").hexdigest(),
    )

    assert receipt["condition_evidence"]["result"]["evidence"] == {
        "condition_satisfied": False,
    }
    assert receipt["accepted"] is False
    assert receipt["write_authority"] == "NONE"

def test_rehashed_source_content_cannot_preserve_original_derivation(tmp_path):
    from copy import deepcopy

    from holosim.canonical import stable_hash
    from holosim.measured_condition_evidence import (
        derive_measured_condition_evidence,
    )

    content = b"current state"
    (tmp_path / "state.txt").write_bytes(content)

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="measured-condition-tamper",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:measured-condition-tamper",
        secret=SECRET,
    )

    run = run_permitted_aligned_observation(
        goal_reference="goal:measure-file-condition",
        reference_state="state:before-observation",
        candidates=[{
            "candidate_id": "read-current-state",
            "request": request,
            "evidence_references": ["evidence:current-environment"],
            "rule_references": ["invariant:bounded-observation"],
            "comparison_status": "SUPPORTED",
            "uncertainty": "LOW",
            "unresolved_conflicts": [],
            "value": 5,
            "cost": 1,
            "urgency": 0,
            "dependency_impact": 0,
        }],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    original = derive_measured_condition_evidence(
        permitted_run=run,
        condition_id="condition:file-content",
        claim_set_hash="a" * 64,
        expected_content_sha256=hashlib.sha256(content).hexdigest(),
    )

    from holosim.canonical import stable_hash

    forged_run = deepcopy(run)
    forged_evidence = forged_run["observation_result"]["evidence"]
    forged_evidence["content"] = "different state"
    forged_evidence["byte_count"] = len(b"different state")
    forged_evidence["content_sha256"] = hashlib.sha256(
        b"different state"
    ).hexdigest()

    forged_result = forged_run["observation_result"]
    forged_result["result_hash"] = stable_hash({
        key: value
        for key, value in forged_result.items()
        if key != "result_hash"
    })
    forged_run["run_hash"] = stable_hash({
        key: value
        for key, value in forged_run.items()
        if key != "run_hash"
    })

    changed = derive_measured_condition_evidence(
        permitted_run=forged_run,
        condition_id="condition:file-content",
        claim_set_hash="a" * 64,
        expected_content_sha256=hashlib.sha256(content).hexdigest(),
    )

    assert original["condition_evidence"]["result"]["evidence"] == {
        "condition_satisfied": True,
    }
    assert changed["condition_evidence"]["result"]["evidence"] == {
        "condition_satisfied": False,
    }
    assert changed["source_run_hash"] != original["source_run_hash"]
    assert changed["derivation_hash"] != original["derivation_hash"]

def test_inconsistent_observation_content_fails_closed(tmp_path):
    from copy import deepcopy
    import pytest

    from holosim.measured_condition_evidence import (
        MeasuredConditionEvidenceError,
        derive_measured_condition_evidence,
    )

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    (tmp_path / "state.txt").write_bytes(b"current state")

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="measured-condition-inconsistent",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:measured-condition-inconsistent",
        secret=SECRET,
    )

    run = run_permitted_aligned_observation(
        goal_reference="goal:measure-file-condition",
        reference_state="state:before-observation",
        candidates=[{
            "candidate_id": "read-current-state",
            "request": request,
            "evidence_references": ["evidence:current-environment"],
            "rule_references": ["invariant:bounded-observation"],
            "comparison_status": "SUPPORTED",
            "uncertainty": "LOW",
            "unresolved_conflicts": [],
            "value": 5,
            "cost": 1,
            "urgency": 0,
            "dependency_impact": 0,
        }],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    tampered = deepcopy(run)
    tampered["observation_result"]["evidence"]["content"] = "altered state"

    with pytest.raises(MeasuredConditionEvidenceError):
        derive_measured_condition_evidence(
            permitted_run=tampered,
            condition_id="condition:file-content",
            claim_set_hash="a" * 64,
            expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
        )



def test_measured_condition_receipt_reconstructs_and_rejects_tampering(tmp_path):
    from copy import deepcopy

    import pytest

    from holosim.measured_condition_evidence import (
        MeasuredConditionEvidenceError,
        derive_measured_condition_evidence,
        validate_measured_condition_evidence,
    )

    (tmp_path / "state.txt").write_bytes(b"current state")

    request = build_hook_request(
        hook_id="local-computer",
        action="read_text",
        reference="state.txt",
        payload={"encoding": "utf-8"},
    )

    permit = build_signed_occurrence(
        source_id="operator",
        occurrence_id="measured-condition-validation",
        payload={
            "type": "bounded_observation_permit",
            "version": 1,
            "request_hash": request["request_hash"],
            "allowed_root_sha256": observation_root_sha256(tmp_path),
            "not_before": "2026-08-04T12:00:00-07:00",
            "not_after": "2026-08-04T13:00:00-07:00",
        },
        observed_at="2026-08-04T11:59:00-07:00",
        sequence=1,
        nonce="nonce:measured-condition-validation",
        secret=SECRET,
    )

    run = run_permitted_aligned_observation(
        goal_reference="goal:measure-file-condition",
        reference_state="state:before-observation",
        candidates=[{
            "candidate_id": "read-current-state",
            "request": request,
            "evidence_references": ["evidence:current-environment"],
            "rule_references": ["invariant:bounded-observation"],
            "comparison_status": "SUPPORTED",
            "uncertainty": "LOW",
            "unresolved_conflicts": [],
            "value": 5,
            "cost": 1,
            "urgency": 0,
            "dependency_impact": 0,
        }],
        allowed_root=tmp_path,
        observed_at="2026-08-04T12:30:00-07:00",
        permit_occurrence=permit,
        permit_source_secrets={"operator": SECRET},
        seen_occurrence_ids=set(),
    )

    receipt = derive_measured_condition_evidence(
        permitted_run=run,
        condition_id="condition:file-content",
        claim_set_hash="a" * 64,
        expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
    )

    assert validate_measured_condition_evidence(receipt) is True

    from holosim.canonical import stable_hash

    for invalid_verification in (
        None,
        {},
        {"verified": False, "status": "VERIFIED"},
        {"verified": True, "status": "FAILED"},
    ):
        invalid_run = deepcopy(run)
        invalid_run["permit_verification"] = invalid_verification
        invalid_run["run_hash"] = stable_hash({
            key: value
            for key, value in invalid_run.items()
            if key != "run_hash"
        })
        with pytest.raises(MeasuredConditionEvidenceError):
            derive_measured_condition_evidence(
                permitted_run=invalid_run,
                condition_id="condition:file-content",
                claim_set_hash="a" * 64,
                expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
            )

    for invalid_byte_count in (-1, "13", None, True):
        invalid_run = deepcopy(run)
        result = invalid_run["observation_result"]
        result["evidence"]["byte_count"] = invalid_byte_count
        result["result_hash"] = stable_hash({
            key: value for key, value in result.items()
            if key != "result_hash"
        })
        invalid_run["run_hash"] = stable_hash({
            key: value for key, value in invalid_run.items()
            if key != "run_hash"
        })
        with pytest.raises(MeasuredConditionEvidenceError):
            derive_measured_condition_evidence(
                permitted_run=invalid_run,
                condition_id="condition:file-content",
                claim_set_hash="a" * 64,
                expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
            )
    duplicate_run = deepcopy(run)
    duplicate_selection = duplicate_run["selection"]
    selected_id = duplicate_selection["selected_candidate_id"]
    selected_evaluation = next(
        item for item in duplicate_selection["evaluations"]
        if item["candidate_id"] == selected_id
    )
    duplicate_selection["evaluations"].append(deepcopy(selected_evaluation))
    duplicate_selection["selection_hash"] = stable_hash({
        key: value
        for key, value in duplicate_selection.items()
        if key != "selection_hash"
    })
    duplicate_run["run_hash"] = stable_hash({
        key: value
        for key, value in duplicate_run.items()
        if key != "run_hash"
    })
    with pytest.raises(MeasuredConditionEvidenceError):
        derive_measured_condition_evidence(
            permitted_run=duplicate_run,
            condition_id="condition:file-content",
            claim_set_hash="a" * 64,
            expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
        )
    forged_run = deepcopy(run)
    forged_run["selection"]["selection_hash"] = "0" * 64
    forged_run["run_hash"] = stable_hash({
        key: value
        for key, value in forged_run.items()
        if key != "run_hash"
    })

    with pytest.raises(MeasuredConditionEvidenceError):
        derive_measured_condition_evidence(
            permitted_run=forged_run,
            condition_id="condition:file-content",
            claim_set_hash="a" * 64,
            expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
        )

    contradictory_run = deepcopy(run)
    contradictory_selection = contradictory_run["selection"]
    contradictory_selection["selected_candidate_id"] = "nonexistent-candidate"
    contradictory_selection["selection_hash"] = stable_hash({
        key: value
        for key, value in contradictory_selection.items()
        if key != "selection_hash"
    })
    contradictory_run["run_hash"] = stable_hash({
        key: value
        for key, value in contradictory_run.items()
        if key != "run_hash"
    })

    with pytest.raises(MeasuredConditionEvidenceError):
        derive_measured_condition_evidence(
            permitted_run=contradictory_run,
            condition_id="condition:file-content",
            claim_set_hash="a" * 64,
            expected_content_sha256=hashlib.sha256(b"current state").hexdigest(),
        )

    tampered = deepcopy(receipt)
    tampered["condition_evidence"]["result"]["evidence"][
        "condition_satisfied"
    ] = False

    with pytest.raises(MeasuredConditionEvidenceError):
        validate_measured_condition_evidence(tampered)



def test_malformed_unicode_is_rejected_as_measured_condition_error():
    import pytest

    from holosim.measured_condition_evidence import (
        MeasuredConditionEvidenceError,
        derive_measured_condition_evidence,
    )

    with pytest.raises(
        MeasuredConditionEvidenceError,
        match="invalid canonical data",
    ):
        derive_measured_condition_evidence(
            permitted_run={
                "type": "permitted_aligned_observation",
                "version": 1,
                "selection": {"content": chr(0xD800)},
                "permit_verification": {},
                "decision": "OBSERVED",
                "reason": "",
                "observation_performed": True,
                "observation_result": {},
                "accepted": False,
                "write_authority": "NONE",
                "execution_authority": "NONE",
                "run_hash": "0" * 64,
            },
            condition_id="condition:file-content",
            claim_set_hash="a" * 64,
            expected_content_sha256="b" * 64,
        )

@pytest.mark.parametrize(
    "overrides",
    [
        {"permitted_run": None},
        {"permitted_run": []},
        {"permitted_run": {}},
        {"condition_id": ""},
        {"condition_id": " condition:file-content"},
        {"condition_id": 42},
        {"claim_set_hash": "a" * 63},
        {"claim_set_hash": "G" * 64},
        {"expected_content_sha256": None},
        {"expected_content_sha256": "A" * 64},
    ],
)
def test_measured_condition_rejects_invalid_inputs(overrides):
    from holosim.measured_condition_evidence import (
        MeasuredConditionEvidenceError,
        derive_measured_condition_evidence,
    )

    arguments = {
        "permitted_run": {},
        "condition_id": "condition:file-content",
        "claim_set_hash": "a" * 64,
        "expected_content_sha256": "b" * 64,
    }
    arguments.update(overrides)

    with pytest.raises(MeasuredConditionEvidenceError):
        derive_measured_condition_evidence(**arguments)
