from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.letta_memory_proposal_boundary import (
    LettaMemoryBoundaryError,
    create_memory_edit_proposal,
    verify_memory_edit_proposal,
)


CURRENT_VALUE = "User prefers concise technical explanations."


def _edit(**overrides):
    body = {
        "type": "letta_memory_edit",
        "version": 1,
        "agent_id": "agent:holo-adapter",
        "block_id": "block:human",
        "block_label": "human",
        "operation": "replace",
        "prior_value_sha256": stable_hash(CURRENT_VALUE),
        "proposed_value": (
            "User prefers concise technical explanations and exact tests."
        ),
        "observed_at": "2026-08-08T14:00:00-07:00",
        "provenance": {"source_id": "letta:memory-tool-event-1"},
    }
    body.update(overrides)
    return {**body, "edit_id": stable_hash(body)}


def test_memory_edit_becomes_non_authoritative_proposal_without_mutation():
    edit = _edit()
    before = deepcopy(edit)

    proposal = create_memory_edit_proposal(
        edit=edit,
        current_value=CURRENT_VALUE,
    )

    assert edit == before
    assert proposal["source_edit"] == edit
    assert proposal["proposed_value"] == edit["proposed_value"]
    assert proposal["accepted"] is False
    assert proposal["truth_claimed"] is False
    assert proposal["write_authority"] == "NONE"
    assert proposal["execution_authority"] == "NONE"
    assert verify_memory_edit_proposal(proposal)["valid"] is True


def test_rehashed_undeclared_edit_authority_field_is_rejected():
    forged = _edit()
    forged["approval"] = "GRANTED"
    forged["edit_id"] = stable_hash(
        {
            key: value
            for key, value in forged.items()
            if key != "edit_id"
        }
    )

    with pytest.raises(
        LettaMemoryBoundaryError,
        match="unsupported fields",
    ):
        create_memory_edit_proposal(
            edit=forged,
            current_value=CURRENT_VALUE,
        )


def test_stale_memory_edit_is_rejected():
    with pytest.raises(
        LettaMemoryBoundaryError,
        match="different current value",
    ):
        create_memory_edit_proposal(
            edit=_edit(),
            current_value="Memory changed after this edit was proposed.",
        )


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("accepted", True),
        ("truth_claimed", True),
        ("write_authority", "GRANTED"),
        ("execution_authority", "GRANTED"),
    ],
)
def test_verifier_rejects_rehashed_proposal_authority_escalation(
    field,
    value,
):
    proposal = create_memory_edit_proposal(
        edit=_edit(),
        current_value=CURRENT_VALUE,
    )
    proposal[field] = value
    proposal["proposal_id"] = stable_hash(
        {
            key: item
            for key, item in proposal.items()
            if key != "proposal_id"
        }
    )

    result = verify_memory_edit_proposal(proposal)

    assert result["valid"] is False
    assert result["accepted"] is False
    assert result["truth_claimed"] is False
    assert result["write_authority"] == "NONE"
    assert result["execution_authority"] == "NONE"


def test_verifier_rejects_rehashed_undeclared_proposal_field():
    proposal = create_memory_edit_proposal(
        edit=_edit(),
        current_value=CURRENT_VALUE,
    )
    proposal["approval"] = "GRANTED"
    proposal["proposal_id"] = stable_hash(
        {
            key: value
            for key, value in proposal.items()
            if key != "proposal_id"
        }
    )

    result = verify_memory_edit_proposal(proposal)

    assert result["valid"] is False
    assert "unsupported fields" in result["violations"][0]