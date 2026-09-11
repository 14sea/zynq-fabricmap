"""Offline seam probes: real archived B1Q transport, explicitly doubled B2 replay.
This is NOT a positive B2/B2Q session or a board qualification.
All modifications are confined to temporary copies.
"""
import copy, json, sys, tempfile, shutil
from pathlib import Path
from unittest.mock import patch
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_runner as rn
import b2_manifest as bm
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT,require_git=False)
import l6_schedule as ls
import test_b2_runner as tf
import test_b2_adjudicate as af
import b2_adjudicate as adj
result={}
source=R/'evidence/b1q/b1q_17A6_2026-09-08-01'
base=json.loads((source/'run_log.json').read_text())
plan=copy.deepcopy(base['l6'])
plan['expected_records']=len(base['loop_records'])
plan['session']='B2Q'
plan['session_timeout_s']=1.0
with tempfile.TemporaryDirectory(prefix='b2-contract-review-') as temp:
 d=Path(temp)
 for name in ('run_log.json','audits.json','timeline.json'):
  shutil.copyfile(source/name,d/name)
 def judge(log,manifest=None):
  (d/'run_log.json').write_text(json.dumps(log))
  # Only replay is doubled: the B1Q transcript has no B2 search blocks. Every
  # instrument validator, audit gate, ledger check and rate report runs for real.
  with patch.object(rn.adj,'adjudicate',return_value={'outcome':'PASS','findings':[],'kills':[]}):
   out=rn.judge_session(d,manifest or {},plan,{}, {},None,inst.DEFAULT_ROOT)
  return {k:out[k] for k in ('outcome','findings','measured_rate_per_hour','audit_policy','instrument')}
 result['instrument_control']=judge(base)
 plan['expected_records']-=1
 result['wrong_record_count_control']=judge(base)
 plan['expected_records']+=1
 for name,fn in (
  ('no_l6_binding',lambda x:x['l6'].pop('binding',None)),
  ('wrong_l6_image',lambda x:x['l6']['binding'].update(image_sha256='0'*64)),
  ('wrong_l6_manifest',lambda x:x['l6']['binding'].update(b2_manifest_sha256='0'*64)),
  ('wrong_identity_carrier',lambda x:x['app_identity'].update(carrier_sha256='0'*64)),
 ):
  log=copy.deepcopy(base);fn(log);result[name]=judge(log)
 result['different_manifest_argument']=judge(base,{'image':{'sha256':'f'*64}})
 result['files_present']=sorted(p.name for p in d.iterdir())
 # Counts beyond budget are independent negative controls over the real layer.
 timeline=json.loads((d/'timeline.json').read_text())
 original=copy.deepcopy(timeline)
 timeline['crc_dropped']=plan['crc_budget']+1
 (d/'timeline.json').write_text(json.dumps(timeline))
 result['crc_over_budget']=judge(base)
 (d/'timeline.json').write_text(json.dumps(original))
 # The record layer also ignores these outer bindings: no doubled replay here.
 af.BlankBaselines.setUpClass()
 for name,fn in (
  ('control',lambda x:None),
  ('no_l6',lambda x:x.pop('l6',None)),
  ('wrong_identity_carrier',lambda x:x['app_identity'].update(carrier_sha256='0'*64)),
 ):
  log=copy.deepcopy(af.BlankBaselines.whole);fn(log)
  out=adj.adjudicate([log],af.PLAN,af.PREDICTION,consts=af.CONSTS,scope='session',common=True)
  result['real_record_replay_'+name]={k:out.get(k) for k in ('outcome','findings','kills')}
 # Evidence membership is tested directly, without asserting a valid transition.
 fixture=tf.Fixture('S1')
 try:
  ev=d/'membership';ev.mkdir()
  (ev/bm.MANIFEST_AT_RUN).write_text(bm.render(fixture.manifest))
  (ev/'run_log.json').write_text('{}')
  (ev/'adjudication.json').write_text(json.dumps({'outcome':'PASS','session':'B2Q','measured_rate_per_hour':2807.0,'audit_policy':'all-self-reporting'}))
  for n in ('audits.json','timeline.json','exports.json','console.log','console.ts.log'):
   (ev/n).write_text('{}')
  before=bm.reconstruct_qualification_record(ev)
  ignored={}
  for n in ('audits.json','timeline.json','exports.json','console.log','console.ts.log'):
   (ev/n).write_text('changed bytes')
   ignored[n]=bm.reconstruct_qualification_record(ev)==before
  result['qualification_record_membership']={'files':sorted(before['files']),'unchanged_after_file_change':ignored}
 finally:fixture.close()
print(json.dumps(result,indent=2))
assert result['instrument_control']['outcome']=='PASS'
assert result['instrument_control']['instrument']['rate_report']['session_span_s']>plan['session_timeout_s']
assert result['crc_over_budget']['outcome'].startswith('HOLD')
assert all(result[n]['outcome']=='PASS' for n in ('no_l6_binding','wrong_l6_image','wrong_l6_manifest','wrong_identity_carrier','different_manifest_argument'))
assert all(result['real_record_replay_'+n]['outcome']=='PASS' for n in ('control','no_l6','wrong_identity_carrier'))

assert result['wrong_record_count_control']['outcome'].startswith('HOLD')
assert all(result['qualification_record_membership']['unchanged_after_file_change'].values())
