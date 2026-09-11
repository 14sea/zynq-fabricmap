"""Independent board-authority acceptance in fresh processes; temporary files only."""
import copy,json,sys,subprocess
from pathlib import Path
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_manifest as bm
import test_b2_runner as tf
f=tf.Fixture('S1');out={}
try:
 cases={'valid':copy.deepcopy(f.manifest)}
 for name,value in [('missing',None),('wrong','FFFF'),('array',['17A6']),('blank','   ')]:
  m=copy.deepcopy(f.manifest)
  if name=='missing':m.pop('board')
  else:m['board']['boardid']=value
  cases[name]=m
 # A mutually consistent rewritten declaration and lineage hash still needs the
 # existing B1 qualification chain; no original B1 file is touched.
 m=copy.deepcopy(f.manifest);m['board']['boardid']='FFFF'
 b1=json.loads(bm.B1_MANIFEST.read_text());b1['board']['boardid']='FFFF'
 p=f.d/'changed_lineage.json';p.write_text(json.dumps(b1))
 m['carrier_lineage']['b1_manifest']={'path':str(p),'sha256':bm.sha256_file(p)}
 cases['rewritten_board_and_lineage']=m
 code="""import sys,json
from pathlib import Path
sys.path.insert(0,sys.argv[1]+'/host')
import b2_manifest as m
try:
 r=m.verify(json.loads(Path(sys.argv[2]).read_text()))
 print(json.dumps({'accepted':True,'stage':r['stage'],'board':r['checks'].get('board')}))
except m.Refusal as e:
 print(json.dumps({'accepted':False,'refusal':str(e)}))
"""
 for name,m in cases.items():
  p=f.d/(name+'.json');p.write_text(bm.render(m))
  r=subprocess.run([sys.executable,'-c',code,str(R),str(p)],cwd=R,capture_output=True,text=True,check=True)
  out[name]=json.loads(r.stdout)
finally:f.close()
print(json.dumps(out,indent=2))
assert out['valid']['accepted'] and out['valid']['board']=='17A6'
assert all(not v['accepted'] for k,v in out.items() if k!='valid')
assert 'B1 qualification chain' in out['rewritten_board_and_lineage']['refusal']
