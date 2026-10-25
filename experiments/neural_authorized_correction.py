"""Non-mutating, checkpoint-bound neural correction proposals."""

from __future__ import annotations

from typing import Any, Mapping

from experiments.neural_checkpoint import capture_checkpoint, verify_checkpoint
from experiments.neural_correction import Perceptron
from holosim.canonical import stable_hash
from holosim.typed_operational_authorization import (
    ACTION_NEURAL_WEIGHT_CORRECTION,
    validate_operational_authorization,
)


PROPOSAL_TYPE = "holo_neural_correction_proposal"
PROPOSAL_VERSION = 1


def propose_neural_correction(
    checkpoint: Mapping[str, Any],
    *,
    inputs: tuple[int, ...],
    expected: int,
) -> dict[str, Any]:
    """Propose an exact transition without mutating the supplied checkpoint."""
    verify_checkpoint(checkpoint)

    if type(inputs) is not tuple:
        raise ValueError("inputs must be a tuple")
    if type(expected) is not int or expected not in (0, 1):
        raise ValueError("expected must be binary")

    model = Perceptron(checkpoint["dimensions"])
    model.weights = list(checkpoint["weights"])
    model.bias = checkpoint["bias"]

    changed = model.correct(inputs, expected)

    after = capture_checkpoint(model, checkpoint["objective"])

    body = {
        "type": PROPOSAL_TYPE,
        "version": PROPOSAL_VERSION,
        "before_checkpoint_hash": checkpoint["checkpoint_hash"],
        "after_checkpoint_hash": after["checkpoint_hash"],
        "inputs": list(inputs),
        "expected": expected,
        "changed": changed,
    }

    return {
        **body,
        "proposal_hash": stable_hash(body),
        "after_checkpoint": after,
        "accepted": False,
        "write_authority": "NONE",
        "truth_claimed": False,
    }



def verify_neural_correction_proposal(
    checkpoint: Mapping[str, Any],
    proposal: Mapping[str, Any],
) -> bool:
    """Recompute the exact proposed transition from the original checkpoint."""
    verify_checkpoint(checkpoint)

    if type(proposal) is not dict:
        raise ValueError("proposal must be a dictionary")

    required = {
        "type", "version", "before_checkpoint_hash",
        "after_checkpoint_hash", "inputs", "expected", "changed",
        "proposal_hash", "after_checkpoint", "accepted",
        "write_authority", "truth_claimed",
    }

    if set(proposal) != required:
        raise ValueError("proposal fields mismatch")

    if (
        proposal["type"] != PROPOSAL_TYPE
        or type(proposal["version"]) is not int
        or proposal["version"] != PROPOSAL_VERSION
        or proposal["accepted"] is not False
        or proposal["write_authority"] != "NONE"
        or proposal["truth_claimed"] is not False
        or type(proposal["inputs"]) is not list
        or type(proposal["changed"]) is not bool
    ):
        raise ValueError("invalid proposal contract")

    try:
        rebuilt = propose_neural_correction(
            checkpoint,
            inputs=tuple(proposal["inputs"]),
            expected=proposal["expected"],
        )
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid proposal transition") from exc

    if proposal != rebuilt:
        raise ValueError("proposal does not match deterministic reconstruction")

    return True



def verify_authorized_neural_correction(
    checkpoint: Mapping[str, Any],
    proposal: Mapping[str, Any],
    authorization: Mapping[str, Any],
) -> bool:
    """Verify an exact declaration, without consuming or executing it.

    The authorization record does not authenticate the external issuer.
    This function grants no mutation or replay protection.
    """
    verify_neural_correction_proposal(checkpoint, proposal)

    validate_operational_authorization(
        authorization,
        expected_action=ACTION_NEURAL_WEIGHT_CORRECTION,
        expected_target_sha256=proposal["proposal_hash"],
    )

    return True
