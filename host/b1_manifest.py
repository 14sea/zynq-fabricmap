#!/usr/bin/env python3
"""B1 — refresh the manifest's DERIVED sections from the tree (host-only).

    b1_manifest.py [--withdraw <image sha256> <reason>] [--qualification <B1Q evidence dir>]

Rewrites, in manifests/b1_manifest.json, only what the tree determines:
  prereg.version ← the preregistration document's own title (DRAFT vN / frozen)
  image      ← evidence/b1/build_evidence.json (sha256, elf, bytes, evidence hash; board_ready
               stays false — it is set true by nothing but a ruling that the manifest is frozen)
  carrier    ← builds/b1/b1_build.json + carrier_manifest.json (bitstream sha256, nonce seed,
               wns, isolation); `carrier.qualification` is the B1Q record pinned with
               --qualification (verified before it is written; never removed by a refresh);
               `carrier.qualified` is DERIVED from that record every refresh
               (host/b1_qualification.verify: files hash, binding, PASS, re-adjudication) —
               it cannot be set by hand
  cartographer ← host/b1_carto constants (code bits, pairs, budget, wire cap)
  reporting_strata ← host/b1_model.STRATA
  signer     ← host/b1_sign_arm.py (path, sha256, contract)
  pins       ← manifests/b1_instrument_pins.json (path, sha256) — generate the table FIRST
  rulings    ← the four ruling texts (two pairs) and their binding fields
  history    ← appends a WITHDRAWN entry for --withdraw (never removes one)
Everything else (universe, seeds, plan, prediction, board) is left as it is; plan/prediction
are pinned by `b1_plan.py --write-manifest` (and `--qualification --write-manifest`). Run
order for a refresh:
  build image (b1_build_evidence.py --build) → b1_manifest.py → b1_plan.py --write-manifest
  → b1_plan.py --qualification --write-manifest → b1_pins.py --generate → b1_manifest.py → tests.
"""
from __future__ import annotations

import hashlib
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_qualification as bq  # noqa: E402

MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
B1_VARIANT = "0x42310001"
RULING_MAPPING = "whole-of-run B1 cartography"
RULING_QUALIFICATION = "whole-of-run B1 carrier qualification"
RULING_PROVISION = "provisioning P3-K"


def prereg_version(manifest: dict) -> str:
    """The version named in the preregistration's own title line (e.g. 'DRAFT v0.2')."""
    doc = REPO_ROOT / manifest["prereg"]["path"]
    if not doc.is_file():
        return "MISSING"
    first = doc.read_text().splitlines()[0]
    m = re.search(r"\((DRAFT v[\d.]+|v[\d.]+)[^)]*\)", first)
    return (m.group(1).replace("DRAFT ", "") + ("-draft" if m and m.group(1).startswith("DRAFT") else "")) if m else "UNPARSED"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def refresh(manifest: dict, withdraw: tuple[str, str] | None = None, qualification_dir: Path | None = None) -> dict:
    manifest["prereg"]["version"] = prereg_version(manifest)
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
    prior_q = (manifest.get("carrier") or {}).get("qualification")
    manifest["carrier"] = {"bitstream": "builds/b1/b1.bit", "bitstream_sha256": build["bitstream_sha256"], "bitstream_bytes": car["bitstream_bytes"],
                           "build_record": {"path": "builds/b1/b1_build.json", "sha256": sha(bd / "b1_build.json")},
                           "carrier_manifest": {"path": "builds/b1/carrier_manifest.json", "sha256": sha(bd / "carrier_manifest.json")},
                           "isolation": {"path": "builds/b1/isolation.txt", "sha256": sha(bd / "isolation.txt"), "result": build["cell_isolation"]},
                           "nonce_seed": car["nonce_seed"] if "nonce_seed" in car else build["nonce_seed"],
                           "variant": B1_VARIANT, "gate": build["gate"], "wns_ns": build["wns_ns"], "icape2_cells": build["icape2_cells"],
                           "part": build["part"], "vivado": build["vivado"], "frame_table_sha256": car["frame_table_sha256"],
                           "contract": "docs/b1_carrier_contract.md", "qualification_doc": "docs/b1_carrier_qualification.md",
                           "qualification": prior_q,
                           "qualified": False,
                           "note": "the B1 carrier (SEMANTIC_GATE=0: the PL verifies the signature and checks the sweep completed, and "
                                   "NEVER compares the readout with the signed table slots, which are the zero words). Built host-only. "
                                   "`qualification` is the B1Q session's record (host/b1_qualification.py), pinned by the owner after the "
                                   "`whole-of-run B1 carrier qualification` session on 17A6; `qualified` is DERIVED from it on every "
                                   "refresh (files hash, binding, PASS, re-adjudication) — the mapping runner and adjudicator re-verify "
                                   "the same chain and refuse on any break."}
    manifest["carrier"]["nonce_seed"] = f"0x{int(manifest['carrier']['nonce_seed'], 16):016x}"
    if qualification_dir is not None:
        rec_path = Path(qualification_dir) / "qualification.json"
        if not rec_path.is_file():
            raise SystemExit(f"{rec_path} is absent: the B1Q runner writes it after its adjudication")
        rec = json.loads(rec_path.read_text())
        manifest["carrier"]["qualification"] = rec
        try:
            bq.verify(manifest)
        except bq.QualificationRefusal as exc:
            raise SystemExit(f"the qualification record does not stand against this manifest: {exc}")
    manifest["carrier"]["qualified"] = bq.qualified(manifest) if manifest["carrier"].get("qualification") else False
    manifest["cartographer"] = {"version": bc.VERSION, "code_bits": bc.CODE_BITS, "pairs": bc.PAIRS_MAX,
                                "budget": bc.CODE_BITS + bc.N + bc.PAIRS_MAX, "wire_changed_cap": 8,
                                "evidence": "per entry: code_mask (which of the code probes lit it), confirm_seq, observed",
                                "source": "firmware/b1/b1_carto.c + b1_orch.c (pure units; host twin firmware/b1/b1_twin.c; Python reference host/b1_carto.py)"}
    manifest["reporting_strata"] = {**{k: list(v) for k, v in bm.STRATA.items()},
                                    "note": "stratum B = CLBLM_L.SLICEM_X0.ALUT/DLUT (LUT indices 4, 5; not consulted while the cartographer was "
                                            "developed), stratum A = the other four; both probed by the same algorithm, scored separately; "
                                            "neither is a blind holdout"}
    manifest.pop("holdout_luts", None)
    sp = REPO_ROOT / "host/b1_sign_arm.py"
    manifest["signer"] = {"path": "host/b1_sign_arm.py", "sha256": sha(sp), "contract": "b1-nonsemantic-v1",
                          "note": "signs commit ‖ twelve zero table words ‖ nonce; the semantic oracle is disarmed in-process; "
                                  "the runner refuses a sign_reply with any non-zero table (rule iii-B1, host/b1_records.py)"}
    pins = REPO_ROOT / "manifests/b1_instrument_pins.json"
    manifest["pins"] = {"path": "manifests/b1_instrument_pins.json", "sha256": sha(pins) if pins.is_file() else None,
                        "note": "every adjudication-critical fabricmap file (host/b1_pins.py PINNED_GLOBS); verified by the runner "
                                "before the port is opened and by the adjudicator before any verdict"}
    manifest["rulings_required"] = {"qualification_pair": [RULING_QUALIFICATION, RULING_PROVISION],
                                    "mapping_pair": [RULING_MAPPING, RULING_PROVISION],
                                    "note": "two sessions, two pairs, FOUR rulings: each session needs its own provisioning ruling "
                                            "(bound to its session name; a ruling is consumed once)"}
    manifest["rulings_binding"] = {
        RULING_QUALIFICATION: ["session=B1Q", "master_seed (the qualification plan's)", "prereg_sha256", "image_sha256", "b1_manifest_sha256"],
        RULING_MAPPING: ["session=B1", "master_seed (the plan's)", "prereg_sha256", "image_sha256", "b1_manifest_sha256"],
        RULING_PROVISION: ["session (B1Q or B1 — one ruling per session)", "prereg_sha256", "image_sha256", "b1_manifest_sha256"],
        "note": "image_sha256 is the B1 image's; prereg_sha256 is B1's frozen preregistration; b1_manifest_sha256 is THIS file as "
                "committed when the ruling is written (the mapping pair binds to the manifest AFTER the qualification record is pinned)"}
    if withdraw:
        image_sha, reason = withdraw
        hist = manifest.setdefault("history", [])
        if not any(h.get("image_sha256") == image_sha and h.get("state") == "WITHDRAWN" for h in hist):
            hist.append({"at": time.strftime("%Y-%m-%d", time.gmtime()), "image_sha256": image_sha, "state": "WITHDRAWN / DEFECTIVE / NO-RUN",
                         "reason": reason})
    manifest["schema_version"] = "0.3.0"
    return manifest


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--withdraw", nargs=2, metavar=("IMAGE_SHA256", "REASON"), default=None)
    ap.add_argument("--qualification", type=Path, default=None, help="pin the B1Q evidence dir's qualification.json (verified first)")
    a = ap.parse_args(argv)
    m = json.loads(a.manifest.read_text())
    m = refresh(m, tuple(a.withdraw) if a.withdraw else None, a.qualification)
    a.manifest.write_text(json.dumps(m, indent=1, ensure_ascii=False) + "\n")
    print(f"prereg {m['prereg']['version']} image {m['image']['sha256'][:16]}… carrier {m['carrier']['bitstream_sha256'][:16]}… "
          f"qualified {m['carrier']['qualified']} pins {(m['pins']['sha256'] or 'NONE')[:16]}… history {len(m.get('history', []))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
