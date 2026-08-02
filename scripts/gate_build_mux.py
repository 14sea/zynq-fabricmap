#!/usr/bin/env python3
"""Build exactly the clb_mux specimens the pre-registered predictions planned.

One Vivado run per specimen, because a mux selection is structural and each variant is
its own implementation. The plan is read from predictions.json, never composed here.

    scripts/gate_build_mux.py --run gate_runs/run_2026_08_02_b --out build/gate_mux
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TCL = REPO / "vivado/specimen/build_mux.tcl"
RUN_VIVADO = REPO / "scripts/run_vivado.sh"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--run", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    pred = args.run / "predictions.json"
    doc = json.loads(pred.read_text())
    print(f"plan: {pred} sha256 {hashlib.sha256(pred.read_bytes()).hexdigest()}")

    failures = []
    for k, s in enumerate(doc["specimens"], 1):
        outdir = args.out / s["specimen_id"]
        outdir.mkdir(parents=True, exist_ok=True)
        if (outdir / f"spec_{s['ff_bel']}_ffsrc{s['ffsrc']}.bit").is_file():
            print(f"  [{k}/{len(doc['specimens'])}] {s['specimen_id']}: already built")
            continue
        tclargs = [str(outdir.resolve()), s["site"], str(s["ffsrc"]), s["ff_bel"]]
        r = subprocess.run([str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
                            "-log", str(outdir / "vivado.log"), "-source", str(TCL),
                            "-tclargs", *tclargs],
                           cwd=outdir, capture_output=True, text=True, timeout=args.timeout)
        (outdir / "run.out").write_text(r.stdout + r.stderr)
        ok = r.returncode == 0 and "SPECIMEN_DONE" in r.stdout
        print(f"  [{k}/{len(doc['specimens'])}] {s['specimen_id']}: {'ok' if ok else 'FAILED'}")
        if not ok:
            failures.append(s["specimen_id"])

    for f in failures:
        print(f"FAILED {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
