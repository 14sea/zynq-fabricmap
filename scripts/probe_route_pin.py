#!/usr/bin/env python3
"""PROBE ONLY — find a way to pin the nine dedicated anchor/keeper nets, on the mine site.

Not a recipe-domain file and not part of any committed build. It answers one question
before the specimen design is touched, so the recipe is edited once rather than once per
idea — every edit invalidates all 184 artifacts.

The question comes from the 2026-08-06 holdout run: `SLICE_X25Y25_base` and `…_ce_tied`
differ by one control connection, and the router put `w1` on a different path, failing
T2. The mine instance cannot reproduce that symptom — its 15 implementations already
share one route for all nine nets — so this probe does not chase the symptom. It tests
the mechanism, with a perturbation that is available on the mine site:

  * **current flow, two router directives** — if the dedicated routes move, the mine site
    has a reproducible trigger of the same class (the router answering differently on one
    design);
  * **pinned flow, the same two directives** — the routes must not move at all;
  * **pinned flow, across variants** — `base`, `ce_tied`, `latch`, `async`, `clkinv` must
    agree byte for byte, and each run's own `first_pass` snapshot must equal its `final`
    one, which is what proves the second routing pass did not revisit them.

Only `SLICE_X2Y25` is ever built here, and nothing reads a bitstream, a frame or any
holdout artifact.

    scripts/probe_route_pin.py --out build/probe_route_pin
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))

import gate_build_ff_formal as builder  # noqa: E402

PROBE_TCL = REPO / "vivado/probe/route_pin/probe_route_pin.tcl"
SITE = "SLICE_X2Y25"
DEDICATED = ("w1", "w2", "qr1", "q_OBUF", "anchor_o_OBUF", "anchor_o2_OBUF",
             "q", "anchor_o", "anchor_o2")

# (label, variant, flow, directive)
MATRIX = [
    ("current/base/Default", "base", "current", "Default"),
    ("current/base/Explore", "base", "current", "Explore"),
    ("current/base/AlternateCLBRouting", "base", "current", "AlternateCLBRouting"),
    ("current/base/NoTimingRelaxation", "base", "current", "NoTimingRelaxation"),
    ("current/ce_tied/Default", "ce_tied", "current", "Default"),
    ("current/ce_tied/Explore", "ce_tied", "current", "Explore"),
    ("pinned/base/Default", "base", "pinned", "Default"),
    ("pinned/base/Explore", "base", "pinned", "Explore"),
    ("pinned/base/AlternateCLBRouting", "base", "pinned", "AlternateCLBRouting"),
    ("pinned/ce_tied/Default", "ce_tied", "pinned", "Default"),
    ("pinned/ce_tied/Explore", "ce_tied", "pinned", "Explore"),
    ("pinned/latch/Default", "latch", "pinned", "Default"),
    ("pinned/async/Default", "async", "pinned", "Default"),
    ("pinned/clkinv/Default", "clkinv", "pinned", "Default"),
]


def read_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("\t")
        out[key] = value
    return out


def run_one(out_root: Path, label: str, variant: str, flow: str, directive: str,
            timeout: int) -> tuple[str, float]:
    spec = builder.VARIANTS[variant]
    sites = builder.sites_for(SITE)
    outdir = out_root / label.replace("/", "_")
    outdir.mkdir(parents=True, exist_ok=True)
    args = [str(outdir), SITE, sites["anchor"], sites["keeper"], variant,
            str(spec["mode"]), str(spec["idx"]), flow, directive]
    started = time.time()
    with (outdir / "vivado.log").open("w") as log:
        checked = subprocess.run(
            [str(REPO / "scripts/run_vivado.sh"), "-mode", "batch", "-nojournal",
             "-notrace", "-log", str(outdir / "run.log"), "-source", str(PROBE_TCL),
             "-tclargs", *args],
            cwd=outdir, stdout=log, stderr=subprocess.STDOUT, timeout=timeout, check=False)
    elapsed = time.time() - started
    if checked.returncode != 0 or not (outdir / "probe_routes.tsv").is_file():
        return "FAILED", elapsed
    return "ok", elapsed


def compare(out_root: Path) -> int:
    runs = {}
    for label, *_rest in MATRIX:
        path = out_root / label.replace("/", "_") / "probe_routes.tsv"
        if path.is_file():
            runs[label] = read_tsv(path)
    if not runs:
        print("no probe run produced a route snapshot")
        return 1

    print("\n--- each run: did the second pass move what the first pass routed? ------")
    problems = []
    for label, kv in runs.items():
        moved = [name for name in DEDICATED
                 if kv.get(f"first_pass.{name}.route") != kv.get(f"final.{name}.route")
                 or kv.get(f"first_pass.{name}.pips") != kv.get(f"final.{name}.pips")]
        fixed = {kv.get(f"final.{name}.fixed") for name in DEDICATED}
        print(f"  {label:26} moved_after_first_pass={len(moved):2}  is_route_fixed={sorted(fixed)}")
        if label.startswith("pinned") and moved:
            problems.append(f"{label}: the pinned flow let {len(moved)} net(s) move: {moved}")

    def signature(kv: dict[str, str]) -> tuple:
        return tuple((name, kv.get(f"final.{name}.route"), kv.get(f"final.{name}.pips"))
                     for name in DEDICATED)

    print("\n--- do runs agree on the nine dedicated routes? --------------------------")
    for flow in ("current", "pinned"):
        group = {label: signature(kv) for label, kv in runs.items()
                 if label.startswith(flow)}
        if not group:
            continue
        distinct = {sig: [lab for lab, s in group.items() if s == sig]
                    for sig in set(group.values())}
        print(f"  {flow:8} runs={len(group)}  distinct route sets={len(distinct)}")
        for sig, labels in distinct.items():
            differing = [name for name, *_ in sig] if len(distinct) > 1 else []
            print(f"      {labels}")
        if flow == "pinned" and len(distinct) > 1:
            reference = signature(runs["pinned/base/Default"])
            for label, sig in group.items():
                bad = [name for (name, route, pips), (rname, rroute, rpips)
                       in zip(sig, reference) if route != rroute or pips != rpips]
                if bad:
                    problems.append(f"{label}: dedicated nets differ from "
                                    f"pinned/base/Default: {bad}")

    current = {label: signature(kv) for label, kv in runs.items()
               if label.startswith("current")}
    trigger = len(set(current.values())) > 1 if current else False
    print("\n--- verdict --------------------------------------------------------------")
    print(f"  reproducible trigger on the mine site (current flow disagrees): {trigger}")
    if not trigger:
        print("    NOTE: without a trigger the mine site cannot show the fix WORKING,")
        print("    only that it did not regress. Say so rather than claiming a fix.")
    print(f"  pinned flow problems: {len(problems)}")
    for problem in problems:
        print(f"    {problem}")
    (out_root / "verdict.json").write_text(json.dumps({
        "trigger_reproduced": trigger,
        "problems": problems,
        "runs": sorted(runs),
    }, indent=2) + "\n")
    return 1 if problems else 0


def collect_evidence(out_root: Path, evidence: Path) -> None:
    """Copy the run's artifacts into versioned evidence and pin them in a manifest.

    Extensions matter here: the first version of this evidence directory kept the
    transcript as `probe_run.log`, which `.gitignore`'s `*.log` rule silently excluded,
    so the README pointed at a file the commit did not contain. Everything the manifest
    lists is copied with a tracked extension and its presence is asserted.
    """
    evidence.mkdir(parents=True, exist_ok=True)
    sites = builder.sites_for(SITE)
    entries: dict[str, dict] = {}

    def pin(source: Path, name: str, role: str) -> None:
        target = evidence / name
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        entries[name] = {"role": role,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    for label, *_rest in MATRIX:
        stem = label.replace("/", "_")
        snapshot = out_root / stem / "probe_routes.tsv"
        if snapshot.is_file():
            pin(snapshot, f"{stem}.probe_routes.tsv", "route snapshot")
    pin(out_root / "verdict.json", "verdict.json", "verdict")
    transcript = out_root.parent / f"{out_root.name}.log"
    if transcript.is_file():
        pin(transcript, "probe_run.txt", "driver transcript")

    tools = {}
    for path in (Path(__file__).resolve(), PROBE_TCL):
        tools[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()
    inputs = {}
    for path in (REPO / "vivado/specimen/specimen_ff_formal.v",
                 REPO / "vivado/specimen/ff_formal_readback.tcl"):
        inputs[str(path.relative_to(REPO))] = hashlib.sha256(path.read_bytes()).hexdigest()

    manifest = {
        "schema": "probe_evidence/1",
        "probe": "route_pin",
        "note": ("Hashes are integrity anchors: they detect substitution of these files. "
                 "They do not prove Vivado produced these snapshots, and they are not a "
                 "target for any later run to reproduce."),
        "vivado_version": builder.vivado_version(),
        "part": builder.PART,
        "site_mapping": {"target": SITE, "anchor": sites["anchor"],
                         "keeper": sites["keeper"]},
        "matrix": [{"label": label, "variant": variant, "flow": flow,
                    "directive": directive} for label, variant, flow, directive in MATRIX],
        "probe_tools": tools,
        "recipe_sources_read": inputs,
        "files": dict(sorted(entries.items())),
    }
    (evidence / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    missing = [name for name in entries if not (evidence / name).is_file()]
    if missing:
        raise SystemExit(f"manifest lists files that are not there: {missing}")
    print(f"evidence: {len(entries)} files pinned in {evidence / 'manifest.json'}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=REPO / "build/probe_route_pin")
    ap.add_argument("--evidence", type=Path, default=None,
                    help="copy artifacts here and write a manifest pinning them")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--compare-only", action="store_true")
    args = ap.parse_args()

    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if args.evidence is not None:
        collect_evidence(out_root, args.evidence.resolve())
        return 0
    if not args.compare_only:
        for label, variant, flow, directive in MATRIX:
            state, elapsed = run_one(out_root, label, variant, flow, directive, args.timeout)
            print(f"  {label:26} {state:8} {elapsed:6.1f}s", flush=True)
    return compare(out_root)


if __name__ == "__main__":
    raise SystemExit(main())
