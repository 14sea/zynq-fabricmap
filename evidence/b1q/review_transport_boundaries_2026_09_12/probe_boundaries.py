"""Offline public-API review probes for 38c91b0. No physical ports or state changes.

Run with python3 -B from the repository root. Prints original observations;
assertions are limited to the positive controls and the deterministic fixtures.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'host'))
import transport_rig as rig

frames = rig.plan_frames('boundary-review', 0)
out = {'provenance': rig.provenance()}
clean = rig.analyse(frames, rig.stream_bytes(frames))
assert clean['clean'] and clean['losses'] == 0
out['positive_stream'] = {k: clean[k] for k in ('clean', 'losses', 'frames_delivered')}

# A writer can have accepted bytes before an internal exception. Compatibility
# fallback must not retry an operation with observable effects.
calls = []
accepted = bytearray()
def writer(data, timeout=None):
    calls.append(timeout)
    accepted.extend(data)
    if len(calls) == 1:
        raise TypeError('internal writer failure after accepting bytes')
    return len(data)
port = rig.callable_port('side-effecting writer', writer, lambda t: b'', takes_timeout=True)
try:
    n = port.write(b'abc', 0.25)
    out['typeerror_writer'] = {'returned_count': n, 'exception': None}
except Exception as exc:
    out['typeerror_writer'] = {'exception': type(exc).__name__ + ': ' + str(exc)}
out['typeerror_writer'].update({'timeouts_received': calls, 'actual_bytes_accepted': accepted.decode()})

# Same single corrupted complete line, under normal completion versus cutoff.
# This frame was fully accepted for transmission, and a whole damaged line arrived.
one = frames[:1]
bad = bytearray(one[0].line)
bad[60] ^= 1
for censor in (False, True):
    r = rig.analyse(one, bytes(bad), censor_tail=censor)
    out['crc_with_cutoff' if censor else 'crc_without_cutoff'] = {
        k: r[k] for k in ('losses', 'censored', 'missing', 'defects_by_kind', 'bytes_received')}
out['truly_in_flight_control'] = {
    k: v for k, v in rig.analyse(one, b'', censor_tail=True).items()
    if k in ('losses', 'censored', 'defects_by_kind')}

def loopback(damage_first=0):
    state = {'queued': bytearray(), 'writes': 0}
    def write(data, timeout=None):
        state['writes'] += 1
        if state['writes'] <= damage_first:
            data = bytearray(data)
            data[50] ^= 1
        state['queued'].extend(data)
        return len(data)
    def read(timeout):
        data = bytes(state['queued'])
        state['queued'].clear()
        return data
    return rig.callable_port('memory loopback', write, read, takes_timeout=True), state

def summary(r):
    return {k: r.get(k) for k in ('repetitions_run', 'stopped', 'losses', 'denominator_bytes',
                                 'losses_per_100k_bytes', 'completed_exposure', 'incomplete',
                                 'error', 'export_complete', 'repetition_results')}

with tempfile.TemporaryDirectory(prefix='rig_boundary_review_') as temp:
    temp = Path(temp)
    p, _ = loopback()
    positive = rig.Run('positive', repetitions=2, tx_during_rx=False).execute(
        p, out_dir=temp / 'positive', sleep=lambda t: None)
    assert positive['completed_exposure'] and positive['losses'] == 0
    out['positive_run'] = summary(positive)

    p, state = loopback(damage_first=3)
    stopped = rig.Run('three losses', repetitions=200, tx_during_rx=False).execute(
        p, out_dir=temp / 'stopped', sleep=lambda t: None)
    out['stop_loss_run'] = {'actual_source_writes': state['writes'], 'requested_repetitions': 200,
                            'persisted': summary(json.loads((temp / 'stopped/run.json').read_text()))}

    p, state = loopback()
    with patch.object(rig, 'analyse', side_effect=ValueError('injected analyser failure')):
        try:
            failed = rig.Run('analysis unavailable', repetitions=2, tx_during_rx=False).execute(
                p, out_dir=temp / 'analysis_failure', sleep=lambda t: None)
            exception = None
        except rig.RigError as exc:
            failed = exc.result
            exception = str(exc)
    out['analyser_failure'] = {'actual_source_writes': state['writes'], 'exception': exception,
                               'persisted': summary(json.loads((temp / 'analysis_failure/run.json').read_text()))}

    # Cut off only while draining after all source writes have completed; all data
    # are withheld to represent accepted bytes that are still in flight at cutoff.
    now = [0.0]
    def last_write(data, timeout=None):
        if b' TERM ' in data:
            now[0] = 1.0
        return len(data)
    p = rig.callable_port('all accepted before cutoff', last_write, lambda t: b'', takes_timeout=True)
    cut = rig.Run('drain cutoff', repetitions=2, seconds=1.0, tx_during_rx=False).execute(
        p, out_dir=temp / 'cutoff', sleep=lambda t: None, clock=lambda: now[0])
    out['all_writes_then_cutoff'] = summary(cut)

print(json.dumps(out, indent=2, sort_keys=True))
