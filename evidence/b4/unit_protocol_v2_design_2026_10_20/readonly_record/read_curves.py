"""READ-ONLY aggregation of the archived curves.json of b4-gate-1 (200 pairs). No model, engine or seed code is called."""
import json, pathlib, statistics as st
R = pathlib.Path('/home/test/zynq_fabricmap/evidence/b4/sim/b4-gate-1_20261020T102526Z')
rows = [json.load(open(p)) for p in sorted(R.glob('pair_*/curves.json'))]
assert len(rows) == 200
grid = rows[0]['grid']; arms = ['R','F','O','X','D','Omega','A0']
print('base_fit: mean %.3f median %s min %d max %d' % (st.mean(r['base_fit'] for r in rows), st.median(r['base_fit'] for r in rows), min(r['base_fit'] for r in rows), max(r['base_fit'] for r in rows)))
print('\narm - R per budget: mean (positives/negatives/ties) ; arm median')
for a in ['Omega','F','O','X','D','A0']:
    line = []
    for i, B in enumerate(grid):
        d = [r['best_at_grid'][a][i] - r['best_at_grid']['R'][i] for r in rows]
        line.append('B%d %+.3f (%d/%d/%d)' % (B, st.mean(d), sum(x>0 for x in d), sum(x<0 for x in d), sum(x==0 for x in d)))
    print(a, ':', ' | '.join(line))
print('\nmedian best per arm per budget')
for a in arms:
    print(a, [st.median(r['best_at_grid'][a][i] for r in rows) for i in range(len(grid))])
print('\nbest over all 7 arms at B=256 per seed: mean %.2f median %s min %d max %d' % (st.mean(max(r['best_at_grid'][a][-1] for a in arms) for r in rows), st.median(max(r['best_at_grid'][a][-1] for a in arms) for r in rows), min(max(r['best_at_grid'][a][-1] for a in arms) for r in rows), max(max(r['best_at_grid'][a][-1] for a in arms) for r in rows)))
mx = [max(r['best_at_grid'][a][-1] for a in arms) for r in rows]
for t in (64, 56, 48, 44, 40): print('  seeds with any arm >= %d at B=256: %d / 200' % (t, sum(m >= t for m in mx)))
print('\ngain over base at B=256, R arm: mean %.2f; Omega: %.2f' % (st.mean(r['best_at_grid']['R'][-1]-r['base_fit'] for r in rows), st.mean(r['best_at_grid']['Omega'][-1]-r['base_fit'] for r in rows)))
print('\nholdout (ceiling 80) mean per arm:', {a: round(st.mean(r['holdout'][a] for r in rows), 2) for a in arms})
print('holdout O - R: mean %+.3f (pos/neg/tie %d/%d/%d)' % (st.mean(r['holdout']['O']-r['holdout']['R'] for r in rows), sum(r['holdout']['O']>r['holdout']['R'] for r in rows), sum(r['holdout']['O']<r['holdout']['R'] for r in rows), sum(r['holdout']['O']==r['holdout']['R'] for r in rows)))
print('\nR progress: median best at B=8 %s, B=32 %s, B=256 %s (base median %s)' % (st.median(r['best_at_grid']['R'][0] for r in rows), st.median(r['best_at_grid']['R'][3] for r in rows), st.median(r['best_at_grid']['R'][-1] for r in rows), st.median(r['base_fit'] for r in rows)))
