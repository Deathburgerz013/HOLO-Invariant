"""End-to-end bounded software convergence example.

A disposable workspace starts with one real behavioral difference.
The converger observes the difference, invokes the bounded builder,
verifies the correction, compares again, and stops when no relevant
difference remains.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from holosim.software_converger import run_software_converger


def main() -> None:
    goal = "add(a, b) must return the sum of its arguments"

    with tempfile.TemporaryDirectory(
        prefix="holosim-software-convergence-"
    ) as temp_dir:
        workspace = Path(temp_dir)

        calculator = workspace / "calculator.py"
        calculator.write_text(
            "def add(a, b):\n"
            "    return a - b\n",
            encoding="utf-8",
        )

        def comparator(goal, workspace: Path):
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

            passed = namespace["add"](2, 3) == 5

            return {
                "passed": passed,
                "message": (
                    "addition correct"
                    if passed
                    else "addition incorrect"
                ),
            }

        receipt = run_software_converger(
            goal,
            workspace,
            comparator,
            proposer,
            verifier,
        )

        print("converged:", receipt["converged"])
        print("terminal_reason:", receipt["terminal_reason"])
        print("cycles:", len(receipt["cycles"]))
        print("builds:", len(receipt["build_receipts"]))


if __name__ == "__main__":
    main()
