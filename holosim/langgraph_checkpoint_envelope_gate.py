"""Fail-closed HOLO gate for LangGraph-shaped checkpoint metadata.

This module intentionally has no LangGraph dependency.  It accepts ordinary
mapping objects shaped like checkpoint metadata and delegates receipt creation
to HOLO's existing exact-schema verifier.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any, Mapping

from holosim.environment_episode_reopen_receipt import (
    EpisodeReopenError,
    create_reopen_receipt,
)


PARENT_ENVELOPE_KEY = "holo_completion_certificate"
TRIGGER_ENVELOPE_KEY = "holo_trigger_snapshot"
REASONS_KEY = "holo_reopen_reasons"
PROVENANCE_KEY = "holo_reopen_provenance"


class CheckpointEnvelopeGateError(ValueError):
    """Raised when checkpoint metadata cannot produce a valid HOLO receipt."""


def _mapping_field(
    metadata: Mapping[str, Any],
    key: str,
) -> dict[str, Any]:
    value = metadata.get(key)
    if not isinstance(value, Mapping):
        raise CheckpointEnvelopeGateError(
            f"checkpoint metadata field {key} must be an object"
        )
    return deepcopy(dict(value))


def create_checkpoint_reopen_receipt(
    *,
    parent_checkpoint_metadata: Mapping[str, Any],
    trigger_checkpoint_metadata: Mapping[str, Any],
) -> dict[str, Any]:
    """Create a reopen receipt from two checkpoint metadata mappings.

    The complete nested envelopes are forwarded without field projection so
    undeclared fields remain visible to HOLO's exact-schema verification.
    Ordinary framework metadata outside the nested HOLO envelopes is ignored.
    """
    if not isinstance(parent_checkpoint_metadata, Mapping):
        raise CheckpointEnvelopeGateError(
            "parent_checkpoint_metadata must be an object"
        )
    if not isinstance(trigger_checkpoint_metadata, Mapping):
        raise CheckpointEnvelopeGateError(
            "trigger_checkpoint_metadata must be an object"
        )

    completion_certificate = _mapping_field(
        parent_checkpoint_metadata,
        PARENT_ENVELOPE_KEY,
    )
    trigger_snapshot = _mapping_field(
        trigger_checkpoint_metadata,
        TRIGGER_ENVELOPE_KEY,
    )
    provenance = _mapping_field(
        trigger_checkpoint_metadata,
        PROVENANCE_KEY,
    )
    reasons = trigger_checkpoint_metadata.get(REASONS_KEY)

    try:
        return create_reopen_receipt(
            completion_certificate=completion_certificate,
            trigger_snapshot=trigger_snapshot,
            relation="reopens",
            reasons=reasons,
            provenance=provenance,
        )
    except EpisodeReopenError as exc:
        raise CheckpointEnvelopeGateError(str(exc)) from exc