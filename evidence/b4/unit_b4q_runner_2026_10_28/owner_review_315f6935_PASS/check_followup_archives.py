"""Fresh verifier processes on retained runner fixtures; no archive regeneration or modification."""
import sys,json,subprocess,tempfile,hashlib
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
root=Path(sys.argv[1]).resolve();out=Path(sys.argv[2]).resolve();scratch=Path(tempfile.mkdtemp(prefix='owner_verify_followup_',dir=root/'build'))
ds=sorted(p for p in (root/'evidence/b4/unit_b4q_runner_2026_10_28/e2e_runner').iterdir() if p.is_dir() and (p/'manifest.json').exists())
def one(p):
 f=scratch/(p.name+'.json');q=subprocess.run([sys.executable,'-B',str(root/'host/b4q_verify.py'),str(p),'--json',str(f)],cwd=root,capture_output=True,text=True,timeout=180)
 r=json.loads(f.read_text());return {'name':p.name,'exit':q.returncode,'agree':r.get('agree'),'clean':r.get('clean'),'refused':r.get('refused'),'session':r.get('session'),'report_sha256':hashlib.sha256(f.read_bytes()).hexdigest(),'stdout':q.stdout,'stderr':q.stderr}
with ThreadPoolExecutor(max_workers=4) as pool:results=list(pool.map(one,ds))
bad=[r for r in results if r['exit']!=0 or r['agree'] is not True]
(out/'followup_archive_checks.json').write_text(json.dumps({'root':str(root),'cases':len(results),'bad':len(bad),'results':results},indent=2)+'\n')
print(json.dumps({'cases':len(results),'agree':len(results)-len(bad),'bad':bad},indent=2));sys.exit(1 if bad else 0)
