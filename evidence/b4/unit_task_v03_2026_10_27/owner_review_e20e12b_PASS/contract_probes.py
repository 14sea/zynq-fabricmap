from pathlib import Path
import json,sys,copy
from unittest import mock
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root']);sys.path[:0]=[str(P/'b4/host'),str(P/'host')]
import b4_landscape as bl,b4_ff_mapping as bm,b4_ff_hypothesis as hy,b4_ff_model as fm,b4_execution as ex,b4_target as bt,b4_sim_schema as sc,b4_protocol as bp,b4_seeds as bs,b4carrier_regmap as cr

def forbidden(*a,**k):raise AssertionError('production derivation reached')
class Scripted:
    def __init__(self):self.values=iter([0,0,0xA5,1,3,0x5A]);self.calls=[]
    def uniform(self,n):self.calls.append(n);v=next(self.values);assert 0<=v<n;return v
out={'scope':'explicit already exposed mechanics seeds only; no batch/production draw; self-score is not search success','seed_fixture_values':[3,5,7,8]}
with mock.patch.object(bs,'master_seed',side_effect=forbidden) as guard1,mock.patch.object(bs,'pair_seeds',side_effect=forbidden) as guard2:
    scripted=Scripted();a=bl._set_step(scripted,1);b=bl._set_step(scripted,0)
    assert scripted.calls==[2,4,256,2,4,256]
    assert a=={'kind':'set','clock':1,'ce':255,'sr':255,'d':0xA5} and b=={'kind':'set','clock':0,'ce':0,'sr':0,'d':0x5A}
    out['scripted_draws']={'uniform_arguments':scripted.calls,'steps':[a,b]}
    m=bm.site_mapping();fab=fm.Fabric(m,hy.load());rows=[]
    for seed in out['seed_fixture_values']:
        parts=bl.public_parts(seed);plan=bt.plan(0,seed,11,m);g=plan['planted_genome'];c=ex.genome_to_config(g,m.addresses)
        assert not ((g >> bt.storage_kind_bit(m)) & 1)
        traces=[fab.observe(c,list(parts[n])) for n in ('stimulus','holdout_stimulus')]
        recs=[bt.record_from_trace(t,g,parts[n],m.addresses,ph) for t,n,ph in zip(traces,('stimulus','holdout_stimulus'),bt.PHASES)]
        assert all(bt.observation_findings(t,len(parts[n]))==[] for t,n in zip(traces,('stimulus','holdout_stimulus')))
        ds={name:ex.sha256_json(obj) for name,obj in zip(bt.SETUP_FILES[:3],(plan,*recs))}
        task,doc=bt.finish(plan,*recs,ds)
        doc=json.loads(json.dumps(dict(doc,written_utc="owner-mechanics-fixture")))
        assert task.ceiling==64 and task.holdout_ceiling==80
        assert bl.score(traces[0],task)==(64,0) and bl.score_holdout(traces[1],task)==(80,0)
        assert sc.task_findings(doc)==[],sc.task_findings(doc)
        assert bt.setup_findings(plan,*recs,doc,m,None)==[]
        for name in ('stimulus','holdout_stimulus'):
            assert bl.stimulus_findings(parts[name])==[]
            for st in parts[name][1:]:
                w=cr.step_word(st['d'],st['ce'],st['sr'],st['clock']);assert cr.realisable(st['ce'],st['sr']);assert cr.decode_applied(w)=={k:st[k] for k in ('d','ce','sr','clock')}
        bad=copy.deepcopy(doc);bad['public_task']['stimulus'][2]['ce']=128;bad['task_digest']=bt.task_from_dict(bad['public_task']).digest();f=sc.task_findings(bad);assert any('broadcast' in x for x in f)
        rows.append({'fixture_seed':seed,'search_score_on_planted_trace':64,'holdout_score_on_planted_trace':80,'setup_findings':[],'old_shape_refused':f})
    out['planted_checks']=rows
    iden=bp.identity();out['protocol_sha256']=bp.protocol_sha256(iden);out['task_identity']=iden['task'];out['architecture_revision']=iden['architecture_revision']
    out['production_derivation_calls']=[guard1.call_count,guard2.call_count];assert out['production_derivation_calls']==[0,0]
(D/'contract_probes.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
