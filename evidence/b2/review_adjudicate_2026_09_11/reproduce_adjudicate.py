#!/usr/bin/env python3
"""Offline review probes: synthetic measured records, never silicon evidence."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

R = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / 'host'), str(R / 'tests')]
import test_b2_adjudicate as fx
import b2_adjudicate as adj
import b2_records as recs
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT, require_git=False)
import b1_records as common

raw = subprocess.check_output([str(R / 'firmware/b2/build/b2_twin'), 'wire'], text=True)
wire = {s.split(' ', 1)[0]: json.loads(s.split(' ', 1)[1]) for s in raw.splitlines()}
base = fx.modelled_log(0, fx.PAIRS)
# Wrap the model fixture in the twin's per-record common envelopes. These are
# synthetic, internally shaped envelopes, not signed/audited session evidence.
ident = copy.deepcopy(wire['IDENT'])
ident.update(base['app_identity'])
base['app_identity'] = ident
for i, src in enumerate(base['loop_records']):
    r = copy.deepcopy(wire['REC'])
    r.pop('search', None)
    r.pop('arm', None)
    r.update({k: copy.deepcopy(v) for k, v in src.items() if k != 'evidence'})
    r['evidence']['score'] = copy.deepcopy(src['evidence']['score'])
    commit = r['evidence']['score']['hw_candidate_commit']
    r['evidence']['sign_reply'].update(seq=r['seq'], commit=commit)
    r['evidence']['app_oracle_record'].update(seq=r['seq'], staged_sha256=commit, readback_sha256=commit)
    common.validate(r)
    base['loop_records'][i] = r
common.validate(ident)

def judge(logs, plan, pred):
    try:
        result = adj.adjudicate(logs, plan, pred, consts=fx.CONSTS, common=True)
        return {k: result[k] for k in ('outcome', 'findings', 'kills', 'refusal', 'primary') if k in result}
    except Exception as exc:
        return {'exception': type(exc).__name__, 'message': str(exc)}

results = {}
def probe(name, mutate):
    logs, plan, pred = [copy.deepcopy(base)], copy.deepcopy(fx.PLAN), copy.deepcopy(fx.PREDICTION)
    mutate(logs, plan, pred)
    results[name] = judge(logs, plan, pred)

probe('baseline', lambda logs, p, q: None)
probe('log_not_object', lambda logs, p, q: logs.__setitem__(0, []))
probe('seq_list', lambda logs, p, q: logs[0]['loop_records'][2].__setitem__('seq', []))
probe('seq_dict', lambda logs, p, q: logs[0]['loop_records'][2].__setitem__('seq', {}))
probe('records_integer', lambda logs, p, q: logs[0].__setitem__('loop_records', 7))
probe('map_null', lambda logs, p, q: p.__setitem__('map', None))
probe('pairs_string', lambda logs, p, q: p.__setitem__('pairs', '3'))
probe('prediction_pairs_missing', lambda logs, p, q: q.pop('pairs'))
probe('prediction_pairs_null', lambda logs, p, q: q.__setitem__('pairs', None))
probe('prediction_pair_runs_null', lambda logs, p, q: q['pairs'][0].__setitem__('runs', None))
probe('valid_record_bad_digest', lambda logs, p, q: logs[0]['loop_records'][2]['search'].__setitem__('state_sha256', '0'*64))

def change_baseline(logs, index):
    r = logs[0]['loop_records'][index]
    r['genome'] = fx.bc.genome_to_hex(1)
    # Rebind all local commit fields, so the example does not depend on a
    # common-envelope inconsistency. The baseline readout remains zero.
    commit = fx.hashlib.sha256(r['genome'].encode()).hexdigest()
    r['evidence']['sign_reply']['commit'] = commit
    r['evidence']['app_oracle_record'].update(staged_sha256=commit, readback_sha256=commit)
    r['evidence']['score']['hw_candidate_commit'] = commit
    common.validate(r)

probe('opening_nonzero_genome', lambda logs, p, q: change_baseline(logs, 0))
probe('closing_nonzero_genome', lambda logs, p, q: change_baseline(logs, -1))

def kill_then_bad_seq(logs, p, q):
    logs[0]['loop_records'][1]['evidence']['score']['scores'][0] += 1
    logs[0]['loop_records'][2]['seq'] = []
probe('measurement_contradiction_then_bad_seq', kill_then_bad_seq)

ctx = recs.context_from(fx.PLAN, 0, fx.PAIRS)
bad = copy.deepcopy(base)
bad['loop_records'][2]['seq'] = []
results['upstream_record_validator_seq_list'] = {'findings': recs.validate_run_log(bad, ctx)}
with tempfile.TemporaryDirectory(prefix='b2-adjudicate-cli-') as tmp:
    d = Path(tmp)
    for name, data in [('log.json', bad), ('plan.json', fx.PLAN), ('prediction.json', fx.PREDICTION)]:
        (d / name).write_text(json.dumps(data))
    p = subprocess.run([sys.executable, str(R / 'host/b2_adjudicate.py'),
                        '--run-log', str(d / 'log.json'), '--plan', str(d / 'plan.json'),
                        '--prediction', str(d / 'prediction.json'), '--out', str(d / 'result.json')],
                       text=True, capture_output=True)
    results['cli_seq_list'] = dict(returncode=p.returncode, result_written=(d / 'result.json').exists(),
                                   stderr_tail=p.stderr.splitlines()[-3:])
out = {'head': subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
       'common_validation': True, 'synthetic_fixture': True, 'cases': results}
print(json.dumps(out, indent=2))
assert results['baseline']['outcome'] == 'PASS', results['baseline']
