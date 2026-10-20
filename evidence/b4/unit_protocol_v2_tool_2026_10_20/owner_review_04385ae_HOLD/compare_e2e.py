import json, sys
from pathlib import Path
old=Path('/home/test/zynq_fabricmap/evidence/b4/unit_protocol_v2_tool_2026_10_20/e2e')
new=Path(sys.argv[1] if len(sys.argv)>1 else '/tmp/owner_04385ae_e2e')
out={}
for p in sorted(old.glob('*/record.json')):
    q=new/p.relative_to(old)
    if not q.exists():
        raise SystemExit('missing regenerated record: '+str(q))
    a=json.loads(p.read_bytes()).get('digests',{})
    b=json.loads(q.read_bytes()).get('digests',{})
    c={'comparable':0,'equal':0,'different':[],'missing':[]}
    for d,files in a.items():
        for n,e in files.items():
            t=b.get(d,{}).get(n)
            if t is None:
                c['missing'].append(d+'/'+n);continue
            if 'canonical_sha256' not in e: continue
            c['comparable']+=1
            if e['canonical_sha256']==t.get('canonical_sha256'): c['equal']+=1
            else: c['different'].append(d+'/'+n)
    out[p.parent.name]=c
print(json.dumps(out,indent=2))
