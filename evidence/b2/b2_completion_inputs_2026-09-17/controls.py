#!/usr/bin/env python3
"""B2 completion inputs — the controls. One positive run of restore_verify.py under `env -i`
(PATH only) in a fresh detached checkout of BASE, and the negative controls: an archive missing
one member (with the original manifest, then with the outer digest patched to match so the
per-member check is the one that refuses), an archive with one byte changed (same two forms), a
target that already holds one of the files, and a target whose HEAD is not BASE. Every run's
command, environment, exit code, stdout JSON and stderr are written to control_runs/. Then the
producer's controls: in a restored checkout it must rebuild the archive byte-identically, and it must
refuse the owner's two counterexamples — a member drifted together with a B1 pin table re-pinned to
it, and the B1 image drifted together with a B1 manifest re-pinned to it (both "consistent" with
themselves, neither the completion state). Throwaway worktrees live under the scratch directory
given as argv[1] and are removed. The main tree is not touched.

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
RUNS = HERE / "control_runs"          # not `runs/`: .gitignore:6 ignores that name (the owner's P2 of 2026-09-17)
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


def drift_b1_table_and_member(wt: Path) -> str:
    """clockInfo.txt changed AND the B1 table re-pinned to the new digest: self-consistent, not the completion state."""
    rel = "vivado/carrier/generated/clockInfo.txt"
    (wt / rel).write_bytes((wt / rel).read_bytes() + b"# drifted\n")
    t = json.loads((wt / "manifests/b1_instrument_pins.json").read_text())
    t["files"][rel] = sha256((wt / rel).read_bytes())
    (wt / "manifests/b1_instrument_pins.json").write_text(json.dumps(t, indent=1, sort_keys=True) + "\n")
    return f"{rel} appended one line; manifests/b1_instrument_pins.json re-pinned to it"


def drift_b1_manifest_and_image(wt: Path) -> str:
    """b1_app.bin changed AND the B1 manifest re-pinned to the new digest."""
    rel = "firmware/b1/bsp/out/b1_app.bin"
    b = (wt / rel).read_bytes()
    (wt / rel).write_bytes(bytes([b[0] ^ 0x01]) + b[1:])
    m = json.loads((wt / "manifests/b1_manifest.json").read_text())
    m["image"]["sha256"] = sha256((wt / rel).read_bytes())
    (wt / "manifests/b1_manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True) + "\n")
    return f"{rel} one byte flipped; manifests/b1_manifest.json image.sha256 re-pinned to it"


def producer(name: str, scratch: Path, mutate, expect_rc: int, expect_needle: str) -> dict:
    """Run THIS directory's make_archive.py as checked out in a fresh worktree of BASE (so it reads
    the worktree), after restoring the 15 inputs from the committed archive and applying `mutate`."""
    wt = worktree(scratch, f"prod_{name[:24]}", BASE)
    pre = subprocess.run([sys.executable, "-B", str(HERE / "restore_verify.py"), "--target", str(wt), "--skip-verify"],
                         capture_output=True, text=True)
    if pre.returncode != 0:
        raise RuntimeError(f"the restore before the producer control failed: {pre.stderr[-300:]}")
    # the producer under test is the one in this commit, copied into the worktree's own directory
    here_in_wt = wt / HERE.relative_to(REPO)
    here_in_wt.mkdir(parents=True, exist_ok=True)
    (here_in_wt / "make_archive.py").write_bytes((HERE / "make_archive.py").read_bytes())
    mutation = mutate(wt) if mutate else "none"
    cmd = [sys.executable, "-B", str(here_in_wt / "make_archive.py")]
    p = subprocess.run(cmd, cwd=wt, capture_output=True, text=True)
    rec = {"name": name, "cmd": cmd, "worktree_head": subprocess.run(["git", "rev-parse", "HEAD"], cwd=wt, capture_output=True, text=True).stdout.strip(),
           "mutation": mutation, "rc": p.returncode, "stdout": p.stdout.strip().splitlines()[-2:], "stderr": p.stderr.strip().splitlines()[-2:],
           "expected": {"rc": expect_rc, "needle": expect_needle}}
    if mutate is None and p.returncode == 0:
        built = json.loads((here_in_wt / "archive.json").read_text())
        orig = json.loads((HERE / "archive.json").read_text())
        rec["rebuilt_archive_sha256"] = sha256((here_in_wt / "inputs.tar.zst").read_bytes())
        rec["rebuilt_files_block_equal"] = built["files"] == orig["files"] and built["tar_sha256"] == orig["tar_sha256"]
        rec["met"] = p.returncode == expect_rc and rec["rebuilt_archive_sha256"] == sha256((HERE / "inputs.tar.zst").read_bytes()) and rec["rebuilt_files_block_equal"]
    else:
        rec["met"] = p.returncode == expect_rc and expect_needle in (p.stdout + p.stderr)
    drop(wt)
    (RUNS / f"{name}.json").write_text(json.dumps(rec, indent=1, sort_keys=True) + "\n")
    print(f"[{'ok' if rec['met'] else 'UNEXPECTED'}] {name}: rc {p.returncode} — {(p.stderr.strip().splitlines() or p.stdout.strip().splitlines() or [''])[-1][:150]}")
    return rec


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
    # the producer: positive reproduction, then the two drifted-B1-authority counterexamples
    recs.append(producer("producer_positive_rebuilds_the_archive_byte_identically", scratch, None, 0, "sha256 " + sha256(orig_a.read_bytes())))
    recs.append(producer("neg_producer_b1_table_repinned_to_a_drifted_member", scratch, drift_b1_table_and_member, 2,
                         "manifests/b1_instrument_pins.json"))
    recs.append(producer("neg_producer_b1_manifest_repinned_to_a_drifted_image", scratch, drift_b1_manifest_and_image, 2,
                         "manifests/b1_manifest.json"))
    subprocess.run(["git", "worktree", "prune"], cwd=REPO)
    summary = {"at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "base": BASE,
               "archive_sha256": sha256(orig_a.read_bytes()), "manifest_sha256": sha256(orig_m.read_bytes()),
               "runs": [{k: r.get(k) for k in ("name", "rc", "met", "seconds")} for r in recs],
               "all_met": all(r["met"] for r in recs),
               "worktrees_after": subprocess.run(["git", "worktree", "list"], cwd=REPO, capture_output=True, text=True).stdout,
               "main_tree_status_porcelain": subprocess.run(["git", "status", "--porcelain"], cwd=REPO, capture_output=True, text=True).stdout}
    (RUNS / "summary.json").write_text(json.dumps(summary, indent=1, sort_keys=True) + "\n")
    print(f"{sum(r['met'] for r in recs)}/{len(recs)} controls met")
    return 0 if summary["all_met"] else 1


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
