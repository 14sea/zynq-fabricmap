import argparse, copy, json, sys, tempfile
from pathlib import Path
ap = argparse.ArgumentParser()
ap.add_argument('--repo-root', type=Path, required=True)
a = ap.parse_args()
sys.path.insert(0, str(a.repo_root.resolve() / 'b4/host'))
import b4_ff_mapping as bm
import b4_ff_hypothesis as hy
import b4_ff_model as fm
m, h = bm.site_mapping(), hy.load()
f = fm.Fabric(m, h)
c = {addr: int(e.semantic in ('ff_srval','ce_mode','sr_mode','sr_kind')) for addr,e in m.entries.items()}
results = {}
def attempt(fn, refusal):
    try:
        fn()
        return {'accepted': True}
    except refusal as e:
        return {'accepted': False, 'refusal': str(e)}
results['observation_without_stimuli'] = f.observe(c, [])
with tempfile.TemporaryDirectory(prefix='b4_owner_probe_') as tmp:
    tmp = Path(tmp)
    bad = json.loads(hy.HYPOTHESIS.read_text())
    bad['sources'][0]['path'] = 'DOES_NOT_EXIST.v'
    p = tmp/'missing_source.json'; p.write_text(json.dumps(bad))
    results['default_load_missing_source'] = attempt(lambda: hy.load(p), hy.HypothesisRefusal)
    bad = json.loads(hy.HYPOTHESIS.read_text())
    bad['decode']['ff_init']['bit_one_means'] = 'not an INIT reading'
    p = tmp/'bad_decode.json'; p.write_text(json.dumps(bad))
    results['unrecognised_decode'] = attempt(lambda: fm.Fabric(m,hy.load(p)).observe(c,[fm.init()]), hy.HypothesisRefusal)
    original = json.loads(bm.CERTIFICATE.read_text())
    edits = {
      'negative_word': lambda row: row['predicted_assignments'][0]['address'].__setitem__('word',-1),
      'missing_baseline': lambda row: row.__setitem__('baseline_specimen_id','DOES_NOT_EXIST'),
      'primary_value_contradicts_transition': lambda row: row['predicted_assignments'][0].__setitem__('expected_value',0),
    }
    for name, edit in edits.items():
        bad = copy.deepcopy(original)
        row = next(r for r in bad['feature_results'] if r['split']=='mine' and r['feature'].endswith('.AFF.ZINI'))
        edit(row)
        p = tmp/(name+'.json'); p.write_text(json.dumps(bad))
        results[name] = attempt(lambda: bm.site_mapping(path=p), bm.MappingRefusal)
    for name, st in [('clock_2',dict(kind='set',clock=2,ce=255,sr=0,d=0)),('negative_sr',dict(kind='set',clock=0,ce=0,sr=-1,d=0))]:
        results[name] = attempt(lambda: f.observe(c,[fm.init(),st]), fm.ModelRefusal)
latch = dict(c)
for sem,val in [('storage_kind',1),('sr_kind',0),('clock_mode',1)]:
    latch[m.address_of(None,sem)] = val
tr = f.observe(latch,[fm.init(),fm.set_(0,ce=255,sr=0,d=0)])
results['latch_endpoint'] = {
 'model_q_after':[s['q_after'] for s in tr['steps']],
 'expected_for_cited_LDCE_IS_G_INVERTED_0_endpoint_at_G_0':[1,None,1,None,1,None,1,None],
 'basis':'docs/ff_latch_probe.md: main_latch and CLKINV-context warning; UNISIM LDCE gate-level rule',
}
print(json.dumps(results, indent=2))
