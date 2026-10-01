from copy import deepcopy
from itertools import product
import json
import subprocess
import sys

import pytest

from holosim.bounded_knowledge_completeness import (
    KnowledgeCompletenessError, _family, _hash, _investigate,
    run_bounded_knowledge_experiment as run,
    verify_bounded_knowledge_experiment as verify,
)


def spec(worlds=None, family="FULL", budget=8, access=None):
    return {"worlds": worlds if worlds is not None else [[False, True, True, False]],
            "family": family, "query_budget": budget,
            "accessible_inputs": access if access is not None else list(range(4))}


def rehash(receipt):
    receipt["receipt_hash"] = _hash({k: v for k, v in receipt.items() if k != "receipt_hash"})


def test_exhaustive_learning_of_every_three_bit_world():
    for world in product((False, True), repeat=8):
        inputs = spec([list(world)], access=list(range(8)))
        receipt = run(inputs)
        phase = receipt["epochs"][0]
        assert phase["audit"]["complete_for_epoch"] is True
        assert phase["predictions"] == list(world)
        assert len(phase["observations"]) == 8
        assert phase["candidate_count"] == 1
        verify(receipt, inputs)


def test_affine_inference_answers_withheld_inputs_for_every_rule():
    for world in _family(8, "AFFINE"):
        phase = run(spec([list(world)], "AFFINE", 4, list(range(8))))["epochs"][0]
        assert phase["family_contains_world"] is True
        assert phase["audit"]["complete_for_epoch"] is True
        assert len(phase["observations"]) == 4
        assert len(phase["unqueried_inputs"]) == 4


def test_same_observations_cannot_distinguish_unrestricted_worlds():
    a = [False] * 8
    b = a[:]
    b[7] = True
    left = run(spec([a], budget=4, access=list(range(8))))["epochs"][0]
    right = run(spec([b], budget=4, access=list(range(8))))["epochs"][0]
    assert left["observations"] == right["observations"]
    assert left["predictions"] == right["predictions"]
    assert left["candidate_count"] == 16
    assert left["audit"]["unknown_inputs"] == [4, 5, 6, 7]
    assert not left["candidate_agreement_complete"]


def test_wrong_family_can_agree_completely_and_still_be_wrong():
    world = [False] * 8
    world[7] = True
    phase = run(spec([world], "AFFINE", 4, list(range(8))))["epochs"][0]
    assert phase["candidate_agreement_complete"] is True
    assert phase["family_contains_world"] is False
    assert phase["audit"]["wrong_inputs"] == [7]
    assert phase["audit"]["complete_for_epoch"] is False


def test_change_reopens_old_complete_model_and_queries_correct_it():
    a = [False] * 8
    b = a[:]
    b[7] = True
    before = run(spec([a], access=list(range(8))))
    after = run(spec([a, b], access=list(range(8))))
    assert after["history"][:8] == before["history"]
    phase = after["epochs"][1]
    assert phase["stale_model_audit"]["wrong_inputs"] == [7]
    assert phase["change_detected_from_queries"] is True
    assert phase["audit"]["complete_for_epoch"] is True
    assert phase["predictions"] == b
    assert phase["history_length"] == 16
    for i, row in enumerate(after["history"]):
        assert row["parent_event_hash"] == (after["history"][i-1]["event_hash"] if i else None)
        assert row["event_hash"] == _hash({k:v for k,v in row.items() if k != "event_hash"})


def test_unobserved_change_is_not_detected_by_oracle_leak():
    a = [False] * 8
    b = a[:]
    b[7] = True
    phase = run(spec([a, b], "AFFINE", 4, list(range(8))))["epochs"][1]
    assert phase["candidate_agreement_complete"] is True
    assert phase["change_detected_from_queries"] is False
    assert phase["stale_model_audit"]["complete_for_epoch"] is False
    assert phase["audit"]["complete_for_epoch"] is False


def test_inaccessible_inputs_prevent_full_knowledge_despite_budget():
    phase = run(spec(access=[0, 1]))["epochs"][0]
    assert len(phase["observations"]) == 2
    assert phase["audit"]["unknown_inputs"] == [2, 3]
    assert not phase["audit"]["complete_for_epoch"]


def test_zero_budget_is_unknown_not_vacuous_completion():
    phase = run(spec(budget=0))["epochs"][0]
    assert phase["observations"] == []
    assert phase["predictions"] == [None] * 4
    assert phase["audit"]["correct_count"] == 0
    assert not phase["audit"]["complete_for_epoch"]


def test_investigator_receives_only_queried_answers():
    calls = []
    def observe(x):
        calls.append(x)
        return False
    candidates, observations = _investigate(_family(8, "FULL"), 8, [2, 6], 1, observe)
    assert calls == [2]
    assert observations == [{"input": 2, "output": False}]
    assert len(candidates) == 128


def test_inputs_not_mutated_and_authority_not_granted():
    inputs = spec()
    before = deepcopy(inputs)
    receipt = run(inputs)
    assert inputs == before
    assert receipt["accepted"] is False
    assert receipt["truth_claimed"] is False
    assert receipt["write_authority"] == receipt["execution_authority"] == "NONE"


@pytest.mark.parametrize("field,value", [
    ("worlds", []), ("worlds", [[False]*4]*5), ("worlds", [[False]*3]),
    ("worlds", [[0, 1]]), ("worlds", [[False]*2, [False]*4]),
    ("worlds", "no"), ("family", "OTHER"),
    ("query_budget", True), ("query_budget", -1), ("query_budget", 9),
    ("query_budget", 1.5), ("accessible_inputs", [True]),
    ("accessible_inputs", [0, 0]), ("accessible_inputs", [-1]),
    ("accessible_inputs", [4]), ("accessible_inputs", "all"),
])
def test_invalid_bounded_inputs_rejected(field, value):
    inputs = spec()
    inputs[field] = value
    with pytest.raises(KnowledgeCompletenessError):
        run(inputs)


def test_extra_input_field_rejected():
    inputs = spec()
    inputs["authority"] = "WRITE"
    with pytest.raises(KnowledgeCompletenessError):
        run(inputs)


@pytest.mark.parametrize("attack", ["completion", "prediction", "history", "authority", "extra", "type"])
def test_rehashed_forgery_rejected_by_original_input_replay(attack):
    inputs = spec(budget=2)
    receipt = run(inputs)
    if attack == "completion":
        receipt["epochs"][0]["audit"]["complete_for_epoch"] = True
    elif attack == "prediction":
        receipt["epochs"][0]["predictions"][2] = True
    elif attack == "history":
        receipt["history"].pop()
    elif attack == "authority":
        receipt["accepted"] = True
    elif attack == "extra":
        receipt["extra"] = "allowed"
    else:
        receipt["truth_claimed"] = 0
    rehash(receipt)
    with pytest.raises(KnowledgeCompletenessError, match="original inputs"):
        verify(receipt, inputs)


@pytest.mark.parametrize("control", ["world", "budget", "family", "access"])
def test_replay_binds_all_original_controls(control):
    inputs = spec()
    receipt = run(inputs)
    changed = deepcopy(inputs)
    if control == "world":
        changed["worlds"][0][3] = True
    elif control == "budget":
        changed["query_budget"] = 3
    elif control == "family":
        changed["family"] = "AFFINE"
    else:
        changed["accessible_inputs"] = [0, 1]
    with pytest.raises(KnowledgeCompletenessError):
        verify(receipt, changed)


def test_fresh_process_replay():
    inputs = spec()
    receipt = run(inputs)
    code = "import json,sys; from holosim.bounded_knowledge_completeness import verify_bounded_knowledge_experiment as v; p=json.load(sys.stdin); v(p['receipt'],p['inputs']); print('OK')"
    result = subprocess.run([sys.executable, "-c", code],
                            input=json.dumps({"receipt":receipt,"inputs":inputs}),
                            text=True, capture_output=True, check=True)
    assert result.stdout.strip() == "OK"
