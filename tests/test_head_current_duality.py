from copy import deepcopy

from holosim.continuity_current_gate import evaluate_continuity_current_gate
from holosim.continuity_head_binding import build_continuity_head_binding, evaluate_continuity_head_binding
from holosim.continuity_compliance import build_continuity_compliance_contract

RECALL_KERNEL = {"identity": {"system": "HOLO-Invariant"}, "history": ["state-1", "state-2"], "last_verified_state": "state-2"}


def _contract(contract_id="continuity-duality-contract"):
    return build_continuity_compliance_contract(contract_id=contract_id, subject_id="HOLO-Invariant", recall_kernel=RECALL_KERNEL, observed_required_fields=list(RECALL_KERNEL), authority_limits=["write:NONE"], unresolved_gap_ids=["gap-1"], recheck_condition_ids=["head-changed"])


def _binding(contract):
    return build_continuity_head_binding(binding_id="continuity-duality-binding-1", contract=contract, originating_head_hash="head-hash-10", originating_head_idx=10)


def test_same_binding_survives_all_status_readings_without_mutation():
    contract = _contract()
    binding = _binding(contract)
    original = deepcopy(binding)
    current = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash="head-hash-10", current_head_idx=10)
    stale = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash="head-hash-11", current_head_idx=11)
    unknown = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash=None, current_head_idx=None)
    invalid = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash="different-head-hash-10", current_head_idx=10)
    assert binding == original
    assert binding["binding_hash"] == original["binding_hash"]
    assert {current["status"], stale["status"], unknown["status"], invalid["status"]} == {"CURRENT", "STALE", "UNKNOWN", "INVALID"}
    for check in (current, stale, unknown, invalid):
        assert check["binding_hash"] == original["binding_hash"]
        assert check["truth_claimed"] is False
        assert check["accepted"] is False
        assert check["write_authority"] == "NONE"


def test_current_gate_does_not_become_authorization():
    contract = _contract()
    binding = _binding(contract)
    check = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash="head-hash-10", current_head_idx=10)
    gate = evaluate_continuity_current_gate(head_check=check)
    assert gate["decision"] == "ALLOW"
    assert gate["head_status"] == "CURRENT"
    assert gate["truth_claimed"] is False
    assert gate["accepted"] is False
    assert gate["write_authority"] == "NONE"
    assert "execution_authority" not in gate
    assert "authorization" not in gate


def test_authorization_does_not_become_currentness():
    contract = _contract()
    binding = _binding(contract)
    check = evaluate_continuity_head_binding(binding=binding, contract=contract, current_head_hash="head-hash-11", current_head_idx=11)
    assert check["status"] == "STALE"
    assert check["binding_hash"] == binding["binding_hash"]
    assert binding["originating_head_hash"] == "head-hash-10"
    assert binding["originating_head_idx"] == 10


def test_new_head_requires_new_binding_without_rewriting_old_binding():
    contract = _contract()
    old_binding = _binding(contract)
    old_original = deepcopy(old_binding)

    stale = evaluate_continuity_head_binding(binding=old_binding, contract=contract, current_head_hash="head-hash-11", current_head_idx=11)
    new_binding = build_continuity_head_binding(binding_id="continuity-duality-binding-2", contract=contract, originating_head_hash="head-hash-11", originating_head_idx=11)
    current = evaluate_continuity_head_binding(binding=new_binding, contract=contract, current_head_hash="head-hash-11", current_head_idx=11)

    assert stale["status"] == "STALE"
    assert current["status"] == "CURRENT"
    assert old_binding == old_original
    assert old_binding["binding_hash"] == old_original["binding_hash"]
    assert old_binding["originating_head_hash"] == "head-hash-10"
    assert old_binding["originating_head_idx"] == 10
    assert new_binding["originating_head_hash"] == "head-hash-11"
    assert new_binding["originating_head_idx"] == 11
    assert new_binding["binding_hash"] != old_binding["binding_hash"]
    assert current["binding_hash"] == new_binding["binding_hash"]
