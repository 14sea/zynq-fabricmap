"""Offline reporter review. Synthetic executions are test inputs, not suite evidence."""
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else '/home/test/zynq_fabricmap').resolve()
sys.path.insert(0, str(ROOT / 'host'))
import b2_test_report as tr

archived = json.loads((ROOT / 'evidence/b2/tests/test_report_2026-09-12T092150Z.json').read_text())
GOOD = 'Ran 4 tests in 1.000s\n\nOK\n'
# Use the archived schema-2 snapshots so this reproduction remains runnable after
# the review itself makes the working tree dirty. These are controlled API inputs.
def run(log=GOOD):
    r = copy.deepcopy(archived['run'])
    r['log'] = log
    return r

def outcome(r):
    try:
        rep = tr.build(r)
        return {'proof': rep['clean_tree_proof'], 'refusals': rep['proof_refusals']}
    except Exception as exc:
        return {'exception': type(exc).__name__, 'message': str(exc)}

out = {'head': tr.git('rev-parse', 'HEAD'), 'synthetic_inputs_not_actual_runs': True}
out['positive'] = outcome(run())
assert out['positive']['proof']
logs = {
    'truncated_after_in': 'Ran 4 tests in \n\nOK\n',
    'nonnumeric_duration': 'Ran 4 tests in nonsense\n\nOK\n',
    'contradictory_results': 'Ran 4 tests in 1.000s\nFAILED (failures=1)\nOK\n',
    'duplicate_ok': 'Ran 4 tests in 1.000s\nOK\nOK\n',
    'result_before_run': 'OK\nRan 4 tests in 1.000s\n',
}
out['remaining_log_gaps'] = {k: outcome(run(v)) for k, v in logs.items()}
old = {
    'missing_result': 'Ran 4 tests in 1.000s\n',
    'bare_failed': 'Ran 4 tests in 1.000s\nFAILED\n',
    'zero_tests': 'Ran 0 tests in 1.000s\nOK\n',
    'truncated': 'Ran 4\nOK\n',
    'unknown_skips': 'Ran 4 tests in 1.000s\nOK (skipped=unknown)\n',
    'two_runs': GOOD + GOOD,
}
out['old_log_controls'] = {k: outcome(run(v)) for k, v in old.items()}
assert all(not r['proof'] for r in out['old_log_controls'].values())
out['malformed_log'] = {name: outcome(run(value)) for name, value in
                        [('null', None), ('array', []), ('integer', 7), ('object', {})]}
out['legacy_null_log'] = outcome((0, None))
out['malformed_snapshots'] = {}
for field in ('instrument', 'pins'):
    r = run()
    r['start'][field] = ['wrong shape']
    out['malformed_snapshots'][field] = outcome(r)

events = []
start = copy.deepcopy(archived['run']['start'])
end = copy.deepcopy(archived['run']['end'])
def snap(root):
    events.append('snapshot')
    return copy.deepcopy(start if len(events) == 1 else end)
def execute(*args, **kwargs):
    events.append('execute')
    return subprocess.CompletedProcess(args[0], 0, GOOD, '')
with patch.object(tr, 'snapshot', side_effect=snap), patch.object(tr.subprocess, 'run', side_effect=execute):
    observed = tr.run_suite()
out['snapshot_order'] = events
assert events == ['snapshot', 'execute', 'snapshot']
out['provenance_controls'] = {}
for name in ('dirty_start', 'head_moved', 'not_executed'):
    r = run()
    if name == 'dirty_start': r['start']['worktree_dirty'] = True
    elif name == 'head_moved': r['end']['head'] = '0' * 40
    else: r['executed'] = False
    out['provenance_controls'][name] = outcome(r)
assert all(not r['proof'] for r in out['provenance_controls'].values())

with tempfile.TemporaryDirectory() as td:
    temp = Path(td)
    log = temp / 'log.txt'
    log.write_text(GOOD)
    file = temp / 'file'
    file.write_text('not a directory')
    cases = {
        'no_run': ['--no-run', '--log', str(log), '--exit-status', '0', '--out-dir', str(temp / 'report')],
        'missing_parameters': ['--no-run'],
        'missing_log': ['--no-run', '--log', str(temp / 'absent'), '--exit-status', '0'],
        'output_is_file': ['--no-run', '--log', str(log), '--exit-status', '0', '--out-dir', str(file)],
    }
    out['cli'] = {}
    for name, args in cases.items():
        p = subprocess.run([sys.executable, str(ROOT / 'host/b2_test_report.py'), *args], capture_output=True, text=True)
        out['cli'][name] = {'rc': p.returncode, 'stdout': p.stdout, 'stderr': p.stderr}
        assert p.returncode == (0 if name == 'no_run' else 3)
        assert 'Traceback' not in p.stderr
    assert not json.loads(next((temp / 'report').glob('*.json')).read_text())['clean_tree_proof']

checks = {}
for path, expected in archived['run']['start']['artifacts_sha256'].items():
    p = subprocess.run(['git', '-C', str(ROOT), 'show', archived['head_at_run'] + ':' + path], capture_output=True)
    actual = hashlib.sha256(p.stdout).hexdigest() if p.returncode == 0 else None
    checks[path] = actual == expected
out['historical_artifact_matches'] = checks
out['archived_proof_recomputed'] = tr.proof_refusals(archived)
out['archived_endpoint_equality_except_time'] = ({k: v for k, v in archived['run']['start'].items() if k != 'at'} ==
                                               {k: v for k, v in archived['run']['end'].items() if k != 'at'})
assert all(checks.values())

# Remove each condition only in an in-memory module and run the unchanged tests.
spec = importlib.util.spec_from_file_location('review_report_tests', ROOT / 'tests/test_b2_test_report.py')
tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(tests)
source = (ROOT / 'host/b2_test_report.py').read_text()
conditions = {
    'worktree_clean': 'if snap.get("worktree_dirty") is not False:',
    'result_line': 'if log["result_line"] != "OK":',
    'executed': 'if not run.get("executed"):',
    'head_stability': 'if start.get("head") != end.get("head"):',
}
out['predicate_mutations'] = {}
for name, condition in conditions.items():
    assert source.count(condition) == 1
    mutant = types.ModuleType('review_mutant_' + name)
    mutant.__file__ = str(ROOT / 'host/b2_test_report.py')
    exec(compile(source.replace(condition, 'if False:'), mutant.__file__, 'exec'), mutant.__dict__)
    stream = io.StringIO()
    with patch.object(tests, 'tr', mutant):
        result = unittest.TextTestRunner(stream=stream).run(unittest.defaultTestLoader.loadTestsFromModule(tests))
    out['predicate_mutations'][name] = {'ran': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors)}
    assert result.failures or result.errors

print(json.dumps(out, indent=2, sort_keys=True))
