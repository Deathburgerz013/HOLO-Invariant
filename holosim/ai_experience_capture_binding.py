"""Bind recorded Ollama transport bytes to an AI-experience evaluator attempt.

This proves consistency of supplied records, not independent execution,
correction delivery, or learning. It grants no authority.
"""

import base64
import binascii
import hashlib
import json
import math

from holosim.canonical import stable_hash
from holosim.verified_ai_experience import EXPOSED, MAX_RAW_BYTES, ExperienceEvidenceError

MAX_CAPTURE_BYTES = 262144
MAX_PROMPT_BYTES = 49152
BOUNDARY = {
    'accepted': False,
    'truth_claimed': False,
    'write_authority': 'NONE',
    'execution_authority': 'NONE',
}
CALL_KEYS = frozenset({
    'model', 'prompt', 'prompt_sha256', 'output', 'error',
    'elapsed_seconds', 'request_bytes_b64', 'response_bytes_b64',
    *BOUNDARY,
})
TASK_KEYS = frozenset({'slot', 'phase', 'task_id', 'prompt', 'expected'})
REQUEST_KEYS = frozenset({'model', 'prompt', 'stream', 'format', 'options'})
OPTION_KEYS = frozenset({'num_gpu', 'num_predict', 'num_ctx', 'seed', 'temperature'})


def _reject(reason):
    raise ExperienceEvidenceError(reason)


def _pairs_unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            _reject('duplicate JSON key')
        result[key] = value
    return result


def _reject_constant(value):
    _reject('nonfinite JSON constant')


def _parse_json(raw):
    try:
        value = json.loads(raw.decode('utf-8'), object_pairs_hook=_pairs_unique,
                           parse_constant=_reject_constant)
    except (UnicodeError, ValueError, RecursionError) as exc:
        raise ExperienceEvidenceError('invalid captured JSON') from exc
    _canonical(value)  # Reject overflows and other non-finite representations.
    return value


def _canonical(value):
    try:
        return json.dumps(value, sort_keys=True, ensure_ascii=False,
                          separators=(',', ':'), allow_nan=False).encode('utf-8')
    except (TypeError, ValueError, UnicodeError, OverflowError, RecursionError) as exc:
        raise ExperienceEvidenceError('noncanonical JSON value') from exc


def _strict_equal(left, right):
    return _canonical(left) == _canonical(right)


def _capture(encoded):
    if type(encoded) is not str or len(encoded) > ((MAX_CAPTURE_BYTES + 2) // 3) * 4:
        _reject('capture missing or exceeds encoded bound')
    try:
        raw = base64.b64decode(encoded, validate=True)
    except (ValueError, binascii.Error) as exc:
        raise ExperienceEvidenceError('invalid base64 capture') from exc
    if not raw or len(raw) > MAX_CAPTURE_BYTES:
        _reject('capture outside raw bound')
    return raw, _parse_json(raw)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _derive(value):
    raw = _canonical(value)
    if len(raw) > MAX_RAW_BYTES:
        _reject('derived evidence exceeds evaluator bound')
    return base64.b64encode(raw).decode('ascii'), _sha(raw)


def _identifier(value):
    if type(value) is not str or not value or len(value) > 128:
        _reject('invalid identifier')


def _check_options(options):
    if type(options) is not dict or not set(options) <= OPTION_KEYS:
        _reject('invalid generation options')
    if type(options.get('num_gpu')) is not int or options['num_gpu'] != 0:
        _reject('GPU option mismatch')
    for name, low, high in (
        ('num_predict', 1, 2048), ('num_ctx', 512, 32768),
        ('seed', 0, 2147483647),
    ):
        if name in options and (type(options[name]) is not int
                                or not low <= options[name] <= high):
            _reject('generation option outside bound')
    if 'temperature' in options:
        value = options['temperature']
        if type(value) not in (int, float) or not math.isfinite(value) or not 0 <= value <= 2:
            _reject('temperature outside bound')


def bind_ollama_capture(call, task, *, model_id, correction_id):
    """Verify supplied capture consistency and derive a bounded attempt.

    The phase's correction-exposure flag is a contract label, not proof that
    correction text was actually presented to a model.
    """
    if type(call) is not dict or set(call) != CALL_KEYS:
        _reject('recorded call schema mismatch')
    if type(task) is not dict or set(task) != TASK_KEYS:
        _reject('task schema mismatch')
    for value in (model_id, correction_id, task['slot'], task['task_id']):
        _identifier(value)
    if type(task['phase']) is not str or task['phase'] not in EXPOSED:
        _reject('unknown experimental phase')
    prompt = task['prompt']
    if type(prompt) is not str or not prompt or len(prompt.encode('utf-8')) > MAX_PROMPT_BYTES:
        _reject('invalid task prompt')
    for key, expected in BOUNDARY.items():
        if type(call[key]) is not type(expected) or call[key] != expected:
            _reject('recorded call authority mismatch')
    if call['error'] is not None:
        _reject('failed recorded call')
    elapsed = call['elapsed_seconds']
    if type(elapsed) not in (int, float) or not math.isfinite(elapsed) or elapsed < 0:
        _reject('invalid elapsed duration')
    if (type(call['model']) is not str or call['model'] != model_id
            or type(call['prompt']) is not str or call['prompt'] != prompt
            or type(call['prompt_sha256']) is not str
            or call['prompt_sha256'] != stable_hash(prompt)):
        _reject('recorded call metadata mismatch')

    raw_request, request = _capture(call['request_bytes_b64'])
    raw_response, envelope = _capture(call['response_bytes_b64'])
    if type(request) is not dict or set(request) != REQUEST_KEYS:
        _reject('unexpected request schema')
    if (type(request['model']) is not str or request['model'] != model_id
            or type(request['prompt']) is not str or request['prompt'] != prompt
            or request['stream'] is not False or request['format'] != 'json'):
        _reject('captured request mismatch')
    _check_options(request['options'])

    if type(envelope) is not dict or envelope.get('model') != model_id:
        _reject('captured response model mismatch')
    if envelope.get('done') is not True or type(envelope.get('response')) is not str:
        _reject('incomplete or invalid response')
    output = _parse_json(envelope['response'].encode('utf-8'))
    if type(output) is not dict or type(call['output']) is not dict:
        _reject('model output must be a JSON object')
    if not _strict_equal(output, call['output']):
        _reject('recorded output does not match response bytes')

    request_b64, request_sha = _derive({'model': model_id, 'prompt': prompt})
    response_b64, response_sha = _derive({
        'model': model_id, 'output': output, 'error': None,
    })
    exposed = EXPOSED[task['phase']]
    attempt = {
        'task_id': task['task_id'],
        'model_id': model_id,
        'correction_exposed': exposed,
        'correction_id': correction_id if exposed else None,
        'request_bytes_b64': request_b64,
        'response_bytes_b64': response_b64,
    }
    receipt = {
        'type': 'ai_experience_capture_binding',
        'version': 1,
        'task_id': task['task_id'],
        'source_request_sha256': _sha(raw_request),
        'source_response_sha256': _sha(raw_response),
        'derived_request_sha256': request_sha,
        'derived_response_sha256': response_sha,
        'correction_exposure_verified': False,
        'execution_authenticated': False,
        'learning_claimed': False,
        **BOUNDARY,
    }
    return {'attempt': attempt, 'receipt': receipt}


def verify_ollama_capture_binding(call, task, binding, *, model_id, correction_id):
    """Reconstruct the complete binding and reject altered fields."""
    expected = bind_ollama_capture(call, task, model_id=model_id,
                                   correction_id=correction_id)
    if type(binding) is not dict or not _strict_equal(binding, expected):
        _reject('binding does not match supplied capture')
    return True
