from __future__ import annotations

from typing import Any, Mapping, Sequence

from holosim.reconstructor import ReconstructionError, validate_reconstructed_state


class CarriedRegistrationError(ValueError):
    """Raised when carried-registration evidence is invalid."""


def evaluate_verified_carried_registration(
    reconstructed_state: Mapping[str, Any],
    source_items: Sequence[Mapping[str, Any]],
    observation: Any,
) -> dict[str, Any]:
    """Evaluate whether verified reconstructed evidence carries prior registration."""

    try:
        validate_reconstructed_state(reconstructed_state, source_items)
    except ReconstructionError as exc:
        raise CarriedRegistrationError(
            f"reconstructed state is invalid: {exc}"
        ) from exc

    carried_items = reconstructed_state["carried_items"]

    registered_items = [
        item
        for item in carried_items
        if item.get("registered") is True
    ]

    matching_registration = [
        item
        for item in registered_items
        if item.get("observation") == observation
    ]

    return {
        "observation": observation,
        "prior_registration_present": bool(registered_items),
        "observation_matches_prior_registration": bool(matching_registration),
        "recognized": bool(matching_registration),
        "accepted": False,
        "write_authority": "NONE",
        "execution_authority": "NONE",
    }