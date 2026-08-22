"""Cross-repository verification of Simulation candidate evidence."""

from __future__ import annotations

import base64
import copy
import hashlib

import pytest

from holosim.canonical import stable_hash
from holosim.guarantee_environment_binding import bind_guarantee_environment
from holosim.guarantee_registry import build_guarantee_registry
from holosim.simulation_candidate_evidence_bridge import (
    CHECK_ID,
    INVARIANT_ID,
    SimulationCandidateEvidenceBridgeError,
    create_simulation_candidate_environment_receipt,
    verify_simulation_candidate_environment_receipt,
    verify_simulation_candidate_evidence_bundle,
)


SOURCE = "a" * 64
CANDIDATE = "f" * 64


def _bundle():
    content = b"new\n"
    proposal = {
        "relative_path": "app.py",
        "new_content_base64": base64.b64encode(content).decode("ascii"),
        "new_content_hash": hashlib.sha256(content).hexdigest(),
        "expected_original_hash": hashlib.sha256(b"old\n").hexdigest(),
        "expected_tree_state_hash": CANDIDATE,
        "source_manifest_hash": SOURCE,
        "source_tree_state_hash": "b" * 64,
    }
    bindable = {key: proposal[key] for key in (
        "relative_path", "new_content_hash", "expected_original_hash",
        "expected_tree_state_hash", "source_manifest_hash", "source_tree_state_hash",
    )}
    materialization = {
        "bound_source_manifest_hash": SOURCE,
        "bound_source_tree_state_hash": "b" * 64,
        "candidate_manifest_hash": "1" * 64,
        "candidate_tree_state_hash": "b" * 64,
        "source_root": "/source", "candidate_root": "/candidate",
    }
    patch = {
        "status": "PATCH_APPLIED", "reason": "candidate_matches_expected_tree_state",
        "relative_path": "app.py", "new_content_hash": proposal["new_content_hash"],
        "expected_tree_state_hash": CANDIDATE,
        "observed_tree_state_hash": CANDIDATE,
        "approved_for_execution": True, "candidate_root": "/candidate",
    }
    execution = {
        "input_tree_state_hash": CANDIDATE, "command_argv": ["python3", "-c", "print('ok')"],
        "executable_identity": "4" * 64, "resolved_executable": "/usr/bin/python3",
        "working_directory": ".", "environment_policy_hash": "5" * 64,
        "execution_platform": "Linux", "kernel_release": "test", "machine": "x86_64",
        "effective_user_id": 0, "effective_group_id": 0, "cap_sys_admin_effective": True,
        "privilege_requirement": "successful-namespace-probe-v1",
        "required_namespaces": ["mount", "network", "pid"],
        "namespace_probe_exit_code": 0, "namespace_probe_stderr_hash": hashlib.sha256(b"").hexdigest(),
        "namespace_probe_passed": True, "automatic_elevation_attempted": False,
        "timeout_seconds": 20, "network_policy": "DENY", "exit_code": 0,
        "timed_out": False, "stdout_hash": hashlib.sha256(b"ok\n").hexdigest(),
        "stderr_hash": hashlib.sha256(b"").hexdigest(), "output_truncated": False,
        "source_manifest_before": SOURCE, "source_manifest_after": SOURCE,
        "candidate_approved": True, "tests_passed": True, "source_unchanged": True,
        "source_write_protection_verified": True, "network_namespace_created": True,
        "environment_allowlist_applied": True, "host_filesystem_restricted": True,
        "process_group_kill_armed": True, "containment_unavailable": False,
        "observation_complete": True, "execution_clone_input_tree_state_hash": CANDIDATE,
        "execution_clone_matched_candidate": True, "verification": "PASS",
        "reason": "all_declared_properties_held",
    }
    packet = {
        "type": "bounded_candidate_validation", "source_manifest_hash": SOURCE,
        "source_tree_state_hash": "b" * 64, "proposal_hash": stable_hash(bindable),
        "materialization_receipt_hash": stable_hash(materialization),
        "patch_receipt_hash": stable_hash(patch), "expected_tree_state_hash": CANDIDATE,
        "approved_candidate_manifest_hash": "1" * 64,
        "execution_clone_input_tree_state_hash": CANDIDATE,
        "test_receipt_hash": stable_hash(execution), "source_manifest_after_hash": SOURCE,
        "candidate_manifest_after_hash": "2" * 64, "status": "VALIDATED_CANDIDATE",
        "promotion_authority": "NONE", "write_authority": "NONE",
        "next_action": "STOP", "reason": "all_declared_conditions_held",
    }
    packet["packet_hash"] = stable_hash(packet)
    body = {
        "type": "portable_candidate_evidence_bundle", "version": 1,
        "validation_packet": packet, "proposal": proposal,
        "materialization_receipt": materialization, "patch_receipt": patch,
        "execution_receipt": execution, "write_authority": "NONE",
        "promotion_authority": "NONE",
    }
    return {**body, "bundle_hash": stable_hash(body)}


def _receipt(bundle=None, current=SOURCE):
    return create_simulation_candidate_environment_receipt(
        bundle=bundle or _bundle(), source_manifest_probe=lambda: current,
        observed_at="2026-08-22T18:00:00Z",
    )


def test_current_source_produces_held_bounded_receipt():
    receipt = _receipt()
    assert receipt["status"] == "HELD"
    assert receipt["write_authority"] == "NONE"
    assert receipt["execution_authority"] == "NONE"
    assert receipt["accepted"] is False
    assert verify_simulation_candidate_environment_receipt(receipt)


def test_changed_source_is_stale_not_held():
    receipt = _receipt(current="changed-source")
    assert receipt["status"] == "STALE"
    assert receipt["stale_reason"] == "DECLARED_ENVIRONMENT_MISMATCH"
    assert verify_simulation_candidate_environment_receipt(receipt)


def test_probe_failure_is_unknown():
    def fail():
        raise OSError("source unavailable")
    receipt = create_simulation_candidate_environment_receipt(
        bundle=_bundle(), source_manifest_probe=fail,
        observed_at="2026-08-22T18:00:00Z",
    )
    assert receipt["status"] == "UNKNOWN"
    assert verify_simulation_candidate_environment_receipt(receipt)


def test_receipt_binds_matching_holo_guarantee():
    receipt = _receipt()
    guarantee = {
        "guarantee_id": INVARIANT_ID, "guarantee_type": "integrity",
        "scope": "simulation.validated_candidate",
        "dependencies": ["portable evidence verifies independently", "source manifest is freshly reobserved"],
        "validator": CHECK_ID,
        "failure_condition": "portable evidence fails or source manifest changes",
        "evidence": ["portable_candidate_evidence_bundle"],
    }
    binding = bind_guarantee_environment(
        registry=build_guarantee_registry([guarantee]), receipt=receipt,
    )
    assert binding["status"] == "BOUND"
    assert binding["write_authority"] == "NONE"


def test_subordinate_tamper_is_rejected():
    bundle = _bundle()
    bundle["execution_receipt"]["tests_passed"] = False
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="bundle hash mismatch"):
        verify_simulation_candidate_evidence_bundle(bundle)


def test_valid_component_substitution_is_rejected_after_rehash():
    bundle = _bundle()
    bundle["execution_receipt"]["stdout_hash"] = "9" * 64
    body = {key: value for key, value in bundle.items() if key != "bundle_hash"}
    bundle["bundle_hash"] = stable_hash(body)
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="execution receipt hash mismatch"):
        verify_simulation_candidate_evidence_bundle(bundle)


def test_missing_and_extra_fields_are_rejected():
    missing = _bundle(); missing.pop("patch_receipt")
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="bundle fields mismatch"):
        verify_simulation_candidate_evidence_bundle(missing)
    extra = _bundle(); extra["trusted"] = True
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="bundle fields mismatch"):
        verify_simulation_candidate_evidence_bundle(extra)


def test_rehashed_authority_claim_is_rejected():
    bundle = _bundle(); bundle["promotion_authority"] = "GRANTED"
    bundle["bundle_hash"] = stable_hash({k: v for k, v in bundle.items() if k != "bundle_hash"})
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="bundle promotion authority invalid"):
        verify_simulation_candidate_evidence_bundle(bundle)


def test_tampered_holo_receipt_is_rejected():
    receipt = copy.deepcopy(_receipt())
    receipt["declared_environment"]["candidate_tree_state_hash"] = "0" * 64
    with pytest.raises(SimulationCandidateEvidenceBridgeError, match="environment receipt invalid"):
        verify_simulation_candidate_environment_receipt(receipt)
