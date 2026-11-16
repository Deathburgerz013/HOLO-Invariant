"""Request-level entrypoint for bounded software convergence.

One software request is planned into dependency-ordered capabilities. Each
capability is converged in order, then the resulting project is verified as a
whole. The receipt returns either one runnable result or the exact stage that
blocked convergence.
"""

from __future__ import annotations

from copy import deepcopy
import tempfile
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from holosim.canonical import stable_hash
from holosim.auditable_residue_verifier import build_auditable_residue_verifier
from holosim.witnessed_source_membership import verify_witnessed_source_membership
from holosim.signer_policy_custody import capture_pinned_signer_policy, SignerPolicyCustodyError
from holosim.software_capability_planner import (
    run_software_capability_planner,
)
from holosim.software_generator import run_software_generator


RECEIPT_TYPE = "software_convergence_request_receipt"
RECEIPT_VERSION = 1


def _bind_capability_verifier(
    capability_verifier: Any,
    capability: Mapping[str, Any],
) -> Callable[[Path], Mapping[str, Any]]:
    """Bind a capability-aware verifier to the builder verifier contract."""
    bind = getattr(capability_verifier, "bind", None)

    if callable(bind):
        bound_verifier = bind(deepcopy(dict(capability)))

        if not callable(bound_verifier):
            raise TypeError(
                "capability_verifier.bind must return a callable"
            )

        return bound_verifier

    if not callable(capability_verifier):
        raise TypeError("capability_verifier must be callable")

    return capability_verifier


def run_software_convergence_request(
    software_request: Any,
    workspace: str | Path,
    decomposer: Callable[
        [Any, Mapping[str, Any]],
        Sequence[Mapping[str, Any]],
    ],
    comparator: Callable[[Any, Path], Mapping[str, Any]],
    proposer: Callable[..., Mapping[str, Any]],
    capability_verifier: Any,
    project_verifier: Callable[[Path], Mapping[str, Any]],
    *,
    max_cycles: int = 3,
    max_builder_attempts: int = 3,
    environmental_constraints: Mapping[str, Any] | None = None,
    residue_verifier: Callable[..., Mapping[str, Any]] | None = None,
    preserved_record: Mapping[str, Any] | None = None,
    reconstructed_state: Mapping[str, Any] | None = None,
    residue_source: Mapping[str, Any] | None = None,
    require_residue_provenance: bool = False,
    expected_policy_sha256: str | None = None,
) -> dict[str, Any]:
    """Converge one request into a verified runnable project or exact blocker."""
    if type(require_residue_provenance) is not bool:
        raise TypeError("require_residue_provenance must be a bool")

    workspace_path = Path(workspace).resolve()

    if not workspace_path.is_dir():
        raise ValueError("workspace must be an existing directory")

    if (
        preserved_record is not None
        and not isinstance(preserved_record, Mapping)
    ):
        raise TypeError("preserved_record must be a mapping")

    if (
        reconstructed_state is not None
        and not isinstance(reconstructed_state, Mapping)
    ):
        raise TypeError("reconstructed_state must be a mapping")

    if residue_verifier is not None and not callable(residue_verifier):
        raise TypeError("residue_verifier must be callable")

    if (residue_verifier is None) != (preserved_record is None):
        raise ValueError(
            "residue_verifier and preserved_record "
            "must be provided together"
        )

    if residue_source is not None and (not isinstance(residue_source, Mapping) or residue_verifier is None):
        raise ValueError("residue_source requires residue_verifier and a mapping")

    request = deepcopy(software_request)
    constraints = deepcopy(dict(environmental_constraints or {}))

    plan = run_software_capability_planner(
        request,
        decomposer,
        environmental_constraints=constraints,
    )

    generation_receipts: list[dict[str, Any]] = []
    completed_capability_ids: list[str] = []
    blocked_capability_id: str | None = None
    final_verification: dict[str, Any] | None = None
    residue_verification: dict[str, Any] | None = None
    residue_provenance: dict[str, Any] | None = None
    policy_digest_matched = False
    policy_check_attempted = False

    if plan["planned"] is not True:
        status = "PLANNING_FAILED"
        terminal_reason = plan["terminal_reason"]
        converged = False
        runnable = False
    else:
        status = "BUILDING"
        terminal_reason = "CAPABILITY_CONVERGENCE_IN_PROGRESS"
        converged = False
        runnable = False

        for capability in plan["capabilities"]:
            bound_capability_verifier = _bind_capability_verifier(
                capability_verifier,
                capability,
            )

            receipt = run_software_generator(
                capability,
                workspace_path,
                comparator,
                proposer,
                bound_capability_verifier,
                max_cycles=max_cycles,
                max_builder_attempts=max_builder_attempts,
                environmental_constraints=constraints,
            )

            generation_receipts.append(receipt)

            if receipt["converged"] is not True:
                blocked_capability_id = capability["id"]
                status = "CAPABILITY_FAILED"
                terminal_reason = receipt["terminal_reason"]
                break

            completed_capability_ids.append(capability["id"])
        else:
            verification = project_verifier(workspace_path)

            if not isinstance(verification, Mapping):
                raise TypeError(
                    "project_verifier must return a mapping"
                )

            final_verification = deepcopy(dict(verification))

            project_passed = (
                final_verification.get("passed") is True
            )
            project_runnable = (
                final_verification.get("runnable") is True
            )
            run_command = final_verification.get("command")
            has_run_command = (
                isinstance(run_command, str)
                and bool(run_command.strip())
            )

            if not (
                project_passed
                and project_runnable
                and has_run_command
            ):
                status = "PROJECT_VERIFICATION_FAILED"
                converged = False
                runnable = False

                if project_runnable and not has_run_command:
                    terminal_reason = (
                        "PROJECT_RUN_COMMAND_MISSING"
                    )
                else:
                    terminal_reason = final_verification.get(
                        "reason",
                        "PROJECT_NOT_VERIFIED_RUNNABLE",
                    )
            else:
                if residue_source is not None:
                    required = {"chain_path", "witness_path", "expected_chain_id", "allowed_signers_path", "entry_idx"}
                    if set(residue_source) == required and type(residue_source["entry_idx"]) is int:
                        if expected_policy_sha256 is not None:
                            policy_check_attempted = True
                            try:
                                captured_policy = capture_pinned_signer_policy(
                                    allowed_signers_path=residue_source["allowed_signers_path"],
                                    expected_sha256=expected_policy_sha256,
                                )
                            except SignerPolicyCustodyError:
                                captured_policy = None
                            if captured_policy is not None:
                                policy_digest_matched = True
                                with tempfile.TemporaryDirectory(prefix="holo-residue-policy-") as folder:
                                    pinned_path = Path(folder) / "allowed_signers"
                                    pinned_path.write_bytes(captured_policy)
                                    residue_provenance = verify_witnessed_source_membership(
                                        chain_path=residue_source["chain_path"],
                                        witness_path=residue_source["witness_path"],
                                        expected_chain_id=residue_source["expected_chain_id"],
                                        allowed_signers_path=pinned_path,
                                        source_bindings=[{"entry_idx": residue_source["entry_idx"], "source_item": deepcopy(dict(preserved_record))}],
                                    )
                provenance_valid = (residue_source is None and not require_residue_provenance) or (
                    residue_provenance is not None
                    and residue_provenance.get("status") == "VERIFIED_SOURCE_MEMBERSHIP"
                    and residue_provenance.get("verified") is True
                    and residue_provenance.get("receipt_hash") == stable_hash({k: v for k, v in residue_provenance.items() if k != "receipt_hash"})
                )
                if not provenance_valid:
                    status = "RESIDUE_PROVENANCE_FAILED"
                    terminal_reason = "WITNESSED_SOURCE_MEMBERSHIP_NOT_VERIFIED"
                    converged = False
                    runnable = False
                elif residue_source is not None:
                    status = "RESIDUE_PROVENANCE_UNAUTHENTICATED"
                    terminal_reason = "INDEPENDENT_PROVENANCE_AUTHENTICATION_REQUIRED"
                    converged = False
                    runnable = False
                else:
                    if residue_verifier is not None:
                        preserved = deepcopy(dict(preserved_record))
                        reconstructed = deepcopy(dict(reconstructed_state if reconstructed_state is not None else final_verification))
                        baseline = build_auditable_residue_verifier()(preserved_record=preserved, reconstructed_state=reconstructed)
                        if baseline["verified"] is not True:
                            residue_verification = baseline
                        else:
                            residue_result = residue_verifier(preserved_record=deepcopy(preserved), reconstructed_state=deepcopy(reconstructed))
                            if not isinstance(residue_result, Mapping):
                                raise TypeError("residue_verifier must return a mapping")
                            residue_verification = deepcopy(dict(residue_result))

                    if residue_verification is not None and residue_verification.get("verified") is not True:
                        status = "RESIDUE_VERIFICATION_FAILED"
                        terminal_reason = residue_verification.get("reason", "AUDITABLE_RESIDUE_NOT_VERIFIED")
                        converged = False
                        runnable = False
                    else:
                        status = "CONVERGED"
                        terminal_reason = "PROJECT_VERIFIED_RUNNABLE"
                        converged = True
                        runnable = True

    body: dict[str, Any] = {
        "type": RECEIPT_TYPE,
        "version": 2 if residue_source is not None else RECEIPT_VERSION,
        "software_request": request,
        "workspace": str(workspace_path),
        "environmental_constraints": constraints,
        "plan_receipt_hash": plan["receipt_hash"],
        "planned_capabilities": deepcopy(
            plan["capabilities"]
        ),
        "generation_receipts": generation_receipts,
        "completed_capability_ids": completed_capability_ids,
        "blocked_capability_id": blocked_capability_id,
        "final_verification": final_verification,
        "residue_verification": residue_verification,
        "status": status,
        "terminal_reason": terminal_reason,
        "converged": converged,
        "runnable": runnable,
        "accepted": False,
        "truth_claimed": False,
        "write_authority": "NONE",
    }

    if residue_source is not None:
        body["residue_provenance"] = residue_provenance
        body["residue_policy_binding"] = {
            "status": "MATCHED" if policy_digest_matched else ("REJECTED_POLICY" if policy_check_attempted else "NOT_ATTEMPTED"),
            "expected_policy_sha256": expected_policy_sha256,
            "policy_digest_matched": policy_digest_matched,
            "policy_custody_verified": False,
            "provenance_authenticated": False,
        }

    return {
        **body,
        "receipt_hash": stable_hash(body),
    }