from pathlib import Path
import json, math, statistics, hashlib, subprocess, sys
from collections import Counter
R=Path('/home/test/zynq_fabricmap');D=Path(__file__).resolve().parent
B=R/'evidence/b4/sim/b4-sim-4_20261021T065339Z';G=R/'evidence/b4/gonogo/b4-sim-4_20261021T065857Z'
load=lambda p: json.loads(p.read_text())
rep=load(B/'sim_report.json');man=load(B/'manifest.json');dec=load(G/'gonogo.json')
grid=[8,16,24,32,48,64,96,128,192,256]
semantics=['ce_mode','clock_mode','ff_init','ff_srval','sr_kind','sr_mode','storage_kind'];elements=['AFF','A5FF','BFF','B5FF','CFF','C5FF','DFF','D5FF']
bybudget={str(b):[] for b in grid};cov={key:{s:[] for s in semantics} for key in ['conditional','all_panel']};positives=Counter();k10=Counter();k7={str(b):[] for b in grid}
def score(q,t,hold=False):
 pre='holdout_' if hold else ''
 return sum(w for (row,col),target,w in zip(t[pre+'mask'],t[pre+'target'],t[pre+'weights']) if q[row][col] is not None and q[row][col]==target)
for i in range(32):
 pd=B/f'pair_{i:03d}';task=load(pd/'task.json')['public_task'];curves=load(pd/'curves.json');best={}
 for arm in ['R','Omega']:
  result=load(pd/f'arm_{arm}.result.json')['result'];search=[];m=None
  for l in result['ledger']:
   f=score(l['q_grid'],task,l['phase']=='holdout');assert f==l['fitness'],(i,arm,'raw fitness')
   if l['phase']=='base':m=f
   elif l['phase']=='search':m=max(m,f);search.append(m)
  assert len(search)==256 and search==result['best_trace']
  best[arm]=[search[b-1] for b in grid]
  assert best[arm]==curves['best_at_grid'][arm]
 for j,b in enumerate(grid):bybudget[str(b)].append(best['Omega'][j]-best['R'][j])
 kd=load(pd/'k9.json');assert kd['complete'] and kd['pairs_done']==1184
 obs={o['id']:o['q_grid'] for o in kd['observations']};tallies={key:{s:[0,0] for s in semantics} for key in cov}
 for pair in kd['pairs']:
  if not pair['applicable']:continue
  indices=[elements.index(e) for e in pair['scope']];q0=obs[pair['obs0']];q1=obs[pair['obs1']]
  covered=any(a[col]!=b[col] for a,b in zip(q0,q1) for col in indices)
  assert covered is pair['covered'],(i,'K9 raw coverage')
  for key,flag in [('conditional','applicable_sr_driven'),('all_panel','applicable')]:
   if pair[flag]:tallies[key][pair['semantic']][0]+=1;tallies[key][pair['semantic']][1]+=int(covered)
 for key,summarykey in [('conditional','per_semantic'),('all_panel','per_semantic_all_panel')]:
  for s,(n,c) in tallies[key].items():
   f=c/n if n else None;assert f==kd['summary'][summarykey][s]['fraction'];cov[key][s].append(f)
   if key=='all_panel' and c:positives[s]+=1
 kt=load(pd/'k10.json');assert kt['complete'] and len(kt['units'])==420
 ko={o['id']:o['q_grid'] for o in kt['observations']};indices=[]
 for u in kt['units']:
  assert u['comparable'];ss={corner:score(ko[v['obs']],task) for corner,v in u['corners'].items()}
  assert all(ss[corner]==v['score'] for corner,v in u['corners'].items())
  ix=ss['11']-ss['10']-ss['01']+ss['00'];assert ix==u['index'];indices.append(ix)
 maxabs=max(abs(v) for v in indices);assert maxabs==kt['max_abs_index'];assert kt['tau']==2
 assert kt['outcome']=='interacting' and maxabs>2;k10[kt['outcome']]+=1
 kp=load(pd/'k7.json')
 for b in grid:k7[str(b)].append(kp['prefixes'][str(b)]['not_unknown'])
stats={}
for b,ds in bybudget.items():
 pos=sum(v>0 for v in ds);neg=sum(v<0 for v in ds);ties=32-pos-neg;n=pos+neg
 pv=sum(math.comb(n,k) for k in range(pos,n+1))/(2**n) if n else 1.0
 mean=sum(ds)/32;var=statistics.pvariance(ds);std=statistics.stdev(ds);d=mean/std if std else (math.inf if mean>0 else 0.0)
 v={'n':32,'positives':pos,'negatives':neg,'ties':ties,'mean':mean,'median':statistics.median(ds),'population_variance':var,'cohen_d':d,'sign_test_p':pv}
 for target in [rep['summary']['per_budget'][b]['deltas']['Omega_minus_R'],dec['omega_minus_R_by_budget'][b]]:
  for k,val in v.items():
   got=target[k]['value'] if k=='cohen_d' else target[k]
   assert math.isclose(got,val,rel_tol=1e-13,abs_tol=1e-14),(b,k,got,val)
 stats[b]=v
med={key:{s:statistics.median(vs) if all(v is not None for v in vs) else None for s,vs in ss.items()} for key,ss in cov.items()}
assert med['conditional']==dec['statistic_2']['conditional_medians'];assert med['all_panel']==dec['statistic_2']['all_panel_medians_descriptive']
assert all(positives[s]==32 for s in semantics)
a=stats['64'];go=(a['positives']>a['negatives'] and a['sign_test_p']<=.2 and all(v is not None and v>=.5 for v in med['conditional'].values()))
assert not go and dec['decision']=='no-go' and dec['formal'] is True
assert rep['status']=='complete' and len(rep['pairs'])==32 and rep['missing']==[] and rep['self_validation']=={} and rep['stopped'] is None
assert rep['head']==man['head']=='495cc360c97aba58bda959a2e867e6b43dbf4f7f'
assert dec['head']=='580c0e5d06079dfe9ad885e69aaec23ff13ffcaa' and dec['batch']['head']==man['head']
for name,key in [('seeds.json','seeds_sha256'),('manifest.json','manifest_sha256'),('sim_report.json','sha256')]:assert hashlib.sha256((B/name).read_bytes()).hexdigest()==dec['batch'][key]
blob_checks={}
for label,commit,folder in [('batch','580c0e5',B),('decision','adce027',G)]:
 rel=str(folder.relative_to(R));raw=subprocess.check_output(['git','ls-tree','-r','-z',commit,'--',rel],cwd=R)
 committed={}
 for line in raw.split(b'\0'):
  if not line:continue
  fields,path=line.split(b'\t',1);committed[path.decode()]=fields.decode().split()[2]
 disk={str(p.relative_to(R)):p for p in folder.rglob('*') if p.is_file()}
 assert set(committed)==set(disk)
 for name,p in disk.items():
  buf=p.read_bytes();sha=hashlib.sha1(b'blob '+str(len(buf)).encode()+b'\0'+buf).hexdigest();assert sha==committed[name]
 blob_checks[label]={'files':len(disk),'bytes':sum(p.stat().st_size for p in disk.values()),'all_equal':True}
assert blob_checks['batch']['files']==771 and blob_checks['decision']['files']==2
for pattern in ['*.QUARANTINE.json','*.part','STOPPED.json','INIT_FAILED.json']:assert not list(B.rglob(pattern))
# Read the current exclusion pool with formal derivation calls guarded. The pool is computed from already committed values only.
sys.path.insert(0,str(R/'b4/host'));import b4_seeds as bs
calls={'master_seed':0,'pair_seeds':0}
def guard(name):
 def refuse(*args,**kwargs):calls[name]+=1;raise AssertionError('new draw forbidden')
 return refuse
bs.master_seed=guard('master_seed');bs.pair_seeds=guard('pair_seeds')
ex=bs.load_exclusion_set(R);old=set(bs.B2_EXCLUDED_SEEDS)|set(bs.B4_EXPOSED_VALUES)|set(ex.receipt.values)
for source in ex.sources:old.update(source.values)
newreg=None
for reg in ex.registry:
 if reg.dir==str(B.relative_to(R)):newreg=reg
 else:old.update(reg.values)
assert len(old)==2625 and newreg is not None and len(newreg.values)==65
collisions=set(newreg.values)&old;assert not collisions and len(ex.values)==2690
out={'status':'all independent assertions passed','method':'standard-library calculations from retained ledgers/grids; K9 uses recorded applicability flags (rechecked by deep verifier); no fabric observation or new seed draw','Omega_minus_R_by_budget':stats,'K9_medians':med,'K9_positive_controls_by_semantic':dict(positives),'K10_counts':dict(k10),'K7_prefix_medians':{b:statistics.median(v) for b,v in k7.items()},'decision':'no-go','blob_checks':blob_checks,'exclusion':{'before':len(old),'new_values':len(newreg.values),'collisions':len(collisions),'after':len(ex.values)},'production_derivation_calls':calls}
(D/'independent_checks.json').write_text(json.dumps(out,indent=2,sort_keys=True)+'\n')
print(json.dumps({'status':out['status'],'at_64':stats['64'],'K9':med,'K10':dict(k10),'blobs':blob_checks,'exclusion':out['exclusion'],'guards':calls},indent=2))
