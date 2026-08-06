from __future__ import annotations

from pathlib import Path

from holosim.local_ollama_software_convergence import (
    build_local_ollama_software_convergence,
)


def _decomposer(request, constraints):
    return [
        {
            "id": "calculator.module",
            "requirement": "create calculator.add",
            "depends_on": [],
        }
    ]


def _comparator(capability, workspace: Path):
    source_path = workspace / "main.py"
    source = (
        source_path.read_text(encoding="utf-8")
        if source_path.exists()
        else ""
    )

    return {
        "relevant_difference": "def add" not in source,
        "reason": (
            "NO_RELEVANT_DIFFERENCE"
            if "def add" in source
            else "CAPABILITY_MISSING"
        ),
        "description": capability,
    }


def _proposer(
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
            )
        }
    }


def _verifier(workspace: Path):
    source_path = workspace / "main.py"
    passed = (
        source_path.is_file()
        and "def add"
        in source_path.read_text(encoding="utf-8")
    )

    return {
        "passed": passed,
        "runnable": passed,
        "command": "python main.py" if passed else None,
        "reason": (
            "PYTHON_VERIFICATION_PASSED"
            if passed
            else "SOURCE_MISSING"
        ),
    }


def test_local_convergence_forwards_residue_gate(
    tmp_path,
):
    def residue_verifier(
        *,
        preserved_record,
        reconstructed_state,
    ):
        return {
            "verified": False,
            "reason": "RECORDED_CONTRADICTION_OMITTED",
            "omitted_contradiction_ids": [
                "status-conflict"
            ],
        }

    convergence = build_local_ollama_software_convergence(
        decomposer=_decomposer,
        comparator=_comparator,
        proposer=_proposer,
        verifier=_verifier,
        residue_verifier=residue_verifier,
    )

    result = convergence(
        {
            "id": "calculator",
            "requirement": "build a runnable calculator",
        },
        tmp_path,
        preserved_record={
            "contradictions": [
                {
                    "id": "status-conflict",
                    "field": "status",
                    "observed_values": [
                        "ready",
                        "blocked",
                    ],
                }
            ]
        },
    )

    assert result["status"] == (
        "RESIDUE_VERIFICATION_FAILED"
    )
    assert result["terminal_reason"] == (
        "RECORDED_CONTRADICTION_OMITTED"
    )
    assert result["converged"] is False
    assert result["runnable"] is False
    assert result["residue_verification"][
        "verified"
    ] is False