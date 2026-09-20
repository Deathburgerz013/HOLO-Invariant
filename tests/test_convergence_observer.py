from __future__ import annotations

from holosim.convergence_observer import observe_convergence


def test_observer_exposes_one_successful_convergence_run() -> None:
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

    assert observed == {
        "goal": "add must return the sum",
        "status": "CONVERGED",
        "terminal_reason": "NO_RELEVANT_DIFFERENCE",
        "iteration_count": 2,
        "correction_count": 1,
        "receipt_hash": "run-hash-1",
        "iterations": [
            {
                "number": 1,
                "status": "CORRECTED",
                "difference_present": True,
                "difference": "Fix add so it returns the sum",
                "builder_invoked": True,
                "builder_receipt_hash": "build-hash-1",
                "verification_passed": True,
            },
            {
                "number": 2,
                "status": "CONVERGED",
                "difference_present": False,
                "difference": "NO_RELEVANT_DIFFERENCE",
                "builder_invoked": False,
                "builder_receipt_hash": None,
                "verification_passed": None,
            },
        ],
    }
def test_observer_exposes_failed_correction() -> None:
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
            }
        ],
        "build_receipts": [
            {
                "receipt_hash": "build-hash-1",
                "final_verification_state": {
                    "passed": False,
                },
            }
        ],
        "converged": False,
        "terminal_reason": "BUILDER_VERIFICATION_FAILED",
        "receipt_hash": "run-hash-2",
    }

    observed = observe_convergence(receipt)

    assert observed["status"] == "STOPPED"
    assert observed["terminal_reason"] == "BUILDER_VERIFICATION_FAILED"
    assert observed["iteration_count"] == 1
    assert observed["correction_count"] == 0

    assert observed["iterations"] == [
        {
            "number": 1,
            "status": "FAILED",
            "difference_present": True,
            "difference": "Fix add so it returns the sum",
            "builder_invoked": True,
            "builder_receipt_hash": "build-hash-1",
            "verification_passed": False,
        }
    ]