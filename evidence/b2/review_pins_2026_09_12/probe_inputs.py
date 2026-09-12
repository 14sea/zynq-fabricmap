"""Read-only checks of the new instrument_pins input boundary and real CLI."""
import copy,json,os,sys,subprocess,tempfile,pwd
from pathlib import Path
from unittest.mock import patch
R=Path('/home/test/zynq_fabricmap')
sys.path[:0]=[str(R/'host'),str(R/'tests')]
from test_b2_runner import Fixture
import b2_pins as pins,b2_manifest as bm,b2_runner as rn,b2_modelled_session as ms

f=Fixture('S1');out={'cases':{}}
for label,bad in [('string','broken'),('list',[{}]),('boolean',True),('number',7),('empty',{}),('missing',None)]:
 m=copy.deepcopy(f.manifest)
 if bad is None:m.pop('instrument_pins')
 else:m['instrument_pins']=bad
 res={}
 for name,fn in [('pins',lambda:pins.verify(m)),('manifest',lambda:bm.verify(m))]:
  try:res[name]={'result':'ACCEPTED','value':fn()}
  except (pins.PinRefusal,bm.Refusal) as e:res[name]={'result':'REFUSED','message':str(e)}
  except Exception as e:res[name]={'result':'UNEXPECTED_EXCEPTION','type':type(e).__name__,'message':str(e)}
 mp=f.d/'bad.json';mp.write_text(json.dumps(m))
 cp=subprocess.run([sys.executable,str(R/'host/b2_pins.py'),'--manifest',str(mp)],cwd=R,capture_output=True,text=True)
 res['cli']={'rc':cp.returncode,'stderr':cp.stderr};out['cases'][label]=res

out['real_pins_baseline']=pins.verify(f.manifest)
ms.bind_instrument(False)
a=f.args(profile=rn.QUALIFICATION,pair_first=None,pair_count=None)
a.boundary.write_text(json.dumps({'runner_user':pwd.getpwuid(os.getuid()).pw_name,
    'signer_user':a.signer_user,'key_store':str(a.key.parent)}))
from validators import records
which=rn.shutil.which
with patch.object(records,'boundary_established',return_value=None),patch.object(rn.shutil,'which',side_effect=lambda x:'/offline/review/sb' if x=='sb' else which(x)):
 cfg=rn.preflight(a,rn.QUALIFICATION)
out['real_pins_preflight']={'pins':cfg['pins'],'session':cfg['plan']['session'],
                           'doubles':['boundary_established','sb discovery'],'out_created':a.out.exists()}
dest=f.d/'cli_modelled'
cp=subprocess.run([sys.executable,str(R/'host/b2_modelled_session.py'),'--manifest',str(f.path()),'--out',str(dest)],cwd=R,capture_output=True,text=True)
res=json.loads(cp.stdout)
out['model_cli']={'rc':cp.returncode,'verdict':res['verdict']['outcome'],'crc_dropped':res['crc_dropped'],
                  'adjudication':json.loads((dest/'adjudication.json').read_text())['outcome'],
                  'summary':json.loads((dest/'summary.json').read_text())['outcome']}
m2=bm.qualify(f.manifest,dest,readjudicate=rn.readjudicator(f.manifest))
out['model_cli_real_qualify']={'qualified':m2['qualified'],'calibration':m2['calibration']}
out['temporary_artifacts']=str(f.d)
(f.d/'review_inputs.json').write_text(json.dumps(out,indent=2)+'\n')
print(json.dumps(out,indent=2))
