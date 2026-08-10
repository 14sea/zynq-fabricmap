#!/usr/bin/env python3
"""Score a `clb_ff_config` run against its committed predictions — certificate 1.6.

Refuses to score unless `predictions.json` still hashes to the committed value. That
check is the whole point of the ordering: a measurement of predictions that were edited
after the bitstreams existed measures nothing.

What 1.6 changed, and it changed where this tool gets its evidence
------------------------------------------------------------------
Every specimen, bitstream and attestation now comes from a `specimen_staging` 1.0.0
manifest, and from nothing else. There is no `--build`: this tool cannot read a build
tree, cannot join `<root>/<specimen_id>/spec.bit` and cannot copy an attestation into the
run directory.

That is not tidying. While the tool built its own paths under `build/`, three separate
things were true at once: it read artifacts no fresh clone has; the `<specimen_id>/`
layout it assumed was a *second* naming rule beside the stager's, free to drift from it;
and the attestation a record pointed at was a **copy this tool made**, so the reference
in the measurement was never the reference the certificate would carry. 1.6 requires the
certificate's attestation reference to equal the staging entry **verbatim**
(`host/verify_certificate.load_feature_staging`), which a re-hashed copy cannot.

So the manifest is now the only door, and it is verified before a single frame is parsed:
its own hash, the commitment it pins recomputed from `predictions.json`, exact set
equality with the 184 committed specimens, every artifact hash recomputed from the staged
bytes, and every reference required to be **in HEAD with exactly those bytes** — tracked
is not enough, because a staging that was only `git add`ed, or committed and then edited,
is not what a verifier's clone would get. Missing, extra, duplicate, escaping, mismatched
or unpublished references each refuse the whole run **before** any measurement is written
— a partially trusted staging is not a smaller measurement, it is no measurement.

Paths are parsed from the manifest and safely resolved; they are never reconstructed from
a specimen id, because a tool that can rebuild the name can disagree with the manifest
about which file it read. Identity between references is decided on the **resolved** file,
so two spellings of one artifact are one artifact; the raw strings still travel into the
record unchanged. And every document is hashed and parsed **in one read** — hashing a path
and then re-opening it is how a record comes to pin bytes nobody scored.

What 1.4 changed, and what this tool therefore does differently from `gate_measure.py`:

* **TP and FN come only from the preregistered assignment and transition.** For every
  predicted address the tool records the value in BOTH endpoints and compares the pair
  against `expected_transition`, plus the feature endpoint against the preregistered
  `expected_value`. Whether a bit shows up in the diff is not an input — a bit that was
  already at the expected value in both endpoints is a failed prediction of a
  *transition*, and the old "is it in the diff" test silently accepted it.
* **FP is fixed by the profile**, not chosen per run:

      FP = ownership_unknown u unattributed
           u {db_attributed bits in an asserted tile that this class claims and that lie
              in no preregistered scope of that pair}

  counted once per `(pair, address)`. A changed bit owned by another class — legal INT
  routing beside a CLB content assertion — is not this class's FP.
* **Observation consistency** is recorded per `(specimen, address)` so the verifier can
  reject a record that reports two values for one bit of one specimen. Opposite values
  in *different* specimens are valid and are how complementary states get certified.

Both endpoints of every pair are committed: the prediction's `specimen_id` is the one
claimed to assert the feature and `comparison_specimen_id` — required from schema 1.5 —
is the other. Neither is derived here. An earlier version worked the second one out from
the specimen plan, which was fine only while every pair happened to be `(base, variant)`
and, worse, left the choice of what an assertion is differenced against open until after
the bitstreams existed (`docs/round10_request.md`).

    scripts/gate_measure_ff.py --run gate_runs/<run> \\
                               --staging-manifest staging/<run>/staging_manifest.json \\
                               --expect-sha256 <committed> --out <run>/measurement.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(REPO))
from bitstream_frames import FRAME_WORDS, column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import read_tile_bits  # noqa: E402
from host.verify_certificate import (  # noqa: E402  — the consumer's own boundary rules
    hash_file,
    safe_child,
    validate_external_schema,
)
from specimen_diff import ECC_BITS, ECC_WORD, features_using, locate, tile_index  # noqa: E402

TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"
STAGING_SCHEMA = REPO / "schemas/specimen_staging.schema.json"
BIT_CLASS = "clb_ff_config"


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def raw_diff(a: dict, b: dict) -> set[tuple[int, int, int]]:
    out = set()
    for far, wa in a.items():
        wb = b[far]
        if wa == wb:
            continue
        for word in range(FRAME_WORDS):
            x = wa[word] ^ wb[word]
            while x:
                bit = (x & -x).bit_length() - 1
                x &= x - 1
                out.add((far, word, bit))
    return out


def address_tuple(address: dict) -> tuple[int, int, int]:
    return int(address["far"], 16), address["word"], address["bit"]


def as_addresses(items) -> list[dict]:
    return sorted(({"far": f"0x{f:08X}", "word": w, "bit": b} for f, w, b in items),
                  key=lambda a: (a["far"], a["word"], a["bit"]))


BUCKETS = ("in_scope", "frame_ecc", "db_attributed", "ownership_unknown", "unattributed")


def classify_diff(raw, scope, index, pattern, asserted_tiles):
    """Label every changed bit into the five 1.4 buckets, plus the same-class subset.

    Returns `(buckets, class_claimed_out_of_scope)`. The second value is the part of
    `db_attributed` that this class itself claims inside a tile the pair asserted and
    that no preregistered scope covers — the only FP contribution that is not simply
    "we cannot explain this bit". Another class's changed bit, such as legal INT routing
    beside a CLB content assertion, is not this class's FP.

    Shared with `gate_build_ff.py` on purpose: an exploration that bucketed bits even
    slightly differently from the gate would answer a question nobody is going to ask.
    """
    buckets = {name: set() for name in BUCKETS}
    class_claimed_out_of_scope = set()
    for far, word, bit in raw:
        if (far, word, bit) in scope:
            buckets["in_scope"].add((far, word, bit))
            continue
        if word == ECC_WORD and bit in ECC_BITS:
            buckets["frame_ecc"].add((far, word, bit))
            continue
        hits = locate(index, far, word, bit)
        if not hits:
            buckets["unattributed"].add((far, word, bit))
        elif any(features_using(hit["type"], hit["segbit"]) for hit in hits):
            buckets["db_attributed"].add((far, word, bit))
            if any(hit["tile"] in asserted_tiles
                   and any(pattern.fullmatch(f)
                           for f in features_using(hit["type"], hit["segbit"]))
                   for hit in hits):
                class_claimed_out_of_scope.add((far, word, bit))
        else:
            buckets["ownership_unknown"].add((far, word, bit))
    return buckets, class_claimed_out_of_scope


def false_positive_bits(buckets: dict, class_claimed_out_of_scope: set) -> set:
    """The fixed 1.4 false-positive profile. **The only definition of it in the repo.**

    `ownership_unknown ∪ unattributed ∪ {db_attributed claimed by THIS class inside an
    asserted tile and covered by no preregistered scope}`, counted once per
    `(pair, address)` — automatic here, because these are address sets and callers key
    them by pair.

    A function rather than three inline lines, for two reasons that both cost something:
    while it was inline, replacing it with `set()` passed the entire test suite; and the
    mine diagnostic briefly carried its own copy, so the rule that decides whether the
    ladder stops existed twice and only one copy was pinned by a test. Every consumer
    calls this one.
    """
    return (set(buckets["ownership_unknown"]) | set(buckets["unattributed"])
            | set(class_claimed_out_of_scope))


def committed_pairs(doc: dict) -> tuple[dict, dict]:
    """`(scopes_by_pair, direction_of_feature)` from the commitment alone.

    Two different things, deliberately separated:

    * **the pair** is an UNORDERED set of two specimens. It is what gets diffed, what
      carries one five-bucket accounting record, and what the verifier rebuilds from the
      commitment — so it is keyed canonically. A complementary pair like
      `CLKINV`/`NOCLKINV` asserts in both directions over one bit, and keying by
      `(comparison, asserting)` recorded it twice: 176 predictions produced 176
      accounting records where the commitment implies 168, double-counting any FP in
      those eight pairs and failing the verifier's completeness check outright.
    * **the direction** is per feature: which endpoint asserts and which supplies the
      `before` value. That stays `(comparison, asserting)`, because the transition is
      read from a specific end.
    """
    scopes: dict[tuple[str, str], set[tuple[int, int, int]]] = {}
    direction: dict[str, tuple[str, str]] = {}
    for prediction in doc["predictions"]:
        asserting = prediction["specimen_id"]
        comparison = prediction.get("comparison_specimen_id")
        if comparison is None:
            raise SystemExit(f"{prediction['feature']}: predictions predate schema 1.5 "
                             "and do not commit a comparison endpoint — refusing to score")
        if comparison == asserting:
            raise SystemExit(f"{prediction['feature']}: committed endpoint pair is a "
                             "single specimen — refusing to score")
        direction[prediction["feature"]] = (comparison, asserting)
        canonical = tuple(sorted((comparison, asserting)))
        scopes.setdefault(canonical, set()).update(
            address_tuple(item["address"]) for item in prediction["predicted_assignments"])
    return scopes, direction


def format_pair_alarm(record: dict) -> str:
    """One line for a pair that carries unexplained bits or false positives.

    Extracted only so it can be tested. This branch runs exactly when something has
    gone wrong, which is precisely when nobody wants to discover that it names a field
    the accounting record stopped having — it read `record['variant']` for one commit
    after the field became `variants`, and would have raised KeyError at the moment the
    report mattered.
    """
    counts = record["counts"]
    label = f"{record['site']}/{'+'.join(record['variants'])}"
    return (f"{label:<34} raw={record['raw_diff_bits']:>4} "
            f"scope={counts['in_scope']:>3} ecc={counts['frame_ecc']:>3} "
            f"db={counts['db_attributed']:>3} unk={counts['ownership_unknown']:>3} "
            f"unatt={counts['unattributed']:>3} "
            f"FP={len(record['false_positive_addresses'])}")


def semantic_verdict(transition_exact: bool, observed, expected) -> bool:
    """`transition_exact and attestation_basis_consistent`, the verifier's rule.

    Kept as its own function because the producer must not invent a weaker or stronger
    semantic pass than the consumer recomputes: `host/verify_certificate.py` rebuilds
    the outcome summary and rejects the record if the copied `passed` disagrees. A
    semantic claim about a specimen whose addressing did not match is not a passing
    naming claim — it names a member the evidence did not select.
    """
    return transition_exact and observed == expected


def address_decision(totals: dict, accounting: list, address_problems: list,
                     committed_holdout: int) -> str:
    """The address decision, with semantics deliberately absent from its inputs.

    1.4 isolates the two: a semantic-only failure keeps `status: passed`, exits zero and
    reports its failure count prominently. Passing `semantic_findings` in here — or
    folding them into `address_problems` — would silently make a naming claim able to
    fail an addressing result, which is the defect this signature exists to prevent.
    """
    holdout = totals["holdout"]
    failed = (holdout["fn"] or holdout["fp"]
              or holdout["tp"] != committed_holdout
              or any(not record["partition_exact"] for record in accounting)
              or address_problems)
    return "FAIL" if failed else "PASS"


FRAME_CACHE_SIZE = 4


class FrameCache:
    """Parsed frame maps, bounded. Keeping 184 of them resident is not an option.

    The staged set is 365.7 MiB of bitstream, but the parsed form is what costs: 5,152
    frames x 101 words per specimen becomes ~20 MB of Python objects, so holding all 184
    is several GB and the run dies of memory where nothing is wrong with the evidence.
    The old unbounded dict simply never met a set this size.

    A small LRU rather than a per-pair teardown, because the access pattern is not
    arbitrary: both ends of a pair are needed at once, and every pair in an instance
    shares one baseline endpoint, so a handful of slots keeps the hit rate high while the
    footprint stays a constant that does not move when the committed set grows.

    Eviction is not a correctness risk, and it is a small integrity gain. Every parse —
    first or repeat — goes through `load`, which re-reads the file and re-checks it
    against the pinned hash, so a bitstream swapped between two uses of the same specimen
    is refused rather than mixed into one accounting.
    """

    def __init__(self, load, size: int | None = None) -> None:
        size = FRAME_CACHE_SIZE if size is None else size
        if size < 2:
            raise ValueError("a frame cache must be able to hold both endpoints of the "
                             "pair being compared")
        self.load = load
        self.size = size
        self.parses = 0
        self.evictions = 0
        self._entries: OrderedDict[str, dict] = OrderedDict()

    def __len__(self) -> int:
        return len(self._entries)

    def frames_of(self, specimen_id: str) -> dict:
        if specimen_id in self._entries:
            self._entries.move_to_end(specimen_id)
            return self._entries[specimen_id]
        frames = self.load(specimen_id)
        self.parses += 1
        self._entries[specimen_id] = frames
        while len(self._entries) > self.size:
            self._entries.popitem(last=False)
            self.evictions += 1
        return frames


def resolve_pointer(value, pointer: str):
    """RFC 6901, objects only — the same restriction the verifier applies."""
    for raw in pointer.removeprefix("/").split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            return None
        value = value[part]
    return value


# ---------------------------------------------------------------------------------------
# The staging manifest is the only door
# ---------------------------------------------------------------------------------------

def uncommitted_references(relatives: list[str]) -> list[str]:
    """Problems: each of these paths must exist in HEAD with exactly its current bytes.

    "Tracked" is not the property that matters and this check used to ask for it, which
    passed three states it should not have: a staging merely `git add`ed and never
    committed, a committed file edited afterwards, and — worst — no git at all, where
    returning "nothing is untracked" read as approval.

    What a certificate actually needs is that an independent verifier cloning this
    repository gets the same bytes the measurement scored. That is `HEAD`, not the index
    and not the working tree, so the question is asked twice: is the path in HEAD, and
    does anything differ between HEAD and what is on disk now.

    Neither question proves the working tree **has** the artifact, and for the bitstreams
    that distinction is real: under Git LFS a pointer-only checkout generally shows a clean
    `git diff HEAD`, because the comparison is the cleaned working file against the pointer
    blob and cleaning a pointer yields that pointer. What establishes possession is the
    SHA-256 comparison every caller already does against the manifest pin — a pointer file
    does not hash to the pinned bitstream. See `docs/ff_staging_producer.md` §2b/§2c; the
    LFS-side check of the pointer oid itself is listed there and is not implemented yet.

    **Absent git authority this refuses.** The stager's `is_ignored()` may decline to
    answer because it guards against a mistake before any evidence exists; here the
    answer *is* the evidence, and a measurement that cannot establish its artifacts are
    published is not a measurement with a caveat. A cold `git archive` export can exercise
    this function against a scratch repository — it cannot produce a measurement, and that
    is the intended consequence.
    """
    if not relatives:
        return []
    head = subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=REPO,
                          capture_output=True, text=True, check=False)
    if head.returncode != 0:
        return ["no git authority in this tree: the staged artifacts cannot be shown to "
                "be committed, and a certificate pins them by repository-relative path "
                "— refusing rather than assuming"]
    listed = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", "HEAD", "--",
                             *relatives], cwd=REPO, capture_output=True, text=True,
                            check=False)
    changed = subprocess.run(["git", "diff", "--name-only", "-z", "HEAD", "--", *relatives],
                             cwd=REPO, capture_output=True, text=True, check=False)
    if listed.returncode != 0 or changed.returncode != 0:
        return [f"git could not report on the staged references: "
                f"{(listed.stderr or changed.stderr).strip()}"]

    in_head = {entry for entry in listed.stdout.split("\0") if entry}
    differing = {entry for entry in changed.stdout.split("\0") if entry}
    problems: list[str] = []
    absent = [relative for relative in relatives if relative not in in_head]
    if absent:
        problems.append(
            f"{len(absent)} reference(s) are not in HEAD — staging that is only written, "
            f"or only `git add`ed, is not published (first: {absent[:2]})")
    if differing:
        problems.append(
            f"{len(differing)} reference(s) differ from HEAD, so what a clone would get "
            f"is not what would be scored (first: {sorted(differing)[:2]})")
    return problems


LFS_POINTER_VERSION = "https://git-lfs.github.com/spec/v1"
LFS_POINTER_LIMIT = 4096


POINTER_FIELDS = ("version", "oid", "size")


def parse_lfs_pointer(payload: bytes) -> tuple[str | None, str]:
    """`(oid, why-not)` for a Git LFS pointer blob, parsed strictly.

    Strictly, because the two failures this has to tell apart look alike from a distance:
    a path that never went through the filter (an ordinary blob — for a bitstream, several
    hundred KB of binary) and a path whose pointer is damaged. Both refuse, but a run that
    cannot say which is a run nobody can act on.

    "Strict" means exactly `version`, `oid`, `size`, in that order and nothing else. The
    LFS spec allows sorted `ext-…` extension fields, and nothing in this pipeline produces
    them: a pointer that grew one was written by something other than the filter this gate
    exists to confirm ran, which is a reason to stop rather than a case to tolerate. An
    earlier version collected the lines into a dict and only looked at the three it knew,
    so a pointer carrying arbitrary extra fields parsed clean while calling itself
    well-formed.
    """
    ordinary = "HEAD holds an ordinary Git blob, not an LFS pointer"
    if len(payload) > LFS_POINTER_LIMIT:
        return None, ordinary
    try:
        text = payload.decode("utf-8")
    except UnicodeDecodeError:
        return None, ordinary
    lines = text.splitlines()
    # The version line comes first or this is not a pointer at all. Deciding that from
    # the *whole* parse instead conflated the two answers: an ordinary short text blob
    # tripped a later rule and was reported as a damaged pointer, which sends a reader
    # looking for corruption when the real story is that the filter never ran.
    if not lines or lines[0] != f"version {LFS_POINTER_VERSION}":
        return None, ordinary
    fields = {}
    for index, line in enumerate(lines):
        name, separator, value = line.partition(" ")
        if not separator:
            return None, f"malformed LFS pointer: {line!r} has no value"
        if index >= len(POINTER_FIELDS) or name != POINTER_FIELDS[index]:
            return None, (f"malformed LFS pointer: expected exactly "
                          f"{'/'.join(POINTER_FIELDS)}, found {name!r} at line "
                          f"{index + 1}")
        fields[name] = value
    if len(fields) != len(POINTER_FIELDS):
        return None, (f"malformed LFS pointer: {len(fields)} field(s), expected "
                      f"{'/'.join(POINTER_FIELDS)}")
    oid = fields["oid"]
    if not oid.startswith("sha256:"):
        return None, f"malformed LFS pointer: oid {oid!r} is not sha256"
    digest = oid.removeprefix("sha256:")
    if not re.fullmatch(r"[0-9a-f]{64}", digest):
        return None, f"malformed LFS pointer: oid {digest!r} is not a sha256 hex digest"
    if not fields.get("size", "").isdigit():
        return None, f"malformed LFS pointer: size {fields.get('size')!r} is not a count"
    return digest, ""


def lfs_pointer_problems(pinned: list[tuple[str, str, str]],
                         ordinary: list[tuple[str, str]]) -> list[str]:
    """What HEAD says each reference *is* — read from HEAD, never from the worktree.

    Two lists, `(label, path, sha256)` for what must be an LFS pointer and
    `(label, path)` for what must not, because which kind a reference is is the caller's
    knowledge: this gate must not re-derive it from a file extension or a path shape, or
    it would hold its own opinion about a layout the manifest already states.

    The working file is the wrong witness twice over. A pointer-only checkout has bytes on
    disk that are not the bitstream, and a materialised one has bytes that are the
    bitstream whatever HEAD holds; neither tells you what a verifier's clone will resolve.
    So each pinned artifact's HEAD blob is read with `git cat-file` and must be a
    well-formed pointer whose **oid is exactly the manifest's pinned sha256** — the oid
    *is* the content hash, so that equality is what ties the published object to the
    measured bytes. The path must also be governed by the LFS filter, and `.gitattributes`
    — the file that decides that — must itself be in HEAD.

    The ordinary references are checked the other way, and that set is **the manifest, the
    prediction commitment and every attestation**: all three are ordinary Git files by
    ruling, and a pointer standing in for one would mean a mis-scoped attribute rule
    quietly moved reviewable evidence out of the repository. An earlier version of this
    gate received only the staging entries, so it could not see the manifest or the
    commitment at all — an attribute rule naming just `staging/*/staging_manifest.json`
    would have passed every check while the manifest itself left the repository.

    Raw reference strings are what get read and reported; the resolved path is used only
    for identity and safety, upstream of here.
    """
    problems: list[str] = []
    if subprocess.run(["git", "rev-parse", "--verify", "HEAD"], cwd=REPO,
                      capture_output=True, check=False).returncode != 0:
        return ["no git authority in this tree: HEAD holds no blobs to read, so what a "
                "clone would resolve cannot be established"]
    if subprocess.run(["git", "cat-file", "-e", "HEAD:.gitattributes"], cwd=REPO,
                      capture_output=True, check=False).returncode != 0:
        problems.append(
            ".gitattributes is not in HEAD, so nothing publishes the rule that keeps "
            "staged bitstreams in Git LFS — a staging committed without it would push "
            "the bitstreams into ordinary history, which no later commit undoes")

    def head_blob(relative: str) -> bytes | None:
        found = subprocess.run(["git", "cat-file", "blob", f"HEAD:{relative}"], cwd=REPO,
                               capture_output=True, check=False)
        return found.stdout if found.returncode == 0 else None

    for label, relative, sha256 in pinned:
        blob = head_blob(relative)
        if blob is None:
            problems.append(f"{label} {relative} is not in HEAD")
            continue
        oid, why = parse_lfs_pointer(blob)
        if oid is None:
            problems.append(f"{label} {relative}: {why}")
        elif oid != sha256:
            problems.append(
                f"{label} {relative}: the LFS pointer in HEAD names object {oid[:12]}…, "
                f"the manifest pins {sha256[:12]}…")
        attribute = subprocess.run(["git", "check-attr", "filter", "--", relative],
                                   cwd=REPO, capture_output=True, text=True, check=False)
        if not attribute.stdout.rstrip().endswith(": filter: lfs"):
            problems.append(f"{label} {relative}: no LFS filter governs this path "
                            f"({attribute.stdout.strip() or 'unset'})")

    for label, relative in ordinary:
        blob = head_blob(relative)
        if blob is None:
            problems.append(f"{label} {relative} is not in HEAD")
            continue
        if parse_lfs_pointer(blob)[0] is not None:
            problems.append(
                f"{label} {relative}: HEAD holds an LFS pointer, but this is an ordinary "
                "Git file by ruling — the attribute rule is mis-scoped and reviewable "
                "evidence has left the repository")
    return problems


def attestation_problems(specimen_id: str, attestation: dict, entry: dict,
                         plan_specimen: dict, commitment_sha256: str) -> list[str]:
    """Identity and integrity of one staged attestation — deliberately not more.

    Whether the routed cell facts rebuild into the `/resolved/*` summaries is
    `host.verify_certificate.ff_formal_attestation_errors`' question, and the verifier
    asks it of the certificate. Re-asking it here would put a producer-side imitation of
    the consumer's rule in the measurement path, where it could drift and agree with
    itself. What this tool must establish is narrower and it must establish it itself:
    that the record staged under this specimen id really describes this committed
    specimen and really pins the bytes that are about to be parsed.
    """
    problems: list[str] = []
    prefix = f"staged {specimen_id}"
    if attestation.get("specimen_id") != specimen_id:
        problems.append(f"{prefix}: attestation names specimen "
                        f"{attestation.get('specimen_id')!r}")
    if attestation.get("schema_version") != entry["attestation"]["schema_version"]:
        problems.append(f"{prefix}: attestation schema_version differs from the manifest entry")
    if attestation.get("prediction_commitment", {}).get("sha256") != commitment_sha256:
        problems.append(f"{prefix}: attestation pins a different prediction commitment")
    if attestation.get("outputs", {}).get("spec.bit") != entry["bitstream"]["sha256"]:
        problems.append(f"{prefix}: attested output bitstream is not the staged one")

    build = attestation.get("source_build") or {}
    if build.get("completed") is not True:
        problems.append(f"{prefix}: source build is not completed")
    if build.get("variant") != plan_specimen["variant"]:
        problems.append(f"{prefix}: built variant {build.get('variant')!r} is not the "
                        f"committed {plan_specimen['variant']!r}")
    if build.get("instance") != plan_specimen["site"]:
        problems.append(f"{prefix}: built instance {build.get('instance')!r} is not the "
                        f"committed {plan_specimen['site']!r}")
    if build.get("artifacts", {}).get("spec.bit") != entry["bitstream"]["sha256"]:
        problems.append(f"{prefix}: stamped bitstream is not the staged one")

    recipe = build.get("recipe") or {}
    if recipe.get("commitment") != commitment_sha256:
        problems.append(f"{prefix}: build recipe pins a different commitment")
    if recipe.get("build_seed") != plan_specimen["build_seed"]:
        problems.append(f"{prefix}: build recipe seed {recipe.get('build_seed')!r} is not "
                        f"the committed {plan_specimen['build_seed']!r}")
    for field in ("part", "vivado_version"):
        # Copied into the specimen record below, so their absence is a refusal rather
        # than a null field the certificate would carry into the verifier.
        if not recipe.get(field):
            problems.append(f"{prefix}: build recipe has no {field}")
    if design_source(recipe) is None:
        problems.append(f"{prefix}: build recipe does not name exactly one design source "
                        "(.v) among its recipe sources")
    return problems


def design_source(recipe: dict) -> str | None:
    """The specimen design's hash, for the certificate's `design_source_sha256`.

    Certificate 1.6 still requires that field on every specimen, but a
    `specimen_attestation` **2.0** has no `inputs.design_sha256` to copy — 2.0 replaced
    the single design input with a recipe whose `sources` map pins every file that can
    change what a build means. The design among them is the specimen Verilog, and the
    formal recipe carries exactly one `.v`.

    "Exactly one" is the rule rather than "the first": picking one of several would make
    the field's meaning depend on sort order, and a recipe that grew a second `.v` is a
    change to what a specimen *is*, which should stop the run and be looked at.
    """
    verilog = [value for name, value in sorted(recipe.get("sources", {}).items())
               if name.endswith(".v")]
    return verilog[0] if len(verilog) == 1 else None


def load_staging(manifest_path: Path, commitment_path: Path, commitment_sha256: str,
                 doc: dict, run_id: str, *, tracked_check=None,
                 pointer_check=None) -> tuple[dict, dict, dict]:
    """`(manifest_reference, entries_by_id, attestations_by_id)`, or refuse the whole run.

    Every check here runs before the caller opens one bitstream, and every failure is a
    refusal rather than a recorded problem. Both properties are deliberate: a measurement
    is a claim about a *complete* committed set, so "we scored the 183 specimens whose
    references verified" is not a weaker result — it is a result about a set nobody
    committed to, wearing the accounting of one that was.

    Nothing is reconstructed. `specimen_id` selects an entry; the paths inside that entry
    are what get resolved and read. The manifest is the only place this tool learns where
    an artifact lives.
    """
    tracked_check = tracked_check or uncommitted_references
    pointer_check = pointer_check or lfs_pointer_problems
    problems: list[str] = []

    if not manifest_path.is_file():
        raise SystemExit(f"staging manifest does not exist: {manifest_path}")
    try:
        manifest_relative = str(manifest_path.resolve().relative_to(REPO))
    except ValueError:
        raise SystemExit(
            f"staging manifest {manifest_path} is outside the repository; certificate 1.6 "
            "pins it by repository-relative path") from None
    try:
        # One read: the hash that goes into the certificate and the document every check
        # below reads are the same bytes. Hashing the file and then re-opening it lets a
        # swap in between produce a record that pins A and was computed from B.
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(manifest_bytes)
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"cannot read staging manifest {manifest_relative}: {exc}") from None
    manifest_digest = hashlib.sha256(manifest_bytes).hexdigest()

    # Shape first, and it is fatal on its own: every check below reads named fields, and
    # reading them out of a document whose shape was never established is how a
    # reassuring pass gets computed over something that is not a manifest.
    findings = validate_external_schema(manifest, STAGING_SCHEMA, "staging manifest")
    if findings:
        raise SystemExit("refusing to measure: staging manifest does not validate:\n  "
                         + "\n  ".join(findings[:10]))

    reference = manifest["prediction_commitment"]
    if manifest["run_id"] != run_id:
        problems.append(f"staging run_id {manifest['run_id']!r} is not the run being "
                        f"measured ({run_id!r})")
    if reference["run_id"] != run_id:
        problems.append(f"staged commitment run_id {reference['run_id']!r} is not {run_id!r}")
    if reference["sha256"] != commitment_sha256:
        problems.append("staged commitment hash differs from the predictions being scored")
    for field, expected in (("schema_version", doc["schema_version"]),
                            ("seed", str(doc["seed"])),
                            ("totals", dict(doc["totals"]))):
        # Recomputed from the commitment document, never copied from the manifest: a
        # reference that describes itself proves nothing about what it points at.
        if reference[field] != expected:
            problems.append(f"staged commitment {field} differs from predictions.json")
    try:
        pinned_commitment = safe_child(REPO, reference["path"])
    except ValueError as exc:
        problems.append(f"staged commitment path: {exc}")
        pinned_commitment = None
    if pinned_commitment is not None:
        if not pinned_commitment.is_file():
            problems.append(f"staged commitment file does not exist: {reference['path']}")
        elif pinned_commitment != commitment_path.resolve():
            problems.append(f"staging pins a different predictions.json: {reference['path']}")
        elif hash_file(pinned_commitment) != commitment_sha256:
            problems.append("staged commitment file no longer hashes to its pinned value")

    committed = {item["specimen_id"]: item for item in doc["specimens"]}
    entries: dict[str, dict] = {}
    attestations: dict[str, dict] = {}
    # Keyed by the *resolved* file, not the reference string. Two spellings of one path —
    # `d/spec.bit` and `d/./spec.bit`, or a symlink alias — are two references and one
    # artifact, and a string-keyed check calls that two staged specimens. The raw strings
    # still travel into the measurement unchanged; only the identity test is canonical.
    seen_targets: dict[Path, str] = {}
    to_check: list[str] = [manifest_relative, reference["path"]]

    for index, entry in enumerate(manifest["specimens"]):
        specimen_id = entry["specimen_id"]
        if specimen_id in entries:
            problems.append(f"staging specimens[{index}] duplicates {specimen_id!r}")
            continue
        entries[specimen_id] = entry
        verified: dict[str, bytes | Path] = {}
        for label in ("bitstream", "attestation"):
            pinned = entry[label]
            relative = pinned["path"]
            to_check.append(relative)
            try:
                path = safe_child(REPO, relative)
            except ValueError as exc:
                problems.append(f"staged {specimen_id} {label}: {exc}")
                continue
            owner = seen_targets.setdefault(path, f"{specimen_id}/{label}")
            if owner != f"{specimen_id}/{label}":
                problems.append(f"staged {specimen_id}: {label} {relative!r} resolves to "
                                f"the same file as {owner}")
            if not path.is_file():
                problems.append(f"staged {specimen_id} {label} does not exist: {relative}")
                continue
            if label == "attestation":
                # Read once, hash and parse the same bytes — the record's own hash must
                # describe the document that was read, not a re-open of the path.
                try:
                    payload = path.read_bytes()
                except OSError as exc:
                    problems.append(f"staged {specimen_id}: cannot read attestation: {exc}")
                    continue
                actual = hashlib.sha256(payload).hexdigest()
            else:
                # Streamed: 184 bitstreams are not held in memory. `frames_of` re-reads
                # and re-checks against this same pinned hash before parsing, so the bytes
                # that get scored are hashed in the same read that parses them.
                payload = path
                actual = hash_file(path)
            if actual != pinned["sha256"]:
                problems.append(f"staged {specimen_id} {label} does not match its pinned "
                                f"hash: {relative}")
                continue
            verified[label] = payload

        plan_specimen = committed.get(specimen_id)
        if plan_specimen is None:
            # Reported by the set-equality check below; nothing further can be said about
            # a specimen the commitment never named.
            continue
        if "attestation" not in verified:
            continue
        try:
            attestation = json.loads(verified["attestation"])
        except json.JSONDecodeError as exc:
            problems.append(f"staged {specimen_id}: cannot parse attestation: {exc}")
            continue
        found = attestation_problems(specimen_id, attestation, entry, plan_specimen,
                                     commitment_sha256)
        problems.extend(found)
        # `not found` is an equivalent mutant today and is kept deliberately: any problem
        # refuses the whole run below, so nothing can read this record either way. It is
        # here for the day someone softens one of these refusals into a report — that is
        # the moment a record that failed its own identity checks becomes reachable.
        if not found and "bitstream" in verified:
            attestations[specimen_id] = attestation

    missing = sorted(set(committed) - set(entries))
    extra = sorted(set(entries) - set(committed))
    if missing or extra:
        problems.append(
            f"staging is not the committed set: {len(entries)} entries for "
            f"{len(committed)} committed specimens (missing {len(missing)}, "
            f"extra {len(extra)}; first missing {missing[:2]}, first extra {extra[:2]})")

    # Last, because it is the most expensive and the least informative when something
    # simpler is already wrong — but not optional: a measurement whose evidence is not
    # published is one no verifier can repeat.
    to_check.append(".gitattributes")
    published = tracked_check(to_check)
    problems.extend(published)
    if not published:
        # Only once publication holds: with a path missing from HEAD every pointer read
        # fails too, and 184 derived complaints would bury the one that explains them.
        #
        # Both lists are assembled here, because this is where a reference's kind is
        # known. Everything the measurement will read is in one of them — the two JSON
        # documents that frame the run, every attestation, every bitstream — and a
        # reference in neither is a reference nobody judged.
        problems.extend(pointer_check(
            [(f"staged {specimen_id} bitstream", entry["bitstream"]["path"],
              entry["bitstream"]["sha256"])
             for specimen_id, entry in sorted(entries.items())],
            [("staging manifest", manifest_relative),
             ("prediction commitment", reference["path"])]
            + [(f"staged {specimen_id} attestation", entry["attestation"]["path"])
               for specimen_id, entry in sorted(entries.items())]))

    if problems:
        raise SystemExit(
            "refusing to measure: the staging manifest does not verify "
            f"({len(problems)} problem(s)). Nothing was scored and nothing was written.\n  "
            + "\n  ".join(problems[:12])
            + (f"\n  ... and {len(problems) - 12} more" if len(problems) > 12 else ""))

    return ({"path": manifest_relative, "sha256": manifest_digest,
             "schema_version": manifest["schema_version"]},
            entries, attestations)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--staging-manifest", type=Path, required=True,
                    help="the specimen_staging 1.0.0 manifest written by "
                         "gate_stage_ff_formal.py --stage; the only source of specimens, "
                         "bitstreams and attestations")
    ap.add_argument("--expect-sha256")
    ap.add_argument("--out", type=Path)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    digest = sha256_file(pred_path)
    if args.expect_sha256 and digest != args.expect_sha256:
        raise SystemExit(f"predictions hash {digest} != committed — refusing to score")
    doc = json.loads(pred_path.read_text())
    if doc["bit_class"] != BIT_CLASS:
        raise SystemExit(f"predictions are for {doc['bit_class']}, not {BIT_CLASS}")
    print(f"predictions: {digest}"
          + ("  (matches the committed hash)" if args.expect_sha256 else ""))

    grid = json.loads(TILEGRID.read_text())
    spec = json.loads(SPEC.read_text())
    pattern = re.compile(next(c["feature_regex"] for c in spec["bit_classes"]
                              if c["id"] == BIT_CLASS))
    cols, layout = column_map(), device_layout()
    index = tile_index()
    by_id = {s["specimen_id"]: s for s in doc["specimens"]}

    # The whole evidence set, verified before a frame is parsed. Every reference below is
    # the manifest's own; nothing is copied into the run directory and no path is built
    # from a specimen id.
    staging_reference, staged, attestation_cache = load_staging(
        args.staging_manifest, pred_path, digest, doc, args.run.name)
    print(f"staging:     {staging_reference['sha256']}  "
          f"{len(staged)} specimens from {staging_reference['path']}")

    address_problems: list[str] = []
    semantic_findings: list[str] = []

    def load_frames(specimen_id: str) -> dict:
        pinned = staged[specimen_id]["bitstream"]
        path = safe_child(REPO, pinned["path"])
        # `load_staging` hashed this file; that read is over. These are the bytes that
        # will actually be scored, so they are hashed and parsed in one read: without
        # that, a file swapped between verification and parsing produces a measurement
        # carrying one hash and the frames of another. A mismatch is fatal, not a
        # recorded problem — nothing has been written yet and nothing will be. Every
        # re-parse after an eviction repeats this, so the check covers the whole run.
        data = path.read_bytes()
        if hashlib.sha256(data).hexdigest() != pinned["sha256"]:
            raise SystemExit(
                f"refusing to measure: {specimen_id} bitstream changed after staging "
                f"verification ({pinned['path']}) — nothing was written")
        return parse_frames(path, cols, layout, data=data)["frames"]

    frames = FrameCache(load_frames)

    def frames_of(specimen: dict) -> dict:
        return frames.frames_of(specimen["specimen_id"])

    specimen_records = []
    for specimen in doc["specimens"]:
        entry = staged[specimen["specimen_id"]]
        recipe = attestation_cache[specimen["specimen_id"]]["source_build"]["recipe"]
        block = grid[specimen["tile"]]["bits"]["CLB_IO_CLK"]
        specimen_records.append({
            "specimen_id": specimen["specimen_id"],
            "split": specimen["split"],
            "variant": specimen["variant"],
            "loc_site": specimen["site"],
            "tile": specimen["tile"],
            "tile_type": specimen["tile_type"],
            "tile_frame_base": block["baseaddr"],
            # preregistered, so the certificate carries the committed seed and the
            # verifier can compare it with the one the build stamped
            "build_seed": specimen["build_seed"],
            "part": recipe["part"],
            "vivado_version": recipe["vivado_version"],
            # required by the certificate schema; see `design_source()` for why a 2.0
            # attestation has no single field to copy it from
            "design_source_sha256": design_source(recipe),
            # Both references verbatim from the manifest entry. Certificate 1.6 requires
            # the attestation reference to equal the staging entry exactly, so adding a
            # convenience field here — or re-hashing a copy — breaks the record one layer
            # down, where it reads as the consumer rejecting the producer's evidence.
            "bitstream": dict(entry["bitstream"]),
            "bitstream_sha256": entry["bitstream"]["sha256"],
            "attestation": dict(entry["attestation"]),
        })

    # ---- endpoint pairs, read from the commitment -------------------------------
    # From schema 1.5 the other endpoint is `comparison_specimen_id`, preregistered per
    # prediction. It is READ here, never derived: deriving it — as this tool did while
    # every pair happened to be (base, variant) — would leave the producer free to pick
    # what an assertion is differenced against after the bitstreams exist, which is the
    # hole `docs/round10_request.md` closed. The verifier rebuilds the same pair set and
    # the same in-scope union from the same committed fields.
    scopes_by_pair, pair_of_feature = committed_pairs(doc)
    for feature, (comparison, asserting) in pair_of_feature.items():
        if comparison not in by_id or asserting not in by_id:
            raise SystemExit(f"{feature}: committed endpoint pair "
                             f"({asserting}, {comparison}) is not two known specimens")

    accounting = []
    false_positives: dict[tuple[str, str], list[dict]] = {}
    for (base_id, variant_id), scope in sorted(scopes_by_pair.items()):
        base, variant = by_id[base_id], by_id[variant_id]
        if base["split"] != variant["split"]:
            address_problems.append(
                f"{base_id}/{variant_id}: endpoints are in different splits")
        base_frames, variant_frames = frames_of(base), frames_of(variant)
        asserted_tiles = {base["tile"], variant["tile"]}
        raw = raw_diff(base_frames, variant_frames)
        buckets, class_claimed_out_of_scope = classify_diff(
            raw, scope, index, pattern, asserted_tiles)

        union = set().union(*buckets.values())
        overlaps = [(a, b) for i, a in enumerate(buckets) for b in list(buckets)[i + 1:]
                    if buckets[a] & buckets[b]]
        uncovered = raw - union
        if overlaps:
            address_problems.append(f"{base_id}/{variant_id}: buckets overlap {overlaps}")
        if uncovered:
            address_problems.append(f"{base_id}/{variant_id}: {len(uncovered)} raw diff bits in no bucket")
        if union - raw:
            address_problems.append(f"{base_id}/{variant_id}: {len(union - raw)} bucketed bits not in the raw diff")

        fp_bits = false_positive_bits(buckets, class_claimed_out_of_scope)
        false_positives[(base_id, variant_id)] = as_addresses(fp_bits)
        accounting.append({
            "site": base["site"],
            # Both ends by name: labelling a pair with one variant reads as "base" for
            # every key whose asserting endpoint is the baseline design.
            "variants": [base["variant"], variant["variant"]],
            "specimen_ids": [base_id, variant_id],
            "raw_diff_bits": len(raw),
            "counts": {name: len(value) for name, value in buckets.items()},
            "buckets": {name: as_addresses(value) for name, value in buckets.items()},
            "partition_exact": not (overlaps or uncovered or (union - raw)),
            "false_positive_addresses": as_addresses(fp_bits),
        })

    # ---- per prediction: endpoint observations decide TP/FN ---------------------
    totals = {split: {"tp": 0, "fn": 0, "fp": 0,
                      "member_identity": {"pass": 0, "fail": 0}}
              for split in ("mine", "holdout")}
    observed_by_specimen: dict[str, dict[tuple[int, int, int], int]] = {}
    results = []
    for prediction in sorted(doc["predictions"], key=lambda p: (p["specimen_id"], p["feature"])):
        feature_specimen = by_id[prediction["specimen_id"]]
        pair = pair_of_feature.get(prediction["feature"])
        if pair is None:
            address_problems.append(f"{prediction['feature']}: no endpoint pair — cannot score")
            continue
        # `pair` is (committed comparison endpoint, asserting endpoint), so the other end
        # is the comparison endpoint by construction — not something to work out here.
        other_id, asserting_id = pair
        if asserting_id != prediction["specimen_id"]:
            raise SystemExit(f"{prediction['feature']}: pair does not name its own "
                             "asserting specimen — refusing")
        feature_bits = read_tile_bits(
            frames_of(feature_specimen),
            grid[feature_specimen["tile"]]["bits"]["CLB_IO_CLK"])
        other_bits = read_tile_bits(
            frames_of(by_id[other_id]),
            grid[by_id[other_id]["tile"]]["bits"]["CLB_IO_CLK"])

        split = prediction["split"]
        transition = prediction["expected_transition"]
        observed_assignments = []
        matched = True
        for item in prediction["predicted_assignments"]:
            token = item["token"].lstrip("!")
            after = feature_bits.get(token)
            before = other_bits.get(token)
            observed_assignments.append({
                "address": item["address"],
                "observed_value": after,
                "before_value": before,
                "after_value": after,
            })
            if after != item["expected_value"] or before != transition["before"] \
                    or after != transition["after"]:
                matched = False
            for specimen_id, value in ((prediction["specimen_id"], after), (other_id, before)):
                seen = observed_by_specimen.setdefault(specimen_id, {})
                key = address_tuple(item["address"])
                if seen.setdefault(key, value) != value:
                    address_problems.append(
                        f"{specimen_id}: two observed values for {item['address']}")

        assertion = prediction["semantic_assertion"]
        # Read straight out of the staged record whose hash the manifest pins — not out
        # of a copy this tool made, which is what the reference in the certificate would
        # then have described.
        attestation = attestation_cache[prediction["specimen_id"]]
        observed_semantic = resolve_pointer(attestation, assertion["attestation_field"])
        semantic_passed = semantic_verdict(matched, observed_semantic,
                                           assertion["expected_value"])
        if not semantic_passed:
            # A semantic finding, never an address problem. `semantic_findings` is
            # reported and carried into the record; it must not reach the address
            # decision, or a naming claim could sink an addressing result that the
            # bitstream itself confirmed. Both ways of failing are recorded, so the
            # count and the findings list cannot disagree.
            reason = (f"attestation field {assertion['attestation_field']} is "
                      f"{observed_semantic!r}, preregistered "
                      f"{assertion['expected_value']!r}"
                      if matched else
                      "the addressing did not match, so the member this names was not "
                      "the one the evidence selected")
            semantic_findings.append(
                f"{prediction['feature']}: {reason} — the naming claim is not auditable")

        totals[split]["tp" if matched else "fn"] += 1
        totals[split]["member_identity"]["pass" if semantic_passed else "fail"] += 1
        results.append({
            "prediction_specimen_id": prediction["specimen_id"],
            "feature": prediction["feature"],
            "split": split,
            "rule_file": prediction["rule_file"],
            # the preregistered comparison endpoint, copied — the verifier compares this
            # field with the commitment and rejects any other value
            "baseline_specimen_id": other_id,
            "feature_specimen_id": prediction["specimen_id"],
            "predicted_assignments": prediction["predicted_assignments"],
            "expected_transition": transition,
            "semantic_assertion": assertion,
            "observed_assignments": observed_assignments,
            "semantic_outcome": {
                "kind": "member_identity",
                "semantic": True,
                "passed": semantic_passed,
                "predicted_member": assertion["predicted_member"],
                "attestation_field": assertion["attestation_field"],
                "expected_value": assertion["expected_value"],
                "observed_value": observed_semantic,
            },
            "verdict": "matched" if matched else "mismatched",
        })

    # FP is a pair-level count, not a per-result one: one address wrong in one pair is
    # one FP however many features that pair carries. Charged to the pair's split.
    # Both ends of a pair are the same site instance and therefore the same split; the
    # accounting loop above records a problem if that ever stops being true, so reading
    # it off either end is safe here.
    for (base_id, _variant_id), addresses in false_positives.items():
        totals[by_id[base_id]["split"]]["fp"] += len(addresses)

    print(f"\n  results: {len(results)} of {len(doc['predictions'])} predictions scored")
    for split in ("mine", "holdout"):
        t = totals[split]
        print(f"    {split:<8} tp={t['tp']:>4} fn={t['fn']:>4} fp={t['fp']:>4}  "
              f"member_identity {t['member_identity']['pass']}/"
              f"{t['member_identity']['pass'] + t['member_identity']['fail']}")
    print(f"\n  frames: {frames.parses} parse(s) over {len(doc['specimens'])} specimens, "
          f"cache {frames.size}, {frames.evictions} eviction(s)")
    print(f"  pair accounting: {len(accounting)} pairs, "
          f"{sum(1 for a in accounting if not a['partition_exact'])} not exact")
    for record in accounting:
        counts = record["counts"]
        if counts["ownership_unknown"] or counts["unattributed"] or record["false_positive_addresses"]:
            print(f"    {format_pair_alarm(record)}")

    holdout = totals["holdout"]
    committed_holdout = doc["totals"]["holdout_predictions"]
    decision = address_decision(totals, accounting, address_problems, committed_holdout)
    semantic_decision = "FAIL" if holdout["member_identity"]["fail"] else "PASS"
    print(f"\n  holdout ADDRESS decision: {decision}")
    print(f"  tp={holdout['tp']}/{committed_holdout} fn={holdout['fn']} fp={holdout['fp']}")
    print(f"  holdout SEMANTIC decision (isolated, never contributes to the above): "
          f"{semantic_decision}")
    print(f"  member_identity pass={holdout['member_identity']['pass']} "
          f"fail={holdout['member_identity']['fail']}")
    for problem in address_problems[:15]:
        print(f"  ADDRESS PROBLEM {problem}")
    if len(address_problems) > 15:
        print(f"  ... and {len(address_problems) - 15} more")
    for finding in semantic_findings[:15]:
        print(f"  SEMANTIC FINDING {finding}")
    if len(semantic_findings) > 15:
        print(f"  ... and {len(semantic_findings) - 15} more")

    if args.out:
        args.out.write_text(json.dumps({
            "schema": "gate_measurement",
            "schema_version": "1.6.0",
            "bit_class": doc["bit_class"],
            # The manifest reference, recomputed here and carried unchanged, so the
            # certifier copies it rather than re-deriving where the evidence lived.
            "staging_manifest": staging_reference,
            "prediction_commitment": {
                "run_id": args.run.name,
                "path": str(pred_path.resolve().relative_to(REPO)),
                "sha256": digest,
                "schema_version": doc["schema_version"],
                "seed": doc["seed"],
                "totals": doc["totals"],
            },
            "split_policy": doc["split_policy"],
            "specimens": specimen_records,
            "totals": totals,
            "results": results,
            "accounting": accounting,
            "decision": decision,
            "semantic_decision": semantic_decision,
            # Two lists, deliberately. `address_problems` sinks the address decision;
            # `semantic_findings` is reported and never does. Merging them back into one
            # `problems` field would restore the isolation defect at the record level.
            "address_problems": address_problems,
            "semantic_findings": semantic_findings,
        }, indent=2) + "\n")
        print(f"  wrote {args.out}")
    # The exit code follows the ADDRESS decision. A semantic-only failure exits zero and
    # says so loudly above; that is the 1.4 contract, not leniency.
    return 0 if decision == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
