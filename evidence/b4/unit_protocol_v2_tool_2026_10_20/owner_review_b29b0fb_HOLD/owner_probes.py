import copy, hashlib, importlib.util, json, shutil, subprocess, sys
from pathlib import Path
from unittest import mock
R=Path('/home/test/zynq_fabricmap')
OUT=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/owner_b29b0fb_probes')
OUT.mkdir(exist_ok=False)
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_execution as ex
import b4_seeds as bs
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
from test_b4_sim import build_hermetic,SCHED_ONE,git,entry
res={}
def keep(): (OUT/'results.json').write_text(json.dumps(res,indent=2)+'\n')
def cli(out):
    p=subprocess.run([sys.executable,'-B',str(R/'b4/host/b4_sim_verify.py'),str(out)],capture_output=True,text=True)
    return {'exit':p.returncode,'stdout':p.stdout,'stderr':p.stderr}
class Bad(ex.ObservationPort):
    def __init__(self,fabric,at): super().__init__(fabric);self.at=at
    def observe(self,config,stimulus):
        t=super().observe(config,stimulus)
        if self.calls==self.at: t['steps'][0]={'marker':'owner_malformed_return'}
        return t
def forbid(*a,**kw): raise AssertionError('production derivation reached')
with mock.patch.object(bs,'master_seed',side_effect=forbid) as gm,mock.patch.object(bs,'pair_seeds',side_effect=forbid) as gp:
    work=build_hermetic(OUT/'root')
    def run(name,at,interrupt=False):
        if git(work,'status','--porcelain').strip():
            git(work,'add','-A');git(work,'commit','-q','-m','previous fixture')
        dest=work/sim.SIM_REL/('b4-mech-1_'+name)
        orig=sim.Batch.write
        def write(self,rel,doc,validator):
            e=orig(self,rel,doc,validator)
            if interrupt and rel.endswith('.QUARANTINE.json'): raise KeyboardInterrupt()
            return e
        with mock.patch.object(sim.Batch,'write',write):
            result=sim.run_batch(work,'b4-mech-1',1,3600,dest,schedule=SCHED_ONE,port_factory=lambda f,role,p:Bad(f,at) if role=='TARGET' else ex.ObservationPort(f))
        rep=json.loads((dest/'sim_report.json').read_bytes())
        res[name]={'status':result['status'],'pair':rep['pairs'][0],'stopped':rep['stopped'],'files':sorted(str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()),'verify':sv.verify_run_dir(dest,deep=True),'fresh_verify':cli(dest)}
        keep();print(name,res[name]['status'],res[name]['verify'],flush=True)
        return dest
    first=run('first_quarantine',1)
    second=run('second_quarantine',2)
    run('interrupt_first_quarantine',1,True)
    run('interrupt_second_quarantine',2,True)
    def refresh(out):
        rep=json.loads((out/'sim_report.json').read_bytes())
        rep['files']=[entry(p,str(p.relative_to(out))) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sim_report.json']
        (out/'sim_report.json').write_text(json.dumps(rep,sort_keys=True,indent=1)+'\n')
    for label,key,value in [('wrong_stimulus','stimulus_sha256','a'*64),('wrong_expected_source','expected_provenance_sha256','b'*64),('missing_expected_source','expected_provenance_sha256',None)]:
        out=work/sim.SIM_REL/('b4-mech-1_'+label);shutil.copytree(second,out)
        qpath=out/'pair_000/target_holdout.QUARANTINE.json'
        q=json.loads(qpath.read_bytes());q['context'][key]=value;qpath.write_text(json.dumps(q,indent=1)+'\n')
        refresh(out)
        res[label]={'schema_findings':sc.quarantine_findings(q),'verify':sv.verify_run_dir(out,deep=True),'fresh_verify':cli(out)}
        keep();print(label,res[label]['verify'],flush=True)
    res['production_derivation_calls']=[gm.call_count,gp.call_count];keep()

# Pure comparison probe: semantic reason fields must not disappear merely
# because they are named "reason". No model / batch / seed is run here.
spec=importlib.util.spec_from_file_location('owner_driver',R/'evidence/b4/unit_protocol_v2_tool_2026_10_20/e2e_v2_fixtures.py')
driver=importlib.util.module_from_spec(spec);spec.loader.exec_module(driver)
tiny=OUT/'normalisation';(tiny/'evidence/fixture').mkdir(parents=True)
f=tiny/'evidence/fixture/gate_report.json'
f.write_text(json.dumps({'schema':'fixture','verdict':{'status':'FAIL','reason':'K9 coverage below threshold'},'rows':[{'status':'FAIL','reason':'SR-driven coverage'}]}))
a=driver.normalise(tiny,set(),{'record':f.parent})
f.write_text(json.dumps({'schema':'fixture','verdict':{'status':'FAIL','reason':'other semantic explanation'},'rows':[{'status':'FAIL','reason':'different semantic criterion'}]}))
b=driver.normalise(tiny,set(),{'record':f.parent})
res['semantic_reasons_normalised_away']={'equal':a['digests']['record'][f.name]['normalised_sha256']==b['digests']['record'][f.name]['normalised_sha256'],'before':a,'after':b}
keep();print('semantic reasons equal',res['semantic_reasons_normalised_away']['equal'],flush=True)
