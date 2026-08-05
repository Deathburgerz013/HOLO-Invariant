from pathlib import Path

from holosim.software_converger import run_software_converger


def test_unverified_model_comparison_cannot_control_convergence(tmp_path: Path):
    def comparator(goal, workspace):
        return {
            "relevant_difference": False,
            "reason": "MODEL_SAYS_COMPLETE",
            "description": goal,
            "model_generated": True,
            "verified": False,
            "accepted": False,
            "write_authority": "NONE",
        }

    def proposer(*args, **kwargs):
        raise AssertionError("proposer must not run")

    def verifier(workspace):
        raise AssertionError("verifier must not run")

    result = run_software_converger(
        {"id": "history", "requirement": "track calculation history"},
        tmp_path,
        comparator,
        proposer,
        verifier,
    )

    assert result["converged"] is False
    assert result["terminal_reason"] == "UNVERIFIED_MODEL_COMPARISON"
    assert result["build_receipts"] == []
