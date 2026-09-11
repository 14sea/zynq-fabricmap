"""Read-only preflight and inert archived-ruling probes. No port or execute()."""
import copy,json,os,pwd,sys,tempfile
from pathlib import Path
from unittest.mock import patch
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_runner as rn
import b2_manifest as bm
import b1_qualification as bq
import claimb_r1p_instrument as inst
import test_b2_runner as tf
inst.bind(inst.DEFAULT_ROOT,require_git=False)
from validators import records
f=tf.Fixture('S1')
result={}
try:
 a=f.args(profile=rn.QUALIFICATION,pair_first=None,pair_count=None)
 a.boundary.write_text(json.dumps({'runner_user':pwd.getpwuid(os.getuid()).pw_name,'signer_user':a.signer_user,'key_store':str(a.key.parent)}))
 # Only the missing pin hook, unrelated principal boundary and executable lookup
 # are doubled. Actual manifest, image/build/instrument/B1-chain checks run.
 with patch.object(records,'boundary_established',return_value=True),patch.object(rn.shutil,'which',return_value='/test/sb'):
  cfg=rn.preflight(a,rn.QUALIFICATION,pins_verify=tf.stub_pins)
 plans={'producer':cfg['plan'],'offline':rn.qualification_session_plan(f.manifest,cfg['manifest_sha256'])}
 result['manifest_board']=f.manifest.get('board')
 result['lineage_board']=json.loads(bm.B1_MANIFEST.read_text())['board']['boardid']
 with patch.object(records,'boundary_established',return_value=True),patch.object(rn.shutil,'which',return_value='/test/sb'):
  for path in (a.ruling,a.provision_ruling):
   doc=json.loads(path.read_text());doc['boardid']='FFFF';path.write_text(json.dumps(doc))
  try:
   wrong_cfg=rn.preflight(a,rn.QUALIFICATION,pins_verify=tf.stub_pins)
   result['both_wrong_board_preflight']='ACCEPTED'
  except Exception as exc:result['both_wrong_board_preflight']=str(exc)
 for label,p in plans.items():
  result[label+'_expected_board']={'plan':p.get('boardid'),'binding':p['binding'].get('boardid')}
  with tempfile.TemporaryDirectory(prefix='b2-board-binding-') as temp:
   d=Path(temp)
   def check(boards,plan=p):
    for key,name in bq.RULING_FILES.items():
     body={k:p['binding'][k] for k in ('session','image_sha256','prereg_sha256','b2_manifest_sha256')}
     body.update(boardid=boards[key],granted_by='test-fixture-only',date='2026-09-11-00',ruling=rn.QUAL_RULING_TEXT if key=='whole_of_run' else rn.PROVISION_RULING_TEXT)
     if key=='whole_of_run':body['master_seed']=p['master_seed']
     (d/name).write_text(json.dumps(bq.archive_envelope(json.dumps(body).encode())))
    return rn.archived_ruling_findings(d,plan)
   correct={'whole_of_run':'17A6','provisioning':'17A6'}
   wrong={'whole_of_run':'FFFF','provisioning':'FFFF'}
   result[label+'_control']=check(correct)
   result[label+'_one_wrong']=check(dict(correct,whole_of_run='FFFF'))
   result[label+'_both_wrong']=check(wrong)
   result[label+'_both_wrong_with_explicit_expectation']=check(wrong,dict(p,boardid='17A6'))
   result[label+'_both_wrong_same_nonstring']=check({'whole_of_run':['FFFF'],'provisioning':['FFFF']})
finally:f.close()
print(json.dumps(result,indent=2))
for label in plans:
 assert not result[label+'_control']
 assert result[label+'_one_wrong']
 assert not result[label+'_both_wrong']
 assert result[label+'_both_wrong_with_explicit_expectation']

assert result["both_wrong_board_preflight"]=="ACCEPTED"
