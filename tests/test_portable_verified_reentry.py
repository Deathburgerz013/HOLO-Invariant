import json
import subprocess
import sys
from copy import deepcopy

from holosim.continuity_compliance import build_continuity_compliance_contract
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)
from holosim.portable_verified_reentry import build_portable_reentry_bundle
from holosim.reconstructor import build_reconstructed_state
from holosim.verified_cold_start_reentry_gateway import (
    build_verified_cold_start_reentry_packet,
)


SOURCE_ITEMS = [
    {
        "id": "active-goal",
        "requires": ["verified-boundary"],
        "value": "continue current work",
    },
    {
        "id": "verified-boundary",
        "requires": [],
        "value": "observation does not grant authority",
    },
]


def _head_check():
    recall_kernel = {
        "identity": {"system": "HOLO-Invariant"},
        "last_verified_state": "head-10",
        "history": ["head-9", "head-10"],
    }
    contract = build_continuity_compliance_contract(
        contract_id="portable-contract-1",
        subject_id="HOLO-Invariant",
        recall_kernel=recall_kernel,
        observed_required_fields=list(recall_kernel),
        authority_limits=["write:NONE", "execution:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )
    binding = build_continuity_head_binding(
        binding_id="portable-binding-1",
        contract=contract,
        originating_head_hash="head-10",
        originating_head_idx=10,
    )
    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash="head-10",
        current_head_idx=10,
    )


def _bundle():
    state = build_reconstructed_state(
        "portable-cold-start",
        ["active-goal"],
        SOURCE_ITEMS,
    )
    packet = build_verified_cold_start_reentry_packet(
        packet_id="portable-packet-1",
        reconstructed_state=state,
        source_items=SOURCE_ITEMS,
        head_check=_head_check(),
        conflicts=[],
    )
    return build_portable_reentry_bundle(
        bundle_id="portable-bundle-1",
        packet=packet,
        source_items=SOURCE_ITEMS,
    )


def _consume(path):
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "holosim.portable_verified_reentry",
            "consume",
            str(path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )


def test_fresh_process_reconstructs_exact_working_state(tmp_path):
    bundle = _bundle()
    path = tmp_path / "reentry.json"
    path.write_text(json.dumps(bundle), encoding="utf-8")

    completed = _consume(path)

    assert completed.returncode == 0, completed.stderr
    result = json.loads(completed.stdout)
    assert result["status"] == "REENTRY_RECONSTRUCTED"
    assert result["packet_hash"] == bundle["packet"]["packet_hash"]
    assert result["carried_item_ids"] == ["active-goal", "verified-boundary"]
    assert result["working_state"] == bundle["packet"]["reconstructed_state"]
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_fresh_process_rejects_changed_source_evidence(tmp_path):
    bundle = _bundle()
    forged = deepcopy(bundle)
    forged["source_items"][1]["value"] = "injected replacement"
    path = tmp_path / "forged-source.json"
    path.write_text(json.dumps(forged), encoding="utf-8")

    completed = _consume(path)

    assert completed.returncode != 0
    assert completed.stdout == ""


def test_fresh_process_rejects_undeclared_authority_field(tmp_path):
    bundle = _bundle()
    forged = deepcopy(bundle)
    forged["approval"] = "GRANTED"
    path = tmp_path / "forged-authority.json"
    path.write_text(json.dumps(forged), encoding="utf-8")

    completed = _consume(path)

    assert completed.returncode != 0
    assert completed.stdout == ""
