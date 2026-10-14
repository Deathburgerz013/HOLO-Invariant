from pathlib import Path

from holosim.software_converger import run_software_converger


def test_missing_verification_warrant_cannot_declare_convergence(
    tmp_path: Path,
) -> None:
    def comparator(goal, workspace):
        return {
            "relevant_difference": False,
            "reason": "UNVERIFIED_ABSENCE",
        }

    def forbidden(*args, **kwargs):
        raise AssertionError("unverified comparison must not execute work")

    receipt = run_software_converger(
        "Require verified convergence",
        tmp_path,
        comparator,
        forbidden,
        forbidden,
    )

    assert receipt["converged"] is False
    assert receipt["terminal_reason"] == "UNVERIFIED_COMPARISON"
    assert receipt["build_receipts"] == []
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
