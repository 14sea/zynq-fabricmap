#!/usr/bin/env python3
"""Freeze the prjxray-db subset this repo depends on into data/, with a manifest.

Why this exists
---------------
The ratified approach (README "Ratified 2026-08-02") is: do not complete prjxray,
extract the needed subset and freeze it, then certify it per bit-class with our own
Vivado specimen-diff prediction gate.  Upstream prjxray-db is archived, so the
dependency is *tool* rot, not *data* rot: a frozen copy plus provenance resolves it
completely.  After certification the authority is our certificates; the frozen copy
is an index.

What it produces
----------------
    data/prjxray/<upstream path>   verbatim byte-identical copies
    data/MANIFEST.json             the freeze record (schema frozen_db_subset 1.0.0)

The manifest pins, for every frozen file: upstream path, sha256, size, line/entry
counts, and whether the file is byte-identical to its artix7 counterpart (the
2026-07-11 "7-series shares one fabric" audit, re-checked mechanically at every
extraction instead of remembered).  It also cuts the feature space into the
bit-classes declared in data/subset_spec.json and gives each one an entry count and
an (initially empty) certification slot for the prediction gate to fill.

Usage
-----
    scripts/extract_prjxray_subset.py --src /home/test/prjxray-db     # freeze
    scripts/extract_prjxray_subset.py --verify                        # no source needed
    scripts/extract_prjxray_subset.py --src ... --dry-run             # report only

--verify recomputes every hash and every count from data/ alone and exits non-zero on
any drift.  It is the integrity gate for the freeze and needs neither prjxray-db nor
Vivado.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
DATA = REPO / "data"
SPEC_PATH = DATA / "subset_spec.json"
MANIFEST_PATH = DATA / "MANIFEST.json"
PAYLOAD_DIR = DATA / "prjxray"

MANIFEST_SCHEMA = "frozen_db_subset"
MANIFEST_SCHEMA_VERSION = "1.0.0"
SUPPORTED_SPEC_MAJOR = 1


# --------------------------------------------------------------------------- io

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_spec() -> dict:
    spec = json.loads(SPEC_PATH.read_text())
    if spec.get("schema") != "prjxray_subset_spec":
        raise SystemExit(f"{SPEC_PATH}: not a prjxray_subset_spec")
    major = int(spec["schema_version"].split(".")[0])
    if major != SUPPORTED_SPEC_MAJOR:
        raise SystemExit(
            f"{SPEC_PATH}: schema_version {spec['schema_version']} is not supported "
            f"by this extractor (expects {SUPPORTED_SPEC_MAJOR}.x)"
        )
    return spec


def git_provenance(src: Path) -> dict:
    def git(*args: str) -> str | None:
        try:
            out = subprocess.run(
                ["git", "-C", str(src), *args],
                capture_output=True, text=True, check=True,
            )
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None
        return out.stdout.strip()

    status = git("status", "--porcelain")
    return {
        "path": str(src),
        "commit": git("rev-parse", "HEAD"),
        "commit_date": git("log", "-1", "--format=%cI"),
        "remote": git("config", "--get", "remote.origin.url"),
        "worktree_clean": (status == "") if status is not None else None,
    }


# ------------------------------------------------------------------- db parsing

def is_origin_info(rel: str) -> bool:
    return rel.endswith(".origin_info.db")


def parse_db(path: Path, role: str) -> tuple[list[str], int]:
    """Return (feature names, total non-empty lines) for a prjxray .db file.

    segbits:  "<FEATURE> <bit> [!bit ...]"
    ppips:    "<FEATURE> always|default|hint"
    mask:     "bit <frame>_<offset>"           -> no features
    *.origin_info.db: "<FEATURE> origin:<fuzzer> <bits...>"
    """
    features: list[str] = []
    lines = 0
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        lines += 1
        if role == "mask":
            continue
        features.append(line.split()[0])
    return features, lines


def db_payload(path: Path, role: str) -> dict[str, str]:
    """feature -> rule payload, for comparing two .db files by meaning.

    `origin:<fuzzer>` tokens are dropped: which fuzzer emitted a rule is provenance,
    not a rule difference.  Mask files have no features, so each line keys itself.
    """
    payload: dict[str, str] = {}
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        tokens = [t for t in line.split() if not t.startswith("origin:")]
        if role == "mask":
            payload[line] = ""
        else:
            payload[tokens[0]] = " ".join(sorted(tokens[1:]))
    return payload


def compare_db(a: Path, b: Path, role: str) -> dict:
    """Rule-level comparison of two .db files (ours vs the cross-family counterpart)."""
    pa, pb = db_payload(a, role), db_payload(b, role)
    only_a = sorted(set(pa) - set(pb))
    only_b = sorted(set(pb) - set(pa))
    conflicting = sorted(k for k in set(pa) & set(pb) if pa[k] != pb[k])
    return {
        "rule_equivalent": not (only_a or only_b or conflicting),
        "only_here": len(only_a),
        "only_there": len(only_b),
        "conflicting_payloads": len(conflicting),
        "examples": (only_a[:3] + only_b[:3] + conflicting[:3]) or None,
    }


def compile_classes(spec: dict) -> list[dict]:
    classes = []
    for cls in spec["bit_classes"]:
        classes.append({**cls, "_re": re.compile(cls["feature_regex"])})
    return classes


def classify(features: list[str], group_id: str, classes: list[dict]) -> tuple[dict[str, list[str]], list[str]]:
    """Assign each feature to exactly one applicable bit-class.

    Applicability is scoped by group: a class only sees files from its from_groups.
    A feature matching two applicable classes is an ambiguity and is fatal — the
    taxonomy is meant to be a partition, not a best-effort tagging.
    """
    applicable = [c for c in classes if group_id in c["from_groups"]]
    assigned: dict[str, list[str]] = {c["id"]: [] for c in applicable}
    unclassified: list[str] = []
    for feat in features:
        hits = [c for c in applicable if c["_re"].match(feat)]
        if len(hits) == 1:
            assigned[hits[0]["id"]].append(feat)
        elif not hits:
            unclassified.append(feat)
        else:
            raise SystemExit(
                f"ambiguous classification: {feat!r} matches "
                f"{[c['id'] for c in hits]} — fix data/subset_spec.json"
            )
    return assigned, unclassified


def tilegrid_summary(path: Path) -> dict:
    grid = json.loads(path.read_text())
    hist: dict[str, int] = {}
    for tile in grid.values():
        hist[tile.get("type", "?")] = hist.get(tile.get("type", "?"), 0) + 1
    return {
        "tiles_total": len(grid),
        "tile_type_counts": dict(sorted(hist.items(), key=lambda kv: (-kv[1], kv[0]))),
    }


# ---------------------------------------------------------------------- freeze

def build(spec: dict, src: Path | None, *, copy: bool, strict: bool = True) -> dict:
    """Build the manifest.  copy=False reads from data/ (verify), True from src.

    strict=False (verify) keeps going when a feature fails to classify, so the caller
    reports it as drift against the frozen manifest instead of aborting.
    """
    classes = compile_classes(spec)
    xfam = spec["cross_family_reference"]["family"] if spec.get("cross_family_reference") else None

    files: list[dict] = []
    class_features: dict[str, list[str]] = {c["id"]: [] for c in classes}
    unclassified: dict[str, list[str]] = {}
    origin_mismatch: list[str] = []
    feature_sets: dict[str, set[str]] = {}
    device_summary: dict | None = None
    xfam_checked = xfam_identical = xfam_equivalent = 0
    xfam_differing: list[dict] = []

    for group in spec["groups"]:
        for rel in group["files"]:
            frozen = PAYLOAD_DIR / rel
            if copy:
                assert src is not None
                origin = src / rel
                if not origin.is_file():
                    raise SystemExit(f"missing upstream file: {origin}")
                frozen.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(origin, frozen)
            elif not frozen.is_file():
                raise SystemExit(f"missing frozen file: {frozen}")

            digest = sha256_file(frozen)
            rec = {
                "path": str(frozen.relative_to(DATA)),
                "source_path": rel,
                "group": group["id"],
                "role": group["role"],
                "tier": group["tier"],
                "sha256": digest,
                "size_bytes": frozen.stat().st_size,
            }

            if rel.endswith(".db"):
                feats, lines = parse_db(frozen, group["role"])
                rec["lines"] = lines
                if group["role"] != "mask":
                    rec["features"] = len(feats)
                    feature_sets[rel] = set(feats)
                    if not is_origin_info(rel):
                        assigned, unc = classify(feats, group["id"], classes)
                        rec["bit_classes"] = {k: len(v) for k, v in assigned.items() if v}
                        for cid, fl in assigned.items():
                            class_features[cid].extend(fl)
                        if unc:
                            unclassified[rel] = unc

            # the artix7 identity claim, re-checked instead of remembered
            if group.get("cross_family_check") and xfam:
                rec["cross_family"] = {"family": xfam, "identical": None}
                if copy:
                    assert src is not None
                    counterpart = src / Path(rel).as_posix().replace(
                        f"{spec['target']['family']}/", f"{xfam}/", 1
                    )
                    if counterpart.is_file():
                        same = sha256_file(counterpart) == digest
                        cf = {
                            "family": xfam,
                            "counterpart": str(counterpart.relative_to(src)),
                            "identical": same,
                        }
                        if not same and rel.endswith(".db"):
                            cf.update(compare_db(frozen, counterpart, group["role"]))
                        rec["cross_family"] = cf
                        xfam_checked += 1
                        xfam_identical += int(same)
                        if not same:
                            xfam_equivalent += int(bool(cf.get("rule_equivalent")))
                            if not cf.get("rule_equivalent"):
                                xfam_differing.append(
                                    {"file": rel,
                                     "only_here": cf.get("only_here"),
                                     "only_there": cf.get("only_there"),
                                     "conflicting_payloads": cf.get("conflicting_payloads"),
                                     "examples": cf.get("examples")}
                                )

            files.append(rec)

            if rel.endswith("tilegrid.json"):
                device_summary = tilegrid_summary(frozen)

    # A non-empty origin_info file must describe exactly the feature set of its
    # parent db.  Several ppips_*.origin_info.db are empty upstream — that is a
    # missing provenance record, not a rule inconsistency, so it is reported
    # separately rather than as a mismatch.
    origin_empty: list[str] = []
    for rel, feats in feature_sets.items():
        if not is_origin_info(rel):
            continue
        parent = rel.replace(".origin_info.db", ".db")
        if not feats:
            origin_empty.append(rel)
        elif parent in feature_sets and feature_sets[parent] != feats:
            origin_mismatch.append(rel)

    if unclassified and strict and spec.get("unclassified_policy", "fail") == "fail":
        for rel, feats in unclassified.items():
            print(f"UNCLASSIFIED in {rel}: {len(feats)} features, e.g. {feats[:5]}",
                  file=sys.stderr)
        raise SystemExit(
            "unclassified features present and unclassified_policy=fail — "
            "extend bit_classes in data/subset_spec.json or narrow the group"
        )

    by_id = {c["id"]: c for c in classes}
    bit_classes = []
    for cid, feats in class_features.items():
        cls = by_id[cid]
        tiles = sorted({f.split(".")[0] for f in feats})
        bit_classes.append({
            "id": cid,
            "tier": cls["tier"],
            "priority": cls["priority"],
            "from_groups": cls["from_groups"],
            "feature_regex": cls["feature_regex"],
            "entries": len(feats),
            "distinct_features": len(set(feats)),
            "tile_types": tiles,
            "sample_features": sorted(set(feats))[:3],
            "board_safety": cls["board_safety"],
            # filled in by the specimen-diff prediction gate, not here
            "certification": {
                "status": "uncertified",
                "gate": None,
                "certificate": None,
                "tp": None,
                "fp": None,
            },
        })
    bit_classes.sort(key=lambda c: (c["priority"], c["id"]))

    manifest = {
        "schema": MANIFEST_SCHEMA,
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "spec": {
            "path": str(SPEC_PATH.relative_to(REPO)),
            "spec_id": spec["spec_id"],
            "schema_version": spec["schema_version"],
            "sha256": sha256_file(SPEC_PATH),
        },
        "target": spec["target"],
        "source": {**spec["source"], **(git_provenance(src) if (copy and src) else {})},
        "cross_family_check": {
            "reference_family": xfam,
            "files_checked": xfam_checked,
            "byte_identical": xfam_identical,
            "rule_equivalent_only": xfam_equivalent,
            "differing": xfam_differing,
            "note": "rule_equivalent_only = files whose bytes differ but whose "
                    "feature->bits rules are the same (origin:<fuzzer> provenance "
                    "tokens are ignored). 'differing' entries are real rule deltas.",
        },
        "device_summary": device_summary,
        "consistency": {
            "unclassified_features": sum(len(v) for v in unclassified.values()),
            "origin_info_feature_mismatch": origin_mismatch,
            "origin_info_empty_upstream": sorted(origin_empty),
        },
        "bit_classes": bit_classes,
        "files": files,
        "totals": {
            "files": len(files),
            "bytes": sum(f["size_bytes"] for f in files),
            "classified_features": sum(len(v) for v in class_features.values()),
        },
        "freeze_stamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return manifest


# ---------------------------------------------------------------------- verify

_VOLATILE = ("freeze_stamp",)


def strip_volatile(manifest: dict) -> dict:
    out = {k: v for k, v in manifest.items() if k not in _VOLATILE}
    # provenance of the *source checkout* is only knowable at extraction time
    out["source"] = {k: v for k, v in out["source"].items()
                     if k not in ("path", "commit", "commit_date", "remote", "worktree_clean")}
    # cross-family identity likewise needs the upstream tree
    out.pop("cross_family_check", None)
    out["files"] = [{k: v for k, v in f.items() if k != "cross_family"} for f in out["files"]]
    return out


def verify() -> int:
    if not MANIFEST_PATH.is_file():
        raise SystemExit(f"no manifest at {MANIFEST_PATH} — run an extraction first")
    stored = json.loads(MANIFEST_PATH.read_text())
    if stored.get("schema") != MANIFEST_SCHEMA:
        raise SystemExit(f"{MANIFEST_PATH}: not a {MANIFEST_SCHEMA} manifest")

    spec = load_spec()
    problems: list[str] = []

    if stored["spec"]["sha256"] != sha256_file(SPEC_PATH):
        problems.append("data/subset_spec.json changed since the freeze — re-extract")

    rebuilt = build(spec, None, copy=False, strict=False)
    a, b = strip_volatile(stored), strip_volatile(rebuilt)

    stored_files = {f["path"]: f for f in a["files"]}
    rebuilt_files = {f["path"]: f for f in b["files"]}
    for path in sorted(set(stored_files) | set(rebuilt_files)):
        if path not in stored_files:
            problems.append(f"{path}: present in data/ but not in the manifest")
        elif path not in rebuilt_files:
            problems.append(f"{path}: in the manifest but not frozen")
        elif stored_files[path] != rebuilt_files[path]:
            sf, rf = stored_files[path], rebuilt_files[path]
            diff = [k for k in set(sf) | set(rf) if sf.get(k) != rf.get(k)]
            problems.append(f"{path}: drift in {sorted(diff)} "
                            f"(manifest sha256 {sf.get('sha256', '?')[:12]}, "
                            f"actual {rf.get('sha256', '?')[:12]})")

    for key in ("bit_classes", "device_summary", "totals", "consistency", "target"):
        sa, sb = a.get(key), b.get(key)
        if key == "bit_classes":
            # certification is written back by the gate; compare only the frozen part
            def core(cs):
                return [{k: v for k, v in c.items() if k != "certification"} for c in cs]
            sa, sb = core(sa), core(sb)
        if sa != sb:
            problems.append(f"{key}: does not match the frozen data")

    orphans = [p for p in sorted(PAYLOAD_DIR.rglob("*")) if p.is_file()
               and str(p.relative_to(DATA)) not in rebuilt_files]
    problems += [f"{p.relative_to(DATA)}: untracked file under data/prjxray/" for p in orphans]

    if problems:
        print("FREEZE VERIFY: FAIL", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    t = stored["totals"]
    print(f"FREEZE VERIFY: OK — {t['files']} files, {t['bytes']:,} bytes, "
          f"{t['classified_features']:,} classified features, "
          f"{len(stored['bit_classes'])} bit classes")
    for c in stored["bit_classes"]:
        print(f"  {c['id']:<16} {c['entries']:>6} entries  tier={c['tier']:<9} "
              f"cert={c['certification']['status']}")
    return 0


# ------------------------------------------------------------------------ main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--src", type=Path, help="prjxray-db checkout to freeze from")
    ap.add_argument("--verify", action="store_true",
                    help="check data/ against data/MANIFEST.json (no source needed)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would be frozen; write nothing")
    args = ap.parse_args()

    if args.verify:
        return verify()

    spec = load_spec()
    src = args.src or Path(spec["source"]["default_path"])
    if not src.is_dir():
        raise SystemExit(f"prjxray-db checkout not found: {src} (pass --src)")

    if args.dry_run:
        n = sum(len(g["files"]) for g in spec["groups"])
        missing = [f for g in spec["groups"] for f in g["files"] if not (src / f).is_file()]
        print(f"spec {spec['spec_id']} ({spec['schema_version']}): "
              f"{len(spec['groups'])} groups, {n} files, "
              f"{len(spec['bit_classes'])} bit classes")
        print(f"source: {src} @ {git_provenance(src)['commit']}")
        print(f"missing upstream files: {missing or 'none'}")
        return 1 if missing else 0

    PAYLOAD_DIR.mkdir(parents=True, exist_ok=True)
    manifest = build(spec, src, copy=True)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n")

    x = manifest["cross_family_check"]
    t = manifest["totals"]
    print(f"froze {t['files']} files ({t['bytes']:,} bytes) from {src} "
          f"@ {manifest['source']['commit'][:12]}")
    print(f"cross-family ({x['reference_family']}): {x['byte_identical']}/{x['files_checked']} "
          f"byte-identical, +{x['rule_equivalent_only']} rule-equivalent")
    for d in x["differing"]:
        print(f"  RULE DELTA {d['file']}: only_here={d['only_here']} "
              f"only_there={d['only_there']} conflicting={d['conflicting_payloads']} "
              f"e.g. {d['examples']}")
    print(f"classified {t['classified_features']:,} features into "
          f"{len(manifest['bit_classes'])} classes:")
    for c in manifest["bit_classes"]:
        print(f"  {c['id']:<16} {c['entries']:>6} entries  tier={c['tier']:<9} "
              f"tiles={','.join(c['tile_types'][:4])}")
    if manifest["consistency"]["origin_info_feature_mismatch"]:
        print("WARNING: origin_info feature-set mismatch: "
              f"{manifest['consistency']['origin_info_feature_mismatch']}", file=sys.stderr)
    print(f"manifest: {MANIFEST_PATH.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
