from pathlib import Path
import json,importlib.util,sys
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root']);A=P/'evidence/b4/unit_task_v03_2026_10_27/e2e_v3';B=D/'e2e_owner'
spec=importlib.util.spec_from_file_location('owner_compare',A.parent/'e2e_v3_compare.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
rows={}
for b in sorted(B.glob('*/record.json')):
    a=A/b.relative_to(B);rb=json.loads(b.read_text());ra=json.loads(a.read_text())
    if 'digests' not in rb:continue
    for name,entries in ra['digests'].items():rows[f'{b.parent.name}/{name}']=m.compare_dir(entries,rb['digests'].get(name,{}))
total={'comparable':sum(r['comparable'] for r in rows.values()),'equal':sum(r['equal'] for r in rows.values()),'different':sum(len(r['different']) for r in rows.values()),'missing':sum(len(r['missing_in_b'])+len(r['extra_in_b']) for r in rows.values())}
expect={p.parent.name for p in A.glob('*/record.json') if 'digests' in json.loads(p.read_text())};have={p.parent.name for p in B.glob('*/record.json') if 'digests' in json.loads(p.read_text())}
out={'per_directory':rows,'total':total,'pending_cases':sorted(expect-have),'extra_cases':sorted(have-expect),'driver_finished':(B/'summary.json').exists(),'all_present_digests_match':total['different']==0 and total['missing']==0}
(D/'regeneration_comparison.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps({k:v for k,v in out.items() if k!='per_directory'},indent=2))
assert out['all_present_digests_match']
if sys.argv[1:]==['--final']:
    assert not out['pending_cases'] and not out['extra_cases'] and out['driver_finished']
    assert json.loads((B/'summary.json').read_text())['as_expected']
