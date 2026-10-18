import sys,copy,json,hashlib
from pathlib import Path
R=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_engine as be,b4_execution as ex,b4_ff_model as fm,b4_ff_hypothesis as hy,b4_ff_mapping as bm,b4_landscape as bl,b4_replay as br,b4_carto as bc
from b4_test_fixtures import mechanics_fabric,InjectingPort

m,h=bm.site_mapping(),hy.load()
fab=mechanics_fabric()
task=bl.make_task(7,m.addresses)
o=be.run('O',task,ex.ObservationPort(fab),11,24).as_dict()
report={}
class Drifting(ex.ObservationPort):
    __slots__=()
    def observe(self,config,stimulus):
        t=super().observe(config,stimulus)
        if self.calls==3:
            t=dict(t);t['hypothesis']=dict(t['hypothesis'],sha256='0'*64)
        return t
def verdict(r):
    try:return {'findings':br.replay(r,task)}
    except Exception as e:return {'uncaught':type(e).__name__+': '+str(e)}

drift=be.run('R',task,Drifting(fab),11,8).as_dict()
val=be.run('R',task,InjectingPort(fab,3,exc=ValueError('value refusal')),11,8).as_dict()
report['legitimate_refusals']={
    'provenance_drift':{'record':drift['other_refusal'],**verdict(drift)},
    'ValueError':{'record':val['other_refusal'],**verdict(val)}
}
variants={k:fm.fixture(k,m,h,seed=5) for k in ['truth','permuted','dropout']}
# Compare source identity only using a baseline observation, not search performance.
traces={k:f.observe({a:0 for a in m.addresses},list(task.stimulus)) for k,f in variants.items()}
headers={k:{'hypothesis':t['hypothesis'],'mapping':t['mapping']} for k,t in traces.items()}
report['effect_identity']={'headers_equal':all(v==headers['truth'] for v in headers.values()),'fixture_markers':{k:v['hypothesis']['fixture'] for k,v in headers.items()},'effect_digests_differ':ex.sha256_json(variants['truth'].effect)!=ex.sha256_json(variants['permuted'].effect),'dropout':sorted(variants['dropout'].dropout)}
report['malformed']={}
for name,edit in [
    ('terminal_is_list',lambda d:d.__setitem__('terminal',[1])),
    ('grid_truncated',lambda d:d['ledger'][0].__setitem__('q_grid',[])),
    ('genome_wrong_type',lambda d:d['ledger'][0].__setitem__('genome','bad')),
    ('given_view_invalid',lambda d:d.__setitem__('given_view',{'groups':[]})),
    ('integer_completed',lambda d:d.__setitem__('completed',1)),
]:
    d=copy.deepcopy(o);edit(d);report['malformed'][name]=verdict(d)

# Regenerate a result from a malformed source header, then replay it.
class IncompleteIdentity(ex.ObservationPort):
    __slots__=()
    def observe(self,config,stimulus):
        t=super().observe(config,stimulus)
        t=dict(t);t['hypothesis']={'sha256':'x','fixture':False};t['mapping']={'certificate_sha256':'y'}
        return t
r=be.run('R',task,IncompleteIdentity(fab),11,8).as_dict()
report['malformed_identity']={'completed':r['completed'],'other_refusal':r['other_refusal'],'provenance':r['provenance'],**verdict(r)}

report['old_probe_fixes']={}
t=be.run('O',task,InjectingPort(fab,6),11,24).as_dict()
f=be.run('F',task,ex.ObservationPort(fm.Fabric(m,h)),11,24).as_dict()
for name,base,edit in [
    ('both_rng_forged',t,lambda d:(d['terminal'].__setitem__('rng_state',0),d.__setitem__('rng_state_final',0))),
    ('F_map_history',f,lambda d:d['ledger'][1].update(map_version_before=999,map_version_after=999,map_commitment_after='0'*64)),
    ('pending_removed',t,lambda d:d.__setitem__('pending_children',[])),
]:
    d=copy.deepcopy(base);edit(d);report['old_probe_fixes'][name]=verdict(d)
ov=bc.shuffled_view(bc.oracle_view(m),2)
report['shuffled_oracle']={'privileged':ov.privileged,'provenance':ov.provenance,'base_commitment':ov.base_commitment}
hh=be.run('O',task,InjectingPort(fab,26),11,24).as_dict()
report['holdout']={'completed':hh['completed'],'search_completed':hh['search_completed'],**verdict(hh)}
groups=bc.oracle_view(m).groups
pi=list(range(21))
for g in groups:
    for i,a in enumerate(g):pi[a]=g[(i+1)%len(g)]
report['X_A_counterexample']={'group_sizes':[len(g) for g in groups],'pi':pi,'fixed_points':[a for a,b in enumerate(pi) if a==b],'same_partition':set(map(frozenset,groups))=={frozenset(pi[a] for a in g) for g in groups},'construction':'rotate within each of the eight two-address groups and within the five-address group; host-only algebraic counterexample, no search'}
imp=json.loads((R/'b4/IMPORT.json').read_text())
report['IMPORT_mismatches']=[p for p,v in imp['files'].items() if hashlib.sha256((R/p).read_bytes()).hexdigest()!=v['sha256']]
print(json.dumps(report,indent=2))
