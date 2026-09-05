#!/usr/bin/env python3
"""Claim B round 1′ — the session plan: seed, budget, schedule, budgets, blocks (host-only,
pure arithmetic over pinned artifacts; nothing here touches a board).

Everything the preregistration says must be derived BEFORE the session rather than typed:

  * the master seed, from the rule the manifest states (a hash of a public string and the
    instrument's archive commit), advanced past every excluded seed; and the check that no
    pair seed of the Claim B schedule equals any pair seed of any L6 session (the owner's
    "every L6 seed excluded");
  * N, from the two PINNED calibration records through the instrument's own policy-matched
    rule (`zynq-psoracle/host/l6_soak_plan.py`, D-n1) with the window as T and the SLOWER
    arm sizing N — the window is a ceiling: N = ⌊0.9 × min(rate_A, rate_B) × W / 3600⌋ with
    the audit fraction solved by fixed point — and the runner's deadline = W after `go`;
  * the sampled audit schedule, the expected frame count, the CRC and bad-frame budgets
    (D-s4's closed formula over rel-v4's brackets), exactly as S #3 was soaked;
  * the post-hoc validation of N against S #3's recorded pace — validation ONLY, never an
    input (D-n1's discipline): predicted wall = N × the normalised interval must be ≤
    WALL_MARGIN × W;
  * the block structure of the primary metric (16 blocks × 367 pairs).

The plan is written to `evidence/claimb_round1prime/plan.json`; its sha256 is pinned in the
manifest and the runner refuses a plan that does not hash to the pin.
"""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

TOOL_VERSION = "claimb_r1p_plan.py/0.1.0"
SEED_LABEL = b"claimb-round1prime|"
WINDOW_FRACTION = 0.9        # N = floor(0.9 × min(rate) × W)
WALL_MARGIN = 0.95           # predicted wall at S #3's pace must be ≤ 0.95 × W
FIXED_POINT_ROUNDS = 8
L6_SESSION_N = {"C1": 64, "C2": 64, "S": 12568}      # the L6 sessions' N, for the pair-seed exclusion


class PlanError(Exception):
    pass


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def excluded_seeds(manifest: dict) -> set[int]:
    ex = manifest["seeds"]["excluded"]
    return {int(s) for k, v in ex.items() if k != "rule" for s in v}


def master_seed_by_rule(manifest: dict) -> dict:
    """The first 4 bytes (big-endian) of sha256(label ‖ archive commit), advanced by 4 bytes
    while the value is excluded; the derivation is recorded whole."""
    commit = manifest["instrument"]["psoracle_commit"].encode()
    digest = hashlib.sha256(SEED_LABEL + commit).digest()
    ex = excluded_seeds(manifest)
    trace = []
    for off in range(0, 32, 4):
        v = int.from_bytes(digest[off:off + 4], "big")
        trace.append({"offset": off, "value": v, "excluded": v in ex})
        if v not in ex:
            return {"master_seed": v, "digest": digest.hex(), "label": SEED_LABEL.decode(),
                    "commit": commit.decode(), "offset": off, "trace": trace}
    raise PlanError("every 4-byte window of the digest is an excluded seed (change the label, record why)")


def pair_seed_exclusion(ls, master_seed: int, n: int, manifest: dict) -> dict:
    """No Claim B pair seed equals any pair seed of any L6 session's schedule."""
    ours = {ls.pair_seed(master_seed, k): k for k in range((n + 1) // 2)}
    l6_seeds = {"C1": manifest["seeds"]["excluded"]["L6_C1_C2"][0], "C2": manifest["seeds"]["excluded"]["L6_C1_C2"][0],
                "S": manifest["seeds"]["excluded"]["L6_S"][0]}
    collisions = []
    checked = 0
    for sess, ms in l6_seeds.items():
        for k in range((L6_SESSION_N[sess] + 1) // 2):
            checked += 1
            ps = ls.pair_seed(ms, k)
            if ps in ours:
                collisions.append({"l6_session": sess, "l6_pair": k, "pair_seed": ps, "claimb_pair": ours[ps]})
    return {"claimb_pairs": len(ours), "l6_pairs_checked": checked, "collisions": collisions}


def load_calibrations(root: Path, manifest: dict) -> tuple[dict, dict]:
    """The two pinned calibration reports and their run logs, each verified against the pin
    (the report bytes hash to the manifest's pin; the run log hashes to the report's
    `inputs.run_log`) — the instrument's own `l6_soak_plan.load_pinned` discipline."""
    reports, logs = {}, {}
    for k in ("C1", "C2"):
        pin = manifest["instrument"]["calibration"][k]
        rp = root / pin["evidence"]
        if sha256_of(rp) != pin["rate_report_sha256"]:
            raise PlanError(f"{k}: {pin['evidence']} does not hash to the pin")
        rep = json.loads(rp.read_text())
        lp = rp.parent / "run_log.json"
        if sha256_of(lp) != rep["inputs"]["run_log"]:
            raise PlanError(f"{k}: run_log.json beside the report does not hash to the report's inputs")
        reports[k], logs[k] = rep, json.loads(lp.read_text())
    return reports, logs


def size_n(lsp, ls, logs: dict, window_s: float) -> dict:
    """N = ⌊0.9 × min(rate_A, rate_B) × W/3600⌋ under policy_matched_wall, the audit fraction
    and N solved together (the instrument's fixed point, with min instead of max)."""
    f = lsp.audit_fraction(int(WINDOW_FRACTION * 3400 * window_s / 3600))
    trace, n = [], None
    for _ in range(FIXED_POINT_ROUNDS):
        rates = {k: lsp.policy_matched_rates(logs[k], f) for k in ("C1", "C2")}
        ra, rb = rates["C1"]["policy_matched_wall"], rates["C2"]["policy_matched_wall"]
        product = WINDOW_FRACTION * min(ra, rb) * window_s / 3600.0
        n_new = int(product)
        trace.append({"f": f, "rate_C1": ra, "rate_C2": rb, "product": product, "n": n_new})
        f_new = lsp.audit_fraction(n_new)
        if n_new == n and abs(f_new - f) < 1e-12:
            break
        n, f = n_new, f_new
    last = trace[-1]
    return {"rule": "policy_matched_wall (D-n1's rates), the SLOWER arm sizes N, T = the window",
            "formula": "floor(0.9 × min(rate_A, rate_B) × W / 3600)", "window_s": window_s,
            "rate_C1": last["rate_C1"], "rate_C2": last["rate_C2"], "sizing_arm": "min",
            "sizing_rate": min(last["rate_C1"], last["rate_C2"]), "unrounded": last["product"], "n": last["n"],
            "audit_fraction": last["f"], "fixed_point_rounds": len(trace), "trace": trace,
            "per_calibration": {k: rates[k]["inputs"] for k in ("C1", "C2")}}


def validate_against_soak(lsp, root: Path, manifest: dict, n: int, audit_fraction: float) -> dict:
    """S #3's recorded pace validates N (never sizes it): the normalised interval × N must
    be ≤ WALL_MARGIN × W. The soak's run log is verified against the pinned rate report's
    `inputs` first."""
    soak = manifest["instrument"]["soak"]
    d = root / soak["evidence"]
    rep_p = d / "rate_report.json"
    if sha256_of(rep_p) != soak["rate_report_sha256"]:
        raise PlanError("S #3's rate_report.json does not hash to the pin")
    rep = json.loads(rep_p.read_text())
    lp = d / "run_log.json"
    if sha256_of(lp) != rep["inputs"]["run_log"]:
        raise PlanError("S #3's run_log.json does not hash to its rate report's inputs.run_log")
    obs = lsp.observed_interval_s(json.loads(lp.read_text()))
    raw = obs["interval_s"]
    adj = (obs["interval_audit_fraction"] - audit_fraction) * obs["mean_audit_s"]
    interval = raw - adj
    predicted = n * interval
    w = float(soak["span_s"])
    return {"soak": soak["session"], "observed_interval_s": raw, "audit_normalisation_s": adj,
            "normalised_interval_s": interval, "predicted_wall_s": predicted, "window_s": w,
            "wall_margin": WALL_MARGIN, "ceiling_s": WALL_MARGIN * w, "pass": predicted <= WALL_MARGIN * w,
            "margin_s": WALL_MARGIN * w - predicted, "observed": obs,
            "note": "validation only — the soak's pace never sizes N (D-n1); S #3's candidates are not Claim B data"}


def check_fabricmap_artifacts(manifest: dict, root: Path) -> list[str]:
    """Falsifier 3 (compatibility drift): this repository's authority files must hash to the
    manifest's pins AND to the copies the instrument imported at 71666b02."""
    out = []
    fa = manifest["fabricmap_artifacts"]
    for k in ("local_map", "phenotype_manifest", "carrier_constants"):
        here = REPO_ROOT / fa[k]["path"]
        if not here.is_file():
            out.append(f"{k}: {fa[k]['path']} missing here")
            continue
        h = sha256_of(here)
        if h != fa[k]["sha256"]:
            out.append(f"{k}: this repository's copy does not hash to the manifest pin")
        theirs = root / "imported/fabricmap" / fa[k]["path"]
        if not theirs.is_file() or sha256_of(theirs) != fa[k]["sha256"]:
            out.append(f"{k}: the instrument's imported copy does not hash to the manifest pin")
    spec = REPO_ROOT / fa["reachability_spec"]["path"]
    if not spec.is_file() or sha256_of(spec) != fa["reachability_spec"]["sha256"]:
        out.append("reachability_spec: does not hash to the pin")
    return out


def build_plan(manifest: dict, root: Path | None = None, require_git: bool = True) -> dict:
    root = root or inst.DEFAULT_ROOT
    verified = inst.bind(root, manifest=manifest, require_git=require_git)
    import l6_schedule as ls  # noqa: E402
    import l6_soak_plan as lsp  # noqa: E402
    drift = check_fabricmap_artifacts(manifest, root)
    if drift:
        raise PlanError("compatibility drift (falsifier 3): " + "; ".join(drift))
    seed = master_seed_by_rule(manifest)
    ms = seed["master_seed"]
    window = float(manifest["window"]["span_s"])
    reports, logs = load_calibrations(root, manifest)
    sizing = size_n(lsp, ls, logs, window)
    n = sizing["n"]
    if n % 2:
        n -= 1          # whole pairs only: the schedule is A,B,B,A over pairs
        sizing["n_rounded_to_pairs"] = n
    excl = pair_seed_exclusion(ls, ms, n, manifest)
    if excl["collisions"]:
        raise PlanError(f"pair-seed collision with an L6 session: {excl['collisions'][:3]}")
    audit_seqs = ls.sampled_audit_seqs(n, int(manifest["audit"]["every"]))
    expected = ls.expected_frames(n, audit_seqs, manifest["protocol"]["wire"])
    budget = ls.crc_budget(expected["total"])
    validation = validate_against_soak(lsp, root, manifest, n, lsp.audit_fraction(n))
    if not validation["pass"]:
        raise PlanError(f"N {n} does not fit the window at S #3's pace: predicted {validation['predicted_wall_s']:.0f} s "
                        f"> {validation['ceiling_s']:.0f} s")
    pairs = n // 2
    import claimb_r1p_model as mdl  # noqa: E402  (block constants only; no model built here)
    if pairs < mdl.BLOCKS * mdl.BLOCK_PAIRS:
        raise PlanError(f"{pairs} pairs < {mdl.BLOCKS} × {mdl.BLOCK_PAIRS}")
    import l6_checks as lc  # noqa: E402
    settle = [lc.median_settle_polls_from_report(reports[k]) for k in ("C1", "C2")]
    sched = ls.schedule(ms, n, ls.MODE_ABBA)
    flags = ls.flags_for(ls.MODE_ABBA, watchdog=True, rec_control=True, sign_control=True)
    return {"schema": "claimb_r1p_plan", "schema_version": "1.0.0", "tool": TOOL_VERSION,
            "instrument": verified,
            "session": "B", "mode": ls.MODE_ABBA, "master_seed": ms, "seed_derivation": seed,
            "seed_exclusion": {"excluded_master_seeds": sorted(excluded_seeds(manifest)), **excl},
            "n": n, "pairs": pairs, "sizing": sizing, "window_s": window,
            "session_timeout_s": window, "timeout_rule": "the runner's deadline is the window after `go`; open at the deadline = STOPPED = HOLD",
            "soak_validation": validation,
            "audit_policy": manifest["audit"]["policy"], "audit_every": int(manifest["audit"]["every"]),
            "audit_seqs": sorted(audit_seqs), "audited_records": len(audit_seqs),
            "expected_frames": expected, "crc_budget": budget, "bad_frame_budget": budget,
            "crc_formula": "ceil(4 × expected_total / 1000) (D-s4)",
            "blocks": {"block_pairs": mdl.BLOCK_PAIRS, "blocks": mdl.BLOCKS, "pairs_in_blocks": mdl.BLOCKS * mdl.BLOCK_PAIRS,
                       "pairs_beyond_blocks": pairs - mdl.BLOCKS * mdl.BLOCK_PAIRS, "sign_threshold": mdl.SIGN_THRESHOLD},
            "flags": flags, "flags_hex": f"{flags:#x}", "protocol": manifest["protocol"]["wire"],
            "watchdog": True, "rec_retry_control": True, "sign_retry_control": True,
            "settle_polls_median_calibration": min(x for x in settle if x is not None),
            "settle_polls_medians": settle,
            "schedule_sha256": hashlib.sha256(json.dumps(sched, sort_keys=True).encode()).hexdigest(),
            "schedule_note": "rows regenerated by l6_schedule.schedule(master_seed, n, 'abba'); the hash pins them",
            "calibration_pins": {k: {"rate_report_sha256": manifest["instrument"]["calibration"][k]["rate_report_sha256"],
                                     "inputs": reports[k]["inputs"]} for k in ("C1", "C2")}}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, default=inst.MANIFEST)
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/claimb_round1prime/plan.json")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    manifest = json.loads(a.manifest.read_text())
    try:
        plan = build_plan(manifest, require_git=not a.no_git)
    except (PlanError, inst.InstrumentRefusal) as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 2
    text = json.dumps(plan, indent=1, sort_keys=True) + "\n"
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(text)
    sha = hashlib.sha256(text.encode()).hexdigest()
    s, v = plan["sizing"], plan["soak_validation"]
    print(f"plan {a.out} sha256 {sha}\n  master_seed {plan['master_seed']} (offset {plan['seed_derivation']['offset']}); "
          f"pair-seed collisions {len(plan['seed_exclusion']['collisions'])} over {plan['seed_exclusion']['l6_pairs_checked']} L6 pairs\n"
          f"  rates C1 {s['rate_C1']:.4f} C2 {s['rate_C2']:.4f} /h; product {s['unrounded']:.4f} -> N {plan['n']} ({plan['pairs']} pairs), "
          f"audits {plan['audited_records']}, frames {plan['expected_frames']['total']}, budget {plan['crc_budget']}\n"
          f"  S #3 validation: interval {v['normalised_interval_s']:.4f} s -> predicted {v['predicted_wall_s']:.1f} s "
          f"<= {v['ceiling_s']:.1f} s ({'PASS' if v['pass'] else 'FAIL'}, margin {v['margin_s']:.1f} s); deadline {plan['session_timeout_s']} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
