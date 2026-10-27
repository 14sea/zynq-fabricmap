from pathlib import Path
import json,sys,copy
D=Path(__file__).resolve().parent
P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
sys.path[:0]=[str(P/'host'),str(P)]
import b4carrier_records as r
from tests.test_b4carrier_records import ClosedSets,ctx_for,INSTRUMENT,LINKS,TIMING,ROOT,fixture_stimuli,_h
c=ClosedSets(); o=c._o(); x=c._x(o); ctx=ctx_for(o['stimulus'],None,session='s')
so=r.session_open(INSTRUMENT,_h('startup'),_h('startup'))
results={'baseline_chain':r.validate_chain(so,[{'o':o,'x':x,'ctx':ctx}])}
z=copy.deepcopy(so); z['instrument']={'variant':'00000000','carrier_sha256':_h('foreign'),'image_sha256':_h('foreign-image')}; z['startup_readback_sha256']=z['base_frames_reference_sha256']=_h('not-the-pinned-reference')
results['foreign_session_open_and_self_chosen_reference']=r.validate_chain(z,[{'o':o,'x':x,'ctx':ctx}])
z=copy.deepcopy(x);z['seq']=999
results['close_sequence_999_for_observation_1']=r.validate_chain(so,[{'o':o,'x':z,'ctx':ctx}])
z=copy.deepcopy(x);z['cleanup']['steps'][0].update(clock_before=0,edge=None)
results['cleanup_skips_real_falling_edge']=r.validate_bound(o,ctx,None,z)
z=copy.deepcopy(x);z['cleanup']['steps'][0].update(ce=False,sr=0.0,d=False,clock_after=0.0)
results['cleanup_non_integer_zero_values']=r.validate_close(z,o)
z=copy.deepcopy(o);z['seq']=2;z['predecessor']={'kind':'closed','seq':999,'close_sha256':r.sha256_json(x)}
x2=c._x(z);x2['seq']=2
results['predecessor_sequence_999_for_previous_close_1']=r.validate_chain(so,[{'o':o,'x':x,'ctx':ctx},{'o':z,'x':x2,'ctx':{**ctx,'predecessor_close_sha256':r.sha256_json(x)}}])
fr=r.fitness(o,{'mask':[[1,1],[1,0]],'target':[1,1],'weights':[1,1],'digest':_h('task')});fr['fitness']=999
results['arbitrary_fitness_999_bound_to_trusted_task_digest']=r.validate_bound(o,ctx,fr,x)
z=copy.deepcopy(o);z.update(status='invalid',fault={'code':'sequence','phase_reached':'P2','step_reached':None});z.pop('initial');z.pop('fabric_readback_sha256_post_event')
results['invalid_P2_with_two_future_steps']=r.validate_observation(z)
# Proper init-only root -> candidate chain, no model-null precondition.
root=copy.deepcopy(o);root['stimulus']=root['stimulus'][:1];root['stimulus_sha256']=r.sha256_json(root['stimulus']);root['steps']=root['steps'][:1]
rx=c._x(root);rx['cleanup']['steps'][0].update(clock_before=0,edge=None,q_after=[1]*8);rx['cleanup']['final_q']=[1]*8
cand=copy.deepcopy(o);cand['seq']=2;cand['predecessor']={'kind':'closed','seq':1,'close_sha256':r.sha256_json(rx)}
cx=c._x(cand);cx['seq']=2
base=[{'o':root,'x':rx,'ctx':ctx_for(root['stimulus'],None,session='s')},{'o':cand,'x':cx,'ctx':ctx_for(cand['stimulus'],r.sha256_json(rx),session='s')}]
results['proper_init_only_root_candidate_baseline']=r.validate_chain(so,base)
foreign=copy.deepcopy(so);foreign['instrument']['carrier_sha256']=_h('foreign-carrier');foreign['startup_readback_sha256']=foreign['base_frames_reference_sha256']=_h('arbitrary-new-reference')
results['proper_chain_foreign_open_and_reference']=r.validate_chain(foreign,base)
bad=copy.deepcopy(base);bad[1]['o']['predecessor']['seq']=999;bad[1]['x']['observation_sha256']=r.sha256_json(bad[1]['o'])
results['proper_chain_wrong_predecessor_seq']=r.validate_chain(so,bad)
try: results['chain_malformed_O']=r.validate_chain(so,[{'o':[],'x':rx,'ctx':ctx}])
except Exception as exc: results['chain_malformed_O']={'raised':type(exc).__name__,'message':str(exc)}
# Real MMIO trace, no new observations. O at P6 versus the same O built after P9 or P10.
flow=r.transactions(r.load_trace(P/'sim/b4/out/flow.jsonl'))
ev=flow[1];stim=fixture_stimuli()[1]
cut=next(i for i,e in enumerate(ev) if e.get('op')=='wr' and e.get('addr')==0x2000 and e.get('data')==0x1000)
a=r.observation(ev[:cut],LINKS,TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=stim)
b=r.observation(ev,LINKS,TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=stim)
results['real_P6_observation_vs_full_trace']={'P6_findings':r.validate_observation(a),'full_findings':r.validate_observation(b),'P6_count':a['init_event']['parameters']['gsr_count_after'],'full_count':b['init_event']['parameters']['gsr_count_after'],'P6_sha256':r.sha256_json(a),'full_sha256':r.sha256_json(b)}
# After the completed P6, provoke CLOSE without restore; sticky fault belongs to X, not O.
e=ev[:cut]+[{'op':'wr','addr':0x2000,'data':0x2000,'resp':0},{'op':'rd','addr':0x2008,'data':7,'resp':0}]
after=r.observation(e,LINKS,TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=stim)
try:
    xx=r.transaction_close(e,a,seq=2,links=LINKS)
    close_result={'X_status':xx['status'],'X_findings':r.validate_close(xx,a)}
except r.RecordRefusal as exc:
    close_result={'raised':str(exc)}
results['post_P6_sequence_fault']={'rebuilt_O_status':after['status'],'rebuilt_O_fault':after.get('fault'),**close_result}
(D/'record_probe_results.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
