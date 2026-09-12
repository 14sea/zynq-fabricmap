#!/usr/bin/env python3
"""B2 — the non-self-referential pin table of every adjudication-critical file in THIS repository
(host-only). `manifests/b2_manifest.json` pins the table's sha256; the runner verifies it before
opening a port or consuming a ruling, and `tests/test_b2_pins.py` regenerates it. The table is not
in the table (it cannot pin its own hash); the manifest is not in the table (it pins the table).

Why, in B1's words and for the same reason: under one manifest an edited verifier, schema,
firmware source or test would change a verdict silently. Every file below is a source of a
decision this package makes — the firmware the image is built from, the host tools that plan,
adjudicate, run, reconstruct and score, the schema the map is validated against, and the tests
that guard them.

What it adds over `b2_manifest.PINNED_CODE`: that list is the eight files the manifest hashes
inline, chosen because the manifest's own derivations depend on them. This table is the whole
decision surface, and it also re-verifies **B1's** instrument pin table against B1's manifest —
the B2 image runs on the B1 carrier under the B1 instrument, so a change there changes a B2
verdict too.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PINS = REPO_ROOT / "manifests/b2_instrument_pins.json"
SCHEMA = "b2_instrument_pins"
SCHEMA_VERSION = "1.0.0"

PINNED_GLOBS = (
    "host/b2_*.py", "host/b3_*.py", "host/gen_b2_data.py",
    "firmware/b2/*.c", "firmware/b2/*.h", "firmware/b2/Makefile", "firmware/b2/IMPORT.json",
    "firmware/b2/bsp/build.sh", "firmware/b2/bsp/lscript.ld",
    "tests/test_b2_*.py", "tests/test_b3_*.py",
    "schemas/self_map_v2.schema.json",
    # B1's own table, by content: the B2 image runs on the B1 carrier under the B1 instrument
    "manifests/b1_instrument_pins.json",
    # the normative documents the runtime is bound to. The preregistration is NOT here: it is
    # pinned separately by its frozen hash, and pinning it twice would let the two disagree.
    "docs/b2_architecture.md",
)
EXCLUDE_SUFFIXES = (".pyc",)


class PinRefusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files(root: Path = REPO_ROOT) -> list[Path]:
    out: set[Path] = set()
    for g in PINNED_GLOBS:
        for p in Path(root).glob(g):
            if p.is_file() and not p.name.endswith(EXCLUDE_SUFFIXES) and "__pycache__" not in p.parts:
                out.add(p)
    return sorted(out)


def generate(root: Path = REPO_ROOT) -> dict:
    files = {str(p.relative_to(root)): sha256_of(p) for p in pinned_files(root)}
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION, "globs": list(PINNED_GLOBS),
            "file_count": len(files), "files": files}


def verify(manifest: dict | None = None, root: Path = REPO_ROOT, pins_path: Path | None = None,
           b1_root: Path = REPO_ROOT) -> dict:
    """The table hashes to the manifest's pin, every pinned file exists and hashes, no file
    matching the globs is missing from the table, and B1's table verifies against B1's manifest.
    Every failure is a REFUSAL: a pin table that is merely present proves nothing."""
    import b2_manifest as bman
    root = Path(root)
    pins_path = Path(pins_path) if pins_path is not None else root / "manifests/b2_instrument_pins.json"
    manifest = manifest if manifest is not None else json.loads((root / "manifests/b2_manifest.json").read_text())
    pinned = (manifest.get("instrument_pins") or {}).get("sha256")
    if not pinned:
        raise PinRefusal("the manifest pins no b2_instrument_pins sha256")
    if not pins_path.is_file():
        raise PinRefusal(f"{pins_path} is absent")
    if sha256_of(pins_path) != pinned:
        raise PinRefusal(f"{pins_path} does not hash to the manifest's pin")
    try:
        table = json.loads(pins_path.read_text())
    except ValueError as exc:
        raise PinRefusal(f"{pins_path} is not readable JSON: {exc}") from None
    if not isinstance(table, dict) or table.get("schema") != SCHEMA or table.get("schema_version") != SCHEMA_VERSION:
        raise PinRefusal(f"{pins_path} is not a {SCHEMA} {SCHEMA_VERSION} document")
    files = table.get("files")
    if not isinstance(files, dict) or not files:
        raise PinRefusal(f"{pins_path} carries no file table")
    if table.get("file_count") != len(files):
        raise PinRefusal(f"{pins_path}: file_count {table.get('file_count')!r} is not the {len(files)} listed")
    bad = []
    for rel, sha in sorted(files.items()):
        if not isinstance(sha, str) or len(sha) != 64:
            bad.append(f"{rel}: not a 64-hex digest")
            continue
        p = root / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
        elif sha256_of(p) != sha:
            bad.append(f"{rel}: hash differs")
        if len(bad) >= 5:
            break
    if bad:
        raise PinRefusal("pinned files changed: " + "; ".join(bad))
    extra = sorted(set(generate(root)["files"]) - set(files))
    if extra:
        raise PinRefusal(f"files matching the pinned globs are not in the table: {extra[:5]}")
    # B1's table, against B1's manifest: this package's verdicts depend on it too
    import b1_pins
    try:
        b1 = b1_pins.verify(Path(b1_root) / "manifests/b1_instrument_pins.json",
                            json.loads((Path(b1_root) / "manifests/b1_manifest.json").read_text()))
    except b1_pins.PinRefusal as exc:
        raise PinRefusal(f"B1's instrument pin table: {exc}") from None
    if manifest.get("schema") != bman.SCHEMA:
        raise PinRefusal("the manifest given is not a b2_manifest document")
    return {"files_verified": len(files), "b1_files_verified": b1["files_verified"],
            "pins_sha256": pinned}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--out", type=Path, default=PINS)
    ap.add_argument("--manifest", type=Path, default=REPO_ROOT / "manifests/b2_manifest.json")
    a = ap.parse_args(argv)
    if a.generate:
        table = generate()
        a.out.write_text(json.dumps(table, indent=1, sort_keys=True) + "\n")
        print(f"pinned {table['file_count']} files -> {a.out} sha256 {sha256_of(a.out)}")
        return 0
    try:
        manifest = json.loads(a.manifest.read_text()) if a.manifest.is_file() else None
        print(verify(manifest, pins_path=a.out))
    except (PinRefusal, OSError, ValueError) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
