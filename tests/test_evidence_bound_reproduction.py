from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path

import pytest

from holosim.canonical import stable_hash
from holosim.evidence_bound_reproduction import (
    EvidenceBoundReproductionError,
    build_evidence_bound_reproduction,
    validate_evidence_bound_reproduction,
)

FIXTURES = Path(__file__).parent / "fixtures" / "reproduction"
INPUT_KEYS = (
    "reference",
    "baseline_substrate",
    "candidate_substrate",
    "baseline_outcomes",
    "candidate_outcomes",
)


def load_fixture(filename):
    fixture = json.loads((FIXTURES / filename).read_text(encoding="utf-8"))
    return {key: fixture[key] for key in INPUT_KEYS}


@pytest.mark.parametrize(
    "filename,expected",
    [
        ("historical_compression_8f8aa4f.json", "REPRODUCED"),
        ("problems_restructure_d154b49.json", "NOT_REPRODUCED"),
    ],
)
def test_historical_reproduction_replays(filename, expected):
    receipt = build_evidence_bound_reproduction(**load_fixture(filename))
    assert receipt["reproduction"]["status"] == expected
    assert validate_evidence_bound_reproduction(receipt) is True
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == "NONE"


def test_forged_reproduction_with_recomputed_hash_fails():
    receipt = build_evidence_bound_reproduction(
        **load_fixture("problems_restructure_d154b49.json")
    )
    forged = deepcopy(receipt)
    forged["reproduction"]["status"] = "REPRODUCED"
    reproduction_body = {
        key: value
        for key, value in forged["reproduction"].items()
        if key != "reproduction_hash"
    }
    forged["reproduction"]["reproduction_hash"] = stable_hash(reproduction_body)
    forged["verification_hash"] = stable_hash({
        key: value for key, value in forged.items()
        if key != "verification_hash"
    })

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(forged)


def test_changed_evidence_with_recomputed_hash_fails():
    receipt = build_evidence_bound_reproduction(
        **load_fixture("historical_compression_8f8aa4f.json")
    )
    forged = deepcopy(receipt)
    forged["inputs"]["candidate_outcomes"][0]["value"] = False
    forged["verification_hash"] = stable_hash({
        key: value for key, value in forged.items()
        if key != "verification_hash"
    })

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(forged)


def test_missing_field_fails():
    receipt = build_evidence_bound_reproduction(
        **load_fixture("historical_compression_8f8aa4f.json")
    )
    del receipt["inputs"]["baseline_outcomes"]

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(receipt)


def test_added_field_fails():
    receipt = build_evidence_bound_reproduction(
        **load_fixture("historical_compression_8f8aa4f.json")
    )
    receipt["obsolete_implementations"] = ["anything"]

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(receipt)


def test_authority_forgery_fails():
    receipt = build_evidence_bound_reproduction(
        **load_fixture("historical_compression_8f8aa4f.json")
    )
    receipt["accepted"] = True
    receipt["write_authority"] = "GRANTED"
    receipt["verification_hash"] = stable_hash({
        key: value for key, value in receipt.items()
        if key != "verification_hash"
    })

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(receipt)


def test_boolean_integer_identity_tampering_fails():
    receipt = build_evidence_bound_reproduction(
        reference="type-identity",
        baseline_substrate=[],
        candidate_substrate=[],
        baseline_outcomes=[{"id": "x", "value": 1}],
        candidate_outcomes=[{"id": "x", "value": 1}],
    )

    receipt["reproduction"]["baseline_outcome_count"] = True

    with pytest.raises(
        EvidenceBoundReproductionError,
        match="receipt does not match reconstructed evidence",
    ):
        validate_evidence_bound_reproduction(receipt)

def test_malformed_nested_receipt_raises_verifier_error():
    receipt = build_evidence_bound_reproduction(
        reference="malformed-test",
        baseline_substrate=[],
        candidate_substrate=[],
        baseline_outcomes=[],
        candidate_outcomes=[],
    )
    receipt["reproduction"]["baseline_outcome_count"] = {"invalid": {1}}

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(receipt)

def test_cyclic_nested_receipt_raises_verifier_error():
    receipt = build_evidence_bound_reproduction(
        reference="cycle-test",
        baseline_substrate=[],
        candidate_substrate=[],
        baseline_outcomes=[],
        candidate_outcomes=[],
    )
    cycle = {}
    cycle["self"] = cycle
    receipt["reproduction"]["baseline_outcome_count"] = cycle

    with pytest.raises(EvidenceBoundReproductionError):
        validate_evidence_bound_reproduction(receipt)

def test_builder_rejects_unsupported_evidence_with_public_error():
    with pytest.raises(EvidenceBoundReproductionError, match="invalid reproduction inputs"):
        build_evidence_bound_reproduction(
            reference="builder-malformed",
            baseline_substrate=[],
            candidate_substrate=[],
            baseline_outcomes=[{"id": "x", "value": {1}}],
            candidate_outcomes=[],
        )
