#!/usr/bin/env python3
"""Independent JSON mutation checks; host-only and production-state preserving."""
import copy
import json
from pathlib import Path
import subprocess
import sys

R = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import b2_records as b
import b2_maps as maps
import claimb_r1p_instrument as inst
inst.bind(inst.DEFAULT_ROOT, require_git=False)
import b1_records as common

fw = R / 'firmware/b2'
subprocess.run(['make', '-s', 'twin'], cwd=fw, check=True, capture_output=True)
wire = subprocess.check_output([str(fw / 'build/b2_twin'), 'wire'], text=True)
raw = {s.split(' ', 1)[0]: json.loads(s.split(' ', 1)[1]) for s in wire.splitlines()}
ctx = b.Context(716169644, 4, 9, 0, 4, 'F1', maps.sha256_of(maps.load_self_map()))
identity_ctx = b.Context(716169644, 600, 9, 0, 4, 'F1', ctx.map_sha256)
want = (0, 'map_guided', False)
results = []

def check(name, action, refuse=True):
    try:
        findings, unchanged = action()
        ok = bool(findings) == refuse and unchanged
        results.append(dict(case=name, findings=findings, state_unchanged=unchanged, ok=ok))
    except Exception as exc:
        results.append(dict(case=name, exception=repr(exc), ok=False))

def rec_case(path, value=None, remove=False):
    rec = copy.deepcopy(raw['REC'])
    obj = rec
    for key in path[:-1]:
        obj = obj[key]
    if remove:
        del obj[path[-1]]
    else:
        obj[path[-1]] = copy.deepcopy(value)
    state = {(0, 'B'): dict(evals=0, best=None, column_moves=None, generation=None, holdout_seen=False)}
    before = copy.deepcopy(state)
    return b.record_findings(rec, ctx, want, state), state == before

def ident_case(key, value=None, remove=False):
    ident = copy.deepcopy(raw['IDENT'])
    if remove:
        del ident[key]
    else:
        ident[key] = copy.deepcopy(value)
    return b.identity_findings(ident, identity_ctx), True

# Explicit independent field inventories, not the validator's own predicate tables.
int_keys = 'pair eval best column_moves generation landscape_seed operator_seed'.split()
nullable = 'holdout fitness parent_born'.split()
strings = 'version arm state_sha256'.split()
values = [None, False, True, 1, 1.5, '1', [], {}, [1], {'x': 1}]
predicates = {k: lambda v: type(v) is int for k in int_keys}
predicates.update({k: lambda v: v is None or type(v) is int for k in nullable})
predicates.update({k: lambda v: type(v) is str for k in strings})
predicates['selected'] = lambda v: type(v) is bool
for key, valid in predicates.items():
    for i, value in enumerate(values):
        if not valid(value):
            check(f'block.{key}.wrong_type.{i}', lambda key=key, value=value: rec_case(['search', key], value))
for key in list(raw['REC']['search']):
    check(f'block.{key}.missing', lambda key=key: rec_case(['search', key], remove=True))
for path in [['search', 'move', 'kind'], ['search', 'move', 'bits', 0],
             ['search', 'population', 0, 'born'], ['search', 'population', 0, 'fit']]:
    for i, value in enumerate(values):
        valid = type(value) is str if path[-1] == 'kind' else type(value) is int
        if not valid:
            check(f'nested.{path}.{i}', lambda path=path, value=value: rec_case(path, value))
for path in [['search', 'move'], ['search', 'population']]:
    for i, value in enumerate([False, True, 1, 'bad', {}, [0, 0, 0, 0]]):
        check(f'container.{path}.{i}', lambda path=path, value=value: rec_case(path, value))
istr = 'schema_version search_version map_sha256 operator_data_sha256 fitness_id carrier_variant protocol control_plane'.split()
iint = 'budget_per_arm master_seed pairs_total pair_first pair_count'.split()
for key in istr + iint:
    for i, value in enumerate(values):
        valid = type(value) is str if key in istr else type(value) is int
        if not valid:
            check(f'identity.{key}.wrong_type.{i}', lambda key=key, value=value: ident_case(key, value))
    check(f'identity.{key}.missing', lambda key=key: ident_case(key, remove=True))
for val in [None, False, True, 1, 'bad', [], [1]]:
    for common_flag in [False, True]:
        check(f'document.{val!r}.common={common_flag}',
              lambda val=val, common_flag=common_flag: (b.validate_run_log(val, ctx, common=common_flag), True))

common.validate(raw['IDENT'])
common.validate(raw['REC'])
baseline = dict(identity=b.identity_findings(raw['IDENT'], identity_ctx),
                record=b.record_findings(raw['REC'], ctx, want, {}))
assert baseline == dict(identity=[], record=[]), baseline

# Format boundary probe: Python's $ also matches before a final newline.
rec = copy.deepcopy(raw['REC'])
rec['search']['state_sha256'] += '\n'
common.validate(rec)
format_probe = dict(length=len(rec['search']['state_sha256']),
                    common='ACCEPTED', findings=b.record_findings(rec, ctx, want, {}))
out = dict(head=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=R, text=True).strip(),
           baseline=baseline, negative_cases=len(results), passed=sum(x['ok'] for x in results),
           failed=[x for x in results if not x['ok']], trailing_newline_digest=format_probe, cases=results)
print(json.dumps(out, indent=2))
assert not out['failed'], out['failed']
