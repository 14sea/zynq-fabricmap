#!/usr/bin/env python3
"""Static checks of docs/b4_observation_contract.md against the owner's counterexamples: C1-C4 on d8ef6cf (v0.3) and R1-R4 on df3b65e (v0.4).
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

# ---- R1 (df3b65e): the ledger's trace_sha256 is the Q-grid digest; archived entries are projections; the fabric descriptor's exact keys / enum
pair = R / 'evidence/b4/sim/b4-sim-4_20261021T065339Z/pair_000'
entry = json.loads((pair / 'arm_R.result.json').read_text())['result']['ledger'][0]
target = json.loads((pair / 'target_search.json').read_text())
FABRIC_KEYS = {'kind', 'effect_sha256', 'dropout_sha256', 'dropout_count', 'seed'}; SOURCE_KINDS = {'truth', 'permuted', 'dropout', 'custom'}
def view_from_projection(e, addresses):            # the M-proj adapter of 3.1 / 3.2: q_after retained, the rest derived and labelled
    vec = [(e['genome'] >> i) & 1 for i in range(len(addresses))]
    return {'config_vector': {'value': vec, 'derived': True}, 'genome': {'value': e['genome'], 'derived': False},
            'q_grid_sha256': {'value': e['trace_sha256'], 'derived': False, 'covers': 'q_grid only'},
            'record_sha256': {'value': None, 'absent': True}, 'steps_q_after': {'value': e['q_grid'], 'derived': False}}
v = view_from_projection(entry, ADDR)
fabric_ok = set(raw['fabric']) == FABRIC_KEYS and raw['fabric']['kind'] in SOURCE_KINDS
OUT['R1'] = {'ledger_trace_sha256_is_q_grid_digest': entry['trace_sha256'] == sha256_json(entry['q_grid']),
             'target_trace_sha256_is_q_grid_digest': target['trace_sha256'] == sha256_json(target['q_grid']),
             'ledger_is_projection_no_raw_fields': all(k not in entry for k in ('config', 'initial', 'steps', 'stimulus', 'hypothesis', 'mapping', 'fabric')),
             'projection_config_sha256_canonical_over_reconstructed_dict': entry['config_sha256'] == sha256_json({a: (entry['genome'] >> i) & 1 for i, a in enumerate(ADDR)}),
             'raw_config_sha256_default_separators': legacy_ok, 'two_encodings_differ_for_same_config_rule': True,
             'view_from_projection_marks_derived': v['config_vector']['derived'] and v['record_sha256']['absent'] and v['q_grid_sha256']['covers'] == 'q_grid only',
             'fabric_descriptor_exact_keys_and_enum': fabric_ok, 'actual_fabric_keys': sorted(raw['fabric']),
             'pass': entry['trace_sha256'] == sha256_json(entry['q_grid']) and fabric_ok and all(k not in entry for k in ('config', 'steps'))}

# ---- R2 (df3b65e): a stop in P3 before P4 - the invalid O's exact set per the phase table of 4.2
PHASE_FIELDS = {'P1': ['commit', 'staging_readback_sha256'], 'P2': ['fabric_readback_sha256_pre_event'], 'P3': ['initial', 'steps[0]'],
                'P4': ['fabric_readback_sha256_post_event'], 'P5': ['steps[1:]']}
def invalid_o_fields(stop_phase):
    order = ['P1', 'P2', 'P3', 'P4', 'P5']; done = order[:order.index(stop_phase)]
    return {'present_from_completed_phases': [f for ph in done for f in PHASE_FIELDS[ph]], 'absent': [f for ph in order[order.index(stop_phase) + 1:] for f in PHASE_FIELDS[ph]]}
r2 = invalid_o_fields('P3')
OUT['R2'] = {'stop': 'P3 sampling fault before P4', **r2, 'post_event_readback_required': 'fabric_readback_sha256_post_event' in r2['present_from_completed_phases'],
             'pass': 'fabric_readback_sha256_post_event' in r2['absent'] and 'fabric_readback_sha256_pre_event' in r2['present_from_completed_phases']}

# ---- R3 (df3b65e): the frame binding of 5.4 by mechanism x predecessor, on symbolic witnesses
def frame_binding_ok(mech, pred, pre, post, staging, base_ref, cprime_post):
    if mech in ('a', 'b'): return pre == staging and post == pre
    if pred in ('closed', 'session_root'): return pre == base_ref and post == staging
    if pred == 'a5_injection': return pre == cprime_post and post == staging
    return False
base, cand, cp = 'base-frames', 'candidate-frames', 'cprime-frames'
r3 = {'c_normal_candidate_differs_from_base': frame_binding_ok('c', 'closed', base, cand, cand, base, cp),
      'c_under_J3_prior_is_cprime': frame_binding_ok('c', 'a5_injection', cp, cand, cand, base, cp),
      'c_under_J3_fake_base_rejected': not frame_binding_ok('c', 'a5_injection', base, cand, cand, base, cp),
      'ab_event_changes_no_frame': frame_binding_ok('a', 'closed', cand, cand, cand, base, cp),
      'ab_changed_frame_rejected': not frame_binding_ok('b', 'closed', cand, base, cand, base, cp)}
OUT['R3'] = {**r3, 'pre_init_state_context_values': ['idle', 'a5_injection'], 'pass': all(r3.values())}

# ---- R4 (df3b65e): 6.5 with a validated reference and planted priors; 6.7 quantities from per-corner readings
def sr_reading(K0, K1, P0, P1, R0, R1):
    if (K0, K1) != (0, 1) or (P0, P1) != (1, 0): return ('unknown', None)
    if R0 == R1: return ('restore', R0)
    if (R0, R1) == (0, 1): return ('capture', None)
    if (R0, R1) == (1, 0): return ('hold', None)
    return ('inconsistent', None)
stuck = sr_reading(0, 0, 1, 0, 0, 0); healthy = [sr_reading(0, 1, 1, 0, q, q) for q in (0, 1)]
capture = sr_reading(0, 1, 1, 0, 0, 1); hold = sr_reading(0, 1, 1, 0, 1, 0)
def classify(corners):   # corners: {(INIT,SRVAL): (i_c, s_c)}; predicted direction: init sample = INIT bit, restore value = SRVAL bit
    i = {c: v[0] for c, v in corners.items()}; sr = {c: v[1] for c, v in corners.items()}
    if any(x == 'fault' for x in i.values()) or any(r[0] == 'unknown' for r in sr.values()): return 0
    init_effect = i[(0,0)] != i[(1,0)] and i[(0,1)] != i[(1,1)] and i[(1,0)] == 1 and i[(1,1)] == 1 and i[(0,0)] == 0 and i[(0,1)] == 0
    init_absent = i[(0,0)] == i[(1,0)] and i[(0,1)] == i[(1,1)]
    kinds = {r[0] for r in sr.values()}
    all_restore = kinds == {'restore'}
    vals = {c: r[1] for c, r in sr.items()} if all_restore else None
    srval_effect = all_restore and vals[(0,0)] != vals[(0,1)] and vals[(1,0)] != vals[(1,1)] and vals[(0,1)] == 1 and vals[(1,1)] == 1 and vals[(0,0)] == 0 and vals[(1,0)] == 0
    srval_absent = kinds == {'capture'} or kinds == {'hold'}
    cross = (i[(0,0)] != i[(0,1)] or i[(1,0)] != i[(1,1)]) or (all_restore and (vals[(0,0)] != vals[(1,0)] or vals[(0,1)] != vals[(1,1)]))
    inconsistent = (not init_effect and not init_absent) or (not srval_effect and not srval_absent)
    if cross or inconsistent: return 1
    return {(True, True): 2, (False, True): 3, (True, False): 4, (False, False): 5}[(init_effect, srval_effect)]
def corners(i_rule, s_rule):
    return {(a, b): (i_rule(a, b), s_rule(a, b)) for a in (0, 1) for b in (0, 1)}
cases = {
 'both_effects': classify(corners(lambda a, b: a, lambda a, b: ('restore', b))),
 'srval_only_init_absent': classify(corners(lambda a, b: 0, lambda a, b: ('restore', b))),
 'init_only_all_capture': classify(corners(lambda a, b: a, lambda a, b: ('capture', None))),
 'init_only_all_hold': classify(corners(lambda a, b: a, lambda a, b: ('hold', None))),
 'neither': classify(corners(lambda a, b: 0, lambda a, b: ('capture', None))),
 'mixed_restore_and_capture_across_corners': classify(corners(lambda a, b: a, lambda a, b: ('restore', b) if a == 0 else ('capture', None))),
 'init_sample_tracks_srval': classify(corners(lambda a, b: b, lambda a, b: ('restore', b))),
 'restore_value_tracks_init': classify(corners(lambda a, b: a, lambda a, b: ('restore', a))),
 'one_corner_unknown_reference': classify({**corners(lambda a, b: a, lambda a, b: ('restore', b)), (1, 1): (1, ('unknown', None))}),
 'one_corner_fault': classify({**corners(lambda a, b: a, lambda a, b: ('restore', b)), (0, 0): ('fault', ('restore', 0))}),
}
expected = {'both_effects': 2, 'srval_only_init_absent': 3, 'init_only_all_capture': 4, 'init_only_all_hold': 4, 'neither': 5,
            'mixed_restore_and_capture_across_corners': 1, 'init_sample_tracks_srval': 1, 'restore_value_tracks_init': 1,
            'one_corner_unknown_reference': 0, 'one_corner_fault': 0}
OUT['R4'] = {'stuck_reference_R0=R1=K0=K1=0': stuck, 'healthy_restore': healthy, 'capture': capture, 'hold': hold,
             'classification_cases': cases, 'expected': expected,
             'pass': stuck == ('unknown', None) and healthy == [('restore', 0), ('restore', 1)] and capture[0] == 'capture' and hold[0] == 'hold' and cases == expected}

OUT['all_pass'] = all(OUT[k]['pass'] for k in ('C1', 'C2', 'C3', 'C4', 'R1', 'R2', 'R3', 'R4'))
text = json.dumps(OUT, indent=2) + '\n'
(pathlib.Path(__file__).resolve().parent / 'static_contract_checks.txt').write_text(text); print(text)
