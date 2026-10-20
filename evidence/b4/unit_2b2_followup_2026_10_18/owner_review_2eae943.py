import sys, copy, json, hashlib
from pathlib import Path

R=Path(__file__).resolve().parent
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_execution as ex
import b4_engine as be
import b4_ff_mapping as bm
import b4_ff_hypothesis as hy
import b4_ff_model as fm
import b4_landscape as bl
import b4_carto as bc
import b4_replay as br
from b4_test_fixtures import InjectingPort

m,h=bm.site_mapping(),hy.load()
mh=h.with_reading('clock_mode','not_inverted','not_inverted','mechanics',context='latch')
fab=fm.Fabric(m,mh)
task=bl.make_task(7,m.addresses)
o=be.run('O',task,ex.ObservationPort(fab),11,24).as_dict()
t=be.run('O',task,InjectingPort(fab,6),11,24).as_dict()
f=be.run('F',task,ex.ObservationPort(fm.Fabric(m,h)),11,24).as_dict()
report={'baseline': {name:br.replay(v,task) for name,v in [('complete_O',o),('terminated_O',t),('formal_terminated_F',f)]}}
checks={}
def check(name,base,edit):
    d=copy.deepcopy(base)
    edit(d)
    try:
        findings=br.replay(d,task)
        checks[name]={'accepted':findings==[],'findings':findings}
    except Exception as exc:
        checks[name]={'exception':type(exc).__name__+': '+str(exc)}
check('terminal_candidate_changed_to_base',t,lambda d:d['terminal'].update(genome=0,config_sha256=ex.sha256_json(ex.genome_to_config(0,task.addresses))))
check('terminal_identity_phase_digest',t,lambda d:d['terminal'].update(code='NOT_DOMAIN',phase='base',operator_seed=42,landscape_seed=42,budget=999,stimulus_sha256='0'*64,map_version=999))
check('both_rng_states_forged',t,lambda d:(d['terminal'].__setitem__('rng_state',0),d.__setitem__('rng_state_final',0)))
check('pending_children_removed',t,lambda d:d.__setitem__('pending_children',[]))
check('terminal_population_removed',t,lambda d:d.__setitem__('population',[]))
check('search_intervention_parent_forged',o,lambda d:d['ledger'][1].update(bits=[],parent_born=999,move_kind='oracle'))
check('completed_champion_forged',o,lambda d:d.__setitem__('champion',{'genome':0,'fit':999,'born':999}))
check('evals_cost_map_final_forged',o,lambda d:d.update(evals=999,cost={'base':0,'probes':0,'search':0,'holdout':0},map_version_final=999,map_specimens_final=999,map_commitment_final='0'*64))
check('formal_F_map_history_corrupted',f,lambda d:d['ledger'][1].update(map_version_before=999,map_version_after=999,map_commitment_after='0'*64))
report['replay_tampers']=checks
report['fixture_provenance']={'input_fixture':mh.fixture,'input_hypothesis_sha':mh.sha256,'model_digest_in_serialised_result':mh.sha256 in json.dumps(o),'fixture_key_in_result':'fixture' in o,'fixture_key_in_ledger':any('fixture' in e for e in o['ledger'])}

# Hand-written observation ledger: two addresses affect lane 0, two lane 1,
# two affect lanes 2 and 3. No fabric or landscape search is involved.
c,sh=bc.ObservationCarto(6),bc.ObservationCarto(6)
p=[1,0,3,2,5,4,7,6]
spec=[(0,[[0]*8])]
for bit,lanes in enumerate([(0,),(0,),(1,),(1,),(2,3),(2,3)]):
    row=[0]*8
    for lane in lanes: row[lane]=1
    spec.append((1<<bit,[row]))
for seq,(genome,grid) in enumerate(spec,1):
    sh.ingest(seq,genome,'s',grid)
    c.ingest(seq,genome,'s',bc.permute_grid(grid,p))
report['X_control']={'shadow_groups':sh.view().groups,'X_groups':c.view().groups,'same_partition':set(map(frozenset,sh.view().groups))==set(map(frozenset,c.view().groups)),'isomorphism_findings':bc.isomorphic(c,sh,p)}
ov=bc.oracle_view(m)
dv=bc.shuffled_view(ov,2)
report['privilege_provenance']={'oracle_privileged':ov.privileged,'shuffled_oracle_privileged':dv.privileged,'shuffled_origin':dv.origin}

imp=json.loads((R/'b4/IMPORT.json').read_text())
report['IMPORT_mismatches']=[p for p,v in imp['files'].items() if hashlib.sha256((R/p).read_bytes()).hexdigest()!=v['sha256']]
print(json.dumps(report,indent=2))
