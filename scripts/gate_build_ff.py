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
}

PAIRS = (
    (0, 1, "control_matched", "first candidate: does matching the reset kind isolate LATCH?"),
    (3, 1, "control_matched_clkinv", "second candidate: reset kind AND clock polarity matched"),
    (2, 1, "plan_default", "what the plan as written would have diffed"),
    (2, 0, "control_match_cost", "what matching the reset kind itself moves"),
    (0, 3, "clock_inversion_cost", "what matching the clock polarity itself moves"),
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if "\t" in line:
            key, value = line.split("\t", 1)
            out[key] = value
    return out


def build(mode: int, outdir: Path, timeout: int) -> bool:
    outdir.mkdir(parents=True, exist_ok=True)
    if (outdir / "spec.bit").is_file() and (outdir / "readback.tsv").is_file():
        print(f"  mode {mode} ({MODES[mode][0]}): already built")
        return True
    tclargs = [str(outdir.resolve()), MINE_SITE, str(mode)]
    checked = subprocess.run(
        [str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
         "-log", str(outdir / "vivado.log"), "-source", str(TCL), "-tclargs", *tclargs],
        cwd=outdir, capture_output=True, text=True, timeout=timeout)
    (outdir / "run.out").write_text(checked.stdout + checked.stderr)
    ok = checked.returncode == 0 and "SPECIMEN_DONE" in checked.stdout
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
    if not args.report_only:
        for mode in sorted(MODES):
            if not build(mode, out / MODES[mode][0], args.timeout):
                return 1

    cols, layout = column_map(), device_layout()
    artifacts, frames, tile_bits = {}, {}, {}
    for mode, (name, description) in sorted(MODES.items()):
        directory = out / name
        bitstream = directory / "spec.bit"
        if not bitstream.is_file():
            raise SystemExit(f"mode {mode}: no bitstream at {bitstream}")
        readback = read_tsv(directory / "readback.tsv")
        frames[mode] = parse_frames(bitstream, cols, layout)["frames"]
        tile_bits[mode] = read_tile_bits(frames[mode], block)
        artifacts[name] = {
            "mode": mode,
            "description": description,
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
        raw = raw_diff(frames[a], frames[b])
        # The scope a real LATCH pair would preregister: exactly the one LATCH bit. The
        # two "cost" pairs make no LATCH claim, so they get no scope and every mover in
        # them is out of scope by construction — that is what makes them a control, not
        # a candidate.
        claims_latch = name in ("control_matched", "control_matched_clkinv", "plan_default")
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
        "schema_version": "1.0.0",
        "status": "exploration — not evidence for any certificate",
        "bit_class": BIT_CLASS,
        "site": MINE_SITE,
        "site_split": "mine (evidence already spent; can never score)",
        "tile": tile_name,
        "tile_type": tile_type,
        "latch_feature": {"feature": latch_feature[0], "token": latch_feature[1],
                          "address": {"far": f"0x{latch_address[0]:08X}",
                                      "word": latch_address[1], "bit": latch_address[2]}},
        "artifacts": artifacts,
        "pairs": pairs,
        "commitment": "none emitted; PREREGISTRATION_HOLD untouched",
    }
    report_path = out / "probe_report.json"
    report_path.write_text(json.dumps(report, indent=2) + "\n")

    print(f"\n  LATCH bit: {latch_feature[0]} = {latch_feature[1]} "
          f"-> 0x{latch_address[0]:08X}/w{latch_address[1]}/b{latch_address[2]}")
    for record in pairs:
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
