#!/usr/bin/env python3
"""B4 probe `latch_ginv` — does the site's CLKINV bit follow IS_G_INVERTED in latch mode?

The owner's ruling of 2026-10-18 (D1', `build/wip/b4_f_domain_xa_owner_ruling_2026_10_18.md` §2):
a host-only pair of control-matched latch endpoints on the mine site, built under ONE recipe
with the same tool, and differed:

    main_latch        MODE 7, GINV 0   four main LDCE, IS_G_INVERTED = 0  (the attested endpoint
                                       of docs/ff_latch_probe.md, REBUILT under this recipe)
    main_latch_ginv   MODE 7, GINV 1   four main LDCE, IS_G_INVERTED = 1  (the endpoint under test)

The expectation, stated before the build and evaluated after it, never tuned: LATCH stays 1 in
both; the site's CLKINV bit (`CLBLL_L.SLICEL_X0.CLKINV` = segbit 01_51, the same bit NOCLKINV
negates) moves 1 -> 0; every other changed bit is frame ECC; the four cells of each endpoint
resolve to LDCE on AFF / BFF / CFF / DFF of SLICE_X2Y25 with the requested IS_G_INVERTED and
identical connections, occupancy and anchors otherwise. Anything else — a cell that does not
resolve, a property the tool does not report, CLKINV not moving, any other mover — is the
RESULT of this probe: archived as it came, exit status 2, and the unit stops for review.
Nothing here falls back to another design, adds a condition or widens the site.

What a met expectation means: host build / readback / bitstream correspondence for THIS recipe
on THIS site. Not a certificate, not a silicon observation, not a verification of the 21-address
domain, not a statement about any other latch combination (the ruling's §2, last paragraph).

Scope enforced, not merely documented: the mine site only; output under build/ only; the old
recipe, scripts, gate_runs and evidence untouched (the analysis helpers of `scripts/` are
IMPORTED read-only and named by digest in the report — nothing under `scripts/` is written).

    python3 -B b4/probes/latch_ginv/probe_latch_ginv.py                 # build both, report, export
    python3 -B b4/probes/latch_ginv/probe_latch_ginv.py --report-only   # re-derive from verified artifacts
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))
from bitstream_frames import column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import read_tile_bits  # noqa: E402
from gate_measure_ff import BUCKETS, address_tuple, as_addresses, classify_diff, raw_diff  # noqa: E402
from specimen_diff import features_using, tile_index  # noqa: E402

TCL = HERE / "build_ff_latch_ginv.tcl"
SOURCE = HERE / "specimen_ff_latch_ginv.v"
DRIVER = Path(__file__).resolve()
RUN_VIVADO = REPO / "scripts/run_vivado.sh"
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"
BIT_CLASS = "clb_ff_config"
MINE_SITE = "SLICE_X2Y25"
MODE = 7                                  # four main storage elements, LDCE (docs/ff_latch_probe.md)
BELS = ("AFF", "BFF", "CFF", "DFF")
ANCHOR_ARGS = ("AFF", "1", "SLICE_X4Y20", "SLICE_X2Y20")   # the old recipe's defaults, passed explicitly
DEFAULT_OUT = REPO / "build/b4_ff_latch_ginv_probe"
DEFAULT_EVIDENCE = REPO / "evidence/b4/unit_d1prime_latch_ginv_2026_10_18"

ENDPOINTS = {
    "main_latch": {"mode": MODE, "ginv": 0,
                   "description": "four main LDCE, IS_G_INVERTED = 0 — the attested endpoint of "
                                  "docs/ff_latch_probe.md, rebuilt under this recipe"},
    "main_latch_ginv": {"mode": MODE, "ginv": 1,
                        "description": "four main LDCE, IS_G_INVERTED = 1 — the endpoint under test"},
}
PAIR = ("main_latch", "main_latch_ginv")

# The borrowed analysis code and data, named by digest. Read-only: the pin table of
# claimb_round1prime covers scripts/; a change there changes this report's provenance.
BORROWED = ("scripts/bitstream_frames.py", "scripts/decode_groups.py", "scripts/gate_measure_ff.py",
            "scripts/specimen_diff.py", "scripts/frame_ecc.py", "scripts/run_vivado.sh",
            "data/prjxray/zynq7/xc7z010/tilegrid.json", "data/subset_spec.json",
            "data/prjxray/zynq7/segbits_clbll_l.db")
ORIGINALS = ("vivado/specimen/specimen_ff_probe.v", "vivado/specimen/build_ff_probe.tcl",
             "scripts/gate_build_ff.py")

# The expectation. Fixed here, in the commit that precedes the build.
EXPECTED_LATCH_FEATURE = "CLBLL_L.SLICEL_X0.LATCH"
EXPECTED_CLKINV_FEATURE = "CLBLL_L.SLICEL_X0.CLKINV"
EXPECTED_CLKINV_DIRECTION = "1->0"
INVERSION_PROPS = ("IS_C_INVERTED", "IS_G_INVERTED", "IS_CLR_INVERTED", "IS_R_INVERTED",
                   "IS_CE_INVERTED", "IS_GE_INVERTED", "IS_D_INVERTED")


def sha256_file(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in Path(path).read_text().splitlines():
        if "\t" in line:
            key, value = line.split("\t", 1)
            out[key] = value
    return out


def recipe_hashes() -> dict[str, str]:
    """What decides what a build means: the derived Verilog, the derived Tcl, this driver."""
    return {str(p.relative_to(REPO)): sha256_file(p) for p in (SOURCE, TCL, DRIVER)}


def borrowed_hashes() -> dict[str, str]:
    return {rel: sha256_file(REPO / rel) for rel in BORROWED}


def originals_hashes() -> dict[str, str]:
    return {rel: sha256_file(REPO / rel) for rel in ORIGINALS}


# ---- the build cache: a stamp on every attempt, reuse only on a full match -------------------------

ARTIFACTS = ("spec.bit", "readback.tsv", "base.dcp")


def cache_state(outdir: Path, endpoint: str) -> tuple[str, str]:
    """(state, why): build / reuse / failed / refuse — the old probe's rule, with GINV in the stamp."""
    ep = ENDPOINTS[endpoint]
    if not outdir.exists() or not any(outdir.iterdir()):
        return "build", "empty"
    stamp_path = outdir / "stamp.json"
    if not stamp_path.is_file():
        return "refuse", "output directory is not empty and carries no build stamp"
    try:
        stamp = json.loads(stamp_path.read_text())
    except json.JSONDecodeError as exc:
        return "refuse", f"build stamp is unreadable: {exc}"
    for key, want in (("endpoint", endpoint), ("mode", ep["mode"]), ("ginv", ep["ginv"]), ("site", MINE_SITE)):
        if stamp.get(key) != want:
            return "refuse", f"stamp {key} is {stamp.get(key)!r}, this run wants {want!r}"
    if stamp.get("recipe") != recipe_hashes():
        return "refuse", "stamp was produced by different sources (recipe hash mismatch)"
    if not stamp.get("completed"):
        return "failed", "stamp records a build of this recipe that did not complete"
    for name in ARTIFACTS:
        if not (outdir / name).is_file():
            return "refuse", f"stamp claims success but {name} is missing"
        if stamp.get("artifacts", {}).get(name) != sha256_file(outdir / name):
            return "refuse", f"{name} does not match the hash the stamp recorded"
    return "reuse", "stamp matches"


def build(endpoint: str, outdir: Path, timeout: int) -> bool:
    state, why = cache_state(outdir, endpoint)
    if state == "reuse":
        print(f"  {endpoint}: reusing verified artifacts ({why})")
        return True
    if state == "failed":
        print(f"  {endpoint}: previously FAILED with this recipe ({why}) — not rebuilt, reported as it stands")
        return False
    if state == "refuse":
        raise SystemExit(f"{endpoint}: refusing to touch {outdir} — {why}. Delete it deliberately if that is what you mean.")
    ep = ENDPOINTS[endpoint]
    outdir.mkdir(parents=True, exist_ok=True)
    tclargs = [str(outdir.resolve()), MINE_SITE, str(ep["mode"]), *ANCHOR_ARGS, str(ep["ginv"])]
    command = [str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
               "-log", str(outdir / "vivado.log"), "-source", str(TCL), "-tclargs", *tclargs]
    started = time.time()
    checked = subprocess.run(command, cwd=outdir, capture_output=True, text=True, timeout=timeout)
    elapsed = round(time.time() - started, 1)
    (outdir / "run.out").write_text(checked.stdout + checked.stderr)
    produced = all((outdir / name).is_file() for name in ARTIFACTS)
    ok = checked.returncode == 0 and "SPECIMEN_DONE" in checked.stdout and produced
    (outdir / "stamp.json").write_text(json.dumps({
        "completed": ok,
        "endpoint": endpoint, "mode": ep["mode"], "ginv": ep["ginv"], "site": MINE_SITE,
        "recipe": recipe_hashes(),
        "borrowed": borrowed_hashes(),
        "command": command,
        "exit_code": checked.returncode,
        "elapsed_s": elapsed,
        "artifacts": {name: sha256_file(outdir / name) for name in ARTIFACTS if (outdir / name).is_file()},
    }, indent=2) + "\n")
    print(f"  {endpoint}: {'ok' if ok else 'FAILED'} (exit {checked.returncode}, {elapsed}s)")
    if not ok:
        for line in (checked.stdout + checked.stderr).splitlines():
            if "ERROR" in line:
                print(f"    {line.strip()}")
    return ok


def verified_state(endpoint: str, outdir: Path) -> tuple[str, str]:
    state, why = cache_state(outdir, endpoint)
    if state in ("reuse", "failed"):
        return state, why
    raise SystemExit(f"{endpoint}: refusing to use {outdir} — {why}.")


# ---- per-cell verification of a readback (pure; tested without Vivado) ---------------------------

def cell_records(readback: dict[str, str]) -> list[dict]:
    """Every storage cell as the readback reports it: name, primitive, LOC, BEL, INIT, every
    inversion property, every pin's net / BEL pin / route status. Missing keys stay None —
    an unresolved value is reported as unresolved, never filled in."""
    try:
        count = int(readback.get("storage_count") or 0)
    except ValueError:
        count = 0
    cells = []
    for n in range(count):
        pins: dict[str, dict] = {}
        for key, value in readback.items():
            m = re.fullmatch(rf"store\.{n}\.pin\.([A-Za-z0-9_]+)\.(net|belpin|route_status)", key)
            if m:
                pins.setdefault(m.group(1), {})[m.group(2)] = value
        cells.append({
            "name": readback.get(f"store.{n}.name"), "ref": readback.get(f"store.{n}.ref"),
            "loc": readback.get(f"store.{n}.loc"), "bel": readback.get(f"store.{n}.bel"),
            "init": readback.get(f"store.{n}.init"),
            "props": {p: readback.get(f"store.{n}.prop.{p}") for p in INVERSION_PROPS},
            "pins": pins,
        })
    return cells


def cell_findings(readback: dict[str, str], ginv: int) -> list[str]:
    """Why this endpoint's readback is NOT four LDCE on AFF..DFF of the mine site with the requested
    gate inversion. Empty = verified. Every cell is checked, not the first."""
    want_g = "1'b1" if ginv else "1'b0"
    findings: list[str] = []
    if readback.get("requested_ginv") != str(ginv):
        findings.append(f"requested_ginv is {readback.get('requested_ginv')!r}, expected {ginv!r}")
    if readback.get("requested_site") != MINE_SITE:
        findings.append(f"requested_site is {readback.get('requested_site')!r}")
    cells = cell_records(readback)
    if len(cells) != 4:
        findings.append(f"storage_count is {len(cells)}, expected 4")
    bels = []
    for i, c in enumerate(cells):
        tag = f"cell {i} ({c['name']})"
        if c["ref"] != "LDCE":
            findings.append(f"{tag}: primitive is {c['ref']!r}, expected LDCE")
        if c["loc"] != MINE_SITE:
            findings.append(f"{tag}: LOC is {c['loc']!r}, expected {MINE_SITE}")
        bel = (c["bel"] or "").split(".")[-1]
        bels.append(bel)
        if bel not in BELS:
            findings.append(f"{tag}: BEL is {c['bel']!r}, expected one of {BELS}")
        g = c["props"].get("IS_G_INVERTED")
        if g is None or g == "":
            findings.append(f"{tag}: IS_G_INVERTED unresolved (the tool reported no value)")
        elif g != want_g:
            findings.append(f"{tag}: IS_G_INVERTED is {g!r}, expected {want_g!r}")
        clr = c["props"].get("IS_CLR_INVERTED")
        if clr is None or clr == "":
            findings.append(f"{tag}: IS_CLR_INVERTED unresolved")
        elif clr != "1'b0":
            findings.append(f"{tag}: IS_CLR_INVERTED is {clr!r}, expected 1'b0")
        for pin in ("G", "GE", "CLR", "D", "Q"):
            rec = c["pins"].get(pin)
            if rec is None or not rec.get("net"):
                findings.append(f"{tag}: pin {pin} has no net in the readback")
            elif rec.get("route_status") != "ROUTED":
                findings.append(f"{tag}: pin {pin} net {rec.get('net')!r} route status {rec.get('route_status')!r}")
    if len(cells) == 4 and sorted(bels) != sorted(BELS):
        findings.append(f"BELs are {bels}, expected each of {BELS} exactly once")
    if len(cells) == 4:
        for pin in ("G", "GE", "CLR"):
            nets = {c["pins"].get(pin, {}).get("net") for c in cells}
            if len(nets) != 1:
                findings.append(f"pin {pin} is driven by different nets across the four cells: {sorted(map(str, nets))}")
    return findings


def _strip_prop(record: dict, prop: str) -> dict:
    out = json.loads(json.dumps(record))
    for c in out["cells"]:
        c["props"].pop(prop, None)
    return out


def endpoint_structure(readback: dict[str, str]) -> dict:
    """Everything of the endpoint that must be IDENTICAL between the pair: cells (minus the property
    under test), LUT cells, occupied BELs, anchors, tool, part."""
    return {
        "part": readback.get("part"), "vivado_version": readback.get("vivado_version"),
        "mode": readback.get("mode"), "site": readback.get("requested_site"),
        "cells": cell_records(readback),
        "lut_cells": [{k: readback.get(f"lut.{n}.{k}") for k in ("name", "ref", "loc", "bel")}
                      for n in range(int(readback.get("lut_count") or 0))],
        "occupied": sorted((v, readback.get(k.replace(".bel", ".ref")))
                           for k, v in readback.items() if re.fullmatch(r"occupied\.\d+\.bel", k)),
        "anchors": {k: v for k, v in sorted(readback.items()) if k.startswith("anchor.")},
    }


def structure_findings(a: dict[str, str], b: dict[str, str]) -> list[str]:
    """Why the two endpoints differ in more than IS_G_INVERTED (structure only — the bitstream diff is
    reported separately and in full)."""
    sa, sb = endpoint_structure(a), endpoint_structure(b)
    sa, sb = _strip_prop(sa, "IS_G_INVERTED"), _strip_prop(sb, "IS_G_INVERTED")
    out = []
    for key in sa:
        if sa[key] != sb[key]:
            out.append(f"{key} differs between the endpoints")
    return out


# ---- the expectation over the bitstream diff (pure; tested without Vivado) ------------------------

def expectation(tile_a: dict[str, int], tile_b: dict[str, int], movers: list[dict], counts: dict[str, int],
                latch_token: str, clkinv_token: str, class_out_of_scope: int = 0) -> dict:
    """The expectation fixed before the build, evaluated after it. `met` is True only when every
    clause holds; every clause is reported with its own value so a miss names itself. The diff is
    bucketed with the CLKINV address as the one in-scope bit (the old probe's rule with the LATCH
    bit), so every other attributed, unknown or unattributed bit is a miss by its bucket."""
    clauses = {
        "latch_set_in_both": tile_a.get(latch_token) == 1 and tile_b.get(latch_token) == 1,
        "clkinv_moves_1_to_0": tile_a.get(clkinv_token) == 1 and tile_b.get(clkinv_token) == 0,
        "clkinv_is_the_only_same_class_mover": [m["segbit"] for m in movers] == [clkinv_token],
        "clkinv_in_scope_once": counts.get("in_scope", 0) == 1,
        "no_bucket_but_in_scope_and_ecc": all(
            counts.get(k, 0) == 0 for k in ("db_attributed", "ownership_unknown", "unattributed")),
        "no_class_claim_out_of_scope": class_out_of_scope == 0,
    }
    return {"clauses": clauses, "met": all(clauses.values()),
            "latch_values": [tile_a.get(latch_token), tile_b.get(latch_token)],
            "clkinv_values": [tile_a.get(clkinv_token), tile_b.get(clkinv_token)]}


# ---- main --------------------------------------------------------------------------------------

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--evidence", type=Path, default=DEFAULT_EVIDENCE)
    ap.add_argument("--timeout", type=int, default=2400)
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()
    out = args.out.resolve()
    if not out.is_relative_to(REPO / "build"):
        raise SystemExit("this probe writes raw output under build/ only")
    evidence = args.evidence.resolve()
    if not evidence.is_relative_to(REPO / "evidence/b4"):
        raise SystemExit("this probe exports under evidence/b4/ only")

    grid = json.loads(TILEGRID.read_text())
    tile_name = next(name for name, tile in grid.items() if MINE_SITE in tile.get("sites", {}))
    block = grid[tile_name]["bits"]["CLB_IO_CLK"]
    tile_type = grid[tile_name]["type"]
    spec = json.loads(SPEC.read_text())
    pattern = re.compile(next(c["feature_regex"] for c in spec["bit_classes"] if c["id"] == BIT_CLASS))
    index = tile_index()
    db = (REPO / f"data/prjxray/zynq7/segbits_{tile_type.lower()}.db").read_text().splitlines()
    tokens = {}
    for line in db:
        f = line.split()
        if f and f[0] in (EXPECTED_LATCH_FEATURE, EXPECTED_CLKINV_FEATURE):
            tokens[f[0]] = f[1].lstrip("!")
    if set(tokens) != {EXPECTED_LATCH_FEATURE, EXPECTED_CLKINV_FEATURE}:
        raise SystemExit(f"the freeze lacks a LATCH or CLKINV rule for {tile_type}: {tokens}")
    latch_token, clkinv_token = tokens[EXPECTED_LATCH_FEATURE], tokens[EXPECTED_CLKINV_FEATURE]

    def address_of(token: str) -> dict:
        frame, bit = (int(x) for x in token.split("_"))
        return {"far": f"0x{int(block['baseaddr'], 16) + frame:08X}", "word": block["offset"] + bit // 32, "bit": bit % 32}

    print(f"latch_ginv probe on {MINE_SITE} ({tile_name}, {tile_type}) -> {out}")
    if not args.report_only:
        for name in PAIR:
            build(name, out / name, args.timeout)

    states = {name: verified_state(name, out / name) for name in PAIR}
    cols, layout = column_map(), device_layout()
    artifacts, frames, tile_bits, readbacks = {}, {}, {}, {}
    for name in PAIR:
        d = out / name
        stamp = json.loads((d / "stamp.json").read_text())
        rec = {**ENDPOINTS[name], "built": states[name][0] == "reuse", "state": states[name][0],
               "why": states[name][1], "exit_code": stamp.get("exit_code"), "elapsed_s": stamp.get("elapsed_s"),
               "command": stamp.get("command")}
        if not rec["built"]:
            rec["error_lines"] = [l.strip() for l in (d / "run.out").read_text().splitlines() if "ERROR" in l][:10] \
                if (d / "run.out").is_file() else []
            artifacts[name] = rec
            continue
        readback = read_tsv(d / "readback.tsv")
        readbacks[name] = readback
        frames[name] = parse_frames(d / "spec.bit", cols, layout)["frames"]
        tile_bits[name] = read_tile_bits(frames[name], block)
        rec.update({
            "bitstream": str((d / "spec.bit").relative_to(REPO)),
            "bitstream_sha256": sha256_file(d / "spec.bit"),
            "checkpoint_sha256": sha256_file(d / "base.dcp"),
            "readback_sha256": sha256_file(d / "readback.tsv"),
            "vivado_version": readback.get("vivado_version"), "part": readback.get("part"),
            "requested_ginv": readback.get("requested_ginv"),
            "cells": cell_records(readback),
            "cell_findings": cell_findings(readback, ENDPOINTS[name]["ginv"]),
            "structure": {k: v for k, v in endpoint_structure(readback).items() if k != "cells"},
            "site_bits": {"latch": tile_bits[name].get(latch_token), "clkinv": tile_bits[name].get(clkinv_token)},
        })
        artifacts[name] = rec

    pair_record: dict = {"pair": "latch_ginv", "modes": list(PAIR),
                         "question": "with four main LDCE on the mine site, does IS_G_INVERTED 0 -> 1 move the site's CLKINV bit 1 -> 0 and nothing else of this class?"}
    verdict = {"met": False, "why": []}
    a, b = PAIR
    if all(artifacts[n]["built"] for n in PAIR):
        raw = raw_diff(frames[a], frames[b])
        scope = {address_tuple(address_of(clkinv_token))}            # the one bit the expectation names
        buckets, class_out_of_scope = classify_diff(raw, scope, index, pattern, {tile_name})
        movers = []
        for token, before in sorted(tile_bits[a].items()):
            after = tile_bits[b].get(token)
            if after == before:
                continue
            movers.append({"segbit": token, "address": address_of(token), "before": before, "after": after,
                           "direction": f"{before}->{after}",
                           "class_features": sorted(f for f in features_using(tile_type, token) if pattern.fullmatch(f)),
                           "all_features": sorted(features_using(tile_type, token))})
        counts = {k: len(v) for k, v in buckets.items()}
        exp = expectation(tile_bits[a], tile_bits[b], movers, counts, latch_token, clkinv_token, len(class_out_of_scope))
        structure = structure_findings(readbacks[a], readbacks[b])
        cells_ok = all(not artifacts[n]["cell_findings"] for n in PAIR)
        pair_record.update({
            "raw_diff_bits": len(raw),
            "raw_diff": as_addresses(raw),                       # EVERY changed bit, address by address
            "counts": counts,
            "buckets": {k: as_addresses(v) for k, v in buckets.items()},
            "preregistered_scope": as_addresses(scope),
            "class_claimed_out_of_scope": as_addresses(class_out_of_scope),
            "same_class_movers": movers,
            "latch": {"feature": EXPECTED_LATCH_FEATURE, "segbit": latch_token, "address": address_of(latch_token)},
            "clkinv": {"feature": EXPECTED_CLKINV_FEATURE, "segbit": clkinv_token, "address": address_of(clkinv_token),
                       "expected_direction": EXPECTED_CLKINV_DIRECTION},
            "expectation": exp,
            "structure_findings": structure,
        })
        verdict = {"met": exp["met"] and cells_ok and not structure,
                   "why": ([k for k, v in exp["clauses"].items() if not v]
                           + [f"{n}: {f}" for n in PAIR for f in artifacts[n]["cell_findings"]]
                           + structure)}
    else:
        pair_record["not_measured"] = "an endpoint could not be built"
        verdict["why"] = [f"{n} not built: {artifacts[n]['why']}" for n in PAIR if not artifacts[n]["built"]]

    # Cross-check against the historical record (a fact, not a condition): the old main_latch
    # was built from a different (the original) recipe, so equality is not expected or required.
    old = REPO / "evidence/ff_latch_probe_2026_08_04/manifest.json"
    historical = None
    if old.is_file():
        m = json.loads(old.read_text())
        h = m.get("bitstreams_not_copied", {}).get("main_latch", {})
        historical = {"manifest": str(old.relative_to(REPO)), "manifest_sha256": sha256_file(old),
                      "main_latch_bitstream_sha256": h.get("bitstream_sha256"),
                      "rebuilt_main_latch_bitstream_sha256": artifacts.get(a, {}).get("bitstream_sha256"),
                      "bit_identical": h.get("bitstream_sha256") == artifacts.get(a, {}).get("bitstream_sha256"),
                      "note": "a different recipe file (the derived copy) — equality is reported, never required"}

    report = {
        "schema": "b4_latch_ginv_probe", "schema_version": "1.0.0",
        "status": "host build / readback / bitstream correspondence on the mine site — exploration; not a certificate, not a silicon observation, not a domain verification",
        "ruling": "build/wip/b4_f_domain_xa_owner_ruling_2026_10_18.md section 2 (D1'); ignored file, quoted in the evidence README",
        "bit_class": BIT_CLASS, "site": MINE_SITE, "site_split": "mine (evidence already spent; can never score)",
        "tile": tile_name, "tile_type": tile_type,
        "recipe": recipe_hashes(), "borrowed": borrowed_hashes(), "originals_unchanged": originals_hashes(),
        "endpoints": artifacts, "pair": pair_record,
        "verdict": {"expectation_met": verdict["met"], "findings": verdict["why"],
                    "meaning_if_met": "for this recipe on this site, IS_G_INVERTED = 1 on four main LDCE clears the site's CLKINV bit; the reading 'latch, CLKINV = 0 => gate inverted' gains a host exploration source of the same kind as the attested CLKINV = 1 endpoint. Nothing about silicon, other combinations, or the 21-address domain.",
                    "on_miss": "archived as it came; the unit stops for review (no fallback to D1 / D2, no added condition, no other site)"},
        "commitment": "none; no hypothesis, HYPOTHESIS_SHA256, domain or F fact changed",
    }
    (out / "probe_report.json").write_text(json.dumps(report, indent=2) + "\n")

    # Portable evidence: the report, every readback, every stamp, every run log, the Vivado logs
    # (copied under a .txt name: evidence/*.log is gitignored in this repository), the digests.
    evidence.mkdir(parents=True, exist_ok=True)
    (evidence / "probe_report.json").write_text(json.dumps(report, indent=2) + "\n")
    copied = {}
    for name in PAIR:
        d = out / name
        for src, dst in (("readback.tsv", f"readbacks/{name}.tsv"), ("stamp.json", f"stamps/{name}.stamp.json"),
                         ("run.out", f"logs/{name}.run.out.txt"), ("vivado.log", f"logs/{name}.vivado.log.txt")):
            if (d / src).is_file():
                target = evidence / dst
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes((d / src).read_bytes())
                copied[dst] = sha256_file(target)
    (evidence / "manifest.json").write_text(json.dumps({
        "schema": "b4_latch_ginv_probe_evidence", "schema_version": "1.0.0",
        "note": "exploration on the mine site; no prediction, commitment, certificate or hypothesis change",
        "site": MINE_SITE, "tile": tile_name, "tile_type": tile_type,
        "recipe": recipe_hashes(), "borrowed": borrowed_hashes(), "originals_unchanged": originals_hashes(),
        "historical_main_latch": historical,
        "bitstreams_not_copied": {n: {k: artifacts[n].get(k) for k in ("bitstream_sha256", "checkpoint_sha256", "readback_sha256")}
                                  for n in PAIR if artifacts[n]["built"]},
        "endpoints_not_built": {n: artifacts[n]["why"] for n in PAIR if not artifacts[n]["built"]},
        "expectation_met": verdict["met"],
        "files": {"probe_report.json": sha256_file(evidence / "probe_report.json"), **copied},
    }, indent=2) + "\n")

    print(f"\n  LATCH {latch_token} values {report['pair'].get('expectation', {}).get('latch_values')}; "
          f"CLKINV {clkinv_token} values {report['pair'].get('expectation', {}).get('clkinv_values')}")
    if "counts" in pair_record:
        print(f"  raw diff {pair_record['raw_diff_bits']}: " + "  ".join(f"{k}={pair_record['counts'][k]}" for k in BUCKETS))
        for m in pair_record["same_class_movers"]:
            print(f"    {m['segbit']}  {m['direction']}  {', '.join(m['class_features']) or '(none)'}")
    print(f"  expectation met: {verdict['met']}")
    for w in verdict["why"]:
        print(f"    - {w}")
    print(f"  evidence -> {evidence.relative_to(REPO)}")
    return 0 if verdict["met"] else 2


if __name__ == "__main__":
    sys.exit(main())
