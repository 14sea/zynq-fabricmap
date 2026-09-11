#!/usr/bin/env python3
"""Independent follow-up probes for the adjudicator's input guards; offline only."""
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile

R = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path[:0] = [str(R / 'host'), str(R / 'tests')]
import test_b2_adjudicate as f
import b2_adjudicate as a
f.BlankBaselines.setUpClass()
base = f.BlankBaselines.whole
results = {}

def probe(name, mutate):
    logs, plan, pred = [copy.deepcopy(base)], copy.deepcopy(f.PLAN), copy.deepcopy(f.PREDICTION)
    mutate(logs, plan, pred)
    try:
        out = a.adjudicate(logs, plan, pred, consts=f.CONSTS, common=True)
        results[name] = {k: out[k] for k in ('outcome','findings','kills','primary','refusal','replay') if k in out}
    except Exception as exc:
        results[name] = {'exception': type(exc).__name__, 'message': str(exc)}

probe('baseline', lambda l,p,q: None)
for value in [[], {}, ['F1'], {'name':'F1'}]:
    probe('fitness_'+repr(value), lambda l,p,q,v=value: p.__setitem__('fitness',v))
probe('unknown_fitness_control', lambda l,p,q:p.__setitem__('fitness','F9'))
probe('prediction_budget_float', lambda l,p,q:q.__setitem__('budget_per_arm',float(p['budget_per_arm'])))
probe('prediction_run_float', lambda l,p,q:q['pairs'][0]['runs']['A'].__setitem__('best_train',2.0))
probe('prediction_run_bool', lambda l,p,q:q['pairs'][0]['runs']['A'].__setitem__('column_moves',False))
probe('prediction_primary_bool', lambda l,p,q:q['predicted_primary'].__setitem__('positives',True))
probe('prediction_primary_float', lambda l,p,q:q['predicted_primary'].__setitem__('ties',2.0))

def duplicate(l,p,q):
    bad=copy.deepcopy(q['pairs'][0])
    bad['runs']['A']['best_train']=-999
    q['pairs'].insert(0,bad)
probe('contradictory_duplicate_prediction_pair',duplicate)
def extra(l,p,q):
    bad=copy.deepcopy(q['pairs'][0]); bad['pair']=p['pairs']
    q['pairs'].append(bad)
probe('out_of_range_prediction_pair',extra)
probe('wrong_numeric_value_control',lambda l,p,q:q['pairs'][0]['runs']['A'].__setitem__('best_train',999))

def seed_alias(l,p,q):
    p['seed_derivation']['master_seed'] += 1 << 32
    l[0]['app_identity']['master_seed'] = p['seed_derivation']['master_seed']
probe('uint32_seed_alias',seed_alias)
def bad_map(l,p,q):
    p['map']['sha256']='not-a-digest'
    l[0]['app_identity'].update(map_sha256='not-a-digest',operator_data_sha256='not-a-digest')
probe('invalid_map_digest',bad_map)

# A real input error should not require the CLI's internal-program-error path.
with tempfile.TemporaryDirectory(prefix='b2-input-cli-') as tmp:
    d=Path(tmp); plan=copy.deepcopy(f.PLAN); plan['fitness']=[]
    for name, data in [('log.json',base),('plan.json',plan),('prediction.json',f.PREDICTION)]:
        (d/name).write_text(json.dumps(data))
    run=subprocess.run([sys.executable,str(R/'host/b2_adjudicate.py'),
                        '--run-log',str(d/'log.json'),'--plan',str(d/'plan.json'),
                        '--prediction',str(d/'prediction.json'),'--out',str(d/'out.json')],
                       capture_output=True,text=True)
    out=json.loads((d/'out.json').read_text()) if (d/'out.json').exists() else {}
    results['cli_fitness_list']={'returncode':run.returncode,'result_written':(d/'out.json').exists(),
                                'outcome':out.get('outcome'),'internal_error':out.get('internal_error')}

assert results['baseline']['outcome']=='PASS',results['baseline']
print(json.dumps({'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
                  'synthetic_common_envelopes':True,'common':True,'cases':results},indent=2))
