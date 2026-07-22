"""Executable end-to-end continuity handoff story.

This example demonstrates one bounded behavior chain that already exists in HOLO-Invariant:

1. Build a continuity handoff contract for a fresh instance.
2. Require the fresh instance to acknowledge the exact recall kernel and limits.
3. Bind that handoff to the verified head it came from.
4. Observe a newer verified head and classify the old handoff as STALE.
5. Fail closed before continuation.
6. Build a handoff from the newer verified head and allow continuation only when CURRENT.

The example does not claim truth, discover the authoritative head, or grant write authority.
"""

from holosim.continuity_compliance import (
    build_continuity_compliance_contract,
    evaluate_continuity_attestation,
)
from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    require_current_continuity,
)
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)


def build_contract(*, contract_id: str, state_name: str) -> dict:
    recall_kernel = {
        "identity": {"system": "HOLO-Invariant"},
        "last_verified_state": state_name,
        "history": ["state-9", state_name],
    }
    return build_continuity_compliance_contract(
        contract_id=contract_id,
        subject_id="HOLO-Invariant",
        recall_kernel=recall_kernel,
        observed_required_fields=["identity", "last_verified_state", "history"],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )


def attest_fresh_instance(contract: dict, *, instance_id: str) -> dict:
    return evaluate_continuity_attestation(
        contract=contract,
        instance_id=instance_id,
        recalled_kernel_hash=contract["recall_kernel_hash"],
        recalled_fields=contract["observed_required_fields"],
        acknowledged_authority_limits=contract["authority_limits"],
        acknowledged_unresolved_gap_ids=contract["unresolved_gap_ids"],
        acknowledged_recheck_condition_ids=contract["recheck_condition_ids"],
    )


def main() -> None:
    # State A was valid when verified head 10 was current.
    old_contract = build_contract(
        contract_id="continuity-example-state-10",
        state_name="state-10",
    )
    old_attestation = attest_fresh_instance(
        old_contract,
        instance_id="fresh-instance-A",
    )
    assert old_attestation["status"] == "COMPLIANT"

    old_binding = build_continuity_head_binding(
        binding_id="continuity-example-binding-10",
        contract=old_contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )

    # New verified evidence advances the independently supplied current head to 11.
    stale_check = evaluate_continuity_head_binding(
        binding=old_binding,
        contract=old_contract,
        current_head_hash="head-hash-11",
        current_head_idx=11,
    )
    assert stale_check["status"] == "STALE"

    # The old handoff is internally valid but no longer current. Continuation must stop.
    try:
        require_current_continuity(head_check=stale_check)
    except ContinuityCurrentGateError as exc:
        print(f"old handoff: {stale_check['status']} -> BLOCKED ({exc})")
    else:
        raise AssertionError("stale continuity handoff unexpectedly passed the gate")

    # A new handoff is built from the newer verified state/head.
    current_contract = build_contract(
        contract_id="continuity-example-state-11",
        state_name="state-11",
    )
    current_attestation = attest_fresh_instance(
        current_contract,
        instance_id="fresh-instance-B",
    )
    assert current_attestation["status"] == "COMPLIANT"

    current_binding = build_continuity_head_binding(
        binding_id="continuity-example-binding-11",
        contract=current_contract,
        originating_head_hash="head-hash-11",
        originating_head_idx=11,
    )
    current_check = evaluate_continuity_head_binding(
        binding=current_binding,
        contract=current_contract,
        current_head_hash="head-hash-11",
        current_head_idx=11,
    )
    assert current_check["status"] == "CURRENT"

    decision = require_current_continuity(head_check=current_check)
    assert decision["decision"] == "ALLOW"
    print("current handoff: CURRENT -> ALLOW")
    print("truth_claimed=False, accepted=False, write_authority=NONE")


if __name__ == "__main__":
    main()
