from pathlib import Path
import subprocess,json,hashlib
R=Path('/home/test/zynq_fabricmap');D=Path(__file__).resolve().parent
cmd=lambda args:subprocess.check_output(args,cwd=R,text=True)
proof={}
for name,parent,commit,allowed in [('archive','495cc36','580c0e5','evidence/b4/sim/b4-sim-4_20261021T065339Z/'),('decision','580c0e5','adce027','evidence/b4/gonogo/b4-sim-4_20261021T065857Z/'),('unit','adce027','196b358','evidence/b4/unit_sim4_execution_2026_10_21/')]:
 files=cmd(['git','diff','--name-only',parent,commit]).splitlines();assert all(f.startswith(allowed) for f in files)
 proof[name]={'parent':cmd(['git','rev-parse',commit+'^']).strip(),'expected_parent':cmd(['git','rev-parse',parent]).strip(),'files':len(files),'only_expected_path':True};assert proof[name]['parent']==proof[name]['expected_parent']
paths=['b4/','b3/','host/','tests/','firmware/','manifests/','evidence/b3/','gate_runs/','evidence/b4/sim/b4-sim-3_20261019T121833Z/','evidence/b4/sim/b4-gate-1_20261020T102526Z/','evidence/b4/gate/']
assert cmd(['git','diff','--name-only','495cc36','HEAD','--',*paths])==''
assert cmd(['git','diff','--name-only','21db2de','HEAD','--','b4/'])==''
B=R/'evidence/b4/sim/b4-sim-4_20261021T065339Z';man=json.loads((B/'manifest.json').read_text());checks={};live_changes=[]
for group in ['inputs','tool_files']:
 for name,sha in man[group].items():
  blob=subprocess.check_output(['git','show','495cc36:'+name],cwd=R);assert hashlib.sha256(blob).hexdigest()==sha,(group,name,'execution tree')
  live=hashlib.sha256((R/name).read_bytes()).hexdigest()
  if live!=sha:
   assert group=='inputs' and name=='docs/b4_architecture.md'
   live_changes.append({'path':name,'recorded_sha256':sha,'execution_blob_sha256':hashlib.sha256(blob).hexdigest(),'live_sha256':live,'reason':'post-execution documentation commit 5b8aabc, method/archives unchanged'})
 checks[group]={'count':len(man[group]),'all_recorded_execution_blob_digests_equal':True,'live_tool_digests_equal':True if group=='tool_files' else None}
for name,sha in man['external_inputs'].items():assert hashlib.sha256(Path(name).read_bytes()).hexdigest()==sha
checks['external_inputs']={'count':len(man['external_inputs']),'all_equal':True}
old=R/'build/wip/owner_review_495cc36_2026_10_21';arch=R/'evidence/b4/unit_sim4_execution_2026_10_21/owner_review_495cc36_PASS';original=[p for p in old.rglob('*') if p.is_file()]
assert all((arch/p.relative_to(old)).read_bytes()==p.read_bytes() for p in original)
lines=(arch/'SHA256SUMS').read_text().splitlines()
for line in lines:
 sha,name=line.split('  ',1);assert hashlib.sha256((arch/name).read_bytes()).hexdigest()==sha
follow=cmd(['git','diff','--name-only','196b358','5b8aabc']).splitlines()
allowed={'docs/b4_architecture.md','docs/b4_sim4_execution_plan.md','evidence/b4/unit_sim4_execution_2026_10_21/README.md','evidence/b4/unit_sim4_execution_2026_10_21/owner_clarification_2026_10_21.txt'}
assert set(follow)==allowed
out={'commit_path_boundaries':proof,'protected_paths_unchanged':paths,'baseline_b4_unchanged':True,'input_bindings':checks,'post_execution_document_differences':live_changes,'prior_owner_review':{'original_files':len(original),'checksum_entries':len(lines),'all_copied_bytes_equal':True,'all_checksums_equal':True},'refs':{r:cmd(['git','rev-parse',r]).strip() for r in ['HEAD','main','b4-protocol-v2']},'status':cmd(['git','status','--short','--branch']),'diff_check':cmd(['git','diff','--check','495cc36','HEAD']),'additional_document_commit':{'commit':cmd(['git','rev-parse','5b8aabc']).strip(),'files':follow,'method_and_archive_changes':False}}
(D/'git_input_checks.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
