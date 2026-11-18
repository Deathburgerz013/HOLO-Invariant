"""Tests use locally compiled, trusted fixtures; never untrusted bytecode execution."""

import importlib.util
import sys

import pytest

from holosim.verified_decompiler import UnsupportedBytecode, reconstruct_function


pytestmark = pytest.mark.skipif(
    sys.version_info[:2] != (3, 13) or importlib.util.MAGIC_NUMBER != bytes.fromhex('f30d0d0a'),
    reason='CPython 3.13 bytecode required',
)


def _code(source):
    namespace = {}
    exec(compile(source, '<trusted-test-fixture>', 'exec'), namespace)
    return namespace['transform'].__code__, namespace['transform']


def test_reconstruct_and_compare_bounded_inputs():
    code, original = _code('def transform(x):\n    return x * 2 + 1\n')
    result = reconstruct_function(code)
    assert result.status == 'STRUCTURALLY_RECONSTRUCTED'
    assert result.exact_original_source_recovered is False
    assert result.execution_authenticated is False
    assert len(result.instruction_digest) == 64
    namespace = {}
    exec(compile(result.source, '<trusted-reconstruction>', 'exec'), namespace)
    rebuilt = namespace['reconstructed']
    assert all(original(x) == rebuilt(x) for x in (-100, -1, 0, 1, 42, 100))


def test_reconstruction_is_deterministic():
    code, _ = _code('def transform(x):\n    return x * 2 + 1\n')
    assert reconstruct_function(code) == reconstruct_function(code)


def test_rejects_unsupported_call():
    code, _ = _code('def transform(x):\n    return abs(x)\n')
    with pytest.raises(UnsupportedBytecode):
        reconstruct_function(code)


def test_rejects_control_flow():
    code, _ = _code('def transform(x):\n    if x:\n        return 1\n    return 0\n')
    with pytest.raises(UnsupportedBytecode):
        reconstruct_function(code)


def test_rejects_additional_locals():
    code, _ = _code('def transform(x):\n    y = x + 1\n    return y\n')
    with pytest.raises(UnsupportedBytecode):
        reconstruct_function(code)


def test_rejects_non_code():
    with pytest.raises(TypeError):
        reconstruct_function('not code')


def test_round_trip_rejects_instruction_mismatch(monkeypatch):
    import holosim.verified_decompiler as decompiler

    code, _ = _code('def transform(x):\n    return x * 2 + 1\n')
    original = decompiler._normalized_instructions

    def altered(candidate):
        result = original(candidate)
        if candidate is not code:
            return result + (('SYNTHETIC_MISMATCH',),)
        return result

    monkeypatch.setattr(decompiler, '_normalized_instructions', altered)
    with pytest.raises(UnsupportedBytecode, match='Round-trip instruction mismatch'):
        reconstruct_function(code)


def test_round_trip_does_not_execute_function_body():
    code, _ = _code('def transform(x):\n    return x / 0\n')
    with pytest.raises(UnsupportedBytecode, match='Unsupported binary operation'):
        reconstruct_function(code)


def test_rejects_unsupported_signature():
    code, _ = _code('def transform(x, /):\n    return x + 1\n')
    with pytest.raises(UnsupportedBytecode, match='Unsupported function signature'):
        reconstruct_function(code)


def test_rejects_oversized_constant():
    code, _ = _code('def transform(x):\n    return x + ' + repr('z' * 257) + '\n')
    with pytest.raises(UnsupportedBytecode, match='Constant too large'):
        reconstruct_function(code)
