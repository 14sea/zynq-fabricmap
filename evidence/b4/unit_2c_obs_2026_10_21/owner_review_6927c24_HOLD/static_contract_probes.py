"""Read-only document review. No B4 production module, model, seed, port or verifier is called."""
from pathlib import Path
import contextlib
import hashlib
import io
import json
import runpy
import subprocess
import tempfile

R = Path('/home/test/zynq_fabricmap')
D = Path(__file__).resolve().parent

def git(*a):
    return subprocess.check_output(['git', *a], cwd=R, text=True).strip()

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

assert git('rev-parse', 'HEAD') == '6927c2452ad7f8ead23d78a0061a3c201b872ac1'
assert git('status', '--porcelain') == ''
unit = R / 'evidence/b4/unit_2c_obs_2026_10_21'
author = unit / 'static_contract_checks.py'
with tempfile.TemporaryDirectory(prefix='owner_6927c24_static_') as temp:
    script = Path(temp) / author.name
    script.write_bytes(author.read_bytes())
    stream = io.StringIO()
    with contextlib.redirect_stdout(stream):
        ns = runpy.run_path(str(script), run_name='__main__')
    result = script.with_suffix('.txt').read_bytes()
    assert result == author.with_suffix('.txt').read_bytes()
    assert json.loads(result)['all_pass'] is True
    (D / 'author_static_rerun.txt').write_text(stream.getvalue())

# Independently recalculate bindings on already retained, public observation records.
pair = R / 'evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000'
ledger = json.loads((pair / 'arm_R.result.json').read_text())['result']['ledger'][0]
target = json.loads((pair / 'target_search.json').read_text())
memo = json.loads((pair / 'k9.json').read_text())['observations'][0]
for rec in (ledger, target, memo):
    assert rec['trace_sha256'] == sha(rec['q_grid'])
    cfg = {a: (rec['genome'] >> i) & 1 for i, a in enumerate(ns['ADDR'])}
    assert rec['config_sha256'] == sha(cfg)
    assert all(k not in rec for k in ('initial', 'steps', 'stimulus', 'config'))

# R1: the new frame table includes session_root, but its predecessor reference terminates.
root_predecessor = {'kind': 'session_root', 'seq': None, 'close_sha256': None}
prior_x_by_seq = {}  # At the first transaction no predecessor X exists.
assert root_predecessor['seq'] not in prior_x_by_seq
root_result = {
    'mechanism': 'c', 'predecessor': root_predecessor,
    'prior_X_available': False,
    'section_5_4_requires': 'pre-event equals predecessor X.base_readback_sha256',
    'section_5_5_terminating_case': 'session_root has seq=null and close_sha256=null; first X not yet written',
    'effect': 'The root cannot resolve its required reference; using its own later X would be circular and use a future value.',
    'author_helper_issue': 'frame_binding_ok accepts a supplied base_ref for session_root but never resolves where it came from, and no root case is in r3 checks.'
}

# R2: all four SR episodes restore to the same constant. This is an absent SRVAL main effect,
# not wrong-bit tracking, unknown reference or disagreement between the paired effects.
# The corner labels/directions below use the author's normalized logical convention;
# the absence result is independent of the physical Z-bit polarity.
def evaluate_written(corners):
    init_values = {c: v[0] for c, v in corners.items()}
    sr = {c: v[1] for c, v in corners.items()}
    not_assessable = any(v == 'fault' for v in init_values.values()) or any(v[0] == 'unknown' for v in sr.values())
    if not_assessable:
        return {'row': 0, 'not_assessable': True}
    i00, i01, i10, i11 = [init_values[c] for c in ((0, 0), (0, 1), (1, 0), (1, 1))]
    init_effect = (i00, i01, i10, i11) == (0, 0, 1, 1)
    init_absent = i00 == i10 and i01 == i11
    kinds = {v[0] for v in sr.values()}
    all_restore = kinds == {'restore'}
    vals = {c: v[1] for c, v in sr.items()} if all_restore else {}
    srval_effect = all_restore and tuple(vals[c] for c in ((0, 0), (0, 1), (1, 0), (1, 1))) == (0, 1, 0, 1)
    srval_absent = kinds == {'capture'} or kinds == {'hold'}
    cross = i00 != i01 or i10 != i11 or (all_restore and (vals[(0, 0)] != vals[(1, 0)] or vals[(0, 1)] != vals[(1, 1)]))
    inconsistent = (not init_effect and not init_absent) or (not srval_effect and not srval_absent)
    row = 1 if cross or inconsistent else (2 if init_effect and srval_effect else 3 if srval_effect else 4 if init_effect else 5)
    return {'row': row, 'not_assessable': False, 'init_effect': init_effect, 'init_absent': init_absent,
            'srval_effect': srval_effect, 'srval_absent': srval_absent, 'cross_tracking': cross, 'inconsistent': inconsistent}

constant_cases = []
for value in (0, 1):
    for init_present in (False, True):
        corners = {(a, b): (a if init_present else 0, ('restore', value)) for a in (0, 1) for b in (0, 1)}
        got = evaluate_written(corners)
        assert got['row'] == ns['classify'](corners) == 1
        assert got['not_assessable'] is False and got['cross_tracking'] is False
        for a, b in corners:
            # References and planted priors valid; the corner reading is an identified restore.
            assert ns['sr_reading'](0, 1, 1, 0, value, value) == ('restore', value)
        constant_cases.append({'constant_restore_value': value, 'init_main_effect_present': init_present,
                               'derived_written_quantities': got,
                               'expected_row_under_absent_main_effect_policy': 4 if init_present else 5,
                               'actual_author_helper_row': 1})

# Positive and negative cases already fixed by the author remain accepted.
assert ns['sr_reading'](0, 0, 1, 0, 0, 0) == ('unknown', None)
assert ns['sr_reading'](0, 1, 1, 0, 0, 1) == ('capture', None)
assert ns['sr_reading'](0, 1, 1, 0, 1, 0) == ('hold', None)

protected = ['b4/', 'b3/', 'host/', 'tests/', 'firmware/', 'manifests/', 'gate_runs/',
             'evidence/b3/', 'evidence/b4/sim/', 'evidence/b4/gate/', 'evidence/b4/gonogo/']
assert not git('diff', '--name-only', 'fceedd6', 'HEAD', '--', *protected)
selection = ['k9_address_record.py', 'k9_address_record.txt', 'positive_control_choice.py', 'positive_control_choice.txt']
assert not git('diff', '--name-only', 'e91650b', 'HEAD', '--', *[str((unit / n).relative_to(R)) for n in selection])
source = R / 'build/wip/owner_review_df3b65e_2026_10_21'
dest = unit / 'owner_review_df3b65e_HOLD'
files = [p for p in source.rglob('*') if p.is_file()]
assert {str(p.relative_to(source)) for p in files} == {str(p.relative_to(dest)) for p in dest.rglob('*') if p.is_file()}
assert all(p.read_bytes() == (dest / p.relative_to(source)).read_bytes() for p in files)
for line in (dest / 'SHA256SUMS').read_text().splitlines():
    h, name = line.split('  ', 1)
    assert hashlib.sha256((dest / name).read_bytes()).hexdigest() == h

out = {'head': git('rev-parse', 'HEAD'), 'author_static_rerun_byte_identical': True,
       'author_all_pass': True, 'prior_review_byte_identical': True, 'prior_review_files': len(files),
       'accepted_R1_representation_bindings': {'ledger_target_memo_grid_and_configuration_hashes_checked': True},
       'R1_root_reference': root_result, 'R2_constant_restore_cases': constant_cases,
       'fixed_reference_and_priors_cases_accepted': True,
       'protected_paths_unchanged': protected, 'selection_scripts_and_outputs_unchanged': True,
       'new_model_or_board_observations': False, 'production_module_imports_or_seed_derivations': False,
       'tree_clean': git('status', '--porcelain') == ''}
(D / 'static_contract_probes.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
