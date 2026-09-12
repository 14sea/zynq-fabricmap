"""Offline review at 146e60a; no physical device, production state or ruling is used.

Run with python3 -B from the repository root. Output records observations, not
assertions that require defective behavior to persist after a correction.
"""
import json
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'host'))
import transport_rig as rig

frames = rig.plan_frames('review', 0)
wire = rig.stream_bytes(frames)
echo = rig.host_schedule(frames)[0]['line']
def brief(r):
    return {k: r[k] for k in ('clean', 'frames_delivered', 'losses', 'host_echo_lines',
                               'defects_by_kind', 'bytes_received', 'divergence')}
out = {'provenance': rig.provenance(), 'positive_control': brief(rig.analyse(frames, wire))}
out['missing_final_newline'] = brief(rig.analyse(frames, wire[:-1]))
out['one_expected_echo_positive'] = brief(rig.analyse(frames, wire + echo, echo_lines=[echo]))
out['duplicate_echo'] = brief(rig.analyse(frames, wire + echo * 100, echo_lines=[echo]))
out['unsent_blank_lines_with_echo'] = brief(rig.analyse(frames, wire + b'\n' * 100 + echo, echo_lines=[echo]))

def local_port(fail=False):
    state = {'buffer': b'', 'writes': 0, 'accepted_bytes': 0, 'read_bytes': 0, 'reads': 0}
    def write(data):
        state['writes'] += 1
        state['accepted_bytes'] += len(data)
        state['buffer'] += data
        return len(data)
    def read(timeout):
        state['reads'] += 1
        if fail and state['reads'] == 2:
            raise OSError('primary synthetic detach')
        b, state['buffer'] = state['buffer'], b''
        state['read_bytes'] += len(b)
        return b
    return rig.callable_port('memory loopback', write, read), state

with tempfile.TemporaryDirectory(prefix='review_driver_') as temp:
    temp = Path(temp)
    # Observe a clean source/capture with a fake bounded clock. Source reads consume
    # exactly the requested timeout, showing whether subsequent writes obey expiry.
    now, events, pending = [0.0], [], [b'']
    def write(data):
        events.append({'op': 'write', 't': now[0], 'source': data.startswith(b'P3L5 '), 'bytes': len(data)})
        pending[0] += data
        return len(data)
    def read(timeout):
        events.append({'op': 'read', 't': now[0], 'timeout': timeout})
        now[0] += timeout
        b, pending[0] = pending[0], b''
        return b
    p = rig.callable_port('timed loopback', write, read)
    bounded = rig.Run('deadline', repetitions=1, seconds=0.01, run_id='review').execute(
        p, out_dir=temp / 'deadline', clock=lambda: now[0],
        sleep=lambda t: now.__setitem__(0, now[0] + t))
    out['deadline'] = {'events': events, 'elapsed': now[0], 'result': bounded}

    p, state = local_port(fail=True)
    try:
        rig.Run('detach', repetitions=1, tx_during_rx=False, run_id='review').execute(
            p, out_dir=temp / 'detach', sleep=lambda _: None)
    except rig.RigError as exc:
        on_disk = json.loads((temp / 'detach/run.json').read_text())
        out['partial_detach'] = {'actual': {k: v for k, v in state.items() if k != 'buffer'}, 'result': on_disk,
                                 'raw_capture_bytes': (temp / 'detach/capture_000.bin').stat().st_size,
                                 'error': str(exc)}

    # A writable output directory with just one component failing must not prevent
    # independent evidence components or the final status from being attempted.
    original = Path.write_text
    def failing_event_file(path, data, *args, **kwargs):
        if path.name == 'events_000.json':
            raise OSError('injected events write failure')
        return original(path, data, *args, **kwargs)
    for fail in (False, True):
        p, state = local_port(fail=fail)
        directory = temp / ('export_error_with_detach' if fail else 'export_error_clean')
        with patch.object(Path, 'write_text', failing_event_file):
            try:
                result = rig.Run('export', repetitions=1, tx_during_rx=False, run_id='review').execute(
                    p, out_dir=directory, sleep=lambda _: None)
                error = None
            except rig.RigError as exc:
                result, error = exc.result, str(exc)
        out[directory.name] = {'result': result, 'exception': error,
                              'files': sorted(f.name for f in directory.iterdir())}

    # Real filesystem failure during provenance collection, without changing a file:
    # patch the read of the framing module, after a separate primary transport error.
    original_bytes = Path.read_bytes
    framing = Path(rig.l5.__file__)
    def inaccessible_framing(path):
        if path == framing:
            raise OSError('injected provenance read failure')
        return original_bytes(path)
    p, _ = local_port(fail=True)
    directory = temp / 'provenance_error'
    with patch.object(Path, 'read_bytes', inaccessible_framing):
        try:
            rig.Run('provenance', repetitions=1, tx_during_rx=False).execute(
                p, out_dir=directory, sleep=lambda _: None)
        except Exception as exc:
            out['provenance_error'] = {'type': type(exc).__name__, 'error': str(exc),
                                      'has_result': getattr(exc, 'result', None) is not None,
                                      'directory_exists': directory.exists()}

# Probe the intended physical transport construction without importing/opening serial.
class SerialDouble:
    def __init__(self, *args, **kwargs):
        out['serial_constructor'] = {'args': args, 'kwargs': kwargs}
    def write(self, data):
        return len(data)
    def read(self, size):
        return b''
    def fileno(self):
        return 123
with patch.dict(sys.modules, {'serial': type('FakeSerialModule', (), {'Serial': SerialDouble})}):
    rig.serial_port('OFFLINE-NOT-A-DEVICE')

# A paced source has finished its last frame before any host command begins.
now, source_busy_until, host_checks = [0.0], [0.0], []
def source_write(data):
    source_busy_until[0] = now[0] + len(data) * rig.BYTE_TIME_S
    return len(data)
def host_write(data):
    host_checks.append({'time': now[0], 'source_busy_until': source_busy_until[0],
                        'overlap': now[0] < source_busy_until[0]})
    return len(data)
source = rig.callable_port('source', source_write, lambda t: b'')
host = rig.callable_port('host', host_write, lambda t: b'')
rep = rig.Repetition(index=0, frames=frames)
rig.Driver(source, host, source, pace=True, sleep=lambda t: now.__setitem__(0, now[0] + t),
           clock=lambda: now[0]).run(rep, 1e6)
out['paced_overlap'] = {'host_writes': len(host_checks),
                        'host_writes_during_source_rx': sum(c['overlap'] for c in host_checks)}

# Source and host scheduled-frame lengths, inspected without a hardware run.
timeline = json.loads((ROOT / rig.TIMELINE_SOURCE).read_text())
out['timeline_frame_example'] = next(f for f in timeline['frames'] if f['dir'] == 'tx')
out['host_schedule_lengths'] = {'min': min(len(s['line']) for s in rig.host_schedule(frames)),
                                'max': max(len(s['line']) for s in rig.host_schedule(frames))}
print(json.dumps(out, indent=2, sort_keys=True))
