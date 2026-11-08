"""Configured boundary for permitted concrete observations."""

from __future__ import annotations

from pathlib import Path
from typing import Any


class PermittedObservationExecutor:
    """Bind observation requests to one configured permit registry.

    The hosting process is responsible for protecting the registry location
    and its persisted contents. This class does not authenticate its caller.
    """

    def __init__(self, *, permit_registry_path: str | Path) -> None:
        path = Path(permit_registry_path)

        if not path.is_absolute():
            raise ValueError("permit registry path must be absolute")

        self._permit_registry_path = path.resolve(strict=False)

    def observe(
        self,
        *,
        goal_reference: str,
        reference_state: str,
        candidates: Any,
        allowed_root: str | Path,
        observed_at: str,
        permit_occurrence: Any,
        permit_source_secrets: Any,
        seen_occurrence_ids: Any,
        expected_content: str,
    ):
        from holosim.concrete_runtime import (
            run_concrete_permitted_observation,
        )

        return run_concrete_permitted_observation(
            goal_reference=goal_reference,
            reference_state=reference_state,
            candidates=candidates,
            allowed_root=allowed_root,
            observed_at=observed_at,
            permit_occurrence=permit_occurrence,
            permit_source_secrets=permit_source_secrets,
            seen_occurrence_ids=seen_occurrence_ids,
            permit_registry_path=self._permit_registry_path,
            expected_content=expected_content,
        )
