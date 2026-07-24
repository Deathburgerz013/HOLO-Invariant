from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from holosim.software_builder import run_software_builder_cycle


def _write_buggy_calculator(workspace: Path) -> None:
    (workspace / "calculator.py").write_text(
        textwrap.dedent(
            """
            def add(a, b):
                return a - b
            """
        ).strip()
        + "\n",
        encoding="utf-8",
    )


def test_first_attempt_success(tmp_path: Path) -> None:
    _write_buggy_calculator(tmp_path)

    def proposer(
        task,
        observed_starting_state,
        environmental_constraints,
        prior_feedback,
    ):
        assert task == "Fix add so it returns the sum"
        assert prior_feedback is None
        assert "workspace_hash" in observed_starting_state

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

        if namespace["add"](2, 3) == 5:
            return {
                "passed": True,
                "message": "addition correct",
            }

        return {
            "passed": False,
            "feedback": "expected add(2, 3) == 5",
        }

    receipt = run_software_builder_cycle(
        "Fix add so it returns the sum",
        tmp_path,
        proposer,
        verifier,
    )

    assert len(receipt["attempts"]) == 1
    assert receipt["attempts"][0]["verification"]["passed"] is True
    assert receipt["attempts"][0]["feedback_used"] is None

    assert receipt["corrections_made"] == []
    assert receipt["feedback_received"] == []
    assert receipt["files_changed"] == ["calculator.py"]

    assert receipt["final_verification_state"]["passed"] is True

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"

    body = {
        key: value
        for key, value in receipt.items()
        if key != "receipt_hash"
    }
    assert receipt["receipt_hash"] == stable_hash(body)


def test_genuine_feedback_correction(tmp_path: Path) -> None:
    _write_buggy_calculator(tmp_path)

    calls = []

    def proposer(
        task,
        observed_starting_state,
        environmental_constraints,
        prior_feedback,
    ):
        calls.append(prior_feedback)

        if len(calls) == 1:
            return {
                "files": {
                    "calculator.py": (
                        "def add(a, b):\n"
                        "    return a * b\n"
                    )
                }
            }

        assert prior_feedback == "expected add(2, 3) == 5"

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

        if namespace["add"](2, 3) == 5:
            return {
                "passed": True,
                "message": "addition correct",
            }

        return {
            "passed": False,
            "feedback": "expected add(2, 3) == 5",
        }

    receipt = run_software_builder_cycle(
        "Fix add so it returns the sum",
        tmp_path,
        proposer,
        verifier,
    )

    assert calls == [
        None,
        "expected add(2, 3) == 5",
    ]

    assert len(receipt["attempts"]) == 2

    assert receipt["attempts"][0]["verification"]["passed"] is False
    assert receipt["attempts"][1]["verification"]["passed"] is True

    assert receipt["attempts"][1]["feedback_used"] == (
        "expected add(2, 3) == 5"
    )

    assert receipt["feedback_received"] == [
        "expected add(2, 3) == 5"
    ]

    assert len(receipt["corrections_made"]) == 1
    assert receipt["corrections_made"][0]["after_attempt"] == 1

    assert receipt["final_verification_state"]["passed"] is True

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


@pytest.mark.parametrize(
    "malicious_path",
    [
        "../escape.py",
        "../../escape.py",
    ],
)
def test_rejects_path_traversal(
    tmp_path: Path,
    malicious_path: str,
) -> None:
    def proposer(*args):
        return {
            "files": {
                malicious_path: "malicious = True\n",
            }
        }

    def verifier(workspace: Path):
        return {"passed": True}

    with pytest.raises(
        ValueError,
        match="escapes workspace",
    ):
        run_software_builder_cycle(
            "attempt traversal",
            tmp_path,
            proposer,
            verifier,
        )


def test_rejects_absolute_path(tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside.py"

    def proposer(*args):
        return {
            "files": {
                str(outside.resolve()): "malicious = True\n",
            }
        }

    def verifier(workspace: Path):
        return {"passed": True}

    with pytest.raises(
        ValueError,
        match="absolute proposed path",
    ):
        run_software_builder_cycle(
            "attempt absolute write",
            tmp_path,
            proposer,
            verifier,
        )

    assert not outside.exists()