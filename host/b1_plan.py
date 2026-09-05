#!/usr/bin/env python3
"""B1 — the session plan and the preregistered prediction (host-only; pure arithmetic over
pinned artifacts; nothing here touches a board).

    b1_plan.py [--write-manifest]   → evidence/b1/plan.json, evidence/b1/prediction.json

The plan derives, before any session:
  * the master seed by the manifest's rule (sha256 of a public label and the instrument's
    archive commit, advanced past every excluded seed — the L5/L6/round-1′ seeds);
  * the budget: the cartographer's own bound, 9 code + 292 confirm + 32 pair probes = 333
    (`b1_carto` constants), so N = 333 candidates + 2 baselines = 335 records;
  * the audit policy: ALL-SELF-REPORTING (every record's readout served and host-verified —
    in B1 every readout IS the data, so the sampled policy of the soak does not apply);
  * the expected frame count and the CRC / bad-frame budget (the instrument's D-s4
    formula over rel-v4 with every seq audited);
  * the runner's deadline from the pinned C1/C2 planning rates (all-self-reporting policy)
    through the instrument's own timeout formula;
  * the flags word (watchdog ON, both seq-1 controls, schedule-mode bits zero);
  * the prediction: the reference cartographer over the truth fabric with this seed and
    budget — the exact probe sequence, every record's `carto` block, the final map and its
    sha256. On a correct instrument the board must reproduce these bytes; a difference is
    a finding, never a silent adjustment.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b1_verify as bv  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "b1_plan.py/0.1.0"
MANIFEST = REPO_ROOT / "manifests/b1_manifest.json"
SEED_LABEL = b"b1-cartography|"
BUDGET = bc.CODE_BITS + bc.N + bc.PAIRS_MAX        # 333
SESSION = "B1"


class PlanError(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excluded_seeds(manifest: dict) -> set[int]:
    return {int(s) for k, v in manifest["seeds"]["excluded"].items() if k != "rule" for s in v}


def master_seed_by_rule(manifest: dict) -> dict:
    commit = manifest["instrument"]["psoracle_commit"].encode()
    digest = hashlib.sha256(SEED_LABEL + commit).digest()
    ex = excluded_seeds(manifest)
    trace = []
    for off in range(0, 32, 4):
        v = int.from_bytes(digest[off:off + 4], "big")
        trace.append({"offset": off, "value": v, "excluded": v in ex})
        if v not in ex:
            return {"master_seed": v, "digest": digest.hex(), "label": SEED_LABEL.decode(), "commit": commit.decode(),
                    "offset": off, "trace": trace}
    raise PlanError("every 4-byte window of the digest is an excluded seed")


def check_pins(manifest: dict, root: Path) -> dict:
    """Falsifier 3: this repository's authority files and the instrument's imported copies
    hash to the pins; the image evidence hashes to the manifest's pin."""
    fa = manifest["universe"]
    out = {}
    for k, rel in (("local_map_sha256", "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/local_map.json"),
                   ("phenotype_manifest_sha256", "gate_runs/claimb_round1_carrier_2026_08_13_erratum006/phenotype_manifest.json"),
                   ("carrier_constants_sha256", "vivado/carrier/generated/carrier_constants.json")):
        here, theirs = REPO_ROOT / rel, root / "imported/fabricmap" / rel
        if sha256_of(here) != fa[k]:
            raise PlanError(f"{rel} here does not hash to the manifest pin")
        if not theirs.is_file() or sha256_of(theirs) != fa[k]:
            raise PlanError(f"the instrument's imported {rel} does not hash to the manifest pin")
        out[k] = fa[k]
    return out


def deadline(manifest: dict, root: Path, n: int) -> dict:
    """The instrument's timeout formula over the pinned calibrations' PLANNING rates (the
    all-self-reporting policy is the calibrations' own): 1.25 × (N+2) × 3600/min(rate) + 600."""
    import l6_schedule as ls  # noqa: E402
    rates = {}
    for k in ("C1", "C2"):
        pin = manifest["instrument"]["calibration"][k]
        rp = root / pin["evidence"]
        if sha256_of(rp) != pin["rate_report_sha256"]:
            raise PlanError(f"{k}: the calibration report does not hash to the pin")
        rep = json.loads(rp.read_text())
        rates[k] = float(rep["planning"]["evals_per_hour"])
    t = ls.session_timeout_s(n, rates["C1"], rates["C2"])
    return {"rate_C1_planning": rates["C1"], "rate_C2_planning": rates["C2"], "session_timeout_s": t,
            "formula": "1.25 × (N+2) × 3600/min(planning rate) + 600 (l6_schedule.session_timeout_s)",
            "expected_span_s": (n + 2) * 3600.0 / min(rates.values())}


def build_plan(manifest: dict, root: Path | None = None, require_git: bool = True) -> tuple[dict, dict]:
    root = root or inst.DEFAULT_ROOT
    verified = inst.bind(root, manifest=manifest, require_git=require_git)
    import l6_schedule as ls  # noqa: E402
    pins = check_pins(manifest, root)
    seed = master_seed_by_rule(manifest)
    ms = seed["master_seed"]
    n = BUDGET
    audit_seqs = ls.all_seqs(n)
    expected = ls.expected_frames(n, audit_seqs, manifest["protocol"]["wire"])
    budget = ls.crc_budget(expected["total"])
    dl = deadline(manifest, root, n)
    flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)   # mode bits 0 = ignored by B1
    # the prediction: the reference SESSION over the truth fabric. The binding (token, image)
    # is per session, so the prediction pins the CONTENT: the probe sequence, every record's
    # content-level block and the content hash; the map hash is checked per session.
    truth = bm.truth_mapping()
    fab = bm.fixture("truth", truth=truth)
    image_lo32 = int(manifest["image"]["sha256"][-8:], 16)
    sim = bm.simulate(ms, n, fab, token=bm.DEFAULT_TOKEN, universe=manifest["universe"]["sha256"], image_lo32=image_lo32)
    whole = json.loads(sim["map"])
    score = bv.score(whole["content"], truth)
    snaps = bv.snapshots(sim["records"], truth)
    def content_block(c: str) -> dict:
        d = json.loads(c)
        return {k: d[k] for k in ("anomalies", "changed", "content_sha256", "phase", "probes_issued", "version")}
    prediction = {"schema": "b1_prediction", "schema_version": "2.0.0", "tool": TOOL_VERSION,
                  "master_seed": ms, "budget": n, "cartographer": bc.VERSION, "universe_sha256": manifest["universe"]["sha256"],
                  "probes": [{"seq": p["seq"], "kind": p["kind"], "genome": p["genome"]} for p in sim["probes"]],
                  "probe_sequence_sha256": hashlib.sha256("\n".join(p["genome"] for p in sim["probes"]).encode()).hexdigest(),
                  "record_content": [{"seq": r["seq"], "content": content_block(r["carto"])} for r in sim["records"]],
                  "content": whole["content"], "content_sha256": sim["content_sha256"],
                  "expected_score": {**{k: score[k] for k in ("precision", "recall", "claimed", "correct", "unobserved_claims", "states",
                                                             "anomalies", "calibration", "stratum_A", "stratum_B", "interaction")},
                                     "snapshots": snaps},
                  "note": "the truth fabric is the certificate's mapping; on a correct instrument the board's records "
                          "reproduce these probes and content-level blocks exactly and the map's content hashes to "
                          "content_sha256 (the map hash also covers the session's token and image, checked per session). "
                          "This is a prediction the run is compared against, never an input to the board."}
    ptext = json.dumps(prediction, indent=1, sort_keys=True) + "\n"
    plan = {"schema": "b1_plan", "schema_version": "1.0.0", "tool": TOOL_VERSION, "instrument": verified, "pins": pins,
            "session": SESSION, "master_seed": ms, "seed_derivation": seed,
            "seed_exclusion": {"excluded_master_seeds": sorted(excluded_seeds(manifest))},
            "budget": n, "records": n + 2, "phases": {"code": bc.CODE_BITS, "confirm": bc.N, "pair": bc.PAIRS_MAX},
            "audit_policy": "all-self-reporting", "audit_seqs": sorted(audit_seqs), "audited_records": len(audit_seqs),
            "expected_frames": expected, "crc_budget": budget, "bad_frame_budget": budget,
            "crc_formula": "ceil(4 × expected_total / 1000) (D-s4)",
            "deadline": dl, "session_timeout_s": dl["session_timeout_s"],
            "flags": flags, "flags_hex": f"{flags:#x}", "protocol": manifest["protocol"]["wire"],
            "watchdog": True, "rec_retry_control": True, "sign_retry_control": True,
            "holdout_luts": list(bm.HOLDOUT_LUTS),
            "prediction_sha256": hashlib.sha256(ptext.encode()).hexdigest(),
            "predicted_content_sha256": sim["content_sha256"], "predicted_probe_sequence_sha256": prediction["probe_sequence_sha256"]}
    return plan, prediction


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--out-dir", type=Path, default=REPO_ROOT / "evidence/b1")
    ap.add_argument("--write-manifest", action="store_true", help="pin the plan/prediction hashes and the seed into the manifest")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    try:
        plan, prediction = build_plan(manifest, require_git=not a.no_git)
    except (PlanError, inst.InstrumentRefusal) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    a.out_dir.mkdir(parents=True, exist_ok=True)
    ptext = json.dumps(prediction, indent=1, sort_keys=True) + "\n"
    (a.out_dir / "prediction.json").write_text(ptext)
    text = json.dumps(plan, indent=1, sort_keys=True) + "\n"
    (a.out_dir / "plan.json").write_text(text)
    psha, tsha = hashlib.sha256(ptext.encode()).hexdigest(), hashlib.sha256(text.encode()).hexdigest()
    if a.write_manifest:
        manifest["seeds"]["master_seed"] = plan["master_seed"]
        manifest["plan"] = {"path": "evidence/b1/plan.json", "sha256": tsha, "budget": plan["budget"], "records": plan["records"],
                            "audited_records": plan["audited_records"], "crc_budget": plan["crc_budget"],
                            "session_timeout_s": plan["session_timeout_s"]}
        manifest["prediction"] = {"path": "evidence/b1/prediction.json", "sha256": psha, "content_sha256": plan["predicted_content_sha256"],
                                  "probe_sequence_sha256": plan["predicted_probe_sequence_sha256"]}
        a.manifest.write_text(json.dumps(manifest, indent=1, ensure_ascii=False) + "\n")
    es = prediction["expected_score"]
    print(f"plan sha256 {tsha}; prediction sha256 {psha}\n  seed {plan['master_seed']} budget {plan['budget']} records {plan['records']} "
          f"audits {plan['audited_records']} frames {plan['expected_frames']['total']} budget {plan['crc_budget']} timeout {plan['session_timeout_s']} s "
          f"(expected span {plan['deadline']['expected_span_s']:.0f} s)\n  predicted content {plan['predicted_content_sha256'][:16]} precision {es['precision']} "
          f"recall {es['recall']} probes_to_full_recall {es['snapshots']['probes_to_full_recall_conf1']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
