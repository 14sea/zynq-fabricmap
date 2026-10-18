from pathlib import Path
import sys,json,tempfile,copy
from unittest import mock
R=Path('/tmp/b4_owner_cdf2c53_y9cov9it');sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_sim as sim,b4_sim_schema as sc,b4_seeds as bs,b4_execution as ex
from test_b4_sim import build_hermetic,Clock
OUT=Path('/home/test/zynq_fabricmap/build/wip/owner_review_cdf2c53_2026_10_18');rs={};roots=[]
def root():
 r=Path(tempfile.mkdtemp(prefix='b4_owner_more_'));roots.append(str(r));return build_hermetic(r)
with mock.patch.object(bs,'master_seed',return_value=1000001),mock.patch.object(bs,'pair_seeds',return_value=[(7,11)]):
 r=root();out=r/sim.SIM_REL/'b4-sim-1_badgrid'
 class BadGrid(ex.ObservationPort):
  def observe(self,config,stimulus):
   t=super().observe(config,stimulus)
   if self.calls==1:t['steps'][0]['q_after'][0]=2
   return t
 def factory(fab,role,pair):return BadGrid(fab) if role=='K9' else ex.ObservationPort(fab)
 b=sim.run_batch(r,'b4-sim-1',1,3600,out,port_factory=factory)
 q=json.loads((out/'pair_000/k9.json').read_text())
 rs['bad_k9_grid_runtime']={'status':b['status'],'exit_code':b['exit_code'],'saved_q':q['observations'][0]['q_grid'][0][0],'self_validation':b['report']['self_validation']}
 r=root();out=r/sim.SIM_REL/'b4-sim-1_selfvalidation'
 with mock.patch.object(sc,'validate_run_dir',return_value={'file':['injected corruption']}):b=sim.run_batch(r,'b4-sim-1',1,3600,out)
 rs['nonempty_self_validation']={'status':b['status'],'exit_code':b['exit_code'],'self_validation':b['report']['self_validation'],'summary_present':b['report']['summary'] is not None}
 r=root();out=r/sim.SIM_REL/'b4-sim-1_badreturned'
 orig=sim.be.run
 def malformed(*a,**kw):
  x=orig(*a,**kw);x.completed=1;return x
 with mock.patch.object(sim.be,'run',malformed):b=sim.run_batch(r,'b4-sim-1',1,3600,out)
 rs['returned_invalid_result_lost']={'status':b['status'],'exit_code':b['exit_code'],'result_file_exists':(out/'pair_000/arm_R.result.json').exists(),'stopped':b['stopped']['detail'],'arm_state':b['report']['pairs'][0]['arms']['R']}
OUT.joinpath('probes_more.json').write_text(json.dumps(rs,indent=2)+'\n');OUT.joinpath('probe_roots_more.json').write_text(json.dumps(roots,indent=2)+'\n');print(json.dumps(rs,indent=2))
