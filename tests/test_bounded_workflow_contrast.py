from holosim.bounded_workflow_contrast import run_contrast


def test_precommitted_workflow_contrast():
    result = run_contrast()

    assert len(result["cases"]) == 4
    assert result["incorrect_continuations"] == {"A": 1, "B": 0}
    assert result["unsupported_continuations"] == {"A": 2, "B": 0}
    assert result["false_blocks_clean_b"] == 0
    assert result["executed_checks"] == {
        "A": {"head_binding": 0, "current_gate": 0},
        "B": {"head_binding": 4, "current_gate": 4},
    }

    assert {
        case["case"]: (case["head_status"], case["arm_b"])
        for case in result["cases"]
    } == {
        "CLEAN": ("CURRENT", "CONTINUE"),
        "SUPERSEDED": ("STALE", "BLOCK"),
        "MISSING_REVALIDATION": ("UNKNOWN", "BLOCK"),
        "CONTRADICTED_HEAD": ("INVALID", "BLOCK"),
    }

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"

    for case in result["cases"]:
        assert case["truth_claimed"] is False
        assert case["accepted"] is False
        assert case["write_authority"] == "NONE"
        assert case["execution_authority"] == "NONE"

    for arm in ("A", "B"):
        assert result["decision_time_ns"][arm]["median"] >= 0
        assert result["decision_time_ns"][arm]["max"] >= 0
from unittest.mock import patch

import holosim.bounded_workflow_contrast as contrast


def test_executed_checks_match_actual_invocations():
    original_evaluator = contrast.evaluate_continuity_head_binding
    original_gate = contrast.require_current_continuity

    with (
        patch.object(
            contrast,
            "evaluate_continuity_head_binding",
            wraps=original_evaluator,
        ) as evaluator,
        patch.object(
            contrast,
            "require_current_continuity",
            wraps=original_gate,
        ) as gate,
    ):
        result = contrast.run_contrast()

    assert evaluator.call_count == 4
    assert gate.call_count == 4

    assert result["executed_checks"]["B"] == {
        "head_binding": evaluator.call_count,
        "current_gate": gate.call_count,
    }
    assert result["executed_checks"]["A"] == {
        "head_binding": 0,
        "current_gate": 0,
    }


def test_modified_fixture_is_rejected(tmp_path, monkeypatch):
    import json
    import pytest

    original = json.loads(
        contrast.FIXTURE.read_text(encoding="utf-8")
    )

    original["latest_justified_claim_ids"] = ["tampered-claim"]

    altered = tmp_path / "altered-fixture.json"
    altered.write_text(
        json.dumps(original),
        encoding="utf-8",
    )

    monkeypatch.setattr(contrast, "FIXTURE", altered)

    with pytest.raises(
        ValueError,
        match="continuity fixture integrity mismatch",
    ):
        contrast.run_contrast()


def test_evaluator_authority_violation_is_rejected(monkeypatch):
    import pytest

    original = contrast.evaluate_continuity_head_binding

    for field, forbidden_value in (
        ("truth_claimed", True),
        ("accepted", True),
        ("write_authority", "WRITE"),
    ):
        def violating_evaluator(*, _field=field, _value=forbidden_value, **kwargs):
            result = dict(original(**kwargs))
            result[_field] = _value
            return result

        with monkeypatch.context() as patcher:
            patcher.setattr(
                contrast,
                "evaluate_continuity_head_binding",
                violating_evaluator,
            )

            with pytest.raises(
                ValueError,
                match="head evaluator violated denial contract",
            ):
                contrast.run_contrast()


def test_result_does_not_overstate_evidence():
    result = run_contrast()
    interpretation = result["interpretation"]

    assert interpretation == {
        "demonstrated": "precommitted symbolic head-currentness classification",
        "arm_a_continues_by_construction": True,
        "superseded_claim_detection_demonstrated": False,
        "claim_lineage_consumed_by_evaluator": False,
        "latency_scope": "single decision-timer reading per case",
        "latency_comparison_supported": False,
        "real_world_error_reduction_demonstrated": False,
    }
