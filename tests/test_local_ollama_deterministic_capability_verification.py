from pathlib import Path

from holosim.deterministic_capability_verifier import (
    build_deterministic_capability_verifier,
)
from holosim.local_ollama_software_convergence import (
    build_local_ollama_software_convergence,
)


def test_local_convergence_uses_separate_capability_and_project_verifiers(
    tmp_path: Path,
):
    def decomposer(request, constraints):
        return [
            {
                "id": "calculator.module",
                "requirement": "provide calculator module",
                "depends_on": [],
                "verification": {
                    "required_files": ["main.py"],
                },
            }
        ]

    def comparator(capability, workspace):
        exists = (workspace / "main.py").is_file()

        return {
            "relevant_difference": not exists,
            "reason": (
                "NO_RELEVANT_DIFFERENCE"
                if exists
                else "REQUIRED_FILE_MISSING"
            ),
            "description": capability,
            "verified": True,
            "model_generated": False,
        }

    def proposer(
        task,
        observed_state,
        constraints,
        prior_feedback,
    ):
        return {
            "files": {
                "main.py": (
                    "def add(a, b):\n"
                    "    return a + b\n\n"
                    "if __name__ == '__main__':\n"
                    "    print(add(2, 3))\n"
                ),
            },
            "reason": "Create calculator entrypoint",
        }

    def project_verifier(workspace):
        exists = (workspace / "main.py").is_file()

        return {
            "passed": exists,
            "runnable": exists,
            "command": "python main.py" if exists else None,
            "reason": (
                "PYTHON_VERIFICATION_PASSED"
                if exists
                else "PROJECT_FILE_MISSING"
            ),
        }

    convergence = build_local_ollama_software_convergence(
        decomposer=decomposer,
        comparator=comparator,
        proposer=proposer,
        capability_verifier=(
            build_deterministic_capability_verifier()
        ),
        project_verifier=project_verifier,
        max_cycles=2,
        max_builder_attempts=2,
    )

    result = convergence(
        "build a calculator",
        tmp_path,
    )

    assert result["status"] == "CONVERGED"
    assert result["converged"] is True
    assert result["runnable"] is True
    assert result["completed_capability_ids"] == [
        "calculator.module"
    ]