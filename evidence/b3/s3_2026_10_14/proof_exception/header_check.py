#!/usr/bin/env python3
"""The S3 node's supplementary verification for the SECOND defect named in
docs/b3_s2_proof_exception_2026_10_14.md (the owner's ruling of 2026-10-14): the pinned
b3/firmware/b3_seed_data.h carries the plan file's digest, which the S3 transition necessarily
changes, so the two byte-for-byte tests of test_b3_orch_twin cannot pass at S3.

This is evidence for one node, not an instrument: it lives in the node's evidence directory,
reads the tree, writes only where told, and mutates copies in a temporary directory only.

  render   : the production generator's complete fresh render, written to --out
  check    : ACCEPT only when (1) the committed header and the fresh render differ in exactly
             one line, (2) that line is `#define B3_SEED_PLAN_SHA256 "..."` in both,
             (3) the committed value equals the historical plan digest (the plan the header was
             rendered from, unchanged until S2), (4) the fresh value equals the manifest's plan pin,
             (5) the committed header's digest equals the pin table's and the build evidence's.
             Anything else is a named REFUSE.
  controls : the negative controls on temporary copies — a second changed line, a fresh digest that
             is not the pin, a committed digest that is not the historical plan — each must REFUSE.
"""
import argparse, difflib, hashlib, json, os, re, shutil, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
LINE = re.compile(r'^#define B3_SEED_PLAN_SHA256 "([0-9a-f]{64})"$')
HEADER_REL = "b3/firmware/b3_seed_data.h"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def render(out: Path) -> dict:
    sys.path.insert(0, str(ROOT / "b3/host"))
    import gen_b3_seed_data as gen  # the production generator, its inputs() validating the plan against the gate
    text = gen.render(gen.inputs())
    out.write_text(text)
    return {"fresh_header": str(out), "sha256": sha(out), "generator": gen.GENERATOR, "plan_read": str(gen.PLAN)}


def check(committed: Path, fresh: Path, historical_plan_sha: str, manifest: Path, pins: Path, build_evidence: Path) -> dict:
    f = []
    c_lines, f_lines = committed.read_text().splitlines(), fresh.read_text().splitlines()
    diff = list(difflib.unified_diff(c_lines, f_lines, "committed " + HEADER_REL, "fresh render", lineterm="", n=0))
    changed = [(i, a, b) for i, (a, b) in enumerate(zip(c_lines, f_lines), 1) if a != b]
    if len(c_lines) != len(f_lines):
        f.append(f"line count differs: committed {len(c_lines)}, fresh {len(f_lines)}")
    if len(changed) != 1:
        f.append(f"{len(changed)} lines differ, not exactly one: {[i for i, _, _ in changed]}")
    old = new = None
    if len(changed) == 1 and len(c_lines) == len(f_lines):
        i, a, b = changed[0]
        ma, mb = LINE.match(a), LINE.match(b)
        if not (ma and mb):
            f.append(f"the differing line {i} is not the B3_SEED_PLAN_SHA256 define in both: {a!r} / {b!r}")
        else:
            old, new = ma.group(1), mb.group(1)
            if old != historical_plan_sha:
                f.append(f"the committed digest {old[:16]}… is not the historical plan's {historical_plan_sha[:16]}…")
            m = json.loads(manifest.read_text())
            pin = (m.get("plan") or {}).get("sha256")
            if new != pin:
                f.append(f"the fresh digest {new[:16]}… is not the manifest's plan pin {str(pin)[:16]}…")
    h = sha(committed)
    p = json.loads(pins.read_text())
    table = p.get("files", p)
    if table.get(HEADER_REL) != h:
        f.append(f"the committed header {h[:16]}… is not the pin table's {str(table.get(HEADER_REL))[:16]}…")
    b = json.loads(build_evidence.read_text())
    if b.get("sources", {}).get("b3_seed_data.h") != h:
        f.append(f"the committed header {h[:16]}… is not the build evidence's source {str(b.get('sources', {}).get('b3_seed_data.h'))[:16]}…")
    return {"verdict": "REFUSE" if f else "ACCEPT", "findings": f, "diff": diff, "changed_lines": [i for i, _, _ in changed],
            "committed_sha256": h, "fresh_sha256": sha(fresh), "committed_plan_digest": old, "fresh_plan_digest": new,
            "historical_plan_sha256": historical_plan_sha}


def controls(committed: Path, fresh: Path, historical: str, manifest: Path, pins: Path, build_evidence: Path) -> dict:
    tmp = Path(tempfile.mkdtemp(prefix="b3_header_controls_"))
    out = {"temp_dir": str(tmp), "controls": [], "all_refused_as_expected": True}
    try:
        def mutant(name, src, edit):
            p = tmp / f"{name}.h"
            lines = src.read_text().splitlines()
            edit(lines)
            p.write_text("\n".join(lines) + "\n")
            return p
        def set_digest(lines, value):
            for i, l in enumerate(lines):
                if LINE.match(l):
                    lines[i] = f'#define B3_SEED_PLAN_SHA256 "{value}"'
                    return
            raise AssertionError("no digest line")
        def bump_budget(lines):
            for i, l in enumerate(lines):
                m = re.match(r"^(#define B3_PROFILE_B3_BUDGET )(\d+)(u)$", l)
                if m:
                    lines[i] = f"{m.group(1)}{int(m.group(2)) + 1}{m.group(3)}"
                    return
            raise AssertionError("no budget line")
        bad = "0" * 64
        cases = [
            ("N1_fresh_with_a_second_changed_line", committed, mutant("N1", fresh, bump_budget), historical, "2 lines differ"),
            ("N2_fresh_digest_not_the_manifest_pin", committed, mutant("N2", fresh, lambda L: set_digest(L, bad)), historical, "not the manifest's plan pin"),
            ("N3_committed_digest_not_the_historical_plan", mutant("N3", committed, lambda L: set_digest(L, bad)), fresh, historical, "not the historical plan's"),
            ("N4_historical_digest_wrong", committed, fresh, bad, "not the historical plan's"),
        ]
        for name, c, fr, hist, expect in cases:
            r = check(c, fr, hist, manifest, pins, build_evidence)
            ok = r["verdict"] == "REFUSE" and any(expect in x for x in r["findings"])
            out["controls"].append({"name": name, "verdict": r["verdict"], "findings": r["findings"], "expected_finding_substring": expect, "refused_as_expected": ok})
            out["all_refused_as_expected"] &= ok
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
        out["temp_dir_removed"] = not tmp.exists()
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render"); r.add_argument("--out", required=True, type=Path); r.add_argument("--record", required=True, type=Path)
    for name in ("check", "controls"):
        s = sub.add_parser(name)
        s.add_argument("--committed", type=Path, default=ROOT / HEADER_REL)
        s.add_argument("--fresh", type=Path, required=True)
        s.add_argument("--historical-plan-sha", required=True)
        s.add_argument("--manifest", type=Path, default=ROOT / "manifests/b3_manifest.json")
        s.add_argument("--pins", type=Path, default=ROOT / "manifests/b3_instrument_pins.json")
        s.add_argument("--build-evidence", type=Path, default=ROOT / "evidence/b3/build_evidence.json")
        s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(argv)
    if a.cmd == "render":
        res = render(a.out)
        a.record.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
        print(json.dumps(res))
        return 0
    elif a.cmd == "check":
        res = check(a.committed, a.fresh, a.historical_plan_sha, a.manifest, a.pins, a.build_evidence)
    else:
        res = controls(a.committed, a.fresh, a.historical_plan_sha, a.manifest, a.pins, a.build_evidence)
    a.out.write_text(json.dumps(res, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: v for k, v in res.items() if k in ("verdict", "findings", "all_refused_as_expected", "sha256", "changed_lines")}))
    if a.cmd == "check":
        return 0 if res["verdict"] == "ACCEPT" else 2
    if a.cmd == "controls":
        return 0 if res["all_refused_as_expected"] else 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
