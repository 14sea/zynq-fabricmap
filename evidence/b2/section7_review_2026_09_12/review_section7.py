"""Offline Section 7 checks. No production manifest, ruling or image is written."""
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path('/home/test/zynq_fabricmap')
sys.path[:0] = [str(ROOT / 'host'), str(ROOT / 'tests')]
import b2_manifest as bm
import b2_build_evidence as be
import b2_test_report as report
import test_b1_carrier as carrier_test
import test_b2_session as session_test
import b2_session as session

def sha(p): return hashlib.sha256(Path(p).read_bytes()).hexdigest()

def function(source, name):
    match = re.search(r'^static [^;{}]*?\b' + name + r'\([^;{}]*?\)\s*\{', source, re.M)
    assert match, name
    start = match.end() - 1
    tokens = re.finditer(r'"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|/\*[\s\S]*?\*/|//[^\n]*|[{}]', source[start:])
    depth = 0
    for token in tokens:
        if token[0] == '{': depth += 1
        elif token[0] == '}':
            depth -= 1
            if depth == 0: return source[match.start():start + token.end()]
    raise AssertionError(name)

out = {'head': report.git('rev-parse', 'HEAD'), 'snapshot_before_review_files': report.snapshot()}
b1 = (ROOT / 'firmware/b1/b1_app.c').read_text()
b2 = (ROOT / 'firmware/b2/b2_app.c').read_text()
names = ['axi_readable', 'axi_writable', 'axi_read', 'axi_write', 'pl_nonce',
         'settle_condition', 'arm_attempt', 'devcfg_wait_done', 'devcfg_dma',
         'stage_streams', 'link2_witness', 'write_envelopes', 'readback_frame',
         'link3_witness', 'audit_word', 'serve_sparse_chunk', 'audit_pull',
         'kick_watchdog', 'tx_run_line', 'emit_record', 'closing_unsigned_control', 'emit_summary']
out['b1_identical_functions'] = {name: function(b1, name) == function(b2, name) for name in names}
assert all(out['b1_identical_functions'].values()), out['b1_identical_functions']

suite = unittest.TestSuite()
for obj in vars(carrier_test).values():
    if isinstance(obj, type) and issubclass(obj, unittest.TestCase) and hasattr(obj, 'app_offsets'):
        klass = obj
for name in ('test_read_allowlist_within_rtl_and_variant_present',
             'test_write_allowlist_within_rtl_and_only_the_key_window_beyond'):
    suite.addTest(klass(name))
defines = {m[1]: int(m[2], 16) for m in re.finditer(r'#define (P3_\w+) (0x[0-9A-Fa-f]+)u', b2)}
log = io.StringIO()
with patch.object(carrier_test, 'APP', b2), patch.object(klass, 'DEFINES', defines):
    result = unittest.TextTestRunner(stream=log).run(suite)
out['b2_allowlist_against_b1_rtl'] = log.getvalue()
assert result.wasSuccessful()

ev = json.loads((ROOT / 'evidence/b2/build_evidence.json').read_text())
out['build_findings'] = be.verify_findings(ev)
assert not out['build_findings']
out['artifact_sha256'] = {p: sha(ROOT / p) for p in (
    'firmware/b2/bsp/out/b2_app.bin', 'firmware/b2/bsp/out/b2_app.elf',
    'evidence/b2/build_evidence.json', 'manifests/b1_manifest.json',
    'manifests/b2_instrument_pins.json', 'evidence/b2/b2q_plan.json',
    'evidence/b2/b2q_prediction.json', 'docs/b2_preregistration.md')}
m = json.loads(bm.render(bm.init(ROOT / 'evidence/b2/build_evidence.json')))
out['s0_verification'] = bm.verify(m)
out['s0_preview_sha256'] = bm.manifest_sha256(m)
out['s0_preview'] = m
assert out['s0_verification']['stage'] == 'S0'
assert not m['prereg']['frozen'] and not m['image']['board_ready']
assert not (ROOT / 'manifests/b2_manifest.json').exists()

plan = json.loads((ROOT / 'evidence/b2/b2q_plan.json').read_text())
got = session_test.drive(plan['seed_derivation']['master_seed'], 8, 1, 0, 1)
ref = session.run(plan['seed_derivation']['master_seed'], 8, 1, 0, 1,
                  session_test.FAB, session_test.VIEW, truth=session_test.TRUTH,
                  masks=session_test.MASKS, pair_seeds=[tuple(x) for x in plan['seed_derivation']['pairs']])
assert len(got['cands']) == len(ref.candidates) == 20
for c, r in zip(got['cands'], ref.candidates):
    assert (c['seq'], c['is_baseline'], c['pair'], c['arm'], c['holdout'], c['genome'], c['block']) == (
        r.seq, r.is_baseline, r.pair, r.arm, r.holdout, r.genome, r.block), r.seq
out['b2q_c_twin'] = {'records': 20, 'all_candidate_and_block_fields_equal': True,
                     'pair_seeds': plan['seed_derivation']['pairs'], 'silicon_evidence': False}

p = ROOT / 'evidence/b2/tests/test_report_2026-09-12T134616Z.json'
d = json.loads(p.read_text())
out['submitted_report'] = {k: d[k] for k in ('head_at_run', 'ran', 'skipped', 'failures', 'errors', 'clean_tree_proof')}
out['submitted_report']['recomputed_refusals'] = report.proof_refusals(d)
out['submitted_report']['endpoints_equal_except_time'] = (
    {k: v for k, v in d['run']['start'].items() if k != 'at'} ==
    {k: v for k, v in d['run']['end'].items() if k != 'at'})
assert out['submitted_report']['endpoints_equal_except_time']
out['submitted_report']['artifact_matches'] = {}
for path, expected in d['run']['start']['artifacts_sha256'].items():
    p = subprocess.run(['git', '-C', str(ROOT), 'show', d['head_at_run'] + ':' + path], capture_output=True)
    actual = hashlib.sha256(p.stdout).hexdigest() if p.returncode == 0 else None
    out['submitted_report']['artifact_matches'][path] = actual == expected
assert all(out['submitted_report']['artifact_matches'].values())
assert not out['submitted_report']['recomputed_refusals']
print(json.dumps(out, indent=2, sort_keys=True))
