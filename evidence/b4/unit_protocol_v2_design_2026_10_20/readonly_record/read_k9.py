"""READ-ONLY aggregation of the archived k9.json of b4-gate-1 (200 seeds): ff_srval / sr_kind / sr_mode pairs split by the
background's decoded SR mode, SR kind and storage kind, read from the recorded endpoint genomes with the bit indexes the
record itself names for each semantic. No model code is called."""
import json, pathlib, collections, statistics as st
R = pathlib.Path('/home/test/zynq_fabricmap/evidence/b4/sim/b4-gate-1_20261020T102526Z')
files = sorted(R.glob('pair_*/k9.json')); assert len(files) == 200
d0 = json.load(open(files[0]))
bit = {}
for p in d0['pairs']:
    if p['element'] is None: bit[p['semantic']] = p['bit']
print('slice-wide semantic -> genome bit:', bit)
# decode (hypothesis v0.3): sr_mode bit_one = driven; sr_kind bit_one = synchronous; storage_kind bit_one = latch
cnt = collections.Counter(); cov = collections.Counter(); per_seed = collections.defaultdict(list)
for f in files:
    d = json.load(open(f))
    for p in d['pairs']:
        if p['semantic'] not in ('ff_srval', 'sr_kind', 'sr_mode') or not p['applicable']: continue
        g = p['g0']
        drv = (g >> bit['sr_mode']) & 1; sync = (g >> bit['sr_kind']) & 1; latch = (g >> bit['storage_kind']) & 1
        key = (p['semantic'], 'driven' if drv else 'tied_low', 'sync' if sync else 'async', 'latch' if latch else 'ff')
        cnt[key] += 1; cov[key] += bool(p['covered'])
    s = d['summary']
    fr = [v['fraction'] for k, v in s['per_address'].items() if v['semantic'] == 'ff_srval']
    per_seed['ff_srval_addr_fracs'].append(fr)
    for sem in ('ff_srval', 'sr_kind', 'sr_mode'):
        a = sum(v['applicable'] for v in s['per_address'].values() if v['semantic'] == sem)
        c = sum(v['covered'] for v in s['per_address'].values() if v['semantic'] == sem)
        per_seed[sem].append(c / a)
for k in sorted(cnt):
    print('%-8s %-9s %-5s %-5s applicable %6d covered %6d fraction %.4f' % (*k, cnt[k], cov[k], cov[k] / cnt[k]))
for sem in ('ff_srval', 'sr_kind', 'sr_mode'):
    v = per_seed[sem]; print('%s seed-level fraction: median %.5f mean %.5f min %.5f max %.5f; seeds >= 0.5: %d' % (sem, st.median(v), st.mean(v), min(v), max(v), sum(x >= 0.5 for x in v)))
# ff_srval among SR-driven only, per seed
drv_fr = []
for f in files:
    d = json.load(open(f)); a = c = 0
    for p in d['pairs']:
        if p['semantic'] == 'ff_srval' and p['applicable'] and (p['g0'] >> bit['sr_mode']) & 1: a += 1; c += bool(p['covered'])
    drv_fr.append(c / a)
print('ff_srval coverage among SR-DRIVEN applicable pairs only, per seed: median %.5f mean %.5f min %.5f max %.5f; seeds >= 0.5: %d' % (st.median(drv_fr), st.mean(drv_fr), min(drv_fr), max(drv_fr), sum(x >= 0.5 for x in drv_fr)))
