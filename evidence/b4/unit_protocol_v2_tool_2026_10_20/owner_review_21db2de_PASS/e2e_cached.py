"""Run the submitted driver unchanged except for memoising its pure global
normalisation, then projecting to requested directories. No batch/case is skipped.
Cache keys cover every evidence file's bytes and the HEAD set; proof below checks
the projection and invalidation against the original function on a tiny DAG.
"""
import hashlib, importlib.util, json, sys, tempfile
from pathlib import Path
R=Path('/home/test/zynq_fabricmap')
P=R/'evidence/b4/unit_protocol_v2_tool_2026_10_20/e2e_v2_fixtures.py'
spec=importlib.util.spec_from_file_location('owner_e2e_driver',P)
d=importlib.util.module_from_spec(spec);spec.loader.exec_module(d)
original=d.normalise
cache={};counts={'computations':0,'hits':0}
def cached(root,heads,compare_dirs):
    root=Path(root);ev=root/'evidence'
    paths=sorted(p for p in ev.rglob('*') if p.is_file())
    key=(str(root),tuple(sorted(heads)),tuple((str(p.relative_to(ev)),hashlib.sha256(p.read_bytes()).hexdigest()) for p in paths))
    if key not in cache:
        cache.clear()
        cache[key]=original(root,heads,{'all':ev})
        counts['computations']+=1
    else: counts['hits']+=1
    all_=cache[key]
    out={}
    for name,directory in compare_dirs.items():
        directory=Path(directory)
        out[name]={str(p.relative_to(directory)):all_['digests']['all'][str(p.relative_to(ev))] for p in sorted(directory.rglob('*')) if p.is_file()}
    return {'digests':out,**{k:v for k,v in all_.items() if k!='digests'}}
with tempfile.TemporaryDirectory(prefix='owner_norm_equivalence_') as tmp:
    r=Path(tmp);a=r/'evidence/a';b=r/'evidence/b';a.mkdir(parents=True);b.mkdir()
    (a/'leaf.json').write_text(json.dumps({'value':7,'written_utc':'x','root':str(r),'head':'h'}))
    leaf=(a/'leaf.json').read_bytes()
    (b/'parent.json').write_text(json.dumps({'ref':hashlib.sha256(leaf).hexdigest(),'path':'leaf.json','sha256':hashlib.sha256(leaf).hexdigest(),'size':len(leaf)}))
    (b/'render.md').write_text('rendering')
    dirs={'a':a,'b':b}
    assert cached(r,{'h'},dirs)==original(r,{'h'},dirs)
    assert cached(r,{'h'},{'b':b})==original(r,{'h'},{'b':b})
    (a/'leaf.json').write_text(json.dumps({'value':8,'written_utc':'y','root':str(r),'head':'h'}))
    assert cached(r,{'h'},dirs)==original(r,{'h'},dirs)
print('CACHE_EQUIVALENCE_AND_INVALIDATION_OK',flush=True)
cache.clear();counts={'computations':0,'hits':0}
d.normalise=cached
code=d.main()
print('NORMALISATION_CACHE',json.dumps(counts),flush=True)
sys.exit(code)
