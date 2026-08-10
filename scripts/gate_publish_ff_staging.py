#!/usr/bin/env python3
"""Judge a staged-for-commit `clb_ff_config` staging by what is in the **index**.

    git add staging/<run_id>
    scripts/gate_publish_ff_staging.py --run-root staging/<run_id>   # <- must pass
    git commit -m "staging: …"

Run it between `git add` and `git commit`, and do not commit if it refuses. Note what is
*not* in that `git add`: `.gitattributes` belongs to the policy commit that lands before
any publication, and so does everything else the gate consults.

Why this exists, and why the stager's own check is not enough
------------------------------------------------------------
`gate_stage_ff_formal.publication_attribute_problems()` asks whether the paths *would* be
stored as LFS pointers under the published rule. That is a pre-check on intent. What
actually enters history is decided later, by `git add`, and between those two moments the
rule can be edited or the filter overridden:

    git -c filter.lfs.process= -c filter.lfs.clean=cat -c filter.lfs.required=false \
        add staging/<run_id>

adds 365.7 MiB of ordinary blobs to the index and no earlier check sees it. (Clearing
`filter.lfs.process` is the part that matters: overriding `clean` and `required` alone
changes nothing wherever git-lfs installed its long-running process filter, which is
every standard install — the index still receives pointers. Verified, not assumed.)
Appending one `-filter` line to the working `.gitattributes` before `git add` does the
same thing with no flags at all. The measurement's pointer gate would catch it afterwards — but afterwards
is after the commit, and a commit that put 366 MiB of binary into ordinary history is the
one mistake in this pipeline that no later commit undoes.

So this gate reads **index blobs**: what the next commit will actually contain.

What it requires
----------------
Everything is read from the index, including the manifest and `.gitattributes`, because
the question is what the **next tree** contains and nothing else answers it.

* the manifest validates against `specimen_staging` 1.0.0 and says `complete: true`;
* the specimen set is rebuilt from the **frozen** commitment — the canonical path and
  `5440ef27…`, hash-pinned in `gate_build_ff_formal` — read from the index and required to
  be those bytes. Not "the commitment the manifest points at": commitment, manifest and
  index are three records one commit can rewrite together, and checking them against each
  other would call that self-consistent set a complete publication;
* no duplicate specimen id and no two entries naming one artifact path;
* every staged bitstream is a **strict LFS pointer** whose oid equals the manifest's
  pinned sha256 — the oid is the content hash, so that equality says the object behind
  the pointer is the artifact that was staged;
* every attestation is an ordinary blob **whose bytes hash to the manifest's pin**.
  "Ordinary" alone is not enough: editing an attestation and adding it without touching
  the manifest leaves every other check satisfied;
* the manifest is an ordinary blob, and the index under the run root holds exactly the
  manifest plus 2 artifacts per committed specimen — nothing missing, nothing extra;
* `.gitattributes` is in HEAD **and** in the index, with every path re-resolved by
  `git check-attr --cached`. "In HEAD or in the index" was wrong: HEAD can carry the rule
  while the index stages its deletion, and the next commit then has no rule at all;
* **the staged change set is exactly this staging and nothing else.** Without that, the
  frozen path and hash above are only as fixed as the Python file they are read from: a
  commit can stage an edited `gate_build_ff_formal.py`, a new commitment and a manifest
  cut to match, and be judged by the authority it is itself rewriting. Pinning a further
  hash does not close it — whatever names the authority can be staged too. Refusing the
  change set does;
* **no tracked file differs between the working tree and the index.** The index seal says
  what the commit contains; this says what judged it. The frozen pin, the pointer parser
  and the schemas are all read from the working tree, so an *unstaged* edit to any of them
  changes the verdict while the staged diff stays exactly a staging — the same hole, one
  level out. Broader than a list of this gate's imports on purpose: a list would be a
  claim about which files can change a verdict, and we do not know all of them.

It reuses `gate_measure_ff.parse_lfs_pointer` rather than re-deriving what a pointer is,
and the consumer's own schema validator for the manifest: two definitions of "well-formed"
is one more than the number that can be right.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
sys.path.insert(0, str(REPO))

import gate_build_ff_formal as builder  # noqa: E402
from gate_measure_ff import parse_lfs_pointer  # noqa: E402
from host.verify_certificate import safe_child, validate_external_schema  # noqa: E402

# The authority for the committed set, and deliberately not anything the commit being
# judged can touch: hash-pinned in the builder, reviewed there.
CANONICAL_COMMITMENT = builder.COMMITMENT
COMMITTED_SHA256 = builder.COMMITTED_SHA256

SPECIMENS_DIR = "specimens"
MANIFEST_NAME = "staging_manifest.json"
STAGING_SCHEMA = REPO / "schemas/specimen_staging.schema.json"
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


def committed_specimen_ids(manifest: dict, root: Path) -> tuple[set, list]:
    """The specimen ids the frozen commitment names — an authority outside this commit.

    The manifest cannot be the authority for "184": cut it to one specimen and it
    describes one specimen perfectly. Neither can the commitment it *points at*, which was
    the earlier mistake here — commitment, manifest and index are three records that can
    be rewritten together in one commit, and a gate that only checked them against each
    other would call that self-consistent set a complete publication.

    So the authority is the **frozen** commitment: the canonical path and
    `5440ef27…d1b2e51`, hash-pinned in `gate_build_ff_formal` and reviewed there, not in
    anything this commit can touch. The manifest must name that path and that hash, and
    the blob **in the index** must be those bytes — no fallback to HEAD, because a staged
    deletion of the commitment is exactly the case a fallback would wave through.
    """
    problems: list[str] = []
    canonical = str(CANONICAL_COMMITMENT.relative_to(REPO))
    reference = manifest.get("prediction_commitment")
    if not isinstance(reference, dict):
        return set(), ["the manifest pins no prediction_commitment, so the committed "
                       "specimen set cannot be rebuilt"]
    relative = reference.get("path")
    if relative != canonical:
        problems.append(f"the manifest pins commitment {relative!r}; the frozen "
                        f"commitment for this class is {canonical!r}")
    if reference.get("sha256") != COMMITTED_SHA256:
        problems.append(f"the manifest pins commitment hash {str(reference.get('sha256'))[:12]}…; "
                        f"the frozen commitment is {COMMITTED_SHA256[:12]}…")
    if problems:
        return set(), problems
    try:
        safe_child(root, relative)
    except ValueError as exc:
        return set(), [f"manifest prediction_commitment.path: {exc}"]

    # The index, and only the index: this gate judges the next tree, and a commitment
    # staged for deletion must refuse rather than resolve against HEAD.
    in_index = index_entries(relative, root)
    if relative not in in_index:
        return set(), [f"the frozen commitment {relative} is not in the index — a staged "
                       "deletion of it would publish a staging whose authority the next "
                       "tree does not contain"]
    payload = blob(in_index[relative], root)
    if hashlib.sha256(payload).hexdigest() != COMMITTED_SHA256:
        return set(), [f"the commitment {relative} in the index is not the frozen "
                       f"{COMMITTED_SHA256[:12]}… — the authority for the committed set "
                       "cannot be rewritten in the commit it authorises"]
    try:
        document = json.loads(payload)
    except json.JSONDecodeError as exc:
        return set(), [f"the frozen commitment {relative} is not JSON: {exc}"]

    identifiers = [item["specimen_id"] for item in document.get("specimens", [])]
    if len(set(identifiers)) != len(identifiers):
        problems.append("the frozen commitment names a specimen twice")
    totals = document.get("totals", {})
    if totals.get("specimens") != len(identifiers):
        problems.append(f"the frozen commitment lists {len(identifiers)} specimens and "
                        f"declares totals.specimens={totals.get('specimens')}")
    # The manifest's copy of the commitment's own description has to be the commitment's.
    for field, expected in (("schema_version", document.get("schema_version")),
                            ("seed", str(document.get("seed"))),
                            ("totals", dict(totals))):
        value = str(reference.get(field)) if field == "seed" else reference.get(field)
        if value != expected:
            problems.append(f"the manifest's commitment {field} differs from the frozen "
                            "commitment document")
    return set(identifiers), problems


def sealed_change_set_problems(expected: set[str], root: Path) -> list[str]:
    """A publication commit changes the staging and **nothing else**.

    This is what makes "an authority outside this commit" a structural fact rather than a
    hopeful sentence. The frozen path and hash are read from
    `gate_build_ff_formal`, a working-tree Python file — so a commit that stages an edited
    builder alongside a new commitment and a manifest cut to match would be judged by its
    own rewritten authority. Pinning another hash does not help: whatever names the
    authority can be staged too. The only fix is to refuse the change set.

    So the staged diff against HEAD must be exactly the manifest plus its artifacts.
    Everything that decides whether a staging is legitimate — the commitment, the builder
    that pins it, this gate, the schemas, the attribute rule — must **already be in HEAD**,
    where it was reviewed as its own commit. `.gitattributes` is deliberately not part of a
    publication: it belongs to the policy commit that precedes one.

    Exact equality, not containment: a path in the manifest that the commit does not
    change is a path this commit is not publishing.
    """
    listed = git("diff", "--cached", "--name-only", "-z", "HEAD", root=root)
    if listed.returncode != 0:
        return [f"git could not read the staged change set: {listed.stderr.decode().strip()}"]
    changed = {item for item in listed.stdout.decode().split("\0") if item}

    problems: list[str] = []
    outside = sorted(changed - expected)
    if outside:
        problems.append(
            f"a publication commit is staging-only, and {len(outside)} staged change(s) "
            f"are not part of this staging (first: {outside[:3]}). Everything that decides "
            "whether a staging is legitimate — the commitment, the builder that hash-pins "
            "it, this gate, the schemas, .gitattributes — has to be in HEAD already, or "
            "the commit rewrites the authority that judges it")
    unchanged = sorted(expected - changed)
    if unchanged:
        problems.append(f"{len(unchanged)} path(s) the manifest names are staged but "
                        f"unchanged against HEAD (first: {unchanged[:3]}), so this commit "
                        "does not publish them")
    return problems


def execution_source_problems(root: Path) -> list[str]:
    """The gate that is running must be the gate the index carries.

    Sealing the index says what the commit contains. It does not say what judged it: this
    tool imports `gate_build_ff_formal` for the frozen path and hash, imports the pointer
    parser from `gate_measure_ff`, and reads the staging schema — all from the **working
    tree**. An unstaged edit to any of them changes the verdict while `git diff --cached`
    stays exactly a staging, so the index seal alone leaves the same hole one level out:
    an authority the commit does not modify, but the run does.

    So every tracked file must be identical between the working tree and the index. That
    is deliberately broader than a list of this gate's own imports — a list would be a
    claim about which files can change a verdict, and the honest answer is that we do not
    know all of them.

    It also catches an artifact swapped after `git add`: under the normal filter a
    materialised `.bit` cleans back to the same pointer and reads clean, so a working file
    that differs is one that changed.
    """
    listed = git("diff", "--name-only", "-z", root=root)
    if listed.returncode != 0:
        return [f"git could not compare the working tree with the index: "
                f"{listed.stderr.decode().strip()}"]
    changed = sorted({item for item in listed.stdout.decode().split("\0") if item})
    if not changed:
        return []
    return [f"{len(changed)} tracked file(s) differ between the working tree and the index "
            f"(first: {changed[:3]}). The gate reads its own authority — the frozen "
            "commitment pin, the pointer parser, the schemas — from the working tree, so "
            "an unstaged edit to any of them means the run that judged this staging is not "
            "the one the index carries. Commit or restore them, then re-run"]


def attribute_problems(paths: dict[str, str], root: Path) -> list[str]:
    """`git check-attr --cached`: how the *index's* rule governs the index's paths."""
    if not paths:
        return []
    asked = git("check-attr", "--cached", "-z", "filter", "--", *sorted(paths), root=root)
    if asked.returncode != 0:
        return [f"git could not resolve the staged attributes: "
                f"{asked.stderr.decode().strip()}"]
    fields = [item for item in asked.stdout.decode().split("\0") if item]
    resolved = {fields[index]: fields[index + 2] for index in range(0, len(fields) - 2, 3)}
    problems = []
    for relative, kind in sorted(paths.items()):
        value = resolved.get(relative, "unspecified")
        if kind == "lfs" and value != "lfs":
            problems.append(f"{relative}: the index's own .gitattributes resolves it to "
                            f"filter={value}, not lfs")
        if kind == "ordinary" and value == "lfs":
            problems.append(f"{relative}: the index's own .gitattributes resolves it to "
                            "filter=lfs, but it is an ordinary Git file by ruling")
    return problems


def publication_problems(run_root: str, root: Path = REPO) -> list[str]:
    """Everything wrong with what the next commit would contain. Empty means publishable."""
    problems: list[str] = []
    if git("rev-parse", "--git-dir", root=root).returncode != 0:
        return [f"{root} is not a git repository: there is no index to judge"]

    staged = index_entries(run_root, root)
    if not staged:
        return [f"nothing is staged under {run_root}: `git add` it before publishing"]

    manifest_path = f"{run_root}/{MANIFEST_NAME}"
    if manifest_path not in staged:
        return [f"{manifest_path} is not in the index — the manifest that describes a "
                "publication has to be part of it"]
    manifest_bytes = blob(staged[manifest_path], root)
    if parse_lfs_pointer(manifest_bytes)[0] is not None:
        problems.append(f"{manifest_path}: the index holds an LFS pointer, but the "
                        "manifest is an ordinary Git file by ruling")
    try:
        manifest = json.loads(manifest_bytes)
    except json.JSONDecodeError as exc:
        return problems + [f"{manifest_path} in the index is not JSON: {exc}"]

    findings = validate_external_schema(manifest, STAGING_SCHEMA, "staged manifest")
    if findings:
        # Fatal on its own: everything below reads named fields out of this document.
        return problems + findings[:10]
    if manifest.get("complete") is not True:
        # Equivalent to the schema today — `complete` is required with `const: true`, so
        # anything else fails validation above and never reaches here. Kept deliberately:
        # it is the semantic statement, and it stops being unreachable the moment the
        # schema relaxes that field. Deleting it is not caught by any test, and should
        # not be.
        problems.append(f"{manifest_path} does not declare complete: true")

    committed, found = committed_specimen_ids(manifest, root)
    problems.extend(found)

    kinds: dict[str, str] = {manifest_path: "ordinary"}
    expected: set[str] = {manifest_path}
    seen_ids: set[str] = set()
    seen_targets: dict[str, str] = {}
    for entry in manifest["specimens"]:
        specimen_id = entry["specimen_id"]
        if specimen_id in seen_ids:
            problems.append(f"the manifest names {specimen_id} twice")
            continue
        seen_ids.add(specimen_id)
        bitstream, attestation = entry["bitstream"]["path"], entry["attestation"]["path"]
        expected |= {bitstream, attestation}
        kinds[bitstream], kinds[attestation] = "lfs", "ordinary"
        for relative in (bitstream, attestation):
            owner = seen_targets.setdefault(relative, specimen_id)
            if owner != specimen_id:
                problems.append(f"{specimen_id}: {relative} is already named by {owner}")

        if bitstream not in staged:
            problems.append(f"{specimen_id}: {bitstream} is named by the manifest and is "
                            "not in the index")
        else:
            oid, why = parse_lfs_pointer(blob(staged[bitstream], root))
            if oid is None:
                problems.append(f"{specimen_id}: {bitstream} in the index is not a "
                                f"pointer — {why}. Committing this puts the bitstream "
                                "into ordinary Git history, which no later commit undoes")
            elif oid != entry["bitstream"]["sha256"]:
                problems.append(
                    f"{specimen_id}: {bitstream} in the index points at object "
                    f"{oid[:12]}…, the manifest pins {entry['bitstream']['sha256'][:12]}…")

        if attestation not in staged:
            problems.append(f"{specimen_id}: {attestation} is named by the manifest and "
                            "is not in the index")
        else:
            payload = blob(staged[attestation], root)
            if parse_lfs_pointer(payload)[0] is not None:
                problems.append(f"{specimen_id}: {attestation} in the index is an LFS "
                                "pointer, but attestations are ordinary Git files by "
                                "ruling")
            elif hashlib.sha256(payload).hexdigest() != entry["attestation"]["sha256"]:
                problems.append(f"{specimen_id}: {attestation} in the index does not hash "
                                "to the value the manifest pins")

    if committed:
        missing, extra = committed - seen_ids, seen_ids - committed
        if missing or extra:
            problems.append(
                f"the manifest describes {len(seen_ids)} specimens where the commitment "
                f"names {len(committed)} (missing {len(missing)}, extra {len(extra)}; "
                f"first missing {sorted(missing)[:2]}, first extra {sorted(extra)[:2]})")

    unexpected = sorted(set(staged) - expected)
    if unexpected:
        problems.append(f"{len(unexpected)} path(s) staged under {run_root} that the "
                        f"manifest does not name (first: {unexpected[:3]})")

    # The rule that will govern these paths is the one in the *next* tree, so it is asked
    # from the index. It must also already be in HEAD: a publication commit does not carry
    # policy, and the change-set seal below refuses one that tries to.
    if git("cat-file", "-e", "HEAD:" + ATTRIBUTES, root=root).returncode != 0:
        problems.append(
            f"{ATTRIBUTES} is not in HEAD: the rule that keeps these paths in LFS belongs "
            "to a policy commit that lands and is reviewed before any publication")
    if ATTRIBUTES not in index_entries(ATTRIBUTES, root):
        problems.append(
            f"{ATTRIBUTES} is not in the index: the next commit would carry no rule for "
            "these paths, so a clone would store them differently. A staged deletion of "
            "it counts — HEAD having the rule is not enough")
    else:
        problems.extend(attribute_problems(kinds, root))

    problems.extend(sealed_change_set_problems(expected, root))
    problems.extend(execution_source_problems(root))
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run-root", required=True,
                    help="the staged run root, repository-relative, e.g. staging/<run_id>")
    ap.add_argument("--repo", type=Path, default=REPO,
                    help="the repository whose index to judge (default: this one). Only "
                         "the git questions move; the frozen authority still comes from "
                         "this checkout, which is what makes the answer meaningful")
    args = ap.parse_args()

    run_root = args.run_root.rstrip("/")
    problems = publication_problems(run_root, args.repo)
    if problems:
        print(f"REFUSING TO PUBLISH: {len(problems)} problem(s) with the index.")
        for problem in problems[:20]:
            print(f"  - {problem}")
        if len(problems) > 20:
            print(f"  … and {len(problems) - 20} more")
        print("\nDo not commit. `git restore --staged` the run root, fix, and re-add.")
        return 1

    staged = index_entries(run_root, args.repo)
    print(f"PUBLISHABLE: {len(staged)} path(s) staged under {run_root}")
    print("  every bitstream is an LFS pointer whose oid is the manifest's pin")
    print("  the manifest and every attestation are ordinary Git blobs")
    print("  the staged set is exactly what the manifest names")
    return 0


if __name__ == "__main__":
    sys.exit(main())
