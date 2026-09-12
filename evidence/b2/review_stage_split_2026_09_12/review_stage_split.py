"""Offline test-readiness probe using explicitly stubbed qualification evidence."""
import json
from pathlib import Path
import sys
from unittest.mock import patch

ROOT = Path('/home/test/zynq_fabricmap')
sys.path[:0] = [str(ROOT / 'host'), str(ROOT / 'tests')]
import b2_manifest as bm
import test_b2_runner as tests

out = {'qualification_is_stubbed_not_silicon': True, 'cases': []}
for rate in (2807.0, 602.0, 4490.86, 6000.0):
    # Use the same documented fixture seam as StageCoverage. No production function changes.
    with patch.object(tests, 'STUB_RATE', rate):
        f = tests.Fixture('S3')
    try:
        verified = bm.verify(f.manifest, readjudicate=f.stub)
        assert verified['stage'] == 'S3' and verified['qualified']
        path = f.path()
        result = tests.StageCoverage().drive(path)
        split = f.plan_doc['session_split']
        out['cases'].append({'rate': rate, 'stage': verified['stage'],
            'first_slice_pairs': split['sessions'][0]['pairs'],
            'ran': result.testsRun, 'failures': len(result.failures),
            'errors': len(result.errors), 'skipped': len(result.skipped),
            'details': [s for _, s in result.failures + result.errors]})
    finally:
        f.close()
assert out['cases'][0]['failures'] == out['cases'][0]['errors'] == 0
assert all(c['failures'] == 1 and c['errors'] == 0 for c in out['cases'][1:])
print(json.dumps(out, indent=2))
