"""Composition test for explicit purpose continuity.

This test asks one bounded question:

Can existing HOLO contracts preserve a declared reason for acting, bind a
later operation to that exact reason, represent when the need is satisfied,
and reconstruct the reason and result together without adding a new
production owner?

It does not establish subjective purpose, consciousness, truth, acceptance,
or authority.
"""

from holosim.canonical import stable_hash
from holosim.check_identity import build_check_identity, bind_check_result
from holosim.functional_awareness_loop import (
    build_functional_awareness_receipt,
    verify_functional_awareness_receipt,
)
from holosim.justification_notice import (
    build_justification_notice,
    validate_justification_notice,
)
from holosim.reconstructor import (
    build_reconstructed_state,
    validate_reconstructed_state,
)


GOAL = {"hydrated": True}
BEFORE = {"hydrated": False}
AFTER = {"hydrated": True}


def _purpose_notice(why_selected: str) -> dict:
    return build_justification_notice(
        notice_id="notice:hydration-purpose:v1",
        parent_notice_hash=None,
        target={
            "target_id": "goal:hydration",
            "target_type": "declared_goal_state",
            "target_sha256": stable_hash(GOAL),
        },
        observed_failure={
            "failure_id": "goal-mismatch",
            "observation": (
                "The verified current state does not match the declared goal."
            ),
        },
        evidence_bindings=[
            {
                "evidence_id": "state:before",
                "evidence_sha256": stable_hash(BEFORE),
            }
        ],
        selected_change={
            "operation": "consume a bounded amount of water",
            "changes_target": False,
        },
        why_selected=why_selected,
        rejected_alternatives=[],
        declared_scope={
            "purpose": "satisfy the current hydration mismatch",
            "stop_condition": "the verified hydration mismatch is removed",
        },
        established_findings=[
            {
                "finding": (
                    "The current state differs from the declared hydration goal."
                )
            }
        ],
        unknowns=[],
        reopen_conditions=[
            "A later verified state shows the hydration mismatch returned."
        ],
        contributors=[
            {
                "contributor_id": "Canyon",
                "role": "declared bounded purpose",
            }
        ],
    )


def _operation(purpose: dict) -> tuple[dict, dict, dict]:
    check_identity = build_check_identity(
        check_id="check:hydration-purpose:v1",
        check_type="functional_awareness",
        subject={
            "loop_id": "loop:hydration",
            "goal_state_hash": stable_hash(GOAL),
        },
        reference_ids=[purpose["notice_hash"]],
        scope={
            "purpose_notice_id": purpose["notice_id"],
            "boundary": "current hydration mismatch only",
        },
        evidence_references=[stable_hash(BEFORE)],
        rule_references=["functional-awareness-loop:v1"],
        input_state_hash=stable_hash(BEFORE),
    )

    awareness = build_functional_awareness_receipt(
        loop_id="loop:hydration",
        goal_state=GOAL,
        before_state=BEFORE,
        after_state=AFTER,
        before_evidence_status="VERIFIED",
        after_evidence_status="VERIFIED",
        solution={
            "solution_id": "solution.water",
            "description": "Consume a bounded amount of water.",
            "execution_status": "VERIFIED_EXECUTED",
            "execution_receipt_hash": "c" * 64,
        },
        adaptation={
            "adaptation_id": "adaptation.stop",
            "statement": (
                "Preserve the resolved result and stop until the mismatch returns."
            ),
        },
    )

    result_binding = bind_check_result(
        check_identity=check_identity,
        result=awareness,
        output_state_hash=awareness["after_state_hash"],
        justifier_reference=purpose["notice_hash"],
    )

    return check_identity, awareness, result_binding


def _items(
    purpose: dict,
    check_identity: dict,
    awareness: dict,
    result_binding: dict,
) -> list[dict]:
    return [
        {
            "id": "purpose",
            "requires": [],
            "notice": purpose,
        },
        {
            "id": "operation-result",
            "requires": ["purpose"],
            "check_identity": check_identity,
            "awareness_receipt": awareness,
            "result_binding": result_binding,
        },
    ]


def test_printed_purpose_need_and_enough_reconstruct_together():
    why = (
        "A current hydration mismatch exists, so perform only the bounded "
        "operation needed to remove it."
    )
    purpose = _purpose_notice(why)
    check_identity, awareness, result_binding = _operation(purpose)

    assert validate_justification_notice(purpose) is True
    assert verify_functional_awareness_receipt(awareness) is True

    # WHY was explicit before the operation identity was constructed.
    assert check_identity["reference_ids"] == [purpose["notice_hash"]]
    assert result_binding["justifier_reference"] == purpose["notice_hash"]

    # NEED existed before the bounded operation.
    assert awareness["problem_visible"] is True
    assert awareness["before_mismatch_paths"] == ["hydrated"]

    # ENOUGH is reached when the verified mismatch is removed.
    assert awareness["effect"] == "RESOLVED"
    assert awareness["after_mismatch_paths"] == []
    assert awareness["adaptation"]["adaptation_id"] == "adaptation.stop"

    items = _items(
        purpose,
        check_identity,
        awareness,
        result_binding,
    )
    reconstructed = build_reconstructed_state(
        "purpose-continuity",
        ["operation-result"],
        items,
    )

    assert validate_reconstructed_state(reconstructed, items) is True
    assert reconstructed["status"] == "COMPLETE"

    carried = {
        item["id"]: item
        for item in reconstructed["carried_items"]
    }

    # A later reconstruction receives the exact printed WHY.
    recovered_purpose = carried["purpose"]["notice"]
    assert recovered_purpose["why_selected"] == why
    assert recovered_purpose["notice_hash"] == purpose["notice_hash"]

    # The reconstructed result remains bound to that exact WHY.
    recovered_operation = carried["operation-result"]
    assert (
        recovered_operation["result_binding"]["justifier_reference"]
        == recovered_purpose["notice_hash"]
    )

    # Nothing in the composition silently gains authority.
    assert recovered_purpose["accepted"] is False
    assert recovered_purpose["write_authority"] == "NONE"
    assert recovered_operation["awareness_receipt"]["accepted"] is False
    assert (
        recovered_operation["awareness_receipt"]["execution_authority"]
        == "NONE"
    )


def test_posthoc_purpose_substitution_is_detectable():
    original = _purpose_notice(
        "A current hydration mismatch exists, so remove only that mismatch."
    )
    check_identity, awareness, result_binding = _operation(original)

    substituted = _purpose_notice(
        "A different reason invented after the operation already occurred."
    )

    assert original["notice_hash"] != substituted["notice_hash"]

    # The operation remains bound to the purpose that existed when its
    # identity and result binding were constructed.
    assert check_identity["reference_ids"] == [original["notice_hash"]]
    assert result_binding["justifier_reference"] == original["notice_hash"]

    # Replacing the printed reason later cannot silently become the reason
    # that the existing operation references.
    assert substituted["notice_hash"] not in check_identity["reference_ids"]
    assert (
        substituted["notice_hash"]
        != result_binding["justifier_reference"]
    )

    original_items = _items(
        original,
        check_identity,
        awareness,
        result_binding,
    )
    substituted_items = _items(
        substituted,
        check_identity,
        awareness,
        result_binding,
    )

    original_state = build_reconstructed_state(
        "purpose-continuity",
        ["operation-result"],
        original_items,
    )
    substituted_state = build_reconstructed_state(
        "purpose-continuity",
        ["operation-result"],
        substituted_items,
    )

    # Even though both source sets are structurally reconstructable, the
    # substituted historical reason produces a different reconstructed
    # state identity and still disagrees with the operation's bound
    # justifier reference.
    assert original_state["state_hash"] != substituted_state["state_hash"]

    substituted_carried = {
        item["id"]: item
        for item in substituted_state["carried_items"]
    }
    assert (
        substituted_carried["operation-result"]["result_binding"][
            "justifier_reference"
        ]
        != substituted_carried["purpose"]["notice"]["notice_hash"]
    )