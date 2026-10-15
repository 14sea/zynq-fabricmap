#!/usr/bin/env python3
"""B3 lifecycle 1, unit 1 — throwaway-worktree probes of the B2 pinned surface.

Every probe checks out the B2 completion commit (BASE) into a fresh DETACHED worktree under a
scratch directory, restores the inputs the S3 verify needs that git does not carry (the two
image binaries and the gitignored files the B1 table pins), applies ONE mutation, runs the
production S3 verify exactly as README "Verify it yourself" does (plus the `b2_pins.py` CLI),
records the outcome, and removes the worktree. The main working tree is never written to,
except for this audit's own evidence directory; its tracked content is asserted clean before
and after, and HEAD is asserted to be BASE.

    probe_pinned_surface.py --scratch <dir> [--only name,name] [--keep]

Writes results.json and probe.log beside this file. Exit 0 iff every probe met its expectation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "73b68d79fd43fc032c178da73dda2b2c95764db8"
EXPECT_MANIFEST = "aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0"
EXPECT_PINS = "82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1"
IMAGE_DIRS = ("firmware/b1/bsp/out", "firmware/b2/bsp/out")     # gitignored build products the verify hashes
AUDIT_PATHS = ("docs/b3_lifecycle1_pinned_surface_audit_2026_09_17.md",
               "evidence/b3/lifecycle1_pinned_surface_audit_2026_09_17/")

VERIFY_SNIPPET = r'''
import sys, json, traceback
sys.path.insert(0, "host")
out = {}
try:
    import b2_manifest as bm, b2_runner as rn
    out["repo_root"] = str(bm.REPO_ROOT)
    m = json.loads(bm.MANIFEST.read_text())
    v = bm.verify(m, readjudicate=rn.readjudicator(m))
    out.update(outcome="verified", stage=v["stage"], qualified=v["qualified"], refusal=v["refusal"],
               manifest_sha256=v["manifest_sha256"], instrument_pins=v["checks"].get("instrument_pins"))
except Exception as exc:  # a named refusal AND an unhandled implementation exception both land here — the type tells them apart
    out.update(outcome="exception", exception_type=type(exc).__name__, exception_module=type(exc).__module__,
               exception_text=str(exc), traceback_tail=traceback.format_exc().splitlines()[-3:])
print(json.dumps(out))
'''


def sh(cmd, cwd=REPO, check=True, env=None) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=check, env=env)


def sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def tracked_clean_state() -> dict:
    """The main tree's state as this audit defines 'clean': HEAD == BASE, no tracked change staged or
    unstaged, and the only untracked paths are this audit's own. The raw porcelain is kept too."""
    head = sh(["git", "rev-parse", "HEAD"]).stdout.strip()
    porcelain = sh(["git", "status", "--porcelain"]).stdout
    tracked_dirty = sh(["git", "diff", "--quiet", "HEAD"], check=False).returncode != 0 \
        or sh(["git", "diff", "--cached", "--quiet"], check=False).returncode != 0
    foreign = [l for l in porcelain.splitlines()
               if not any(l[3:].startswith(a) for a in AUDIT_PATHS)]
    return {"head": head, "head_is_base": head == BASE, "tracked_dirty": tracked_dirty,
            "status_porcelain": porcelain, "untracked_or_changed_outside_audit": foreign,
            "clean_by_this_definition": head == BASE and not tracked_dirty and not foreign}


def untracked_pinned() -> list[str]:
    tracked = set(sh(["git", "ls-files"]).stdout.split("\n"))
    out = []
    for t in ("manifests/b1_instrument_pins.json", "manifests/b2_instrument_pins.json"):
        out += [f for f in json.loads((REPO / t).read_text())["files"] if f not in tracked]
    return sorted(set(out))


def restore_untracked_inputs(wt: Path, extra: list[str]) -> dict:
    """Copy from the main tree what a checkout of BASE lacks but the verify hashes. Recorded by digest."""
    copied = {}
    for d in IMAGE_DIRS:
        src, dst = REPO / d, wt / d
        if src.is_dir():
            shutil.copytree(src, dst, dirs_exist_ok=True)
            for f in sorted(dst.rglob("*")):
                if f.is_file():
                    copied[str(f.relative_to(wt))] = sha256(f)
    for rel in extra:
        src, dst = REPO / rel, wt / rel
        if src.is_file():
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
            copied[rel] = sha256(dst)
    return copied


# ---- the mutations: each returns a short description of what it did -------------------------------
def append_comment(rel):
    def f(wt: Path):
        p = wt / rel
        p.write_bytes(p.read_bytes() + b"\n# lifecycle-1 pinned-surface probe: one appended comment line\n")
        return f"appended one comment line to {rel}"
    return f


def delete(rel):
    def f(wt: Path):
        (wt / rel).unlink()
        return f"deleted {rel}"
    return f


def add_file(rel, body="# lifecycle-1 pinned-surface probe: a new file\n"):
    def f(wt: Path):
        p = wt / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
        return f"added {rel}"
    return f


def bump_sim_master_seed(wt: Path):
    p = wt / "evidence/b3/sim/sim_report.json"
    r = json.loads(p.read_text())
    r["seeds"]["master_seed"] += 1
    p.write_text(json.dumps(r, indent=1, sort_keys=True))
    return "evidence/b3/sim/sim_report.json: seeds.master_seed += 1 (the frozen seed-exclusion source b2_plan.FROZEN_SEED_SETS reads)"


def bump_sim_v011_master_seed(wt: Path):
    p = wt / "evidence/b3/sim_v0.1.1/sim_report.json"
    r = json.loads(p.read_text())
    r["seeds"]["master_seed"] += 1
    p.write_text(json.dumps(r, indent=1, sort_keys=True))
    return "evidence/b3/sim_v0.1.1/sim_report.json: seeds.master_seed += 1 (NOT a frozen seed-exclusion source)"


# expectation kinds:
#   ("verified", None)              -> S3 / True / None / EXPECT_MANIFEST (a negative control: the mutation is outside the surface)
#   ("refusal", "<substring>")      -> b2_manifest.Refusal whose text contains the substring (a NAMED refusal)
#   ("exception", "<TypeName>")     -> an unhandled implementation exception of that type (recorded as a finding, not a pass)
PROBES = [
    ("control_no_mutation", None, ("verified", None)),
    # the checkout ALONE, nothing restored, then with only the two image binaries restored: what a clone of
    # the commit can and cannot verify (finding P-F1). The verify checks the image before the pin tables.
    ("control_fresh_checkout_nothing_restored", None, ("refusal", "image: the image binary 'firmware/b2/bsp/out/b2_app.bin' is absent")),
    ("control_fresh_checkout_images_only_restored", None, ("refusal", "instrument pins: B1's instrument pin table: pinned files changed: vivado/carrier/generated/clockInfo.txt: missing; vivado/carrier/generated/vivado.jou: missing")),
    # --- the three files the B2 table pins by name: modify ---
    ("modify_host_b3_online", append_comment("host/b3_online.py"), ("refusal", "instrument pins: pinned files changed: host/b3_online.py: hash differs")),
    ("modify_host_b3_sim", append_comment("host/b3_sim.py"), ("refusal", "instrument pins: pinned files changed: host/b3_sim.py: hash differs")),
    ("modify_tests_test_b3_online", append_comment("tests/test_b3_online.py"), ("refusal", "instrument pins: pinned files changed: tests/test_b3_online.py: hash differs")),
    # --- delete ---
    ("delete_host_b3_online", delete("host/b3_online.py"), ("refusal", "instrument pins: pinned files changed: host/b3_online.py: missing")),
    ("delete_host_b3_sim", delete("host/b3_sim.py"), ("refusal", "instrument pins: pinned files changed: host/b3_sim.py: missing")),
    ("delete_tests_test_b3_online", delete("tests/test_b3_online.py"), ("refusal", "instrument pins: pinned files changed: tests/test_b3_online.py: missing")),
    # --- a NEW file each glob would capture ---
    ("add_host_b3_glob_match", add_file("host/b3_lifecycle1_probe.py"), ("refusal", "instrument pins: files matching the pinned globs are not in the table: ['host/b3_lifecycle1_probe.py']")),
    ("add_tests_test_b3_glob_match", add_file("tests/test_b3_lifecycle1_probe.py"), ("refusal", "instrument pins: files matching the pinned globs are not in the table: ['tests/test_b3_lifecycle1_probe.py']")),
    # --- B3 evidence the B2 S3 plan derives its seed exclusion from (not in the pin table; bound through the plan) ---
    ("modify_evidence_b3_sim_report_master_seed", bump_sim_master_seed, ("refusal", "evidence/b2/b2q_plan.json is not the canonical B2Q plan: ['seed_derivation.excluded_frozen_sets.evidence/b3/sim/sim_report.json.master_seed: 3829368064 != 3829368065'")),
    ("delete_evidence_b3_sim_report", delete("evidence/b3/sim/sim_report.json"), ("exception", "FileNotFoundError")),
    # --- negative controls: B3 material OUTSIDE the B2 surface must leave the verify at S3 / True / None ---
    ("neg_add_host_b3_subdir_module", add_file("host/b3/online.py"), ("verified", None)),
    ("neg_add_tests_b3_subdir_test", add_file("tests/b3/test_online.py"), ("verified", None)),
    ("neg_add_toplevel_b3_dir", add_file("b3/host/online.py"), ("verified", None)),
    ("neg_modify_docs_b3_architecture", append_comment("docs/b3_architecture.md"), ("verified", None)),
    ("neg_modify_schemas_specimen_ledger", append_comment("schemas/specimen_ledger.schema.json"), ("verified", None)),
    ("neg_modify_evidence_b3_sim_v011_report", bump_sim_v011_master_seed, ("verified", None)),
    ("neg_add_evidence_b3_new_dir", add_file("evidence/b3/lifecycle1_probe/x.json", "{}\n"), ("verified", None)),
]


def run_probe(name, mutate, expect, scratch: Path, extra_inputs: list[str], keep: bool, log) -> dict:
    wt = scratch / "wt" / name
    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], check=False)
        shutil.rmtree(wt, ignore_errors=True)
    t0 = time.time()
    env = dict(os.environ, GIT_LFS_SKIP_SMUDGE="1")      # LFS payloads stay pointers: the verify does not hash any
    sh(["git", "worktree", "add", "--detach", str(wt), BASE], env=env)
    mode = {"control_fresh_checkout_nothing_restored": "none", "control_fresh_checkout_images_only_restored": "images"}.get(name, "all")
    rec = {"name": name, "worktree": str(wt), "head": sh(["git", "rev-parse", "HEAD"], cwd=wt).stdout.strip(),
           "lfs_skip_smudge": True, "restore_mode": mode,
           "restored_untracked_inputs": {} if mode == "none" else restore_untracked_inputs(wt, [] if mode == "images" else extra_inputs)}
    rec["mutation"] = mutate(wt) if mutate else "none (control)"
    rec["worktree_status_porcelain"] = sh(["git", "status", "--porcelain", "--ignored=no"], cwd=wt).stdout
    p = subprocess.run([sys.executable, "-B", "-c", VERIFY_SNIPPET], cwd=wt, capture_output=True, text=True)
    try:
        rec["verify"] = json.loads(p.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        rec["verify"] = {"outcome": "no-json", "stdout_tail": p.stdout[-500:], "stderr_tail": p.stderr[-800:]}
    cli = subprocess.run([sys.executable, "-B", "host/b2_pins.py"], cwd=wt, capture_output=True, text=True)
    rec["pins_cli"] = {"returncode": cli.returncode, "stdout_tail": cli.stdout[-300:], "stderr_tail": cli.stderr[-400:]}
    kind, needle = expect
    v = rec["verify"]
    if kind == "verified":
        met = v.get("outcome") == "verified" and v.get("stage") == "S3" and v.get("qualified") is True \
            and v.get("refusal") is None and v.get("manifest_sha256") == EXPECT_MANIFEST \
            and (v.get("instrument_pins") or {}).get("pins_sha256") == EXPECT_PINS and cli.returncode == 0
    elif kind == "refusal":
        met = v.get("outcome") == "exception" and v.get("exception_type") == "Refusal" \
            and v.get("exception_module") == "b2_manifest" and needle in v.get("exception_text", "")
    else:
        met = v.get("outcome") == "exception" and v.get("exception_type") == needle
    rec["expected"] = {"kind": kind, "needle": needle}
    rec["expectation_met"] = bool(met)
    rec["seconds"] = round(time.time() - t0, 1)
    if not keep:
        sh(["git", "worktree", "remove", "--force", str(wt)])
        rec["worktree_removed"] = not wt.exists()
    line = f"[{'ok' if met else 'UNEXPECTED'}] {name}: {v.get('outcome')} " + \
           (f"{v.get('stage')}/{v.get('qualified')}/{v.get('refusal')}" if v.get("outcome") == "verified"
            else f"{v.get('exception_type')}: {str(v.get('exception_text'))[:160]}") + f"  ({rec['seconds']}s)"
    print(line, flush=True)
    log.write(line + "\n")
    return rec


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scratch", required=True, type=Path)
    ap.add_argument("--only", default="")
    ap.add_argument("--keep", action="store_true", help="leave the worktrees in place (for inspection)")
    a = ap.parse_args(argv)
    a.scratch.mkdir(parents=True, exist_ok=True)
    before = tracked_clean_state()
    if not before["clean_by_this_definition"]:
        print("REFUSED: the main tree is not at BASE and clean:", json.dumps(before, indent=1), file=sys.stderr)
        return 2
    extra = untracked_pinned()
    results = {"schema": "b3_lifecycle1_pinned_surface_probes", "schema_version": "1.0.0",
               "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "base": BASE,
               "expect_manifest_sha256": EXPECT_MANIFEST, "expect_pins_sha256": EXPECT_PINS,
               "python": sys.version.split()[0], "git": sh(["git", "--version"]).stdout.strip(),
               "main_tree_before": before,
               "pinned_but_untracked_files_restored_per_probe": extra,
               "image_dirs_restored_per_probe": list(IMAGE_DIRS), "probes": []}
    only = {s for s in a.only.split(",") if s}
    with (HERE / "probe.log").open("w") as log:
        for name, mutate, expect in PROBES:
            if only and name not in only:
                continue
            results["probes"].append(run_probe(name, mutate, expect, a.scratch, extra, a.keep, log))
    sh(["git", "worktree", "prune"])
    results["worktrees_after"] = sh(["git", "worktree", "list", "--porcelain"]).stdout
    results["main_tree_after"] = tracked_clean_state()
    results["finished_utc"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    results["all_expectations_met"] = all(p["expectation_met"] for p in results["probes"])
    results["main_tree_clean_before_and_after"] = before["clean_by_this_definition"] and results["main_tree_after"]["clean_by_this_definition"]
    (HERE / "results.json").write_text(json.dumps(results, indent=1, sort_keys=True) + "\n")
    print(f"{sum(p['expectation_met'] for p in results['probes'])}/{len(results['probes'])} expectations met; "
          f"main tree clean before/after: {results['main_tree_clean_before_and_after']}")
    return 0 if results["all_expectations_met"] and results["main_tree_clean_before_and_after"] else 1


if __name__ == "__main__":
    sys.exit(main())
