import argparse, copy, hashlib, json, sys, tempfile
from pathlib import Path
ap=argparse.ArgumentParser();ap.add_argument('--repo-root',type=Path,required=True);arg=ap.parse_args()
sys.path.insert(0,str(arg.repo_root.resolve()/'b4/host'))
import b4_ff_mapping as bm, b4_ff_hypothesis as hy, b4_ff_model as fm
m,h=bm.site_mapping(),hy.load();f=fm.Fabric(m,h)
c={a:int(e.semantic in ('ff_srval','ce_mode','sr_mode','sr_kind')) for a,e in m.entries.items()}
results={}
latch={**c,m.address_of(None,'storage_kind'):1,m.address_of(None,'clock_mode'):1,m.address_of(None,'sr_kind'):0}
results['latch_endpoint_q']=[s['q_after'] for s in f.observe(latch,[fm.init(),fm.set_(0,ce=255,d=0),fm.set_(1,ce=255,d=0)])['steps']]
try:f.observe({**latch,m.address_of(None,'clock_mode'):0},[])
except fm.ModelRefusal as e:results['public_refusal']=str(e)
with tempfile.TemporaryDirectory(prefix='b4_followup_probe_') as tmp:
 tmp=Path(tmp)
 doc=json.loads(hy.HYPOTHESIS.read_text());doc['behaviour']['ce_gates_capture']=False
 p=tmp/'altered.json';p.write_text(json.dumps(doc))
 try:
  changed=hy.load(p)
  results['external_hypothesis']={'accepted':True,'fixture':changed.fixture,'q_after':fm.Fabric(m,changed).observe(c,[fm.init(),fm.set_(1,ce=0,d=0)])['steps'][-1]['q_after']}
 except (hy.HypothesisRefusal, TypeError) as e:results['external_hypothesis']={'accepted':False,'refusal':type(e).__name__+': '+str(e)}
 original=json.loads(bm.CERTIFICATE.read_text())
 for token in ('NOCLKINV','AFF.ZINI'):
  doc=copy.deepcopy(original);row=next(r for r in doc['feature_results'] if r['split']=='mine' and r['feature'].endswith('.'+token))
  a=row['predicted_assignments'][0];neg=not a['segbit']['negated'];a['segbit']['negated']=neg;a['expected_value']=0 if neg else 1;row['expected_transition']={'before':1 if neg else 0,'after':0 if neg else 1}
  p=tmp/(token+'.json');p.write_text(json.dumps(doc))
  try:
   mm=bm.site_mapping(path=p,expected_sha256=hashlib.sha256(p.read_bytes()).hexdigest())
   results['coordinated_'+token]={'accepted':True,'count':len(mm.addresses)}
  except bm.MappingRefusal as e:results['coordinated_'+token]={'accepted':False,'refusal':str(e)}
 doc=json.loads(hy.HYPOTHESIS.read_text());doc['decode']['clock_mode']['by_storage_context']['flipflop']['bit_one']='unknown'
 p=tmp/'flipflop_unknown.json';p.write_text(json.dumps(doc))
 try:hy.load(p);results['unknown_in_flipflop_context']={'accepted':True}
 except (hy.HypothesisRefusal, TypeError) as e:results['unknown_in_flipflop_context']={'accepted':False,'refusal':type(e).__name__+': '+str(e)}
 try:hy.fixture_file(p,'probe');results['unknown_in_flipflop_context_as_fixture']={'accepted':True}
 except hy.HypothesisRefusal as e:results['unknown_in_flipflop_context_as_fixture']={'accepted':False,'refusal':str(e)}
print(json.dumps(results,indent=2))
