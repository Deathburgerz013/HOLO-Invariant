from __future__ import annotations

from pathlib import Path

from holosim.canonical import stable_hash
from holosim.software_generator import run_software_generator


def _write_buggy_calculator(workspace: Path) -> None:
    (workspace / "calculator.py").write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )


def _comparator(goal, workspace: Path):
    source = (workspace / "calculator.py").read_text(
        encoding="utf-8",
    )

    if "return a + b" in source:
        return {
            "relevant_difference": False,
            "reason": "NO_RELEVANT_DIFFERENCE",
        }

    return {
        "relevant_difference": True,
        "description": "Fix add so it returns the sum",
    }


def _correct_proposer(
    task,
    observed_starting_state,
    environmental_constraints,
    prior_feedback,
):
    return {
        "files": {
            "calculator.py": (
                "def add(a, b):\n"
                "    return a + b\n"
            )
        }
    }


def _incorrect_proposer(
    task,
    observed_starting_state,
    environmental_constraints,
    prior_feedback,
):
    return {
        "files": {
            "calculator.py": (
                "def add(a, b):\n"
                "    return a * b\n"
            )
        }
    }


def _verifier(workspace: Path):
    namespace: dict = {}

    source = (workspace / "calculator.py").read_text(
        encoding="utf-8",
    )
    exec(source, namespace)

    return {
        "passed": namespace["add"](2, 3) == 5,
        "feedback": "add must return 5 for inputs 2 and 3",
    }


def test_verified_convergence_produces_generation_receipt(
    tmp_path: Path,
) -> None:
    _write_buggy_calculator(tmp_path)

    capability = {
        "id": "calculator.add",
        "requirement": "add must return the sum",
    }

    receipt = run_software_generator(
        capability,
        tmp_path,
        _comparator,
        _correct_proposer,
        _verifier,
    )

    assert receipt["type"] == "software_generation_receipt"
    assert receipt["version"] == 1
    assert receipt["requested_capability"] == capability

    assert receipt["generated"] is True
    assert receipt["converged"] is True
    assert receipt["terminal_reason"] == "NO_RELEVANT_DIFFERENCE"

    assert isinstance(receipt["base_state_hash"], str)
    assert len(receipt["base_state_hash"]) == 64

    assert isinstance(receipt["convergence_receipt_hash"], str)
    assert len(receipt["convergence_receipt_hash"]) == 64

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    assert receipt["receipt_hash"] == stable_hash(body)


def test_failed_convergence_cannot_claim_success(
    tmp_path: Path,
) -> None:
    _write_buggy_calculator(tmp_path)

    receipt = run_software_generator(
        {
            "id": "calculator.add",
            "requirement": "add must return the sum",
        },
        tmp_path,
        _comparator,
        _incorrect_proposer,
        _verifier,
        max_builder_attempts=1,
    )

    assert receipt["generated"] is False
    assert receipt["converged"] is False
    assert receipt["terminal_reason"] == (
        "BUILDER_VERIFICATION_FAILED"
    )

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
