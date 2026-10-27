#!/usr/bin/env python3
"""The read of the committed b4-sim-4 archive that informed the positive-control address choice of docs/b4_observation_contract.md
section 8 (the data-influence disclosure). Reads evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_*/k9.json ONLY: per address, the
K9 covered / applicable counts summed over the 32 pairs under both applicabilities ((b') conditional SR-driven, the judged estimand
of protocol v0.2.0; (b) all-panel). Nothing is run, derived or written outside this directory; no seed is printed; the archive is not
modified. The fractions are a host-model record under hypothesis v0.3 — never a measurement of silicon."""
import collections, hashlib, json, pathlib
R = pathlib.Path('/home/test/zynq_fabricmap'); A = R / 'evidence/b4/sim/b4-sim-4_20261021T065339Z'
agg = collections.defaultdict(lambda: {'applicable': 0, 'covered': 0, 'applicable_ap': 0, 'covered_ap': 0}); sem = {}; elem = {}; n = 0
for pd in sorted(A.glob('pair_*')):
    s = json.loads((pd / 'k9.json').read_bytes())['summary']; n += 1
    for a, r in s['per_address'].items():
        agg[a]['applicable'] += r['applicable']; agg[a]['covered'] += r['covered']; sem[a] = r['semantic']; elem[a] = r['element']
    for a, r in s['per_address_all_panel'].items():
        agg[a]['applicable_ap'] += r['applicable']; agg[a]['covered_ap'] += r['covered']
rep = A / 'sim_report.json'
print('archive', A.relative_to(R), 'sim_report.json sha256', hashlib.sha256(rep.read_bytes()).hexdigest(), '| pairs read', n)
print(f"{'address':20} {'element':8} {'semantic':13} {'(b′) covered/applicable':>24} {'fraction':>9} {'(b) covered/applicable':>24} {'fraction':>9}")
for a in sorted(agg, key=lambda x: (sem[x], str(elem[x]))):
    g = agg[a]; f1 = g['covered'] / g['applicable'] if g['applicable'] else None; f2 = g['covered_ap'] / g['applicable_ap'] if g['applicable_ap'] else None
    print(f"{a:20} {str(elem[a]):8} {sem[a]:13} {g['covered']:>12}/{g['applicable']:<11} {('n/a' if f1 is None else f'{f1:.3f}'):>9} {g['covered_ap']:>12}/{g['applicable_ap']:<11} {('n/a' if f2 is None else f'{f2:.3f}'):>9}")
print('choice rule (section 8): per semantic the address with the highest (b′) fraction; ties in address (genome-bit) order; for the two per-element semantics one main-element and one x5FF-element address each')
