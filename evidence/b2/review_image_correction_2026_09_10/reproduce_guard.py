#!/usr/bin/env python3
"""Exercise the submitted BuildEvidence test class on isolated evidence mutations.

No repository evidence, firmware, image, toolchain or instrument file is changed.
ACCEPTED means the existing seven tests passed, not that this review accepts the data.
"""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
from unittest.mock import patch

R = Path(__file__).resolve().parents[3]
spec = importlib.util.spec_from_file_location('guard', R / 'tests/test_b2_build_evidence.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
original = json.loads(mod.EVIDENCE.read_text())

def remove_console(ev):
    ev['sources'].pop('bsp/src/console.c')
    ev['bsp_inputs']['translation_units'].pop(str(R / 'firmware/b2/bsp/src/console.c'))

def missing_unit(ev):
    tus = ev['bsp_inputs']['translation_units']
    key = next(k for k in tus if k.endswith('/xil_cache.c'))
    tus['/nonexistent-b2-review/xil_cache.c'] = tus.pop(key)

def header_hash(ev):
    key = next(k for k in ev['bsp_inputs']['headers'] if k.endswith('/stdint.h'))
    ev['bsp_inputs']['headers'][key] = '0' * 64

def remove_header(ev):
    key = next(k for k in ev['bsp_inputs']['headers'] if k.endswith('/stdint.h'))
    ev['bsp_inputs']['headers'].pop(key)

def runtime_hash(ev):
    ev['bsp_inputs']['toolchain_objects']['libc.a']['sha256'] = '0' * 64

def compiler_hash(ev):
    ev['toolchain']['gcc_sha256'] = '0' * 64

def second_build(ev):
    ev['reproducibility']['builds'][1]['bin_sha256'] = '0' * 64
    ev['reproducibility']['builds'][1]['elf_sha256'] = '1' * 64

def source_hash(ev):
    ev['sources']['b2_app.c'] = '0' * 64

def image_hash(ev):
    ev['image']['sha256'] = '0' * 64

def dirty(ev):
    ev['git']['worktree_dirty'] = True

results = {}
for name, mutate in [('baseline', lambda _: None), ('changed_app_hash_control', source_hash),
                     ('changed_image_hash_control', image_hash), ('dirty_tree_control', dirty),
                     ('mismatched_second_build', second_build), ('changed_header_hash', header_hash),
                     ('missing_header_entry', remove_header), ('changed_runtime_hash', runtime_hash),
                     ('changed_compiler_hash', compiler_hash), ('missing_external_unit', missing_unit),
                     ('unrecorded_console_source_and_unit', remove_console)]:
    ev = copy.deepcopy(original)
    mutate(ev)
    with patch.object(mod.BuildEvidence, 'setUpClass', classmethod(lambda cls: None)):
        mod.BuildEvidence.ev = ev
        suite = unittest.defaultTestLoader.loadTestsFromTestCase(mod.BuildEvidence)
        result = unittest.TestResult()
        suite.run(result)
    results[name] = {'verdict': 'ACCEPTED' if result.wasSuccessful() else 'REJECTED',
                     'ran': result.testsRun, 'skipped': len(result.skipped),
                     'failures': [str(t) for t, _ in result.failures],
                     'errors': [str(t) for t, _ in result.errors]}
print(json.dumps(results, indent=2))
