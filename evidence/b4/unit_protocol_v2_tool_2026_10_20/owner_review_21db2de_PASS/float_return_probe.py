import json,subprocess,sys
from pathlib import Path
from unittest import mock
R=Path('/home/test/zynq_fabricmap');O=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/owner_b29b0fb_probes')
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_execution as ex
import b4_seeds as bs
import b4_sim as sim
import b4_sim_verify as sv
from test_b4_sim import SCHED_ONE,git
root=O/'root'
git(root,'add','-A');git(root,'commit','-q','-m','previous fixtures')
class FloatReturn(ex.ObservationPort):
    def observe(self,config,stimulus):
        t=super().observe(config,stimulus)
        t['owner_raw_marker']='preserve_entire_original_target_return'
        t['steps'][0]['q_after'][0]=float(t['steps'][0]['q_after'][0])
        return t
def forbidden(*a,**kw):raise AssertionError('production derivation reached')
with mock.patch.object(bs,'master_seed',side_effect=forbidden) as gm,mock.patch.object(bs,'pair_seeds',side_effect=forbidden) as gp:
    out=root/sim.SIM_REL/'b4-mech-1_float_return'
    r=sim.run_batch(root,'b4-mech-1',1,3600,out,schedule=SCHED_ONE,port_factory=lambda f,role,p:FloatReturn(f) if role=='TARGET' else ex.ObservationPort(f))
    q=json.loads((out/'pair_000/target_search.QUARANTINE.json').read_bytes())
    p=subprocess.run([sys.executable,'-B',str(R/'b4/host/b4_sim_verify.py'),str(out)],capture_output=True,text=True)
    record={'status':r['status'],'quarantine':q,'marker_kept':'preserve_entire_original_target_return' in json.dumps(q),'verify':sv.verify_run_dir(out,deep=True),'fresh_verify':{'exit':p.returncode,'stdout':p.stdout},'production_derivation_calls':[gm.call_count,gp.call_count]}
    (O/'float_return.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps({k:v for k,v in record.items() if k!='quarantine'},indent=1))
