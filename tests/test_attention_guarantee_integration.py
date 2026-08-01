from __future__ import annotations

from holosim.attention_cost_value import build_attention_guarantee
from holosim.guarantee_registry import build_guarantee_registry


def test_attention_decision_registers_its_bounded_guarantee() -> None:
    guarantee = build_attention_guarantee()
    registry = build_guarantee_registry([guarantee])

    assert registry["guarantees"] == [
        {
            "guarantee_id": "attention-cost-value-decision",
            "guarantee_type": "attention-allocation",
            "scope": "holosim.attention_cost_value.evaluate_attention_candidate",
            "dependencies": [
                "finite numeric inputs",
                "explicit additive scoring rule",
                "canonical JSON encoding",
                "SHA-256",
            ],
            "validator": (
                "holosim.attention_cost_value."
                "evaluate_attention_candidate"
            ),
            "failure_condition": (
                "inputs are invalid or the bounded score and decision "
                "cannot be reproduced"
            ),
            "evidence": [
                "holosim/attention_cost_value.py",
                "tests/test_attention_cost_value.py",
            ],
        }
    ]

    assert registry["accepted"] is False
    assert registry["write_authority"] == "NONE"