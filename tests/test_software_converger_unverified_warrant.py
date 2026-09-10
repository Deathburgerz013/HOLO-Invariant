"""Falsification test for software-convergence build warrant.

A claimed relevant difference is not enough to warrant production work when
the comparator explicitly says that difference is unverified.

This test does not grant truth, acceptance, write authority, or execution
authority. It only checks whether an unverified difference can currently
trigger the builder.
"""

from pathlib import Path

from holosim.software_converger import run_software_converger


def test_explicitly_unverified_difference_cannot_warrant_builder(
    tmp_path: Path,
) -> None:
    proposer_calls = {"count": 0}
    verifier_calls = {"count": 0}

    def comparator(goal, workspace: Path):
        return {
            "relevant_difference": True,
            "verified": False,
            "description": "A claimed difference that has not been verified.",
        }

    def proposer(
        task,
        observed_starting_state,
        environmental_constraints,
        prior_feedback,
    ):
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
        "Only verified relevant differences may warrant a build.",
        tmp_path,
        comparator,
        proposer,
        verifier,
        max_cycles=1,
    )

    assert proposer_calls["count"] == 0
    assert verifier_calls["count"] == 0
    assert receipt["build_receipts"] == []
    assert receipt["converged"] is False
    assert receipt["terminal_reason"] == "UNVERIFIED_COMPARISON"

    assert len(receipt["cycles"]) == 1
    assert receipt["cycles"][0]["builder_invoked"] is False

    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"