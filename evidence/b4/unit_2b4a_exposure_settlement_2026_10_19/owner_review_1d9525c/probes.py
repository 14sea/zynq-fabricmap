import sys,pathlib,json,tempfile,hashlib,shutil
from unittest import mock
D=pathlib.Path(__file__).resolve().parent
S=pathlib.Path('/tmp/b4_owner_1d9525c_iw24rf_4')
sys.path[:0]=[str(S/'b4/host'),str(S/'b4/tests')]
import test_b4_sim as ts
import b4_seeds as bs
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
read=lambda p:json.loads(p.read_bytes())
write=lambda p,d:p.write_text(json.dumps(d,sort_keys=True,indent=1)+'\n')
r={};temp=pathlib.Path(tempfile.mkdtemp(prefix='b4_owner_receipt_'));root=ts.build_hermetic(temp/'root');out=root/sim.SIM_REL/'b4-mech-1_owner_receipt'
def forbid(*a,**kw):raise AssertionError('OWNER: no production derivation during archive probes')
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 got=sim.run_batch(root,'b4-mech-1',1,3600,out,schedule=ts.SCHED_ONE)
 assert got['status']=='complete',got
 r['baseline']={'path':str(out),'status':got['status'],'verify':sv.verify_run_dir(out)}
 original={str(p.relative_to(out)):p.read_bytes() for p in out.rglob('*') if p.is_file()}
 receipt=read(root/bs.EXPOSURE_RECEIPT_REL)
 for n in (0,1,67):
  for rel,b in original.items():(out/rel).write_bytes(b)
  sd=read(out/'seeds.json');md=read(out/'manifest.json')
  sd['exclusion']['exposure_receipt']['count']=n;md['exclusion']['exposure_receipt']['count']=n
  write(out/'seeds.json',sd);md['seeds_sha256']=sim.sha_file(out/'seeds.json');write(out/'manifest.json',md);ts.reindex(out)
  r['coordinated_count_'+str(n)]={'declared_count':n,'actual_count':len(receipt['pooled']),'seeds_findings':sc.seeds_findings(sd),'manifest_findings':sc.manifest_findings(md),'deep_verify':sv.verify_run_dir(out)}
  dst=temp/('wrong_count_'+str(n));shutil.copytree(out,dst);r['coordinated_count_'+str(n)]['path']=str(dst)
 for rel,b in original.items():(out/rel).write_bytes(b)
 r['restored_verify']=sv.verify_run_dir(out)
 # A count/reference downgrade in seeds remains rejected by cross-file binding.
 sd=read(out/'seeds.json');sd['schema_version']='1.1.0';del sd['exclusion']['exposure_receipt'];write(out/'seeds.json',sd)
 md=read(out/'manifest.json');md['seeds_sha256']=sim.sha_file(out/'seeds.json');write(out/'manifest.json',md);ts.reindex(out)
 r['downgraded_seeds']={'deep_verify':sv.verify_run_dir(out)}
(D/'probes_results.json').write_text(json.dumps(r,sort_keys=True,indent=1)+'\n');print(json.dumps(r,sort_keys=True,indent=1))
