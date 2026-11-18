"""Scripted evidence tests; they do not establish real model performance."""
import base64
import json
from copy import deepcopy

import pytest

from holosim.verified_ai_experience import (
    ExperienceEvidenceError, evaluate_experience, verify_experience_comparison,
)

PHASES = ("baseline", "immediate_treatment", "cold_start_control", "cold_start_treatment")


def encoded(value):
    return base64.b64encode(json.dumps(value, separators=(",", ":")).encode()).decode()


def sample(results=(False, True, False, True)):
    contract = {"type": "verified_ai_experience_contract", "version": 1,
                "model_id": "model-a", "correction_id": "correction-1", "tasks": []}
    attempts = []
    for phase, passed in zip(PHASES, results):
        task_id = f"task-{phase}"
        prompt = "Compute withheld case for slot-1"
        contract["tasks"].append({"slot": "slot-1", "phase": phase, "task_id": task_id,
                                  "prompt": prompt, "expected": {"answer": 7}})
        attempts.append({"task_id": task_id, "model_id": "model-a",
                         "correction_exposed": phase in ("immediate_treatment", "cold_start_treatment"),
                         "correction_id": "correction-1" if phase in ("immediate_treatment", "cold_start_treatment") else None,
                         "request_bytes_b64": encoded({"model": "model-a", "prompt": prompt}),
                         "response_bytes_b64": encoded({"model": "model-a", "output": {"answer": 7 if passed else 8}, "error": None})})
    return contract, attempts


def test_reconstructs_improvement_without_claiming_learning():
    contract, attempts = sample()
    result = evaluate_experience(contract, attempts)
    assert result["changes"] == {"newly_solved": 1, "preserved": 0, "regressed": 0, "unresolved": 0}
    assert result["difference_in_gains"] == 1
    assert result["status"] == "EVIDENCE_RELATIVE_COMPARISON_ONLY"
    assert not result["truth_claimed"] and not result["accepted"]
    assert result["write_authority"] == result["execution_authority"] == "NONE"
    assert verify_experience_comparison(contract, attempts, result)


@pytest.mark.parametrize("results,category", [
    ((True, True, True, True), "preserved"),
    ((True, True, True, False), "regressed"),
    ((False, False, False, False), "unresolved"),
])
def test_change_categories(results, category):
    contract, attempts = sample(results)
    assert evaluate_experience(contract, attempts)["changes"][category] == 1


def test_control_improvement_cancels_treatment_gain():
    contract, attempts = sample((False, True, True, True))
    assert evaluate_experience(contract, attempts)["difference_in_gains"] == 0


def test_missing_or_duplicate_attempt_refused():
    contract, attempts = sample()
    with pytest.raises(ExperienceEvidenceError):
        evaluate_experience(contract, attempts[:-1])
    with pytest.raises(ExperienceEvidenceError):
        evaluate_experience(contract, attempts[:-1] + [attempts[0]])


def test_correction_exposure_declaration_refused():
    contract, attempts = sample()
    attempts[0]["correction_exposed"] = True
    with pytest.raises(ExperienceEvidenceError, match="correction"):
        evaluate_experience(contract, attempts)


def test_changed_request_refused():
    contract, attempts = sample()
    attempts[0]["request_bytes_b64"] = encoded({"model": "model-a", "prompt": "changed"})
    with pytest.raises(ExperienceEvidenceError, match="request differs"):
        evaluate_experience(contract, attempts)


def test_changed_model_refused():
    contract, attempts = sample()
    attempts[0]["response_bytes_b64"] = encoded({"model": "other", "output": {"answer": 7}, "error": None})
    with pytest.raises(ExperienceEvidenceError, match="response model"):
        evaluate_experience(contract, attempts)


def test_bool_not_integer():
    contract, attempts = sample()
    attempts[-1]["response_bytes_b64"] = encoded({"model": "model-a", "output": {"answer": True}, "error": None})
    assert not evaluate_experience(contract, attempts)["outcomes"][attempts[-1]["task_id"]]["passed"]


def test_error_is_failed_attempt():
    contract, attempts = sample()
    attempts[-1]["response_bytes_b64"] = encoded({"model": "model-a", "output": None, "error": "timeout"})
    result = evaluate_experience(contract, attempts)
    assert result["phase_counts"]["cold_start_treatment"] == {"passed": 0, "total": 1, "errors": 1}


def test_missing_phase_refused():
    contract, attempts = sample()
    contract["tasks"][-1]["phase"] = "baseline"
    with pytest.raises(ExperienceEvidenceError):
        evaluate_experience(contract, attempts)


def test_tampered_result_refused():
    contract, attempts = sample()
    result = evaluate_experience(contract, attempts)
    result["difference_in_gains"] = 99
    with pytest.raises(ExperienceEvidenceError):
        verify_experience_comparison(contract, attempts, result)


def test_inputs_not_mutated():
    contract, attempts = sample()
    before = deepcopy((contract, attempts))
    evaluate_experience(contract, attempts)
    assert (contract, attempts) == before


def test_fabricated_but_consistent_attempts_remain_unverified():
    contract, attempts = sample()
    result = evaluate_experience(contract, attempts)
    assert result["status"] == "EVIDENCE_RELATIVE_COMPARISON_ONLY"
    assert "no independently authenticated model execution" in result["interpretation_notice"]


def test_mismatched_expected_answers_within_slot_refused():
    contract, attempts = sample()
    contract['tasks'][-1]['expected'] = {'answer': 8}
    with pytest.raises(ExperienceEvidenceError, match='slot'):
        evaluate_experience(contract, attempts)


def test_mismatched_prompts_within_slot_refused():
    contract, attempts = sample()
    contract['tasks'][-1]['prompt'] = 'different prompt'
    with pytest.raises(ExperienceEvidenceError, match='slot'):
        evaluate_experience(contract, attempts)


def test_duplicate_json_keys_refused():
    contract, attempts = sample()
    raw = b'{"model":"other","model":"model-a","prompt":"Compute withheld case for slot-1"}'
    attempts[0]['request_bytes_b64'] = base64.b64encode(raw).decode('ascii')
    with pytest.raises(ExperienceEvidenceError, match='duplicate'):
        evaluate_experience(contract, attempts)
