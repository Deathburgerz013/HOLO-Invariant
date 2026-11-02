from copy import deepcopy

import pytest

from tests.test_reconstruction_correction_binding import inputs
from holosim.continuity_under_absence import build_continuity_receipt
from holosim.environment_invariant_receipts import evaluate_environment_invariant
from holosim.reconstruction_correction_binding import (
    ReconstructionCorrectionBindingError,
    build_reconstruction_correction_binding,
)


def test_valid_but_incompatible_history_is_rejected():
    _, _, proposal = inputs()

    alternate_endpoint = deepcopy(proposal["current_claims"])

    alternate_receipt = build_continuity_receipt(
        prior_state=deepcopy(proposal["current_claims"]),
        current_state=alternate_endpoint,
        observer_present_before=True,
        observer_present_after=False,
    )

    alternate_evidence = evaluate_environment_invariant(
        invariant_id="alternate-history",
        statement="alternate endpoint matches observed environment",
        scope={"phase": "adversarial"},
        environment=alternate_endpoint,
        environment_probe=lambda: alternate_endpoint,
        check=lambda: True,
        check_id="alternate-history-check",
        observed_at="2026-11-01T12:00:00-07:00",
    )

    with pytest.raises(
        ReconstructionCorrectionBindingError,
        match="identity mismatch",
    ):
        build_reconstruction_correction_binding(
            continuity_receipt=alternate_receipt,
            external_evidence=alternate_evidence,
            proposal=proposal,
        )
