#!/usr/bin/env python3
"""The read-only derivation of the positive-control PROPOSAL of docs/b4_observation_contract.md section 7 from the committed
b4-sim-4 archive (evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_*/k9.json). Reads only; writes nothing; derives no seed; the
archive is not modified. Rule (section 7.2): per semantic the address with the highest (b') covered / applicable fraction summed over
the 32 pairs (ties in the mapping's address order); for ff_init and ff_srval one main-element and one x5FF-element address each;
for the chosen address, the background whose pair is applicable under (b') and covered in the most pairs of the 32 (ties: the
lowest g0 genome value). The result is a host-model record under hypothesis v0.3 — not a measurement of silicon."""
import collections, hashlib, json, pathlib, sys
R = pathlib.Path('/home/test/zynq_fabricmap'); A = R / 'evidence/b4/sim/b4-sim-4_20261021T065339Z'
sys.path.insert(0, str(R / 'b4/host')); import b4_ff_mapping as bm  # noqa: E402
order = {a: i for i, a in enumerate(bm.site_mapping().addresses)}
addr = collections.defaultdict(lambda: [0, 0]); bg = collections.defaultdict(lambda: collections.defaultdict(lambda: [0, 0, None, None]))
sem, elem, n = {}, {}, 0
for pd in sorted(A.glob('pair_*')):
    d = json.loads((pd / 'k9.json').read_bytes()); n += 1
    for p in d['pairs']:
        a = p['address']; sem[a] = p['semantic']; elem[a] = p['element']
        if not p['applicable_sr_driven']:
            continue
        addr[a][0] += 1; addr[a][1] += p['covered']
        key = (p['g0_hex'], p['g1_hex']); b = bg[a][key]
        b[0] += 1; b[1] += p['covered']; b[2] = p['g0']; b[3] = p['backgrounds']
print('archive', A.relative_to(R), '| pairs read', n, '| sim_report.json sha256',
      hashlib.sha256((A / 'sim_report.json').read_bytes()).hexdigest())
def pick(cands):
    best = max(cands, key=lambda a: (addr[a][1] / addr[a][0], -order[a]))
    bgs = bg[best]; k = max(bgs, key=lambda k: (bgs[k][1], -bgs[k][2]))
    return best, bgs[k], k
groups = {'ce_mode': [a for a in addr if sem[a] == 'ce_mode'], 'clock_mode': [a for a in addr if sem[a] == 'clock_mode'],
          'sr_kind': [a for a in addr if sem[a] == 'sr_kind'], 'sr_mode': [a for a in addr if sem[a] == 'sr_mode'],
          'storage_kind': [a for a in addr if sem[a] == 'storage_kind'],
          'ff_init (main)': [a for a in addr if sem[a] == 'ff_init' and '5' not in elem[a]],
          'ff_init (x5FF)': [a for a in addr if sem[a] == 'ff_init' and '5' in elem[a]],
          'ff_srval (main)': [a for a in addr if sem[a] == 'ff_srval' and '5' not in elem[a]],
          'ff_srval (x5FF)': [a for a in addr if sem[a] == 'ff_srval' and '5' in elem[a]]}
print(f"{'semantic':16} {'address':18} {'element':8} {'(b′) frac':>10} {'endpoints g0/g1 (hex)':>24} {'covered/applicable at bg':>26} {'bg idx':>8}")
for g, cands in groups.items():
    a, b, k = pick(cands)
    print(f"{g:16} {a:18} {str(elem[a]):8} {addr[a][1] / addr[a][0]:>10.3f} {k[0] + '/' + k[1]:>24} {str(b[1]) + '/' + str(b[0]):>26} {str(b[3]):>8}")
print('rule: highest (b′) fraction per semantic, ties in mapping address order; background = the endpoint pair covered in the most of the',
      n, 'pairs, ties the lowest g0; ff_init / ff_srval one main-element and one x5FF-element address each')
