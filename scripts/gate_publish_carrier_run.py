#!/usr/bin/env python3
"""Judge a staged-for-commit carrier run by what is in the **index**.

    git add gate_runs/<run_id>
    scripts/gate_publish_carrier_run.py --run-root gate_runs/<run_id>   # <- must pass
    git commit -m "gate_runs: …"

Run it between `git add` and `git commit`, and do not commit if it refuses. Note what is
*not* in that `git add`: `.gitattributes` belongs to the policy commit that lands first —
a publication commit does not stage its own policy.

Why the index and not the working tree
--------------------------------------
What enters history is decided by `git add`, and the LFS filter can be defeated at exactly
that moment:

    git -c filter.lfs.process= -c filter.lfs.clean=cat -c filter.lfs.required=false \\
        add gate_runs/<run_id>

puts 5 MiB of ordinary blobs in the index and no check of the working tree sees it.
Appending one `-filter` line to the working `.gitattributes` first does the same with no
flags at all. Committing binary into ordinary history is the one mistake here that a later
commit does not undo, so the question has to be asked of the index.

What it requires
----------------
* `.gitattributes` is present **unchanged** in the index — the policy is not being staged
  alongside the artifacts it governs;
* every artifact the bundle pins is staged, and nothing under the run root is staged that
  the bundle does not pin (a file smuggled into a published run is unreviewed either way);
* every `lfs: true` artifact is a **strict LFS pointer whose oid equals the sha256 the
  bundle pins**. The oid is the content hash, so that equality is what says the object
  behind the pointer is the artifact the bundle vouches for;
* every other artifact is an **ordinary blob whose bytes hash to the bundle's pin**.
  "Ordinary" alone is not enough: editing a verdict and adding it without touching the
  bundle would leave every other check satisfied;
* the bundle itself is in the index and is an ordinary blob;
* **the staged change set is exactly the run root.** A publication commit that also carried
  the builder, the two production gates, this gate and its tests was still called
  PUBLISHABLE, because the gate only looked under the run root — the commit was judging
  itself. Authority code lands in its own commit, before the artifacts it governs;
* **no tracked file carries an unstaged modification.** The gate that runs must be the gate
  in history; a verdict from an edited working copy describes something nobody can review.

It reuses `gate_measure_ff.parse_lfs_pointer` rather than re-deriving what a pointer is:
one parser, one place to be wrong.

Exit codes: 0 publishable, 2 refused, 3 usage.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from gate_measure_ff import parse_lfs_pointer  # noqa: E402

TOOL_VERSION = "gate_publish_carrier_run.py/1.0.0"
BUNDLE_NAME = "carrier_run.json"
ATTRIBUTES = ".gitattributes"


def git(*arguments: str, root: Path = REPO) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(["git", *arguments], cwd=root, capture_output=True, check=False)


def index_entries(run_root: str, root: Path) -> dict[str, str]:
    """`{repo-relative path: blob id}` for everything staged under the run root."""
    listed = git("ls-files", "-s", "-z", "--", run_root, root=root)
    entries: dict[str, str] = {}
    for record in listed.stdout.decode().split("\0"):
        if not record:
            continue
        meta, _, path = record.partition("\t")
        entries[path] = meta.split()[1]
    return entries


def blob(object_id: str, root: Path) -> bytes:
    return git("cat-file", "blob", object_id, root=root).stdout


def attribute_problems(paths: dict[str, str], root: Path) -> list[str]:
    """`git check-attr --cached`: how the *index's* rule governs the index's paths."""
    if not paths:
        return []
    asked = git("check-attr", "--cached", "-z", "filter", "--", *sorted(paths), root=root)
    if asked.returncode != 0:
        return [f"git could not resolve the staged attributes: {asked.stderr.decode().strip()}"]
    fields = [item for item in asked.stdout.decode().split("\0") if item]
    resolved = {fields[i]: fields[i + 2] for i in range(0, len(fields) - 2, 3)}
    problems = []
    for relative, kind in sorted(paths.items()):
        value = resolved.get(relative, "unspecified")
        if kind == "lfs" and value != "lfs":
            problems.append(
                f"{relative}: the index's own .gitattributes resolves it to filter={value}, not lfs"
            )
        if kind == "ordinary" and value == "lfs":
            problems.append(
                f"{relative}: the index's own .gitattributes resolves it to filter=lfs, "
                "but it is an ordinary Git file by ruling"
            )
    return problems


def change_set_problems(run_root: str, root: Path) -> list[str]:
    """The staged change set must be exactly the run root, and the tree must be clean.

    Both halves exist because a commit that carries its own judge is not judged. The first
    version of this gate passed a change set containing the builder, both production gates,
    this gate and its tests alongside the artifacts.
    """
    problems = []
    staged = [p for p in git("diff", "--cached", "--name-only", root=root)
              .stdout.decode().split("\n") if p]
    outside = sorted(p for p in staged if not p.startswith(f"{run_root}/"))
    if outside:
        problems.append(
            f"{len(outside)} staged path(s) are outside {run_root}, so this commit would "
            f"carry its own judge: {outside[:5]}"
        )
    dirty = [p for p in git("diff", "--name-only", root=root).stdout.decode().split("\n") if p]
    if dirty:
        problems.append(
            f"{len(dirty)} tracked file(s) carry unstaged modifications: the gate that runs "
            f"must be the gate in history: {dirty[:5]}"
        )
    return problems


def publication_problems(run_root: str, root: Path = REPO) -> list[str]:
    """Everything wrong with what the next commit would contain. Empty means publishable."""
    problems: list[str] = []
    if git("rev-parse", "--git-dir", root=root).returncode != 0:
        return [f"{root} is not a git repository: there is no index to judge"]

    problems.extend(change_set_problems(run_root, root))

    staged = index_entries(run_root, root)
    if not staged:
        return problems + [f"nothing is staged under {run_root}: `git add` it before publishing"]

    bundle_path = f"{run_root}/{BUNDLE_NAME}"
    if bundle_path not in staged:
        return problems + [
            f"{bundle_path} is not in the index — the bundle that pins a run is the first "
            "thing that must enter history with it"
        ]

    try:
        bundle = json.loads(blob(staged[bundle_path], root).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        return problems + [f"{bundle_path} in the index is not readable JSON: {exc}"]
    if bundle.get("schema") != "carrier_run":
        return problems + [
            f"{bundle_path} is not a carrier_run bundle: schema={bundle.get('schema')!r}"]

    # The policy commit must already be history, and must not be part of this one.
    if git("cat-file", "-e", "HEAD:" + ATTRIBUTES, root=root).returncode != 0:
        problems.append(f"{ATTRIBUTES} is not in HEAD: land the policy commit first")
    else:
        head_attr = blob(f"HEAD:{ATTRIBUTES}", root)
        index_attr_id = index_entries(ATTRIBUTES, root).get(ATTRIBUTES)
        if index_attr_id is None:
            problems.append(f"{ATTRIBUTES} is not in the index at all")
        elif blob(index_attr_id, root) != head_attr:
            problems.append(
                f"{ATTRIBUTES} differs between HEAD and the index: a publication commit "
                "must not stage the policy that governs it"
            )

    artifacts = bundle.get("artifacts") or {}
    if not artifacts:
        problems.append(f"{bundle_path} pins no artifacts")

    expected_paths = {f"{run_root}/{name}" for name in artifacts}
    kinds = {
        f"{run_root}/{name}": ("lfs" if rec.get("lfs") else "ordinary")
        for name, rec in artifacts.items()
    }
    kinds[bundle_path] = "ordinary"

    for path in sorted(expected_paths - set(staged)):
        problems.append(f"{path} is pinned by the bundle but is not staged")

    # Anything else under the run root is unreviewed content riding along in a published
    # run. README.md is the one documented exception, and it is named rather than pattern
    # matched so a second exception has to be argued for.
    allowed = expected_paths | {bundle_path, f"{run_root}/README.md"}
    for path in sorted(set(staged) - allowed):
        problems.append(f"{path} is staged under the run root but the bundle does not pin it")

    problems.extend(attribute_problems({p: k for p, k in kinds.items() if p in staged}, root))

    for name, rec in sorted(artifacts.items()):
        path = f"{run_root}/{name}"
        object_id = staged.get(path)
        if object_id is None:
            continue
        payload = blob(object_id, root)
        pinned = rec.get("sha256")
        if rec.get("lfs"):
            oid, why_not = parse_lfs_pointer(payload)
            if oid is None:
                problems.append(f"{path}: {why_not} — the LFS filter did not run on it")
            elif oid != pinned:
                problems.append(
                    f"{path}: the staged pointer's oid is {oid}, the bundle pins {pinned}"
                )
        else:
            actual = hashlib.sha256(payload).hexdigest()
            oid, _ = parse_lfs_pointer(payload)
            if oid is not None:
                problems.append(
                    f"{path}: the index holds an LFS pointer, but this is an ordinary Git "
                    "file by ruling — a reviewer must be able to read and diff it"
                )
            elif actual != pinned:
                problems.append(
                    f"{path}: the staged bytes hash to {actual}, the bundle pins {pinned}"
                )

    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--run-root", required=True,
                    help="repo-relative, e.g. gate_runs/claimb_round1_carrier_2026_08_11")
    args = ap.parse_args()

    problems = publication_problems(args.run_root.rstrip("/"))
    if problems:
        for p in problems:
            print(f"REFUSED: {p}", file=sys.stderr)
        return 2
    print(f"PUBLISHABLE: {args.run_root} — every pinned artifact is staged, every LFS "
          "pointer's oid is the bundle's pin, every ordinary blob hashes to it")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
