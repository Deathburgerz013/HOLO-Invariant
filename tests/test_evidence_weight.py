import math

import pytest

from holosim.canonical import stable_hash
from holosim.evidence_weight import EvidenceWeightError, weigh_observation


def _inputs():
    return {
        "hypothesis_id": "event-happened",
        "alternative_id": "event-did-not-happen",
        "observation_id": "report-1",
        "observation": "A report says the event happened",
        "observation_source_ref": "source-record-1",
        "prior_probability": 0.25,
        "prior_basis_ref": "prior-model-v1",
        "likelihood_given_h": 0.8,
        "likelihood_given_alternative": 0.2,
        "likelihood_basis": "MODEL",
        "basis_ref": "report-model-v1",
    }


def test_two_bits_update_prior_and_preserve_inputs():
    receipt = weigh_observation(**_inputs())
    assert receipt["status"] == "WEIGHTED"
    assert receipt["weight_bits"] == pytest.approx(2.0)
    assert receipt["posterior_probability"] == pytest.approx(4 / 7)
    assert receipt["prior_probability"] == 0.25
    assert receipt["prior_basis_ref"] == "prior-model-v1"
    assert receipt["binary_exhaustive_assumed"] is True
    assert receipt["observation_source_ref"] == "source-record-1"
    assert receipt["likelihood_basis"] == "MODEL"
    assert receipt["basis_ref"] == "report-model-v1"
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"
    assert receipt["receipt_hash"] == stable_hash(
        {key: value for key, value in receipt.items() if key != "receipt_hash"}
    )


def test_equal_likelihoods_leave_prior_unchanged():
    inputs = _inputs()
    inputs["likelihood_given_h"] = 0.6
    inputs["likelihood_given_alternative"] = 0.6
    receipt = weigh_observation(**inputs)
    assert receipt["weight_bits"] == pytest.approx(0.0)
    assert receipt["posterior_probability"] == pytest.approx(0.25)


@pytest.mark.parametrize("missing_field", ["likelihood_given_h", "likelihood_given_alternative"])
def test_missing_likelihood_is_unresolved(missing_field):
    inputs = _inputs()
    inputs[missing_field] = None
    receipt = weigh_observation(**inputs)
    assert receipt["status"] == "UNRESOLVED"
    assert receipt["missing_inputs"] == [missing_field]
    assert receipt["weight_bits"] is None
    assert receipt["posterior_probability"] is None
    assert receipt["accepted"] is False


@pytest.mark.parametrize("bad", [True, -0.1, 0.0, 1.0, float("nan"), float("inf")])
def test_invalid_likelihood_fails_closed(bad):
    inputs = _inputs()
    inputs["likelihood_given_h"] = bad
    with pytest.raises(EvidenceWeightError, match="likelihood_given_h"):
        weigh_observation(**inputs)


def test_missing_model_reference_does_not_claim_weight():
    inputs = _inputs()
    inputs["basis_ref"] = None
    with pytest.raises(EvidenceWeightError, match="basis_ref"):
        weigh_observation(**inputs)


def test_hypothesis_and_alternative_must_be_distinct():
    inputs = _inputs()
    inputs["alternative_id"] = inputs["hypothesis_id"]
    with pytest.raises(EvidenceWeightError, match="distinct"):
        weigh_observation(**inputs)


def test_supplied_unreliable_source_example():
    inputs = _inputs()
    inputs["likelihood_given_h"] = 0.68
    inputs["likelihood_given_alternative"] = 0.32
    receipt = weigh_observation(**inputs)
    assert receipt["weight_bits"] == pytest.approx(math.log2(2.125))


def test_missing_prior_reference_is_rejected():
    inputs = _inputs()
    inputs["prior_basis_ref"] = None
    with pytest.raises(EvidenceWeightError, match="prior_basis_ref"):
        weigh_observation(**inputs)
