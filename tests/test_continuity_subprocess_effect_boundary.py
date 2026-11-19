
"""Observe continuity effects across a subprocess boundary.

Tests cooperating gate invocation and an intentional bypass.

The parent independently observes filesystem effects, but gate invocation
and reported decisions come from the child process.

This does not establish independent head authority, authenticated
attempt provenance, or a security boundary against arbitrary code.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from holosim.continuity_compliance import (
    build_continuity_compliance_contract,
)
from holosim.continuity_effect_observation import (
    evaluate_continuity_effect,
)
from holosim.continuity_head_binding import (
    build_continuity_head_binding,
    evaluate_continuity_head_binding,
)


RECALL_KERNEL = {
    "identity": {"system": "HOLO-Invariant"},
    "last_verified_state": "state-10",
    "history": ["state-9", "state-10"],
}


def make_head_check(*, current_hash, current_idx):
    contract = build_continuity_compliance_contract(
        contract_id="continuity-contract-gate-1",
        subject_id="HOLO-Invariant",
        recall_kernel=RECALL_KERNEL,
        observed_required_fields=[
            "identity",
            "last_verified_state",
            "history",
        ],
        authority_limits=["write:NONE"],
        unresolved_gap_ids=[],
        recheck_condition_ids=["head-changed"],
    )

    binding = build_continuity_head_binding(
        binding_id="continuity-binding-gate-1",
        contract=contract,
        originating_head_hash="head-hash-10",
        originating_head_idx=10,
    )

    return evaluate_continuity_head_binding(
        binding=binding,
        contract=contract,
        current_head_hash=current_hash,
        current_head_idx=current_idx,
    )


CHILD = """
import json
import sys
from pathlib import Path

from holosim.continuity_current_gate import (
    ContinuityCurrentGateError,
    require_current_continuity,
)

head_check = json.loads(
    Path(sys.argv[1]).read_text(encoding="utf-8")
)
target = Path(sys.argv[2])
bypass = sys.argv[3] == "bypass"

if bypass:
    decision = "BLOCK"
    gate_invoked = False
else:
    gate_invoked = True

    try:
        require_current_continuity(head_check=head_check)
    except ContinuityCurrentGateError:
        decision = "BLOCK"
    else:
        decision = "ALLOW"

if bypass or decision == "ALLOW":
    target.write_text(
        "continuation effect",
        encoding="utf-8",
    )

print(json.dumps({
    "reported_decision": decision,
    "gate_invoked": gate_invoked,
}))
"""


@pytest.mark.parametrize(
    (
        "current_hash",
        "current_idx",
        "bypass",
        "expected_decision",
        "expected_effect",
        "expected_classification",
    ),
    [
        (
            "head-hash-11",
            11,
            False,
            "BLOCK",
            False,
            "BLOCK_REPORTED_NO_EFFECT",
        ),
        (
            "head-hash-10",
            10,
            False,
            "ALLOW",
            True,
            "EXECUTION_OBSERVED",
        ),
        (
            "head-hash-11",
            11,
            True,
            "BLOCK",
            True,
            "REPORTED_BLOCK_EFFECT_CONTRADICTION",
        ),
    ],
)
def test_subprocess_continuation_effect(
    tmp_path,
    current_hash,
    current_idx,
    bypass,
    expected_decision,
    expected_effect,
    expected_classification,
):
    # Build a real continuity head-binding check.
    check = make_head_check(
        current_hash=current_hash,
        current_idx=current_idx,
    )

    check_path = tmp_path / "head-check.json"
    check_path.write_text(
        json.dumps(check),
        encoding="utf-8",
    )

    target = tmp_path / "continuation-effect.txt"

    # Execute the candidate behavior in a separate process.
    completed = subprocess.run(
        [
            sys.executable,
            "-c",
            CHILD,
            str(check_path),
            str(target),
            "bypass" if bypass else "gate",
        ],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
        cwd=Path(__file__).resolve().parents[1],
    )

    # The child supplies the reported decision.
    report = json.loads(completed.stdout)

    assert report["reported_decision"] == expected_decision
    assert report["gate_invoked"] is (not bypass)

    # The parent independently inspects the filesystem effect.
    effect_observed = target.exists()

    assert effect_observed is expected_effect

    if expected_effect:
        assert target.read_text(
            encoding="utf-8"
        ) == "continuation effect"

    # Classify the reported decision against the observed effect.
    #
    # action_attempted=True describes the configured test scenario.
    # It is not independently authenticated attempt provenance.
    classification = evaluate_continuity_effect(
        reported_decision=report["reported_decision"],
        action_attempted=True,
        effect_observed=effect_observed,
    )

    assert classification["classification"] == expected_classification
    assert classification["reported_decision"] == expected_decision
    assert classification["action_attempted"] is True
    assert classification["effect_observed"] is expected_effect

    # Classification must not grant authority or claim truth.
    assert classification["accepted"] is False
    assert classification["truth_claimed"] is False
    assert classification["write_authority"] == "NONE"
    assert classification["execution_authority"] == "NONE"
