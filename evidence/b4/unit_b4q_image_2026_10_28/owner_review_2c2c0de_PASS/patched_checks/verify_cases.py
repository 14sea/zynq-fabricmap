import sys,json,subprocess
from pathlib import Path
code=Path(sys.argv[1]).resolve();base=Path(sys.argv[2]).resolve();out=Path(__file__).resolve().parent;rows=[]
for group,path in [('submitted',base/'evidence/b4/unit_b4q_image_2026_10_28/e2e'),('regenerated',base/'build/owner_console_e2e')]:
 for d in sorted(path.iterdir()):
  if not d.is_dir():continue
  j=out/f'verify_{group}_{d.name}.json';cmd=[sys.executable,'-B',str(code/'host/b4q_verify.py'),str(d),'--json',str(j)];p=subprocess.run(cmd,cwd=code,capture_output=True,text=True,timeout=50);j.with_suffix('.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(p.returncode)+'\n'+p.stdout+p.stderr);rep=json.loads(j.read_text());rows.append({'group':group,'case':d.name,'exit':p.returncode,'clean':rep['clean'],'agree':rep['agree'],'verifier_error':rep.get('verifier_error')})
(out/'verify_cases.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
