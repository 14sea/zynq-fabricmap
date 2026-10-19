"""Round-4 owner checks: no production derivation, only exposed literal pair (7,11)."""
import json,sys,tempfile,subprocess
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent;S=Path('/tmp/b4_owner_43ca57d_f0ok808x')
sys.path[:0]=[str(S/'b4/host'),str(S/'b4/tests')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
import b4_seeds as bs
import test_b4_sim as ts
from b4_deadline import Deadline
temp=Path(tempfile.mkdtemp(prefix='b4_owner_round4_'));result={'snapshot':str(S),'temp':str(temp)}
def read(p):return json.loads(p.read_bytes())
def forbid(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 prior=read(Path('/home/test/zynq_fabricmap/build/wip/owner_review_8d1eefd_2026_10_19/probes_results.json'))
 for name in ('malformed_k7','malformed_k9','malformed_k10'):
  result[name]=sv.verify_run_dir(Path(prior[name]['path']))
 nested=read(Path('/home/test/zynq_fabricmap/build/wip/owner_review_8d1eefd_2026_10_19/nested_malformed_results.json'))
 result['malformed_nested']=sv.verify_run_dir(Path(nested['path']))
 args=[sys.executable,'-B',str(S/'b4/host/b4_sim_verify.py'),prior['malformed_k9']['path']]
 cli=subprocess.run(args,capture_output=True,text=True)
 result['cli']={'command':args,'exit_code':cli.returncode,'stdout':json.loads(cli.stdout),'stderr':cli.stderr}
 vals=iter([1000.0,1059.990,1060.010,1060.030]);dl=Deadline(60,clock=lambda:next(vals));records=[dl.record() for _ in range(3)]
 result['records']=[{'record':r,'findings':sc.deadline_findings(r)} for r in records]

 inp=temp/'input';inp.mkdir();root=ts.build_hermetic(inp)
 class Clock:
  def __init__(self):self.t=1000.0;self.queue=[]
  def __call__(self):
   if self.queue:self.t=self.queue.pop(0)
   return self.t
 for stage,queue in (('K9',[1059.990,1060.010,1060.030]),('K9',[1060.010,1060.030,1060.050]),('K10',[1059.990,1060.010,1060.030])):
  clock=Clock()
  def interrupt(*a,**kw):
   clock.queue=list(queue);raise KeyboardInterrupt('owner fixed interruption at '+stage)
  out=root/sim.SIM_REL/('b4-mech-1_'+stage+'_'+str(int(queue[0]*1000)))
  module=sim.k9 if stage=='K9' else sim.k10;function='coverage' if stage=='K9' else 'seed_k10'
  with mock.patch.object(module,function,side_effect=interrupt):
   got=sim.run_batch(root,'b4-mech-1',1,60,out,clock=clock,schedule=ts.SCHED_ONE)
  rep=read(out/'sim_report.json');stop=read(out/'STOPPED.json')
  result[stage+'_'+str(queue[0])]={
   'path':str(out),'status':got['status'],'exit_code':got['exit_code'],'kind':stop['kind'],
   'diagnostic_state':rep['pairs'][0][stage.lower()],'diagnostic_file_present':(out/'pair_000'/f'{stage.lower()}.json').exists(),
   'stop_deadline':stop['deadline'],'report_deadline':rep['deadline'],'summary':rep['summary'],'verify':sv.verify_run_dir(out)}
  ts.git(root,'add','-A');ts.git(root,'commit','-q','-m','owner fixed mechanics '+stage)

 # Check the newly documented claim that an invalid diagnostic may have no file.
 out=root/sim.SIM_REL/'b4-mech-1_early_refusal'
 with mock.patch.object(sim.k9,'coverage',side_effect=ValueError('owner pre-record refusal')):
  got=sim.run_batch(root,'b4-mech-1',1,60,out,clock=Clock(),schedule=ts.SCHED_ONE)
 rep=read(out/'sim_report.json')
 result['early_invalid_without_record']={'path':str(out),'status':got['status'],'exit_code':got['exit_code'],
  'diagnostic_state':rep['pairs'][0]['k9'],'kind':rep['stopped']['kind'],'self_validation':rep['self_validation'],
  'verify':sv.verify_run_dir(out),'summary':rep['summary']}

(D/'probes_results.json').write_text(json.dumps(result,indent=1,sort_keys=True)+'\n');print(json.dumps(result,indent=1,sort_keys=True))
