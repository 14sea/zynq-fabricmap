"""Independent full run_batch checks, explicit exposed mechanics schedule only."""
import json,sys,tempfile
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent;S=Path('/tmp/b4_owner_6c00156_3mc7z1rw')
sys.path[:0]=[str(S/'b4/host'),str(S/'b4/tests')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_seeds as bs
import test_b4_sim as ts
root=ts.build_hermetic(Path(tempfile.mkdtemp(prefix='b4_owner_round2_final_')))
result={'root':str(root)}
def forbid(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
class Clock:
 t=1000.0
 def __call__(self):return self.t
real=sv.verify_run_dir
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 for kind in ('deadline','input_drift'):
  clock=Clock();target=root/'docs/b4_architecture.md';original=target.read_bytes()
  def after(*a,**kw):
   f=real(*a,**kw)
   if kw.get('deep'):
    if kind=='deadline':clock.t+=10000
    else:target.write_bytes(original+b'\nowner publication input drift\n')
   return f
  out=root/sim.SIM_REL/('b4-mech-1_'+kind)
  try:
   with mock.patch.object(sv,'verify_run_dir',side_effect=after):
    res=sim.run_batch(root,'b4-mech-1',1,60,out,clock=clock,schedule=ts.SCHED_ONE)
   rep=json.loads((out/'sim_report.json').read_bytes())
   result[kind]={'status':res['status'],'exit_code':res['exit_code'],'stopped':res['stopped'],
    'summary':rep['summary'],'deadline':rep['deadline'],'archive_verify':real(out)}
  finally:target.write_bytes(original)
  ts.git(root,'add','-A');ts.git(root,'commit','-q','-m','owner mechanics '+kind)
(D/'finalisation_results.json').write_text(json.dumps(result,sort_keys=True,indent=1)+'\n')
print(json.dumps(result,sort_keys=True,indent=1))
