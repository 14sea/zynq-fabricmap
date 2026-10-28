"""Verify the exact approved two-file follow-up. Read-only; no build, draw, contact, git mutation or image execution."""
import sys,json,hashlib,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
approved=json.loads((here/'approved_file_hashes.json').read_text());report={'files':{},'imports':{},'unexpected_runtime_paths':[]};bad=[]
for name,expected in approved['files'].items():
 got=hashlib.sha256((root/name).read_bytes()).hexdigest();report['files'][name]={'sha256':got,'matches':got==expected['repaired']}
 if got!=expected['repaired']:bad.append(name+': not approved bytes')
for name in ['b4/IMPORT.json','firmware/b4q/IMPORT.json']:
 d=json.loads((root/name).read_text());entries=[(k,v['sha256']) for k,v in d['files'].items() if isinstance(v,dict) and v.get('sha256')]
 mismatch=[k for k,h in entries if hashlib.sha256((root/k).read_bytes()).hexdigest()!=h];report['imports'][name]={'count':len(entries),'mismatch':mismatch};bad+=mismatch
scope=['host','tests','firmware','b4','rtl','sim','tb','vivado','builds','b3','manifests','evidence/b4/sim','evidence/b4/gate','evidence/b4/gonogo']
q=subprocess.run(['git','diff','--name-only',approved['base'],'--',*scope],cwd=root,capture_output=True,text=True)
if q.returncode:bad.append('cannot compare approved base')
else:
 touched=q.stdout.splitlines();report['runtime_paths']=touched;report['unexpected_runtime_paths']=[x for x in touched if x not in approved['files']];bad+=report['unexpected_runtime_paths']
q=subprocess.run(['git','diff','--check',approved['base'],'--',*approved['files']],cwd=root,capture_output=True,text=True);report['code_whitespace_exit']=q.returncode
if q.returncode:bad.append(q.stdout+q.stderr)
image=root/'build/b4q_image/b4q_app_v2.bin'
if image.is_file():
 got=hashlib.sha256(image.read_bytes()).hexdigest();report['image_sha256_if_present']=got
 if got!=approved['image_unchanged_sha256']:bad.append('image changed')
report['findings']=bad;report['approved_followup_matches']=not bad;print(json.dumps(report,indent=2));sys.exit(1 if bad else 0)
