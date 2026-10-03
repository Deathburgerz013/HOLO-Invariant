"""Scripted floor checks only; no real model calls."""
import base64
import json
import subprocess
import sys
from copy import deepcopy

import pytest
from holosim.canonical import stable_hash
from holosim.cross_model_correction_handoff import (
    BOUNDARY, load_floor_fixture, run_capability_floor, score_floor_output,
)


class Response:
    def __init__(self, raw): self.raw = raw
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size=-1): return self.raw if size < 0 else self.raw[:size]


class Transport:
    def __init__(self, fail=None):
        self.requests = []
        self.fail = fail
    def __call__(self, request, timeout):
        if isinstance(request, str):
            return Response(json.dumps({'models': [{'name':'a','digest':'a'*64}, {'name':'b','digest':'b'*64}]}).encode())
        body = json.loads(request.data)
        self.requests.append((body, timeout))
        case = next(c for c in load_floor_fixture()['cases'] if c['prompt'] == body['prompt'])
        output = deepcopy(case['expected'])
        if body['model'] == 'b' and case['id'] == self.fail:
            output = {'incorrect': True}
        return Response(json.dumps({'model':body['model'],'done':True,'response':json.dumps(output)}).encode())


def test_frozen_cases_and_arithmetic_oracle():
    f = load_floor_fixture()
    assert [c['id'] for c in f['cases']] == ['schema_echo','id_copy','arithmetic_1','arithmetic_2','arithmetic_3']
    assert [c['expected']['answer'] for c in f['cases'][2:]] == [3,4,0]


def test_equal_fixed_schedule_raw_binding_and_bounds():
    transport = Transport()
    r = run_capability_floor(sender_model='a', receiver_model='b', opener=transport)
    assert len(transport.requests) == len(r['trials']) == 20
    assert all(timeout == 300 for _,timeout in transport.requests)
    assert all(body['options'] == {'num_gpu':0,'num_predict':512,'num_ctx':8192,'seed':0,'temperature':0} for body,_ in transport.requests)
    assert all('context' not in body for body,_ in transport.requests)
    assert [t['call']['model'] for t in r['trials'][:2]] == ['a','b']
    assert [t['call']['model'] for t in r['trials'][10:12]] == ['b','a']
    assert r['trials'][10]['case_id'] == 'arithmetic_3'
    for t in r['trials']:
        call = t['call']
        assert json.loads(base64.b64decode(call['request_bytes_b64']))['prompt'] == call['prompt']
        assert json.loads(json.loads(base64.b64decode(call['response_bytes_b64']))['response']) == call['output']
    assert all(s['eligible_for_this_fixture'] for s in r['summary'].values())
    assert r['ranking'] is None and not r['handoff_executed'] and not r['action_gate_tested']
    assert all(r[k] == v for k,v in BOUNDARY.items())
    assert stable_hash({k:v for k,v in r.items() if k!='result_hash'}) == r['result_hash']


@pytest.mark.parametrize('case_id', ['schema_echo','id_copy','arithmetic_1','arithmetic_2','arithmetic_3'])
def test_one_failed_case_blocks_eligibility_without_dropping_attempts(case_id):
    r = run_capability_floor(sender_model='a', receiver_model='b', opener=Transport(case_id))
    assert r['summary']['a']['eligible_for_this_fixture']
    assert not r['summary']['b']['eligible_for_this_fixture']
    assert r['summary']['b']['confounded_by'] == ['floor_failure']
    assert r['summary']['b']['cases'][case_id] == {'attempts':2,'passed':0}
    assert len(r['trials']) == 20


@pytest.mark.parametrize('actual,expected', [({'answer':False},{'answer':0}), ({'answer':3.0},{'answer':3}),
    ({'answer':3,'accepted':True},{'answer':3}), ({'ids':['record rule-current']},{'ids':['rule-current']}),
    ({'ids':['b','a']},{'ids':['a','b']}), (None,{'answer':0})])
def test_exact_types_structure_ids_and_order(actual,expected):
    before = deepcopy(actual)
    assert not score_floor_output(actual, expected)
    assert actual == before


def test_transport_errors_remain_failed_attempts():
    normal = Transport()
    def broken(request, timeout):
        return normal(request,timeout) if isinstance(request,str) else Response(b'bad JSON')
    r = run_capability_floor(sender_model='a',receiver_model='b',opener=broken)
    assert len(r['trials']) == 20
    assert all(t['call']['error'] and not t['passed'] for t in r['trials'])
    assert all(s['request_errors'] == 10 for s in r['summary'].values())


@pytest.mark.parametrize('model', ['',None,'x'*257])
def test_invalid_identifier_before_inventory(model):
    def forbidden(*args,**kwargs): raise AssertionError('no request allowed')
    with pytest.raises(ValueError): run_capability_floor(sender_model=model,receiver_model='b',opener=forbidden)


def test_modified_fixture_refused(tmp_path):
    f = load_floor_fixture(); f['cases'][2]['expected']['answer'] = 99
    p = tmp_path/'fixture.json';p.write_text(json.dumps(f))
    with pytest.raises(ValueError,match='unsupported'): load_floor_fixture(p)


@pytest.mark.parametrize('extra', [['--num-predict','100'],['--repeats','1'],['--timeout-seconds','300'],['--audit-runs','any']])
def test_cli_refuses_floor_override_or_mixed_modes_before_calls(tmp_path,extra):
    out = tmp_path/'run.json'
    r = subprocess.run([sys.executable,'-m','holosim.cross_model_correction_handoff','--capability-floor',
        '--sender-model','a','--receiver-model','b','--output',str(out),*extra],capture_output=True)
    assert r.returncode != 0 and not out.exists()
