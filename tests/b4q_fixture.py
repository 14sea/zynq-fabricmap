"""The shared fixture of the B4Q tests (the owner's P3 of 2026-10-27): the executing side BUILT and the `valid` offline scenario
GENERATED under build/b4q_e2e/valid before any test consumes it — a directory's existence is not completion: the fixture is
complete only when the manifest declares four records, every record directory holds its files and the access log is present;
anything else is regenerated. Prerequisites stated: a host C compiler; the instrument at /home/test/zynq_psoracle (the signer
library); nothing else. (The carrier bench test, tests/test_b4carrier_benches.py, additionally needs iverilog, the UNISIM
sources and the ignored GSR-aware netlist builds/b4/b4_core_funcsim.v — a carrier-unit dependency, not this unit's.)"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
VALID = R / "build/b4q_e2e/valid"


def complete(d: Path = VALID) -> bool:
    try:
        m = json.loads((d / "manifest.json").read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(m, dict) or len(m.get("records", [])) != 4 or m.get("halted") is not None or "qualification_plan" not in m:
        return False
    for r in m["records"]:
        if not isinstance(r, dict) or not isinstance(r.get("dir"), str):
            return False
        td = d / r["dir"]
        if not all((td / f).is_file() for f in ("o.json", "x.json", "ctx.json", "links.json", "firmware_result.json", "record.json")):
            return False
    return (d / "accesses.jsonl").is_file() and (d / "pcap_log.jsonl").is_file() and (d / "trace.jsonl").is_file()


def ensure(d: Path = VALID) -> Path:
    """Build the executing side (always: a stale binary is as bad as none) and generate the fixture unless it is complete."""
    p = subprocess.run(["bash", str(R / "firmware/b4q/build.sh")], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"the executing side did not build (a failure, never a skip):\n{p.stdout}{p.stderr}")
    if not complete(d):
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_e2e.py"), str(d.parent), "valid"], capture_output=True, text=True, timeout=600)
        if q.returncode != 0 or not complete(d):
            raise AssertionError(f"the valid fixture could not be generated:\n{q.stdout[-2000:]}{q.stderr[-2000:]}")
    return d
