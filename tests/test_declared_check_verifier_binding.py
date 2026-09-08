from __future__ import annotations

import importlib
from collections.abc import Mapping

from holosim.next_check_organizer import organize_next_checks


def _candidate(condition: str) -> dict:
    result = organize_next_checks([{
        "idx": 1,
        "entry_hash": "hash-1",
        "claim": "A bounded claim requires another check",
        "status": "open",
        "resolution_conditions": [condition],
        "residual_uncertainty": ["The declared check has not been performed"],
        "source_refs": ["source-1"],
    }])
    candidate = result["candidate_checks"][0]
    assert candidate["routing_status"] == "DECLARED_CHECK_AVAILABLE"
    return candidate


def _find_binding_callable():
    module_names = (
        "holosim.next_check_organizer",
        "holosim.next_check_verifier_binding",
        "holosim.declared_check_verifier_binding",
        "holosim.verifier_binding",
    )
    callable_names = (
        "bind_declared_check",
        "bind_next_check",
        "bind_check_verifier",
        "bind_declared_check_verifier",
    )
    for module_name in module_names:
        try:
            module = importlib.import_module(module_name)
        except ModuleNotFoundError:
            continue
        for callable_name in callable_names:
            value = getattr(module, callable_name, None)
            if callable(value):
                return value
    return None


def test_declared_check_requires_explicit_verifier_binding_surface():
    candidate = _candidate("Run replay verifier")
    binder = _find_binding_callable()

    assert binder is not None, (
        "No production callable was found that binds a DECLARED_CHECK_AVAILABLE "
        "candidate to an explicitly identified existing verifier. The organizer "
        "surfaces the declared condition, while existing verifier adapters receive "
        "their verifier from a caller; no checked bridge between those states was found."
    )

    result = binder(candidate, verifier_id=None, available_verifiers={})

    assert isinstance(result, Mapping)
    assert result["bound"] is False
    assert result["binding_status"] == "VERIFIER_ID_REQUIRED"
    assert result["verifier_inferred"] is False
    assert result["execution_authorized"] is False
    assert result["truth_claimed"] is False
    assert result["accepted"] is False
    assert result["write_authority"] == "NONE"
