from pathlib import Path
from fractions import Fraction
from collections import defaultdict
import subprocess,hashlib,json,ast,sys
R=Path('/home/test/zynq_fabricmap');D=Path(__file__).resolve().parent;E=R/'evidence/b4/unit_2c_obs_2026_10_21';A=R/'evidence/b4/sim/b4-sim-4_20261021T065339Z'
checks={}
for name in ['k9_address_record','positive_control_choice']:
 p=subprocess.run(['python3','-B',str(E/(name+'.py'))],cwd=R,text=True,capture_output=True)
 raw=(E/(name+'.txt')).read_bytes();assert p.returncode==0 and p.stdout.encode()==raw
 (D/(name+'_rerun.txt')).write_text(p.stdout)
 checks[name]={'exit':p.returncode,'output_byte_identical':True,'sha256':hashlib.sha256(raw).hexdigest()}
# Independent exact-arithmetic selection; no production model/scorer or seed generator is called.
counts=defaultdict(lambda:[0,0]);backgrounds=defaultdict(lambda:defaultdict(lambda:[0,0]));sem={};elem={}
for pd in sorted(A.glob('pair_*')):
 k=json.loads((pd/'k9.json').read_text())
 for row in k['pairs']:
  a=row['address'];sem[a]=row['semantic'];elem[a]=row['element']
  if row['applicable_sr_driven']:
   counts[a][0]+=1;counts[a][1]+=row['covered'];b=backgrounds[a][(row['g0'],row['g1'])];b[0]+=1;b[1]+=row['covered']
def order(a):
 far,w,b=a.split('/');return (int(far,16),int(w),int(b))
selected=[]
for label,semantic,kind in [('ce_mode','ce_mode',None),('clock_mode','clock_mode',None),('sr_kind','sr_kind',None),('sr_mode','sr_mode',None),('storage_kind','storage_kind',None),('ff_init (main)','ff_init','main'),('ff_init (x5FF)','ff_init','x5FF'),('ff_srval (main)','ff_srval','main'),('ff_srval (x5FF)','ff_srval','x5FF')]:
 candidates=[a for a in counts if sem[a]==semantic and (kind is None or (('5' in elem[a])==(kind=='x5FF')))]
 chosen=min(candidates,key=lambda a:(-Fraction(counts[a][1],counts[a][0]),order(a)))
 bg=min(backgrounds[chosen],key=lambda bg:(-backgrounds[chosen][bg][1],bg[0]))
 n,c=backgrounds[chosen][bg];assert n<=32
 selected.append({'label':label,'address':chosen,'element':elem[chosen],'covered':counts[chosen][1],'applicable':counts[chosen][0],'fraction':str(Fraction(counts[chosen][1],counts[chosen][0])),'g0':hex(bg[0]),'g1':hex(bg[1]),'background_covered':c,'background_applicable':n})
checks['independent_selection']=selected
# Mathematical scoring counterexample over an EXISTING retained grid, not a device/model observation.
first=A/'pair_000';task=json.loads((first/'task.json').read_text())['public_task'];k=json.loads((first/'k10.json').read_text())
for obs in k['observations']:
 cells=[(obs['q_grid'][r][c],t,w) for (r,c),t,w in zip(task['mask'],task['target'],task['weights'])]
 undefined=sum(w for q,t,w in cells if q is None)
 if undefined:
  known=sum(w for q,t,w in cells if q is not None and q==t)
  checks['D1_scoring_counterexample']={'source':'pair_000/k10.json retained observation id '+str(obs['id']),'genome':obs['genome'],'model_fitness':known,'masked_undefined_weight':undefined,'possible_completion_fitness_low':known,'possible_completion_fitness_high':known+undefined,'meaning':'hypothetical 0/1 completions demonstrate differing scoring domains; no claim that a board produces either completion'}
  break
assert 'D1_scoring_counterexample' in checks
# Existing observe() return shape obtained by AST, without constructing a Fabric or observing.
tree=ast.parse((R/'b4/host/b4_ff_model.py').read_text());fn=next(n for n in ast.walk(tree) if isinstance(n,ast.FunctionDef) and n.name=='observe')
ret=next(n for n in ast.walk(fn) if isinstance(n,ast.Return) and isinstance(n.value,ast.Dict))
keys=[k.value for k in ret.value.keys if isinstance(k,ast.Constant)]
checks['existing_model_trace_top_keys']=keys
checks['carrier_only_fields_missing_from_legacy_model']=[s for s in ['source','configuration','init_event','timing','stimulus_sha256','nonce','session_label'] if s not in keys]
# No protected surfaces change.
paths=['b4/','b3/','host/','tests/','firmware/','manifests/','gate_runs/','evidence/b3/','evidence/b4/sim/','evidence/b4/gonogo/','evidence/b4/gate/']
p=subprocess.run(['git','diff','--exit-code','fceedd6','HEAD','--',*paths],cwd=R,text=True,capture_output=True);assert p.returncode==0
checks['protected_paths_unchanged']=paths
checks['status']=subprocess.check_output(['git','status','--short','--branch'],cwd=R,text=True)
checks['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
checks['diff_check']=subprocess.check_output(['git','diff','--check','fceedd6','HEAD'],cwd=R,text=True)
(D/'readonly_checks.json').write_text(json.dumps(checks,indent=2)+'\n')
print(json.dumps(checks,indent=2))
