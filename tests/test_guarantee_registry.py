from __future__ import annotations

from holosim.guarantee_registry import build_guarantee_registry


def test_registry_exposes_one_bounded_guarantee() -> None:
    registry = build_guarantee_registry(
        [
            {
                "guarantee_id": "truth-state-integrity",
                "guarantee_type": "integrity",
                "scope": "holosim.truth.validate_truth_state",
                "dependencies": [
                    "canonical JSON encoding",
                    "SHA-256",
                    "validated truth-state schema",
                ],
                "validator": "holosim.truth.validate_truth_state",
                "failure_condition": "truth-state fields or canonical hash differ",
                "evidence": [
                    "holosim/truth.py",
                    "tests/test_truth.py",
                ],
            }
        ]
    )

    assert registry["type"] == "holo_guarantee_registry"
    assert registry["version"] == 1
    assert registry["accepted"] is False
    assert registry["write_authority"] == "NONE"

    assert registry["guarantees"] == [
        {
            "guarantee_id": "truth-state-integrity",
            "guarantee_type": "integrity",
            "scope": "holosim.truth.validate_truth_state",
            "dependencies": [
                "canonical JSON encoding",
                "SHA-256",
                "validated truth-state schema",
            ],
            "validator": "holosim.truth.validate_truth_state",
            "failure_condition": "truth-state fields or canonical hash differ",
            "evidence": [
                "holosim/truth.py",
                "tests/test_truth.py",
            ],
        }
    ]

    assert isinstance(registry["registry_hash"], str)
    assert len(registry["registry_hash"]) == 64
from copy import deepcopy

import pytest

from holosim.guarantee_registry import (
    GuaranteeRegistryError,
    build_guarantee_registry,
)


def _guarantee() -> dict[str, object]:
    return {
        "guarantee_id": "truth-state-integrity",
        "guarantee_type": "integrity",
        "scope": "holosim.truth.validate_truth_state",
        "dependencies": [
            "canonical JSON encoding",
            "SHA-256",
            "validated truth-state schema",
        ],
        "validator": "holosim.truth.validate_truth_state",
        "failure_condition": "truth-state fields or canonical hash differ",
        "evidence": [
            "holosim/truth.py",
            "tests/test_truth.py",
        ],
    }


def test_registry_rejects_duplicate_guarantee_ids() -> None:
    first = _guarantee()
    duplicate = deepcopy(first)

    with pytest.raises(
        GuaranteeRegistryError,
        match="duplicate guarantee_id",
    ):
        build_guarantee_registry([first, duplicate])


def test_registry_rejects_missing_dependencies() -> None:
    guarantee = _guarantee()
    guarantee["dependencies"] = []

    with pytest.raises(
        GuaranteeRegistryError,
        match="dependencies must be a non-empty sequence",
    ):
        build_guarantee_registry([guarantee])