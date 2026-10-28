import json,subprocess,sys
from pathlib import Path
root=Path(sys.argv[1]).resolve();out=Path(__file__).resolve().parent;rows=[]
for group,path in [('submitted',root/'evidence/b4/unit_b4q_image_2026_10_28/e2e'),('regenerated',root/'build/owner_console_e2e')]:
 for p in sorted(path.iterdir()):
  if not p.is_dir():continue
  j=out/f'verify_{group}_{p.name}.json';cmd=[sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(j)]
  v=subprocess.run(cmd,cwd=root,capture_output=True,text=True,timeout=50);j.with_suffix('.txt').write_text('COMMAND '+repr(cmd)+'\nEXIT '+str(v.returncode)+'\n'+v.stdout+v.stderr)
  d=json.loads(j.read_text());rows.append({'group':group,'case':p.name,'exit':v.returncode,'clean':d['clean'],'agree':d['agree'],'refused':d.get('refused'),'verifier_error':d.get('verifier_error')})
out.joinpath('verify_cases.json').write_text(json.dumps(rows,indent=2)+'\n');print(json.dumps(rows,indent=2))
