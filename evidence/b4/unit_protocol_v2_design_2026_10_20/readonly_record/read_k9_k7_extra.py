"""READ-ONLY (the inline snippet run once in the 2026-10-20 session, reproduced verbatim as a file for the record):
sr_kind / ff_srval coverage among SR-driven backgrounds per seed; K7 O not_unknown per budget; O group_moves. No model code called."""
import json, pathlib, statistics as st
R = pathlib.Path('/home/test/zynq_fabricmap/evidence/b4/sim/b4-gate-1_20261020T102526Z')
files = sorted(R.glob('pair_*/k9.json'))
bit = {'sr_mode': 3, 'sr_kind': 0, 'storage_kind': 10}
out = {s: [] for s in ('sr_kind', 'ff_srval')}
for f in files:
    d = json.load(open(f))
    for sem in out:
        a = c = 0
        for p in d['pairs']:
            if p['semantic'] == sem and p['applicable'] and (p['g0'] >> bit['sr_mode']) & 1: a += 1; c += bool(p['covered'])
        out[sem].append(c / a)
for sem, v in out.items():
    print('%s, SR-driven backgrounds only, per-seed fraction: median %.5f mean %.5f min %.5f max %.5f; seeds >= 0.5: %d / 200' % (sem, st.median(v), st.mean(v), min(v), max(v), sum(x >= 0.5 for x in v)))
rows = [json.load(open(p))['prefixes'] for p in sorted(R.glob('pair_*/k7.json'))]
grid = [8,16,24,32,48,64,96,128,192,256]
print('K7 O not_unknown: median / seeds >= 11, per budget:')
for B in grid:
    v = [r[str(B)]['not_unknown'] for r in rows]
    print('  B%d: median %s, >=11: %d/200, mean %.1f' % (B, st.median(v), sum(x >= 11 for x in v), st.mean(v)))
gm = [json.load(open(p))['result']['group_moves'] for p in sorted(R.glob('pair_*/arm_O.result.json'))]
print('O group_moves per run (of 256 evals): median %s mean %.1f min %d max %d' % (st.median(gm), st.mean(gm), min(gm), max(gm)))
