#!/usr/bin/env python3
"""Test real runtime-resolution caching against changes to temporary runtime copies.

The only toolchain double redirects -print-file-name results to copied runtime objects.
It does not replace hashing, verification, caching, dependency discovery or test bodies.
No repository or instrument inputs are changed.
"""
import copy
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import b2_build_evidence as be

spec = importlib.util.spec_from_file_location('submitted', R / 'tests/test_b2_build_evidence.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
base = json.loads((R / 'evidence/b2/build_evidence.json').read_text())
real_run = subprocess.run

def committed(ev):
    with patch.object(tests.Committed, 'setUpClass', classmethod(lambda cls: None)):
        tests.Committed.ev = ev
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(tests.Committed).run(result)
    return {'passed': result.wasSuccessful(), 'ran': result.testsRun, 'skips': len(result.skipped),
            'failures': [str(t) for t, _ in result.failures],
            'errors': [str(t) for t, _ in result.errors]}

out = {}
for mode in ('same_size_overwrite', 'delete'):
    with tempfile.TemporaryDirectory(prefix='b2-runtime-cache-') as tmp:
        tmp = Path(tmp)
        ev = copy.deepcopy(base)
        for name, record in ev['bsp_inputs']['toolchain_objects'].items():
            shutil.copyfile(record['path'], tmp / name)
            record['path'] = str(tmp / name)
        def resolve_copies(args, **kwargs):
            flag = next((a for a in args if a.startswith('-print-file-name=')), None)
            if flag:
                return SimpleNamespace(returncode=0, stdout=str(tmp / flag.split('=', 1)[1]) + '\n', stderr='')
            return real_run(args, **kwargs)
        with patch.object(be.subprocess, 'run', side_effect=resolve_copies):
            be._RESOLVED_RUNTIME = None
            before = be.verify_findings(ev, R)
            before_tests = committed(ev)
            victim = tmp / 'crti.o'
            if mode == 'delete':
                victim.unlink()
            else:
                data = bytearray(victim.read_bytes())
                data[-1] ^= 1
                victim.write_bytes(data)
            warm = be.verify_findings(ev, R)
            warm_tests = committed(ev)
            be._RESOLVED_RUNTIME = None
            cold = be.verify_findings(ev, R)
            out[mode] = {'before': before, 'before_committed': before_tests,
                         'warm_after': warm, 'warm_committed_after': warm_tests,
                         'after_cache_reset': cold}
be._RESOLVED_RUNTIME = None
print(json.dumps(out, indent=2))
