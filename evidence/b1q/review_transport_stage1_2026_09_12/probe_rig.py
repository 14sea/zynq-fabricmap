"""Offline review probes. No serial device, production manifest or ruling is touched.

Run from the repository root: python3 -B evidence/b1q/review_transport_stage1_2026_09_12/probe_rig.py
Print observations rather than assertions of the defective answers, so fixes can be compared.
"""
import base64
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'host'))
import transport_rig as rig

frames = rig.plan_frames()
wire = rig.stream_bytes(frames)
rec = next(f for f in frames if f.kind == 'REC')
hb = next(f for f in frames if f.kind == 'HB')

def brief(result):
    return {k: result[k] for k in ('clean', 'frames_delivered', 'missing', 'losses',
                                  'bytes_received', 'divergence')}

def run_with(data, **kwargs):
    return rig.Run('offline probe', **kwargs).execute(lambda b: len(b), lambda: data,
                                                     sleep=lambda _: None)

out = {'tool_sha256': rig.self_sha256(), 'positive_control': brief(rig.analyse(frames, wire))}
damaged = bytearray(wire)
for f in (rec, hb):
    damaged[f.offset + 20] ^= 1
one = bytearray(wire)
one[rec.offset + 20] ^= 1
out['one_corrupted_frame'] = brief(rig.analyse(frames, bytes(one)))
out['two_corrupted_frames_run'] = run_with(bytes(damaged), repetitions=2, tx_during_rx=False)
out['silence_run'] = run_with(b'', repetitions=1, tx_during_rx=False)

# Keep the known index, change the pad, then build a correct CRC for the foreign bytes.
parsed = rig.l5.parse_line(rec.line.decode())
payload = bytearray(base64.urlsafe_b64decode(parsed['payload']))
payload[-1] ^= 1
foreign = rig.l5.build_line(rec.kind, rec.seq, rig.TOKEN,
                           base64.urlsafe_b64encode(payload).decode()).encode()
replacement = wire[:rec.offset] + foreign + wire[rec.offset + rec.bytes:]
out['foreign_payload_known_index'] = brief(rig.analyse(frames, replacement))

# Exact bytes from repetition 1 are replayed for repetition 2.
writes = []
replayed = rig.Run('stale repetition', repetitions=2, tx_during_rx=False).execute(
    lambda data: writes.append(data), lambda: wire, sleep=lambda _: None)
out['repetition_replay'] = {'both_writes_equal': writes[0] == writes[1],
                           'results_clean': [r['clean'] for r in replayed['repetition_results']]}

# Trace the production driver with a transport double: no hidden pump or filtering.
events = []
now = [0.0]
def write(data):
    events.append({'operation': 'write', 'time': now[0], 'bytes': len(data),
                   'kind': 'source stream' if data.startswith(b'P3L5 ') else 'host command'})
    return len(data)
def sleep(seconds):
    now[0] += seconds
def read():
    events.append({'operation': 'read', 'time': now[0]})
    return wire
timed = rig.Run('trace', repetitions=1, seconds=0.1).execute(write, read, sleep=sleep, clock=lambda: now[0])
out['driver_trace'] = {'events': events, 'stopped': timed['stopped'],
                       'elapsed': now[0], 'declared_limit': 0.1,
                       'host_command_counts': dict(Counter(s['line'].split()[0] for s in rig.host_sends(frames)))}
out['short_write_ignored'] = rig.Run('short write', repetitions=1, tx_during_rx=False).execute(
    lambda data: 0, lambda: wire, sleep=lambda _: None)['repetition_results'][0]['clean']

# Error after successful capture of one repetition; check final counter sampling/result.
counter_calls = []
reads = [wire]
failed = rig.Run('detach', repetitions=2, tx_during_rx=False)
def detach_read():
    if reads:
        return reads.pop()
    raise OSError('synthetic detach')
with patch.object(rig, 'read_icounters', side_effect=lambda fd: counter_calls.append(fd) or
                  {'available': False, 'reason': 'offline double'}):
    try:
        failed.execute(lambda data: len(data), detach_read, fd=123, sleep=lambda _: None)
    except rig.RigError as exc:
        out['error_path'] = {'error': str(exc), 'counter_samples': len(counter_calls),
                             'completed_results_in_memory': len(failed.results),
                             'returned_result': False}

# A newline is not sufficient evidence of resynchronisation to a known valid frame.
insert_at = rec.offset + 100
inserted = wire[:insert_at] + b'\n' + wire[insert_at:]
out['inserted_newline'] = brief(rig.analyse(frames, inserted))

import b2_manifest as bm
import b2_runner as rn
m = json.loads((ROOT / 'manifests/b2_manifest.json').read_text())
out['b2_verify'] = bm.verify(m)
out['b2q_expected_frames'] = rn.qualification_session_plan(m)['expected_frames']
out['bindings'] = {p: hashlib.sha256((ROOT / p).read_bytes()).hexdigest() for p in
                   ('manifests/b2_manifest.json', 'manifests/b2_instrument_pins.json',
                    'docs/b2_preregistration.md')}
print(json.dumps(out, indent=2, sort_keys=True))
