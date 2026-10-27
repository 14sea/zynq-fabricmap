"""docs/b4_sim5_execution_plan.md section 2.3 — the operator's stop, against the owner's execution ruling of 2026-10-27
(build/wip/owner_review_ae7fc35_2026_10_27/README.md, section 4). Reads of committed files, git state and the tool's constants only.
No seed is derived or printed (master_seed / pair_seeds are never called); no pre-flight, smoke or batch runs here.
Exit 0 = every row equal, the run may start; exit 1 = a difference, the run does not start, nothing is repaired."""
import sys, subprocess, pathlib, hashlib, datetime, json, shutil
R = pathlib.Path('/home/test/zynq_fabricmap'); sys.path.insert(0, str(R / 'b4/host'))
import b4_seeds as bs, b4_protocol as bp, b4_thresholds as th, b4_landscape as bl
AUTH_HEAD = 'ae7fc3547e1f9271a430b38ffee7fd469b89a7ee'   # the execution HEAD the ruling names
BASELINE = 'e20e12b'                                       # the accepted tool baseline (owner PASS 2026-10-27)
BRANCH = 'b4-sim-5-execution'                              # organisational (the ruling): recorded, a difference here is reported, not a stop
PROTOCOL_SHA = '5bba53c78d08f3ad32e41a90ef37d2639ea584e97fbf74996d941cec4fe14e7f'
IMPORT_SHA = '9de52e257e2b5c733118b097ffdb5ba69b941726b815bace302a6d1d8eecf02b'
RECEIPT_SHA = '68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146'
REGISTRY = {'evidence/b4/sim/b4-sim-3_20261019T121833Z': ('seeds', '1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d', 65),
            'evidence/b4/sim/b4-gate-1_20261020T102526Z': ('seeds', '785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced', 401),
            'evidence/b4/sim/b4-sim-4_20261021T065339Z': ('seeds', 'ae179c376282ae61f7057765a061105badee5e0d576a161af5fa43dd6c7e0296', 65)}
git = lambda *a: subprocess.run(['git', '-C', str(R), *a], capture_output=True, text=True).stdout
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ok = []
def chk(name, cond, detail):
    ok.append(bool(cond)); print(f"[{'OK' if cond else 'DIFF'}] {name}: {detail}")
now = datetime.datetime.now(datetime.timezone.utc)
print('UTC', now.isoformat(), '(no calendar-date gate in the ruling; recorded only)')
head = git('rev-parse', 'HEAD').strip(); branch = git('rev-parse', '--abbrev-ref', 'HEAD').strip()
chk('HEAD == execution HEAD', head == AUTH_HEAD, head)
print(f'   branch {branch} (proposed {BRANCH}; organisational, not a gate)')
chk('main untouched (a243ee8)', git('rev-parse', 'main').strip().startswith('a243ee8'), git('rev-parse', 'main').strip())
por = git('status', '--porcelain', '--untracked-files=all')
chk('clean tree (porcelain, untracked=all)', por == '', repr(por) if por else 'empty')
td = git('diff', '--stat', BASELINE, 'HEAD', '--', 'b4/').strip()
chk(f'b4/ bytes identical to baseline {BASELINE}', td == '', td or 'git diff --stat empty')
imp = json.loads((R / 'b4/IMPORT.json').read_text())
chk('IMPORT.json 59 entries, sha 9de52e25…', len(imp['files']) == 59 and sha(R / 'b4/IMPORT.json') == IMPORT_SHA, f"{len(imp['files'])} {sha(R / 'b4/IMPORT.json')}")
ic = subprocess.run([sys.executable, '-B', str(R / 'evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py')], capture_output=True, text=True, cwd=str(R))
print('   import_check:', ' | '.join(ic.stdout.strip().splitlines()))
chk('import_check all equal, no untabled file', ic.returncode == 0 and 'all equal: True' in ic.stdout and 'without an entry: none' in ic.stdout, f'exit {ic.returncode}')
ident = bp.identity(R)
chk('protocol_sha256', bp.protocol_sha256(ident) == PROTOCOL_SHA, bp.protocol_sha256(ident))
print('   architecture_revision', ident['architecture_revision'], '(informational)')
t = ident['task']
chk('identity task component (task-v0.3, ce 2, sr 4, broadcast {0:0,1:255})', t['version'] == 'task-v0.3' and t['ce_high_one_in'] == 2 and t['sr_high_one_in'] == 4 and t['broadcast'] == {'0': 0, '1': 255},
    json.dumps({k: t[k] for k in ('version', 'ce_high_one_in', 'sr_high_one_in', 'broadcast')}, sort_keys=True))
tb = th.THRESHOLDS['task']
chk('task constants (landscape + table)', bl.TASK_VERSION == 'task-v0.3' and bl.CE_HIGH_ONE_IN == 2 and bl.SR_HIGH_ONE_IN == 4 and bl.BROADCAST == {0: 0x00, 1: 0xFF}
    and tb['version'] == 'task-v0.3' and tb['stimulus']['draw_order'] == 'ce, sr, d' and tb['target_salt'] == 1413567047 and tb['setup_observations_per_pair'] == 2 and tb['ceilings'] == {'search': 64, 'holdout': 80},
    f"TASK_VERSION {bl.TASK_VERSION} CE {bl.CE_HIGH_ONE_IN} SR {bl.SR_HIGH_ONE_IN} BROADCAST {bl.BROADCAST} | table {tb['version']} order '{tb['stimulus']['draw_order']}' salt {tb['target_salt']} obs {tb['setup_observations_per_pair']} ceilings {tb['ceilings']}")
a = th.THRESHOLDS['anchor']
chk('labels', bs.EXPLORATION_LABEL == 'b4-sim-5' and bs.GATE_LABEL == 'b4-gate-2' and sorted(bs.RETIRED_LABELS) == ['b4-sim-1', 'b4-sim-2'] and sorted(bs.CONSUMED_LABELS) == ['b4-gate-1', 'b4-sim-3', 'b4-sim-4']
    and a['exploration_label'] == 'b4-sim-5' and a['gate_label'] == 'b4-gate-2' and sorted(a['consumed_labels']) == ['b4-gate-1', 'b4-sim-3', 'b4-sim-4'],
    f"exploration {bs.EXPLORATION_LABEL} gate {bs.GATE_LABEL} retired {sorted(bs.RETIRED_LABELS)} consumed {sorted(bs.CONSUMED_LABELS)}; table agrees")
g = th.THRESHOLDS['gonogo']
chk('gonogo policy S 32 / B_go 64 / p_max_go 0.2 (no alpha_go) / K9 min 0.5 / applies_to b4-sim-5', g['S'] == 32 and g['B_go'] == 64 and g['p_max_go'] == 0.2 and 'alpha_go' not in g and g['k9_conditional_medians_min'] == 0.5 and g['applies_to'].startswith('b4-sim-5'), json.dumps(g, sort_keys=True))
rec = bs.read_exposure_receipt(R)
chk('receipt sha 68764bbc…', rec.sha256 == RECEIPT_SHA == bs.EXPOSURE_RECEIPT_SHA256, rec.sha256)
chk('receipt 66 values, pinned 66', len(rec.values) == 66 == bs.pinned_receipt_count(), f'len={len(rec.values)} pinned={bs.pinned_receipt_count()}')
regs, note = bs.sim_registry(R); print('   registry note:', note)
seen = {}
for r in regs:
    print(f'   registry entry: dir={r.dir} status={r.status} seeds_sha256={r.seeds_sha256} count={len(r.values)}'); seen[str(r.dir)] = (r.status, r.seeds_sha256, len(r.values))
chk('registry exactly the three named directories / status / digests / counts', seen == REGISTRY, f'{len(regs)} entries')
simdir = sorted(x.name for x in (R / 'evidence/b4/sim').iterdir())
chk('evidence/b4/sim/ holds nothing else', simdir == ['b4-gate-1_20261020T102526Z', 'b4-sim-3_20261019T121833Z', 'b4-sim-4_20261021T065339Z'], simdir)
ex = bs.load_exclusion_set(R)
chk('pooled exclusion 2690 values, 38 historical sources', len(ex.values) == 2690 and len(ex.sources) == 38, f'{len(ex.values)} values, {len(ex.sources)} sources')
gg = sorted(x.name for x in (R / 'evidence/b4/gonogo').iterdir()) if (R / 'evidence/b4/gonogo').is_dir() else None
chk('evidence/b4/gonogo/ holds exactly b4-sim-4_20261021T065857Z', gg == ['b4-sim-4_20261021T065857Z'], gg)
chk('no b4-sim-5 output directory exists (sim / gonogo)', not list((R / 'evidence/b4/sim').glob('b4-sim-5_*')) and not list((R / 'evidence/b4/gonogo').glob('b4-sim-5_*')), 'none')
free = shutil.disk_usage(str(R)).free; chk('disk >= 2 GB free', free >= 2e9, f'{free / 1e9:.1f} GB')
procs = subprocess.run(['pgrep', '-af', 'b4_sim|b4_gate|b4_gonogo|b4_sim_verify'], capture_output=True, text=True).stdout
procs = '\n'.join(l for l in procs.splitlines() if 'pgrep' not in l and 'operator_stop_check' not in l)
chk('no competing b4 process', procs == '', procs or 'none')
print('seed derivation called: NO (master_seed / pair_seeds not invoked)')
print('ALL CHECKS PASS — the run may start' if all(ok) else 'STOP — a difference was found; the run does not start; nothing is repaired')
sys.exit(0 if all(ok) else 1)
