#!/usr/bin/env python3
"""Offline review counterexamples for df28407; no production files are changed.

The adjudicator is a fixed test double because B2Q's real adjudicator does not exist.
It always returns the ORIGINAL evidence-derived rate and audit policy, including after
mutations. These probes test the lifecycle's contract, not a real B2Q qualification.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import shutil
import sys
import tempfile

R = Path("/home/test/zynq_fabricmap")
sys.path.insert(0, str(R / "host"))
import b2_manifest as bm
import b2_plan as bp


def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix="b2_review_v02_") as td:
        tmp = Path(td)
        image_evidence = tmp / "build.json"
        image_evidence.write_text(json.dumps({"image": {
            "path": "firmware/b2/bsp/out/b2_app.bin", "sha256": "ab" * 32,
            "elf_sha256": "cd" * 32, "bytes": 123456}}))
        frozen = bm.freeze(bm.init(image_evidence), bm.sha256_file(R / "docs/b2_preregistration.md"))
        frozen = json.loads(bm.render(frozen))  # the on-disk API, as in the lifecycle tests
        ev = tmp / "b2q"
        ev.mkdir()
        original_adjudication = {"outcome": "PASS", "session": "B2Q",
                                 "measured_rate_per_hour": 2500.0,
                                 "audit_policy": "all-self-reporting"}
        (ev / "manifest_at_run.json").write_text(bm.render(frozen))
        (ev / "run_log.json").write_text('{"session":"B2Q"}')
        (ev / "adjudication.json").write_text(json.dumps(original_adjudication))
        def adjudicate(ev, m_run):
            return copy.deepcopy(original_adjudication)
        qualified = bm.qualify(frozen, ev, readjudicate=adjudicate)

        def check(name, manifest, root=R):
            try:
                v = bm.verify(manifest, readjudicate=adjudicate, root=root)
                results[name] = {"accepted": True, "qualified": v["qualified"], "checks": v["checks"]}
            except bm.Refusal as exc:
                results[name] = {"accepted": False, "refusal": str(exc)}

        check("baseline_S2", qualified)
        changed = copy.deepcopy(qualified)
        changed["calibration"]["rate_per_hour"] = 100000.0
        changed["qualification"]["measured_rate_per_hour"] = 100000.0
        check("rate_changed_in_record_and_calibration_original_evidence_2500", changed)
        results["rate_changed_in_record_and_calibration_original_evidence_2500"]["claimed_rate"] = 100000.0
        changed = copy.deepcopy(qualified)
        changed["calibration"]["audit_policy"] = "sampled"
        changed["qualification"]["audit_policy"] = "sampled"
        check("audit_policy_changed_original_evidence_all_self_reporting", changed)
        changed = copy.deepcopy(qualified)
        changed["qualification"]["files"] = {}
        check("empty_evidence_file_table", changed)

        # Mirror live inputs, then mutate only the mirror. The initial mirror verifies.
        mirror = tmp / "tree"
        paths = list(qualified["pins"]) + [qualified["carrier_lineage"]["b1_manifest"]["path"],
                                          qualified["prereg"]["path"], qualified["map"]["path"]]
        for rel in paths:
            dest = mirror / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(R / rel, dest)
        check("baseline_mirrored_tree", qualified, mirror)
        for name, rel, remove in (
            ("missing_pinned_search_file", "host/b2_search.py", True),
            ("changed_prereg_file_only", qualified["prereg"]["path"], False),
            ("changed_map_file_only", qualified["map"]["path"], False),
            ("changed_lineage_manifest_file_only", qualified["carrier_lineage"]["b1_manifest"]["path"], False),
        ):
            p = mirror / rel
            original = p.read_bytes()
            if remove:
                p.unlink()
            else:
                p.write_bytes(original + b"\n ")
            check(name, qualified, mirror)
            p.write_bytes(original)

        plan_dir = tmp / "plan"
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(["--out", str(plan_dir), "--rate-per-hour", "2500"])
        original_plan = json.loads((plan_dir / "plan.json").read_text())
        def pin(name, path):
            try:
                check(name, bm.pin_plan(qualified, path, readjudicate=adjudicate))
            except bm.Refusal as exc:
                results[name] = {"accepted": False, "refusal": str(exc)}
        pin("baseline_S3", plan_dir / "plan.json")
        mutations = {
            "wrong_map": lambda p: p["map"].update(sha256="00" * 32),
            "wrong_engine": lambda p: p["engine"].update(mu=999),
            "wrong_audit_policy": lambda p: p.update(audit_policy="sampled"),
            "wrong_prediction_digest": lambda p: p.update(prediction_sha256="00" * 32),
        }
        for name, mutate in mutations.items():
            p = copy.deepcopy(original_plan)
            mutate(p)
            path = tmp / (name + ".json")
            path.write_text(json.dumps(p))
            pin("pin_plan_accepts_" + name, path)

        # S3 re-verification also omits checks that pin_plan itself makes.
        p = copy.deepcopy(original_plan)
        p["seed_derivation"]["master_seed"] = 42
        path = tmp / "changed_master_seed.json"
        path.write_text(json.dumps(p))
        planned = bm.pin_plan(qualified, plan_dir / "plan.json", readjudicate=adjudicate)
        planned["plan"].update(path=str(path), sha256=bm.sha256_file(path))
        check("S3_changed_master_seed_and_rehashed_plan", planned)

        split = bp.session_split(9, 600, 100)
        results["slow_positive_rate"] = {"rate_per_hour": 100, "status": split["status"], "detail": {k: v for k, v in split.items() if k != "note"}}
        for rate in (0, -1, float("inf"), float("nan")):
            try:
                split = bp.session_split(9, 600, rate)
                results["invalid_rate_" + str(rate)] = {"status": split["status"],
                    "expected_span_s": str(split["sessions"][0]["expected_span_s"])}
            except Exception as exc:
                results["invalid_rate_" + str(rate)] = {"exception": type(exc).__name__, "message": str(exc)}
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
