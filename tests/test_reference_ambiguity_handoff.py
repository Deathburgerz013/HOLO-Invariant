from copy import deepcopy
import json
import subprocess
import sys

import pytest

from holosim.canonical import stable_hash
from holosim.reference_ambiguity_handoff import (
    ReferenceHandoffError, demo_inputs, evaluate_reference_handoff,
    verify_reference_handoff,
)


def test_shared_name_requires_context_and_conflicting_id_is_not_guessed():
    receipt = evaluate_reference_handoff(**demo_inputs())
    rows = receipt['packet']['resolutions']
    assert [r['status'] for r in rows] == ['AMBIGUOUS', 'RESOLVED', 'RESOLVED', 'CONFLICT']
    assert rows[0]['entity_id'] is None
    assert len(rows[0]['candidate_ids']) == 2
    assert rows[1]['entity_id'] == 'person:canyon-brock-haney'
    assert rows[2]['entity_id'] == 'place:grand-canyon'
    assert rows[3]['entity_id'] is None


@pytest.mark.parametrize('context', [{'scope': 'project:holo'}, {'kind': 'person', 'scope': 'project:holo'}])
def test_scope_can_disambiguate(context):
    inputs = demo_inputs()
    inputs['requests'] = [{'name': 'Canyon', 'context': context, 'entity_id': None}]
    assert evaluate_reference_handoff(**inputs)['packet']['resolutions'][0]['status'] == 'RESOLVED'


@pytest.mark.parametrize('name', ['canyon', ' Canyon ', 'Unknown'])
def test_matching_is_exact_and_unknown_is_not_inferred(name):
    inputs = demo_inputs()
    inputs['requests'] = [{'name': name, 'context': {}, 'entity_id': None}]
    assert evaluate_reference_handoff(**inputs)['packet']['resolutions'][0]['status'] == 'UNAVAILABLE'


def test_explicit_id_selects_only_a_matching_candidate():
    inputs = demo_inputs()
    inputs['requests'][0]['entity_id'] = 'person:canyon-brock-haney'
    assert evaluate_reference_handoff(**inputs)['packet']['resolutions'][0]['status'] == 'RESOLVED'


def test_rename_changes_snapshot_but_not_declared_contribution_binding():
    inputs = demo_inputs()
    before = evaluate_reference_handoff(**inputs)
    inputs['registry'][0]['names'] = ['Anchor']
    after = evaluate_reference_handoff(**inputs)
    assert before['registry_hash'] != after['registry_hash']
    assert before['packet']['attributions'] == after['packet']['attributions']
    assert before['packet']['registry'][0]['names'] == ['Canyon', 'Canyon Brock Haney']
    # Removing one alias changes what a new lookup resolves to; old receipt stays intact.
    assert after['packet']['resolutions'][0]['entity_id'] == 'place:grand-canyon'
    with pytest.raises(ReferenceHandoffError):
        verify_reference_handoff(before, **inputs)


def test_fresh_process_recovers_and_verifies_original_bindings(tmp_path):
    inputs = demo_inputs()
    receipt = evaluate_reference_handoff(**inputs)
    path = tmp_path / 'handoff.json'
    path.write_text(json.dumps({'inputs': inputs, 'receipt': receipt}), encoding='utf-8')
    original = path.read_bytes()
    code = "import json,sys; from holosim.reference_ambiguity_handoff import verify_reference_handoff; p=json.load(open(sys.argv[1],encoding='utf-8')); assert verify_reference_handoff(p['receipt'],**p['inputs']); print(json.dumps(p['receipt']['recovered_packet']))"
    result = subprocess.run([sys.executable, '-c', code, str(path)], capture_output=True, text=True, timeout=15, check=True)
    assert json.loads(result.stdout) == receipt['packet']
    assert path.read_bytes() == original


@pytest.mark.parametrize('change', ['entity', 'contribution', 'accepted', 'authority', 'extra', 'boolean'])
def test_rehashed_receipt_changes_fail_original_input_replay(change):
    inputs = demo_inputs()
    receipt = evaluate_reference_handoff(**inputs)
    if change == 'entity':
        receipt['packet']['resolutions'][1]['entity_id'] = 'place:grand-canyon'
    elif change == 'contribution':
        receipt['packet']['attributions'][0]['contributor_id'] = 'place:grand-canyon'
    elif change == 'accepted':
        receipt['accepted'] = True
    elif change == 'authority':
        receipt['write_authority'] = 'GRANTED'
    elif change == 'extra':
        receipt['extra'] = 1
    else:
        receipt['recovery_equal'] = 1
    receipt['receipt_hash'] = stable_hash({k:v for k,v in receipt.items() if k != 'receipt_hash'})
    with pytest.raises(ReferenceHandoffError):
        verify_reference_handoff(receipt, **inputs)


def test_valid_rebuild_under_substituted_registry_is_not_original_receipt():
    original = demo_inputs()
    changed = deepcopy(original)
    changed['registry'][0]['entity_id'] = 'person:other'
    changed['contributions'][0]['entity_id'] = 'person:other'
    forged = evaluate_reference_handoff(**changed)
    with pytest.raises(ReferenceHandoffError):
        verify_reference_handoff(forged, **original)


def test_no_mutation_or_authority_from_any_resolution():
    inputs = demo_inputs()
    saved = deepcopy(inputs)
    receipt = evaluate_reference_handoff(**inputs)
    assert inputs == saved
    assert receipt['recovery_equal'] is True
    assert receipt['accepted'] is False and receipt['truth_claimed'] is False
    assert receipt['write_authority'] == receipt['execution_authority'] == 'NONE'
    attribution = receipt['packet']['attributions'][0]
    assert attribution['accepted'] is False
    assert attribution['authorship_claimed'] is False


@pytest.mark.parametrize('mutation', ['duplicate', 'names', 'id', 'context', 'unknown', 'oversize', 'extra'])
def test_invalid_inputs_fail_closed(mutation):
    inputs = demo_inputs()
    if mutation == 'duplicate': inputs['registry'].append(deepcopy(inputs['registry'][0]))
    elif mutation == 'names': inputs['registry'][0]['names'] = ['Canyon', 'Canyon']
    elif mutation == 'id': inputs['registry'][0]['entity_id'] = True
    elif mutation == 'context': inputs['requests'][0]['context'] = {'guess': 'person'}
    elif mutation == 'unknown': inputs['contributions'][0]['entity_id'] = 'unknown'
    elif mutation == 'oversize': inputs['requests'] *= 65
    else: inputs['registry'][0]['approved'] = True
    with pytest.raises(ReferenceHandoffError):
        evaluate_reference_handoff(**inputs)


def test_empty_registry_reports_unavailable_and_empty_requests_are_not_completion():
    receipt = evaluate_reference_handoff(registry=[], requests=[{'name':'Canyon','context':{},'entity_id':None}], contributions=[])
    assert receipt['packet']['resolutions'][0]['status'] == 'UNAVAILABLE'
    empty = evaluate_reference_handoff(registry=[], requests=[], contributions=[])
    assert empty['packet']['resolutions'] == []
    assert 'complete' not in empty


def test_context_is_not_enough_when_two_people_share_it():
    inputs = demo_inputs()
    other = deepcopy(inputs['registry'][0])
    other['entity_id'] = 'person:other'
    inputs['registry'].append(other)
    row = evaluate_reference_handoff(**inputs)['packet']['resolutions'][1]
    assert row['status'] == 'AMBIGUOUS' and row['entity_id'] is None


def test_registry_order_does_not_choose_a_winner():
    inputs = demo_inputs()
    before = evaluate_reference_handoff(**inputs)
    inputs['registry'].reverse()
    assert evaluate_reference_handoff(**inputs) == before


@pytest.mark.parametrize('change', ['request', 'role', 'text'])
def test_original_requests_and_contributions_are_bound(change):
    inputs = demo_inputs()
    receipt = evaluate_reference_handoff(**inputs)
    if change == 'request': inputs['requests'][0]['context'] = {'kind':'person'}
    elif change == 'role': inputs['contributions'][0]['role'] = 'approval'
    else: inputs['contributions'][0]['text'] = 'Different contribution'
    with pytest.raises(ReferenceHandoffError):
        verify_reference_handoff(receipt, **inputs)
