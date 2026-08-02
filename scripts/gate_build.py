#!/usr/bin/env python3
"""Build exactly the specimens a pre-registered prediction file planned — no more.

The build plan is read from `predictions.json`, never composed here, so the set of
bitstreams that exist cannot quietly differ from the set that was committed to.  Each
(site, BEL) pair is one Vivado invocation producing the base plus its variants, and
each output directory gets its own attestation.

    scripts/gate_build.py --run gate_runs/run_2026_08_02_a --out build/gate
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
TCL = REPO / "vivado/specimen/build_specimen.tcl"
RUN_VIVADO = REPO / "scripts/run_vivado.sh"
ATTEST = REPO / "scripts/specimen_attest.py"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", type=Path, required=True, help="dir holding predictions.json")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--timeout", type=int, default=1800)
    args = ap.parse_args()

    pred_path = args.run / "predictions.json"
    doc = json.loads(pred_path.read_text())
    digest = hashlib.sha256(pred_path.read_bytes()).hexdigest()
    print(f"plan: {pred_path} sha256 {digest}")

    plan: dict[tuple[str, str], list[str]] = defaultdict(list)
    for s in doc["specimens"]:
        plan[(s["site"], s["bel"])].append(s["variant_init"])
        base = s["base_init"]

    failures = []
    for (site, bel), inits in sorted(plan.items()):
        outdir = args.out / f"{site}_{bel}"
        outdir.mkdir(parents=True, exist_ok=True)
        tclargs = [str(outdir.resolve()), site, bel, base, *sorted(set(inits))]
        print(f"  building {site}/{bel}: {len(set(inits))} variant(s)")
        r = subprocess.run(
            [str(RUN_VIVADO), "-mode", "batch", "-nojournal", "-notrace",
             "-log", str(outdir / "vivado.log"), "-source", str(TCL), "-tclargs", *tclargs],
            cwd=outdir, capture_output=True, text=True, timeout=args.timeout)
        if r.returncode != 0 or "SPECIMEN_DONE" not in r.stdout:
            (outdir / "run.out").write_text(r.stdout + r.stderr)
            failures.append(f"{site}/{bel}: vivado rc={r.returncode}, see {outdir}/run.out")
            continue
        (outdir / "run.out").write_text(r.stdout)
        a = subprocess.run([sys.executable, str(ATTEST), "--dir", str(outdir),
                            "--tclargs", *tclargs[1:]], capture_output=True, text=True)
        print("   ", a.stdout.strip().replace("\n", "\n    "))
        if a.returncode != 0:
            failures.append(f"{site}/{bel}: attestation rejected the build (pin mapping "
                            f"not identity) — predictions for interior INIT bits are void")

    for f in failures:
        print(f"FAILED {f}", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
