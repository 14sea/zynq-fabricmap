"""Independent checks for the pre-index publication window and both setup phases.
All batches use SCHED_ONE under /tmp, with production derivation forbidden.
"""
import json,shutil,subprocess,sys
from pathlib import Path
from unittest import mock
R=Path('/home/test/zynq_fabricmap');O=Path('/tmp/owner_21db2de_probes')
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_execution as ex
import b4_seeds as bs
import b4_sim as sim
import b4_sim_verify as sv
from test_b4_sim import SCHED_ONE,git,entry
root=O/'root';results={}
def keep(): (O/'extra_results.json').write_text(json.dumps(results,indent=2)+'\n')
def forbidden(*a,**kw):raise AssertionError('production derivation reached')
def verify(out):
    p=subprocess.run([sys.executable,'-B',str(R/'b4/host/b4_sim_verify.py'),str(out)],capture_output=True,text=True)
    return {'findings':sv.verify_run_dir(out,deep=True),'fresh_exit':p.returncode,'fresh_stdout':p.stdout}
def refresh(out):
    rep=json.loads((out/'sim_report.json').read_bytes())
    rep['files']=[entry(p,str(p.relative_to(out))) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sim_report.json']
    (out/'sim_report.json').write_text(json.dumps(rep,sort_keys=True,indent=1)+'\n')
class Bad(ex.ObservationPort):
    def __init__(self,f,at):super().__init__(f);self.at=at
    def observe(self,c,s):
        t=super().observe(c,s)
        if self.calls==self.at:t['steps'][0]={'marker':'returned-before-index-interrupt'}
        return t
with mock.patch.object(bs,'master_seed',side_effect=forbidden) as gm,mock.patch.object(bs,'pair_seeds',side_effect=forbidden) as gp:
    for at in (1,2):
        if git(root,'status','--porcelain').strip():
            git(root,'add','-A');git(root,'commit','-q','-m','previous fixtures')
        name=f'interrupt_before_index_{at}';out=root/sim.SIM_REL/('b4-mech-1_'+name)
        original=sim.write_exclusive
        def published(path,doc,validator=None):
            ret=original(path,doc,validator)
            if path.name.endswith('.QUARANTINE.json'):raise KeyboardInterrupt()
            return ret
        with mock.patch.object(sim,'write_exclusive',published):
            res=sim.run_batch(root,'b4-mech-1',1,3600,out,schedule=SCHED_ONE,port_factory=lambda f,role,p,at=at:Bad(f,at) if role=='TARGET' else ex.ObservationPort(f))
        results[name]={'status':res['status'],'plan':res['report']['pairs'][0],**verify(out)}
        assert results[name]['fresh_exit']==0 and not results[name]['findings']
        assert results[name]['plan']['task']=='invalid' and results[name]['plan']['task_quarantine']==('target' if at==1 else 'target_holdout')
        keep()
    for phase,base,filename in [('target','first_quarantine','target_search.QUARANTINE.json'),('target_holdout','second_quarantine','target_holdout.QUARANTINE.json')]:
        for label,key,value in [('stimulus','stimulus_sha256','a'*64),('source','expected_provenance_sha256','b'*64),('null_source','expected_provenance_sha256',None)]:
            name=phase+'_'+label;out=root/sim.SIM_REL/('b4-mech-1_extra_'+name)
            shutil.copytree(root/sim.SIM_REL/('b4-mech-1_'+base),out)
            q=out/'pair_000'/filename;doc=json.loads(q.read_bytes());doc['context'][key]=value;q.write_text(json.dumps(doc)+'\n');refresh(out)
            results[name]=verify(out)
            assert results[name]['fresh_exit']==1 and results[name]['findings']
            assert key in results[name]['fresh_stdout']
            keep()
    out=root/sim.SIM_REL/'b4-mech-1_coordinated_source';shutil.copytree(root/sim.SIM_REL/'b4-mech-1_second_quarantine',out)
    p=out/'pair_000/target_search.json';first=json.loads(p.read_bytes());first['provenance']['fabric']['effect_sha256']='a'*64;first['provenance_sha256']=ex.sha256_json(first['provenance']);p.write_text(json.dumps(first)+'\n')
    q=out/'pair_000/target_holdout.QUARANTINE.json';doc=json.loads(q.read_bytes());doc['context']['expected_provenance_sha256']=first['provenance_sha256'];q.write_text(json.dumps(doc)+'\n');refresh(out)
    results['coordinated_source']=verify(out)
    assert results['coordinated_source']['fresh_exit']==1 and results['coordinated_source']['findings']
    results['production_derivation_calls']=[gm.call_count,gp.call_count];keep()
print(json.dumps({k:({'fresh_exit':v['fresh_exit'],'findings':v['findings']} if isinstance(v,dict) else v) for k,v in results.items()},indent=1))
