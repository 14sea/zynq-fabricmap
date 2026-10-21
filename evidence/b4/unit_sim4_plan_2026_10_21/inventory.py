#!/usr/bin/env python3
"""The read-only inventory of the b4-sim-4 execution-plan unit (docs/b4_sim4_execution_plan.md, section 2.3): reads of committed files,
git state and the tool's own constants. NO seed is derived or printed (b4_seeds.master_seed / pair_seeds are never called), nothing is
written outside this unit's directory, no batch, pre-flight, smoke or verifier of any production label runs."""
import datetime, hashlib, json, pathlib, shutil, subprocess, sys
R = pathlib.Path('/home/test/zynq_fabricmap'); sys.path.insert(0, str(R / 'b4/host'))
import b4_seeds as bs, b4_thresholds as th, b4_protocol as bp, b4_sim as sim  # noqa: E402
git = lambda *a: subprocess.run(['git', '-C', str(R), *a], capture_output=True, text=True).stdout
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
BASELINE = '21db2de'                                              # the accepted tool baseline (the owner's PASS of 2026-10-21)
print('UTC', datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
print('HEAD', git('rev-parse', 'HEAD').strip(), 'branch', git('rev-parse', '--abbrev-ref', 'HEAD').strip())
print('main', git('rev-parse', 'main').strip())
por = sim.porcelain(R)
print('porcelain entries', len(por), '(this unit\'s own untracked files, if any, listed):', [p for p in por][:10])
print(f'b4/ bytes vs baseline {BASELINE}: git diff --stat empty =', git('diff', '--stat', BASELINE, 'HEAD', '--', 'b4/').strip() == '')
ident = bp.identity(R)
print('protocol_sha256', bp.protocol_sha256(ident), '| architecture_revision', ident['architecture_revision'], '(informational, excluded from the digest)')
imp = json.loads((R / 'b4/IMPORT.json').read_text())
print('IMPORT.json entries', len(imp['files']), 'sha256', sha(R / 'b4/IMPORT.json'))
print('architecture document sha256', sha(R / 'docs/b4_architecture.md'), '(a root input recorded in the manifest, not pinned)')
print('labels: exploration', bs.EXPLORATION_LABEL, '| gate', bs.GATE_LABEL, '| retired', sorted(bs.RETIRED_LABELS), '| consumed', sorted(bs.CONSUMED_LABELS))
print('thresholds anchor labels', th.THRESHOLDS['anchor']['exploration_label'], th.THRESHOLDS['anchor']['gate_label'], '| hypothesis', th.THRESHOLDS['anchor']['hypothesis_sha256'])
print('gonogo policy', json.dumps(th.THRESHOLDS['gonogo'], sort_keys=True))
print('task block', json.dumps({k: th.THRESHOLDS['task'][k] for k in ('version', 'target_salt', 'setup_observations_per_pair', 'ceilings')}, sort_keys=True))
rec = bs.read_exposure_receipt(R)
print('exposure receipt', rec.sha256, 'values', len(rec.values), 'pinned', bs.EXPOSURE_RECEIPT_SHA256, 'pinned count', bs.pinned_receipt_count())
regs, note = bs.sim_registry(R)
print('registry note:', note)
for r in regs:
    print('  registry entry', r.dir, r.status, r.seeds_sha256, 'values', len(r.values))
ex = bs.load_exclusion_set(R)
print('pooled exclusion', len(ex.values), '| historical sources', len(ex.sources))
for d in ('evidence/b4/sim', 'evidence/b4/gate', 'evidence/b4/gonogo'):
    p = R / d
    print(d, 'exists' if p.exists() else 'DOES NOT EXIST', '| symlink' if p.is_symlink() else '', '| entries', sorted(x.name for x in p.iterdir()) if p.is_dir() else None)
for d in ('evidence/b4/sim/b4-sim-3_20261019T121833Z', 'evidence/b4/sim/b4-gate-1_20261020T102526Z'):
    files = [x for x in (R / d).rglob('*') if x.is_file()]
    rep = json.loads((R / d / 'sim_report.json').read_bytes())
    print(d, 'files', len(files), 'bytes', sum(x.stat().st_size for x in files), '| status', rep['status'], '| elapsed_s', rep['deadline']['elapsed_s'], 'of', rep['deadline']['seconds'])
u = shutil.disk_usage(str(R)); print('disk free GB', round(u.free / 1e9, 1), 'of', round(u.total / 1e9, 1))
print('seed derivation called: NO (master_seed / pair_seeds not invoked by this inventory)')
