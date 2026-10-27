"""Counterexamples against the committed record builder/validators in the isolated snapshot."""
from pathlib import Path
import copy
import json
import sys

D = Path(__file__).resolve().parent
root = Path(json.loads((D / 'snapshot.json').read_text())['temporary_root'])
sys.path[:0] = [str(root), str(root / 'host')]
import b4carrier_records as rec
from tests.test_b4carrier_records import ClosedSets, LINKS, TIMING, ROOT

base = ClosedSets()._o()
assert rec.validate_observation(base) == []
out = {}

def accepted_case(label, mutate):
    o = copy.deepcopy(base)
    mutate(o)
    try:
        findings = rec.validate_observation(o)
        out[label] = {'findings': findings, 'accepted': not findings}
    except Exception as e:
        out[label] = {'exception': type(e).__name__ + ': ' + str(e), 'accepted': False}

accepted_case('nested_instrument_answer_bits', lambda o: o['instrument'].update(answer_bits=[1]))
accepted_case('nested_init_parameters_answer_bits', lambda o: o['init_event']['parameters'].update(answer_bits=[1]))
accepted_case('wrong_instrument_variant', lambda o: o['instrument'].update(variant='42310001'))
accepted_case('empty_complete_steps', lambda o: o.update(steps=[]))
accepted_case('invalid_complete_preinit_sample', lambda o: (o['initial'].update(q=None), o['steps'][0].update(q_before=None)))
accepted_case('wrong_step_kind_and_timing', lambda o: (o['steps'][0].update(kind='nonsense'), o['timing'].update(settle=True)))
accepted_case('wrong_predecessor_shape', lambda o: o['predecessor'].update(seq='not-an-int', close_sha256='bad'))
for name in ('nested_instrument_answer_bits', 'nested_init_parameters_answer_bits', 'wrong_instrument_variant',
             'empty_complete_steps', 'invalid_complete_preinit_sample', 'wrong_step_kind_and_timing', 'wrong_predecessor_shape'):
    assert out[name]['accepted'], out[name]

ordered = json.loads(json.dumps(base, sort_keys=True))
out['same_O_after_sorted_JSON_roundtrip'] = {'findings': rec.validate_observation(ordered),
    'same_canonical_digest': rec.observation_sha256(base) == rec.observation_sha256(ordered)}
assert out['same_O_after_sorted_JSON_roundtrip']['findings']
assert out['same_O_after_sorted_JSON_roundtrip']['same_canonical_digest']
try:
    rec.validate_observation([])
except Exception as e:
    out['malformed_O_list'] = {'exception': type(e).__name__ + ': ' + str(e)}
else:
    raise AssertionError('expected current uncaught exception')

f = rec.fitness(base, 'a' * 64, [(0, 0)], [1], [1])
f['fitness'] = True
out['boolean_fitness'] = {'findings': rec.validate_fitness(f, base)}
assert out['boolean_fitness']['findings'] == []
truncated_f = rec.fitness(base, 'a' * 64, [(0, 0), (0, 1)], [1], [1])
out['short_target_silently_truncates_mask'] = {'mask_cells': 2, 'target_cells': 1, 'fitness': truncated_f['fitness']}
assert truncated_f['fitness'] == 1
x = {'schema': rec.SCHEMA_X, 'schema_version': rec.VERSION, 'observation_sha256': rec.observation_sha256(base), 'seq': 1,
     'cleanup': {'steps': [], 'final_q': [None] * 8, 'answer_bits': [1]},
     'base_readback_sha256': 'b' * 64, 'base_state_sample': [None] * 8, 'idle_status': 0, 'status': 'closed'}
out['closed_X_with_null_samples_nonidle_and_extra_key'] = {'findings': rec.validate_close(x, base)}
assert out['closed_X_with_null_samples_nonidle_and_extra_key']['findings'] == []
out['session_open_with_missing_digest_values'] = {'findings': rec.validate_session_open({
    'schema': rec.SCHEMA_SO, 'schema_version': rec.VERSION, 'instrument': {},
    'startup_readback_sha256': None, 'base_frames_reference_sha256': None, 'status': 'open'})}
assert out['session_open_with_missing_digest_values']['findings'] == []

flow = rec.transactions(rec.load_trace(root / 'sim/b4/out/flow.jsonl'))
tx = flow[1]
cut = next(i for i, e in enumerate(tx) if e.get('op') == 'wr' and e.get('addr') == 0x2000 and e.get('data') == 0x2000)
before_close = tx[:cut]
obs = rec.observation(before_close, LINKS, TIMING, seq=2, session='bench', predecessor=ROOT)
premature = rec.transaction_close(before_close, obs, seq=2, links=LINKS)
out['producer_seals_X_before_CLOSE'] = {'status': premature['status'], 'idle_status': premature['idle_status'],
    'findings': rec.validate_close(premature, obs), 'CLOSE_present_in_trace': rec._ctrl(before_close, 'close')}
assert premature['status'] == 'closed' and not premature['idle_status']
assert rec.validate_close(premature, obs) == [] and not rec._ctrl(before_close, 'close')

events = rec.load_trace(root / 'sim/b4/out/fault_realisable.jsonl')
o = rec.observation(events, LINKS, TIMING, seq=1, session='bench', predecessor=ROOT)
issued = rec._steps_issued(events)
out['rejected_step_removed_from_O_stimulus'] = {
    'attempted_set_steps': len(issued), 'O_set_steps_in_stimulus': len(o['stimulus']) - 1,
    'retained_observation_steps_including_init': len(o['steps']), 'fault': o['fault'],
    'rejected_word': issued[-1], 'last_O_stimulus': o['stimulus'][-1]}
assert len(issued) == 3 and len(o['stimulus']) == 3  # only two set steps retained in the declared stimulus
no_return_events = rec.load_trace(root / 'sim/b4/out/fault_not_armed.jsonl')
o2 = rec.observation(no_return_events, LINKS, TIMING, seq=1, session='bench', predecessor=ROOT)
out['before_any_sample_fault_still_has_fabricated_init_step'] = {'status': o2['status'], 'fault': o2['fault'],
    'steps': o2['steps'], 'initial_present': 'initial' in o2}
assert o2['status'] == 'invalid' and o2['steps'][0]['q_after'] is None

(D / 'record_findings.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
