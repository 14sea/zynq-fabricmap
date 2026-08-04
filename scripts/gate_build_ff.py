#!/usr/bin/env python3
"""Explore the `clb_ff_config` LATCH question on the mine site. Exploration only.

Scope, fixed by the author's ruling on `docs/ff_preregistration_plan.md` §5 risk 3 and
enforced below rather than merely documented:

* **`SLICE_X2Y25` only** — the mine site, whose evidence is already spent and can never
  score. No holdout site is built and no holdout bitstream is read.
* **`build/ff_latch_probe/` only** — never `gate_runs/`, which is where committed
  evidence lives.
* **No commitment.** `PREREGISTRATION_HOLD` is not consulted, not lifted and not
  needed: nothing here writes a predictions artifact or a hash anybody could commit.

The question is narrow. `LDCE` is a different primitive from the plan's baseline
`FDRE`, so the LATCH pair was expected to move more of the slice-wide control set than
the single `LATCH` bit — and those extra movers would be `db_attributed`, claimed by
this class, outside the pair's one preregistered scope, i.e. FP with FP=0 required. The
ruling was to try a **control-matched baseline** first and, if movers remain, report
every one of them with its direction so they can be preregistered feature by feature.
Not to guess a wider scope, and not to drop `LATCH`.

Three modes are built so the comparison is a measurement rather than an assertion:

    0  FDCE  control-matched baseline (asynchronous clear, like LDCE's CLR)
    1  LDCE  the latch under test
    2  FDRE  the plan's default baseline B (synchronous reset)

and three pairs are differed: 0->1 (the candidate), 2->1 (what the plan would have
done), 2->0 (what the control match itself costs). Buckets come from the gate's own
`classify_diff`, so the exploration cannot bucket bits differently from the run.

    scripts/gate_build_ff.py --out build/ff_latch_probe
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bitstream_frames import column_map, device_layout, parse_frames  # noqa: E402
from decode_groups import read_tile_bits  # noqa: E402
from gate_measure_ff import (BUCKETS, address_tuple, as_addresses,  # noqa: E402
                             classify_diff, raw_diff)
from specimen_diff import features_using, locate, tile_index  # noqa: E402

REPO = Path(__file__).resolve().parent.parent
TCL = REPO / "vivado/specimen/build_ff_probe.tcl"
SOURCE = REPO / "vivado/specimen/specimen_ff_probe.v"
RUN_VIVADO = REPO / "scripts/run_vivado.sh"
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"
SPEC = REPO / "data/subset_spec.json"
BIT_CLASS = "clb_ff_config"

# The mine site, and the only site this tool will build. Holdout evidence is not spent
# on exploration — that is the whole reason a mine site exists.
MINE_SITE = "SLICE_X2Y25"

MODES = {
    0: ("fdce", "control-matched baseline: FDCE, asynchronous clear, CE and CLR driven"),
    1: ("ldce", "the latch under test: LDCE, GE and CLR driven"),
    2: ("fdre", "the plan's default baseline B: FDRE, synchronous reset"),
    3: ("fdce_inv", "second control match: FDCE with the clock inverted, added after "
                    "mode 0 measured a residual CLKINV mover"),
    4: ("full_base", "formal topology: 8 storage elements, FDCE with the clock inverted"),
    5: ("full_latch", "formal topology: 8 storage elements, LDCE"),
    6: ("main_base", "4 storage elements (main only), FDCE with the clock inverted"),
    7: ("main_latch", "4 storage elements (main only), LDCE"),
}

PAIRS = (
    (0, 1, "control_matched", "first candidate: does matching the reset kind isolate LATCH?"),
    (3, 1, "control_matched_clkinv", "second candidate: reset kind AND clock polarity matched"),
    (4, 5, "full_slice", "THE ONE THAT DECIDES IT: the formal 8-element topology"),
    (6, 7, "main_only", "fallback topology if the slice cannot hold 8 latches"),
    (2, 1, "plan_default", "what the plan as written would have diffed"),
    (2, 0, "control_match_cost", "what matching the reset kind itself moves"),
    (0, 3, "clock_inversion_cost", "what matching the clock polarity itself moves"),
)
LATCH_PAIRS = ("control_matched", "control_matched_clkinv", "full_slice", "main_only",
               "plan_default")

# A mode that legitimately cannot be built. UG474 says the "5FF" storage elements are
# unavailable while the slice is in latch mode; if that is what Vivado enforces, mode 5
# fails and the 4-element pair is the answer. A build failure here is evidence, so it is
# recorded rather than aborting the run — but only for the modes where it is a real
# question, never as a blanket "carry on regardless".
MAY_FAIL = {5}


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "\t" in line:
            key, value = line.split("\t", 1)
            out[key] = value
    return out


def recipe_hashes() -> dict[str, str]:
    """The sources that decide what a build means. Any change invalidates a cache hit."""
    return {str(path.relative_to(REPO)): sha256_file(path)
            for path in (SOURCE, TCL, Path(__file__).resolve())}


def cache_state(outdir: Path, mode: int) -> tuple[str, str]:
    """`(state, why)` for an existing output directory: build / reuse / failed / refuse.

    The presence of artifacts is NOT evidence that they are the artifacts this run
    wants. A stale `spec.bit` from an earlier mode, an earlier site or an earlier
    version of the Verilog looks exactly like a successful build, and a probe that
    accepted it would report yesterday's answer to today's question with today's
    confidence.

    So reuse requires a stamp naming the mode, the site, the hash of every source that
    produced it and the hash of every artifact. **A stamp is written on every attempt,
    successful or not** — a failure that left no stamp would be indistinguishable from
    a directory nobody ever built in — and only `completed: true` is reusable. A
    non-empty directory whose stamp does not match is refused rather than overwritten.

    `failed` is distinct from `refuse` on purpose: it means "this exact recipe was run
    at this mode and site and did not complete", which for `MAY_FAIL` modes is the
    answer rather than an accident.
    """
    if not outdir.exists() or not any(outdir.iterdir()):
        return "build", "empty"
    stamp_path = outdir / "stamp.json"
    if not stamp_path.is_file():
        return "refuse", "output directory is not empty and carries no build stamp"
    try:
        stamp = json.loads(stamp_path.read_text())
    except json.JSONDecodeError as exc:
        return "refuse", f"build stamp is unreadable: {exc}"
    if stamp.get("mode") != mode:
        return "refuse", f"stamp is for mode {stamp.get('mode')}, this run wants {mode}"
    if stamp.get("site") != MINE_SITE:
        return "refuse", f"stamp is for site {stamp.get('site')!r}"
    if stamp.get("recipe") != recipe_hashes():
        return "refuse", "stamp was produced by different sources (recipe hash mismatch)"
    if not stamp.get("completed"):
        return "failed", "stamp records a build of this recipe that did not complete"
    for name in ("spec.bit", "readback.tsv", "base.dcp"):
        if not (outdir / name).is_file():
            return "refuse", f"stamp claims success but {name} is missing"
        if stamp.get("artifacts", {}).get(name) != sha256_file(outdir / name):
            return "refuse", f"{name} does not match the hash the stamp recorded"
    return "reuse", "stamp matches"


def verified_state(mode: int, outdir: Path) -> tuple[str, str]:
    """The single gate every artifact passes before it is read, on every code path.

    `--report-only` used to skip straight to parsing whatever was on disk, which meant
    the one flag that exists to avoid rebuilding was also the one that would stamp the
    current recipe's hashes onto an older run's bitstreams. Export and build now go
    through the same check.
    """
    state, why = cache_state(outdir, mode)
    if state in ("reuse", "failed"):
        return state, why
    raise SystemExit(
        f"mode {mode} ({MODES[mode][0]}): refusing to use {outdir} — {why}.\n"
        "  Rebuild it, or delete it deliberately if that is what you mean; a report\n"
        "  built on unverified artifacts answers a question nobody asked.")


def build(mode: int, outdir: Path, timeout: int) -> bool:
    state, why = cache_state(outdir, mode)
    if state == "reuse":
        print(f"  mode {mode} ({MODES[mode][0]}): reusing verified artifacts ({why})")
        return True
    if state == "failed":
        print(f"  mode {mode} ({MODES[mode][0]}): previously FAILED with this recipe ({why})")
        return False
    if state == "refuse":
        raise SystemExit(
            f"mode {mode}: refusing to touch {outdir} — {why}.\n"
            "  Delete it deliberately if that is what you mean; a probe that reused it\n"
            "  would answer a question nobody asked with artifacts nobody checked.")

    outdir.mkdir(parents=True, exist_ok=True)
    tclargs = [str(outdir.resolve()), MINE_SITE, str(mode)]
    checked = subprocess.run(
        [str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
         "-log", str(outdir / "vivado.log"), "-source", str(TCL), "-tclargs", *tclargs],
        cwd=outdir, capture_output=True, text=True, timeout=timeout)
    (outdir / "run.out").write_text(checked.stdout + checked.stderr)
    produced = all((outdir / name).is_file()
                   for name in ("spec.bit", "readback.tsv", "base.dcp"))
    ok = checked.returncode == 0 and "SPECIMEN_DONE" in checked.stdout and produced
    (outdir / "stamp.json").write_text(json.dumps({
        "completed": ok,
        "mode": mode,
        "site": MINE_SITE,
        "recipe": recipe_hashes(),
        "artifacts": {name: sha256_file(outdir / name)
                      for name in ("spec.bit", "readback.tsv", "base.dcp")
                      if (outdir / name).is_file()},
    }, indent=2) + "\n")
    print(f"  mode {mode} ({MODES[mode][0]}): {'ok' if ok else 'FAILED'}")
    if not ok:
        for line in (checked.stdout + checked.stderr).splitlines():
            if "ERROR" in line:
                print(f"    {line.strip()}")
    return ok


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "build/ff_latch_probe")
    ap.add_argument("--site", default=MINE_SITE)
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--report-only", action="store_true",
                    help="skip Vivado and re-derive the report from existing artifacts")
    ap.add_argument("--evidence", type=Path,
                    default=REPO / "evidence/ff_latch_probe_2026_08_04",
                    help="portable copy: report, readbacks and hashes, no bitstreams")
    args = ap.parse_args()

    if args.site != MINE_SITE:
        raise SystemExit(
            f"this probe builds {MINE_SITE} only.\n"
            "  Every other site instance of clb_ff_config is holdout: exploring on one\n"
            "  would spend evidence that the certificate needs in order to mean\n"
            "  anything. See docs/ff_preregistration_plan.md §1.")
    out = args.out.resolve()
    if not out.is_relative_to(REPO / "build"):
        raise SystemExit("this probe writes under build/ only — gate_runs/ holds committed evidence")

    grid = json.loads(TILEGRID.read_text())
    tile_name = next(name for name, tile in grid.items() if MINE_SITE in tile.get("sites", {}))
    block = grid[tile_name]["bits"]["CLB_IO_CLK"]
    spec = json.loads(SPEC.read_text())
    pattern = re.compile(next(c["feature_regex"] for c in spec["bit_classes"]
                              if c["id"] == BIT_CLASS))
    index = tile_index()
    tile_type = grid[tile_name]["type"]

    print(f"LATCH probe on {MINE_SITE} ({tile_name}, {tile_type}) -> {out}")
    unbuildable: dict[str, dict] = {}
    if not args.report_only:
        for mode in sorted(MODES):
            if not build(mode, out / MODES[mode][0], args.timeout) and mode not in MAY_FAIL:
                return 1

    # Every mode is verified against its stamp before anything is read, whether it was
    # just built or is being reported from disk.
    states = {}
    for mode, (name, _) in sorted(MODES.items()):
        state, why = verified_state(mode, out / name)
        states[mode] = state
        if state == "failed":
            if mode not in MAY_FAIL:
                raise SystemExit(f"mode {mode} ({name}) failed and is not a mode whose "
                                 "failure is a permitted answer")
            errors = [line.strip() for line in
                      (out / name / "run.out").read_text().splitlines()
                      if "ERROR" in line] if (out / name / "run.out").is_file() else []
            unbuildable[name] = {"why": why, "error_lines": errors[:5],
                                 "log": f"failures/{name}.run.out"}
            print(f"  mode {mode} ({name}): recorded as unbuildable — this mode is a "
                  f"real question, not an accident")

    cols, layout = column_map(), device_layout()
    artifacts, frames, tile_bits = {}, {}, {}
    for mode, (name, description) in sorted(MODES.items()):
        directory = out / name
        if states[mode] == "failed":
            artifacts[name] = {"mode": mode, "description": description,
                               "built": False, **unbuildable[name]}
            continue
        bitstream = directory / "spec.bit"
        readback = read_tsv(directory / "readback.tsv")
        frames[mode] = parse_frames(bitstream, cols, layout)["frames"]
        tile_bits[mode] = read_tile_bits(frames[mode], block)
        artifacts[name] = {
            "mode": mode,
            "description": description,
            "built": True,
            "bitstream": str(bitstream.relative_to(REPO)),
            "bitstream_sha256": sha256_file(bitstream),
            "checkpoint_sha256": sha256_file(directory / "base.dcp"),
            "readback_sha256": sha256_file(directory / "readback.tsv"),
            "vivado_version": readback.get("vivado_version"),
            "part": readback.get("part"),
            "storage": {k: readback.get(f"storage_{k}")
                        for k in ("ref", "loc", "bel", "init")},
            "storage_inversions": {key.split(".", 1)[1]: value
                                   for key, value in sorted(readback.items())
                                   if key.startswith("storage_prop.") and value},
            "lut": {k: readback.get(f"lut_{k}") for k in ("loc", "bel", "lock_pins")},
            # what each control pin is actually connected to: "CE is driven" as evidence
            "control_pins": {key.split(".")[1]: value
                             for key, value in sorted(readback.items())
                             if key.startswith("pin.") and key.endswith(".net")},
            "storage_count": readback.get("storage_count"),
            "storage_cells": [{"name": readback.get(f"store.{n}.name"),
                               "ref": readback.get(f"store.{n}.ref"),
                               "loc": readback.get(f"store.{n}.loc"),
                               "bel": readback.get(f"store.{n}.bel"),
                               "init": readback.get(f"store.{n}.init")}
                              for n in range(int(readback.get("storage_count", 0) or 0))],
            "lut_cells": [{"name": readback.get(f"lut.{n}.name"),
                           "ref": readback.get(f"lut.{n}.ref"),
                           "loc": readback.get(f"lut.{n}.loc"),
                           "bel": readback.get(f"lut.{n}.bel")}
                          for n in range(int(readback.get("lut_count", 0) or 0))],
            "occupied_bels": [value for key, value in sorted(readback.items())
                              if re.fullmatch(r"occupied\.\d+\.bel", key)],
            "anchor_placement": {key: value for key, value in sorted(readback.items())
                                 if key.startswith("anchor.")},
        }

    # Same-class movers: which features of THIS class each changed bit of the site's own
    # tile belongs to, and which way it moved. This is the list the ruling asks for.
    def movers(a: int, b: int) -> list[dict]:
        out_rows = []
        for token, before in sorted(tile_bits[a].items()):
            after = tile_bits[b].get(token)
            if after == before:
                continue
            frame, bit = (int(x) for x in token.split("_"))
            claimed = sorted(f for f in features_using(tile_type, token)
                             if pattern.fullmatch(f))
            out_rows.append({
                "segbit": token,
                "address": {"far": f"0x{int(block['baseaddr'], 16) + frame:08X}",
                            "word": block["offset"] + bit // 32, "bit": bit % 32},
                "before": before, "after": after,
                "direction": f"{before}->{after}",
                "class_features": claimed,
                "all_features": sorted(features_using(tile_type, token)),
            })
        return out_rows

    latch_feature = None
    for line in (REPO / f"data/prjxray/zynq7/segbits_{tile_type.lower()}.db").read_text().splitlines():
        fields = line.split()
        if fields and fields[0].endswith(".LATCH") and pattern.fullmatch(fields[0]):
            # the site instance under test is SLICEL_X0 of this tile
            if ".SLICEL_X0." in fields[0] or ".SLICEM_X0." in fields[0]:
                latch_feature = (fields[0], fields[1])
    if latch_feature is None:
        raise SystemExit(f"no LATCH rule for {tile_type} in the freeze")
    latch_token = latch_feature[1].lstrip("!")
    latch_frame, latch_bit = (int(x) for x in latch_token.split("_"))
    latch_address = (int(block["baseaddr"], 16) + latch_frame,
                     block["offset"] + latch_bit // 32, latch_bit % 32)

    pairs = []
    for a, b, name, question in PAIRS:
        if a not in frames or b not in frames:
            pairs.append({"pair": name, "question": question,
                          "modes": [MODES[a][0], MODES[b][0]],
                          "not_measured": "an endpoint of this pair could not be built"})
            continue
        raw = raw_diff(frames[a], frames[b])
        # The scope a real LATCH pair would preregister: exactly the one LATCH bit. The
        # two "cost" pairs make no LATCH claim, so they get no scope and every mover in
        # them is out of scope by construction — that is what makes them a control, not
        # a candidate.
        claims_latch = name in LATCH_PAIRS
        scope = {latch_address} if claims_latch else set()
        buckets, class_out_of_scope = classify_diff(
            raw, scope, index, pattern, {tile_name})
        fp = buckets["ownership_unknown"] | buckets["unattributed"] | class_out_of_scope
        same_class = movers(a, b)
        pairs.append({
            "pair": name,
            "question": question,
            "modes": [MODES[a][0], MODES[b][0]],
            "raw_diff_bits": len(raw),
            "counts": {key: len(value) for key, value in buckets.items()},
            "buckets": {key: as_addresses(value) for key, value in buckets.items()},
            "preregistered_scope": as_addresses(scope),
            "same_class_movers": same_class,
            "same_class_movers_outside_scope": [
                row for row in same_class
                if address_tuple(row["address"]) not in scope],
            "false_positive_count_under_1_4": len(fp),
            "false_positive_addresses": as_addresses(fp),
            "claims_latch": claims_latch,
            "isolated_to_latch_bit": (
                claims_latch and len(same_class) == 1
                and address_tuple(same_class[0]["address"]) == latch_address
                and not fp),
        })

    report = {
        "schema": "ff_latch_probe",
        "schema_version": "1.1.0",
        "status": "exploration — not evidence for any certificate",
        "bit_class": BIT_CLASS,
        "site": MINE_SITE,
        "site_split": "mine (evidence already spent; can never score)",
        "tile": tile_name,
        "tile_type": tile_type,
        "latch_feature": {"feature": latch_feature[0], "token": latch_feature[1],
                          "address": {"far": f"0x{latch_address[0]:08X}",
                                      "word": latch_address[1], "bit": latch_address[2]}},
        "recipe": recipe_hashes(),
        "unbuildable_modes": unbuildable,
        "artifacts": artifacts,
        "pairs": pairs,
        "commitment": "none emitted; PREREGISTRATION_HOLD untouched",
    }
    report_path = out / "probe_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    # A portable copy. `build/` is gitignored, so a report that lived only there names
    # evidence a fresh clone cannot resolve — the same reason measurements copy their
    # attestations into the run directory. The bitstreams stay behind (they are large
    # and rebuildable from the pinned recipe); what travels is the full bucket
    # addresses, the raw readbacks, and every hash needed to tell whether a rebuild
    # produced the same thing.
    if args.evidence:
        evidence = args.evidence.resolve()
        evidence.mkdir(parents=True, exist_ok=True)
        (evidence / "probe_report.json").write_text(json.dumps(report, indent=2) + "\n")
        readbacks = evidence / "readbacks"
        readbacks.mkdir(exist_ok=True)
        for mode, (name, _) in sorted(MODES.items()):
            source = out / name / "readback.tsv"
            if source.is_file():
                (readbacks / f"{name}.tsv").write_bytes(source.read_bytes())
        # A mode that cannot be built is a RESULT, so its log travels with the record.
        # Saying "see run.out" while run.out lives only under gitignored build/ names
        # evidence nobody else can read — which is the same defect as leaving the report
        # there, one level further down.
        failures = evidence / "failures"
        failures.mkdir(exist_ok=True)
        for name in unbuildable:
            source = out / name / "run.out"
            if source.is_file():
                (failures / f"{name}.run.out").write_bytes(source.read_bytes())
            stamp = out / name / "stamp.json"
            if stamp.is_file():
                (failures / f"{name}.stamp.json").write_bytes(stamp.read_bytes())
        (evidence / "manifest.json").write_text(json.dumps({
            "schema": "ff_latch_probe_evidence",
            "schema_version": "1.0.0",
            "bit_class": BIT_CLASS,
            "note": "exploration on the mine site; no prediction, commitment or certificate",
            "site": MINE_SITE, "tile": tile_name, "tile_type": tile_type,
            "recipe": recipe_hashes(),
            "vivado_version": sorted({a.get("vivado_version") for a in artifacts.values()
                                      if a.get("vivado_version")}),
            "part": sorted({a.get("part") for a in artifacts.values() if a.get("part")}),
            "unbuildable_modes": unbuildable,
            "bitstreams_not_copied": {
                name: {"bitstream_sha256": a.get("bitstream_sha256"),
                       "checkpoint_sha256": a.get("checkpoint_sha256"),
                       "readback_sha256": a.get("readback_sha256")}
                for name, a in artifacts.items() if a.get("built")},
            "files": {"probe_report.json": sha256_file(evidence / "probe_report.json"),
                      **{f"readbacks/{path.name}": sha256_file(path)
                         for path in sorted(readbacks.iterdir())},
                      **{f"failures/{path.name}": sha256_file(path)
                         for path in sorted(failures.iterdir())}},
        }, indent=2) + "\n")
        print(f"  portable evidence -> {evidence.relative_to(REPO)}")

    print(f"\n  LATCH bit: {latch_feature[0]} = {latch_feature[1]} "
          f"-> 0x{latch_address[0]:08X}/w{latch_address[1]}/b{latch_address[2]}")
    for record in pairs:
        if "not_measured" in record:
            print(f"\n  pair {record['pair']} ({' -> '.join(record['modes'])}): "
                  f"NOT MEASURED — {record['not_measured']}")
            continue
        counts = record["counts"]
        print(f"\n  pair {record['pair']} ({' -> '.join(record['modes'])}): "
              f"raw={record['raw_diff_bits']}")
        print("    " + "  ".join(f"{key}={counts[key]}" for key in BUCKETS))
        print(f"    same-class movers: {len(record['same_class_movers'])}, "
              f"outside scope: {len(record['same_class_movers_outside_scope'])}, "
              f"FP under 1.4: {record['false_positive_count_under_1_4']}")
        for row in record["same_class_movers"]:
            names = ", ".join(f.split(".", 2)[2] for f in row["class_features"]) or "(none)"
            print(f"      {row['segbit']}  {row['direction']}  {names}")
        if record["claims_latch"]:
            print(f"    ISOLATED TO THE LATCH BIT: {record['isolated_to_latch_bit']}")
    print(f"\n  wrote {report_path}")
    print("  exploration only — no commitment emitted, hold untouched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
