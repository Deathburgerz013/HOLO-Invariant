"""Verify Simulation candidate evidence and bind it to a current HOLO environment.

This consumer does not import Simulation_Invariant.  It independently checks
the portable JSON contract, then requires a fresh source-manifest probe before
emitting a standard HOLO environment-invariant receipt.
"""

from __future__ import annotations

import base64
import json
import secrets
from collections.abc import Callable, Mapping
from typing import Any

from holosim.canonical import stable_hash
from holosim.environment_invariant_receipts import (
    EnvironmentInvariantReceiptError,
    evaluate_environment_invariant,
    verify_environment_invariant_receipt,
)


BUNDLE_TYPE = "portable_candidate_evidence_bundle"
BUNDLE_VERSION = 1
INVARIANT_ID = "simulation-candidate-evidence-integrity"
CHECK_ID = "verify-portable-candidate-evidence-bundle-v1"

_BUNDLE_FIELDS = {
    "type", "version", "validation_packet", "proposal",
    "materialization_receipt", "patch_receipt", "execution_receipt",
    "write_authority", "promotion_authority", "bundle_hash",
}
_PACKET_FIELDS = {
    "type", "source_manifest_hash", "source_tree_state_hash", "proposal_hash",
    "materialization_receipt_hash", "patch_receipt_hash",
    "expected_tree_state_hash", "approved_candidate_manifest_hash",
    "execution_clone_input_tree_state_hash", "test_receipt_hash",
    "source_manifest_after_hash", "candidate_manifest_after_hash", "status",
    "promotion_authority", "write_authority", "next_action", "reason",
    "packet_hash",
}
_PROPOSAL_FIELDS = {
    "relative_path", "new_content_base64", "new_content_hash",
    "expected_original_hash", "expected_tree_state_hash",
    "source_manifest_hash", "source_tree_state_hash",
}
_MATERIALIZATION_FIELDS = {
    "bound_source_manifest_hash", "bound_source_tree_state_hash",
    "candidate_manifest_hash", "candidate_tree_state_hash",
    "source_root", "candidate_root",
}
_PATCH_FIELDS = {
    "status", "reason", "relative_path", "new_content_hash",
    "expected_tree_state_hash", "observed_tree_state_hash",
    "approved_for_execution", "candidate_root",
}
_EXECUTION_FIELDS = {
    "input_tree_state_hash", "command_argv", "executable_identity",
    "resolved_executable", "working_directory", "environment_policy_hash",
    "execution_platform", "kernel_release", "machine", "effective_user_id",
    "effective_group_id", "cap_sys_admin_effective", "privilege_requirement",
    "required_namespaces", "namespace_probe_exit_code",
    "namespace_probe_stderr_hash", "namespace_probe_passed",
    "automatic_elevation_attempted", "timeout_seconds", "network_policy",
    "exit_code", "timed_out", "stdout_hash", "stderr_hash",
    "output_truncated", "source_manifest_before", "source_manifest_after",
    "candidate_approved", "tests_passed", "source_unchanged",
    "source_write_protection_verified", "network_namespace_created",
    "environment_allowlist_applied", "host_filesystem_restricted",
    "process_group_kill_armed", "containment_unavailable",
    "observation_complete", "execution_clone_input_tree_state_hash",
    "execution_clone_matched_candidate", "verification", "reason",
}


class SimulationCandidateEvidenceBridgeError(ValueError):
    """Portable evidence or its HOLO binding violates the bridge contract."""


def _closed(value: Any, label: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise SimulationCandidateEvidenceBridgeError(f"{label} must be an object")
    try:
        encoded = json.dumps(
            dict(value), sort_keys=True, separators=(",", ":"),
            ensure_ascii=False, allow_nan=False,
        )
        decoded = json.loads(encoded)
    except (TypeError, ValueError) as exc:
        raise SimulationCandidateEvidenceBridgeError(
            f"{label} must contain only JSON values"
        ) from exc
    return decoded


def _fields(value: Mapping[str, Any], expected: set[str], label: str) -> None:
    if set(value) != expected:
        raise SimulationCandidateEvidenceBridgeError(f"{label} fields mismatch")


def _hash(value: Any) -> str:
    return stable_hash(value)


def verify_simulation_candidate_evidence_bundle(
    value: Mapping[str, Any],
) -> bool:
    """Independently verify the complete Simulation portable bundle."""
    bundle = _closed(value, "bundle")
    _fields(bundle, _BUNDLE_FIELDS, "bundle")
    if bundle["type"] != BUNDLE_TYPE or bundle["version"] != BUNDLE_VERSION:
        raise SimulationCandidateEvidenceBridgeError("bundle schema mismatch")
    if bundle["write_authority"] != "NONE":
        raise SimulationCandidateEvidenceBridgeError("bundle write authority invalid")
    if bundle["promotion_authority"] != "NONE":
        raise SimulationCandidateEvidenceBridgeError("bundle promotion authority invalid")
    body = {key: item for key, item in bundle.items() if key != "bundle_hash"}
    supplied = bundle["bundle_hash"]
    if not isinstance(supplied, str) or not secrets.compare_digest(supplied, _hash(body)):
        raise SimulationCandidateEvidenceBridgeError("bundle hash mismatch")

    packet = _closed(bundle["validation_packet"], "packet")
    _fields(packet, _PACKET_FIELDS, "packet")
    packet_body = {key: item for key, item in packet.items() if key != "packet_hash"}
    if not isinstance(packet["packet_hash"], str) or not secrets.compare_digest(
        packet["packet_hash"], _hash(packet_body)
    ):
        raise SimulationCandidateEvidenceBridgeError("packet hash mismatch")
    if packet["type"] != "bounded_candidate_validation":
        raise SimulationCandidateEvidenceBridgeError("packet type mismatch")
    if packet["status"] != "VALIDATED_CANDIDATE":
        raise SimulationCandidateEvidenceBridgeError("candidate is not validated")
    if packet["write_authority"] != "NONE" or packet["promotion_authority"] != "NONE":
        raise SimulationCandidateEvidenceBridgeError("packet authority invalid")

    proposal = _closed(bundle["proposal"], "proposal")
    _fields(proposal, _PROPOSAL_FIELDS, "proposal")
    encoded = proposal["new_content_base64"]
    try:
        content = base64.b64decode(encoded.encode("ascii"), validate=True)
    except (AttributeError, UnicodeEncodeError, ValueError) as exc:
        raise SimulationCandidateEvidenceBridgeError("proposal content invalid") from exc
    if base64.b64encode(content).decode("ascii") != encoded:
        raise SimulationCandidateEvidenceBridgeError("proposal content is not canonical")
    if proposal["new_content_hash"] != __import__("hashlib").sha256(content).hexdigest():
        raise SimulationCandidateEvidenceBridgeError("proposal content hash mismatch")
    bindable = {
        "relative_path": proposal["relative_path"],
        "new_content_hash": proposal["new_content_hash"],
        "expected_original_hash": proposal["expected_original_hash"],
        "expected_tree_state_hash": proposal["expected_tree_state_hash"],
        "source_manifest_hash": proposal["source_manifest_hash"],
        "source_tree_state_hash": proposal["source_tree_state_hash"],
    }
    comparisons = (
        (packet["proposal_hash"], _hash(bindable), "proposal hash mismatch"),
        (packet["expected_tree_state_hash"], proposal["expected_tree_state_hash"], "expected tree mismatch"),
        (packet["source_manifest_hash"], proposal["source_manifest_hash"], "source manifest mismatch"),
        (packet["source_tree_state_hash"], proposal["source_tree_state_hash"], "source tree mismatch"),
    )
    for actual, expected, error in comparisons:
        if actual != expected:
            raise SimulationCandidateEvidenceBridgeError(error)

    materialization = _closed(bundle["materialization_receipt"], "materialization receipt")
    _fields(materialization, _MATERIALIZATION_FIELDS, "materialization receipt")
    if packet["materialization_receipt_hash"] != _hash(materialization):
        raise SimulationCandidateEvidenceBridgeError("materialization receipt hash mismatch")
    if materialization["bound_source_manifest_hash"] != packet["source_manifest_hash"]:
        raise SimulationCandidateEvidenceBridgeError("materialization source mismatch")
    if materialization["bound_source_tree_state_hash"] != packet["source_tree_state_hash"]:
        raise SimulationCandidateEvidenceBridgeError("materialization tree mismatch")

    patch = _closed(bundle["patch_receipt"], "patch receipt")
    _fields(patch, _PATCH_FIELDS, "patch receipt")
    if packet["patch_receipt_hash"] != _hash(patch):
        raise SimulationCandidateEvidenceBridgeError("patch receipt hash mismatch")
    if (
        patch["status"] != "PATCH_APPLIED"
        or patch["approved_for_execution"] is not True
        or patch["relative_path"] != proposal["relative_path"]
        or patch["new_content_hash"] != proposal["new_content_hash"]
        or patch["expected_tree_state_hash"] != packet["expected_tree_state_hash"]
        or patch["observed_tree_state_hash"] != packet["expected_tree_state_hash"]
    ):
        raise SimulationCandidateEvidenceBridgeError("patch binding mismatch")

    execution = _closed(bundle["execution_receipt"], "execution receipt")
    _fields(execution, _EXECUTION_FIELDS, "execution receipt")
    if packet["test_receipt_hash"] != _hash(execution):
        raise SimulationCandidateEvidenceBridgeError("execution receipt hash mismatch")
    if execution["verification"] != "PASS" or execution["tests_passed"] is not True:
        raise SimulationCandidateEvidenceBridgeError("execution did not pass")
    if execution["execution_clone_input_tree_state_hash"] != packet["expected_tree_state_hash"]:
        raise SimulationCandidateEvidenceBridgeError("execution input mismatch")
    if execution["source_manifest_before"] != packet["source_manifest_hash"]:
        raise SimulationCandidateEvidenceBridgeError("execution source-before mismatch")
    if execution["source_manifest_after"] != packet["source_manifest_after_hash"]:
        raise SimulationCandidateEvidenceBridgeError("execution source-after mismatch")
    return True


def create_simulation_candidate_environment_receipt(
    *,
    bundle: Mapping[str, Any],
    source_manifest_probe: Callable[[], str],
    observed_at: str,
) -> dict[str, Any]:
    """Verify evidence and compare its source identity with the source now."""
    verify_simulation_candidate_evidence_bundle(bundle)
    if not callable(source_manifest_probe):
        raise SimulationCandidateEvidenceBridgeError("source manifest probe must be callable")
    closed_bundle = _closed(bundle, "bundle")
    packet = closed_bundle["validation_packet"]
    declared = {
        "protocol": f"{BUNDLE_TYPE}/v{BUNDLE_VERSION}",
        "bundle_hash": closed_bundle["bundle_hash"],
        "validation_packet_hash": packet["packet_hash"],
        "source_manifest_hash": packet["source_manifest_hash"],
        "source_tree_state_hash": packet["source_tree_state_hash"],
        "candidate_tree_state_hash": packet["expected_tree_state_hash"],
    }

    def probe() -> dict[str, Any]:
        current = source_manifest_probe()
        if not isinstance(current, str) or not current:
            raise SimulationCandidateEvidenceBridgeError(
                "source manifest probe must return a non-empty string"
            )
        return {**declared, "source_manifest_hash": current}

    return evaluate_environment_invariant(
        invariant_id=INVARIANT_ID,
        statement=(
            "A Simulation validated candidate remains bound to the currently "
            "observed source manifest and its complete portable evidence."
        ),
        scope={
            "target": "simulation.validated_candidate",
            "candidate_tree_state_hash": packet["expected_tree_state_hash"],
            "conditions": [
                "portable evidence verifies independently",
                "source manifest is freshly reobserved",
            ],
        },
        environment=declared,
        environment_probe=probe,
        check_id=CHECK_ID,
        check=lambda: True,
        observed_at=observed_at,
        evidence={
            "sources": ["portable_candidate_evidence_bundle"],
            "portable_candidate_evidence_bundle": closed_bundle,
        },
    )


def verify_simulation_candidate_environment_receipt(
    receipt: Mapping[str, Any],
) -> bool:
    """Verify both the standard HOLO receipt and the embedded Simulation proof."""
    try:
        verify_environment_invariant_receipt(receipt)
    except EnvironmentInvariantReceiptError as exc:
        raise SimulationCandidateEvidenceBridgeError(
            f"environment receipt invalid: {exc}"
        ) from exc
    closed = _closed(receipt, "environment receipt")
    if closed.get("invariant_id") != INVARIANT_ID or closed.get("check_id") != CHECK_ID:
        raise SimulationCandidateEvidenceBridgeError("bridge receipt identity mismatch")
    evidence = closed.get("evidence", {})
    bundle = evidence.get("portable_candidate_evidence_bundle")
    verify_simulation_candidate_evidence_bundle(bundle)
    packet = bundle["validation_packet"]
    declared = closed["declared_environment"]
    expected = {
        "protocol": f"{BUNDLE_TYPE}/v{BUNDLE_VERSION}",
        "bundle_hash": bundle["bundle_hash"],
        "validation_packet_hash": packet["packet_hash"],
        "source_manifest_hash": packet["source_manifest_hash"],
        "source_tree_state_hash": packet["source_tree_state_hash"],
        "candidate_tree_state_hash": packet["expected_tree_state_hash"],
    }
    if declared != expected:
        raise SimulationCandidateEvidenceBridgeError("declared bridge environment mismatch")
    if closed["status"] == "HELD" and closed["observed_environment"] != declared:
        raise SimulationCandidateEvidenceBridgeError("held receipt is not current")
    return True
