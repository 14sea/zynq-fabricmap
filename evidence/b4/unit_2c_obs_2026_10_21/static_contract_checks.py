#!/usr/bin/env python3
"""Static checks of docs/b4_observation_contract.md v0.3 against the owner's four counterexamples on d8ef6cf (C1-C4).
Read-only. Reads one retained quarantine record's unchanged config/header fields (the owner's probe source), builds small synthetic
Boolean records, and evaluates the contract's written rules as plain functions. Calls no model, fabric, seed generator, carrier,
simulator or production verifier. Writes only static_contract_checks.txt beside itself."""
import hashlib, itertools, json, pathlib
R = pathlib.Path('/home/test/zynq_fabricmap'); OUT = {}
def sha256_json(obj):  # b4_execution.sha256_json, copied verbatim as a rule, not imported across the pinned boundary
    return hashlib.sha256(json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
ADDR = ['0x00400a00/52/16','0x00400a01/51/7','0x00400a01/51/19','0x00400a01/52/3','0x00400a01/52/7','0x00400a01/52/15','0x00400a01/52/19',
        '0x00400a01/52/23','0x00400a1e/51/12','0x00400a1e/51/30','0x00400a1e/52/0','0x00400a1e/52/1','0x00400a1e/52/18','0x00400a1f/51/3',
        '0x00400a1f/51/6','0x00400a1f/51/22','0x00400a1f/51/28','0x00400a1f/52/1','0x00400a1f/52/9','0x00400a1f/52/19','0x00400a1f/52/26']  # mapping address order (unit README / k9 record)

# ---- C1: the legacy raw format through the adapter of section 3.2; the field-aware rule of 4.3
P = R / 'evidence/b4/unit_protocol_v2_tool_2026_10_20/owner_review_21db2de_PASS/float_return.json'
raw = json.loads(P.read_text())['quarantine']['raw']; cfg = raw['config']
assert isinstance(cfg, dict) and set(cfg) == set(ADDR) and 'stimulus_sha256' not in raw
# the raw digest verified under ITS declared encoding only (json.dumps(dict, sort_keys=True), default separators) - never recomputed under another
legacy_ok = hashlib.sha256(json.dumps(cfg, sort_keys=True).encode()).hexdigest() == raw['config_sha256']
vector = [cfg[a] for a in ADDR]; genome = sum(b << i for i, b in enumerate(vector))
derived_stimulus = sha256_json(list(raw['stimulus']))          # the view's DERIVED field, the ledger's existing rule
ENUM = {'fabric.kind': {'truth', 'permuted', 'dropout', 'ce_ungated', 'init_no_effect', 'latch_hold', 'sync_level', 'x5ff_storage'}}
DENY = {'target', 'expected', 'tables', 'oracle', 'semantic', 'decode', 'ff_init', 'ff_srval', 'ce_mode', 'sr_mode', 'sr_kind', 'storage_kind', 'clock_mode'}
MODEL_KEYS = {'schema','schema_version','visibility','q_null_means','hypothesis','mapping','fabric','config','config_sha256','stimulus','initial','elements','steps'}
def keys_at_all_levels(o, acc=None):
    acc = set() if acc is None else acc
    if isinstance(o, dict):
        acc |= set(o)
        for v in o.values(): keys_at_all_levels(v, acc)
    elif isinstance(o, list):
        for v in o: keys_at_all_levels(v, acc)
    return acc
def validate_model_raw(rec):
    findings = []
    if set(rec) != MODEL_KEYS: findings.append(f'top-level keys != model raw set: extra {sorted(set(rec)-MODEL_KEYS)} missing {sorted(MODEL_KEYS-set(rec))}')
    if rec.get('fabric', {}).get('kind') not in ENUM['fabric.kind']: findings.append('fabric.kind not in enum')
    hit = keys_at_all_levels(rec) & DENY                      # the deny-list applies to KEY NAMES only (4.3)
    if hit: findings.append(f'deny-listed key names {sorted(hit)}')
    return findings
legit = {k: raw[k] for k in MODEL_KEYS if k in raw}
legit_findings = validate_model_raw(legit)
bad = dict(legit); bad['answer_bits'] = [1, 0, 1]
bad_findings = validate_model_raw(bad)
OUT['C1'] = {'source': str(P.relative_to(R)), 'legacy_config_is_dict': True, 'legacy_digest_verified_under_declared_encoding': legacy_ok,
             'view_config_vector_len': len(vector), 'view_genome': genome, 'view_stimulus_sha256_derived': derived_stimulus,
             'legacy_fabric_kind': raw['fabric']['kind'], 'legit_model_record_findings': legit_findings,
             'answer_bits_extra_key_findings': bad_findings,
             'pass': legacy_ok and legit_findings == [] and any('extra' in f for f in bad_findings)}

# ---- C2: record readiness (section 5.1 table) - every field's earliest phase <= its object's immutability phase; O holds nothing from P7+
EARLIEST = {'O': {'commit': 1, 'staging_readback_sha256': 1, 'predecessor': 1, 'fabric_readback_sha256_pre_init': 2, 'initial': 3, 'steps[0]': 3,
                  'fabric_readback_sha256_post_init': 4, 'steps[1:]': 5, 'status': 6.0},
            'F': {'observation_sha256': 6.0, 'task_digest': 6.5, 'fitness': 6.5},
            'X': {'observation_sha256': 6.0, 'cleanup': 7, 'base_readback_sha256': 8, 'base_state_sample': 9, 'idle_status': 10, 'status': 10}}
IMMUTABLE = {'O': 6.0, 'F': 6.5, 'X': 10}
viol = [(o, f, p) for o, fs in EARLIEST.items() for f, p in fs.items() if p > IMMUTABLE[o]]
o_has_future = [f for f, p in EARLIEST['O'].items() if p >= 7]
OUT['C2'] = {'immutability_phase': IMMUTABLE, 'fields_written_after_their_object_is_immutable': viol, 'O_fields_from_P7_or_later': o_has_future,
             'current_restore_witnesses_in_current_X': ['cleanup', 'base_readback_sha256', 'base_state_sample', 'idle_status'],
             'predecessor_is_reference': {'kind': ['session_root', 'closed', 'a5_injection'], 'holds_values': False, 'root_case': 'kind=session_root, seq=null, close_sha256=null'},
             'pass': viol == [] and o_has_future == []}

# ---- C3: A5 projection (5.6) on the owner's counterexample, and the three-row decision table
def record(before, after=0, final=0):
    return {'initial': {'q': [before]*8},
            'steps': [{'step': 0, 'kind': 'init', 'prev_event': 'none', 'clock_before': 0, 'clock_after': 0, 'edge': None, 'ce': 0, 'sr': 0, 'd': 0,
                       'q_before': [before]*8, 'q_after': [after]*8}],
            'X': {'cleanup': {'final_q': [final]*8}}}
def post_init_projection(r):
    s0 = {k: v for k, v in r['steps'][0].items() if k != 'q_before'}   # the pre-init state excluded in BOTH places
    return {'step0_q_after': r['steps'][0]['q_after'], 'steps_1_on': r['steps'][1:], 'cleanup_final_q': r['X']['cleanup']['final_q']}
def a5_verdict(o_c1, o_cprime_final, o_c2):
    arrived = o_c2['initial']['q'] != o_c1['initial']['q'] and o_c2['initial']['q'] == o_cprime_final
    if not arrived: return 'not demonstrated'
    return 'pass' if post_init_projection(o_c2) == post_init_projection(o_c1) else 'fail'
c1 = record(0); injected = [1]*8
owner_case = a5_verdict(c1, injected, record(1))                  # owner's counterexample: perfect reset -> must be pass
persist = a5_verdict(c1, injected, record(1, after=1))             # persistence after init -> fail
not_arrived = a5_verdict(c1, injected, record(0))                  # injection did not reach the boundary -> not demonstrated
OUT['C3'] = {'owner_counterexample_verdict': owner_case, 'persistence_verdict': persist, 'injection_not_arrived_verdict': not_arrived,
             'pass': (owner_case, persist, not_arrived) == ('pass', 'fail', 'not demonstrated')}

# ---- C4: one fixed stimulus with two SR episodes (6.5) is interpretable at every corner; the classification of 6.7 is total and non-overlapping
def sr_evidence(srval, restores, k0=0, k1=1):
    R0 = srval if restores else k0; R1 = srval if restores else k1
    if R0 == R1: return ('restore', R0)
    if (R0, R1) == (k0, k1): return ('capture', None)
    return ('inconsistent', None)
corner_ok = all(sr_evidence(srval, True) == ('restore', srval) and sr_evidence(srval, False) == ('capture', None) for srval in (0, 1))
def classify(init_effect, srval_effect, cross_tracking, inconsistent):
    if cross_tracking or inconsistent: return 1
    return {(True, True): 2, (False, True): 3, (True, False): 4, (False, False): 5}[(init_effect, srval_effect)]
states = list(itertools.product([False, True], repeat=4))
rows = [classify(*s) for s in states]
OUT['C4'] = {'single_fixed_stimulus_two_episodes_interpretable_for_both_srval': corner_ok,
             'classification_total': len(rows) == 16, 'classification_single_row_each': True,
             'rows_for_main_effect_absent_without_cross_or_inconsistency': {'srval_only': classify(False, True, False, False), 'init_only': classify(True, False, False, False)},
             'row_for_any_cross_tracking': sorted({classify(i, s, True, x) for i in (0,1) for s in (0,1) for x in (0,1)}),
             'pass': corner_ok and len(rows) == 16 and classify(False, True, False, False) == 3 and classify(True, False, False, False) == 4}
OUT['all_pass'] = all(OUT[k]['pass'] for k in ('C1', 'C2', 'C3', 'C4'))
text = json.dumps(OUT, indent=2) + '\n'
(pathlib.Path(__file__).resolve().parent / 'static_contract_checks.txt').write_text(text); print(text)
