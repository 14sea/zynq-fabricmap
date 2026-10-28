"""Read-only independent inventory / provenance checks. No production derivation."""
from pathlib import Path
import json,hashlib,subprocess
R=Path(__file__).resolve().parents[3]
# review lives R/build/wip/review; keep explicit supplied repository for portable replay
import sys
R=Path(sys.argv[1]).resolve()
def sha(b):return hashlib.sha256(b).hexdigest()
def git(*a):return subprocess.check_output(['git','-C',str(R),*a])
checks={}
checks['head']=git('rev-parse','HEAD').decode().strip();checks['status']=git('status','--porcelain').decode()
checks['transaction_unchanged']=git('show','e267405:firmware/b4q/b4q_tx.c')==(R/'firmware/b4q/b4q_tx.c').read_bytes()
prot='b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2 evidence/b4/sim evidence/b4/gate evidence/b4/gonogo gate_runs manifests evidence/b4/unit_b4q_integration_2026_10_27'.split()
checks['protected_since_e267405']=git('diff','--name-only','e267405','HEAD','--',*prot).decode().splitlines()
checks['protected_since_main']=git('diff','--name-only','dd8a7b9','HEAD','--',*'b4/host b4/schemas b4/hypothesis rtl builds vivado tb sim b3 firmware/b1 firmware/b2'.split()).decode().splitlines()
checks['imports']={}
for rel in ['b4/IMPORT.json','firmware/b4q/IMPORT.json']:
 d=json.loads((R/rel).read_text());fs=d['files'];pinned={k:v for k,v in fs.items() if isinstance(v,dict) and 'sha256' in v}
 checks['imports'][rel]={'entries':len(fs),'hashed':len(pinned),'mismatch':[k for k,v in pinned.items() if not (R/k).is_file() or sha((R/k).read_bytes())!=v['sha256']]}
a=json.loads((Path(__file__).resolve().parent/'build_evidence.json').read_text());b=json.loads((R/'evidence/b4/unit_b4q_image_2026_10_28/build_evidence.json').read_text())
def normalized_keys(x,old):
 if isinstance(x,dict):return {k.replace(old,'<REPO>'):normalized_keys(v,old) for k,v in x.items()}
 if isinstance(x,list):return [normalized_keys(v,old) for v in x]
 if isinstance(x,str):return x.replace(old,'<REPO>')
 return x
checks['build']={'image_sha256':a['image']['sha256'],'submitted_image_matches':a['image']['sha256']==b['image']['sha256'],'reviewer_two_builds_equal':a['reproducibility']['reproduced_byte_identical'],'sources_equal':a['sources']==b['sources'],'verbatim':a['b1_verbatim'],'bsp_inputs_equal_after_path_normalization':normalized_keys(a['bsp_inputs'],'/tmp/owner_b4q_repair_i_m6wlns')==normalized_keys(b['bsp_inputs'],str(R)),'translation_units':len(a['bsp_inputs']['translation_units']),'headers':len(a['bsp_inputs']['headers']),'entry':a['image']['layout']['entry'],'elf_equal':a['image']['elf_sha256']==b['image']['elf_sha256'],'map_equal':a['image']['map_sha256']==b['image']['map_sha256']}
print(json.dumps(checks,indent=2))
