#!/usr/bin/env python3
"""Offline lifecycle review of 151124f; only temporary fixtures are mutated.

The fixture image is arbitrary data, not a firmware build. The fixed adjudicator double
returns the original evidence's rate and policy. Every plan mutation has a complete,
otherwise correct sidecar prediction, so missing files cannot mask validation gaps.
"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host"))
import b2_manifest as bm
import b2_plan as bp


def main():
    results = {}
    with tempfile.TemporaryDirectory(prefix="b2_review_151124f_") as td:
        tmp = Path(td)
        binary = tmp / "fixture.bin"
        original_binary = b"B2 review fixture only; not executable firmware.\n"
        binary.write_bytes(original_binary)
        be = tmp / "build.json"
        be.write_text(json.dumps({"image": {"path": str(binary),
            "sha256": bm.sha256_file(binary), "bytes": binary.stat().st_size,
            "elf_sha256": "cd" * 32}}))
        frozen = bm.freeze(bm.init(be), bm.sha256_file(R / "docs/b2_preregistration.md"))
        frozen = json.loads(bm.render(frozen))
        ev = tmp / "b2q"
        ev.mkdir()
        adj = {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2500.0,
               "audit_policy": "all-self-reporting"}
        (ev / "manifest_at_run.json").write_text(bm.render(frozen))
        (ev / "run_log.json").write_text('{"session":"B2Q"}')
        (ev / "adjudication.json").write_text(json.dumps(adj))
        def adjudicate(ev, m_run):
            return copy.deepcopy(adj)
        qualified = bm.qualify(frozen, ev, readjudicate=adjudicate)

        def check(name, candidate):
            try:
                v = bm.verify(candidate, readjudicate=adjudicate)
                results[name] = {"accepted": True, "qualified": v["qualified"], "checks": v["checks"]}
            except bm.Refusal as exc:
                results[name] = {"accepted": False, "refusal": str(exc)}
        check("baseline_S2_real_fixture_bytes", qualified)
        binary.write_bytes(b"Z" * len(original_binary))
        assert bm.sha256_file(binary) != qualified["image"]["sha256"]
        check("image_bytes_changed_same_size", qualified)
        binary.unlink()
        check("image_file_deleted", qualified)
        binary.write_bytes(original_binary)
        original_be = be.read_bytes()
        be.write_bytes(original_be + b" ")
        check("negative_control_build_evidence_changed", qualified)
        be.write_bytes(original_be)

        generated = tmp / "generated"
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(["--out", str(generated), "--rate-per-hour", "2500"])
        plan = json.loads((generated / "plan.json").read_text())
        prediction = json.loads((generated / "prediction.json").read_text())
        planned = bm.pin_plan(qualified, generated / "plan.json", readjudicate=adjudicate)
        check("baseline_S3", planned)

        def probe(name, change_plan=None, change_prediction=None):
            folder = tmp / name
            folder.mkdir()
            p, pr = copy.deepcopy(plan), copy.deepcopy(prediction)
            if change_plan:
                change_plan(p)
            if change_prediction:
                change_prediction(pr)
            pp = folder / "plan.json"
            predp = folder / "prediction.json"
            predp.write_text(json.dumps(pr))
            p["prediction_sha256"] = bm.sha256_file(predp)
            pp.write_text(json.dumps(p))
            item = {}
            try:
                pinned = bm.pin_plan(qualified, pp, readjudicate=adjudicate)
                item["pin_accepted"] = pinned["qualified"]
            except bm.Refusal as exc:
                item.update(pin_accepted=False, pin_refusal=str(exc))
            # Exercise verification independently, even if pinning refused the input.
            candidate = copy.deepcopy(planned)
            candidate["plan"].update(path=str(pp), sha256=bm.sha256_file(pp),
                prediction_path=str(predp), prediction_sha256=bm.sha256_file(predp))
            try:
                v = bm.verify(candidate, readjudicate=adjudicate)
                item["reverify_qualified"] = v["qualified"]
            except bm.Refusal as exc:
                item.update(reverify_qualified=False, verify_refusal=str(exc))
            results[name] = item

        probe("baseline_copied_plan_and_prediction")
        probe("plan_wrong_session", change_plan=lambda p: p.update(session="B1"))
        probe("plan_wrong_schema_version", change_plan=lambda p: p.update(schema_version="99.0.0"))
        probe("plan_wrong_primary_alpha", change_plan=lambda p: p["primary"].update(alpha=1.0))
        probe("plan_wrong_ties_policy", change_plan=lambda p: p["primary"].update(ties="count as positive"))
        probe("plan_wrong_record_counts", change_plan=lambda p: p["records"].update(per_pair=1, single_session_total=1))
        probe("plan_primary_missing", change_plan=lambda p: p.pop("primary"))
        probe("prediction_wrong_primary", change_prediction=lambda p: p["predicted_primary"].update(
            sign_test_p=1.0, verdict="NOT SUPPORTED"))
        probe("prediction_wrong_sequence_length", change_prediction=lambda p: p.update(fitness_sequence_length=1))
        probe("prediction_wrong_pair_id", change_prediction=lambda p: p["pairs"][0].update(pair=99))
        probe("prediction_wrong_pair_delta", change_prediction=lambda p: p["pairs"][0].update(delta_B_minus_A=-999))
        probe("prediction_wrong_base_fitness", change_prediction=lambda p: p["pairs"][0].update(base_train_fitness=-999))
        probe("negative_control_plan_wrong_map", change_plan=lambda p: p["map"].update(sha256="00" * 32))
        probe("negative_control_prediction_changed_runs", change_prediction=lambda p: p["pairs"][0]["runs"]["A"].update(best_train=-999))

        # The manifest can name a different prediction than the plan's checked sidecar.
        other = tmp / "unrelated_prediction.json"
        other.write_text('{}')
        candidate = copy.deepcopy(planned)
        candidate["plan"].update(prediction_path=str(other), prediction_sha256=bm.sha256_file(other))
        check("manifest_prediction_points_to_unrelated_bytes", candidate)
        results["manifest_prediction_points_to_unrelated_bytes"]["same_digest_as_plan_sidecar"] = (
            candidate["plan"]["prediction_sha256"] == plan["prediction_sha256"])
    print(json.dumps(results, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
