"""Off-board counterexamples for the v2.4.2 review; no physical transport is opened."""
from pathlib import Path
import sys,json,hashlib,tempfile,shutil,os
from unittest import mock
R=Path(__file__).resolve().parents[3];sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b1_session as bs,b1_modelled_session as ms,b1q_adjudicate as qa,b1_adjudicate as adj
from test_b1_qualification import frozen,QPLAN,QPRED
from test_b1_session_finalize import EarlyFailure
m=frozen();sha=hashlib.sha256(json.dumps(m,indent=1,ensure_ascii=False).encode()).hexdigest()
d=Path(tempfile.mkdtemp(prefix='b1_v241_review_'))
ms.run_modelled(m,QPLAN,d/'baseline',binding_extra={'b1_manifest_sha256':sha})
base=qa.adjudicate(d/'baseline',m,QPLAN,QPRED,sha,require_git=False)
assert base['outcome']=='PASS',base['outcome']
results={'baseline':base['outcome']}
for mode in ('omit_console_hash','empty_files','missing_files'):
 out=d/mode;shutil.copytree(d/'baseline',out)
 (out/'console.log').rename(d/(mode+'_saved_console.log'))
 p=out/'exports.json';doc=json.loads(p.read_text())
 if mode=='omit_console_hash':doc['files'].pop('console.log')
 elif mode=='empty_files':doc['files']={}
 else:doc.pop('files')
 p.write_text(json.dumps(doc))
 try:
  adj.check_exports(out);check='accepted'
 except adj.Refusal as exc:check='REFUSED: '+str(exc)
 verdict=qa.adjudicate(out,m,QPLAN,QPRED,sha,require_git=False)
 results[mode]={'console_exists':(out/'console.log').exists(),'check_exports':check,'adjudication_outcome':verdict['outcome'],'files_entries':list(doc.get('files',{}))}
# The real run(), using the new test's fake-board setup. Inject a primary PROTOCOL
# plus host exception at the console, then an independent local exports.json write error.
e=EarlyFailure()
for failure in ('write','replace'):
 tmp=d/('seal_'+failure);tmp.mkdir();session,plan,cfg,page=e._fake_board(tmp)
 def end_then_boom(collector,console,now,deadline):
  collector.epoch_end={'kind':'PROTOCOL','last_seq':11,'reason':'PROTOCOL_CRC_BUDGET: 5 > 4'}
  raise RuntimeError('primary console-loop host error')
 original_write=Path.write_text;original_replace=os.replace
 def fail_write(path,*args,**kwargs):
  if path.name=='exports.json.part':raise OSError('injected exports manifest write failure')
  return original_write(path,*args,**kwargs)
 def fail_replace(path,*args,**kwargs):
  if path.name=='exports.json.part':raise OSError('injected exports manifest replace failure')
  return original_replace(path,*args,**kwargs)
 escaped=None
 try:
  with mock.patch.object(Path,'write_text',fail_write) if failure=='write' else mock.patch.object(os,'replace',fail_replace):
   e._run_with(tmp,session,cfg,page,end_then_boom)
 except Exception as exc:escaped=type(exc).__name__+': '+str(exc)
 out=tmp/'out'
 saved=json.loads((out/'summary.json').read_text()) if (out/'summary.json').exists() else {}
 results['seal_'+failure]={'escaped_exception':escaped,'summary_outcome':saved.get('outcome'),'host_error':saved.get('host_error',{}).get('error'),'seal_error':saved.get('seal_error',{}).get('error'),'summary_exists':(out/'summary.json').exists(),'exports_exists':(out/'exports.json').exists(),'run_log_exists':(out/'run_log.json').exists(),'audits_exists':(out/'audits.json').exists(),'saved_epoch_end':json.loads((out/'run_log.json').read_text())['session_summary']['epoch_end']}
for name in ('omit_console_hash','empty_files','missing_files'):
 assert results[name]['adjudication_outcome'].startswith('REFUSED'),results[name]
for name in ('seal_write','seal_replace'):
 assert results[name]['escaped_exception'] is None and results[name]['summary_exists'],results[name]
 assert results[name]['host_error'] and results[name]['seal_error'],results[name]
print(json.dumps(results,indent=2))
(d/'reproduction.json').write_text(json.dumps(results,indent=2)+'\n')
