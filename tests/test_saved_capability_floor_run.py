"""Replay retained negative evidence; never call an actual model."""
import base64
import json
import subprocess
import sys
from pathlib import Path

import pytest
from holosim.canonical import canonical_bytes, stable_hash
from holosim.cross_model_correction_handoff import audit_floor_run

SOURCE = Path(__file__).resolve().parents[1]/'benchmarks/cross-model-correction-handoff-runs/handoff-capability-floor-run.json'
SHA = 'aa2887da86176088d610b9438ca9c97ca720058b165128c92aaecf7b7e49ef3d'


def test_saved_negative_results_and_original_bytes():
    before = SOURCE.read_bytes()
    r = audit_floor_run(SOURCE)
    assert r['source_sha256'] == SHA and SOURCE.read_bytes() == before
    assert len(r['rows']) == 20 and sum(row['passed'] for row in r['rows']) == 8
    assert all(not s['eligible_for_this_fixture'] for s in r['summary'].values())
    assert sorted(sum(c['passed'] for c in s['cases'].values()) for s in r['summary'].values()) == [2,6]
    assert not r['accepted'] and not r['truth_claimed'] and r['ranking'] is None
    assert r['write_authority'] == r['execution_authority'] == 'NONE'
    assert stable_hash({k:v for k,v in r.items() if k != 'result_hash'}) == r['result_hash']


def write_run(tmp_path, change, rehash=True):
    run = json.loads(SOURCE.read_bytes());change(run)
    if rehash: run['result_hash'] = stable_hash({k:v for k,v in run.items() if k!='result_hash'})
    path=tmp_path/'altered.json';path.write_bytes(canonical_bytes(run));return path


@pytest.mark.parametrize('change', [
    lambda r:r['trials'][0].update(passed=False),
    lambda r:r['trials'][0]['call'].update(prompt='different'),
    lambda r:r['trials'][0]['call'].update(output={'count':99}),
    lambda r:r['trials'][0]['call'].update(accepted=True),
    lambda r:r['trials'][0]['call'].update(error='unverified failure'),
    lambda r:r['trials'][0].update(repeat=True),
    lambda r:r['trials'].reverse(),
    lambda r:r['trials'].pop(),
    lambda r:r.update(accepted=True),
    lambda r:r.update(handoff_executed=True),
    lambda r:r['budgets'].update(repeats=1),
    lambda r:r['summary'][r['capability_pair']['sender_model']].update(eligible_for_this_fixture=True),
    lambda r:r['model_identities']['declared_digests'].update({'llama3.2:1b':'invented'}),
])
def test_rehashed_binding_score_schedule_and_boundary_changes_refused(tmp_path,change):
    with pytest.raises(ValueError): audit_floor_run(write_run(tmp_path,change))


def test_stale_hash_refused(tmp_path):
    with pytest.raises(ValueError,match='result hash'):
        audit_floor_run(write_run(tmp_path,lambda r:r.update(status='changed'),rehash=False))


def test_request_cpu_override_refused_after_report_rehash(tmp_path):
    def change(r):
        c=r['trials'][0]['call'];req=json.loads(base64.b64decode(c['request_bytes_b64']))
        req['options']['num_gpu']=1;c['request_bytes_b64']=base64.b64encode(json.dumps(req).encode()).decode()
    with pytest.raises(ValueError,match='request binding'): audit_floor_run(write_run(tmp_path,change))


def test_capture_model_substitution_refused_after_report_rehash(tmp_path):
    def change(r):
        c=r['trials'][0]['call'];res=json.loads(base64.b64decode(c['response_bytes_b64']))
        res['model']='different';c['response_bytes_b64']=base64.b64encode(json.dumps(res).encode()).decode()
    with pytest.raises(ValueError,match='response binding'): audit_floor_run(write_run(tmp_path,change))


def test_oversize_refused(tmp_path):
    p=tmp_path/'large.json';p.write_bytes(b'x'*2_097_153)
    with pytest.raises(ValueError,match='exceeds'): audit_floor_run(p)


def test_fresh_process_audit_and_exclusive_output(tmp_path):
    out=tmp_path/'analysis.json'
    cmd=[sys.executable,'-m','holosim.cross_model_correction_handoff','--audit-floor-run',str(SOURCE),'--output',str(out)]
    done=subprocess.run(cmd,capture_output=True,text=True)
    assert done.returncode==0,done.stderr
    assert json.loads(done.stdout)['passed']==8
    assert json.loads(out.read_bytes())==audit_floor_run(SOURCE)
    before=out.read_bytes();again=subprocess.run(cmd,capture_output=True)
    assert again.returncode!=0 and out.read_bytes()==before
