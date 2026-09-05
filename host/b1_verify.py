#!/usr/bin/env python3
"""B1 — the verifier (host-only; pure): expand the board's map into the board-authored
`self_map` 2.0.0 document, score it against the ground truth in a SEPARATE verifier report,
and compute the preregistered metrics.

Two documents, never mixed (owner's review 2026-09-05, blocker 4):
  * the BOARD-AUTHORED map (`expand`): only what the board derived — per address the
    relation it measured (LUT index, INIT index), its confidence and state, the observed
    transition (base 0 → set 1 lit), and the evidence (which code probes, which single
    probe) — plus the binding (session token, universe digest, image) and the interaction
    edges. The physical address string is the board's too (the whitelist is compiled in).
    No LUT key, no polarity claim, no truth.
  * the VERIFIER REPORT (`report`): the truth per address, correct / wrong / no-claim, the
    LUT key, the reporting stratum, and the metrics.

Metrics (the preregistration §4), each over a SNAPSHOT of the map:
  * provisional — the map after the 9th probe (every decoded entry at confidence 1), from
    the reconstruction's per-record states;
  * confirmed — the final map (confidence 2 after the singles).
  precision (correct among claims), recall (correct over the truth-mapped addresses),
  observation consistency (every claim carries observed = 1), calibration (accuracy at each
  confidence level in the snapshot where it exists), sample efficiency (probes to full
  recall at confidence ≥ 1; to full confirmation), the reporting strata (LUTs 4-5 vs 0-3 —
  a preregistered stratum, NOT a holdout: the same algorithm probes both and the prediction
  knows the truth), interaction edges, anomalies.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402

CLAIMING = ("decoded", "confirmed")
STRATUM_B = tuple(bm.HOLDOUT_LUTS)        # the preregistered reporting stratum B (LUT indices 4, 5)


def _entries(content: dict) -> list[dict]:
    out = []
    for i, lut, init, conf, state, code_mask, confirm_seq, observed in content["entries"]:
        out.append({"i": i, "lut": lut, "init": init, "confidence": conf, "state": state,
                    "code_mask": code_mask, "confirm_seq": confirm_seq, "observed": observed})
    return out


def expand(whole: dict, addresses: list[tuple[int, int, int]] | None = None) -> dict:
    """The board-authored self_map 2.0.0 from the whole map {"binding", "content"}."""
    addrs = addresses or bm.addresses()
    content, binding = whole["content"], whole["binding"]
    code_seqs = content["code_seqs"]
    entries = []
    for e in _entries(content):
        far, w, b = addrs[e["i"]]
        claim = e["state"] in CLAIMING
        entries.append({"genome_bit": e["i"], "address": f"{far:#010x}/{w}/{b}",
                        "relation": {"kind": "lut_init", "lut_index": e["lut"], "init_index": e["init"]} if claim else None,
                        "confidence": e["confidence"], "state": e["state"],
                        "observed_transition": {"base": 0, "set": 1} if e["observed"] else None,
                        "evidence": {"code_probe_seqs": [code_seqs[p] for p in range(bc.CODE_BITS) if (e["code_mask"] >> p) & 1],
                                     "confirm_seq": e["confirm_seq"] or None}})
    edges = [{"a": a, "b": b, "kind": "same_lut" if k == 0 else "cross_lut",
              "result": {0: "pending", 1: "none", 2: "deviation"}[r], "record_seq": s}
             for a, b, k, r, s in content["pairs"]]
    return {"schema": "self_map", "schema_version": "2.0.0", "cartographer": content["version"],
            "binding": {"token": binding["token"], "universe_sha256": binding["universe"], "image_sha256_lo32": binding["image_lo32"]},
            "seed": content["seed"], "budget": content["budget"], "anomalies": content["anomalies"],
            "code_probe_seqs": list(code_seqs),
            "universe": {"addresses": len(addrs), "class": "clb_lut_init", "safety_class": "content"},
            "entries": entries, "interaction_edges": edges}


def score(content: dict, truth: dict | None = None) -> dict:
    """Metrics of one snapshot (a content dict) against the truth."""
    truth = truth or bm.truth_mapping()
    m = truth["mapping"]
    per_lut = {k: {"total": 0, "claimed": 0, "correct": 0} for k in range(bc.LUTS)}
    claimed = correct = unobserved_claims = 0
    by_conf = {0: [0, 0], 1: [0, 0], 2: [0, 0]}
    states: dict[str, int] = {}
    wrong = []
    for e in _entries(content):
        states[e["state"]] = states.get(e["state"], 0) + 1
        want = m.get(e["i"])
        if want is not None:
            per_lut[want[0]]["total"] += 1
        if e["state"] in CLAIMING:
            claimed += 1
            by_conf[e["confidence"]][0] += 1
            if not e["observed"]:
                unobserved_claims += 1
            ok = want is not None and (e["lut"], e["init"]) == want
            if ok:
                correct += 1
                by_conf[e["confidence"]][1] += 1
                per_lut[want[0]]["correct"] += 1
            else:
                wrong.append(e["i"])
            if want is not None:
                per_lut[want[0]]["claimed"] += 1
    total = sum(1 for i in range(bc.N) if m.get(i) is not None)
    return {"claimed": claimed, "correct": correct, "total_mapped": total, "wrong_claims": wrong[:20],
            "precision": (correct / claimed) if claimed else None, "recall": (correct / total) if total else None,
            "unobserved_claims": unobserved_claims, "states": states, "anomalies": content["anomalies"],
            "calibration": {str(c): {"claimed": v[0], "correct": v[1], "accuracy": (v[1] / v[0]) if v[0] else None}
                            for c, v in by_conf.items()},
            "per_lut": {truth["lut_keys"][k]: {**v, "stratum": "B" if k in STRATUM_B else "A"} for k, v in per_lut.items()},
            "stratum_A": _split(per_lut, False), "stratum_B": _split(per_lut, True),
            "interaction": {"pairs_tested": len(content["pairs"]),
                            "deviations": sum(1 for p in content["pairs"] if p[3] == 2),
                            "pending": sum(1 for p in content["pairs"] if p[3] == 0)}}


def _split(per_lut: dict, stratum_b: bool) -> dict:
    ks = [k for k in per_lut if (k in STRATUM_B) == stratum_b]
    tot = sum(per_lut[k]["total"] for k in ks)
    cor = sum(per_lut[k]["correct"] for k in ks)
    cla = sum(per_lut[k]["claimed"] for k in ks)
    return {"luts": ks, "total": tot, "claimed": cla, "correct": cor,
            "recall": cor / tot if tot else None, "precision": cor / cla if cla else None}


def snapshots(records: list[dict], truth: dict | None = None) -> dict:
    """From a session's records (reference or reconstruction, with `changed_full` entries):
    the provisional snapshot = the belief right after the last code probe, and the probes
    at which full recall (conf ≥ 1) and full confirmation (conf 2) were first reached."""
    truth = truth or bm.truth_mapping()
    m = truth["mapping"]
    belief: dict[int, tuple[int, int, int, str]] = {}
    provisional = None
    full_recall_at = full_confirm_at = None
    probes = 0
    phases: dict[str, int] = {}
    for r in records:
        c = r["carto"] if isinstance(r["carto"], dict) else json.loads(r["carto"])
        if c["phase"] == "baseline":
            continue
        probes = c["probes_issued"]
        phases[c["phase"]] = phases.get(c["phase"], 0) + 1
        for row in r.get("changed_full") or []:
            i, lut, init, conf, state, code_mask, confirm_seq, observed = json.loads(row) if isinstance(row, str) else row
            belief[i] = (lut, init, conf, state)
        if c["phase"] == "code" and probes == bc.CODE_BITS:
            provisional = dict(belief)
        if full_recall_at is None and all(i in belief and belief[i][:2] == m[i] and belief[i][3] in CLAIMING for i in m):
            full_recall_at = probes
        if full_confirm_at is None and all(i in belief and belief[i][:2] == m[i] and belief[i][2] == 2 for i in m):
            full_confirm_at = probes
    prov_score = None
    if provisional is not None:
        n_claim = sum(1 for v in provisional.values() if v[3] in CLAIMING)
        n_ok = sum(1 for i, v in provisional.items() if v[3] in CLAIMING and v[:2] == m.get(i))
        prov_score = {"claimed": n_claim, "correct": n_ok, "precision": n_ok / n_claim if n_claim else None,
                      "recall": n_ok / len(m) if m else None}
    return {"probes_issued": probes, "phases": phases, "provisional": prov_score,
            "probes_to_full_recall_conf1": full_recall_at, "probes_to_full_confirmation": full_confirm_at}


def report(whole: dict, records: list[dict] | None = None, truth: dict | None = None) -> dict:
    """The verifier's document: truth per entry (never in the board's map), the confirmed
    snapshot's metrics, and — with the session records — the provisional snapshot and the
    sample-efficiency figures."""
    truth = truth or bm.truth_mapping()
    m = truth["mapping"]
    content = whole["content"]
    per_entry = []
    for e in _entries(content):
        want = m.get(e["i"])
        claim = e["state"] in CLAIMING
        per_entry.append({"genome_bit": e["i"], "truth": {"lut_index": want[0], "init_index": want[1],
                                                           "lut_key": truth["lut_keys"][want[0]]} if want else None,
                          "claimed": claim, "correct": bool(claim and want is not None and (e["lut"], e["init"]) == want),
                          "stratum": ("B" if want and want[0] in STRATUM_B else "A") if want else None})
    out = {"schema": "self_map_verifier_report", "schema_version": "1.0.0",
           "truth_source": {"local_map": str(bm.LOCAL_MAP.relative_to(REPO_ROOT)), "lut_keys": truth["lut_keys"]},
           "confirmed": score(content, truth), "per_entry": per_entry}
    if records is not None:
        out["snapshots"] = snapshots(records, truth)
    return out


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", type=Path, required=True, help="the whole map JSON (binding + content)")
    ap.add_argument("--expand", type=Path, default=None)
    ap.add_argument("--report", type=Path, default=None)
    a = ap.parse_args(argv)
    whole = json.loads(a.map.read_text())
    rep = report(whole)
    print(json.dumps({k: rep["confirmed"][k] for k in ("precision", "recall", "claimed", "states", "anomalies", "stratum_A", "stratum_B")}, indent=1))
    if a.expand:
        a.expand.write_text(json.dumps(expand(whole), indent=1) + "\n")
    if a.report:
        a.report.write_text(json.dumps(rep, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
