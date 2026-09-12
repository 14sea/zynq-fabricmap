"""Review B2 pin coverage on a temporary mirror. No original file is modified."""
from pathlib import Path
import copy,hashlib,json,os,shutil,subprocess,sys,tempfile
R=Path('/home/test/zynq_fabricmap')
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_manifest as bm
import b2_pins as pin
from test_b2_runner import Fixture

d=Path(tempfile.mkdtemp(prefix='b2_pin_coverage_review_'))
root=d/'mirror';root.mkdir()
f=Fixture('S1');m=copy.deepcopy(f.manifest)
# Absolute external fixture prereg path remains live when the repository is mirrored.
m['prereg']['path']=str(f.prereg)
table=json.loads(pin.PINS.read_text())
names=set(table['files'])|{'manifests/b2_instrument_pins.json'}
def paths(x):
 if isinstance(x,dict):
  for k,v in x.items():
   if k=='path' and isinstance(v,str) and not Path(v).is_absolute() and (R/v).is_file(): names.add(v)
   paths(v)
 elif isinstance(x,list):
  for v in x: paths(v)
paths(m)
omitted=sorted(str(p.relative_to(R)) for base in ('tb/b2/hostapp','firmware/b2/bsp/src','firmware/b2/bsp/include') for p in (R/base).rglob('*') if p.is_file() and str(p.relative_to(R)) not in names)
for rel in names|set(omitted):
 dest=root/rel;dest.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(R/rel,dest)
mp=d/'manifest.json';mp.write_text(bm.render(m))
initial_manifest=hashlib.sha256(mp.read_bytes()).hexdigest()
initial_table=hashlib.sha256((root/'manifests/b2_instrument_pins.json').read_bytes()).hexdigest()
code='''import json,sys
from pathlib import Path
import b2_manifest as bm,b2_pins as pin
m=json.load(open(sys.argv[1]));root=Path(sys.argv[2]);out={}
for name,call in [('pins',lambda:pin.verify(m,root=root)),('manifest',lambda:bm.verify(m,root=root))]:
 try: out[name]={'result':'ACCEPTED','value':call()}
 except (pin.PinRefusal,bm.Refusal) as e: out[name]={'result':'REFUSED','message':str(e)}
print(json.dumps(out))
'''
def verify():
 p=subprocess.run([sys.executable,'-c',code,str(mp),str(root)],cwd=R,env=dict(os.environ,PYTHONPATH=str(R/'host')),capture_output=True,text=True)
 return json.loads(p.stdout) if p.returncode==0 else {'exception':p.stderr}
def build():
 p=subprocess.run(['bash',str(root/'tb/b2/hostapp/build.sh'),str(d/'native')],capture_output=True,text=True)
 return {'returncode':p.returncode,'stderr':p.stderr[-1200:]}
result={'reviewed_head':subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip(),'omitted':omitted,'baseline':verify(),'native_build_baseline':build(),'cases':{}}
if result['native_build_baseline']['returncode']==0:
 p=subprocess.run([str(d/'native/hostapp'),'startup_valid'],capture_output=True,text=True)
 result['native_startup_baseline']={'returncode':p.returncode,'result':[x for x in p.stdout.splitlines() if x.startswith('RESULT ')]}
for rel in ('tb/b2/hostapp/hostapp.c','tb/b2/hostapp/build.sh','tb/b2/hostapp/hostbsp/xil_io.h','firmware/b2/bsp/src/console.c','firmware/b2/bsp/include/xparameters.h','host/b2_records.py','tests/test_b2_hostapp.py'):
 p=root/rel;old=p.read_bytes()
 try:
  p.write_bytes((b'exit 73\n' if rel.endswith('.sh') else b'#error REVIEW_PIN_COVERAGE_MUTATION\n')+old)
  res=verify()
  if rel.startswith('tb/'):res['native_build']=build()
  result['cases'][rel]=res
 finally:p.write_bytes(old)
new=root/'host/b2_review_new.py'
try:
 new.write_text('# review-only additional module\n');result['new_glob_member']=verify()
finally:new.unlink()
assert hashlib.sha256(mp.read_bytes()).hexdigest()==initial_manifest
assert hashlib.sha256((root/'manifests/b2_instrument_pins.json').read_bytes()).hexdigest()==initial_table
result['unchanged_manifest_sha256']=initial_manifest
result['unchanged_table_sha256']=initial_table
result['temporary_artifacts']=str(d)
(d/'result.json').write_text(json.dumps(result,indent=2)+'\n')
print(json.dumps(result,indent=2))
