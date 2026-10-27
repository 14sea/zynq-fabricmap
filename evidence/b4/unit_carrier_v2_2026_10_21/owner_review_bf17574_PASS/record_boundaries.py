from pathlib import Path
import json,sys,copy
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root']);sys.path[:0]=[str(P/'host'),str(P)]
import b4carrier_records as r
from tests.test_b4carrier_records import ClosedSets,ctx_for,INSTRUMENT,LINKS,TIMING,ROOT,fixture_stimuli,_h
C=ClosedSets();txs=r.transactions(r.load_trace(P/'sim/b4/out/session.jsonl'))
base=_h('signed-base-genome-0-frames'); loaded=_h('loaded-natural-carrier-frames'); links={**LINKS,'base_readback_sha256':base}
root=r.observation(txs[0],links,TIMING,seq=1,session='bench',predecessor=ROOT,declared_stimulus=[{'kind':'init'}]);rx=r.transaction_close(txs[0],root,seq=1,links=links)
cand=r.observation(txs[1],links,TIMING,seq=2,session='bench',predecessor={'kind':'closed','seq':1,'close_sha256':r.sha256_json(rx)},declared_stimulus=fixture_stimuli()[1]);cx=r.transaction_close(txs[1],cand,seq=2,links=links)
ctxr={**ctx_for(root['stimulus'],None),'base_readback_sha256':base,'loaded_frames_reference_sha256':loaded}
ctxc={**ctx_for(cand['stimulus'],r.sha256_json(rx)),'base_readback_sha256':base,'loaded_frames_reference_sha256':loaded}
chain=[{'o':root,'x':rx,'ctx':ctxr},{'o':cand,'x':cx,'ctx':ctxc}];so=r.session_open(INSTRUMENT,loaded,loaded)
results={'root_shape':r.validate_observation(root),'candidate_shape':r.validate_observation(cand),'root_close_shape':r.validate_close(rx,root),'candidate_close_shape':r.validate_close(cx,cand),'loaded_reference':loaded,'restored_base_reference':base,'honest_distinct_reference_chain':r.validate_chain(so,chain)}
o=C._o();x=C._x(o);ctx=ctx_for(o['stimulus'],None,session='s');valid_so=r.session_open(INSTRUMENT,LINKS['base_readback_sha256'],LINKS['base_readback_sha256'])
results['ordinary_fixture_chain']=r.validate_chain(valid_so,[{'o':o,'x':x,'ctx':ctx}])
cases={}
def call(name,func):
    try: cases[name]={'findings':func()}
    except Exception as exc: cases[name]={'raised':type(exc).__name__,'message':str(exc)}
for v in (None,[],5):call('session_open_'+repr(v),lambda v=v:r.validate_chain(v,[{'o':o,'x':x,'ctx':ctx}]))
for v in (None,[],5):
    z=copy.deepcopy(o);z['predecessor']=v
    call('predecessor_'+repr(v),lambda z=z:r.validate_chain(valid_so,[{'o':z,'x':x,'ctx':ctx}]))
z=copy.deepcopy(x);z['status']='faulted';z['fault']='bad'
call('faulted_X_bad_fault',lambda:r.validate_chain(valid_so,[{'o':o,'x':z,'ctx':ctx}]))
results['malformed_chain_inputs']=cases
(D/'record_boundaries.json').write_text(json.dumps(results,indent=2)+'\n');print(json.dumps(results,indent=2))
