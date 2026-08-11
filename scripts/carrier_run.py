#!/usr/bin/env python3
"""Load a `carrier_run` bundle and verify every artifact it pins, before anyone judges.

Both production gates take a run directory and nothing else. Neither accepts a map, a LUT
key, a bitstream or a build directory on the command line: an operator who can choose the
inputs chooses the verdict, which is the same defect as a gate that asks the builder what
to expect.

Everything here returns findings rather than raising, so a caller reports all of them
instead of the first. A gate that stops at the first mismatch hides the shape of the
failure — and this repo has been bitten by exactly that.

LFS-backed artifacts have one extra failure mode worth naming: in a clone without
`git lfs pull` the file on disk is a ~130-byte POINTER, not the bitstream. Its sha256 will
not match, so the check below already refuses — but it refuses with a confusing message, so
pointers are detected and reported as themselves.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

from gate_measure_ff import parse_lfs_pointer  # noqa: E402

TOOL_VERSION = "carrier_run.py/2.0.0"

LFS_POINTER_PREFIX = b"version https://git-lfs.github.com/spec/"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def looks_like_lfs_pointer(path: Path) -> bool:
    try:
        with path.open("rb") as fh:
            return fh.read(len(LFS_POINTER_PREFIX)) == LFS_POINTER_PREFIX
    except OSError:
        return False


def load(run_dir: Path) -> tuple[dict | None, list[dict]]:
    """Return (bundle, findings). `bundle` is None when it could not be read at all."""
    findings: list[dict] = []

    def bad(kind: str, message: str, **detail):
        findings.append({"kind": kind, "message": message, **detail})

    path = run_dir / "carrier_run.json"
    if not path.is_file():
        bad("bundle", "no carrier_run.json: this directory is not a published carrier run",
            path=str(path))
        return None, findings
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        bad("bundle", f"carrier_run.json is unreadable: {exc}", path=str(path))
        return None, findings

    if doc.get("schema") != "carrier_run":
        bad("bundle", f"not a carrier_run bundle: schema={doc.get('schema')!r}")
        return doc, findings

    artifacts = doc.get("artifacts") or {}
    if not artifacts:
        bad("bundle", "the bundle pins no artifacts")

    for name, rec in sorted(artifacts.items()):
        p = run_dir / name
        if not p.is_file():
            bad("artifact", f"{name} is pinned by the bundle but is not present",
                path=str(p))
            continue
        if rec.get("lfs") and looks_like_lfs_pointer(p):
            bad(
                "lfs",
                f"{name} is still a Git LFS POINTER, not the artifact: run `git lfs pull`",
                path=str(p),
            )
            continue
        actual = sha256_of(p)
        if actual != rec.get("sha256"):
            bad("artifact", f"{name} does not match the digest the bundle pins",
                path=str(p), pinned=rec.get("sha256"), actual=actual)
        size = p.stat().st_size
        if rec.get("bytes") is not None and size != rec["bytes"]:
            bad("artifact", f"{name} is {size} bytes, the bundle pins {rec['bytes']}",
                path=str(p))

    return doc, findings


def _git(*arguments: str) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *arguments], cwd=REPO_ROOT, capture_output=True, check=False)


def head_authority_problems(run_dir: Path) -> list[dict]:
    """Is this run the one HEAD published, or merely a directory that agrees with itself?

    `load()` proves the files match the bundle. It cannot prove the bundle is an authority:
    copy a whole published run to /tmp, outside any repository, and every digest still
    agrees — which is exactly what a reviewer reproduced. A self-consistent set is not a
    publication, and the production gates must not accept one.

    So the CLI asks git, and there is deliberately **no `--repo` escape**: an operator who
    can point the authority elsewhere has no authority.

      * the run must live inside THIS repository — the one whose scripts are running;
      * every artifact and the bundle must be tracked in HEAD;
      * ordinary artifacts must be byte-identical to their HEAD blobs;
      * an LFS artifact's HEAD blob must be a pointer whose **oid is the bundle's pin** —
        the digest of the bytes, so the pointer names the artifact the bundle vouches for;
      * no tracked file may differ from HEAD **in the working tree or in the index**,
        including the gates themselves. `git diff` alone was not enough: it compares the
        working tree against the INDEX, so editing a gate and then `git add`-ing it left
        `git diff` empty and the verdict was accepted. `git diff HEAD` is the question that
        was meant — is anything different from what is published — and staging is not a way
        to answer it.
    """
    problems: list[dict] = []

    def bad(kind: str, message: str, **detail):
        problems.append({"kind": kind, "message": message, **detail})

    top = _git("-C", str(run_dir.resolve()), "rev-parse", "--show-toplevel")
    if top.returncode != 0:
        bad("authority", "the run directory is not inside a git repository: a directory "
                         "that agrees with itself is not a publication",
            path=str(run_dir))
        return problems
    if Path(top.stdout.decode().strip()).resolve() != REPO_ROOT.resolve():
        bad("authority",
            "the run directory belongs to a different repository than the scripts judging it",
            run_repo=top.stdout.decode().strip(), scripts_repo=str(REPO_ROOT))
        return problems

    try:
        relative = run_dir.resolve().relative_to(REPO_ROOT.resolve())
    except ValueError:
        bad("authority", "the run directory is not under the repository root", path=str(run_dir))
        return problems

    doc, _ = load(run_dir)
    if doc is None:
        return problems          # load() already reported it

    # `git diff HEAD`, NOT `git diff`: the latter compares the working tree against the
    # index, so `git add` of an edited gate emptied it and the verdict was accepted.
    dirty = _git("diff", "HEAD", "--name-only").stdout.decode().split()
    if dirty:
        bad("authority",
            f"{len(dirty)} tracked file(s) differ from HEAD in the working tree or the "
            "index, so this verdict would describe an edited copy rather than what is "
            "published",
            examples=dirty[:5])

    names = list((doc.get("artifacts") or {})) + ["carrier_run.json"]
    for name in names:
        rel = f"{relative}/{name}"
        shown = _git("cat-file", "-e", f"HEAD:{rel}")
        if shown.returncode != 0:
            bad("authority", f"{rel} is not tracked in HEAD", path=rel)
            continue
        blob = _git("cat-file", "blob", f"HEAD:{rel}").stdout
        rec = (doc.get("artifacts") or {}).get(name)
        if rec is None:                       # the bundle itself
            if blob != (run_dir / name).read_bytes():
                bad("authority", f"{rel} differs from its HEAD blob", path=rel)
            continue
        if rec.get("lfs"):
            oid, why_not = parse_lfs_pointer(blob)
            if oid is None:
                bad("authority", f"{rel}: {why_not} — HEAD does not hold an LFS pointer",
                    path=rel)
            elif oid != rec.get("sha256"):
                bad("authority", f"{rel}: HEAD's pointer oid is {oid}, the bundle pins "
                                 f"{rec.get('sha256')}", path=rel)
        else:
            if hashlib.sha256(blob).hexdigest() != rec.get("sha256"):
                bad("authority", f"{rel}: the HEAD blob does not hash to the bundle's pin",
                    path=rel)
            if blob != (run_dir / name).read_bytes():
                bad("authority", f"{rel} differs from its HEAD blob", path=rel)

    return problems


def input_digests(doc: dict) -> dict[str, str]:
    """The digests a verdict must carry, so the verdict names what it judged."""
    return {name: rec.get("sha256") for name, rec in sorted((doc.get("artifacts") or {}).items())}
