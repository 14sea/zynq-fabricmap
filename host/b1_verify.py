#!/usr/bin/env python3
"""B1 — the verifier: score a self-built map against the ground truth, expand it to the
map-v2 schema, and compute the preregistered metrics (host-only; pure).

The map the board renders (and the reference reproduces) is the compact canonical form
`{"anomalies", "entries": [[i, lut, init, confidence, state, [evidence]]...], "pairs": [...],
"seed", "version"}` whose bytes are hashed. `expand()` turns it into the map-v2 document
(`schemas/self_map_v2.schema.json`): one object per address with the functional relation
(LUT, INIT index, polarity), the confidence, the state, the evidence provenance, and the
interaction edges phase C tested.

Metrics (the preregistration §4):
  * precision  — of the entries that CLAIM a position (state decoded/confirmed), the
                 fraction whose (lut, init) is the truth's;
  * recall     — of the addresses the truth maps, the fraction claimed correctly;
  * polarity_errors — claimed entries whose polarity is not the truth's (all direct here);
  * sample_efficiency — probes issued in total, and the probes at which recall at
                 confidence >= 1 first reached 1.0 (from the records' `carto` blocks);
  * calibration — accuracy by confidence level (2 must be >= 1, and both near 1.0 on a
                 correct fabric; a contradiction entry is never counted as a claim);
  * per LUT, with the engineering holdout LUTs (b1_model.HOLDOUT_LUTS) reported apart;
  * replay — two renderings from the same seed and observations are byte-identical
                 (checked by the adjudicator, not here);
  * interaction edges — pairs tested, deviations found.
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


def expand(compact: dict, truth: dict | None = None) -> dict:
    """The map-v2 document from the compact rendering."""
    addrs = (truth or bm.truth_mapping())["addresses"]
    lut_keys = (truth or bm.truth_mapping())["lut_keys"]
    entries = []
    for i, lut, init, conf, state, ev in compact["entries"]:
        far, w, b = addrs[i]
        entries.append({"address": f"{far:#010x}/{w}/{b}", "genome_bit": i,
                        "relation": None if lut < 0 else {"kind": "lut_init", "lut_index": lut,
                                                          "lut_key": lut_keys[lut] if truth else None,
                                                          "init_index": init, "polarity": "direct"},
                        "confidence": conf, "state": state,
                        "evidence": {"record_seqs": list(ev)}})
    edges = [{"a": a, "b": b, "kind": "same_lut" if k == 0 else "cross_lut",
              "result": {0: "pending", 1: "none", 2: "deviation"}[r], "record_seq": s}
             for a, b, k, r, s in compact["pairs"]]
    return {"schema": "self_map", "schema_version": "2.0.0", "cartographer": compact["version"],
            "seed": compact["seed"], "anomalies": compact["anomalies"], "universe": {"addresses": len(addrs),
            "class": "clb_lut_init", "safety_class": "content"}, "entries": entries, "interaction_edges": edges}


def score(compact: dict, truth: dict | None = None, records: list[dict] | None = None) -> dict:
    truth = truth or bm.truth_mapping()
    m = truth["mapping"]
    per_lut = {k: {"total": 0, "claimed": 0, "correct": 0} for k in range(bc.LUTS)}
    claimed = correct = 0
    by_conf = {0: [0, 0], 1: [0, 0], 2: [0, 0]}     # conf -> [claimed, correct]
    polarity_errors = 0
    states = {}
    for i, lut, init, conf, state, ev in compact["entries"]:
        states[state] = states.get(state, 0) + 1
        want = m.get(i)
        if want is not None:
            per_lut[want[0]]["total"] += 1
        if state in CLAIMING:
            claimed += 1
            by_conf[conf][0] += 1
            ok = want is not None and (lut, init) == want
            if ok:
                correct += 1
                by_conf[conf][1] += 1
                per_lut[want[0]]["correct"] += 1
            if want is not None:
                per_lut[want[0]]["claimed"] += 1
    total = sum(1 for i in range(bc.N) if m.get(i) is not None)
    out = {"claimed": claimed, "correct": correct, "total_mapped": total,
           "precision": (correct / claimed) if claimed else None, "recall": correct / total if total else None,
           "polarity_errors": polarity_errors, "states": states, "anomalies": compact["anomalies"],
           "calibration": {str(c): {"claimed": v[0], "correct": v[1], "accuracy": (v[1] / v[0]) if v[0] else None}
                           for c, v in by_conf.items()},
           "per_lut": {truth["lut_keys"][k]: {**v, "holdout": k in bm.HOLDOUT_LUTS} for k, v in per_lut.items()},
           "holdout": _split(per_lut, True), "train": _split(per_lut, False),
           "interaction": {"pairs_tested": len(compact["pairs"]),
                           "deviations": sum(1 for p in compact["pairs"] if p[3] == 2),
                           "pending": sum(1 for p in compact["pairs"] if p[3] == 0)}}
    if records is not None:
        out["sample_efficiency"] = efficiency(records, truth)
    return out


def _split(per_lut: dict, holdout: bool) -> dict:
    ks = [k for k in per_lut if (k in bm.HOLDOUT_LUTS) == holdout]
    tot = sum(per_lut[k]["total"] for k in ks)
    cor = sum(per_lut[k]["correct"] for k in ks)
    cla = sum(per_lut[k]["claimed"] for k in ks)
    return {"luts": ks, "total": tot, "claimed": cla, "correct": cor,
            "recall": cor / tot if tot else None, "precision": cor / cla if cla else None}


def efficiency(records: list[dict], truth: dict) -> dict:
    """From the per-record `carto` blocks (cumulative belief): the probe count at which
    every mapped address was first claimed correctly at confidence >= 1 — the phase A
    decode lands it in one record — and the counts of the phases."""
    m = truth["mapping"]
    correct_at = None
    claimed: dict[int, tuple[int, int]] = {}
    phases = {}
    probes = 0
    for r in records:
        c = r["carto"] if isinstance(r["carto"], dict) else json.loads(r["carto"])
        probes = c["probes_issued"]
        phases[c["phase"]] = phases.get(c["phase"], 0) + 1
        full = r.get("changed_full")
        changed = [json.loads(x) for x in full] if full is not None else c["changed"]
        for i, lut, init, conf, state, ev in changed:
            if state in CLAIMING:
                claimed[i] = (lut, init)
            else:
                claimed.pop(i, None)
        if correct_at is None and all(claimed.get(i) == m[i] for i in m):
            correct_at = probes
    return {"probes_issued": probes, "records": len(records), "phases": phases,
            "probes_to_full_recall_conf1": correct_at,
            "from": "reconstruction (uncapped changed lists)" if any(r.get("changed_full") is not None for r in records)
                    else "board records (changed lists capped at 8 entries: a lower bound)"}


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--map", type=Path, required=True, help="compact map JSON (the rendering)")
    ap.add_argument("--expand", type=Path, default=None, help="write the map-v2 document here")
    a = ap.parse_args(argv)
    compact = json.loads(a.map.read_text())
    truth = bm.truth_mapping()
    s = score(compact, truth)
    print(json.dumps({k: s[k] for k in ("precision", "recall", "claimed", "correct", "states", "anomalies", "holdout", "train")}, indent=1))
    if a.expand:
        a.expand.write_text(json.dumps(expand(compact, truth), indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
