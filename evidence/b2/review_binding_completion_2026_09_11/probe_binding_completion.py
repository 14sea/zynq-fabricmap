"""Offline contract probes, not a complete B2 session.
The transport fixture is a temporary B1Q copy with consistent synthetic B2 invocation
metadata. Only B2 replay is doubled. Original evidence and live rulings are untouched.
"""
import copy,json,sys,tempfile,shutil
from pathlib import Path
from unittest.mock import patch
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b2_runner as rn
import b2_manifest as bm
import b1_session as sess
import b1_qualification as q
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT,require_git=False)
import test_b2_runner as tf
import test_b2_adjudicate as af
result={}
f=tf.Fixture('S1')
try:
 with tempfile.TemporaryDirectory(prefix='b2-bind-review-') as temp:
  d=Path(temp);source=R/'evidence/b1q/b1q_17A6_2026-09-08-01'
  for n in bm.QUAL_EVIDENCE_FILES:shutil.copyfile(source/n,d/n)
  (d/bm.MANIFEST_AT_RUN).write_text(bm.render(f.manifest))
  p=rn.qualification_session_plan(f.manifest,rn._sha(d/bm.MANIFEST_AT_RUN))
  # This is an isolated transport test: B1Q has 11 records, not B2Q's 20.
  # Only the expected record count is adjusted for the inherited transport.
  p['expected_records']=11
  log=json.loads((d/'run_log.json').read_text())
  log['l6']['binding']=copy.deepcopy(p['binding'])
  log['l6']['inputs']=rn.expected_inputs(f.manifest,rn.QUALIFICATION)
  ident=log['app_identity']
  ident.update(pair_first=0,pair_count=1,pairs_total=1,master_seed=p['master_seed'],
   budget_per_arm=p['n'],map_sha256=f.manifest['map']['canonical_json_sha256'],fitness_id='F1',
   universe_sha256=f.manifest['universe']['sha256'],carrier_sha256=f.manifest['carrier']['bitstream_sha256'])
  whole={k:p['binding'][k] for k in ('session','image_sha256','prereg_sha256','b2_manifest_sha256','master_seed')}
  whole.update(boardid='17A6',ruling=rn.QUAL_RULING_TEXT,granted_by='test-fixture-only',date='2026-09-11-00')
  provision=dict(whole,ruling=rn.PROVISION_RULING_TEXT);provision.pop('master_seed')
  def archive(name,doc):
   raw=json.dumps(doc).encode();(d/name).write_text(json.dumps(q.archive_envelope(raw)));return raw
  archive('ruling_whole_of_run.json',whole)
  pk=archive('ruling_provisioning.json',provision)
  summary=json.loads((d/'summary.json').read_text());summary['ruling']=whole
  import hashlib
  summary['provisioning_ruling_sha256']=hashlib.sha256(pk).hexdigest()
  (d/'summary.json').write_text(json.dumps(summary))
  def judge(doc):
   (d/'run_log.json').write_text(json.dumps(doc))
   sess.write_exports_manifest(d,{k:'ok' for k in sess.REQUIRED_EXPORTS})
   with patch.object(rn.adj,'adjudicate',return_value={'outcome':'PASS','findings':[],'kills':[]}):
    out=rn.judge_session(d,f.manifest,p,{}, {},None,inst.DEFAULT_ROOT)
   return {k:out[k] for k in ('outcome','findings','binding_checked')}
  result['transport_control']=judge(log)
  for name,fn in (
    ('ident_carrier',lambda x:x['app_identity'].update(carrier_sha256='0'*64)),
    ('ident_universe',lambda x:x['app_identity'].update(universe_sha256='0'*64)),
    ('missing_inputs',lambda x:x['l6'].pop('inputs')),
    ('wrong_inputs',lambda x:x['l6']['inputs'].update(b2_manifest_sha256='0'*64)),
    ('wrong_binding_image_control',lambda x:x['l6']['binding'].update(image_sha256='0'*64)),
    ('wrong_slice_control',lambda x:x['app_identity'].update(pair_first=1)),
  ):
   doc=copy.deepcopy(log);fn(doc);result[name]=judge(doc)
  for name,n,raw in (
   ('whole_not_json','ruling_whole_of_run.json','not JSON'),
   ('provision_not_json','ruling_provisioning.json','not JSON'),
   ('summary_not_json','summary.json','not JSON'),
  ):
   saved=(d/n).read_bytes();(d/n).write_text(raw);result[name]=judge(log);(d/n).write_bytes(saved)
  for key,val in (('master_seed',p['master_seed']^1),('image_sha256','0'*64),('boardid','FFFF'),('session','B1')):
   name='whole_wrong_'+key
   saved=(d/'ruling_whole_of_run.json').read_bytes()
   archive('ruling_whole_of_run.json',dict(whole,**{key:val}))
   result[name]=judge(log)
   (d/'ruling_whole_of_run.json').write_bytes(saved)
  result['qualification_plan_has_inputs']='inputs' in rn.qualification_session_plan(f.manifest)
  # Direct evidence membership/parse comparison. This proves byte coverage alone
  # accepts an invalid envelope at record creation, not an end-to-end transition.
  (d/'adjudication.json').write_text(json.dumps({'session':'B2Q','outcome':'PASS','measured_rate_per_hour':2807.0,'audit_policy':'all-self-reporting'}))
  (d/'ruling_whole_of_run.json').write_text('not JSON')
  record=bm.reconstruct_qualification_record(d)
  try:q.read_archived_ruling(d/'ruling_whole_of_run.json');refused=False
  except q.QualificationRefusal:refused=True
  result['invalid_archive_record']={'record_created':True,'file_count':len(record['files']),'archive_parser_refuses':refused}
 # Independent real B2 record replay, with common validation enabled.
 af.BlankBaselines.setUpClass()
 for field in ('control','carrier_sha256','universe_sha256'):
  doc=copy.deepcopy(af.BlankBaselines.whole)
  if field!='control':doc['app_identity'][field]='0'*64
  out=rn.adj.adjudicate([doc],af.PLAN,af.PREDICTION,consts=af.CONSTS,scope='session',common=True)
  result['real_replay_'+field]={k:out[k] for k in ('outcome','findings')}
finally:f.close()
print(json.dumps(result,indent=2))
assert result['transport_control']['outcome']=='PASS'
for n in ('ident_carrier','ident_universe','missing_inputs','wrong_inputs','whole_not_json','provision_not_json','summary_not_json','whole_wrong_master_seed','whole_wrong_image_sha256','whole_wrong_boardid','whole_wrong_session'):
 assert result[n]['outcome']=='PASS',(n,result[n])
for n in ('wrong_binding_image_control','wrong_slice_control'):
 assert result[n]['outcome'].startswith('HOLD'),(n,result[n])
assert all(result['real_replay_'+k]['outcome']=='PASS' for k in ('control','carrier_sha256','universe_sha256'))
