"""Section 2.3 operator's stop: reads of committed files and git state only. No seed derived, no seed value printed."""
import sys, subprocess, pathlib, hashlib, datetime
R = pathlib.Path('/home/test/zynq_fabricmap'); sys.path.insert(0, str(R / 'b4/host'))
import b4_seeds as bs
AUTH_HEAD = 'a243ee8'; BASELINE = '00336d0'
head = subprocess.run(['git','-C',str(R),'rev-parse','HEAD'],capture_output=True,text=True).stdout.strip()
porcelain = subprocess.run(['git','-C',str(R),'status','--porcelain'],capture_output=True,text=True).stdout
tool_diff = subprocess.run(['git','-C',str(R),'diff','--stat',BASELINE,'HEAD','--','b4/'],capture_output=True,text=True).stdout
ok = []
def chk(name, cond, detail):
    ok.append(cond); print(f"[{'OK' if cond else 'DIFF'}] {name}: {detail}")
print("UTC", datetime.datetime.now(datetime.timezone.utc).isoformat())
chk("HEAD == execution HEAD", head.startswith(AUTH_HEAD), head)
chk("clean tree", porcelain == '', repr(porcelain) if porcelain else 'git status --porcelain empty')
chk(f"b4/ bytes identical to baseline {BASELINE}", tool_diff.strip() == '', tool_diff.strip() or 'git diff --stat empty')
rec = bs.read_exposure_receipt(R)
chk("receipt sha", rec.sha256 == bs.EXPOSURE_RECEIPT_SHA256 and rec.sha256.startswith('68764bbc1a51ec25'), rec.sha256)
chk("receipt count 66", len(rec.values) == 66 == bs.pinned_receipt_count(), f"len={len(rec.values)} pinned={bs.pinned_receipt_count()}")
regs, note = bs.sim_registry(R)
print("   registry note:", note)
for r in regs: print(f"   registry entry: dir={r.dir} status={r.status} seeds_sha256={r.seeds_sha256} count={len(r.values)}")
chk("registry exactly one b4-sim-3", len(regs) == 1 and regs[0].dir.endswith('b4-sim-3_20261019T121833Z') and regs[0].status == 'seeds'
    and (regs[0].seeds_sha256 or '').startswith('1a0d1e7b91132ed6') and len(regs[0].values) == 65, f"{len(regs)} entries")
ex = bs.load_exclusion_set(R)
chk("pooled exclusion 2224", len(ex.values) == 2224, f"pooled_total={len(ex.values)}")
print("ALL CHECKS PASS — run may start" if all(ok) else "STOP — a difference was found; the run does not start")
sys.exit(0 if all(ok) else 1)
