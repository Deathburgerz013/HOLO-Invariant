from copy import deepcopy

import pytest

from holosim.canonical import stable_hash
from holosim.environment_snapshot import build_snapshot
from holosim.receipt_graph import build_receipt_graph, plan_dependency_rechecks
from holosim.environment_route_gate import RouteGateError, evaluate_route_gate, verify_route_gate_receipt


EVIDENCE = 'a' * 64


def _snapshot(observed=None, *, observed_at='2026-09-25T20:00:00Z', unknown=None, missing=None):
    return build_snapshot(
        episode_id='episode:door', environment_id='building:1',
        check_id='check:lock', check_purpose='Read lock state',
        goal_reference='route:front-door', observer_ids=['observer:lock-sensor'],
        clock_id='clock:1', observed_at=observed_at,
        feature_schema_id='schema:door-v1',
        observed={'door_locked': True} if observed is None else observed,
        missing=[] if missing is None else missing, unknown=[] if unknown is None else unknown,
        assumptions=[], falsifiers=[], evidence_sha256=[EVIDENCE],
        provenance={'source_id': 'lock-sensor:1'}, uncertainty=[],
    )


def _evaluate(snapshot, requirements=None):
    return evaluate_route_gate(
        snapshot=snapshot, route_id='route:front-door',
        required_observations={'door_locked': False} if requirements is None else requirements,
        requirement_basis_ref='route-spec:1',
    )


def test_observed_conflict_is_bound_to_snapshot_time_and_dependencies():
    snapshot = _snapshot()
    receipt = _evaluate(snapshot)
    assert receipt['status'] == 'OBSERVED_CONFLICT'
    assert receipt['conflicting_fields'] == ['door_locked']
    assert receipt['unresolved_fields'] == []
    assert receipt['observed_at'] == snapshot['observed_at']
    assert receipt['environment_id'] == snapshot['environment_id']
    assert receipt['snapshot_id'] == snapshot['snapshot_id']
    assert receipt['evidence_receipt_hashes'] == sorted([
        snapshot['snapshot_id'], EVIDENCE, receipt['requirements_hash'],
    ])
    assert receipt['truth_claimed'] is False
    assert receipt['accepted'] is False
    assert receipt['write_authority'] == 'NONE'
    assert receipt['receipt_hash'] == stable_hash({
        k: v for k, v in receipt.items() if k != 'receipt_hash'
    })


def test_missing_or_explicitly_unknown_requirement_is_unresolved():
    absent = _evaluate(_snapshot(observed={}))
    contradictory = _evaluate(_snapshot(unknown=[{'field': 'door_locked'}]))
    assert absent['status'] == 'UNRESOLVED'
    assert absent['unresolved_fields'] == ['door_locked']
    assert contradictory['status'] == 'UNRESOLVED'
    assert contradictory['conflicting_fields'] == []


def test_compatible_observation_does_not_grant_route_permission():
    receipt = _evaluate(_snapshot(observed={'door_locked': False}))
    assert receipt['status'] == 'OBSERVED_COMPATIBLE'
    assert receipt['accepted'] is False
    assert receipt['write_authority'] == 'NONE'


def test_later_snapshot_changes_result_without_overwriting_old_receipt():
    first = _evaluate(_snapshot())
    second = _evaluate(_snapshot(observed={'door_locked': False}, observed_at='2026-09-25T21:00:00Z'))
    assert first['status'] == 'OBSERVED_CONFLICT'
    assert second['status'] == 'OBSERVED_COMPATIBLE'
    assert first['receipt_hash'] != second['receipt_hash']
    assert first['snapshot_id'] != second['snapshot_id']


def test_corrected_evidence_triggers_recheck_even_without_environment_shift():
    first = _evaluate(_snapshot())
    graph = build_receipt_graph([first])
    plan = plan_dependency_rechecks(graph, [EVIDENCE])
    target = next(item for item in plan['results'] if item['receipt_hash'] == first['receipt_hash'])
    assert target['status'] == 'RECHECK_REQUIRED'


def test_modified_snapshot_and_unsupported_route_requirements_fail_closed():
    snapshot = _snapshot()
    tampered = deepcopy(snapshot)
    tampered['observed']['door_locked'] = False
    with pytest.raises(RouteGateError, match='snapshot'):
        _evaluate(tampered)
    with pytest.raises(RouteGateError, match='required_observations'):
        _evaluate(snapshot, requirements={'door_locked': 0})


def test_receipt_replay_rejects_rehashed_status_forgery():
    snapshot = _snapshot()
    original = _evaluate(snapshot)
    assert verify_route_gate_receipt(original, snapshot)['valid'] is True
    forged = deepcopy(original)
    forged['status'] = 'OBSERVED_COMPATIBLE'
    forged['receipt_hash'] = stable_hash({
        k: v for k, v in forged.items() if k != 'receipt_hash'
    })
    result = verify_route_gate_receipt(forged, snapshot)
    assert result['valid'] is False
    assert any('status' in violation for violation in result['violations'])


@pytest.mark.parametrize('category, marker', [
    ('unknown', 'door_locked'),
    ('unknown', {'claim': 'door_locked'}),
    ('missing', 'door_locked'),
])
def test_unstructured_unknown_marker_cannot_claim_compatibility(category, marker):
    snapshot = _snapshot(
        observed={'door_locked': False}, **{category: [marker]}
    )
    with pytest.raises(RouteGateError, match=f'{category} marker'):
        _evaluate(snapshot)


def test_receipt_replay_rejects_different_snapshot_and_extra_fields():
    snapshot = _snapshot()
    original = _evaluate(snapshot)
    later = _snapshot(observed={'door_locked': False}, observed_at='2026-09-25T21:00:00Z')
    assert verify_route_gate_receipt(original, later)['valid'] is False
    forged = deepcopy(original)
    forged['extra'] = True
    forged['receipt_hash'] = stable_hash({
        k: v for k, v in forged.items() if k != 'receipt_hash'
    })
    assert verify_route_gate_receipt(forged, snapshot)['valid'] is False
