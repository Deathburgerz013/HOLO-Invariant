from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.reconstructor import ReconstructionError, validate_reconstructed_state


class CarriedNoticeError(ValueError):
    """Raised when carried-notice evidence is invalid."""


def evaluate_carried_notice(
    reconstructed_state: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
    observation: Any,
) -> dict[str, Any]:
    """Evaluate whether verified reconstructed evidence carries prior notice."""

    try:
        validate_reconstructed_state(reconstructed_state, source_items)
    except ReconstructionError as exc:
        raise CarriedNoticeError(
            f"reconstructed state is invalid: {exc}"
        ) from exc

    carried_items = reconstructed_state["carried_items"]

    noticed_items = [
        item
        for item in carried_items
        if item.get("noticed") is True
    ]

    matching_notice = [
        item
        for item in noticed_items
        if item.get("observation") == observation
    ]

    return {
        "observation": observation,
        "prior_notice_present": bool(noticed_items),
        "observation_matches_prior_notice": bool(matching_notice),
        "recognized": bool(matching_notice),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }