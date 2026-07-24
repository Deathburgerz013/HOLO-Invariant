from __future__ import annotations

from pathlib import Path

from holosim.canonical import stable_hash
from holosim.software_converger import run_software_converger


def _write_buggy_calculator(workspace: Path) -> None:
    (workspace / "calculator.py").write_text(
        "def add(a, b):\n"
        "    return a - b\n",
        encoding="utf-8",
    )


def test_already_converged_stops_without_builder(tmp_path: Path) -> None:
    (tmp_path / "calculator.py").write_text(
        "def add(a, b):\n"
        "    return a + b\n",
        encoding="utf-8",
    )

    proposer_calls = {"count": 0}
    verifier_calls = {"count": 0}

    def comparator(goal, workspace: Path):
        source = (workspace / "calculator.py").read_text(
            encoding="utf-8"
        )

        return {
            "relevant_difference": "return a + b" not in source,
            "reason": "NO_RELEVANT_DIFFERENCE",
        }

    def proposer(*args):
        proposer_calls["count"] += 1
        return {
            "files": {
                "calculator.py": (
                    "def add(a, b):\n"
                    "    return a + b\n"
                )
            }
        }

    def verifier(workspace: Path):
        verifier_calls["count"] += 1
        return {"passed": True}

    receipt = run_software_converger(
        "add must return the sum",
        tmp_path,
        comparator,
        proposer,
        verifier,
    )

    assert proposer_calls["count"] == 0
    assert verifier_calls["count"] == 0

    assert receipt["converged"] is True
    assert receipt["terminal_reason"] == "NO_RELEVANT_DIFFERENCE"

    assert len(receipt["cycles"]) == 1
    assert receipt["cycles"][0]["builder_invoked"] is False

    assert receipt["build_receipts"] == []

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    assert receipt["receipt_hash"] == stable_hash(body)


def test_one_real_difference_builds_then_converges(
    tmp_path: Path,
) -> None:
    _write_buggy_calculator(tmp_path)

    comparator_calls = {"count": 0}

    def comparator(goal, workspace: Path):
        comparator_calls["count"] += 1

        source = (workspace / "calculator.py").read_text(
            encoding="utf-8"
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

    def proposer(
        task,
        observed_starting_state,
        environmental_constraints,
        prior_feedback,
    ):
        assert task == "Fix add so it returns the sum"
        assert prior_feedback is None

        return {
            "files": {
                "calculator.py": (
                    "def add(a, b):\n"
                    "    return a + b\n"
                )
            }
        }

    def verifier(workspace: Path):
        namespace: dict = {}
        source = (workspace / "calculator.py").read_text(
            encoding="utf-8"
        )
        exec(source, namespace)

        return {
            "passed": namespace["add"](2, 3) == 5,
        }

    receipt = run_software_converger(
        "add must return the sum",
        tmp_path,
        comparator,
        proposer,
        verifier,
    )

    assert comparator_calls["count"] == 2

    assert receipt["converged"] is True
    assert receipt["terminal_reason"] == "NO_RELEVANT_DIFFERENCE"

    assert len(receipt["cycles"]) == 2

    assert receipt["cycles"][0]["builder_invoked"] is True
    assert receipt["cycles"][1]["builder_invoked"] is False

    assert len(receipt["build_receipts"]) == 1

    build_receipt = receipt["build_receipts"][0]

    assert build_receipt["final_verification_state"]["passed"] is True
    assert len(build_receipt["attempts"]) == 1

    assert receipt["cycles"][0]["builder_receipt_hash"] == (
        build_receipt["receipt_hash"]
    )

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


def test_builder_failure_stops_convergence(tmp_path: Path) -> None:
    _write_buggy_calculator(tmp_path)

    def comparator(goal, workspace: Path):
        return {
            "relevant_difference": True,
            "description": "Fix add so it returns the sum",
        }

    def proposer(
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

    def verifier(workspace: Path):
        return {
            "passed": False,
            "feedback": "implementation still incorrect",
        }

    receipt = run_software_converger(
        "add must return the sum",
        tmp_path,
        comparator,
        proposer,
        verifier,
        max_cycles=3,
        max_builder_attempts=1,
    )

    assert receipt["converged"] is False
    assert receipt["terminal_reason"] == (
        "BUILDER_VERIFICATION_FAILED"
    )

    assert len(receipt["cycles"]) == 1
    assert receipt["cycles"][0]["builder_invoked"] is True

    assert len(receipt["build_receipts"]) == 1
    assert receipt["build_receipts"][0][
        "final_verification_state"
    ]["passed"] is False