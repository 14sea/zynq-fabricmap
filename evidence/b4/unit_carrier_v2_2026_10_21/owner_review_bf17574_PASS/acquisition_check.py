from pathlib import Path
import json,sys
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root']);sys.path[:0]=[str(P/'host'),str(P)]
import b4carrier_records as r
from tests.test_b4carrier_records import LINKS,TIMING,ROOT,fixture_stimuli
stim=fixture_stimuli()[1]
tx=r.transactions(r.load_trace(P/'sim/b4/out/early_cleanup.jsonl'))[1]
cut=next(i for i,e in enumerate(tx) if e.get('op')=='wr' and e.get('addr')==0x2000 and e.get('data')==0x1000)
assert r.acquisition_boundary(tx[:cut],len(stim))[1]=='open'
try:r.observation(tx[:cut],LINKS,TIMING,seq=2,session='bench',predecessor=ROOT,declared_stimulus=stim)
except r.RecordRefusal as e: refused=str(e)
else:raise AssertionError('open incomplete acquisition was sealed')
root=r.transactions(r.load_trace(P/'sim/b4/out/session.jsonl'))[0]
o=r.observation(root,LINKS,TIMING,seq=1,session='bench',predecessor=ROOT,declared_stimulus=stim)
assert o['status']=='invalid' and o['fault']['code']=='premature_operation' and r.validate_observation(o)==[]
assert r.acquisition_boundary(root,1)[1]=='sealed'
out={'open_incomplete_acquisition_refused':refused,'premature_accepted_O_fault':o['fault'],'premature_accepted_O_findings':r.validate_observation(o),'same_root_with_actual_init_only_stimulus':'sealed'}
(D/'acquisition_check.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
