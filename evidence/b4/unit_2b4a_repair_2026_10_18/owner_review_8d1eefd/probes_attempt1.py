"""Owner review of round 3: fixed exposed mechanics schedule, no production seed derivation."""
import copy,json,sys,tempfile,shutil,hashlib
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent;S=Path('/tmp/b4_owner_8d1eefd_wz0tbo0p')
sys.path[:0]=[str(S/'b4/host'),str(S/'b4/tests')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
import b4_seeds as bs
import test_b4_sim as ts
from b4_deadline import Deadline

temp=Path(tempfile.mkdtemp(prefix='b4_owner_round3_probe_'));result={'snapshot':str(S),'temp':str(temp)}
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=1,allow_nan=False)+'\n')
def entry(p,rel):
 b=p.read_bytes();return {'path':rel,'size':len(b),'sha256':hashlib.sha256(b).hexdigest()}
def reindex(p):
 idx=read(p/'pair_000/index.json');idx['files']=[entry(f,f.name) for f in sorted((p/'pair_000').iterdir()) if f.is_file() and f.name!='index.json'];write(p/'pair_000/index.json',idx)
 rep=read(p/'sim_report.json');rep['files']=[entry(f,str(f.relative_to(p))) for f in sorted(p.rglob('*')) if f.is_file() and f.name!='sim_report.json'];write(p/'sim_report.json',rep)
def forbid(*a,**kw):raise AssertionError('OWNER: production seed derivation forbidden')
def verify(p):
 try:return {'findings':sv.verify_run_dir(p)}
 except Exception as e:return {'raised':f'{type(e).__name__}: {e}'}
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 old=Path('/home/test/zynq_fabricmap/build/wip/owner_review_6c00156_2026_10_18')
 previous=read(old/'probes_results.json')
 for name in ('partial_k10_complete_batch','manifest_deadline_mismatch'):
  result['previous_'+name]=verify(Path(previous[name]['path']))
 for name,rec in read(old/'types_results.json').items():result['previous_'+name]=verify(Path(rec['path']))
 result['previous_contradictory_deadline']=verify(Path(read(old/'deadline_archive_results.json')['path']))
 for name,rec in read(old/'finalisation_results.json').items():
  if name in ('deadline','input_drift'):
   root=Path(read(old/'finalisation_results.json')['root'])
   result['previous_valid_stop_'+name]=verify(root/sim.SIM_REL/('b4-mech-1_'+name))

 inp=temp/'input';inp.mkdir();root=ts.build_hermetic(inp);base=root/sim.SIM_REL/'b4-mech-1_owner'
 res=sim.run_batch(root,'b4-mech-1',1,3600,base,schedule=ts.SCHED_ONE)
 result['fresh_baseline']={'status':res['status'],'exit_code':res['exit_code'],'path':str(base),**verify(base)}
 assert res['status']=='complete',res
 for diagnostic,bad in (('k7',[]),('k9',[]),('k10','malformed')):
  p=temp/('bad_'+diagnostic);shutil.copytree(base,p);write(p/'pair_000'/f'{diagnostic}.json',bad);reindex(p)
  result['malformed_'+diagnostic]={'path':str(p),**verify(p)}

 # A real Deadline with a monotonic clock crossing the limit between its record() samples.
 values=iter([1000.0,1059.990,1060.010,1060.010])
 dl=Deadline(60,clock=lambda:next(values));rec=dl.record()
 result['producer_boundary']={'record':rec,'validator_findings':sc.deadline_findings(rec)}
 result['late_positive']=sc.deadline_findings({'seconds':60,'elapsed_s':10000.0,'checks':3,'expired':True,'first_expired_at_s':60.0,'clock':'time.monotonic'})

 # The same producer/validator mismatch in an actual batch stopped inside K9.
 ts.git(root,'add','-A');ts.git(root,'commit','-q','-m','owner mechanics baseline')
 clock=ts.Clock();real_record=Deadline.record;recorded=[]
 def at_first_expiry(obj):
  if not recorded:
   seq=iter([obj.start+59.990,obj.start+60.010,obj.start+60.010]);saved=obj._clock;obj._clock=lambda:next(seq)
   try:r=real_record(obj)
   finally:obj._clock=saved
   clock.t=obj.start+60.010;recorded.append(r);return r
  return real_record(obj)
 def interrupt(*a,**kw):raise KeyboardInterrupt('owner fixed interruption')
 p=root/sim.SIM_REL/'b4-mech-1_boundary_stop'
 with mock.patch.object(sim.k9,'coverage',side_effect=interrupt),mock.patch.object(Deadline,'record',new=at_first_expiry):
  res=sim.run_batch(root,'b4-mech-1',1,60,p,clock=clock,schedule=ts.SCHED_ONE)
 result['boundary_stopped_batch']={'path':str(p),'status':res['status'],'exit_code':res['exit_code'],
  'stopped_exists':(p/'STOPPED.json').exists(),'report_exists':(p/'sim_report.json').exists(),
  'error_file_exists':(p/'sim_report.ERROR.txt').exists(),'first_produced_record':recorded[0],
  'report_error':res.get('report_error'),'stopped_detail':res.get('stopped',{}).get('detail'),**verify(p)}

write(D/'probes_results.json',result);print(json.dumps(result,sort_keys=True,indent=1))
