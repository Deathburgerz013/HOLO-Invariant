from __future__ import annotations

from holosim.convergence_observer import observe_convergence
from holosim.convergence_renderer import render_convergence_html


def test_convergence_receipt_renders_through_observer() -> None:
    receipt = {
        "type": "software_converger_receipt",
        "version": 1,
        "goal": "add must return the sum",
        "cycles": [
            {
                "cycle": 1,
                "comparison": {
                    "relevant_difference": True,
                    "description": "Fix add so it returns the sum",
                },
                "builder_invoked": True,
                "builder_receipt_hash": "build-hash-1",
            },
            {
                "cycle": 2,
                "comparison": {
                    "relevant_difference": False,
                    "reason": "NO_RELEVANT_DIFFERENCE",
                },
                "builder_invoked": False,
                "builder_receipt_hash": None,
            },
        ],
        "build_receipts": [
            {
                "receipt_hash": "build-hash-1",
                "final_verification_state": {
                    "passed": True,
                },
            }
        ],
        "converged": True,
        "terminal_reason": "NO_RELEVANT_DIFFERENCE",
        "receipt_hash": "run-hash-1",
    }

    observed = observe_convergence(receipt)
    html = render_convergence_html(observed)

    assert observed["status"] == "CONVERGED"
    assert observed["correction_count"] == 1

    assert "Iteration 1" in html
    assert "CORRECTED" in html
    assert "Iteration 2" in html
    assert "CONVERGED" in html
    assert "Fix add so it returns the sum" in html
    assert "NO_RELEVANT_DIFFERENCE" in html
