"""Owner's read-only/static document review: no B4 imports or observations/draws."""
from pathlib import Path
import copy
import hashlib
import itertools
import json
import subprocess
import tempfile

R = Path('/home/test/zynq_fabricmap')
D = Path(__file__).resolve().parent

def sha(obj):
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(',', ':')).encode()).hexdigest()

def git(*args):
    return subprocess.check_output(['git', *args], cwd=R, text=True).strip()

head = git('rev-parse', 'HEAD')
assert head == 'df3b65e8072eaab96d7c19d9d10e177b14e1ff9b'
assert not git('status', '--porcelain')

# Existing, committed observation projections. No replay or model call is made.
pair = R / 'evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000'
arm = json.loads((pair / 'arm_R.result.json').read_text())['result']
entry = arm['ledger'][0]
target = json.loads((pair / 'target_search.json').read_text())
assert entry['trace_sha256'] == sha(entry['q_grid'])
assert target['trace_sha256'] == sha(target['q_grid'])
mutated = copy.deepcopy(entry)
mutated['stimulus_sha256'] = '0' * 64
assert mutated['trace_sha256'] == sha(mutated['q_grid'])
assert sha(entry) != sha(mutated)
quarantine = R / 'evidence/b4/unit_protocol_v2_tool_2026_10_20/owner_review_21db2de_PASS/float_return.json'
raw = json.loads(quarantine.read_text())['quarantine']['raw']
raw_grid = [s['q_after'] for s in raw['steps']]
assert sha(raw) != sha(raw_grid)
assert set(raw['fabric']) == {'kind', 'effect_sha256', 'dropout_sha256', 'dropout_count', 'seed'}
out = {'R1': {
    'retained_entry_source': str((pair / 'arm_R.result.json').relative_to(R)),
    'ledger_trace_sha256': entry['trace_sha256'],
    'q_grid_sha256': sha(entry['q_grid']),
    'whole_ledger_entry_sha256': sha(entry),
    'target_trace_hash_is_q_grid_hash': True,
    'changing_stimulus_commitment_leaves_trace_sha256_unchanged': True,
    'whole_raw_trace_hash_differs_from_raw_q_grid_hash': True,
    'note': 'The preserved quarantine trace has a deliberately malformed float cell. It is inspected only for hashing representation and source-header shape, never accepted as a valid observation.',
    'ledger_missing_raw_fields': [k for k in ('config', 'initial', 'steps', 'stimulus', 'hypothesis', 'mapping', 'fabric') if k not in entry],
    'actual_fabric_keys': sorted(raw['fabric']),
    'actual_source_kinds_from_source_reading': ['truth', 'permuted', 'dropout', 'custom'],
    'document_fabric_keys': ['kind', 'effect_sha256', 'dropout', 'seed'],
    'document_kind_omits_custom_and_adds_hypothesis_swap_names': True,
}}

# Mechanism (c): symbolic, distinct frame witnesses, not computed configuration/readback.
base, candidate = 'base-frame-witness', 'different-candidate-frame-witness'
pre, post, staging = base, candidate, candidate
assert post == staging
assert pre != post
out['R3'] = {
    'mechanism_c_pre_witness': pre, 'mechanism_c_post_witness': post,
    'staging_witness': staging, 'section_6_3_post_equals_staging': post == staging,
    'section_5_4_requires_pre_equals_post': pre == post,
    'effect': 'A candidate different from the base satisfies 6.3 but necessarily violates 5.4; 6.7 requires 5.4 on every cross record.',
    'additional_order_context': 'The generic P3 pre-init-sample placement is after P2, while mechanism (c) requires an actual sample before the P2 write. The per-mechanism exception must be reflected in phase/readiness and frame rules; no new event/operation is requested.',
    'A5_context_exception': 'Section 3.1 view pre_init_state fixes clock/ce/sr/d to zero, while J3 explicitly copies nonzero held inputs into raw initial and 3.2 maps initial into the view. Make the already declared qualification exception explicit in the view contract, not an unrecorded cleanup or fabricated zero.'
}

# Invalid O at P3 cannot include the future P4 readback as a real hex digest.
partial = {'status': 'invalid', 'fault': {'code': 'sample_fault', 'step_reached': 0},
           'fabric_readback_sha256_pre_init': 'a' * 64, 'steps': []}
missing = ['fabric_readback_sha256_post_init']
assert all(k not in partial for k in missing)
out['R2'] = {
    'synthetic_stop': 'sampling fault during P3, before P4',
    'future_required_fields_not_obtainable': missing,
    'partial_observation': partial,
    'section_4_2': 'O exactly requires both readback fields of type hex for complete and invalid; invalid adds fault, but no partial-field exception is defined.',
    'section_5_7': 'P1-P5 failure seals O invalid, preserving only the observed prefix and no invented future values.',
    'required_resolution': 'Define phase-dependent exact allowed/required key sets for invalid O (as already done for faulted X), or a distinct bound partial object. Complete O must retain all normal requirements.'
}

# Exactly the written 6.5 rule on synthetic sample values, not a fabric simulation.
def sr_reading(r0, r1, k0, k1):
    if r0 == r1:
        return {'kind': 'restore', 'value': r0}
    if (r0, r1) == (k0, k1):
        return {'kind': 'capture', 'value': None}
    return {'kind': 'inconsistent', 'value': None}

stuck = sr_reading(0, 0, 0, 0)
assert stuck == {'kind': 'restore', 'value': 0}
indistinguishable = [{'R0': q, 'R1': q, 'K0': q, 'K1': q,
                     'written_reading': sr_reading(q, q, q, q)} for q in (0, 1)]
out['R4'] = {
    'stuck_or_non_capturing_reference_case': {'R0': 0, 'R1': 0, 'K0': 0, 'K1': 0},
    'written_reading': stuck,
    'indistinguishable_SR_on_and_SR_off_records': indistinguishable,
    'limitation': 'The rule declares restore even when its SR-off reference cannot distinguish either D. These data do not distinguish an SR restore from holding/no capture. A reference-validity prerequisite or a weaker, explicitly conditional evidence claim is needed.',
    'capture_case': sr_reading(0, 1, 0, 1),
    'healthy_restore_cases': [sr_reading(q, q, 0, 1) for q in (0, 1)],
    'six_seven_missing_evidence_case': 'When 6.5 returns capture, no SR-restore evidence value exists. Define how 6.7 computes cross_tracking/paired effects from absent evidence, rather than merely classifying four precomputed booleans.'
}

# Reproduce author's existing static checks at a temporary copy, not in tracked evidence.
author = R / 'evidence/b4/unit_2c_obs_2026_10_21/static_contract_checks.py'
author_txt = author.with_suffix('.txt')
with tempfile.TemporaryDirectory(prefix='df3b65e_static_') as td:
    copied = Path(td) / author.name
    copied.write_bytes(author.read_bytes())
    p = subprocess.run(['python3', '-B', str(copied)], cwd=R, text=True, capture_output=True)
    assert p.returncode == 0, p.stderr
    produced = copied.with_suffix('.txt').read_bytes()
    assert produced == author_txt.read_bytes()
    assert json.loads(produced)['all_pass'] is True
    (D / 'author_static_rerun.txt').write_text(p.stdout)
out['author_static_checks'] = {'exit': p.returncode, 'byte_identical_to_committed_output': True,
                             'all_pass': True, 'scope_limit': 'Does not check ledger-vs-whole-record hashing, mechanism-c frame invariance, failed SR-off reference captures, or deriving 6.7 quantities from missing evidence.'}

paths = ['b4/', 'b3/', 'host/', 'tests/', 'firmware/', 'manifests/', 'gate_runs/',
         'evidence/b3/', 'evidence/b4/sim/', 'evidence/b4/gonogo/', 'evidence/b4/gate/']
assert not git('diff', '--name-only', 'fceedd6', 'HEAD', '--', *paths)
names = ['k9_address_record.py', 'k9_address_record.txt', 'positive_control_choice.py', 'positive_control_choice.txt']
assert not git('diff', '--name-only', 'e91650b', 'HEAD', '--',
               *['evidence/b4/unit_2c_obs_2026_10_21/' + n for n in names])
src = R / 'build/wip/owner_review_d8ef6cf_2026_10_21'
dst = R / 'evidence/b4/unit_2c_obs_2026_10_21/owner_review_d8ef6cf_HOLD'
originals = [p for p in src.rglob('*') if p.is_file()]
assert {str(p.relative_to(src)) for p in originals} == {str(p.relative_to(dst)) for p in dst.rglob('*') if p.is_file()}
assert all((dst / p.relative_to(src)).read_bytes() == p.read_bytes() for p in originals)
for line in (dst / 'SHA256SUMS').read_text().splitlines():
    digest, name = line.split('  ', 1)
    assert hashlib.sha256((dst / name).read_bytes()).hexdigest() == digest

out['checks'] = {'head': head, 'tree_clean': not git('status', '--porcelain'),
                 'protected_paths_unchanged_since_fceedd6': paths,
                 'selection_scripts_and_outputs_unchanged': True,
                 'prior_review_copied_byte_identical': True, 'prior_review_files': len(originals),
                 'new_model_or_board_observations': False, 'new_production_seed_derivation': False}
(D / 'static_contract_probes.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
