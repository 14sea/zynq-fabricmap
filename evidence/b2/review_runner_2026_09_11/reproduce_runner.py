#!/usr/bin/env python3
"""Offline runner integration probes; never execute(), no ports or consumed rulings."""
import copy,json,sys,tempfile,subprocess,os,pwd
from pathlib import Path
from unittest.mock import patch
R=Path(sys.argv[1]).resolve() if len(sys.argv)>1 else Path(__file__).resolve().parents[3]
sys.path[:0]=[str(R/'host'),str(R/'tests')]
import test_b2_runner as t
import test_b2_adjudicate as f
import b2_runner as rn
import b2_adjudicate as adj
import b2_manifest as bm
import b2_session as bsess
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT,require_git=False)
from validators import records
import l6_schedule as ls

results={}
f.BlankBaselines.setUpClass()
base=copy.deepcopy(f.BlankBaselines.whole)
with tempfile.TemporaryDirectory(prefix='b2-runner-review-') as tmp:
 d=Path(tmp)
 cfg={'round_plan':f.PLAN,'prediction':f.PREDICTION}
 for kind in ('baseline','STOPPED','PROTOCOL','missing_audits'):
  log=copy.deepcopy(base)
  if kind in ('STOPPED','PROTOCOL'):
   log['session_summary']={'epoch_end':{'kind':kind,'last_seq':len(log['loop_records']),'reason':'review control'},
                            'closing':{'baseline':'not_reached','restore':'not_reached','unsigned_control':'not_reached'},
                            'written_by':'collector'}
  if kind=='missing_audits':
   for r in log['loop_records']:r['verified']='replayed-only'
  (d/'run_log.json').write_text(json.dumps(log))
  out=rn.adjudication_for(cfg)(d)
  results['B2_callback_'+kind]={k:out.get(k) for k in ('outcome','findings','not_checked_here')}

 fixture=t.Fixture('S1')
 try:
  plan,pred,seeds=rn.qualification_documents(fixture.manifest)
  master=rn.qualification_master(fixture.manifest)
  native=bsess.pair_seeds(master,1)
  results['B2Q_seeds']={'master':master,'qualification':seeds,'reference_default':native,'equal':seeds==native}
  assert seeds==native, 'Build an explicit-seed model if the rules no longer coincide on this fixed master.'
  with patch.multiple(f,MASTER=master,BUDGET=8,PAIRS=1):
   qlog=f.BlankBaselines.wrap(f.modelled_log(0,1))
  qd=d/'b2q';qd.mkdir();(qd/'run_log.json').write_text(json.dumps(qlog))
  out=rn.readjudicator(fixture.manifest)(qd)
  results['B2Q_real_readjudicator']={k:out.get(k) for k in ('outcome','session','measured_rate_per_hour','audit_policy','pair_seeds')}
  results['B2Q_session_callback']=rn.adjudication_for({'round_plan':None})(qd)
  (qd/bm.MANIFEST_AT_RUN).write_text(bm.render(fixture.manifest))
  (qd/'adjudication.json').write_text(json.dumps({'outcome':'PASS','session':'B2Q',
       'measured_rate_per_hour':2807.0,'audit_policy':t.bp.AUDIT_POLICY}))
  try:
   bm.qualify(fixture.manifest,qd,readjudicate=rn.readjudicator(fixture.manifest))
   results['B2Q_qualify']='ACCEPTED'
  except bm.Refusal as exc:results['B2Q_qualify']=str(exc)

  # Read-only preflight. Only the absent pins hook and the unrelated OS boundary/sb
  # checks are doubled. The temporary ruling documents are test fixtures, not authorizations.
  args=fixture.args(profile=rn.QUALIFICATION,pair_first=None,pair_count=None,qual_rate_per_hour=2807.0)
  args.boundary.write_text(json.dumps({'runner_user':pwd.getpwuid(os.getuid()).pw_name,
                     'signer_user':args.signer_user,'key_store':str(args.key.parent)}))
  with patch.object(records,'boundary_established',return_value=True),patch.object(rn.shutil,'which',return_value='/test/sb'):
   try:
    rn.preflight(args,rn.QUALIFICATION,pins_verify=t.stub_pins)
    results['preflight_actual_instrument_shape']='ACCEPTED'
   except Exception as exc:results['preflight_actual_instrument_shape']={'exception':type(exc).__name__,'message':str(exc)}
   # Expose the remaining independent branches after recording the real schema failure.
   # Only add the absent wire selector to a read-only in-memory instrument-manifest view.
   saved_read=Path.read_text
   target=Path(inst.DEFAULT_ROOT)/'manifests/l6_manifest.json'
   def read_with_wire(path,*a,**kw):
    text=saved_read(path,*a,**kw)
    if path.resolve()==target.resolve():
     doc=json.loads(text);doc['protocol']['wire']='rel-v4';return json.dumps(doc)
    return text
   wire_patch=patch.object(Path,'read_text',read_with_wire);wire_patch.start()
   cfgq=rn.preflight(args,rn.QUALIFICATION,pins_verify=t.stub_pins)
   results['B2Q_preflight_control']={'records':cfgq['plan']['expected_records'],
      'frame_records':cfgq['plan']['expected_frames']['records'],'frames':cfgq['plan']['expected_frames']['total'],
      'crc_budget':cfgq['plan']['crc_budget']}
   real=ls.expected_frames(cfgq['plan']['expected_records']-2,cfgq['plan']['audit_seqs'],cfgq['plan']['protocol'])
   results['B2Q_correct_frame_count']=real
   ru=json.loads(args.ruling.read_text());ru['master_seed']=master^1;args.ruling.write_text(json.dumps(ru))
   try:
    rn.preflight(args,rn.QUALIFICATION,pins_verify=t.stub_pins)
    results['B2Q_wrong_ruling_master']='ACCEPTED'
   except Exception as exc:results['B2Q_wrong_ruling_master']=str(exc)
   args.qual_rate_per_hour=float('inf')
   try:
    x=rn.preflight(args,rn.QUALIFICATION,pins_verify=t.stub_pins)
    results['B2Q_infinite_rate']={'accepted':True,'deadline_s':x['plan']['session_timeout_s']}
   except Exception as exc:results['B2Q_infinite_rate']=str(exc)
   wire_patch.stop()
 finally:fixture.close()

 for seeds_bad in (7,[None],[1]):
  try:
   out=adj.adjudicate([base],f.PLAN,f.PREDICTION,consts=f.CONSTS,common=True,seeds=seeds_bad)
   results['bad_seeds_'+repr(seeds_bad)]=out['outcome']
  except Exception as exc:results['bad_seeds_'+repr(seeds_bad)]={'exception':type(exc).__name__,'message':str(exc)}
results['head']=subprocess.check_output(['git','rev-parse','HEAD'],cwd=R,text=True).strip()
print(json.dumps(results,indent=2))
