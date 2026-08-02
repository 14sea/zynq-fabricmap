#!/usr/bin/env python3
"""Bind a specimen family's bitstreams to the exact build that produced them.

The certificate has to be able to show that the measured feature index was protected
from Vivado's implementation freedom — above all from LUT input pin swapping, which
silently moves every interior INIT bit (`docs/specimen_harness.md`).  Hashing the
build inputs is not enough: a hash of the RTL and Tcl proves what was *asked for*.
So this attestation carries both:

  inputs   sha256 of every design input (HDL, Tcl, the tclargs, part, tool version)
  resolved what the tool actually did, read back from the routed design by the Tcl:
           resolved LOC/BEL, LOCK_PINS as the tool reports it, and the resolved
           I0..I5 -> A1..A6 bel-pin mapping
  outputs  sha256 of each emitted bitstream

The sha256 of the resulting attestation.json is what a certificate pins.

    scripts/specimen_attest.py --dir build/spec [--tclargs ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
# Which design inputs a specimen family was built from.  Passed explicitly rather
# than assumed: a mux specimen is a different HDL and a different Tcl, and attesting
# the wrong pair would produce a record that hashes cleanly and means nothing.
DESIGN_INPUTS = {
    "lut": [REPO / "vivado/specimen/specimen_lut.v",
            REPO / "vivado/specimen/build_specimen.tcl"],
    "mux": [REPO / "vivado/specimen/specimen_mux.v",
            REPO / "vivado/specimen/build_mux.tcl"],
}


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", type=Path, required=True, help="specimen output directory")
    ap.add_argument("--tclargs", nargs="*", default=[], help="the tclargs used")
    ap.add_argument("--family", choices=sorted(DESIGN_INPUTS), default="lut",
                    help="which specimen family's design inputs to attest")
    args = ap.parse_args()

    placement = json.loads((args.dir / "placement.json").read_text())
    # Driver readback, when a family has one.  placement.json is written during the
    # build; ff_readback.json is read back from the routed checkpoint afterwards and
    # names the cell that actually drives the FF's D net.
    rb = args.dir / "ff_readback.json"
    if rb.is_file():
        placement.update(json.loads(rb.read_text()))
    att = {
        "schema": "specimen_attestation",
        "schema_version": "1.0.0",
        "inputs": {
            "family": args.family,
            "files": {str(p.relative_to(REPO)): sha256(p)
                      for p in DESIGN_INPUTS[args.family]},
            "tclargs": args.tclargs,
            "part": placement["part"],
            "vivado_version": placement["vivado_version"],
        },
        # Everything the tool read back, not a hand-picked subset: an allowlist here
        # silently dropped the FF's LOC/BEL and its data-source fields, which are the
        # only evidence that the netlist edge a semantic claim names was actually built.
        "resolved": {k: v for k, v in placement.items()
                     if k not in ("part", "vivado_version", "variants")},
        # The routed checkpoint. Hashing it alongside the bitstream PINS both against
        # later substitution; it does not independently prove the bitstream was
        # produced from this checkpoint. That relationship is asserted by this record,
        # and can only be re-established by rebuilding with Vivado.
        "checkpoint": ({"file": "base.dcp", "sha256": sha256(args.dir / "base.dcp")}
                       if (args.dir / "base.dcp").is_file() else None),
        "outputs": {p.name: sha256(p) for p in sorted(args.dir.glob("*.bit"))},
    }
    # The claim the pin mapping exists to support, checked here rather than trusted.
    identity = {f"I{k}": f"A{k + 1}" for k in range(6)}
    resolved = {k: v.rsplit("/", 1)[-1] for k, v in att["resolved"]["pin_mapping"].items()}
    att["resolved"]["pin_mapping_is_identity"] = resolved == identity
    if not att["resolved"]["pin_mapping_is_identity"]:
        att["resolved"]["pin_mapping_warning"] = (
            "LUT inputs are permuted: logical INIT bit index != physical truth-table "
            "index. Predictions for interior bits will be wrong unless the permutation "
            "is applied. See docs/specimen_harness.md.")

    out = args.dir / "attestation.json"
    out.write_text(json.dumps(att, indent=2) + "\n")
    print(f"{out}: sha256 {sha256(out)}")
    print(f"  pin mapping identity: {att['resolved']['pin_mapping_is_identity']}")
    print(f"  bitstreams attested : {len(att['outputs'])}")
    return 0 if att["resolved"]["pin_mapping_is_identity"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
