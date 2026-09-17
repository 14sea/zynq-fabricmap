#!/usr/bin/env python3
"""B3 lifecycle 1, unit 1 — inventory of every B3 file at BASE and the dependency scan in both
directions (B3 -> B2/B1 imports; B2 -> B3 references), read-only. Writes inventory.json beside
this file. Host-only; no manifest, pin table, ruling or board action."""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "73b68d79fd43fc032c178da73dda2b2c95764db8"

B3_FILES = ["docs/b3_architecture.md", "host/b3_online.py", "host/b3_sim.py", "tests/test_b3_online.py",
            "schemas/specimen_ledger.schema.json",
            "evidence/b3/sim/sim_report.json", "evidence/b3/sim/raw_F1.json", "evidence/b3/sim/raw_F2.json",
            "evidence/b3/sim_v0.1.1/sim_report.json", "evidence/b3/sim_v0.1.1/raw_F1.json", "evidence/b3/sim_v0.1.1/raw_F2.json"]
# the B2 authority documents a B3 audit has to read (never edit)
B2_AUTHORITY = ["manifests/b2_manifest.json", "manifests/b2_instrument_pins.json", "manifests/b1_instrument_pins.json",
                "manifests/b1_manifest.json", "docs/b2_preregistration.md", "evidence/b2/plan.json", "evidence/b2/prediction.json"]
SCAN_DIRS = ["host", "tests", "scripts", "docs", "manifests", "schemas", "README.md", "evidence/b2/plan.json",
             "evidence/b2/review_2026_09_10"]
PATTERNS = {"host/b3_online.py": r"b3_online", "host/b3_sim.py": r"b3_sim", "tests/test_b3_online.py": r"test_b3_online",
            "docs/b3_architecture.md": r"b3_architecture", "schemas/specimen_ledger.schema.json": r"specimen_ledger",
            "evidence/b3/sim/sim_report.json": r"evidence/b3/sim/sim_report", "evidence/b3/sim/raw_F1.json": r"evidence/b3/sim/raw_",
            "evidence/b3/sim_v0.1.1/sim_report.json": r"sim_v0\.1\.1"}


def sh(cmd, check=True):
    return subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, check=check).stdout


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def imports_of(p: Path) -> list[str]:
    out = []
    for line in p.read_text().splitlines():
        m = re.match(r"\s*(?:import|from)\s+([A-Za-z_][\w.]*)", line)
        if m:
            out.append(m.group(1))
    return out


def references_to(pattern: str, exclude: set[str]) -> list[dict]:
    hits = []
    files = sh(["git", "ls-files"] + SCAN_DIRS).split("\n")
    for rel in files:
        if not rel or rel in exclude or rel.startswith("evidence/b3/") or rel.startswith("docs/b3_"):
            continue
        p = REPO / rel
        try:
            text = p.read_text(errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        for n, line in enumerate(text.splitlines(), 1):
            if re.search(pattern, line):
                hits.append({"file": rel, "line": n, "text": line.strip()[:160]})
    return hits


def main() -> int:
    assert sh(["git", "rev-parse", "HEAD"]).strip() == BASE, "not at BASE"
    tracked = set(sh(["git", "ls-files"]).split("\n"))
    b1 = json.loads((REPO / "manifests/b1_instrument_pins.json").read_text())
    b2 = json.loads((REPO / "manifests/b2_instrument_pins.json").read_text())
    globs = b2["globs"]
    inv = {"schema": "b3_lifecycle1_inventory", "schema_version": "1.0.0", "base": BASE,
           "generated_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "b2_pins_sha256": sha256(REPO / "manifests/b2_instrument_pins.json"),
           "b2_manifest_sha256": sha256(REPO / "manifests/b2_manifest.json"),
           "b2_globs": globs, "b2_globs_capturing_b3": [g for g in globs if "b3" in g],
           "b3_files": {}, "b2_to_b3_references": {}, "pinned_but_untracked": {}, "b2_authority_digests": {}}
    for rel in B3_FILES:
        p = REPO / rel
        matched = [g for g in globs if p.match(g) or Path(rel).match(g)]
        entry = {"exists": p.is_file(), "tracked": rel in tracked, "sha256": sha256(p) if p.is_file() else None,
                 "bytes": p.stat().st_size if p.is_file() else None,
                 "in_b2_pin_table": rel in b2["files"], "b2_pin_sha256": b2["files"].get(rel),
                 "matches_b2_globs": matched, "in_b1_pin_table": rel in b1["files"],
                 "git_history": [l for l in sh(["git", "log", "--format=%h %ad %s", "--date=short", "--", rel]).split("\n") if l][:6]}
        if rel.endswith(".py"):
            entry["imports"] = imports_of(p)
            entry["b1_b2_modules_imported"] = [i for i in entry["imports"] if re.match(r"b[12]_", i)]
            entry["reads_committed_state"] = [l.strip()[:140] for l in p.read_text().splitlines()
                                              if re.search(r"evidence/|schemas/|manifests/|SELF_MAP|load_self_map", l)]
        if rel.endswith("sim_report.json"):
            r = json.loads(p.read_text())
            entry["provenance"] = {k: r.get(k) for k in ("head_at_run", "worktree_dirty_at_start", "label", "carto_version", "generated_utc")}
            entry["seeds"] = r.get("seeds")
            entry["map"] = r.get("map")
        inv["b3_files"][rel] = entry
    for rel, pat in PATTERNS.items():
        inv["b2_to_b3_references"][rel] = references_to(pat, exclude=set(B3_FILES))
    for t in ("manifests/b1_instrument_pins.json", "manifests/b2_instrument_pins.json"):
        files = json.loads((REPO / t).read_text())["files"]
        un = sorted(f for f in files if f not in tracked)
        inv["pinned_but_untracked"][t] = {"pinned": len(files), "untracked": un,
                                          "gitignore_rule": {f: sh(["git", "check-ignore", "-v", f], check=False).strip() for f in un}}
    for rel in B2_AUTHORITY:
        inv["b2_authority_digests"][rel] = sha256(REPO / rel)
    m = json.loads((REPO / "manifests/b2_manifest.json").read_text())
    inv["b2_manifest_seed_exclusion_sources"] = m["seeds"]["excluded_frozen_sets"]
    inv["b2_image_binaries_not_tracked"] = {k: (REPO / k).is_file() and k not in tracked for k in
                                            (m["image"]["path"], json.loads((REPO / "manifests/b1_manifest.json").read_text())["image"]["path"])}
    (HERE / "inventory.json").write_text(json.dumps(inv, indent=1, sort_keys=True) + "\n")
    print(json.dumps({k: {"tracked": v["tracked"], "in_b2_table": v["in_b2_pin_table"], "globs": v["matches_b2_globs"]}
                      for k, v in inv["b3_files"].items()}, indent=1))
    print("b2->b3 reference counts:", {k: len(v) for k, v in inv["b2_to_b3_references"].items()})
    return 0


if __name__ == "__main__":
    sys.exit(main())
