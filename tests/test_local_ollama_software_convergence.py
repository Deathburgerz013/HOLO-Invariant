from __future__ import annotations

from pathlib import Path

import pytest

from holosim.local_ollama_software_convergence import (
    build_local_ollama_software_convergence,
    run_local_ollama_software_convergence,
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


def _proposer(task, observed_state, constraints, prior_feedback):
    return {
        "files": {
            "main.py": (
                "def add(a, b):\n"
                "    return a + b\n\n"
                "if __name__ == '__main__':\n"
                "    print(add(2, 3))\n"
            )
        },
        "reason": "Create a runnable calculator entrypoint",
    }


def _verifier(workspace: Path):
    source_path = workspace / "main.py"
    passed = (
        source_path.is_file()
        and "def add" in source_path.read_text(encoding="utf-8")
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
        "feedback": None if passed else "main.py is missing",
    }


def test_composition_wires_complete_local_convergence_path(tmp_path):
    convergence = build_local_ollama_software_convergence(
        decomposer=_decomposer,
        comparator=_comparator,
        proposer=_proposer,
        verifier=_verifier,
        max_cycles=2,
        max_builder_attempts=2,
    )

    result = convergence(
        {
            "id": "calculator",
            "requirement": "build a runnable calculator",
        },
        tmp_path,
        environmental_constraints={
            "python_version": "3.13",
        },
    )

    assert result["status"] == "CONVERGED"
    assert result["converged"] is True
    assert result["runnable"] is True
    assert result["terminal_reason"] == "PROJECT_VERIFIED_RUNNABLE"
    assert result["environmental_constraints"]["language"] == "python"
    assert result["environmental_constraints"]["python_version"] == "3.13"
    assert (
        result["environmental_constraints"]["model_authority"]
        == "PROPOSAL_ONLY"
    )
    assert (
        result["environmental_constraints"]["verification_authority"]
        == "DETERMINISTIC_LOCAL_PROCESS"
    )
    assert (tmp_path / "main.py").is_file()
    assert convergence.last_receipt == result
    assert convergence.last_receipt is not result


def test_existing_constraints_are_not_overwritten(tmp_path):
    convergence = build_local_ollama_software_convergence(
        decomposer=_decomposer,
        comparator=_comparator,
        proposer=_proposer,
        verifier=_verifier,
    )

    result = convergence(
        "request",
        tmp_path,
        environmental_constraints={
            "language": "python-custom",
            "model_authority": "CUSTOM_PROPOSAL_ONLY",
            "verification_authority": "CUSTOM_LOCAL_VERIFIER",
        },
    )

    constraints = result["environmental_constraints"]

    assert constraints["language"] == "python-custom"
    assert constraints["model_authority"] == "CUSTOM_PROPOSAL_ONLY"
    assert (
        constraints["verification_authority"]
        == "CUSTOM_LOCAL_VERIFIER"
    )


def test_function_entrypoint_builds_and_runs_composition(tmp_path):
    result = run_local_ollama_software_convergence(
        "request",
        tmp_path,
        decomposer=_decomposer,
        comparator=_comparator,
        proposer=_proposer,
        verifier=_verifier,
    )

    assert result["converged"] is True
    assert result["runnable"] is True


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        (
            {"max_cycles": 0},
            "max_cycles must be a positive integer",
        ),
        (
            {"max_builder_attempts": 0},
            "max_builder_attempts must be a positive integer",
        ),
    ],
)
def test_invalid_cycle_bounds_are_rejected(kwargs, message):
    with pytest.raises(ValueError, match=message):
        build_local_ollama_software_convergence(**kwargs)


@pytest.mark.parametrize(
    "name",
    [
        "decomposer",
        "comparator",
        "proposer",
        "verifier",
    ],
)
def test_dependencies_must_be_callable(name):
    kwargs = {
        "decomposer": _decomposer,
        "comparator": _comparator,
        "proposer": _proposer,
        "verifier": _verifier,
    }
    kwargs[name] = object()

    with pytest.raises(TypeError, match=f"{name} must be callable"):
        build_local_ollama_software_convergence(**kwargs)


def test_environmental_constraints_must_be_mapping(tmp_path):
    convergence = build_local_ollama_software_convergence(
        decomposer=_decomposer,
        comparator=_comparator,
        proposer=_proposer,
        verifier=_verifier,
    )

    with pytest.raises(
        TypeError,
        match="environmental_constraints must be a mapping",
    ):
        convergence(
            "request",
            tmp_path,
            environmental_constraints=[],
        )