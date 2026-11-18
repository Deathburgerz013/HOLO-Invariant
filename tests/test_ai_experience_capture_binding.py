"""Regression tests for evidence-relative Ollama capture binding."""

import base64
import copy
import json

import pytest

from holosim.ai_experience_capture_binding import (
    bind_ollama_capture,
    verify_ollama_capture_binding,
)
from holosim.cross_model_correction_handoff import recorded_call
from holosim.verified_ai_experience import ExperienceEvidenceError


class Response:
    def __init__(self, raw):
        self.raw = raw

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self, size=-1):
        return self.raw if size < 0 else self.raw[:size]


def scripted(request, timeout):
    body = json.loads(request.data)
    envelope = {
        'model': body['model'],
        'done': True,
        'response': json.dumps({'answer': 7}),
        'done_reason': 'stop',
    }
    return Response(json.dumps(envelope).encode('utf-8'))


def sample(phase='baseline'):
    call = recorded_call(
        'Compute', model='model-a', options={'seed': 0},
        timeout=1, opener=scripted,
    )
    assert call['error'] is None
    task = {
        'slot': 's1', 'phase': phase, 'task_id': 't1',
        'prompt': 'Compute', 'expected': {'answer': 7},
    }
    return call, task


def bind(call, task):
    return bind_ollama_capture(
        call, task, model_id='model-a', correction_id='c1',
    )


def verify(call, task, binding):
    return verify_ollama_capture_binding(
        call, task, binding, model_id='model-a', correction_id='c1',
    )


def rewrite_capture(call, field, mutate):
    raw = base64.b64decode(call[field])
    value = json.loads(raw)
    mutate(value)
    call[field] = base64.b64encode(
        json.dumps(value).encode('utf-8')
    ).decode('ascii')


def test_binds_recorded_capture_and_preserves_inputs():
    call, task = sample()
    before_call, before_task = copy.deepcopy(call), copy.deepcopy(task)
    binding = bind(call, task)
    assert binding['attempt']['task_id'] == 't1'
    assert binding['attempt']['correction_exposed'] is False
    assert binding['attempt']['correction_id'] is None
    assert binding['receipt']['execution_authenticated'] is False
    assert binding['receipt']['correction_exposure_verified'] is False
    assert binding['receipt']['learning_claimed'] is False
    assert binding['receipt']['write_authority'] == 'NONE'
    assert verify(call, task, binding) is True
    assert call == before_call
    assert task == before_task


@pytest.mark.parametrize('phase, exposed', [
    ('baseline', False),
    ('immediate_treatment', True),
    ('cold_start_control', False),
    ('cold_start_treatment', True),
])
def test_phase_labels_do_not_claim_verified_exposure(phase, exposed):
    call, task = sample(phase)
    binding = bind(call, task)
    assert binding['attempt']['correction_exposed'] is exposed
    assert binding['attempt']['correction_id'] == ('c1' if exposed else None)
    assert binding['receipt']['correction_exposure_verified'] is False


def test_corrupted_response_byte_rejected():
    call, task = sample()
    raw = bytearray(base64.b64decode(call['response_bytes_b64']))
    raw[-1] ^= 1
    call['response_bytes_b64'] = base64.b64encode(raw).decode('ascii')
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_valid_json_contradictory_output_rejected():
    call, task = sample()
    rewrite_capture(call, 'response_bytes_b64',
                    lambda envelope: envelope.update(response=json.dumps({'answer': 8})))
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


@pytest.mark.parametrize('field, replacement', [
    ('execution_authenticated', True),
    ('correction_exposure_verified', True),
    ('learning_claimed', True),
    ('write_authority', 'ALL'),
    ('source_response_sha256', '0' * 64),
])
def test_forged_receipt_rejected(field, replacement):
    call, task = sample()
    altered = copy.deepcopy(bind(call, task))
    altered['receipt'][field] = replacement
    with pytest.raises(ExperienceEvidenceError):
        verify(call, task, altered)


@pytest.mark.parametrize('field, replacement', [
    ('accepted', True),
    ('truth_claimed', True),
    ('write_authority', 'ALL'),
    ('execution_authority', 'ALL'),
])
def test_source_authority_change_rejected(field, replacement):
    call, task = sample()
    call[field] = replacement
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


@pytest.mark.parametrize('field', ['request_bytes_b64', 'response_bytes_b64'])
def test_missing_capture_rejected(field):
    call, task = sample()
    call[field] = None
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_duplicate_json_key_rejected():
    call, task = sample()
    raw = base64.b64decode(call['response_bytes_b64'])
    assert raw.startswith(b'{')
    raw = b'{"model":"model-a",' + raw[1:]
    call['response_bytes_b64'] = base64.b64encode(raw).decode('ascii')
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_nonfinite_json_constant_rejected():
    call, task = sample()
    raw = base64.b64decode(call['response_bytes_b64'])
    raw = raw[:-1] + b',"unexpected":NaN}'
    call['response_bytes_b64'] = base64.b64encode(raw).decode('ascii')
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_captured_request_prompt_mismatch_rejected():
    call, task = sample()
    rewrite_capture(call, 'request_bytes_b64',
                    lambda request: request.update(prompt='Different'))
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_captured_request_unsupported_option_rejected():
    call, task = sample()
    rewrite_capture(call, 'request_bytes_b64',
                    lambda request: request['options'].update(unknown=1))
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_captured_request_boolean_seed_rejected():
    call, task = sample()
    rewrite_capture(call, 'request_bytes_b64',
                    lambda request: request['options'].update(seed=True))
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_recorded_output_type_change_rejected():
    call, task = sample()
    call['output'] = {'answer': True}
    with pytest.raises(ExperienceEvidenceError):
        bind(call, task)


def test_altered_derived_attempt_rejected():
    call, task = sample()
    altered = copy.deepcopy(bind(call, task))
    altered['attempt']['task_id'] = 'forged-task'
    with pytest.raises(ExperienceEvidenceError):
        verify(call, task, altered)

def test_four_phase_capture_integration():
    from holosim.verified_ai_experience import (
        PHASES,
        evaluate_experience,
        verify_experience_comparison,
    )
    from holosim.ai_experience_capture_binding import (
        verify_ollama_capture_binding,
    )

    model_id = "model-a"
    correction_id = "c1"
    tasks = []
    attempts = []

    for phase in PHASES:
        task = {
            "slot": "s1",
            "phase": phase,
            "task_id": f"t-{phase}",
            "prompt": "Compute",
            "expected": {"answer": 7},
        }
        call = recorded_call(
            "Compute",
            model=model_id,
            options={"seed": 0},
            timeout=1,
            opener=scripted,
        )
        binding = bind_ollama_capture(
            call, task, model_id=model_id, correction_id=correction_id
        )
        assert verify_ollama_capture_binding(
            call, task, binding,
            model_id=model_id,
            correction_id=correction_id,
        )
        assert binding["receipt"]["execution_authenticated"] is False
        assert binding["receipt"]["correction_exposure_verified"] is False
        tasks.append(task)
        attempts.append(binding["attempt"])

    contract = {
        "type": "verified_ai_experience_contract",
        "version": 1,
        "model_id": model_id,
        "correction_id": correction_id,
        "tasks": tasks,
    }
    comparison = evaluate_experience(contract, attempts)

    assert comparison["status"] == "EVIDENCE_RELATIVE_COMPARISON_ONLY"
    assert comparison["difference_in_gains"] == 0
    assert comparison["changes"]["preserved"] == 1
    assert comparison["accepted"] is False
    assert comparison["execution_authority"] == "NONE"
    assert verify_experience_comparison(contract, attempts, comparison)
