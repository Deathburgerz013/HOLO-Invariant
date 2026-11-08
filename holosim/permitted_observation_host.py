"""Host-owned configuration boundary for permitted observations.

This is an in-process facade, not a security boundary against
arbitrary Python code executing in the same process.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from types import MappingProxyType
from typing import Any, Callable, Mapping

from holosim.permitted_observation_executor import PermittedObservationExecutor


class PermittedObservationHost:
    """Bind permitted observations to host-controlled configuration."""

    def __init__(
        self,
        *,
        permit_registry_path: str | Path,
        allowed_root: str | Path,
        source_secrets: Mapping[str, bytes],
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        registry = Path(permit_registry_path)
        root = Path(allowed_root)

        if not registry.is_absolute():
            raise ValueError("permit registry path must be absolute")

        if not root.is_absolute():
            raise ValueError("allowed root must be absolute")

        resolved_root = root.resolve(strict=True)
        if not resolved_root.is_dir():
            raise ValueError("allowed root must be a directory")

        resolved_registry = registry.resolve(strict=False)
        if resolved_registry.is_relative_to(resolved_root):
            raise ValueError(
                "permit registry must be outside the observation root"
            )

        if not source_secrets:
            raise ValueError("at least one trusted source is required")

        secrets: dict[str, bytes] = {}

        for source_id, secret in source_secrets.items():
            if type(source_id) is not str or not source_id.strip():
                raise ValueError("source_id must be nonempty")

            if type(secret) is not bytes or not secret:
                raise ValueError("source secret must be nonempty bytes")

            secrets[source_id] = bytes(secret)

        self._source_secrets = MappingProxyType(secrets)
        self._allowed_root = resolved_root
        self._executor = PermittedObservationExecutor(
            permit_registry_path=registry
        )
        self._clock = clock if clock is not None else (
            lambda: datetime.now(timezone.utc)
        )

    def observe(
        self,
        *,
        goal_reference: str,
        reference_state: str,
        candidates: Any,
        permit_occurrence: Any,
        expected_content: str,
    ):
        now = self._clock()

        if not isinstance(now, datetime):
            raise ValueError("host clock must return a datetime")

        if now.tzinfo is None or now.utcoffset() is None:
            raise ValueError("host clock must return an aware datetime")

        return self._executor.observe(
            goal_reference=goal_reference,
            reference_state=reference_state,
            candidates=candidates,
            allowed_root=self._allowed_root,
            observed_at=now.isoformat(),
            permit_occurrence=permit_occurrence,
            permit_source_secrets=self._source_secrets,
            seen_occurrence_ids=frozenset(),
            expected_content=expected_content,
        )
