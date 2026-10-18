"""Additional owner checks, exclusively already-exposed mechanics seeds."""
import copy,hashlib,json,shutil,sys
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent
first=json.loads((D/'probes_results.json').read_bytes())
S=Path(first['snapshot']); sys.path[:0]=[str(S/'b4/host'),str(S/'b4/tests')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
import b4_seeds as bs
import b4_replay as br
import test_b4_sim as ts
root=Path(first['root']); base=root/sim.SIM_REL/'b4-mech-1_owner'
result={}
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=1,allow_nan=False)+'\n')
def entry(p,rel):
    b=p.read_bytes();return {'path':rel,'sha256':hashlib.sha256(b).hexdigest(),'size':len(b)}
def reindex(p):
    idx=read(p/'pair_000/index.json')
    idx['files']=[entry(f,f.name) for f in sorted((p/'pair_000').iterdir()) if f.is_file() and f.name!='index.json']
    write(p/'pair_000/index.json',idx)
    rep=read(p/'sim_report.json')
    rep['files']=[entry(f,str(f.relative_to(p))) for f in sorted(p.rglob('*')) if f.is_file() and f.name!='sim_report.json']
    rep['identity']['manifest_sha256']=sim.sha_file(p/'manifest.json');write(p/'sim_report.json',rep)
def case(name):
    p=root.parent/(root.name+'_extra_'+name);shutil.copytree(base,p);return p
def forbidden(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbidden),mock.patch.object(bs,'pair_seeds',side_effect=forbidden):
    p=case('unaudited_bad_rng')
    rep=read(p/'sim_report.json');rep['pairs'][0]['arms']['R']='written';write(p/'sim_report.json',rep)
    idx=read(p/'pair_000/index.json');idx['arms']['R']='written';write(p/'pair_000/index.json',idx)
    (p/'pair_000/arm_R.audit.json').unlink()
    doc=read(p/'pair_000/arm_R.result.json');doc['result']['rng_state_final']^=1;write(p/'pair_000/arm_R.result.json',doc)
    task=sim.bl.make_task(7,sim.bm.site_mapping().addresses)
    reindex(p)
    result['unaudited_bad_rng']={'verify':sv.verify_run_dir(p),'direct_replay':br.replay(doc['result'],task),'path':str(p)}

    p=case('bool_observation_id')
    doc=read(p/'pair_000/k9.json');doc['observations'][0]['id']=False;write(p/'pair_000/k9.json',doc);reindex(p)
    result['bool_observation_id']={'validator':sc.k9_findings(doc,task),'verify':sv.verify_run_dir(p),'path':str(p)}

    p=case('float_interaction_index')
    doc=read(p/'pair_000/k10.json');doc['units'][0]['index']=float(doc['units'][0]['index']);write(p/'pair_000/k10.json',doc);reindex(p)
    result['float_interaction_index']={'validator':sc.k10_findings(doc,task),'verify':sv.verify_run_dir(p),'path':str(p)}

    p=case('manifest_source_mismatch')
    doc=read(p/'manifest.json');doc['fabric']={'kind':'dropout'};doc['mapping']['addresses']=[None]*21
    write(p/'manifest.json',doc);reindex(p)
    result['manifest_source_mismatch']={'validator':sc.manifest_findings(doc),'verify':sv.verify_run_dir(p),'path':str(p)}

    # Full run_batch reproduction, not a re-entry into finish: elapsed time and input drift at the last verifier boundary.
    ts.git(root,'add','-A');ts.git(root,'commit','-q','-m','owner fixed mechanics baseline')
    class Clock:
        t=1000.0
        def __call__(self):return self.t
    clock=Clock(); target=root/'docs/b4_architecture.md';original=target.read_bytes(); real=sv.verify_run_dir
    def after_verify(*a,**kw):
        f=real(*a,**kw)
        if kw.get('deep'):
            target.write_bytes(original+b'\nowner finalisation drift probe\n');clock.t+=10000
        return f
    p=root/sim.SIM_REL/'b4-mech-2_owner_full_finalisation'
    try:
        with mock.patch.object(sv,'verify_run_dir',side_effect=after_verify):
            got=sim.run_batch(root,'b4-mech-2',1,60,p,clock=clock,schedule=sim.FixtureSchedule('b4-mech-2',((3,13),)))
        result['full_run_finalisation']={'status':got['status'],'exit_code':got['exit_code'],'actual_elapsed_s':clock.t-1000,
            'reported_deadline':got['report']['deadline'],'source_drifted':target.read_bytes()!=original,
            'self_validation':got['report']['self_validation'],'path':str(p)}
    finally:target.write_bytes(original)
write(D/'probes_more_results.json',result)
print(json.dumps(result,indent=1))
