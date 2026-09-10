#!/usr/bin/env python3
"""Offline counterexamples against the build guard and its complete Committed suite.

Repository and instrument files remain unchanged. Temporary stand-in bytes are never run.
"""
import ast
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / 'host'))
import b2_build_evidence as be

spec = importlib.util.spec_from_file_location('submitted_guard_tests', R / 'tests/test_b2_build_evidence.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
base = json.loads((R / 'evidence/b2/build_evidence.json').read_text())

# Reuse all eleven original mutation/baseline definitions, without executing the obsolete
# test-class driver from the preceding review (the class has since been refactored).
old = ast.parse((R / 'evidence/b2/review_image_correction_2026_09_10/reproduce_guard.py').read_text())
scope = {'R': R}
exec(compile(ast.Module(body=[n for n in old.body if isinstance(n, ast.FunctionDef)], type_ignores=[]),
             '<archived review mutators>', 'exec'), scope)
old_cases = [('baseline', lambda _: None), ('changed_app_hash_control', scope['source_hash']),
             ('changed_image_hash_control', scope['image_hash']), ('dirty_tree_control', scope['dirty']),
             ('mismatched_second_build', scope['second_build']), ('changed_header_hash', scope['header_hash']),
             ('missing_header_entry', scope['remove_header']), ('changed_runtime_hash', scope['runtime_hash']),
             ('changed_compiler_hash', scope['compiler_hash']), ('missing_external_unit', scope['missing_unit']),
             ('unrecorded_console_source_and_unit', scope['remove_console'])]
out = {'previous_cases': {}, 'authority_cases': {}}
for name, mutate in old_cases:
    ev = copy.deepcopy(base)
    mutate(ev)
    findings = be.verify_findings(ev, R)
    out['previous_cases'][name] = {'findings': findings, 'accepted': not findings}

def committed_checks(ev):
    with patch.object(tests.Committed, 'setUpClass', classmethod(lambda cls: None)):
        tests.Committed.ev = ev
        result = unittest.TestResult()
        unittest.defaultTestLoader.loadTestsFromTestCase(tests.Committed).run(result)
    return {'passed': result.wasSuccessful(), 'ran': result.testsRun, 'skipped': len(result.skipped),
            'failures': [str(t) for t, _ in result.failures],
            'errors': [str(t) for t, _ in result.errors]}

with tempfile.TemporaryDirectory(prefix='b2-build-authority-') as tmp:
    tmp = Path(tmp)
    fakecc = tmp / 'bin/arm-none-eabi-gcc'
    fakecc.parent.mkdir()
    fakecc.write_bytes(b'Review-only stand-in, not a compiler and never executed.\n')

    def replace_compiler(ev):
        ev['toolchain']['path'] = str(tmp)
        ev['toolchain']['gcc_sha256'] = hashlib.sha256(fakecc.read_bytes()).hexdigest()

    def substitute_libc(ev):
        ev['bsp_inputs']['toolchain_objects']['libc.a'] = copy.deepcopy(ev['bsp_inputs']['toolchain_objects']['libm.a'])

    def remove_linker(ev):
        ev['sources'].pop('bsp/lscript.ld')

    def remove_build_script(ev):
        ev['sources'].pop('bsp/build.sh')

    def erase_dependencies(ev):
        ev['bsp_inputs']['headers'] = {}
        ev['bsp_inputs']['dependencies'] = {unit: [] for unit in ev['bsp_inputs']['translation_units']}

    for name, mutate in [('baseline', lambda _: None), ('different_file_as_compiler', replace_compiler),
                         ('libm_file_as_libc', substitute_libc), ('missing_linker_script_source', remove_linker),
                         ('missing_build_script_source', remove_build_script),
                         ('self_consistent_empty_graph_control', erase_dependencies)]:
        ev = copy.deepcopy(base)
        mutate(ev)
        out['authority_cases'][name] = {'findings': be.verify_findings(ev, R),
                                         'committed_checks': committed_checks(ev)}
print(json.dumps(out, indent=2))
