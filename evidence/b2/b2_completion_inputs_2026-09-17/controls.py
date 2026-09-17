#!/usr/bin/env python3
"""B2 completion inputs — the controls. One positive run of restore_verify.py under `env -i`
(PATH only) in a fresh detached checkout of BASE, and the negative controls: an archive missing
one member (with the original manifest, then with the outer digest patched to match so the
per-member check is the one that refuses), an archive with one byte changed (same two forms), a
target that already holds one of the files, and a target whose HEAD is not BASE. Every run's
command, environment, exit code, stdout JSON and stderr are written to runs/. Throwaway worktrees
live under the scratch directory given as argv[1] and are removed. The main tree is not touched.

    controls.py <scratch dir>
"""
from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
RUNS = HERE / "runs"
BASE = "73b68d79fd43fc032c178da73dda2b2c95764db8"
OTHER = "4800c15"                                  # main before the B2 merge: a checkout that is NOT the base
PATH_ONLY = "/usr/local/bin:/usr/bin:/bin"


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def worktree(scratch: Path, name: str, rev: str) -> Path:
    wt = scratch / "wt" / f"cinp_{name}"
    if wt.exists():
        subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO)
    subprocess.run(["git", "worktree", "add", "--detach", str(wt), rev], cwd=REPO, check=True, capture_output=True,
                   env=dict(os.environ, GIT_LFS_SKIP_SMUDGE="1"))
    return wt


def drop(wt: Path):
    subprocess.run(["git", "worktree", "remove", "--force", str(wt)], cwd=REPO, check=True)


def restore(name: str, wt: Path, archive: Path, manifest: Path, env: dict, expect_rc: int, expect_needle: str) -> dict:
    cmd = ["env", "-i"] + [f"{k}={v}" for k, v in env.items()] + [sys.executable, "-B", str(HERE / "restore_verify.py"),
                                                                    "--target", str(wt), "--archive", str(archive), "--manifest", str(manifest)]
    t0 = time.time()
    p = subprocess.run(cmd, capture_output=True, text=True)
    try:
        js = json.loads(p.stdout.strip().splitlines()[0]) if p.returncode else json.loads(p.stdout)
    except (ValueError, IndexError):
        js = {"unparsed_stdout": p.stdout[-800:]}
    rec = {"name": name, "cmd": cmd, "env": env, "rc": p.returncode, "seconds": round(time.time() - t0, 1),
           "stdout_json": js, "stderr": p.stderr.strip().splitlines()[-3:],
           "expected": {"rc": expect_rc, "needle": expect_needle},
           "met": p.returncode == expect_rc and expect_needle in (p.stdout + p.stderr)}
    (RUNS / f"{name}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    print(f"[{'ok' if rec['met'] else 'UNEXPECTED'}] {name}: rc {p.returncode} — {(p.stderr.strip().splitlines() or [''])[-1][:150]}")
    return rec


def tampered(kind: str, scratch: Path) -> tuple[Path, Path]:
    """An archive missing one member / with one byte changed, plus a manifest whose OUTER digest is
    patched to match it (so only the per-member checks can refuse)."""
    zst = (HERE / "inputs.tar.zst").read_bytes()
    raw = subprocess.run(["zstd", "-dc"], input=zst, capture_output=True, check=True).stdout
    src = tarfile.open(fileobj=io.BytesIO(raw), mode="r:")
    buf = io.BytesIO()
    victim = "vivado/carrier/generated/clockInfo.txt"
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as dst:
        for m in src.getmembers():
            data = src.extractfile(m).read()
            if m.name == victim:
                if kind == "missing":
                    continue
                data = bytes([data[0] ^ 0x01]) + data[1:]          # one byte changed, same size
            ti = tarfile.TarInfo(m.name)
            ti.size, ti.mtime, ti.mode = len(data), 0, 0o644
            dst.addfile(ti, io.BytesIO(data))
    out_zst = subprocess.run(["zstd", "-19", "-q", "-c"], input=buf.getvalue(), capture_output=True, check=True).stdout
    d = scratch / "cinp_tampered"
    d.mkdir(parents=True, exist_ok=True)
    a = d / f"inputs_{kind}.tar.zst"
    a.write_bytes(out_zst)
    doc = json.loads((HERE / "archive.json").read_text())
    doc["archive_sha256"] = sha256(out_zst)
    mp = d / f"archive_{kind}_outer_patched.json"
    mp.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    return a, mp


def main(scratch: Path) -> int:
    RUNS.mkdir(exist_ok=True)
    orig_a, orig_m = HERE / "inputs.tar.zst", HERE / "archive.json"
    recs = []
    # positive, env -i with PATH only, fresh detached checkout of BASE
    wt = worktree(scratch, "positive", BASE)
    recs.append(restore("positive_env_i", wt, orig_a, orig_m, {"PATH": PATH_ONLY}, 0, "OK: restored 15 files"))
    # N3 on the same checkout: every file now exists -> refuse to overwrite, nothing written
    recs.append(restore("neg_target_already_holds_the_files", wt, orig_a, orig_m, {"PATH": PATH_ONLY}, 2, "refuses to overwrite"))
    drop(wt)
    # N1 / N2
    for kind, needle_inner in (("missing", "archive members are not exactly the 15 listed: missing ['vivado/carrier/generated/clockInfo.txt']"),
                               ("onebyte", "archive member vivado/carrier/generated/clockInfo.txt: 365 bytes sha256")):
        a, mp = tampered(kind, scratch)
        wt = worktree(scratch, f"{kind}_orig", BASE)
        recs.append(restore(f"neg_{kind}_member_original_manifest", wt, a, orig_m, {"PATH": PATH_ONLY}, 2, "archive sha256"))
        drop(wt)
        wt = worktree(scratch, f"{kind}_patched", BASE)
        recs.append(restore(f"neg_{kind}_member_outer_digest_patched", wt, a, mp, {"PATH": PATH_ONLY}, 2, needle_inner))
        drop(wt)
    # N4: a checkout that is not the base
    wt = worktree(scratch, "otherhead", OTHER)
    recs.append(restore("neg_target_head_is_not_base", wt, orig_a, orig_m, {"PATH": PATH_ONLY}, 2, "is not the base"))
    drop(wt)
    subprocess.run(["git", "worktree", "prune"], cwd=REPO)
    summary = {"at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "base": BASE,
               "archive_sha256": sha256(orig_a.read_bytes()), "manifest_sha256": sha256(orig_m.read_bytes()),
               "runs": [{k: r[k] for k in ("name", "rc", "met", "seconds")} for r in recs],
               "all_met": all(r["met"] for r in recs),
               "worktrees_after": subprocess.run(["git", "worktree", "list"], cwd=REPO, capture_output=True, text=True).stdout,
               "main_tree_status_porcelain": subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout}
    (RUNS / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(f"{sum(r['met'] for r in recs)}/{len(recs)} controls met")
    return 0 if summary["all_met"] else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
