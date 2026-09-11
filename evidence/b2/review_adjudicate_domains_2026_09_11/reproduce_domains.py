#!/usr/bin/env python3
"""Independent checks of the corrected guard domains. Synthetic data; offline only."""
import copy
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import test_b2_adjudicate as f
import b2_adjudicate as a
f.BlankBaselines.setUpClass()
base=f.BlankBaselines.whole
cases=[]

def run_case(name, path, value, expected='REFUSED', repair=False):
    p,q=copy.deepcopy(f.PLAN),copy.deepcopy(f.PREDICTION)
    root={'plan':p,'prediction':q}; obj=root
    for key in path[:-1]: obj=obj[key]
    obj[path[-1]]=copy.deepcopy(value)
    if repair:
        for e in q['pairs']:
            e['delta_B_minus_A']=e['runs']['B']['best_train']-e['runs']['A']['best_train']
        q['deltas']=[e['delta_B_minus_A'] for e in q['pairs']]
        q['predicted_primary']=f.bp.decision(q['deltas'])
    try:
        out=a.adjudicate([copy.deepcopy(base)],p,q,consts=f.CONSTS,common=True)
        item={'case':name,'outcome':out['outcome'],'has_primary':'primary' in out,
              'expected':expected,'ok':out['outcome'].startswith(expected)}
    except Exception as exc:
        item={'case':name,'exception':repr(exc),'expected':expected,'ok':False}
    cases.append(item)

# Independent inventories; do not read the production predicate tables.
count_paths=[['prediction','pairs',0,'runs','A',k] for k in ('best_train','champion_holdout','column_moves')]
count_paths += [['prediction','predicted_primary',k] for k in ('positives','negatives','ties')]
count_paths += [['prediction','budget_per_arm'],['prediction','fitness_sequence_length'],['prediction','pairs',0,'pair']]
for path in count_paths:
    for i,value in enumerate([None,False,True,1.0,'1',[],{}]):
        run_case(f'{path}.bad_type.{i}',path,value)
digests=[['plan','map','sha256'],['prediction','fitness_sequence_sha256']]
digests += [['prediction','pairs',0,'runs','A',k] for k in ('champion_genome_sha256','moves_sha256')]
for path in digests:
    for i,value in enumerate([None,False,{},[],'','A'*64,'a'*63,'a'*65,'a'*64+'\n']):
        run_case(f'{path}.bad_digest.{i}',path,value)
for k in ('sign_test_p','alpha'):
    for i,value in enumerate([False,True,None,'0.05',[],{},-0.1,1.1,float('nan'),float('inf'),-float('inf')]):
        run_case(f'probability.{k}.{i}',['prediction','predicted_primary',k],value)
for value in (-1,1<<32):
    run_case(f'master_seed.{value}',['plan','seed_derivation','master_seed'],value)
for value in (0,-1,17,True,16.0):
    run_case(f'pairs.{value}',['plan','pairs'],value)
for k,upper in [('best_train',40),('champion_holdout',24),('column_moves',f.BUDGET)]:
    for value in (-1,upper+1):
        run_case(f'run_domain.{k}.{value}',['prediction','pairs',0,'runs','A',k],value)

positive=a.adjudicate([copy.deepcopy(base)],f.PLAN,f.PREDICTION,consts=f.CONSTS,common=True)
assert positive['outcome']=='PASS',positive
run_case('in_domain_self_consistent_mismatch',['prediction','pairs',0,'runs','A','best_train'],3,
         expected='HOLD',repair=True)
# The optional redundant per-pair delta is compared, but still lacks an integer guard.
run_case('redundant_delta_bool',['prediction','pairs',0,'delta_B_minus_A'],False,expected='PASS')
run_case('redundant_delta_float',['prediction','pairs',0,'delta_B_minus_A'],0.0,expected='PASS')
run_case('redundant_delta_wrong_value_control',['prediction','pairs',0,'delta_B_minus_A'],99)

families={}
for fid in ('F1','F2','F3'):
    p=copy.deepcopy(f.PLAN);p['fitness']=fid
    q=f.bp.build_prediction(fid,f.BUDGET,f.SEEDS,f.MAP_SHA)
    a.check_plan(p);a.check_prediction(q,p)
    families[fid]='ACCEPTED'
with tempfile.TemporaryDirectory(prefix='b2-genuine-error-') as tmp:
    d=Path(tmp)
    for name,data in [('log.json',base),('plan.json',f.PLAN),('prediction.json',f.PREDICTION)]:
        (d/name).write_text(json.dumps(data))
    with patch.object(a,'adjudicate',side_effect=RuntimeError('review injected programming defect')):
        with contextlib.redirect_stdout(io.StringIO()):
            rc=a.main(['--run-log',str(d/'log.json'),'--plan',str(d/'plan.json'),
                       '--prediction',str(d/'prediction.json'),'--out',str(d/'out.json')])
    error=json.loads((d/'out.json').read_text())
    internal_control={'exit':rc,'outcome':error['outcome'],'traceback_saved':'internal_error' in error,
                      'misclassified_as_refusal':'refusal' in error}
    assert rc==3 and 'internal_error' in error and 'refusal' not in error,internal_control
out={'head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),
     'common':True,'synthetic_fixture':True,'baseline':positive['outcome'],
     'valid_prediction_family_controls':families,'genuine_internal_error_control':internal_control,
     'cases':cases,'failed':[x for x in cases if not x['ok']]}
print(json.dumps(out,indent=2,allow_nan=False))
assert not out['failed'],out['failed']
