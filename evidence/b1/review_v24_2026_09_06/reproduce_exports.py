from pathlib import Path
import sys,json,hashlib,tempfile
from unittest import mock
R=Path('/home/test/zynq_fabricmap');sys.path[:0]=[str(R/'host'),str(R/'tests')]
import b1_session as bs,b1_modelled_session as ms,b1q_adjudicate as qa
from test_b1_qualification import frozen,QPLAN,QPRED
m=frozen();sha=hashlib.sha256(json.dumps(m,indent=1,ensure_ascii=False).encode()).hexdigest()
d=Path(tempfile.mkdtemp(prefix='b1_v24_exports_'));capture={};export=bs.export_evidence

def save(*args,**kwargs):
 capture['args']=args
 return export(*args,**kwargs)
with mock.patch.object(bs,'export_evidence',save):
 ms.run_modelled(m,QPLAN,d/'baseline',binding_extra={'b1_manifest_sha256':sha})
args=list(capture['args']);collector=args[3];console=args[4]
import l6_timing as lt
results={}
# Real finalized successful B1Q objects, real exporter and real B1Q adjudicator.
# Only console.log's disk write is injected to fail.
def fail_raw(path,data):
 if path.name=='console.log':raise OSError('injected console.log write failure')
 return write_bytes(path,data)
write_bytes=Path.write_bytes
out=d/'raw_failure';out.mkdir();a=[out,{},*args[2:]]
with mock.patch.object(Path,'write_bytes',fail_raw):
 s=bs.finalize(*a,lambda path:qa.adjudicate(path,m,QPLAN,QPRED,sha,require_git=False))
results['raw_write_failure']={'outcome':s['outcome'],'exports':s['exports'],'console_exists':(out/'console.log').exists(),'adjudication_outcome':json.loads((out/'adjudication.json').read_text())['outcome']}
# A ledger rendering exception prevents all already-collected chunks from being exported.
out=d/'ledger_failure';out.mkdir();a=[out,{},*args[2:]]
with mock.patch.object(console,'rel_ledgers_json',side_effect=RuntimeError('injected ledger serialization failure')):
 ex=export(*a)
results['ledger_failure']={'collected_chunks':len(collector.audits),'audits_exists':(out/'audits.json').exists(),'exports':ex}
# A timing calculation exception prevents all records and the independent notary log export.
out=d/'timing_failure';out.mkdir();a=[out,{},*args[2:]]
with mock.patch.object(lt,'record_timing',side_effect=RuntimeError('injected timing failure')):
 ex=export(*a)
results['timing_failure']={'collected_records':len(collector.loop_records),'notary_entries':len(args[5].notary_log()['entries']),'run_log_exists':(out/'run_log.json').exists(),'exports':ex}
print(json.dumps(results,indent=2))
Path('/tmp/b1_v24_review/reproduction.json').write_text(json.dumps(results,indent=2)+'\n')
