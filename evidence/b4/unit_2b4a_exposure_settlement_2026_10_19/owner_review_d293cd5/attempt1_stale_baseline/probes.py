import sys,pathlib,json
from unittest import mock
D=pathlib.Path(__file__).resolve().parent;S=pathlib.Path('/tmp/b4_owner_d293cd5_m9gm8xko');sys.path.insert(0,str(S/'b4/host'))
import b4_seeds as bs
import b4_sim_verify as sv
import b4_sim_schema as sc
old=json.loads(pathlib.Path('/home/test/zynq_fabricmap/build/wip/owner_review_1d9525c_2026_10_19/probes_results.json').read_bytes());results={}
def forbid(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 results['true_count']=bs.pinned_receipt_count()
 for name in ('baseline','coordinated_count_0','coordinated_count_1','coordinated_count_67'):
  out=pathlib.Path(old[name]['path']);sd=json.loads((out/'seeds.json').read_bytes());md=json.loads((out/'manifest.json').read_bytes())
  f=sv.verify_run_dir(out)
  with mock.patch.dict(sc.VALIDATORS,{'seeds.json':lambda d:[],'manifest.json':lambda d:[]}):deep_only=sv.verify_run_dir(out)
  results[name]={'path':str(out),'seeds_findings':sc.seeds_findings(sd),'manifest_findings':sc.manifest_findings(md),'deep_verify':f,'linkage_with_record_validators_bypassed':deep_only}
  if name=='baseline':assert f=={} and deep_only=={}
  else:assert any('pooled length' in x for v in f.values() for x in v) and any('pooled length' in x for x in deep_only.get('linkage',[]))
 ref={'path':bs.EXPOSURE_RECEIPT_REL,'sha256':bs.EXPOSURE_RECEIPT_SHA256,'count':results['true_count']}
 results['valid_reference']=bs.receipt_reference_findings(ref,'owner');assert results['valid_reference']==[]
 with mock.patch.object(bs,'EXPOSURE_RECEIPT_SHA256','00'*32):
  results['unreadable_authority']=bs.receipt_reference_findings({**ref,'sha256':'00'*32},'owner')
 assert any('cannot be bound' in x for x in results['unreadable_authority'])
(D/'probes_results.json').write_text(json.dumps(results,sort_keys=True,indent=1)+'\n');print(json.dumps(results,sort_keys=True,indent=1))
