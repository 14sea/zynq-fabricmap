"""Offline S0 review: a temporary S1 preview, never a production freeze."""
import copy
import hashlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path('/home/test/zynq_fabricmap')
sys.path[:0] = [str(ROOT / 'host'), str(ROOT / 'tests')]
import b2_manifest as bm
import b2_runner as rn
import test_b2_runner as tests

path = ROOT / 'manifests/b2_manifest.json'
raw = path.read_bytes()
m = json.loads(raw)
digest = hashlib.sha256((ROOT / m['prereg']['path']).read_bytes()).hexdigest()
out = {'manifest_sha256': hashlib.sha256(raw).hexdigest(), 'prereg_sha256': digest,
       's0_verify': bm.verify(m), 'production_manifest_unchanged': None}

def run_test():
    stream = io.StringIO()
    suite = unittest.TestSuite([tests.RefusalOrder('test_the_committed_manifest_is_not_permission')])
    result = unittest.TextTestRunner(stream=stream).run(suite)
    return {'ran': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
            'skipped': len(result.skipped), 'output': stream.getvalue()}

out['s0_test'] = run_test()
assert out['s0_test']['failures'] == out['s0_test']['errors'] == 0
# Production freeze logic operates on a deep copy only; the actual S0 file is never written.
preview = bm.freeze(copy.deepcopy(m), digest)
out['s1_preview_verify'] = bm.verify(preview)
assert out['s1_preview_verify']['stage'] == 'S1'
with tempfile.TemporaryDirectory(prefix='b2_s0_review_') as td:
    p = Path(td) / 'manifest.json'
    p.write_text(bm.render(preview))
    # Only redirect the path read by the unchanged test. No preflight/verification double.
    with patch.object(rn, 'MANIFEST', p):
        out['s1_preview_test'] = run_test()
assert out['s1_preview_test']['failures'] == 1
assert out['s1_preview_test']['errors'] == 0
out['production_manifest_unchanged'] = path.read_bytes() == raw
assert out['production_manifest_unchanged']
print(json.dumps(out, indent=2, sort_keys=True))
