from holosim.check_identity import build_check_identity
from holosim.declared_verifier_check_identity_binding import (
    bind_declared_verifier_check_identity,
)


def test_binds_exact_declared_verifier_binding_to_exact_check_identity():
    declared_binding = {
        'type': 'declared_check_verifier_binding',
        'version': 1,
        'candidate': {
            'routing_status': 'DECLARED_CHECK_AVAILABLE',
            'condition': 'Compare current environment with baseline',
        },
        'verifier_inferred': False,
        'execution_authorized': False,
        'truth_claimed': False,
        'accepted': False,
        'write_authority': 'NONE',
        'verifier_id': 'environment_snapshot_comparison',
        'bound': True,
        'binding_status': 'DECLARED_VERIFIER_BOUND',
        'verifier_available': True,
    }

    from holosim.canonical import stable_hash
    declared_binding['binding_hash'] = stable_hash(declared_binding)

    check_identity = build_check_identity(
        check_id='check:environment-comparison:1',
        check_type='environment_snapshot_comparison',
        subject={'environment_id': 'env:1'},
        reference_ids=['snapshot:before', 'snapshot:after'],
        scope={'environment_id': 'env:1'},
        evidence_references=[],
        rule_references=[],
        input_state_hash='state:before-after',
    )

    result = bind_declared_verifier_check_identity(
        declared_verifier_binding=declared_binding,
        check_identity=check_identity,
    )

    assert result['declared_verifier_binding_hash'] == declared_binding['binding_hash']
    assert result['verifier_id'] == 'environment_snapshot_comparison'
    assert result['check_id'] == check_identity['check_id']
    assert result['check_identity_hash'] == check_identity['check_identity_hash']
    assert result['execution_claimed'] is False
    assert result['truth_claimed'] is False
    assert result['accepted'] is False
    assert result['write_authority'] == 'NONE'


def test_tampered_declared_verifier_binding_fails_closed():
    declared_binding = {
        "type": "declared_check_verifier_binding",
        "version": 1,
        "verifier_id": "environment_snapshot_comparison",
        "binding_status": "DECLARED_VERIFIER_BOUND",
        "binding_hash": "tampered",
    }

    check_identity = build_check_identity(
        check_id="check:environment-comparison:1",
        check_type="environment_snapshot_comparison",
        subject={"environment_id": "env:1"},
        reference_ids=["snapshot:before", "snapshot:after"],
        scope={"environment_id": "env:1"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before-after",
    )

    try:
        bind_declared_verifier_check_identity(
            declared_verifier_binding=declared_binding,
            check_identity=check_identity,
        )
    except Exception:
        pass
    else:
        raise AssertionError("tampered declared verifier binding must fail closed")


def test_tampered_check_identity_fails_closed():
    from holosim.canonical import stable_hash

    declared_binding = {
        "type": "declared_check_verifier_binding",
        "version": 1,
        "candidate": {
            "routing_status": "DECLARED_CHECK_AVAILABLE",
            "condition": "Compare current environment with baseline",
        },
        "verifier_inferred": False,
        "execution_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "verifier_id": "environment_snapshot_comparison",
        "bound": True,
        "binding_status": "DECLARED_VERIFIER_BOUND",
        "verifier_available": True,
    }
    declared_binding["binding_hash"] = stable_hash(declared_binding)

    check_identity = build_check_identity(
        check_id="check:environment-comparison:1",
        check_type="environment_snapshot_comparison",
        subject={"environment_id": "env:1"},
        reference_ids=["snapshot:before", "snapshot:after"],
        scope={"environment_id": "env:1"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before-after",
    )
    check_identity["check_identity_hash"] = "tampered"

    try:
        bind_declared_verifier_check_identity(
            declared_verifier_binding=declared_binding,
            check_identity=check_identity,
        )
    except Exception:
        pass
    else:
        raise AssertionError("tampered check identity must fail closed")


def test_mismatched_verifier_and_check_type_fails_closed():
    from holosim.canonical import stable_hash

    declared_binding = {
        "type": "declared_check_verifier_binding",
        "version": 1,
        "candidate": {
            "routing_status": "DECLARED_CHECK_AVAILABLE",
            "condition": "Compare current environment with baseline",
        },
        "verifier_inferred": False,
        "execution_authorized": False,
        "truth_claimed": False,
        "accepted": False,
        "write_authority": "NONE",
        "verifier_id": "environment_snapshot_comparison",
        "bound": True,
        "binding_status": "DECLARED_VERIFIER_BOUND",
        "verifier_available": True,
    }
    declared_binding["binding_hash"] = stable_hash(declared_binding)

    check_identity = build_check_identity(
        check_id="check:wrong:1",
        check_type="different_verifier",
        subject={"environment_id": "env:1"},
        reference_ids=["snapshot:before", "snapshot:after"],
        scope={"environment_id": "env:1"},
        evidence_references=[],
        rule_references=[],
        input_state_hash="state:before-after",
    )

    try:
        bind_declared_verifier_check_identity(
            declared_verifier_binding=declared_binding,
            check_identity=check_identity,
        )
    except Exception:
        pass
    else:
        raise AssertionError("mismatched verifier and check type must fail closed")
