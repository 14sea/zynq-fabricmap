#!/usr/bin/env python3
"""B1 — the non-self-referential pin table of every adjudication-critical file in THIS
repository (host-only). `manifests/b1_manifest.json` pins the table's sha256; the runner
verifies the table before opening a port or consuming a ruling, the adjudicator before
computing anything, and tests/test_b1_pins.py regenerates it. The table itself is not in the
table (it cannot pin its own hash); the manifest is not in the table (it pins the table).

Why: under one manifest, an edited verifier, schema, firmware source or RTL would change a
verdict silently (owner's review 2026-09-05, blocker 5). Every file below is a source of a
decision the package makes: the firmware the image is built from, the RTL the carrier is
built from, the host tools that plan, sign, run, reconstruct and score, the schema the map
is validated against, the tests that guard them.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
PINS = REPO_ROOT / "manifests/b1_instrument_pins.json"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"

PINNED_GLOBS = (
    "host/b1_*.py", "host/b1q_*.py", "host/gen_b1_data.py", "host/claimb_r1p_instrument.py",
    "firmware/b1/*.c", "firmware/b1/*.h", "firmware/b1/Makefile", "firmware/b1/IMPORT.json",
    "firmware/b1/bsp/build.sh", "firmware/b1/bsp/lscript.ld", "firmware/b1/bsp/src/*.c", "firmware/b1/bsp/include/*.h",
    "rtl/b1/*.v", "vivado/b1/*.tcl", "tb/b1/*.py", "tb/b1/*.v", "sim/b1/run.sh",
    "vivado/carrier/carrier_axi3_lite.v", "vivado/carrier/carrier_scorer.v", "vivado/carrier/carrier.xdc",
    "vivado/carrier/isolation_checks.tcl", "vivado/carrier/generated/*",
    "schemas/self_map_v2.schema.json", "tests/test_b1_*.py",
    "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/local_map.json",
    "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json",
    "manifests/claimb_round1prime_instrument_pins.json",
    # the normative documents the runtime is bound to (owner's review 2026-09-05, blocker 4):
    # the contract, the qualification criteria, the architecture. (The preregistration is
    # pinned separately by its frozen hash.)
    "docs/b1_carrier_contract.md", "docs/b1_carrier_qualification.md", "docs/b1_architecture.md",
)
EXCLUDE_SUFFIXES = (".pyc",)


class PinRefusal(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def pinned_files() -> list[Path]:
    out: set[Path] = set()
    for g in PINNED_GLOBS:
        for p in REPO_ROOT.glob(g):
            if p.is_file() and not p.name.endswith(EXCLUDE_SUFFIXES) and "__pycache__" not in p.parts:
                out.add(p)
    return sorted(out)


def generate() -> dict:
    files = {str(p.relative_to(REPO_ROOT)): sha256_of(p) for p in pinned_files()}
    return {"schema": "b1_instrument_pins", "schema_version": "1.0.0", "globs": list(PINNED_GLOBS),
            "file_count": len(files), "files": files}


def verify(pins_path: Path = PINS, manifest: dict | None = None) -> dict:
    manifest = manifest or json.loads(MANIFEST.read_text())
    want = (manifest.get("pins") or {}).get("sha256")
    if not want:
        raise PinRefusal("the manifest pins no b1_instrument_pins sha256")
    if not pins_path.is_file() or sha256_of(pins_path) != want:
        raise PinRefusal(f"{pins_path} does not hash to the manifest's pin")
    pins = json.loads(pins_path.read_text())
    bad = []
    for rel, sha in pins["files"].items():
        p = REPO_ROOT / rel
        if not p.is_file():
            bad.append(f"{rel}: missing")
        elif sha256_of(p) != sha:
            bad.append(f"{rel}: hash differs")
        if len(bad) >= 5:
            break
    if bad:
        raise PinRefusal("pinned files changed: " + "; ".join(bad))
    now = generate()
    extra = sorted(set(now["files"]) - set(pins["files"]))
    if extra:
        raise PinRefusal(f"files matching the pinned globs are not in the table: {extra[:5]}")
    return {"files_verified": len(pins["files"])}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--generate", action="store_true")
    ap.add_argument("--out", type=Path, default=PINS)
    a = ap.parse_args(argv)
    if a.generate:
        pins = generate()
        a.out.write_text(json.dumps(pins, indent=1, sort_keys=True) + "\n")
        print(f"pinned {pins['file_count']} files -> {a.out} sha256 {sha256_of(a.out)}")
        return 0
    try:
        print(verify(a.out))
    except PinRefusal as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
