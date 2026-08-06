#!/usr/bin/env python3
"""PROBE ONLY — reproduce the T2 routing freedom on a NON-COMMITTED site, then remove it.

The mine instance cannot show the fix working: its nine dedicated nets take one route
under every variant and every router directive, before any change. So this probe moves to
a sacrificial site of the same geometry as the failure point and creates the congestion
itself, which is the one thing the mine site would not provide.

    target SLICE_X31Y25   keeper SLICE_X31Y20   anchor SLICE_X33Y20
    CLBLM_R / SLICEL / row 25, the same classes as SLICE_X25Y25, and none of the three
    is one of the commitment's 24 target/keeper/anchor sites.

**Every role, and every congestion site, is recomputed against the published commitment
and refused if it touches a committed site.** The refusal is not a courtesy check: a
probe that writes into a committed instance's site would put a bitstream nobody planned
next to artifacts that are supposed to be a closed set.

The pass criteria are stated before the run, in `CRITERIA` below, and evaluated by
`verdict()`. Reproducing the freedom is a *precondition*: if the current flow does not
disagree with itself, this probe has not shown anything about the fix and says so.

    scripts/probe_sacrificial_site.py --out build/probe_sacrificial
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

PROBE_TCL = REPO / "vivado/probe/route_pin/probe_congest.tcl"
TILEGRID = REPO / "data/prjxray/zynq7/xc7z010/tilegrid.json"

TARGET = "SLICE_X31Y25"
DEDICATED = ("w1", "w2", "qr1", "q_OBUF", "anchor_o_OBUF", "anchor_o2_OBUF",
             "q", "anchor_o", "anchor_o2")
ROUTABLE = DEDICATED[:6]          # the six with an interconnect route
INTRASITE = DEDICATED[6:]         # the three pad nets, which have none

# Slices around the anchor and along the anchor->keeper span, four LUT6 cells each.
CONGEST_SITES = ["SLICE_X32Y20", "SLICE_X34Y20", "SLICE_X30Y20", "SLICE_X35Y20",
                 "SLICE_X32Y21", "SLICE_X34Y21", "SLICE_X30Y21", "SLICE_X33Y21"]

CRITERIA = [
    "the current flow, under two congestion conditions, routes at least one dedicated "
    "net differently (the freedom is reproduced)",
    "the pinned flow, under the same conditions, variants and directives, yields one "
    "route set",
    "no dedicated net moves after the freeze, in any pinned run",
    "endpoints, drivers and sinks are identical across every run",
    "the six routable nets read IS_ROUTE_FIXED=1 in the six pinned runs",
    "the three pad nets stay INTRASITE with empty route and pips in all ten runs",
]

# (label, variant, flow, directive, congest)
MATRIX = [
    ("current/base/Default/c0", "base", "current", "Default", 0),
    ("current/base/Default/c32", "base", "current", "Default", 32),
    ("current/ce_tied/Default/c0", "ce_tied", "current", "Default", 0),
    ("current/ce_tied/Default/c32", "ce_tied", "current", "Default", 32),
    ("pinned/base/Default/c0", "base", "pinned", "Default", 0),
    ("pinned/base/Default/c32", "base", "pinned", "Default", 32),
    ("pinned/ce_tied/Default/c0", "ce_tied", "pinned", "Default", 0),
    ("pinned/ce_tied/Default/c32", "ce_tied", "pinned", "Default", 32),
    ("pinned/base/Explore/c32", "base", "pinned", "Explore", 32),
    ("pinned/latch/Default/c32", "latch", "pinned", "Default", 32),
]


def committed_sites() -> set[str]:
    """The 24 target/keeper/anchor sites, recomputed from the published commitment."""
    plan = json.loads(builder.COMMITMENT.read_text())
    digest = hashlib.sha256(builder.COMMITMENT.read_bytes()).hexdigest()
    if digest != builder.COMMITTED_SHA256:
        raise SystemExit(f"commitment sha256 is {digest}, expected "
                         f"{builder.COMMITTED_SHA256} — refusing to derive anything")
    sites: set[str] = set()
    for target in sorted({item["site"] for item in plan["specimens"]}):
        sites.update(builder.sites_for(target).values())
    if len(sites) != 24:
        raise SystemExit(f"expected 24 committed role sites, computed {len(sites)}")
    return sites


def site_classes() -> dict[str, tuple[str, str, str]]:
    grid = json.loads(TILEGRID.read_text())
    out: dict[str, tuple[str, str, str]] = {}
    for tile, info in grid.items():
        for site, site_type in (info.get("sites") or {}).items():
            if site.startswith("SLICE_"):
                out[site] = (tile, info["type"], site_type)
    return out


def check_scope(roles: dict[str, str], congest: list[str]) -> dict:
    """Refuse before building if any site this probe touches is a committed one."""
    committed = committed_sites()
    classes = site_classes()
    used = {**roles, **{f"congest[{i}]": s for i, s in enumerate(congest)}}

    collisions = {label: site for label, site in used.items() if site in committed}
    if collisions:
        raise SystemExit(
            "refusing to run: this probe would touch committed sites.\n  "
            + "\n  ".join(f"{label} -> {site}" for label, site in sorted(collisions.items())))
    unknown = {label: site for label, site in used.items() if site not in classes}
    if unknown:
        raise SystemExit(f"refusing to run: sites absent from the freeze: {unknown}")
    if len(set(roles.values())) != len(roles):
        raise SystemExit(f"refusing to run: probe roles are not distinct: {roles}")

    rule = builder.sites_for(roles["target"])
    if rule != roles:
        raise SystemExit(f"refusing to run: roles {roles} are not what the site rule "
                         f"gives for {roles['target']}: {rule}")
    return {
        "committed_sites": sorted(committed),
        "probe_roles": {role: {"site": site, "tile": classes[site][0],
                               "tile_type": classes[site][1],
                               "site_type": classes[site][2]}
                        for role, site in roles.items()},
        "congestion_sites": [{"site": s, "tile_type": classes[s][1]} for s in congest],
    }


def read_tsv(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        key, _, value = line.partition("\t")
        out[key] = value
    return out


def run_one(out_root: Path, label: str, variant: str, flow: str, directive: str,
            congest: int, roles: dict[str, str], timeout: int) -> tuple[str, float]:
    spec = builder.VARIANTS[variant]
    outdir = out_root / label.replace("/", "_")
    outdir.mkdir(parents=True, exist_ok=True)
    args = [str(outdir), roles["target"], roles["anchor"], roles["keeper"], variant,
            str(spec["mode"]), str(spec["idx"]), flow, directive, str(congest),
            " ".join(CONGEST_SITES)]
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


def empty_route(value: str | None) -> bool:
    """True when Vivado's ROUTE is empty. It prints an empty route as `{}`."""
    return (value or "").strip().strip("{}").strip() == ""


def signature(kv: dict[str, str]) -> tuple:
    return tuple((name, kv.get(f"final.{name}.route"), kv.get(f"final.{name}.pips"))
                 for name in DEDICATED)


def verdict(out_root: Path, scope: dict) -> int:
    runs = {}
    for label, *_rest in MATRIX:
        path = out_root / label.replace("/", "_") / "probe_routes.tsv"
        if path.is_file():
            runs[label] = read_tsv(path)
    expected = {label for label, *_ in MATRIX}
    problems: list[str] = []
    if set(runs) != expected:
        missing = sorted(expected - set(runs))
        extra = sorted(set(runs) - expected)
        # A verdict over whatever happens to be on disk is how a run that lost a build
        # reports one route set and passes. The matrix is the unit, not the file listing.
        print(f"\nMATRIX INCOMPLETE: {len(runs)} of {len(expected)} runs present "
              f"(missing {missing}, extra {extra})")
        problems.append(f"matrix incomplete: {len(runs)}/{len(expected)} runs "
                        f"(missing {missing}, extra {extra})")
    current = {k: v for k, v in runs.items() if k.startswith("current")}
    pinned = {k: v for k, v in runs.items() if k.startswith("pinned")}

    # 1. is the freedom reproduced at all?
    moved_nets: set[str] = set()
    for variant in ("base", "ce_tied"):
        a = current.get(f"current/{variant}/Default/c0")
        b = current.get(f"current/{variant}/Default/c32")
        if a and b:
            moved_nets.update(name for name in DEDICATED
                              if a.get(f"final.{name}.route") != b.get(f"final.{name}.route")
                              or a.get(f"final.{name}.pips") != b.get(f"final.{name}.pips"))
    reproduced = bool(moved_nets)
    print(f"\n1. freedom reproduced under the current flow : {reproduced}"
          f"  nets={sorted(moved_nets) or 'none'}")
    if not reproduced:
        problems.append("the current flow did not disagree with itself: the congestion "
                        "did not reproduce the routing freedom, so nothing here shows "
                        "the pinned flow removing it")

    # 2. one route set under the pinned flow
    distinct = {signature(kv) for kv in pinned.values()}
    print(f"2. pinned flow route sets                    : {len(distinct)} "
          f"over {len(pinned)} runs")
    if len(distinct) != 1:
        problems.append(f"the pinned flow produced {len(distinct)} route sets")

    # 3. nothing moved after the freeze
    for label, kv in pinned.items():
        moved = [n for n in DEDICATED
                 if kv.get(f"first_pass.{n}.route") != kv.get(f"final.{n}.route")
                 or kv.get(f"first_pass.{n}.pips") != kv.get(f"final.{n}.pips")]
        if moved:
            problems.append(f"{label}: {len(moved)} net(s) moved after the freeze: {moved}")
    print(f"3. nets moving after the freeze               : "
          f"{sum(1 for p in problems if 'moved after the freeze' in p)} run(s)")

    # 4. endpoints identical everywhere
    endpoint_sets = {name: {(kv.get(f"final.{name}.driver"), kv.get(f"final.{name}.sinks"))
                            for kv in runs.values()} for name in DEDICATED}
    bad_endpoints = {n: s for n, s in endpoint_sets.items() if len(s) != 1}
    print(f"4. nets whose driver/sinks differ anywhere    : {len(bad_endpoints)}")
    if bad_endpoints:
        problems.append(f"driver/sinks differ for {sorted(bad_endpoints)}")

    # 5. the six routable nets are frozen — in the PINNED runs, which are the only ones
    #    that freeze anything. Asserting it of the current-flow runs would be asserting a
    #    property of the thing being compared against.
    fixed_problems = [f"{label}: {name} is not IS_ROUTE_FIXED"
                      for label, kv in pinned.items() for name in ROUTABLE
                      if kv.get(f"final.{name}.fixed") != "1"]
    # 6. the three pad nets have no route to pin — asserted over ALL runs, both flows,
    #    because that is a fact about the design, not about the flow.
    pad_problems = []
    for label, kv in runs.items():
        for name in INTRASITE:
            if kv.get(f"final.{name}.status") != "INTRASITE":
                pad_problems.append(f"{label}: {name} is "
                                    f"{kv.get(f'final.{name}.status')}, not INTRASITE")
            # Vivado renders an empty route as the empty Tcl list `{}`; a truthiness
            # test on that string calls an empty route a route.
            if not empty_route(kv.get(f"final.{name}.route")) \
                    or kv.get(f"final.{name}.pips", "").strip():
                pad_problems.append(
                    f"{label}: {name} is INTRASITE but carries "
                    f"route={kv.get(f'final.{name}.route')!r} "
                    f"pips={kv.get(f'final.{name}.pips')!r}")
    problems.extend(fixed_problems)
    problems.extend(pad_problems)
    print(f"5. six routable nets frozen in {len(pinned)} pinned runs   : "
          f"{'ok' if not fixed_problems else f'{len(fixed_problems)} PROBLEM(S)'}")
    print(f"6. three pad nets INTRASITE+empty in {len(runs)} runs  : "
          f"{'ok' if not pad_problems else f'{len(pad_problems)} PROBLEM(S)'}")

    print(f"\nproblems: {len(problems)}")
    for problem in problems:
        print(f"  {problem}")
    print("\nWording this may support, and no more: the routing freedom was reproduced "
          "and removed\non a NON-COMMITTED site of the same geometry. It is not evidence "
          "that the observed\nSLICE_X25Y25 failure is repaired — that site was not built.")
    (out_root / "verdict.json").write_text(json.dumps({
        "criteria": CRITERIA,
        "runs_required": len(expected),
        "runs_present": len(runs),
        "scope": scope,
        "freedom_reproduced": reproduced,
        "nets_that_moved_under_current_flow": sorted(moved_nets),
        "pinned_route_sets": len(distinct),
        "problems": problems,
        "runs": sorted(runs),
        "claim_limit": ("reproduced and removed on a non-committed site of the same "
                        "geometry; NOT a repair of the observed SLICE_X25Y25 failure"),
    }, indent=2) + "\n")
    return 1 if problems else 0


def collect_evidence(out_root: Path, evidence: Path, scope: dict) -> None:
    """Copy artifacts into versioned evidence and pin them. Extensions matter: a `.log`
    here would be swallowed by .gitignore and the README would cite nothing."""
    evidence.mkdir(parents=True, exist_ok=True)
    entries: dict[str, dict] = {}

    def pin(source: Path, name: str, role: str) -> None:
        target = evidence / name
        if source.resolve() != target.resolve():
            target.write_bytes(source.read_bytes())
        entries[name] = {"role": role,
                         "sha256": hashlib.sha256(target.read_bytes()).hexdigest()}

    required: list[tuple[Path, str, str]] = []
    for label, *_rest in MATRIX:
        stem = label.replace("/", "_")
        required.append((out_root / stem / "probe_routes.tsv",
                         f"{stem}.probe_routes.tsv", "route snapshot"))
        required.append((out_root / stem / "readback.tsv",
                         f"{stem}.readback.tsv", "structural readback"))
    required.append((out_root / "verdict.json", "verdict.json", "verdict"))
    required.append((out_root.parent / f"{out_root.name}.txt", "probe_run.txt",
                     "driver transcript"))
    # No `if source.is_file()`: skipping a missing artifact is how an incomplete run gets
    # a complete-looking manifest.
    absent = [str(source) for source, *_ in required if not source.is_file()]
    if absent:
        raise SystemExit("refusing to write evidence: these artifacts are missing, and "
                         "an evidence set is whole or it is not evidence:\n  "
                         + "\n  ".join(absent))
    for source, name, role in required:
        pin(source, name, role)

    tools = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
             for path in (Path(__file__).resolve(), PROBE_TCL)}
    inputs = {str(path.relative_to(REPO)): hashlib.sha256(path.read_bytes()).hexdigest()
              for path in (REPO / "vivado/specimen/specimen_ff_formal.v",
                           REPO / "vivado/specimen/ff_formal_readback.tcl",
                           builder.COMMITMENT, TILEGRID)}
    manifest = {
        "schema": "probe_evidence/1",
        "probe": "sacrificial_site_congestion",
        "note": ("Hashes are integrity anchors: they detect substitution of these files. "
                 "They do not prove Vivado produced these snapshots, and they are not a "
                 "target for any later run to reproduce."),
        "vivado_version": builder.vivado_version(),
        "part": builder.PART,
        "criteria": CRITERIA,
        "claim_limit": ("reproduced and removed on a non-committed site of the same "
                        "geometry; NOT a repair of the observed SLICE_X25Y25 failure"),
        "scope": scope,
        "matrix": [{"label": label, "variant": variant, "flow": flow,
                    "directive": directive, "congest": congest}
                   for label, variant, flow, directive, congest in MATRIX],
        "probe_tools": tools,
        "inputs_read": inputs,
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
    ap.add_argument("--out", type=Path, default=REPO / "build/probe_sacrificial")
    ap.add_argument("--evidence", type=Path, default=None,
                    help="copy artifacts here and write a manifest pinning them")
    ap.add_argument("--timeout", type=int, default=1800)
    ap.add_argument("--compare-only", action="store_true")
    ap.add_argument("--scope-only", action="store_true")
    args = ap.parse_args()

    roles = builder.sites_for(TARGET)
    scope = check_scope(roles, CONGEST_SITES)
    print("scope check passed — no committed site is touched")
    for role, info in scope["probe_roles"].items():
        print(f"  {role:8} {info['site']:14} {info['tile']:16} "
              f"{info['tile_type']:9} {info['site_type']}")
    if args.scope_only:
        return 0

    out_root = args.out.resolve()
    out_root.mkdir(parents=True, exist_ok=True)
    if args.evidence is not None:
        collect_evidence(out_root, args.evidence.resolve(), scope)
        return 0
    if not args.compare_only:
        for label, variant, flow, directive, congest in MATRIX:
            state, elapsed = run_one(out_root, label, variant, flow, directive, congest,
                                     roles, args.timeout)
            print(f"  {label:30} {state:8} {elapsed:6.1f}s", flush=True)
    return verdict(out_root, scope)


if __name__ == "__main__":
    raise SystemExit(main())
