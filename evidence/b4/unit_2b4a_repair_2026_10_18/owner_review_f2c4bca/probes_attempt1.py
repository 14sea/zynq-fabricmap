"""Owner review: known mechanics seeds only; no production derivation."""
import copy, hashlib, json, shutil, sys, tempfile
from pathlib import Path
from unittest import mock

SNAP = Path('/tmp/b4_owner_f2c4bca_7__gab_9')
sys.path[:0] = [str(SNAP/'b4/host'), str(SNAP/'b4/tests')]
import test_b4_sim as ts
import b4_sim as sim
import b4_sim_verify as sv
import b4_seeds as bs
import b4_engine as be
import b4_execution as ex
import b4_snapshot as sn
import b4_replay as br
from b4_deadline import Deadline

DEST = Path(__file__).resolve().parent
root = ts.build_hermetic(Path(tempfile.mkdtemp(prefix='b4_owner_repair_probe_')))
findings = {'root':str(root), 'snapshot':str(SNAP)}
captured = []
real_finish = sim.Batch.finish
def capture(batch,*a,**kw):
    captured.append(batch)
    return real_finish(batch,*a,**kw)
def forbidden(*a,**kw):
    raise AssertionError('OWNER: production derivation forbidden')
def read(p): return json.loads(p.read_bytes())
def write(p,d): p.write_text(json.dumps(d,sort_keys=True,indent=1,allow_nan=False)+'\n')
def entry(p,rel):
    b=p.read_bytes()
    return {'path':rel,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def reindex(out):
    idx=read(out/'pair_000/index.json')
    idx['files']=[entry(p,p.name) for p in sorted((out/'pair_000').iterdir()) if p.is_file() and p.name!='index.json']
    write(out/'pair_000/index.json',idx)
    rep=read(out/'sim_report.json')
    rep['files']=[entry(p,str(p.relative_to(out))) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sim_report.json']
    rep['identity']['seeds_sha256']=sim.sha_file(out/'seeds.json')
    rep['identity']['manifest_sha256']=sim.sha_file(out/'manifest.json')
    write(out/'sim_report.json',rep)
def case_copy(name):
    p=root.parent/(root.name+'_'+name)
    shutil.copytree(out,p)
    return p

with mock.patch.object(bs,'master_seed',side_effect=forbidden), mock.patch.object(bs,'pair_seeds',side_effect=forbidden):
    out=root/sim.SIM_REL/'b4-mech-1_owner'
    with mock.patch.object(sim.Batch,'finish',new=capture):
        res=sim.run_batch(root,'b4-mech-1',1,3600,out,schedule=ts.SCHED_ONE)
    findings['baseline']={'status':res['status'],'exit_code':res['exit_code'],'verify':sv.verify_run_dir(out)}
    assert res['status']=='complete',res
    batch=captured[0]

    # Last verification is a started work unit; publication is a new unit.
    p=case_copy('deadline_after_verify'); (p/'sim_report.json').unlink()
    batch.out=p
    class Clock:
        t=1000.0
        def __call__(self):return self.t
    clock=Clock(); batch.dl=Deadline(60,clock=clock)
    real_verify=sv.verify_run_dir
    def expired_after(*a,**kw):
        f=real_verify(*a,**kw); clock.t+=10000; return f
    with mock.patch.object(sv,'verify_run_dir',side_effect=expired_after):
        got=real_finish(batch,'complete',None,0)
    findings['deadline_after_deep_verification']={'status':got['status'],'exit_code':got['exit_code'],
        'report_deadline':got['report']['deadline'],'actual_elapsed':batch.dl.elapsed(),
        'summary_present':got['report']['summary'] is not None,'published':(p/'sim_report.json').exists()}

    # Input checkpoint preceded the deep verification, but not publication.
    p=case_copy('drift_after_verify'); (p/'sim_report.json').unlink()
    batch.out=p; batch.dl=Deadline(3600)
    target=root/'docs/b4_architecture.md'; original=target.read_bytes()
    def drift_after(*a,**kw):
        f=real_verify(*a,**kw); target.write_bytes(original+b'\nowner input drift probe\n'); return f
    try:
        with mock.patch.object(sv,'verify_run_dir',side_effect=drift_after):
            got=real_finish(batch,'complete',None,0)
        findings['input_drift_after_deep_verification']={'status':got['status'],'exit_code':got['exit_code'],
            'input_digest_changed':sim.sha_file(target)!=batch.c['inputs']['docs/b4_architecture.md'],
            'published':(p/'sim_report.json').exists()}
    finally:target.write_bytes(original)

    # A complete pair downgraded to "written" can bypass the full arm audit.
    p=case_copy('unaudited_complete')
    rep=read(p/'sim_report.json'); rep['pairs'][0]['arms']['R']='written'; write(p/'sim_report.json',rep)
    idx=read(p/'pair_000/index.json'); idx['arms']['R']='written'; write(p/'pair_000/index.json',idx)
    (p/'pair_000/arm_R.audit.json').unlink()
    reindex(p)
    findings['complete_pair_without_R_audit']={'findings':real_verify(p),'path':str(p)}

    # A self-consistent arm from another exposed operator seed, same declared plan.
    p=case_copy('wrong_operator')
    task=sim.bl.make_task(7,batch.c['mapping'].addresses)
    port=ex.ObservationPort(batch.c['fabric'])
    d=be.run('R',task,port,12,sim.B_MAX).as_dict()
    doc=read(p/'pair_000/arm_R.result.json'); doc.update(operator_seed=12,result=d,port_calls=port.calls)
    write(p/'pair_000/arm_R.result.json',doc)
    rc=sn.recompute_findings(d,task)
    aud=read(p/'pair_000/arm_R.audit.json')
    aud.update(completion_findings=sim.completion_findings(d,'R',task,port.calls,None), replay_findings=br.replay(d,task),
        recompute={k:v for k,v in rc.items() if k!='relations_final'}|{'relations_final_sha256':ex.sha256_json(rc['relations_final'])},
        states=sn.arm_states(d,task),view_findings=[],invalid=False)
    write(p/'pair_000/arm_R.audit.json',aud)
    results={role:read(p/f'pair_000/arm_{role}.result.json')['result'] for role in sim.ROLES}
    curves=sim.curves_of(results,0,7,11); write(p/'pair_000/curves.json',curves)
    rows=copy.deepcopy(batch.rows); rows[0].update(base_fit=curves['base_fit'],best_at_grid=curves['best_at_grid'],
        f_end_to_end_at_grid=[x['value'] for x in curves['f_end_to_end_at_grid']])
    rep=read(p/'sim_report.json'); rep['summary']=sim.summarise_batch(rows,1)[0]; write(p/'sim_report.json',rep)
    reindex(p)
    findings['wrong_R_operator_seed']={'planned':11,'actual':12,'findings':real_verify(p),'path':str(p)}

    # Wrapper identities must also be compared to file position / planned pair.
    p=case_copy('wrong_pair_role')
    doc=read(p/'pair_000/arm_R.result.json'); doc.update(pair=99,role='O'); write(p/'pair_000/arm_R.result.json',doc)
    reindex(p)
    findings['wrong_pair_role']={'findings':real_verify(p),'path':str(p)}

write(DEST/'probes_results.json',findings)
print(json.dumps(findings,indent=1))
