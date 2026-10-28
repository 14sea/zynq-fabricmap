"""Read-only acceptance check for the exact owner-reviewed follow-up. No build or production derivation."""
import sys,json,hashlib,subprocess
from pathlib import Path
root=Path(sys.argv[1]).resolve();here=Path(__file__).resolve().parent
pins=json.loads((here/'approved_file_hashes.json').read_text())
rows={p:{'sha256':hashlib.sha256((root/p).read_bytes()).hexdigest() if (root/p).is_file() else None,'expected':v['repaired_sha256']} for p,v in pins.items()}
changed=subprocess.check_output(['git','-C',str(root),'diff','--name-only','2c2c0de','--','firmware','host','tests','b4','rtl','builds','vivado','tb','sim','b3','scripts','manifests','gate_runs','evidence/b4/sim','evidence/b4/gate','evidence/b4/gonogo'],text=True).splitlines()
allowed={'host/b4q_verify.py','tests/test_b4q_app.py'}
unexpected=[p for p in changed if p not in allowed]
imports={}
for name in ['b4/IMPORT.json','firmware/b4q/IMPORT.json']:
 fs=json.loads((root/name).read_text())['files'];pinned={p:v for p,v in fs.items() if isinstance(v,dict) and 'sha256' in v};imports[name]={'hashed':len(pinned),'mismatch':[p for p,v in pinned.items() if not (root/p).is_file() or hashlib.sha256((root/p).read_bytes()).hexdigest()!=v['sha256']]}
check=subprocess.run(['git','-C',str(root),'diff','--check','2c2c0de','--',*pins],capture_output=True,text=True)
ok=all(v['sha256']==v['expected'] for v in rows.values()) and not unexpected and all(not v['mismatch'] for v in imports.values()) and check.returncode==0
print(json.dumps({'approved_files':rows,'unexpected_runtime_changes':unexpected,'imports':imports,'source_diff_check_exit':check.returncode,'source_diff_check_output':check.stdout+check.stderr,'exact_followup_checks_pass':ok},indent=2))
sys.exit(0 if ok else 1)
