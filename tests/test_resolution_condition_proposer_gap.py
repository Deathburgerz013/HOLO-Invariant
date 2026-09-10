from copy import deepcopy
from importlib import import_module

import pytest


def _unresolved_record():
    return {
        "idx": 1,
        "entry_hash": "a" * 64,
        "claim": "Either interpretation A or interpretation B remains possible.",
        "status": "open",
        "resolution_conditions": [],
        "residual_uncertainty": [
            "Available evidence does not distinguish A from B."
        ],
        "source_refs": ["observation-1"],
    }


def _load_contract():
    try:
        module = import_module("holosim.resolution_condition_proposer")
    except ModuleNotFoundError:
        pytest.fail(
            "No bounded resolution-condition proposal contract exists for "
            "unresolved records that require a discriminator."
        )

    proposer = getattr(module, "propose_resolution_conditions", None)

    assert callable(proposer), (
        "holosim.resolution_condition_proposer must expose "
        "propose_resolution_conditions"
    )

    return module, proposer


def test_external_candidate_can_be_bound_to_unresolved_uncertainty():
    """
    A fuzzy external source may suggest a discriminator.

    HOLO must be able to preserve that suggestion as a bounded proposal
    without treating it as truth, acceptance, execution authority, or a
    resolved uncertainty.
    """

    _, proposer = _load_contract()

    record = _unresolved_record()
    original = deepcopy(record)

    def candidate_source(source_record):
        assert source_record == original

        return {
            "candidate_conditions": [
                {
                    "condition": (
                        "Observe a property whose outcome differs between "
                        "interpretation A and interpretation B."
                    ),
                    "targets_uncertainty": (
                        "Available evidence does not distinguish A from B."
                    ),
                    "rationale": (
                        "A discriminating observation could eliminate at "
                        "least one surviving interpretation."
                    ),
                }
            ]
        }

    result = proposer(
        record,
        candidate_source=candidate_source,
    )

    # Proposal must not mutate the uncertainty record.
    assert record == original

    # The proposal remains bound to the source that caused it to exist.
    assert result["source"]["entry_hash"] == record["entry_hash"]
    assert result["source"]["idx"] == record["idx"]

    # This case has an explicitly supplied candidate, so a permanent
    # "NO_KNOWN_DISCRIMINATOR" stub cannot satisfy the contract.
    assert result["proposal_status"] == "CANDIDATES_PROPOSED"

    assert len(result["candidate_conditions"]) == 1
    candidate = result["candidate_conditions"][0]

    assert candidate["condition"].strip()
    assert (
        candidate["targets_uncertainty"]
        == record["residual_uncertainty"][0]
    )
    assert candidate["rationale"].strip()

    # Proposal is not determination or authority.
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["execution_authorized"] is False
    assert result["write_authority"] == "NONE"

    assert candidate["truth_claimed"] is False
    assert candidate["accepted"] is False
    assert candidate["execution_authorized"] is False
    assert candidate["write_authority"] == "NONE"


def test_empty_candidate_source_does_not_claim_no_discriminator_exists():
    """
    Failure of one bounded proposer to produce a candidate is not proof that
    no discriminator exists.
    """

    _, proposer = _load_contract()

    record = _unresolved_record()

    def candidate_source(_source_record):
        return {
            "candidate_conditions": [],
        }

    result = proposer(
        record,
        candidate_source=candidate_source,
    )

    assert result["proposal_status"] == "NO_CANDIDATE_PROPOSED"
    assert result["candidate_conditions"] == []

    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["execution_authorized"] is False
    assert result["write_authority"] == "NONE"


def test_candidate_cannot_target_uncertainty_not_present_in_source():
    """
    A proposed condition must remain bound to uncertainty actually declared
    by the supplied source record.
    """

    module, proposer = _load_contract()

    error_type = getattr(
        module,
        "ResolutionConditionProposalError",
        None,
    )

    assert isinstance(error_type, type), (
        "holosim.resolution_condition_proposer must expose "
        "ResolutionConditionProposalError"
    )

    record = _unresolved_record()

    def candidate_source(_source_record):
        return {
            "candidate_conditions": [
                {
                    "condition": "Inspect an unrelated property.",
                    "targets_uncertainty": "A different uncertainty.",
                    "rationale": "This does not address the declared gap.",
                }
            ]
        }

    with pytest.raises(error_type):
        proposer(
            record,
            candidate_source=candidate_source,
        )