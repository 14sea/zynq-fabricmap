"""Acceptance over all twelve previously omitted inputs; only temporary copies change."""
import hashlib,json,os,subprocess,sys
from pathlib import Path
R=Path('/home/test/zynq_fabricmap')
sys.path.insert(0,str(R/'host'))
import b2_pins as pin
d=Path(sys.argv[1]);root=d/'mirror';mp=d/'manifest.json'
m=json.loads(mp.read_text())
paths=json.loads((R/'evidence/b2/review_pins_2026_09_12/coverage.json').read_text())['omitted']
assert len(paths)==12
initial=(hashlib.sha256(mp.read_bytes()).hexdigest(),pin.sha256_of(root/'manifests/b2_instrument_pins.json'))
code='''import json,sys
from pathlib import Path
import b2_manifest as m
try: print(json.dumps({'result':'ACCEPTED','value':m.verify(json.load(open(sys.argv[1])),root=Path(sys.argv[2]))}))
except m.Refusal as e: print(json.dumps({'result':'REFUSED','message':str(e)}))
'''
def check():
 try:a={'result':'ACCEPTED','value':pin.verify(m,root=root)}
 except pin.PinRefusal as e:a={'result':'REFUSED','message':str(e)}
 p=subprocess.run([sys.executable,'-c',code,str(mp),str(root)],env=dict(os.environ,PYTHONPATH=str(R/'host')),cwd=R,capture_output=True,text=True)
 assert p.returncode==0,p.stderr
 return {'pins':a,'fresh_manifest':json.loads(p.stdout)}
out={'baseline':check(),'cases':{}}
assert all(v['result']=='ACCEPTED' for v in out['baseline'].values())
for rel in paths:
 p=root/rel;raw=p.read_bytes()
 for mode in ('change','delete'):
  try:
   if mode=='change':p.write_bytes(raw+b'\nREVIEW_INPUT_CHANGED\n')
   else:p.unlink()
   res=check();out['cases'][rel+' '+mode]=res
   assert all(v['result']=='REFUSED' and rel in v['message'] for v in res.values()),res
  finally:p.write_bytes(raw)
out['restored']=check()
assert all(v['result']=='ACCEPTED' for v in out['restored'].values())
assert initial==(hashlib.sha256(mp.read_bytes()).hexdigest(),pin.sha256_of(root/'manifests/b2_instrument_pins.json'))
out['manifest_and_table_unchanged']=True
out['negative_cases']=len(out['cases'])
(d/'acceptance_matrix.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps({'negative_cases':len(out['cases']),'all_named_refusals':True,'positive_controls':'ACCEPTED','output':str(d/'acceptance_matrix.json')}))
