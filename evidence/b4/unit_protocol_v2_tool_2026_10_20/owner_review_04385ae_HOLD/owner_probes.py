import copy
import hashlib
import json
import shutil
import subprocess
import sys
from pathlib import Path
from unittest import mock

R = Path('/home/test/zynq_fabricmap')
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else '/tmp/owner_04385ae_review_repro')
OUT.mkdir(exist_ok=False)
sys.path[:0] = [str(R/'b4/host'), str(R/'b4/tests')]
import b4_execution as ex
import b4_seeds as bs
import b4_sim as sim
import b4_sim_verify as sv
from test_b4_sim import build_hermetic, SCHED_ONE, git, reindex

results = {}
def keep():
    (OUT/'results.json').write_text(json.dumps(results, indent=2)+'\n')

# A fresh interpreter loads the actual modified informational constant, not a
# dictionary whose top-level informational field alone has been changed.
root = OUT/'identity_copy'
for rel in ('b4/host', 'b4/schemas'):
    shutil.copytree(R/rel, root/rel)
shutil.copyfile(R/'b4/IMPORT.json', root/'b4/IMPORT.json')
def ident():
    p = subprocess.run([sys.executable, '-B', str(root/'b4/host/b4_protocol.py')], capture_output=True, text=True)
    assert p.returncode == 0, p.stderr+p.stdout
    return json.loads(p.stdout)
a = ident()
f = root/'b4/host/b4_thresholds.py'
old = f.read_text()
assert old.count('ARCHITECTURE_REVISION = "v0.2.0"') == 1
f.write_text(old.replace('ARCHITECTURE_REVISION = "v0.2.0"', 'ARCHITECTURE_REVISION = "v0.2.1"'))
t = json.loads((root/'b4/IMPORT.json').read_text())
t['files']['b4/host/b4_thresholds.py']['sha256'] = hashlib.sha256(f.read_bytes()).hexdigest()
(root/'b4/IMPORT.json').write_text(json.dumps(t))
b = ident()
results['informational_constant_edit'] = {'before':a, 'after':b, 'method_changed':a['protocol_sha256'] != b['protocol_sha256']}
keep()
print('identity probe', results['informational_constant_edit'], flush=True)

class Alter(ex.ObservationPort):
    def __init__(self, fabric, kind):
        super().__init__(fabric)
        self.kind = kind
    def observe(self, config, stimulus):
        t = super().observe(config, stimulus)
        if self.kind == 'init_none' and self.calls == 1:
            t['steps'][0]['q_after'][0] = None
        if self.kind == 'drift' and self.calls == 2:
            t['fabric']['effect_sha256'] = 'a'*64
            t['owner_raw_marker'] = 'returned_target_with_drift'
        if self.kind == 'malformed' and self.calls == 1:
            t['steps'][0] = {'owner_raw_marker':'returned_malformed_target'}
        return t

def guard(*args, **kwargs):
    raise AssertionError('production derivation reached')

with mock.patch.object(bs, 'master_seed', side_effect=guard) as gm, mock.patch.object(bs, 'pair_seeds', side_effect=guard) as gp:
    work = build_hermetic(OUT/'fixture_root')
    outputs = {}
    def run(name, kind=None, write_patch=False):
        if git(work, 'status', '--porcelain').strip():
            git(work, 'add', '-A');git(work, 'commit', '-q', '-m', 'previous fixture')
        dest = work/sim.SIM_REL/('b4-mech-1_'+name)
        def factory(fab, role, pair):
            return Alter(fab, kind) if role == 'TARGET' and kind else ex.ObservationPort(fab)
        original = sim.Batch.write
        def interrupt_after_holdout(self, rel, doc, validator):
            value = original(self, rel, doc, validator)
            if rel.endswith('/target_holdout.json'):
                raise KeyboardInterrupt()
            return value
        ctx = mock.patch.object(sim.Batch, 'write', interrupt_after_holdout) if write_patch else mock.patch.object(sim.Batch, 'write', original)
        with ctx:
            r = sim.run_batch(work, 'b4-mech-1', 1, 3600, dest, schedule=SCHED_ONE, port_factory=factory)
        report = json.loads((dest/'sim_report.json').read_text())
        vf = sv.verify_run_dir(dest, deep=True)
        filenames = sorted(str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file())
        results[name] = {'status':r['status'], 'exit_code':r['exit_code'], 'task_state':report['pairs'][0]['task'], 'stop':report['stopped'], 'findings':vf, 'files':filenames}
        outputs[name] = dest
        keep()
        print(name, {k: results[name][k] for k in ('status','task_state','findings')}, flush=True)
        return dest

    normal = run('baseline')
    run('init_none', 'init_none')
    run('drift', 'drift')
    run('malformed', 'malformed')
    run('interrupt_after_holdout', write_patch=True)

    # A coherent invalid report containing a later setup readout without its
    # prerequisite earlier readout. Refresh all ordinary archive hashes.
    forged = work/sim.SIM_REL/'b4-mech-1_impossible_order'
    shutil.copytree(outputs['drift'], forged)
    (forged/'pair_000/target_search.json').unlink()
    shutil.copyfile(normal/'pair_000/target_holdout.json', forged/'pair_000/target_holdout.json')
    rep = json.loads((forged/'sim_report.json').read_bytes())
    def row(p):
        raw=p.read_bytes()
        return {'path':str(p.relative_to(forged)), 'sha256':hashlib.sha256(raw).hexdigest(), 'size':len(raw)}
    rep['files']=[row(p) for p in sorted(forged.rglob('*')) if p.is_file() and p.name!='sim_report.json']
    (forged/'sim_report.json').write_text(json.dumps(rep, indent=1, sort_keys=True)+'\n')
    vf = sv.verify_run_dir(forged, deep=True)
    cli = subprocess.run([sys.executable, '-B', str(R/'b4/host/b4_sim_verify.py'), str(forged)], capture_output=True, text=True)
    results['impossible_setup_order'] = {'findings':vf, 'fresh_exit':cli.returncode, 'fresh_stdout':cli.stdout}
    keep()
    print('impossible_setup_order',results['impossible_setup_order'],flush=True)
    results['production_derivation_calls'] = [gm.call_count, gp.call_count]
    keep()

# The go/no-go reference validator is exercised with refreshed MD / file hashes.
import b4_gonogo as gg
work=OUT/'fixture_root'
base=work/sim.SIM_REL/'b4-mech-1_baseline'
gout=work/'evidence/b4/gonogo/b4-mech-1_owner'
r=gg.write_decision(work,base,gout)
results['gonogo_baseline']={'status':r['status'],'findings':gg.verify_gonogo_dir(gout,root=work)}
original=json.loads((gout/'gonogo.json').read_bytes())
escaped=OUT/'escaped_batch';shutil.copytree(base,escaped)
results['gonogo_contract_probes']={}
for name,field,value in [('float_count','count',1.0),('integer_fixture','fixture',1),('outside_root_path','path','../escaped_batch')]:
    d=copy.deepcopy(original);d['batch'][field]=value
    md=gg.render_md(d).encode();d['files']=[{'path':'gonogo.md','sha256':hashlib.sha256(md).hexdigest(),'size':len(md)}]
    (gout/'gonogo.md').write_bytes(md);(gout/'gonogo.json').write_text(json.dumps(d,indent=1)+'\n')
    cli=subprocess.run([sys.executable,'-B',str(R/'b4/host/b4_gonogo.py'),'verify',str(gout)],capture_output=True,text=True)
    results['gonogo_contract_probes'][name]={'decision_findings':gg.decision_findings(d),'fresh_exit':cli.returncode,'fresh_stdout':cli.stdout}
    keep()
print('DONE', OUT, flush=True)
