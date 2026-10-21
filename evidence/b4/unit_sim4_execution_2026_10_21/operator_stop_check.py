"""docs/b4_sim4_execution_plan.md section 2.3 — the operator's stop, against the owner's execution ruling of 2026-10-21
(build/wip/owner_review_495cc36_2026_10_21/README.md, section 3). Reads of committed files, git state and the tool's constants only.
No seed is derived or printed (master_seed / pair_seeds are never called); no pre-flight, smoke or batch runs here.
Exit 0 = every row equal, the run may start; exit 1 = a difference, the run does not start, nothing is repaired."""
import sys, subprocess, pathlib, hashlib, datetime, json, shutil
R = pathlib.Path('/home/test/zynq_fabricmap'); sys.path.insert(0, str(R / 'b4/host'))
import b4_seeds as bs, b4_protocol as bp, b4_thresholds as th
AUTH_HEAD = '495cc360c97aba58bda959a2e867e6b43dbf4f7f'   # the execution HEAD the ruling names
BASELINE = '21db2de'                                       # the accepted tool baseline (owner PASS 2026-10-21)
BRANCH = 'b4-sim-4-execution'
START_DATES = (datetime.date(2026, 10, 21), datetime.date(2026, 10, 22))   # the corrected ruling (2026-10-21): either UTC day
PROTOCOL_SHA = '2f096d4adbd83e0ec6350e6da2942cc862e99df4e81539719fa7261dad5a258c'
IMPORT_SHA = 'a6af67efd18d47829a91f6041a53b98a240d2d16802cda8f45f233f7fbe91b4e'
RECEIPT_SHA = '68764bbc1a51ec2506bf9d9bcbb3f55f88f3d7642b5eb46c6fd3dd39f8dae146'
REGISTRY = {'evidence/b4/sim/b4-sim-3_20261019T121833Z': ('seeds', '1a0d1e7b91132ed6814a9e369e23f2c55f28886448fa5efd55d722182f50b17d', 65),
            'evidence/b4/sim/b4-gate-1_20261020T102526Z': ('seeds', '785e76988d4e6ec49cfb86b7b896358b484e5899d48700ee1bcfffd6e034bced', 401)}
git = lambda *a: subprocess.run(['git', '-C', str(R), *a], capture_output=True, text=True).stdout
sha = lambda p: hashlib.sha256(pathlib.Path(p).read_bytes()).hexdigest()
ok = []
def chk(name, cond, detail):
    ok.append(bool(cond)); print(f"[{'OK' if cond else 'DIFF'}] {name}: {detail}")
now = datetime.datetime.now(datetime.timezone.utc)
print('UTC', now.isoformat())
chk('date is 2026-10-21 or 2026-10-22 UTC (the corrected ruling)', now.date() in START_DATES, now.date().isoformat())
head = git('rev-parse', 'HEAD').strip(); branch = git('rev-parse', '--abbrev-ref', 'HEAD').strip()
chk('HEAD == execution HEAD', head == AUTH_HEAD, head)
chk(f'branch == {BRANCH}', branch == BRANCH, branch)
chk('main untouched (a243ee8)', git('rev-parse', 'main').strip().startswith('a243ee8'), git('rev-parse', 'main').strip())
por = git('status', '--porcelain', '--untracked-files=all')
chk('clean tree (porcelain, untracked=all)', por == '', repr(por) if por else 'empty')
td = git('diff', '--stat', BASELINE, 'HEAD', '--', 'b4/').strip()
chk(f'b4/ bytes identical to baseline {BASELINE}', td == '', td or 'git diff --stat empty')
imp = json.loads((R / 'b4/IMPORT.json').read_text())
chk('IMPORT.json 59 entries, sha a6af67ef…', len(imp['files']) == 59 and sha(R / 'b4/IMPORT.json') == IMPORT_SHA, f"{len(imp['files'])} {sha(R / 'b4/IMPORT.json')}")
ic = subprocess.run([sys.executable, '-B', str(R / 'evidence/b4/unit_2b4a_repair_2026_10_18/import_check.py')], capture_output=True, text=True, cwd=str(R))
print('   import_check:', ' | '.join(ic.stdout.strip().splitlines()))
chk('import_check all equal, no untabled file', ic.returncode == 0 and 'all equal: True' in ic.stdout and 'without an entry: none' in ic.stdout, f'exit {ic.returncode}')
ident = bp.identity(R)
chk('protocol_sha256', bp.protocol_sha256(ident) == PROTOCOL_SHA, bp.protocol_sha256(ident))
print('   architecture_revision', ident['architecture_revision'], '(informational)')
chk('labels', bs.EXPLORATION_LABEL == 'b4-sim-4' and bs.GATE_LABEL == 'b4-gate-2' and sorted(bs.RETIRED_LABELS) == ['b4-sim-1', 'b4-sim-2'] and sorted(bs.CONSUMED_LABELS) == ['b4-gate-1', 'b4-sim-3'],
    f"exploration {bs.EXPLORATION_LABEL} gate {bs.GATE_LABEL} retired {sorted(bs.RETIRED_LABELS)} consumed {sorted(bs.CONSUMED_LABELS)}")
g = th.THRESHOLDS['gonogo']
chk('gonogo policy S 32 / B_go 64 / alpha 0.2 / K9 min 0.5', g['S'] == 32 and g['B_go'] == 64 and g['alpha_go'] == 0.2 and g['k9_conditional_medians_min'] == 0.5, json.dumps(g, sort_keys=True))
rec = bs.read_exposure_receipt(R)
chk('receipt sha 68764bbc…', rec.sha256 == RECEIPT_SHA == bs.EXPOSURE_RECEIPT_SHA256, rec.sha256)
chk('receipt 66 values, pinned 66', len(rec.values) == 66 == bs.pinned_receipt_count(), f'len={len(rec.values)} pinned={bs.pinned_receipt_count()}')
regs, note = bs.sim_registry(R); print('   registry note:', note)
seen = {}
for r in regs:
    print(f'   registry entry: dir={r.dir} status={r.status} seeds_sha256={r.seeds_sha256} count={len(r.values)}'); seen[str(r.dir)] = (r.status, r.seeds_sha256, len(r.values))
chk('registry exactly the two named directories / status / digests / counts', seen == REGISTRY, f'{len(regs)} entries')
simdir = sorted(x.name for x in (R / 'evidence/b4/sim').iterdir())
chk('evidence/b4/sim/ holds nothing else', simdir == ['b4-gate-1_20261020T102526Z', 'b4-sim-3_20261019T121833Z'], simdir)
ex = bs.load_exclusion_set(R)
chk('pooled exclusion 2625 values, 38 historical sources', len(ex.values) == 2625 and len(ex.sources) == 38, f'{len(ex.values)} values, {len(ex.sources)} sources')
chk('evidence/b4/gonogo/ absent', not (R / 'evidence/b4/gonogo').exists(), 'absent' if not (R / 'evidence/b4/gonogo').exists() else 'EXISTS')
chk('no b4-sim-4 output directory exists', not list((R / 'evidence/b4/sim').glob('b4-sim-4_*')), 'none')
free = shutil.disk_usage(str(R)).free; chk('disk >= 2 GB free', free >= 2e9, f'{free / 1e9:.1f} GB')
procs = subprocess.run(['pgrep', '-af', 'b4_sim|b4_gate|b4_gonogo|b4_sim_verify'], capture_output=True, text=True).stdout
procs = '\n'.join(l for l in procs.splitlines() if 'pgrep' not in l and 'operator_stop_check' not in l)
chk('no competing b4 process', procs == '', procs or 'none')
print('seed derivation called: NO (master_seed / pair_seeds not invoked)')
print('ALL CHECKS PASS — the run may start' if all(ok) else 'STOP — a difference was found; the run does not start; nothing is repaired')
sys.exit(0 if all(ok) else 1)
