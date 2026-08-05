"""Compose the bounded local Ollama software-convergence path.

This module wires the local capability decomposer, comparator, proposer,
and deterministic Python verifier into the existing request-level
convergence entrypoint.

The composition grants no acceptance, truth, write, or execution authority.
"""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping

from holosim.bounded_python_workspace_verifier import (
    BoundedPythonWorkspaceVerifier,
    build_bounded_python_workspace_verifier,
)
from holosim.local_ollama_adapter import (
    DEFAULT_ENDPOINT,
    DEFAULT_MODEL,
)
from holosim.local_ollama_capability_comparator import (
    LocalOllamaCapabilityComparator,
    build_local_ollama_capability_comparator,
)
from holosim.local_ollama_capability_decomposer import (
    LocalOllamaCapabilityDecomposer,
    build_local_ollama_capability_decomposer,
)
from holosim.local_ollama_capability_proposer import (
    LocalOllamaCapabilityProposer,
    build_local_ollama_capability_proposer,
)
from holosim.software_convergence_entrypoint import (
    run_software_convergence_request,
)


class LocalOllamaSoftwareConvergence:
    """Run one bounded local-model software convergence request."""

    def __init__(
        self,
        *,
        model: str = DEFAULT_MODEL,
        endpoint: str = DEFAULT_ENDPOINT,
        timeout_seconds: float = 120.0,
        verifier_timeout_seconds: float = 30.0,
        max_cycles: int = 3,
        max_builder_attempts: int = 3,
        decomposer: LocalOllamaCapabilityDecomposer | None = None,
        comparator: LocalOllamaCapabilityComparator | None = None,
        proposer: LocalOllamaCapabilityProposer | None = None,
        verifier: BoundedPythonWorkspaceVerifier | None = None,
    ) -> None:
        if (
            not isinstance(max_cycles, int)
            or isinstance(max_cycles, bool)
            or max_cycles < 1
        ):
            raise ValueError("max_cycles must be a positive integer")

        if (
            not isinstance(max_builder_attempts, int)
            or isinstance(max_builder_attempts, bool)
            or max_builder_attempts < 1
        ):
            raise ValueError(
                "max_builder_attempts must be a positive integer"
            )

        self._decomposer = decomposer or (
            build_local_ollama_capability_decomposer(
                model=model,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
            )
        )
        self._comparator = comparator or (
            build_local_ollama_capability_comparator(
                model=model,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
            )
        )
        self._proposer = proposer or (
            build_local_ollama_capability_proposer(
                model=model,
                endpoint=endpoint,
                timeout_seconds=timeout_seconds,
            )
        )
        self._verifier = verifier or (
            build_bounded_python_workspace_verifier(
                timeout_seconds=verifier_timeout_seconds,
            )
        )

        for name, dependency in (
            ("decomposer", self._decomposer),
            ("comparator", self._comparator),
            ("proposer", self._proposer),
            ("verifier", self._verifier),
        ):
            if not callable(dependency):
                raise TypeError(f"{name} must be callable")

        self._max_cycles = max_cycles
        self._max_builder_attempts = max_builder_attempts
        self.last_receipt: dict[str, Any] | None = None

    def __call__(
        self,
        software_request: Any,
        workspace: str | Path,
        *,
        environmental_constraints: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        if (
            environmental_constraints is not None
            and not isinstance(environmental_constraints, Mapping)
        ):
            raise TypeError(
                "environmental_constraints must be a mapping"
            )

        constraints = deepcopy(
            dict(environmental_constraints or {})
        )

        constraints.setdefault("language", "python")
        constraints.setdefault(
            "model_authority",
            "PROPOSAL_ONLY",
        )
        constraints.setdefault(
            "verification_authority",
            "DETERMINISTIC_LOCAL_PROCESS",
        )

        receipt = run_software_convergence_request(
            software_request,
            workspace,
            self._decomposer,
            self._comparator,
            self._proposer,
            self._verifier,
            self._verifier,
            max_cycles=self._max_cycles,
            max_builder_attempts=self._max_builder_attempts,
            environmental_constraints=constraints,
        )

        self.last_receipt = deepcopy(receipt)
        return receipt


def build_local_ollama_software_convergence(
    **kwargs: Any,
) -> LocalOllamaSoftwareConvergence:
    """Build the complete bounded local Ollama convergence callable."""

    return LocalOllamaSoftwareConvergence(**kwargs)


def run_local_ollama_software_convergence(
    software_request: Any,
    workspace: str | Path,
    *,
    environmental_constraints: Mapping[str, Any] | None = None,
    **kwargs: Any,
) -> dict[str, Any]:
    """Build and run one bounded local Ollama convergence request."""

    convergence = build_local_ollama_software_convergence(
        **kwargs,
    )
    return convergence(
        software_request,
        workspace,
        environmental_constraints=environmental_constraints,
    )