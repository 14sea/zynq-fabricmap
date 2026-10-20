import json,sys,shutil
from pathlib import Path
from unittest import mock
D=Path(__file__).resolve().parent;S=Path('/tmp/b4_owner_6c00156_3mc7z1rw')
sys.path[:0]=[str(S/'b4/host')]
import b4_sim as sim
import b4_sim_verify as sv
import b4_sim_schema as sc
import b4_seeds as bs
data=json.loads((D/'probes_results.json').read_bytes());base=Path(data['base']);temp=Path(data['temp'])
result={}
def read(p):return json.loads(p.read_bytes())
def write(p,d):p.write_text(json.dumps(d,sort_keys=True,indent=1)+'\n')
def ent(p,rel):return {'path':rel,'size':p.stat().st_size,'sha256':sim.sha_file(p)}
def reindex(p):
 idx=read(p/'pair_000/index.json');idx['files']=[ent(f,f.name) for f in sorted((p/'pair_000').iterdir()) if f.name!='index.json'];write(p/'pair_000/index.json',idx)
 rep=read(p/'sim_report.json');rep['files']=[ent(f,str(f.relative_to(p))) for f in sorted(p.rglob('*')) if f.is_file() and f.name!='sim_report.json'];write(p/'sim_report.json',rep)
def forbid(*a,**kw):raise AssertionError('OWNER: production derivation forbidden')
with mock.patch.object(bs,'master_seed',side_effect=forbid),mock.patch.object(bs,'pair_seeds',side_effect=forbid):
 task=sim.bl.make_task(7,sim.bm.site_mapping().addresses)
 cases=[('k9_pairs_total_float','k9.json',lambda d:d.update(pairs_total=float(d['pairs_total']))),
        ('k10_units_total_float','k10.json',lambda d:d.update(units_total=float(d['units_total']))),
        ('k10_corner_genome_bool','k10.json',lambda d:d['units'][0]['corners']['00'].update(genome=False))]
 for name,filename,mutate in cases:
  p=temp/name;shutil.copytree(base,p);doc=read(p/'pair_000'/filename);mutate(doc);write(p/'pair_000'/filename,doc);reindex(p)
  fn=sc.k9_findings if filename=='k9.json' else sc.k10_findings
  result[name]={'path':str(p),'validator':fn(doc,task),'verify':sv.verify_run_dir(p)}
(D/'types_results.json').write_text(json.dumps(result,indent=1)+'\n');print(json.dumps(result,indent=1))
