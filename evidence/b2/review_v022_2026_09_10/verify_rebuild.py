#!/usr/bin/env python3
"""Offline fourth-review checks. Generates only temporary JSON and arbitrary fixture bytes."""
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
    out = {}
    original = json.loads((R / "evidence/b2/plan.json").read_text())
    canonical = bp.build_plan(None)
    assert canonical == {k: v for k, v in original.items() if k not in ("generated_utc", "prediction_sha256")}
    out["canonical_plan_matches_committed_operational_fields"] = True
    seeds = bp.session_seeds(canonical["pairs"])[1]
    expected = json.loads((R / "evidence/b2/prediction.json").read_text())
    bp._PREDICT_CACHE.clear()
    predicted = bp.build_prediction(canonical["fitness"], canonical["budget_per_arm"], seeds, canonical["map"]["sha256"])
    assert predicted == expected
    predicted["deltas"][0] = -999
    predicted["pairs"][0]["runs"]["A"]["best_train"] = -999
    assert bp.build_prediction(canonical["fitness"], canonical["budget_per_arm"], seeds, canonical["map"]["sha256"]) == expected
    out["cold_prediction_matches_and_cache_copies_are_isolated"] = True
    with tempfile.TemporaryDirectory(prefix="b2_fourth_review_") as td:
        tmp = Path(td)
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(["--out", str(tmp / "draft")])
        assert (tmp / "draft/prediction.json").read_bytes() == (R / "evidence/b2/prediction.json").read_bytes()
        out["prediction_bytes_reproduced"] = True
        binary = tmp / "fixture.bin"
        binary.write_bytes(b"Offline review fixture; not executable firmware.\n")
        be = tmp / "build.json"
        be.write_text(json.dumps({"image": {"path": str(binary), "sha256": bm.sha256_file(binary),
                                            "bytes": binary.stat().st_size}}))
        frozen = json.loads(bm.render(bm.freeze(bm.init(be), bm.sha256_file(R / "docs/b2_preregistration.md"))))
        ev = tmp / "b2q"
        ev.mkdir()
        adj = {"outcome": "PASS", "session": "B2Q", "measured_rate_per_hour": 2500.0,
               "audit_policy": "all-self-reporting"}
        (ev / "manifest_at_run.json").write_text(bm.render(frozen))
        (ev / "run_log.json").write_text('{"session":"B2Q"}')
        (ev / "adjudication.json").write_text(json.dumps(adj))
        def adjudicate(ev, mrun):
            return copy.deepcopy(adj)
        qualified = bm.qualify(frozen, ev, readjudicate=adjudicate)
        with contextlib.redirect_stdout(io.StringIO()):
            bp.main(["--out", str(tmp / "planned"), "--rate-per-hour", "2500"])
        pp = tmp / "planned/plan.json"
        planned = bm.pin_plan(qualified, pp, readjudicate=adjudicate)
        assert bm.verify(planned, readjudicate=adjudicate)["qualified"]
        doc = json.loads(pp.read_text())
        doc["generated_utc"] = "2026-09-10T00:00:00Z"
        pp.write_text(json.dumps(doc))
        planned["plan"]["sha256"] = bm.sha256_file(pp)
        assert bm.verify(planned, readjudicate=adjudicate)["qualified"]
        out["generation_time_change_with_rehash_accepted"] = True
        moved = tmp / "relocated_prediction.json"
        moved.write_bytes((tmp / "planned/prediction.json").read_bytes())
        planned["plan"]["prediction_path"] = str(moved)
        assert bm.verify(planned, readjudicate=adjudicate)["qualified"]
        out["identical_prediction_relocation_accepted"] = True
    print(json.dumps(out, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
