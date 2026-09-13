"""Offline entry-point review. All ports and device identities are doubles.
Only temporary output directories are passed to the production CLI. No hardware access.
Run with python3 -B; output describes observed behavior, not link qualification.
"""
import contextlib
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'host'))
import transport_rig as rig

class FakePort:
    def __init__(self, mode='loop'):
        self.mode, self.buf, self.writes, self.reads, self.now = mode, bytearray(), [], 0, 0.0
    def fileno(self):
        return -1
    def write(self, data, timeout=None):
        self.writes.append(bytes(data))
        self.buf.extend(data)
        return len(data)
    def read(self, timeout):
        self.now += timeout
        self.reads += 1
        if self.mode == 'detach' and self.reads > 1:
            raise OSError('synthetic preflight detach after receiving the nonce')
        if self.mode == 'continuous':
            if self.now > 3.0:
                raise RuntimeError('probe watchdog: preflight still reading after 3 seconds')
            return b'background noise\n'
        if self.mode == 'silence':
            return b''
        out = bytes(self.buf)
        self.buf.clear()
        return out

identity = {'path': '/dev/FAKE', 'realpath': '/dev/FAKE', 'char_device': True,
            'rdev': '188:99', 'usb': {'idVendor': '1a86', 'idProduct': '7523'}}
original_preflight = rig.loopback_preflight

def invoke(directory, port, *, ident=None, extra=()):
    counter_calls = []
    def counters(fd):
        counter_calls.append(fd)
        return {'available': False, 'reason': 'offline fake fd'}
    output = io.StringIO()
    with patch.object(rig, 'serial_port', return_value=port), \
         patch.object(rig, 'device_identity', return_value=ident or identity), \
         patch.object(rig, 'read_icounters', side_effect=counters), \
         patch.object(rig, 'loopback_preflight', side_effect=lambda p: original_preflight(p, clock=lambda: p.now)), \
         patch.object(rig.time, 'sleep', return_value=None), contextlib.redirect_stdout(output):
        try:
            rc = rig.main(['run', '--device', '/dev/FAKE', '--label', 'offline-review',
                           '--out', str(directory), '--no-tx-during-rx', '--repetitions', '1', *extra])
            result = {'exit': rc}
        except Exception as exc:
            result = {'escaped_exception': type(exc).__name__ + ': ' + str(exc)}
    result.update(writes=len(port.writes), counter_calls=len(counter_calls),
                  fake_elapsed=port.now, files=sorted(p.name for p in directory.iterdir()),
                  stdout=output.getvalue().strip())
    if (directory / 'run.json').exists():
        try:
            run = json.loads((directory / 'run.json').read_text())
            result['run'] = {k: run.get(k) for k in ['frames_accepted', 'losses', 'completed_exposure', 'export_complete']}
        except ValueError:
            pass
    return result

results = {'head': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
           'tool_sha256': hashlib.sha256((ROOT/'host/transport_rig.py').read_bytes()).hexdigest(),
           'scope': 'offline CLI probes; no real device opened'}
with tempfile.TemporaryDirectory(prefix='rig_entry_review_') as temp:
    base=Path(temp)
    def directory(name):
        p=base/name
        p.mkdir()
        return p
    results['positive'] = invoke(directory('positive'), FakePort())
    results['silence_control'] = invoke(directory('silence'), FakePort('silence'))
    results['continuous_preflight'] = invoke(directory('continuous'), FakePort('continuous'))
    results['preflight_detach'] = invoke(directory('detach'), FakePort('detach'))
    old=directory('old')
    sentinels={'invocation.json': b'{"old": "invocation"}\n', 'run.json': b'{"old": "run"}\n',
               'capture_000.bin': b'old capture', 'capture_001.bin': b'old second capture'}
    for name,data in sentinels.items():
        (old/name).write_bytes(data)
    results['reuse_directory'] = invoke(old, FakePort())
    results['reuse_directory']['preserved_old_files'] = {name: (old/name).read_bytes()==data for name,data in sentinels.items()}
    wrong={**identity,'usb': {'idVendor':'0403','idProduct':'6001'}}
    results['wrong_usb_identity'] = invoke(directory('wrong_usb'), FakePort(), ident=wrong)
    results['zero_repetitions'] = invoke(directory('zero'), FakePort(), extra=('--repetitions','0'))

assert results['positive']['exit']==0 and results['positive']['run']['losses']==0
assert results['silence_control']['exit']==3 and results['silence_control']['writes']==1
assert 'watchdog' in results['continuous_preflight']['escaped_exception']
assert results['preflight_detach']['counter_calls']==1
assert results['preflight_detach']['files']==['invocation.json']
assert results['reuse_directory']['preserved_old_files']=={
    'invocation.json':False,'run.json':False,'capture_000.bin':False,'capture_001.bin':True}
assert results['wrong_usb_identity']['exit']==0
print(json.dumps(results,indent=2,sort_keys=True))
