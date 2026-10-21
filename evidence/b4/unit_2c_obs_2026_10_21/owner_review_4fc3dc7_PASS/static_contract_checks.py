"""Owner's targeted document checks; no production B4 imports, seed draws or observations."""
from pathlib import Path
import contextlib
import copy
import hashlib
import io
import json
import runpy
import subprocess
import tempfile

R = Path('/home/test/zynq_fabricmap')
D = Path(__file__).resolve().parent
UNIT = R / 'evidence/b4/unit_2c_obs_2026_10_21'

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R, text=True).strip()

def digest(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

assert git('rev-parse', 'HEAD') == '4fc3dc70b5a84355298e4f3f30ab3443f62a0cf1'
assert not git('status', '--porcelain')
author = UNIT / 'static_contract_checks.py'
with tempfile.TemporaryDirectory(prefix='owner_4fc3dc7_') as temp:
    script = Path(temp) / author.name
    script.write_bytes(author.read_bytes())
    stdout = io.StringIO()
    with contextlib.redirect_stdout(stdout):
        ns = runpy.run_path(str(script), run_name='__main__')
    produced = script.with_suffix('.txt').read_bytes()
    assert produced == author.with_suffix('.txt').read_bytes()
    assert json.loads(produced)['all_pass'] is True
    (D / 'author_static_rerun.txt').write_text(stdout.getvalue())

# Symbolic fixture only: these words/digests are not a device, a bitstream or a production manifest.
# The trusted reference exists before the opening record and is never read from that record.
instrument = {'variant': '00000000', 'carrier_sha256': '1' * 64, 'image_sha256': '2' * 64}
trusted_base_content = {'fixture_encoding': 'ordered words', 'words': [0, 0, 0, 0]}
trusted_base_digest = digest(trusted_base_content)

def make_open(startup_content):
    observed = digest(startup_content)
    return {'instrument': instrument, 'startup_readback_sha256': observed,
            'base_frames_reference_sha256': trusted_base_digest,
            'status': 'open' if observed == trusted_base_digest else 'refused'}

opening = make_open(trusted_base_content)
opening_sha = digest(opening)
root_context = {'predecessor': {'kind': 'session_root', 'seq': None, 'close_sha256': None},
                'init_event': {'parameters': {'session_open_sha256': opening_sha}}}

def root_binding(rec, available_before_event, context, pre, post, staging):
    if rec is None or not available_before_event:
        return False
    if rec['instrument'] != instrument or rec['base_frames_reference_sha256'] != trusted_base_digest:
        return False
    if rec['status'] != 'open' or rec['startup_readback_sha256'] != trusted_base_digest:
        return False
    return (context['predecessor'] == {'kind': 'session_root', 'seq': None, 'close_sha256': None}
            and context['init_event']['parameters']['session_open_sha256'] == digest(rec)
            and pre == rec['startup_readback_sha256'] and post == staging)

bad_startup = make_open({'fixture_encoding': 'ordered words', 'words': [1, 0, 0, 0]})
assert bad_startup['status'] == 'refused'
wrong_pin = dict(opening, base_frames_reference_sha256='3' * 64)
bad_link = copy.deepcopy(root_context)
bad_link['init_event']['parameters']['session_open_sha256'] = '4' * 64
root_cases = {
    'opens_against_independent_preexisting_pin': opening['status'] == 'open',
    'root_without_predecessor_binds_available_opening': root_binding(opening, True, root_context, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'missing_opening_rejected': not root_binding(None, True, root_context, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'future_or_own_close_cannot_supply_opening': not root_binding(opening, False, root_context, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'startup_mismatch_refused_and_root_rejected': bad_startup['status'] == 'refused' and not root_binding(bad_startup, True, root_context, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'self_declared_wrong_pin_rejected': not root_binding(wrong_pin, True, root_context, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'root_hash_reference_mismatch_rejected': not root_binding(opening, True, bad_link, trusted_base_digest, trusted_base_digest, trusted_base_digest),
    'actual_root_pre_event_drift_rejected': not root_binding(opening, True, root_context, '5' * 64, trusted_base_digest, trusted_base_digest),
}
assert all(root_cases.values())

# Direct Boolean/readout cases in the author's normalized logical direction convention.
# No model/fabric is executed to obtain these values.
def independently_classify(corners):
    iv = {c: r[0] for c, r in corners.items()}
    sv = {c: r[1] for c, r in corners.items()}
    if any(v == 'fault' for v in iv.values()) or any(v[0] == 'unknown' for v in sv.values()):
        return 0
    order = ((0, 0), (0, 1), (1, 0), (1, 1))
    init_effect = tuple(iv[c] for c in order) == (0, 0, 1, 1)
    init_absent = iv[(0, 0)] == iv[(1, 0)] and iv[(0, 1)] == iv[(1, 1)]
    all_restore = all(r[0] == 'restore' for r in sv.values())
    values = {c: r[1] for c, r in sv.items()} if all_restore else {}
    srval_effect = all_restore and tuple(values[c] for c in order) == (0, 1, 0, 1)
    srval_absent = (all(r[0] == 'capture' for r in sv.values())
                    or all(r[0] == 'hold' for r in sv.values())
                    or (all_restore and values[(0, 0)] == values[(0, 1)] and values[(1, 0)] == values[(1, 1)]))
    cross = (iv[(0, 0)] != iv[(0, 1)] or iv[(1, 0)] != iv[(1, 1)]
             or (all_restore and (values[(0, 0)] != values[(1, 0)] or values[(0, 1)] != values[(1, 1)])))
    if cross or (not init_effect and not init_absent) or (not srval_effect and not srval_absent):
        return 1
    return 2 if init_effect and srval_effect else 3 if srval_effect else 4 if init_effect else 5

constant_cases = []
for init_present in (True, False):
    for value in (0, 1):
        corners = {(a, b): (a if init_present else 0, ('restore', value)) for a in (0, 1) for b in (0, 1)}
        expected = 4 if init_present else 5
        actual = independently_classify(corners)
        assert actual == ns['classify'](corners) == expected
        constant_cases.append({'init_effect_present': init_present, 'constant_restore_value': value,
                               'expected_row': expected, 'independent_row': actual, 'author_row': ns['classify'](corners)})

cross = {(a, b): (a, ('restore', a)) for a in (0, 1) for b in (0, 1)}
assert independently_classify(cross) == ns['classify'](cross) == 1
assert ns['sr_reading'](0, 0, 1, 0, 0, 0) == ('unknown', None)
assert ns['a5_verdict'](ns['record'](0), [1] * 8, ns['record'](1)) == 'pass'
assert ns['a5_verdict'](ns['record'](0), [1] * 8, ns['record'](1, after=1)) == 'fail'

protected = ['b4/', 'b3/', 'host/', 'tests/', 'firmware/', 'manifests/', 'gate_runs/',
             'evidence/b3/', 'evidence/b4/sim/', 'evidence/b4/gate/', 'evidence/b4/gonogo/']
assert not git('diff', '--name-only', 'fceedd6', 'HEAD', '--', *protected)
names = ['k9_address_record.py', 'k9_address_record.txt', 'positive_control_choice.py', 'positive_control_choice.txt']
assert not git('diff', '--name-only', 'e91650b', 'HEAD', '--', *[str((UNIT / n).relative_to(R)) for n in names])
original_arch = subprocess.check_output(['git', 'show', 'fceedd6:docs/b4_architecture.md'], cwd=R, text=True)
live_arch = (R / 'docs/b4_architecture.md').read_text()
assert original_arch.split('\n## 13.')[0] == live_arch.split('\n## 13.')[0]
previous = R / 'build/wip/owner_review_6927c24_2026_10_21'
archived = UNIT / 'owner_review_6927c24_HOLD'
files = [p for p in previous.rglob('*') if p.is_file()]
assert {str(p.relative_to(previous)) for p in files} == {str(p.relative_to(archived)) for p in archived.rglob('*') if p.is_file()}
assert all(p.read_bytes() == (archived / p.relative_to(previous)).read_bytes() for p in files)
for line in (archived / 'SHA256SUMS').read_text().splitlines():
    sha, name = line.split('  ', 1)
    assert hashlib.sha256((archived / name).read_bytes()).hexdigest() == sha

out = {'head': git('rev-parse', 'HEAD'), 'root_bootstrap_cases': root_cases,
       'constant_restore_cases': constant_cases, 'restore_tracking_INIT_still_row_1': True,
       'stuck_reference_still_unknown': True, 'A5_clear_and_persistence_cases_preserved': True,
       'author_static_rerun_byte_identical': True, 'author_all_pass': True,
       'previous_review_copy_byte_identical': True, 'previous_review_files': len(files),
       'protected_paths_unchanged': protected, 'architecture_sections_before_13_unchanged': True,
       'choice_7_unchanged': True, 'selection_scripts_and_outputs_unchanged': True,
       'new_model_or_board_observations': False, 'production_seed_derivation': False,
       'production_B4_module_imports_in_this_script': False, 'tracked_tree_clean': not git('status', '--porcelain'),
       'scope': 'Targeted static/manual examples only; not a generic validator or proof of physical behavior.'}
(D / 'independent_checks.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
