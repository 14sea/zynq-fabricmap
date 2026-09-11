#!/usr/bin/env python3
"""Check B2 extension types on the native twin's real REC, without any board contact."""
import copy
import json
from pathlib import Path
import subprocess
import sys

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import b2_maps as maps
import b2_records as records
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT, require_git=False)
import b1_records as common

fw = R / 'firmware/b2'
subprocess.run(['make', '-s', 'twin'], cwd=fw, capture_output=True, text=True, check=True)
wire = subprocess.check_output([str(fw / 'build/b2_twin'), 'wire'], text=True)
raw = {line.split(' ', 1)[0]: json.loads(line.split(' ', 1)[1]) for line in wire.splitlines()}
ctx = records.Context(master_seed=716169644, budget=4, pairs_total=9, pair_first=0,
                      pair_count=4, fitness='F1', map_sha256=maps.sha256_of(maps.load_self_map()))

cases = {
    'baseline': lambda r: None,
    'pair_string': lambda r: r['search'].__setitem__('pair', '0'),
    'population_scalars': lambda r: r['search'].__setitem__('population', [0] * 4),
    'population_wrong_values': lambda r: r['search'].__setitem__('population', [{'born': 'invalid', 'fit': {}}] * 4),
    'selected_wrong_type': lambda r: r['search'].__setitem__('selected', 'invalid'),
}
result = {}
for name, mutate in cases.items():
    rec = copy.deepcopy(raw['REC'])
    mutate(rec)
    common.validate(rec)  # every case still passes common-envelope validation
    try:
        got = {'findings': records.record_findings(rec, ctx, (0, 'map_guided', False), {})}
    except Exception as exc:
        got = {'exception': type(exc).__name__, 'message': str(exc)}
    result[name] = {'common': 'ACCEPTED', **got}
assert result['baseline']['findings'] == [], result['baseline']
print(json.dumps(result, indent=2))
