from pathlib import Path
from collections import defaultdict
from statistics import mean, median, stdev, pvariance
from math import comb,isclose
from unittest.mock import patch
import hashlib,json,subprocess,sys
R=Path('/home/test/zynq_fabricmap'); O=R/'build/wip/owner_review_9577654_2026_10_27'
A='evidence/b4/sim/b4-sim-5_20261027T170605Z'; G='evidence/b4/gonogo/b4-sim-5_20261027T171342Z'
BASE='ae7fc3547e1f9271a430b38ffee7fd469b89a7ee'; AC='d1e0e2cc33e9cdfbdf65270a89277599a17ccd74'; GC='61733c55e49ed39737f537eae4f01aaf700f8ca4'
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
def read(p):return json.loads((R/p).read_bytes())
def sha(b):return hashlib.sha256(b).hexdigest()
def same(a,b):return json.dumps(a,sort_keys=True,separators=(',',':'))==json.dumps(b,sort_keys=True,separators=(',',':'))
head=git('rev-parse','HEAD').decode().strip();assert head.startswith('9577654')
assert git('status','--porcelain','--untracked-files=all')==b''
assert git('rev-parse',AC+'^').decode().strip()==BASE
assert git('rev-parse',GC+'^').decode().strip()==AC
assert git('rev-parse','0c57bc1^').decode().strip()==GC
assert git('rev-parse','9577654^').decode().strip().startswith('0c57bc1')
assert not git('diff','--name-only','e20e12b','HEAD','--','b4/','rtl/','sim/','vivado/','host/','tests/','scripts/','firmware/','manifests/')
changes={}
for commit,allowed in [(AC,A+'/'),(GC,G+'/')]:
 paths=git('diff-tree','--no-commit-id','--name-only','-r',commit).decode().splitlines()
 assert all(p.startswith(allowed) for p in paths);changes[commit]={'files':len(paths),'only_expected_directory':True}
blobs={}
for commit,rel in [(AC,A),(GC,G)]:
 tree={}
 for line in git('ls-tree','-r',commit,'--',rel).decode().splitlines():
  meta,p=line.split('\t');mode,typ,oid=meta.split();assert typ=='blob' and mode=='100644';tree[p]=oid
 files=sorted(str(p.relative_to(R)) for p in (R/rel).rglob('*') if p.is_file())
 assert set(files)==set(tree)
 for p in files:
  assert not (R/p).is_symlink()
  assert git('hash-object','--',p).decode().strip()==tree[p]
 blobs[rel]={'commit':commit,'equal':len(files),'missing':0,'extra':0,'different':0}
report=read(A+'/sim_report.json');manifest=read(A+'/manifest.json');decision=read(G+'/gonogo.json')
assert report['head']==manifest['head']==BASE
assert decision['head']==AC and decision['batch']['head']==BASE
assert report['status']=='complete' and report['count']==32 and not report['fixture']
assert not report['self_validation'] and not decision['self_validation']
assert decision['decision']=='no-go' and decision['formal'] is True
assert manifest['deadline_s']==3600
assert manifest['protocol']['protocol_sha256']=='5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f'
source_counts={}
for k in ['inputs','tool_files']:
 for p,dig in manifest[k].items():assert sha(git('show',BASE+':'+p))==dig,(k,p)
 source_counts[k]=len(manifest[k])
for p,dig in manifest['external_inputs'].items():assert sha(Path(p).read_bytes())==dig,p
source_counts['external_inputs']=len(manifest['external_inputs'])
archive=R/'evidence/b4/unit_sim5_execution_2026_10_27/owner_review_ae7fc35_PASS'
original=R/'build/wip/owner_review_ae7fc35_2026_10_27'
owner_count=0
for line in (archive/'SHA256SUMS').read_text().splitlines():
 dig,p=line.split(None,1);p=p.lstrip('* ');assert sha((archive/p).read_bytes())==dig
 assert (archive/p).read_bytes()==(original/p).read_bytes();owner_count+=1
assert (archive/'SHA256SUMS').read_bytes()==(original/'SHA256SUMS').read_bytes()
assert owner_count==9
S=32;grid=report['summary']['grid'];per_B=defaultdict(list);k7_counts=defaultdict(list)
coverage={key:defaultdict(list) for key in ['per_semantic','per_semantic_all_panel']}; positives={key:defaultdict(int) for key in coverage}
elements=['AFF','A5FF','BFF','B5FF','CFF','C5FF','DFF','D5FF'];interacting=0;all_positive_seeds=0;arm_ledger_scores=0
k9_rows=0;k10_units=0

def score(q,t):return sum(w for (step,e),v,w in zip(t['mask'],t['target'],t['weights']) if q[step][e] is not None and q[step][e]==v)
for i in range(S):
 P=f'{A}/pair_{i:03d}';cur=read(P+'/curves.json');t=read(P+'/task.json')['public_task']
 assert cur['grid']==grid
 for role,expected in cur['best_at_grid'].items():
  result=read(P+f'/arm_{role}.result.json')['result']
  assert result['completed'] and not result['terminal'] and not result['control_failure'] and not result['other_refusal']
  vals=[]
  for entry in result['ledger']:
   if entry['phase'] in ['base','search']:
    s=score(entry['q_grid'],t);assert s==entry['fitness'];vals.append(s);arm_ledger_scores+=1
  assert len(vals)==257,(role,len(vals))
  got=[max(vals[:b+1]) for b in grid];assert got==expected,(i,role)
 for j,b in enumerate(grid):per_B[b].append(cur['best_at_grid']['Omega'][j]-cur['best_at_grid']['R'][j])
 k7=read(P+'/k7.json')
 for b in grid:
  pref=k7['prefixes'][str(b)];n=sum(v['state']!='unknown' for v in pref['relations'].values())
  assert n==pref['not_unknown'];assert pref['records']==b+1;k7_counts[b].append(n)
 k9=read(P+'/k9.json');assert k9['complete'] and len(k9['pairs'])==1184
 obs={o['id']:o['q_grid'] for o in k9['observations']};tally={key:defaultdict(lambda:[0,0]) for key in coverage}
 for p in k9['pairs']:
  k9_rows+=1;covered=False
  if p['applicable']:
   q0,q1=obs[p['obs0']],obs[p['obs1']];idx=[elements.index(e) for e in p['scope']]
   diffs=[]
   for step,(r0,r1) in enumerate(zip(q0,q1)):
    for e in idx:
     if r0[e]!=r1[e]:diffs.append({'step':step,'element':elements[e],'kind':'presence' if (r0[e] is None)!=(r1[e] is None) else 'value','q0':r0[e],'q1':r1[e]})
   assert same(diffs,p['differences']);covered=bool(diffs);assert covered==p['covered']
  for key,flag in [('per_semantic','applicable_sr_driven'),('per_semantic_all_panel','applicable')]:
   if p[flag]:tally[key][p['semantic']][0]+=1;tally[key][p['semantic']][1]+=covered
 for key in coverage:
  for sem,(total,hits) in tally[key].items():
   assert total>0;f=hits/total;rec=k9['summary'][key][sem]
   assert (rec['applicable'],rec['covered'],rec['fraction'])==(total,hits,f)
   coverage[key][sem].append(f);positives[key][sem]+=hits>0
 all_positive_seeds+=all(hits>0 for total,hits in tally['per_semantic_all_panel'].values())
 k10=read(P+'/k10.json');assert k10['complete'] and len(k10['units'])==420 and k10['tau']==2
 obs10={o['id']:o['q_grid'] for o in k10['observations']};indexes=[]
 for unit in k10['units']:
  assert unit['comparable'];corners={}
  for corner,c in unit['corners'].items():
   s=score(obs10[c['obs']],t);assert s==c['score'];corners[corner]=s
  ix=corners['11']-corners['10']-corners['01']+corners['00'];assert ix==unit['index'];indexes.append(abs(ix));k10_units+=1
 mx=max(indexes);assert mx==k10['max_abs_index'];interacting+=mx>=2

by_budget={}
for b,v in per_B.items():
 pos=sum(x>0 for x in v);neg=sum(x<0 for x in v);ties=S-pos-neg;n=pos+neg
 p=sum(comb(n,k) for k in range(pos,n+1))/2**n if n else 1.
 d=mean(v)/stdev(v) if stdev(v) else (float('inf') if mean(v)>0 else 0.)
 got={'positives':pos,'negatives':neg,'ties':ties,'mean':mean(v),'median':median(v),'cohen_d':d,'sign_test_p':p,'k7_median_not_unknown':median(k7_counts[b])}
 rec=report['summary']['per_budget'][str(b)]['deltas']['Omega_minus_R']
 for k in ['positives','negatives','ties','mean','median','sign_test_p']:assert got[k]==rec[k],(b,k)
 assert isclose(d,rec['cohen_d']['value'],rel_tol=1e-13,abs_tol=1e-15)
 by_budget[b]=got
meds={key:{s:median(v) for s,v in vals.items()} for key,vals in coverage.items()}
for key in meds:
 assert len(meds[key])==7
 for s,v in meds[key].items():assert v==report['summary']['k9'][key][s]['median_coverage_over_all_S']
assert same(meds['per_semantic'],decision['statistic_2']['conditional_medians'])
assert same(meds['per_semantic_all_panel'],decision['statistic_2']['all_panel_medians_descriptive'])
assert same(dict(positives['per_semantic']),dict(positives['per_semantic_all_panel']))
assert all_positive_seeds==25 and interacting==32
assert report['summary']['k9']['seeds_with_all_seven_positive_controls']==25
v=by_budget[64];assert (v['positives'],v['negatives'],v['ties'])==(9,7,16) and v['sign_test_p']==.4018096923828125
assert v['positives']>v['negatives'] and v['sign_test_p']>.2 and min(meds['per_semantic'].values())>=.5
sys.path.insert(0,str(R/'b4/host'));import b4_seeds as bs
with patch.object(bs,'master_seed',side_effect=AssertionError('no new draw')) as g1,patch.object(bs,'pair_seeds',side_effect=AssertionError('no new draw')) as g2:
 regs,_=bs.sim_registry(R);ex=bs.load_exclusion_set(R)
 new=next(r for r in regs if r.dir==A)
 other=set().union(*(r.values for r in regs if r.dir!=A));prior=set(ex.values)-set(new.values)
 assert len(regs)==4 and len(new.values)==65 and len(ex.values)==2755
 assert not (set(new.values)&other) and len(prior)==2690
 guards=[g1.call_count,g2.call_count];assert guards==[0,0]
result={'reviewed_tip':head,'execution_HEAD':BASE,'archive_commit':AC,'decision_HEAD':AC,'commit_scopes':changes,'blob_checks':blobs,
 'source_bindings_to_execution_HEAD':source_counts,'archived_owner_payload_checksums':owner_count,'protocol_sha256':manifest['protocol']['protocol_sha256'],
 'batch_status':report['status'],'deadline':report['deadline'],'S':32,'per_budget':by_budget,'K9_medians':meds,'K9_positive_control_seeds':dict(positives['per_semantic']),
 'K9_all_seven_positive_controls':all_positive_seeds,'K9_pairs_recounted':k9_rows,'K10_units_recounted':k10_units,'K10_interacting':interacting,'arm_ledger_scores_recomputed':arm_ledger_scores,
 'decision':'no-go','registry_count':len(regs),'pooled_before':len(prior),'pooled_after':len(ex.values),'new_distinct_values':len(new.values),'new_values_collisions':0,
 'seed_derivation_guard_calls':guards,'tracked_changes_by_reviewer':False}
(O/'independent_checks.json').write_text(json.dumps(result,indent=2)+'\n')
assert git('status','--porcelain','--untracked-files=all')==b''
print('Independent raw-grid, curve, record, source and blob checks complete; no new observation or seed derivation. Output: independent_checks.json')
