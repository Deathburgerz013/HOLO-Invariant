from __future__ import annotations

from pathlib import Path

from holosim.convergence_observer import observe_convergence
from holosim.convergence_renderer import render_convergence_html


def main() -> None:
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

    output_path = Path("convergence_observer.html")
    output_path.write_text(html, encoding="utf-8")

    print(f"Wrote {output_path.resolve()}")


if __name__ == "__main__":
    main()