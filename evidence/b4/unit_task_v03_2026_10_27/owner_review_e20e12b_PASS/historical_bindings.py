from pathlib import Path
import json,subprocess,hashlib
D=Path(__file__).resolve().parent;P=Path(json.loads((D/'snapshot.json').read_text())['temporary_root'])
m=json.loads((P/'evidence/b4/sim/b4-sim-4_20261021T065339Z/manifest.json').read_text());head=m['head']
def expected(v):return v if isinstance(v,str) else v['sha256']
rows={}
for section in ('inputs','tool_files'):
    bad=[]
    for rel,rec in m[section].items():
        b=subprocess.check_output(['git','show',f'{head}:{rel}'],cwd=P)
        if hashlib.sha256(b).hexdigest()!=expected(rec):bad.append(rel)
    rows[section]={'count':len(m[section]),'mismatches':bad};assert not bad,bad
bad=[]
for path,rec in m['external_inputs'].items():
    if hashlib.sha256(Path(path).read_bytes()).hexdigest()!=expected(rec):bad.append(path)
assert not bad,bad
rows['external_inputs']={'count':len(m['external_inputs']),'mismatches':bad}
out={'archive':'b4-sim-4','recorded_code_HEAD':head,'recorded_protocol_sha256':m['protocol']['protocol_sha256'],'checks':rows,'scope':'manifest provenance only; no seeds, K9 coverage or search-effect statistics read; no historical deep verification or new observation'}
(D/'historical_bindings.json').write_text(json.dumps(out,indent=2)+'\n');print(json.dumps(out,indent=2))
