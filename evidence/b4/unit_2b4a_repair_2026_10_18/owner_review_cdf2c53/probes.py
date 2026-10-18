from pathlib import Path
import sys,tempfile,json,copy,dataclasses
from unittest import mock
R=Path('/tmp/b4_owner_cdf2c53_y9cov9it')
sys.path[:0]=[str(R/'b4/host'),str(R/'b4/tests')]
import b4_sim as sim,b4_sim_schema as sc,b4_seeds as bs,b4_ff_hypothesis as hy,b4_ff_mapping as bm,b4_ff_model as fm,b4_execution as ex,b4_k9 as k9,b4_k10 as k10,b4_landscape as bl
from test_b4_sim import build_hermetic,git,RaisingPort,Clock
from b4_test_fixtures import InjectingPort
OUT=Path('/home/test/zynq_fabricmap/build/wip/owner_review_cdf2c53_2026_10_18')
results={}
roots=[]
def root():
 p=Path(tempfile.mkdtemp(prefix='b4_owner_mechanics_'));roots.append(str(p));return build_hermetic(p)
# No master or production seed stream is generated: every batch below uses a MOCKED fixture schedule, l=7,o=11.
# Seed mechanics are not adjudicated by these tests.
patches=[mock.patch.object(bs,'master_seed',return_value=1000001),mock.patch.object(bs,'pair_seeds',return_value=[(7,11)])]
with patches[0],patches[1]:
 r=root();ns=r/sim.SIM_REL;outside=Path(tempfile.mkdtemp(prefix='b4_owner_outside_'))
 ns.parent.mkdir(parents=True,exist_ok=True);ns.symlink_to(outside,target_is_directory=True)
 git(r,'add','-A');git(r,'commit','-qm','symlink namespace fixture')
 try:
  ctx=sim.preflight(r,'b4-sim-1',1,60,ns/'b4-sim-1_probe')
  results['symlink_namespace']={'accepted':True,'resolved_out':str(ctx['out'].resolve()),'outside_root':not ctx['out'].resolve().is_relative_to(r.resolve())}
 except Exception as e:results['symlink_namespace']={'accepted':False,'reason':repr(e)}
 # Direct K10 DOMAIN: does a four-corner unit keep observing after a refused first corner?
 h,m=hy.load(),bm.site_mapping();fabric=fm.Fabric(m,h);task=bl.make_task(7,m.addresses);port=InjectingPort(fabric,1)
 try:k10.seed_k10(task,port)
 except k10.K10Invalid as e:results['k10_after_domain']={'refusal_at':1,'port_calls':port.calls,'kept_observations':len(e.partial['observations']),'units':len(e.partial['units'])}
 # Actual complete fixed-seed mechanics fixture for offline mutations.
 r=root();out=r/sim.SIM_REL/'b4-sim-1_fixture';b=sim.run_batch(r,'b4-sim-1',1,3600,out)
 assert b['status']=='complete',b
 results['fixture_complete']={'root':str(r),'out':str(out),'status':b['status'],'self_validation':b['report']['self_validation']}
 originals={str(p.relative_to(out)):p.read_bytes() for p in out.rglob('*.json')}
 def load(rel):return json.loads(originals[rel])
 def put(rel,d): (out/rel).write_text(json.dumps(d))
 # No hash list repair: validator must detect plain raw corruption, missing required files, or false summary.
 d=load('pair_000/curves.json');d['best_at_grid']['O']=[0]*len(sim.GRID);put('pair_000/curves.json',d)
 results['tampered_curves']=sc.validate_run_dir(out,task_of=lambda i:task)
 (out/'pair_000/curves.json').write_bytes(originals['pair_000/curves.json'])
 saved=originals['pair_000/arm_R.result.json'];(out/'pair_000/arm_R.result.json').unlink()
 results['deleted_arm']=sc.validate_run_dir(out,task_of=lambda i:task)
 (out/'pair_000/arm_R.result.json').write_bytes(saved)
 d=load('sim_report.json');d['summary']['per_budget']['8']['deltas']['delta1_O_minus_R']['mean']=999;put('sim_report.json',d)
 results['tampered_summary']=sc.validate_run_dir(out,task_of=lambda i:task)
 (out/'sim_report.json').write_bytes(originals['sim_report.json'])
 d=load('pair_000/k10.json');d['units']=[copy.deepcopy(d['units'][0]) for _ in range(420)];
 from b4_stats import seed_max,classify
 ma,counts=seed_max(d['units']);d.update(max_abs_index=ma,comparable_pairs=counts['comparable_pairs'],not_comparable_pairs=counts['not_comparable_pairs'],outcome=classify(ma,d['tau']))
 results['k10_duplicate_units_recompute']=k10.recompute(d,task)
 put('pair_000/k10.json',d);results['k10_duplicate_units_validator']=sc.validate_run_dir(out,task_of=lambda i:task)
 (out/'pair_000/k10.json').write_bytes(originals['pair_000/k10.json'])
 d=load('pair_000/k9.json');d['pairs']=[];d['pairs_done']=0;d['summary']=k9.summarise([],m)
 results['k9_empty_complete_recompute']=k9.recompute(d,task,fabric)
 put('pair_000/k9.json',d);results['k9_empty_complete_validator']=sc.validate_run_dir(out,task_of=lambda i:task)
 (out/'pair_000/k9.json').write_bytes(originals['pair_000/k9.json'])
 # Mid-K9 DOMAIN: preserve the successful first observation?
 r=root();out=r/sim.SIM_REL/'b4-sim-1_k9domain'
 def factory(fabric,role,pair):return InjectingPort(fabric,2) if role=='K9' else ex.ObservationPort(fabric)
 b=sim.run_batch(r,'b4-sim-1',1,3600,out,port_factory=factory)
 results['k9_domain_archive']={'status':b['status'],'kind':b['stopped']['kind'],'k9_file_exists':(out/'pair_000/k9.json').exists(),'stage':b['stopped']['stage']}
 # Late expiration after statistics but before final input validation: can report complete/expired?
 r=root();out=r/sim.SIM_REL/'b4-sim-1_latedeadline';clock=Clock(step=0)
 original_hold=sim.Batch.hold_inputs
 def hold(self,stage):
  if stage=='final':clock.t+=10000
  return original_hold(self,stage)
 with mock.patch.object(sim.Batch,'hold_inputs',hold):b=sim.run_batch(r,'b4-sim-1',1,60,out,clock=clock)
 results['late_deadline']={'status':b['status'],'exit_code':b['exit_code'],'deadline':b['report']['deadline'],'summary_present':b['report']['summary'] is not None}
 # A validator error or nonempty self_validation must never leave complete exit 0.
 r=root();out=r/sim.SIM_REL/'b4-sim-1_failedreport'
 original=sim.sc.report_findings
 def reject(doc):return ['injected report validation error']
 with mock.patch.object(sim.sc,'report_findings',reject):b=sim.run_batch(r,'b4-sim-1',1,3600,out)
 results['report_write_failure']={'status':b['status'],'exit_code':b['exit_code'],'report_exists':(out/'sim_report.json').exists(),'error_exists':(out/'sim_report.ERROR.txt').exists()}
 # type-totality probes on genuine valid documents
 d=load('manifest.json');d['arm_order']=None
 try:results['malformed_manifest']=sc.manifest_findings(d)
 except Exception as e:results['malformed_manifest']={'uncaught':repr(e)}
 d=load('pair_000/k9.json');d['observations'][0]['q_grid'][0][0]=2
 results['malformed_q_grid']=sc.k9_findings(d)
 # Are all input source files bound at end checkpoints?
 inputs,tools=sim.input_snapshot(r,hy.load())
 vendors=[str(Path(s['root'])/s['path']) for s in h.doc['sources'] if s['kind']=='vendor_primitive']
 results['external_sources_snapshot']={'vendor_count':len(vendors),'snapshot_external_paths':sorted(set(inputs)&set(vendors)),'historical_snapshot_count':len(set(inputs)&{x[0] for x in bs.FIELDS})}
OUT.joinpath('probes.json').write_text(json.dumps(results,indent=2)+'\n')
OUT.joinpath('probe_roots.json').write_text(json.dumps(roots,indent=2)+'\n')
print(json.dumps(results,indent=2))
