import json
from copy import deepcopy
from pathlib import Path

from holosim.justification_notice import build_justification_notice


FIXTURE_DIR = (
    Path(__file__).parent
    / "fixtures"
    / "interpretation_set_receipt"
)


def _valid_notice(*, alternative_id="B", target_id="obs-001"):
    return build_justification_notice(
        notice_id="notice:obs-001:v1",
        parent_notice_hash=None,
        target={
            "target_id": target_id,
            "target_type": "interpretation_set",
            "target_sha256": "a" * 64,
        },
        observed_failure={
            "failure_id": "ambiguity",
            "observation": "A and B remain possible.",
        },
        evidence_bindings=[
            {
                "evidence_id": "evidence-001",
                "evidence_sha256": "b" * 64,
            }
        ],
        selected_change={
            "operation": "subtract interpretation",
            "changes_target": False,
        },
        why_selected="Discriminating evidence eliminates an interpretation.",
        rejected_alternatives=[
            {
                "alternative_id": alternative_id,
                "description": f"Interpretation {alternative_id}",
                "rejection_reason": "Evidence excludes this interpretation.",
                "evidence_ids": ["evidence-001"],
            }
        ],
        declared_scope={
            "observation_id": target_id,
        },
        established_findings=[],
        unknowns=[],
        reopen_conditions=[
            "New evidence changes the interpretation set.",
        ],
        contributors=[
            {
                "contributor_id": "test",
                "role": "fixture",
            }
        ],
    )


def test_argmax_is_not_determination():
    fixture = json.loads(
        (FIXTURE_DIR / "argmax_is_not_determination.json").read_text(
            encoding="utf-8"
        )
    )

    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id=fixture["observation_id"],
        prior_set=fixture["prior_set"],
        ranks=fixture["ranks"],
        subtract_receipts=[],
    )

    assert list(receipt.current_set) == fixture["expected_set"]


def test_reason_without_valid_notice_cannot_eliminate_member():
    fixture = json.loads(
        (FIXTURE_DIR / "unbound_reason_cannot_eliminate.json").read_text(
            encoding="utf-8"
        )
    )

    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id=fixture["observation_id"],
        prior_set=fixture["prior_set"],
        ranks=fixture["ranks"],
        subtract_receipts=fixture["subtract_receipts"],
    )

    assert list(receipt.current_set) == fixture["expected_set"]


def test_valid_justification_notice_does_not_subtract_by_itself():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[],
        justification_notices=[_valid_notice()],
    )

    assert list(receipt.current_set) == ["A", "B"]


def test_tampered_justification_notice_cannot_subtract():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    notice = deepcopy(_valid_notice())
    notice["rejected_alternatives"][0]["rejection_reason"] = "rewritten"

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[],
        justification_notices=[notice],
    )

    assert list(receipt.current_set) == ["A", "B"]


def test_notice_for_different_observation_cannot_subtract():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[],
        justification_notices=[
            _valid_notice(target_id="obs-002"),
        ],
    )

    assert list(receipt.current_set) == ["A", "B"]


def test_justification_notice_alone_does_not_eliminate_member():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[],
        justification_notices=[_valid_notice()],
    )

    assert list(receipt.current_set) == ["A", "B"]


def test_explicit_subtract_receipt_eliminates_member():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    evidence_hash = "b" * 64

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[
            {
                "member": "B",
                "reason": "discriminating evidence eliminated B",
                "evidence_receipt_hash": evidence_hash,
            }
        ],
        evidence_receipt_hashes=[evidence_hash],
    )

    assert list(receipt.current_set) == ["A"]


def test_unbound_subtract_receipt_cannot_eliminate_member():
    from holosim.interpretation_set_receipt import InterpretationSetReceipt

    receipt = InterpretationSetReceipt(
        observation_id="obs-001",
        prior_set=["A", "B"],
        ranks={"A": 0.9, "B": 0.1},
        subtract_receipts=[
            {
                "member": "B",
                "reason": "because A seems more likely",
                "evidence_receipt_hash": "e" * 64,
            }
        ],
        evidence_receipt_hashes=[],
    )

    assert list(receipt.current_set) == ["A", "B"]