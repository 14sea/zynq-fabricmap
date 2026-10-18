"""Owner review, fixed and already exposed mechanics seeds only."""
import copy,json,sys,tempfile,shutil,hashlib
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent
R=Path('/tmp/b4_owner_6c00156_3mc7z1rw')
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
import b4_seeds as bs
import b4_k10 as k10
import b4_execution as ex
import test_b4_sim as ts
from b4_deadline import StopWork
old=Path('/home/test/zynq_fabricmap/build/wip/owner_review_f2c4bca_2026_10_18')
prior=json.loads((old/'probes_results.json').read_bytes())
more=json.loads((old/'probes_more_results.json').read_bytes())
temp=Path(tempfile.mkdtemp(prefix='b4_owner_round2_probes_'))
results={'snapshot':str(R),'temp':str(temp)}
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=1,allow_nan=False)+'\n')
def entry(p,rel):
 b=p.read_bytes();return {'path':rel,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def reindex(out):
 idx=read(out/'pair_000/index.json')
 idx['files']=[entry(p,p.name) for p in sorted((out/'pair_000').iterdir()) if p.is_file() and p.name!='index.json'];write(out/'pair_000/index.json',idx)
 rep=read(out/'sim_report.json');rep['files']=[entry(p,str(p.relative_to(out))) for p in sorted(out.rglob('*')) if p.is_file() and p.name!='sim_report.json']
 rep['identity']['manifest_sha256']=sim.sha_file(out/'manifest.json');write(out/'sim_report.json',rep)
def case(name):
 p=temp/name;shutil.copytree(base,p);return p
def forbidden(*a,**kw):raise AssertionError('OWNER: production seed derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbidden),mock.patch.object(bs,'pair_seeds',side_effect=forbidden):
 root=ts.build_hermetic(temp/'input_tree') if (temp/'input_tree').mkdir() is None else None
 base=root/sim.SIM_REL/'b4-mech-1_owner'
 baseline=sim.run_batch(root,'b4-mech-1',1,3600,base,schedule=ts.SCHED_ONE)
 assert baseline['status']=='complete',baseline
 results['base']=str(base)
 results['baseline']=sv.verify_run_dir(base)
 for name,rec in list(prior.items())+list(more.items()):
  if isinstance(rec,dict) and rec.get('path') and 'full_run' not in name:
   try:results['previous_'+name]=sv.verify_run_dir(Path(rec['path']))
   except Exception as exc:results['previous_'+name]={'RAISED':f'{type(exc).__name__}: {exc}'}

 # Real partial diagnostic from the production driver, under the same exposed task seed.
 mapping=sim.bm.site_mapping();task=sim.bl.make_task(7,mapping.addresses)
 fabric=sim.fm.Fabric(mapping,sim.hy.load());n=0
 def one_unit():
  global n
  n+=1
  if n>1:raise StopWork('owner fixed partial diagnostic probe')
 partial=k10.seed_k10(task,ex.ObservationPort(fabric),check=one_unit)
 p=case('partial_k10_complete_batch');doc=read(p/'pair_000/k10.json')
 doc.update(partial);write(p/'pair_000/k10.json',doc)
 curves=read(p/'pair_000/curves.json');k7=read(p/'pair_000/k7.json');k9=read(p/'pair_000/k9.json')
 row={'pair':0,'landscape_seed':7,'operator_seed':11,'base_fit':curves['base_fit'],'best_at_grid':curves['best_at_grid'],
  'f_end_to_end_at_grid':[x['value'] for x in curves['f_end_to_end_at_grid']],
  'k7_not_unknown_at_grid':[k7['prefixes'][str(B)]['not_unknown'] for B in sim.GRID],
  'k9':k9['summary']['per_semantic'],'k9_all_seven':k9['summary']['all_seven_positive_controls'],
  'k10_max_abs':partial['max_abs_index'],'k10_outcome':partial['outcome']}
 rep=read(p/'sim_report.json');rep['summary']=sim.summarise_batch([row],1)[0];write(p/'sim_report.json',rep);reindex(p)
 results['partial_k10_complete_batch']={'path':str(p),'actual_complete':doc['complete'],'planned':rep['pairs'][0]['k10'],
  'units':len(doc['units']),'validator':sc.k10_findings(doc,task),'verify':sv.verify_run_dir(p),'summary_k10':rep['summary']['k10']}

 # The deadline is declared before observations, so its copies must agree.
 p=case('manifest_deadline_mismatch');man=read(p/'manifest.json');man['deadline_s']=1;write(p/'manifest.json',man);reindex(p)
 results['manifest_deadline_mismatch']={'path':str(p),'manifest_deadline_s':1,'report_deadline_s':read(p/'sim_report.json')['deadline']['seconds'],'verify':sv.verify_run_dir(p)}

write(D/'probes_results.json',results);print(json.dumps(results,indent=1))
