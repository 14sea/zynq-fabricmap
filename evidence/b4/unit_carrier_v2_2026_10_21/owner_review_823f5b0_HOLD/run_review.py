"""Isolated owner review of committed carrier sources. No board, production task, pair seed or write to tracked source."""
from pathlib import Path
import hashlib
import io
import json
import subprocess
import tarfile
import tempfile
import datetime

R = Path('/home/test/zynq_fabricmap')
D = Path(__file__).resolve().parent

def git(*a):
    return subprocess.check_output(['git', *a], cwd=R, text=True).strip()

HEAD = git('rev-parse', 'HEAD')
assert HEAD.startswith('823f5b0')
(D / 'status_before.txt').write_text(git('status', '--short', '--branch') + '\n')
snapshot = Path(tempfile.mkdtemp(prefix='owner_carrier_823f5b0_'))
paths = ['rtl/b4', 'rtl/b1/p3_siphash.v', 'tb/b4', 'sim/b4/run.sh', 'host/claimb_r1p_instrument.py',
         'host/b4carrier_manifest.py', 'host/b4carrier_records.py', 'host/b4carrier_regmap.py',
         'tests/__init__.py', 'tests/test_b4carrier_regmap.py', 'tests/test_b4carrier_records.py', 'tests/test_b4carrier_benches.py',
         'manifests/claimb_round1prime_manifest.json', 'manifests/claimb_round1prime_instrument_pins.json',
         'b4/host/b4_ff_mapping.py', 'b4/host/b4_ff_hypothesis.py', 'b4/host/b4_ff_model.py', 'b4/hypothesis',
         'gate_runs/run_2026_08_05_ff/certificate.json', 'docs/ff_latch_probe.md',
         'evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json']
tracked = set(subprocess.check_output(['git', 'ls-files'], cwd=R, text=True).splitlines())
paths = [p for p in paths if p in tracked or any(s.startswith(p + '/') for s in tracked)]
archive = subprocess.check_output(['git', 'archive', HEAD, '--', *paths], cwd=R)
with tarfile.open(fileobj=io.BytesIO(archive)) as tf:
    tf.extractall(snapshot, filter='data')
(D / 'snapshot.json').write_text(json.dumps({'head': HEAD, 'temporary_root': str(snapshot), 'paths': paths,
    'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
    'initial_files_sha256': {str(p.relative_to(snapshot)): hashlib.sha256(p.read_bytes()).hexdigest()
                             for p in snapshot.rglob('*') if p.is_file()}}, indent=2) + '\n')
p = subprocess.run(['python3', '-B', '-m', 'unittest', 'tests.test_b4carrier_regmap', 'tests.test_b4carrier_records',
                    'tests.test_b4carrier_benches'], cwd=snapshot, text=True, capture_output=True, timeout=120)
(D / 'host_tests.txt').write_text(p.stdout + p.stderr)
assert p.returncode == 0, p.stdout + p.stderr
assert 'Ran 20 tests' in p.stderr and 'skipped' not in p.stderr
assert (snapshot / 'tb/b4/b4_fixture.vh').read_bytes() == (R / 'tb/b4/b4_fixture.vh').read_bytes()
out = {'head': HEAD, 'temporary_root': str(snapshot), 'host_tests': 20, 'host_test_exit': p.returncode,
       'baseline_bench_results': {f.stem: f.read_text().strip() for f in (snapshot / 'sim/b4/out').glob('*.result')},
       'generated_fixture_byte_identical': True}
assert len(out['baseline_bench_results']) == 13  # twelve core runs plus unisim; SipHash is in captured runner stdout
(D / 'baseline_checks.json').write_text(json.dumps(out, indent=2) + '\n')
print(json.dumps(out, indent=2))
