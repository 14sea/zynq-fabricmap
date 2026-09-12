"""Offline production-Run check of unresolved damage versus confirmed loss counts.

No serial device or production state is touched. Run with python3 -B from the
repository root; results are printed for comparison after correction.
"""
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'host'))
import transport_rig as rig

out = {'provenance': rig.provenance(), 'cases': {}}
with tempfile.TemporaryDirectory(prefix='rig_uncertainty_review_') as temp:
    for name in ('intact', 'known_crc_damage', 'unidentifiable_damage', 'silence'):
        now, queued = [0.0], [b'']
        def write(data, timeout=None):
            if name == 'intact':
                queued[0] += data
            elif name == 'known_crc_damage':
                changed = bytearray(data)
                changed[60] ^= 1
                queued[0] += changed
            elif name == 'unidentifiable_damage':
                queued[0] += b'garbled\n'
            return len(data)
        def read(timeout):
            now[0] += timeout
            data, queued[0] = queued[0], b''
            return data
        port = rig.callable_port('offline double', write, read, takes_timeout=True)
        directory = Path(temp) / name
        run = rig.Run(name, repetitions=200, seconds=0.01, tx_during_rx=False, run_id='review')
        result = run.execute(port, clock=lambda: now[0], out_dir=directory,
                             sleep=lambda t: now.__setitem__(0, now[0] + t))
        persisted = json.loads((directory / 'run.json').read_text())
        out['cases'][name] = {'returned': result, 'persisted': persisted,
                              'capture_hex': (directory / 'capture_000.bin').read_bytes().hex()}
print(json.dumps(out, indent=2, sort_keys=True))
