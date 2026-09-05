#!/usr/bin/env python3
"""B1 — refresh the manifest's DERIVED sections from the tree (host-only).

    b1_manifest.py [--withdraw <image sha256> <reason>]

Rewrites, in manifests/b1_manifest.json, only what the tree determines:
  image      ← evidence/b1/build_evidence.json (sha256, elf, bytes, evidence hash; board_ready
               stays false — it is set true by nothing but a ruling that the manifest is frozen)
  carrier    ← builds/b1/b1_build.json + carrier_manifest.json (bitstream sha256, nonce seed,
               wns, isolation, the qualification flag — always false until the owner's
               `whole-of-run B1 carrier qualification` ruling; docs/b1_carrier_qualification.md)
  signer     ← host/b1_sign_arm.py (path, sha256, contract)
  pins       ← manifests/b1_instrument_pins.json (path, sha256) — generate the table FIRST
  history    ← appends a WITHDRAWN entry for --withdraw (never removes one)
Everything else (prereg, universe, seeds, plan, prediction, rulings, board) is left as it is;
plan/prediction are pinned by `b1_plan.py --write-manifest`. Run order for a refresh:
  build image (b1_build_evidence.py --build) → b1_manifest.py → b1_plan.py --write-manifest
  → b1_pins.py --generate → b1_manifest.py (pins hash) → tests.
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B1_VARIANT = "0x42310001"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def refresh(manifest: dict, withdraw: tuple[str, str] | None = None) -> dict:
    ev_path = REPO_ROOT / "evidence/b1/build_evidence.json"
    ev = json.loads(ev_path.read_text())
    im = ev["image"]
    manifest["image"] = {"path": im["path"], "sha256": im["sha256"], "elf_sha256": im["elf_sha256"], "bytes": im["bytes"],
                         "load_address": im["load_address"], "entry": im["entry"], "board_ready": False,
                         "build_evidence": {"path": "evidence/b1/build_evidence.json", "sha256": sha(ev_path),
                                            "reproduced_byte_identical": ev["reproducibility"]["reproduced_byte_identical"],
                                            "worktree_dirty_at_build": ev["git"]["worktree_dirty"], "head_at_build": ev["git"]["head"]},
                         "note": "the binary is not committed (bsp/out is gitignored, as the instrument's is); it is rebuilt byte-identically "
                                 "by firmware/b1/bsp/build.sh from the pinned sources and toolchain, and the runner refuses any image whose "
                                 "sha256 is not this one. board_ready is set by a ruling, never by this tool."}
    bd = REPO_ROOT / "builds/b1"
    build = json.loads((bd / "b1_build.json").read_text())
    car = json.loads((bd / "carrier_manifest.json").read_text())
    if car["bitstream_sha256"] != build["bitstream_sha256"]:
        raise SystemExit("builds/b1: carrier_manifest.json and b1_build.json name different bitstreams")
    if (bd / "b1.bit").is_file() and sha(bd / "b1.bit") != build["bitstream_sha256"]:
        raise SystemExit("builds/b1/b1.bit does not hash to b1_build.json")
    manifest["carrier"] = {"bitstream": "builds/b1/b1.bit", "bitstream_sha256": build["bitstream_sha256"], "bitstream_bytes": car["bitstream_bytes"],
                           "build_record": {"path": "builds/b1/b1_build.json", "sha256": sha(bd / "b1_build.json")},
                           "carrier_manifest": {"path": "builds/b1/carrier_manifest.json", "sha256": sha(bd / "carrier_manifest.json")},
                           "isolation": {"path": "builds/b1/isolation.txt", "sha256": sha(bd / "isolation.txt"), "result": build["cell_isolation"]},
                           "nonce_seed": car["nonce_seed"] if "nonce_seed" in car else build["nonce_seed"],
                           "variant": B1_VARIANT, "gate": build["gate"], "wns_ns": build["wns_ns"], "icape2_cells": build["icape2_cells"],
                           "part": build["part"], "vivado": build["vivado"], "frame_table_sha256": car["frame_table_sha256"],
                           "contract": "docs/b1_carrier_contract.md", "qualification": "docs/b1_carrier_qualification.md",
                           "qualified": False,
                           "note": "the B1 carrier (SEMANTIC_GATE=0: the PL verifies the signature and checks the sweep completed, and "
                                   "NEVER compares the readout with the signed table slots, which are the zero words). Built host-only; "
                                   "qualified is set true by nothing but the owner's `whole-of-run B1 carrier qualification` ruling after "
                                   "the qualification session on 17A6 — the runner refuses a B1 session on an unqualified carrier."}
    manifest["carrier"]["nonce_seed"] = f"0x{int(manifest['carrier']['nonce_seed'], 16):016x}"
    sp = REPO_ROOT / "host/b1_sign_arm.py"
    manifest["signer"] = {"path": "host/b1_sign_arm.py", "sha256": sha(sp), "contract": "b1-nonsemantic-v1",
                          "note": "signs commit ‖ twelve zero table words ‖ nonce; the semantic oracle is disarmed in-process; "
                                  "the runner refuses a sign_reply with any non-zero table (rule iii-B1, host/b1_records.py)"}
    pins = REPO_ROOT / "manifests/b1_instrument_pins.json"
    manifest["pins"] = {"path": "manifests/b1_instrument_pins.json", "sha256": sha(pins) if pins.is_file() else None,
                        "note": "every adjudication-critical fabricmap file (host/b1_pins.py PINNED_GLOBS); verified by the runner "
                                "before the port is opened and by the adjudicator before any verdict"}
    manifest["rulings_required"] = ["whole-of-run B1 carrier qualification", "whole-of-run B1 cartography", "provisioning P3-K"]
    if withdraw:
        image_sha, reason = withdraw
        hist = manifest.setdefault("history", [])
        if not any(h.get("image_sha256") == image_sha and h.get("state") == "WITHDRAWN" for h in hist):
            hist.append({"at": time.strftime("%Y-%m-%d", time.gmtime()), "image_sha256": image_sha, "state": "WITHDRAWN / DEFECTIVE / NO-RUN",
                         "reason": reason})
    manifest["schema_version"] = "0.2.0"
    return manifest


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--withdraw", nargs=2, metavar=("IMAGE_SHA256", "REASON"), default=None)
    a = ap.parse_args(argv)
    m = json.loads(a.manifest.read_text())
    m = refresh(m, tuple(a.withdraw) if a.withdraw else None)
    a.manifest.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"image {m['image']['sha256'][:16]}… carrier {m['carrier']['bitstream_sha256'][:16]}… pins {(m['pins']['sha256'] or 'NONE')[:16]}… "
          f"history {len(m.get('history', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
