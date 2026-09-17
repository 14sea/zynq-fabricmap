#!/usr/bin/env python3
"""Fresh restore and production re-judge of this session's archived evidence.

Run from the repository root:  python3 -B evidence/b2/b2_17A6_2026-09-16-01/restore_rejudge.py
It (1) creates an EMPTY temporary directory, (2) extracts the archive's five members into it,
(3) copies the ten ordinary files listed in archive.json, (4) requires the file set to be exactly
those fifteen, (5) checks every file's size and sha256 against archive.json, (6) puts BOTH
instrument import paths (PSORACLE_ROOT and PSORACLE_ROOT/host) on sys.path and runs the
production b2_runner.judge_session over the restored directory, requiring the result to equal the
stored adjudication.json key for key. Exit status 0 only if every step holds. Read-only on the
repository; the temporary directory is left in place and its path printed."""
from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys, tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
os.chdir(ROOT)
doc = json.loads((HERE / "archive.json").read_text())
members = {m["name"]: m for m in doc["archive"]["members"]}
ordinary = {m["name"]: m for m in doc["ordinary_files"]}
want = {**members, **ordinary}
assert len(members) == 5 and len(ordinary) == 10 and len(want) == 15, "archive.json does not list 5 + 10 files"
sha = lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest()
archive = HERE / doc["archive"]["path"]
assert archive.stat().st_size == doc["archive"]["bytes"] and sha(archive) == doc["archive"]["sha256"], "exports.tar.zst does not match archive.json"

T = Path(tempfile.mkdtemp(prefix="b2_s1_fresh_restore_"))           # (1) empty
assert not any(T.iterdir())
subprocess.run(f"zstd -dc {archive} | tar -xf - -C {T}", shell=True, check=True)     # (2)
for name in ordinary:                                                # (3)
    shutil.copy2(HERE / name, T / name)
present = sorted(p.name for p in T.iterdir())
assert present == sorted(want), f"restored file set is not exactly the 15: extra {sorted(set(present)-set(want))}, missing {sorted(set(want)-set(present))}"   # (4)
for name, m in want.items():                                         # (5)
    p = T / name
    assert p.stat().st_size == m["bytes"], f"{name}: size {p.stat().st_size} != {m['bytes']}"
    assert sha(p) == m["sha256"], f"{name}: sha256 differs"
print(f"restored 15/15 into {T}: sizes and sha256 equal archive.json")

psoracle = Path(os.environ.get("PSORACLE_ROOT", "/home/test/zynq_psoracle"))
for p in (ROOT / "host", ROOT / "tests", psoracle, psoracle / "host"):       # (6) both instrument paths
    sys.path.insert(0, str(p))
import b2_runner as rn  # noqa: E402
manifest = json.loads((T / "manifest_at_run.json").read_text())
session_plan = json.loads((T / "summary.json").read_text())["l6"]           # the session plan the runner saved
plan_doc = json.loads((ROOT / "evidence/b2/plan.json").read_text())
prediction_doc = json.loads((ROOT / "evidence/b2/prediction.json").read_text())
assert sha(ROOT / "evidence/b2/plan.json") == manifest["plan"]["sha256"], "evidence/b2/plan.json is not the plan this session's manifest pins"
verdict = rn.judge_session(T, manifest, session_plan, plan_doc, prediction_doc, None, psoracle)
stored = json.loads((T / "adjudication.json").read_text())
diff = sorted(k for k in set(verdict) | set(stored) if verdict.get(k) != stored.get(k))
print("re-judge:", verdict["outcome"], "rate", verdict["measured_rate_per_hour"], "findings", verdict["findings"], "kills", verdict["kills"])
assert not diff, f"re-judge differs from the stored adjudication in {diff}"
print("re-judge equals adjudication.json key for key; restored directory left at", T)
