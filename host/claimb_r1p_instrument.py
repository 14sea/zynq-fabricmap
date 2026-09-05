#!/usr/bin/env python3
"""Claim B round 1′ — the read-only binding to the archived P3 instrument (`zynq-psoracle`).

The owner's ruling of 2026-09-05 keeps `zynq-psoracle` archived and read-only: round 1′ USES
its host stack (reader, console session, notary relay, collector, validators, rate report,
operator twins, schedule arithmetic, the D4 signer) exactly as the L6 soak did, and may not
change a byte of it. This module is the only place the instrument is located and verified:

  * the checkout must be at the pinned commit (`instrument.psoracle_commit`) with a clean
    working tree — `git rev-parse HEAD` and `git status --porcelain` — and
  * every file the instrument's Python stack consists of must hash to the pinned table
    (`manifests/claimb_round1prime_instrument_pins.json`, generated from that commit by
    `--generate` and checked by tests/test_claimb_r1p_instrument.py), git or no git.

Only after both hold does `bind()` put the instrument's directories on `sys.path`, in the
same order `zynq-psoracle/host/l6_runner.py` uses, so the modules imported here are the
ones that ran S #3. A mismatch is a refusal by name, never a warning: a runner that ran on
an edited instrument would attribute its result to an instrument that never existed.

Nothing here touches a board.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "manifests/claimb_round1prime_manifest.json"
PINS = REPO_ROOT / "manifests/claimb_round1prime_instrument_pins.json"
DEFAULT_ROOT = Path(os.environ.get("PSORACLE_ROOT", "/home/test/zynq_psoracle"))

# The instrument's Python stack and the authority files the round reads from it. Directories
# are pinned whole (every tracked file under them); single files are pinned by name.
PINNED_DIRS = ("host", "validators", "scripts", "imported", "firmware", "rtl", "fixtures", "manifests", "builds/p3")
PINNED_FILES = ("docs/l6_soak_prereg.md", "docs/l6_s_session3_findings.md",
                "evidence/l6_17A6_2026-09-03-01-C1/rate_report.json", "evidence/l6_17A6_2026-09-03-01-C1/run_log.json",
                "evidence/l6_17A6_2026-09-03-02-C2/rate_report.json", "evidence/l6_17A6_2026-09-03-02-C2/run_log.json",
                "evidence/l6_17A6_2026-09-04-01-S/rate_report.json", "evidence/l6_17A6_2026-09-04-01-S/run_log.json",
                "evidence/l6_17A6_2026-09-04-01-S/audits.json", "evidence/l6_17A6_2026-09-04-01-S/timeline.json")
SYS_PATH_ORDER = ("scripts", "host", "", "imported/fabricmap/scripts")     # l6_runner.py's order


class InstrumentRefusal(Exception):
    """The instrument is not the pinned one. Nothing may run."""


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_manifest(path: Path = MANIFEST) -> dict:
    return json.loads(path.read_text())


def _git(root: Path, *args: str) -> str:
    p = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise InstrumentRefusal(f"git {' '.join(args)} failed in {root}: {p.stderr.strip()}")
    return p.stdout.strip()


def tracked_files(root: Path) -> list[str]:
    return [l for l in _git(root, "ls-files", "-z").split("\0") if l]


def generate_pins(root: Path = DEFAULT_ROOT) -> dict:
    """The pin table from the checkout as it is: commit, and sha256 of every tracked file
    under PINNED_DIRS plus PINNED_FILES. Refuses a dirty tree — a pin of an edited file
    would pin something that is not in any commit."""
    dirty = _git(root, "status", "--porcelain")
    if dirty:
        raise InstrumentRefusal(f"{root} has uncommitted changes; pins are generated from a clean tree only")
    head = _git(root, "rev-parse", "HEAD")
    files = {}
    tracked = set(tracked_files(root))
    for rel in sorted(tracked):
        if any(rel == d or rel.startswith(d + "/") for d in PINNED_DIRS) or rel in PINNED_FILES:
            files[rel] = sha256_of(root / rel)
    missing = [f for f in PINNED_FILES if f not in files]
    if missing:
        raise InstrumentRefusal(f"pinned files are not tracked in {root}: {missing}")
    return {"schema": "claimb_r1p_instrument_pins", "schema_version": "1.0.0",
            "psoracle_commit": head, "pinned_dirs": list(PINNED_DIRS), "pinned_files": list(PINNED_FILES),
            "file_count": len(files), "files": files}


def verify(root: Path = DEFAULT_ROOT, pins_path: Path = PINS, manifest: dict | None = None,
           require_git: bool = True) -> dict:
    """Every pinned file hashes to its pin; with git, HEAD is the pinned commit and the tree
    is clean. Returns what was verified. Raises InstrumentRefusal naming the first defect."""
    manifest = manifest or load_manifest()
    pins = json.loads(pins_path.read_text())
    want_commit = manifest["instrument"]["psoracle_commit"]
    if pins["psoracle_commit"] != want_commit:
        raise InstrumentRefusal(f"the pin table was generated from {pins['psoracle_commit'][:12]}, the manifest pins "
                                f"{want_commit[:12]} — regenerate the table from the pinned commit")
    if not root.is_dir():
        raise InstrumentRefusal(f"no instrument checkout at {root} (set PSORACLE_ROOT)")
    if require_git:
        head = _git(root, "rev-parse", "HEAD")
        if head != want_commit:
            raise InstrumentRefusal(f"{root} is at {head[:12]}, not the pinned archive head {want_commit[:12]}")
        dirty = _git(root, "status", "--porcelain")
        if dirty:
            raise InstrumentRefusal(f"{root} is not clean: the archived instrument must be used as committed:\n{dirty[:400]}")
    bad = []
    for rel, sha in pins["files"].items():
        p = root / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
        elif sha256_of(p) != sha:
            bad.append(f"{rel}: hash differs from the pin")
        if len(bad) >= 5:
            break
    if bad:
        raise InstrumentRefusal("the instrument is not the pinned one: " + "; ".join(bad))
    return {"root": str(root), "psoracle_commit": want_commit, "files_verified": len(pins["files"]),
            "git_checked": bool(require_git)}


def bind(root: Path = DEFAULT_ROOT, manifest: dict | None = None, require_git: bool = True) -> dict:
    """verify(), then put the instrument on sys.path in l6_runner.py's order. Idempotent."""
    v = verify(root, manifest=manifest, require_git=require_git)
    for sub in reversed(SYS_PATH_ORDER):     # insert(0, …) in reverse keeps l6_runner's order
        p = str(root / sub) if sub else str(root)
        if p in sys.path:
            sys.path.remove(p)
        sys.path.insert(0, p)
    return v


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=DEFAULT_ROOT)
    ap.add_argument("--generate", action="store_true", help="write the pin table from the checkout (clean tree only)")
    ap.add_argument("--out", type=Path, default=PINS)
    a = ap.parse_args(argv)
    try:
        if a.generate:
            pins = generate_pins(a.root)
            a.out.write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n")
            print(f"pinned {pins['file_count']} files of {a.root} at {pins['psoracle_commit'][:12]} -> {a.out}")
        else:
            v = verify(a.root)
            print(f"instrument verified: {v}")
    except InstrumentRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
