from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.computer_observer import execute_observation
from holosim.hook_contract import build_hook_request
from holosim.self_correcting_extraction_ledger import (
    ExtractionLedgerError,
    append_extraction,
    build_extraction_ledger,
    validate_extraction_ledger,
)


def _ledger():
    return build_extraction_ledger(
        ledger_id="extraction-ledger-1",
        objective_id="objective:determine-current-meaning",
        context_id="context:repo-main",
    )


def _source(tmp_path, *, name, content):
    (tmp_path / name).write_text(content, encoding="utf-8")
    request = build_hook_request(
        hook_id=f"source:{name}",
        action="read_text",
        reference=name,
        payload={"encoding": "utf-8"},
    )
    result = execute_observation(request=request, allowed_root=tmp_path)
    return request, result


def _append(
    ledger,
    tmp_path,
    *,
    relationship,
    name,
    content,
    meaning_id="meaning:problem-solution",
    problem=None,
    solution=None,
    parent_extraction_id=None,
    recheck_conditions=(),
):
    request, result = _source(tmp_path, name=name, content=content)
    return append_extraction(
        ledger=ledger,
        relationship=relationship,
        meaning_id=meaning_id,
        problem=problem or {"mismatch": "expected and observed differ"},
        solution=solution,
        request=request,
        observation_result=result,
        parent_extraction_id=parent_extraction_id,
        recheck_conditions=list(recheck_conditions),
    )


def test_add_appends_first_meaning_and_continues(tmp_path):
    ledger = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="add.txt",
        content="A witnessed problem and solution.",
        solution={"response": "retain the new distinction"},
    )

    entry = ledger["entries"][0]
    assert entry["extraction_index"] == 1
    assert entry["relationship"] == "ADD"
    assert entry["source_result_hash"] == entry["observation_result"][
        "result_hash"
    ]
    assert ledger["active_extraction_ids"] == [entry["extraction_id"]]
    assert ledger["decision"] == "CONTINUE"
    assert ledger["stop_condition"] is None
    assert ledger["truth_claimed"] is False
    assert ledger["accepted"] is False
    assert ledger["write_authority"] == "NONE"
    assert validate_extraction_ledger(ledger) is True


def test_same_stops_without_duplicating_active_meaning(tmp_path):
    added = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="first.txt",
        content="First expression.",
        solution={"response": "stable meaning"},
    )
    parent = added["entries"][0]["extraction_id"]
    same = _append(
        added,
        tmp_path,
        relationship="SAME",
        name="same.txt",
        content="Equivalent expression.",
        solution={"response": "stable meaning"},
        parent_extraction_id=parent,
    )

    assert same["active_extraction_ids"] == [parent]
    assert same["decision"] == "STOP"
    assert same["stop_condition"] == "NO_NEW_DISTINCTION"


def test_verified_correction_creates_successor_without_rewriting_parent(tmp_path):
    original = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="original.txt",
        content="Original extraction.",
        solution={"response": "initial solution"},
    )
    before = deepcopy(original)
    parent = original["entries"][0]["extraction_id"]
    corrected = _append(
        original,
        tmp_path,
        relationship="CORRECT",
        name="correction.txt",
        content="A witness exposes the omitted condition.",
        solution={"response": "condition-bound solution"},
        parent_extraction_id=parent,
    )

    successor = corrected["entries"][1]
    assert original == before
    assert corrected["entries"][0] == original["entries"][0]
    assert successor["parent_extraction_id"] == parent
    assert corrected["active_extraction_ids"] == [successor["extraction_id"]]
    assert corrected["decision"] == "CONTINUE"


def test_conflict_preserves_parent_and_stops_for_resolution(tmp_path):
    original = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="original.txt",
        content="Original extraction.",
        solution={"response": "first account"},
    )
    parent = original["entries"][0]["extraction_id"]
    conflicted = _append(
        original,
        tmp_path,
        relationship="CONFLICT",
        name="conflict.txt",
        content="A second supported account conflicts.",
        solution={"alternatives": ["first account", "second account"]},
        parent_extraction_id=parent,
        recheck_conditions=["obtain distinguishing evidence"],
    )

    assert conflicted["active_extraction_ids"] == [parent]
    assert conflicted["decision"] == "STOP"
    assert conflicted["stop_condition"] == "CONTRADICTION_REQUIRES_REVIEW"


def test_unknown_stops_and_retains_recheck_condition(tmp_path):
    unknown = _append(
        _ledger(),
        tmp_path,
        relationship="UNKNOWN",
        name="unknown.txt",
        content="The source cannot distinguish the alternatives.",
        solution=None,
        meaning_id="meaning:unresolved",
        recheck_conditions=["new observer becomes available"],
    )

    entry = unknown["entries"][0]
    assert entry["solution"] is None
    assert entry["recheck_conditions"] == ["new observer becomes available"]
    assert unknown["active_extraction_ids"] == []
    assert unknown["decision"] == "STOP"
    assert unknown["stop_condition"] == "BLOCKED_BY_UNCERTAINTY"


def test_no_new_distinction_records_source_without_inventing_meaning(tmp_path):
    request, result = _source(
        tmp_path,
        name="chatter.txt",
        content="Conversation with no objective-relevant distinction.",
    )
    ledger = append_extraction(
        ledger=_ledger(),
        relationship="NO_NEW_DISTINCTION",
        meaning_id=None,
        problem={"question": "did this change current meaning?"},
        solution=None,
        request=request,
        observation_result=result,
        parent_extraction_id=None,
        recheck_conditions=["objective or context changes"],
    )

    assert ledger["entries"][0]["meaning_id"] is None
    assert ledger["active_extraction_ids"] == []
    assert ledger["decision"] == "STOP"
    assert ledger["stop_condition"] == "NO_NEW_DISTINCTION"


def test_reopen_can_continue_from_a_prior_stopped_extraction(tmp_path):
    unknown = _append(
        _ledger(),
        tmp_path,
        relationship="UNKNOWN",
        name="unknown.txt",
        content="Initially unresolved.",
        solution=None,
        meaning_id="meaning:reopenable",
        recheck_conditions=["new evidence"],
    )
    parent = unknown["entries"][0]["extraction_id"]
    reopened = _append(
        unknown,
        tmp_path,
        relationship="REOPEN",
        name="reopen.txt",
        content="New evidence now resolves the earlier unknown.",
        meaning_id="meaning:reopenable",
        solution={"response": "resolved under new evidence"},
        parent_extraction_id=parent,
    )

    assert reopened["entries"][1]["parent_extraction_id"] == parent
    assert reopened["active_extraction_ids"] == [
        reopened["entries"][1]["extraction_id"]
    ]
    assert reopened["decision"] == "CONTINUE"
    assert reopened["stop_condition"] is None


def test_reopen_conflict_retires_its_still_active_ancestor(tmp_path):
    original = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="original-conflict.txt",
        content="Original supported account.",
        solution={"response": "first account"},
    )
    active_parent = original["entries"][0]["extraction_id"]
    conflicted = _append(
        original,
        tmp_path,
        relationship="CONFLICT",
        name="stopped-conflict.txt",
        content="A conflicting account stops extraction.",
        solution={"alternatives": ["first account", "second account"]},
        parent_extraction_id=active_parent,
        recheck_conditions=["obtain distinguishing evidence"],
    )
    conflict_id = conflicted["entries"][1]["extraction_id"]

    reopened = _append(
        conflicted,
        tmp_path,
        relationship="REOPEN",
        name="resolved-conflict.txt",
        content="New evidence resolves the conflict.",
        solution={"response": "resolved account"},
        parent_extraction_id=conflict_id,
    )

    successor = reopened["entries"][2]
    assert successor["parent_extraction_id"] == conflict_id
    assert active_parent not in reopened["active_extraction_ids"]
    assert reopened["active_extraction_ids"] == [successor["extraction_id"]]
    assert validate_extraction_ledger(reopened) is True


def test_reopen_same_retires_its_still_active_ancestor(tmp_path):
    original = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="original-same.txt",
        content="Original supported expression.",
        solution={"response": "stable meaning"},
    )
    active_parent = original["entries"][0]["extraction_id"]
    same = _append(
        original,
        tmp_path,
        relationship="SAME",
        name="stopped-same.txt",
        content="Equivalent expression stops without duplication.",
        solution={"response": "stable meaning"},
        parent_extraction_id=active_parent,
    )
    same_id = same["entries"][1]["extraction_id"]

    reopened = _append(
        same,
        tmp_path,
        relationship="REOPEN",
        name="extended-same.txt",
        content="New evidence adds a distinction to the stopped expression.",
        solution={"response": "meaning with retained distinction"},
        parent_extraction_id=same_id,
    )

    successor = reopened["entries"][2]
    assert successor["parent_extraction_id"] == same_id
    assert active_parent not in reopened["active_extraction_ids"]
    assert reopened["active_extraction_ids"] == [successor["extraction_id"]]
    assert validate_extraction_ledger(reopened) is True


def test_correction_requires_an_existing_active_parent(tmp_path):
    with pytest.raises(ExtractionLedgerError, match="active parent"):
        _append(
            _ledger(),
            tmp_path,
            relationship="CORRECT",
            name="invalid.txt",
            content="Cannot correct an absent extraction.",
            solution={"response": "invalid"},
            parent_extraction_id="missing-parent",
        )


def test_rehashed_undeclared_authority_field_is_rejected(tmp_path):
    ledger = _append(
        _ledger(),
        tmp_path,
        relationship="ADD",
        name="add.txt",
        content="Witness.",
        solution={"response": "meaning"},
    )
    forged = deepcopy(ledger)
    forged["approval"] = "GRANTED"
    body = dict(forged)
    body.pop("ledger_hash")
    forged["ledger_hash"] = stable_hash(body)

    with pytest.raises(ExtractionLedgerError, match="schema"):
        validate_extraction_ledger(forged)


def test_ledger_is_deterministic_for_identical_inputs(tmp_path):
    request, result = _source(
        tmp_path,
        name="stable.txt",
        content="Stable source.",
    )
    initial = _ledger()
    kwargs = {
        "relationship": "ADD",
        "meaning_id": "meaning:stable",
        "problem": {"mismatch": "stable"},
        "solution": {"response": "stable"},
        "request": request,
        "observation_result": result,
        "parent_extraction_id": None,
        "recheck_conditions": [],
    }

    assert append_extraction(ledger=initial, **kwargs) == append_extraction(
        ledger=initial, **kwargs
    )
