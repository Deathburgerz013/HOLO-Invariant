"""Read-only, single-observation likelihood-ratio receipts.

Numbers are conditional on caller-supplied prior and likelihood models.
This evaluator does not verify the models, sources, independence, or truth.
It does not combine multiple observations or grant acceptance.
The supplied hypothesis and alternative are assumed to be exhaustive.
"""

from __future__ import annotations

import math
from typing import Any

from holosim.canonical import stable_hash

RECEIPT_TYPE = "bounded_evidence_weight"
RECEIPT_VERSION = 1


class EvidenceWeightError(ValueError):
    """Raised for malformed or unsupported evidence-weight inputs."""


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise EvidenceWeightError(f"{name} must be a non-empty string")
    return value


def _probability(value: Any, name: str) -> float:
    if type(value) is not float or not math.isfinite(value) or not 0 < value < 1:
        raise EvidenceWeightError(f"{name} must be a finite probability strictly between 0 and 1")
    return float(value)


def weigh_observation(
    *,
    hypothesis_id: str,
    alternative_id: str,
    observation_id: str,
    observation: str,
    observation_source_ref: str,
    prior_probability: float,
    prior_basis_ref: str,
    likelihood_given_h: float | None,
    likelihood_given_alternative: float | None,
    likelihood_basis: str | None,
    basis_ref: str | None,
) -> dict[str, Any]:
    """Compute one conditional update; leave absent likelihoods unresolved.

    A report must be modeled as a report, not as the event it describes.
    Source references identify supplied records; they do not verify them.
    """
    hypothesis = _text(hypothesis_id, "hypothesis_id")
    alternative = _text(alternative_id, "alternative_id")
    if hypothesis == alternative:
        raise EvidenceWeightError("hypothesis_id and alternative_id must be distinct")
    observed_id = _text(observation_id, "observation_id")
    observed = _text(observation, "observation")
    source = _text(observation_source_ref, "observation_source_ref")
    prior = _probability(prior_probability, "prior_probability")
    prior_ref = _text(prior_basis_ref, "prior_basis_ref")

    given_h = None if likelihood_given_h is None else _probability(likelihood_given_h, "likelihood_given_h")
    given_alternative = (
        None if likelihood_given_alternative is None
        else _probability(likelihood_given_alternative, "likelihood_given_alternative")
    )
    basis = None if likelihood_basis is None else _text(likelihood_basis, "likelihood_basis")
    reference = None if basis_ref is None else _text(basis_ref, "basis_ref")
    missing = [
        name for name, value in (
            ("likelihood_given_h", given_h),
            ("likelihood_given_alternative", given_alternative),
        ) if value is None
    ]

    weight_bits: float | None = None
    posterior: float | None = None
    if not missing:
        if basis is None:
            raise EvidenceWeightError("likelihood_basis is required for a weighted result")
        if reference is None:
            raise EvidenceWeightError("basis_ref is required for a weighted result")
        weight_bits = math.log2(given_h) - math.log2(given_alternative)
        log_odds = (
            math.log(prior) - math.log1p(-prior)
            + math.log(given_h) - math.log(given_alternative)
        )
        if log_odds >= 0:
            posterior = 1 / (1 + math.exp(-log_odds))
        else:
            scaled = math.exp(log_odds)
            posterior = scaled / (1 + scaled)

    body = {
        "type": RECEIPT_TYPE,
        "version": RECEIPT_VERSION,
        "hypothesis_id": hypothesis,
        "alternative_id": alternative,
        "observation_id": observed_id,
        "observation": observed,
        "observation_source_ref": source,
        "prior_probability": prior,
        "prior_basis_ref": prior_ref,
        "binary_exhaustive_assumed": True,
        "likelihood_given_h": given_h,
        "likelihood_given_alternative": given_alternative,
        "likelihood_basis": basis,
        "basis_ref": reference,
        "status": "UNRESOLVED" if missing else "WEIGHTED",
        "missing_inputs": missing,
        "weight_bits": weight_bits,
        "posterior_probability": posterior,
        "input_probabilities_verified": False,
        "dependence_verified": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
    }
    return {**body, "receipt_hash": stable_hash(body)}
