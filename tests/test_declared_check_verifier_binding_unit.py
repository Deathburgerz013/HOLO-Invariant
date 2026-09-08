from __future__ import annotations

from holosim.declared_check_verifier_binding import (
    DeclaredCheckVerifierBindingError,
    bind_declared_check_verifier,
)
from holosim.next_check_organizer import organize_next_checks


def _candidate(condition: str = "Run replay verifier") -> dict:
    result = organize_next_checks([{
        "idx": 1,
        "entry_hash": "hash-1",
        "claim": "A bounded claim requires another check",
        "status": "open",
        "resolution_conditions": [condition],
        "residual_uncertainty": ["The declared check has not been performed"],
        "source_refs": ["source-1"],
    }])
    return result["candidate_checks"][0]


def test_missing_verifier_identity_does_not_infer_from_condition():
    result = bind_declared_check_verifier(
        _candidate(),
        verifier_id=None,
        available_verifiers={"replay_verifier": lambda value: value},
    )
    assert result["bound"] is False
    assert result["binding_status"] == "VERIFIER_ID_REQUIRED"
    assert result["verifier_inferred"] is False
    assert result["execution_authorized"] is False


def test_unknown_explicit_verifier_identity_remains_unbound():
    result = bind_declared_check_verifier(
        _candidate(),
        verifier_id="missing-verifier",
        available_verifiers={"replay_verifier": lambda value: value},
    )
    assert result["bound"] is False
    assert result["binding_status"] == "DECLARED_VERIFIER_UNAVAILABLE"
    assert result["verifier_id"] == "missing-verifier"
    assert result["verifier_inferred"] is False


def test_exact_explicit_identity_binds_supplied_callable_without_execution():
    calls = []

    def verifier(value):
        calls.append(value)
        return {"verified": True}

    result = bind_declared_check_verifier(
        _candidate(),
        verifier_id="replay_verifier",
        available_verifiers={"replay_verifier": verifier},
    )
    assert result["bound"] is True
    assert result["binding_status"] == "DECLARED_VERIFIER_BOUND"
    assert result["verifier_id"] == "replay_verifier"
    assert result["verifier_available"] is True
    assert result["verifier_inferred"] is False
    assert result["execution_authorized"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
    assert calls == []


def test_non_callable_declared_verifier_fails_closed():
    try:
        bind_declared_check_verifier(
            _candidate(),
            verifier_id="replay_verifier",
            available_verifiers={"replay_verifier": object()},
        )
    except DeclaredCheckVerifierBindingError:
        pass
    else:
        raise AssertionError("non-callable declared verifier must fail closed")


def test_binding_is_deterministic_for_same_declared_inputs():
    candidate = _candidate()
    verifiers = {"replay_verifier": lambda value: value}
    first = bind_declared_check_verifier(
        candidate,
        verifier_id="replay_verifier",
        available_verifiers=verifiers,
    )
    second = bind_declared_check_verifier(
        candidate,
        verifier_id="replay_verifier",
        available_verifiers=verifiers,
    )
    assert first == second
