#!/usr/bin/env python3
"""B2 completion inputs — the consumer. In a FRESH DETACHED CHECKOUT of the B2 completion commit
(BASE), restore exactly the 15 non-tracked inputs from inputs.tar.zst, verify each against
archive.json, then run the production B2 S3 verify and require S3 / true / null / the expected
manifest sha256 and pin-table sha256.

    restore_verify.py --target <checkout> [--archive inputs.tar.zst] [--manifest archive.json] [--skip-verify]

Every check that fails is a NAMED refusal (exit 2, one line `REFUSED: ...`, JSON on stdout). It
never overwrites: if any listed path already exists in the target, nothing is written. Anything
unexpected is an INTERNAL ERROR (exit 3) and is never dressed up as a refusal. Needs `zstd` on PATH
and the pinned instrument checkout (PSORACLE_ROOT, default /home/test/zynq_psoracle) for the verify.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
SCHEMA, SCHEMA_VERSION = "b2_completion_inputs", "1.0.0"

VERIFY_SNIPPET = r'''
import sys, json
sys.path.insert(0, "host")
import b2_manifest as bm, b2_runner as rn
m = json.loads(bm.MANIFEST.read_text())
try:
    v = bm.verify(m, readjudicate=rn.readjudicator(m))
    print(json.dumps({"outcome": "verified", "stage": v["stage"], "qualified": v["qualified"], "refusal": v["refusal"],
                      "manifest_sha256": v["manifest_sha256"], "pins_sha256": (v["checks"].get("instrument_pins") or {}).get("pins_sha256"),
                      "files_verified": (v["checks"].get("instrument_pins") or {}).get("files_verified")}))
except bm.Refusal as exc:
    print(json.dumps({"outcome": "refused", "refusal": str(exc)}))
'''


class Refusal(Exception):
    pass


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def git(target: Path, *args) -> str:
    p = subprocess.run(["git", "-C", str(target), *args], capture_output=True, text=True)
    if p.returncode != 0:
        raise Refusal(f"target is not a usable git checkout: git {' '.join(args)}: {p.stderr.strip()[:200]}")
    return p.stdout.strip()


def run(a) -> dict:
    out = {"tool": "restore_verify 1.0.0", "at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "target": str(a.target), "archive": str(a.archive), "manifest": str(a.manifest)}
    # 1. the manifest: type before use
    if not a.manifest.is_file():
        raise Refusal(f"manifest {a.manifest} is absent")
    try:
        doc = json.loads(a.manifest.read_text())
    except ValueError as exc:
        raise Refusal(f"manifest is not JSON: {exc}")
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA or doc.get("schema_version") != SCHEMA_VERSION:
        raise Refusal(f"manifest is not a {SCHEMA} {SCHEMA_VERSION} document")
    files = doc.get("files")
    if not isinstance(files, dict) or not files or doc.get("file_count") != len(files):
        raise Refusal("manifest carries no consistent file table")
    for rel, e in files.items():
        if rel.startswith("/") or ".." in Path(rel).parts or not isinstance(e, dict) \
                or not isinstance(e.get("sha256"), str) or len(e["sha256"]) != 64 or not isinstance(e.get("bytes"), int):
            raise Refusal(f"manifest entry {rel!r} is malformed")
    out["manifest_sha256"] = sha256(a.manifest.read_bytes())
    out["base"], out["file_count"] = doc["base"], len(files)
    # 2. the archive hashes to the manifest's pin
    if not a.archive.is_file():
        raise Refusal(f"archive {a.archive} is absent")
    zst = a.archive.read_bytes()
    out["archive_sha256"] = sha256(zst)
    if out["archive_sha256"] != doc.get("archive_sha256"):
        raise Refusal(f"archive sha256 {out['archive_sha256'][:12]}… differs from the manifest's {str(doc.get('archive_sha256'))[:12]}…")
    # 3. the target: a checkout at BASE, tracked-clean, none of the paths present
    head = git(a.target, "rev-parse", "HEAD")
    out["target_head"] = head
    if head != doc["base"]:
        raise Refusal(f"target HEAD {head[:12]} is not the base {doc['base'][:12]}")
    if subprocess.run(["git", "-C", str(a.target), "diff", "--quiet", "HEAD"]).returncode != 0:
        raise Refusal("target has tracked changes: not a fresh checkout")
    present = [rel for rel in files if (a.target / rel).exists()]
    if present:
        raise Refusal(f"refuses to overwrite: {len(present)} listed path(s) already exist in the target: {present[:3]}")
    # 4. the archive's members: exactly the listed regular files, each hashing to its entry
    p = subprocess.run(["zstd", "-dc"], input=zst, capture_output=True)
    if p.returncode != 0:
        raise Refusal(f"zstd could not decompress the archive: {p.stderr.decode(errors='replace').strip()[:200]}")
    try:
        tar = tarfile.open(fileobj=io.BytesIO(p.stdout), mode="r:")
    except tarfile.TarError as exc:
        raise Refusal(f"the archive is not a tar: {exc}")
    members = tar.getmembers()
    names = [m.name for m in members]
    if sorted(names) != sorted(files) or len(names) != len(files):
        missing = sorted(set(files) - set(names))
        extra = sorted(set(names) - set(files))
        raise Refusal(f"archive members are not exactly the {len(files)} listed: missing {missing[:3]}, extra {extra[:3]}")
    data = {}
    for m in members:
        if not m.isfile():
            raise Refusal(f"archive member {m.name} is not a regular file")
        b = tar.extractfile(m).read()
        if len(b) != files[m.name]["bytes"] or sha256(b) != files[m.name]["sha256"]:
            raise Refusal(f"archive member {m.name}: {len(b)} bytes sha256 {sha256(b)[:12]}… differs from the manifest's "
                          f"{files[m.name]['bytes']} bytes {files[m.name]['sha256'][:12]}…")
        data[m.name] = b
    # 5. write, then re-hash on disk
    restored = {}
    for rel in sorted(data):
        dst = a.target / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_bytes(data[rel])
        got = sha256(dst.read_bytes())
        if got != files[rel]["sha256"]:
            raise Refusal(f"{rel} does not hash to its entry after writing")
        restored[rel] = got
    out["restored"] = restored
    out["restored_count"] = len(restored)
    if a.skip_verify:
        out["verify"] = "skipped"
        return out
    # 6. the production B2 verify in the target
    v = subprocess.run([sys.executable, "-B", "-c", VERIFY_SNIPPET], cwd=a.target, capture_output=True, text=True)
    try:
        res = json.loads(v.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        raise RuntimeError(f"the verify produced no result: rc {v.returncode}; stderr tail: {v.stderr[-600:]}")
    out["verify"] = res
    if res.get("outcome") != "verified":
        raise Refusal(f"the B2 verify refused after the restore: {res.get('refusal')}")
    want = (("stage", "S3"), ("qualified", True), ("refusal", None),
            ("manifest_sha256", doc["expect_manifest_sha256"]), ("pins_sha256", doc["expect_pins_sha256"]))
    bad = [f"{k}={res.get(k)!r} (want {w!r})" for k, w in want if res.get(k) != w]
    if bad:
        raise Refusal("the B2 verify did not give the expected completion state: " + "; ".join(bad))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--target", type=Path, required=True)
    ap.add_argument("--archive", type=Path, default=HERE / "inputs.tar.zst")
    ap.add_argument("--manifest", type=Path, default=HERE / "archive.json")
    ap.add_argument("--skip-verify", action="store_true", help="restore and hash only (no B2 verify)")
    a = ap.parse_args(argv)
    try:
        out = run(a)
    except Refusal as exc:
        print(json.dumps({"outcome": "REFUSED", "refusal": str(exc)}))
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    except Exception as exc:  # never dressed up as a refusal
        print(json.dumps({"outcome": "INTERNAL ERROR", "error": f"{type(exc).__name__}: {exc}"}))
        print(f"INTERNAL ERROR: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 3
    out["outcome"] = "OK"
    print(json.dumps(out, indent=1, sort_keys=True))
    print(f"OK: restored {out['restored_count']} files into {a.target}; verify {out['verify'] if isinstance(out['verify'], str) else 'S3 / true / null / ' + out['verify']['manifest_sha256'][:8] + '…'}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
