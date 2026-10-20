#!/usr/bin/env python3
"""Seed-only forensic reconstruction of the prior production-seed exposure (the owner's ruling of 2026-10-19, sections 2–4).

WHAT THIS IS. Before the repair of 2026-10-18 the harness's integration tests, the author's smoke test and the mutant battery
derived PRODUCTION exploration sets (labels `b4-sim-1` / `b4-sim-2`, the formal hypothesis anchor) on hermetic repository
copies. Most of those trees were deleted; 22 seed records from two trees survive under
`evidence/b4/unit_2b4a_repair_2026_10_18/exposure/`. This script re-derives, from the HISTORICAL derivation code and the
HISTORICAL exclusion contents, every set the committed recipes could have drawn, compares the result with every preserved
record, and writes the exposure receipt the loader excludes from. It derives the retired labels ONLY. It never derives
`b4-sim-3` or any gate label, never runs the engine, the fabric, the cartographer, K9 / K10 or any statistic, and never writes
under `evidence/b4/sim/`.

WHAT THIS IS NOT. Not a recovery of execution records: no manifest, readout, log or verdict is recreated. Every value here is
marked `observed` (present in a preserved record), `reconstructed_recipe` (the committed recipe drew it; no record survives) or
`conservative_superset` (derivable from a drawn pair; whether the run reached the point of computing it cannot be shown).

THE HISTORICAL RECIPE (fixed in section 3 of the ruling, audited in the README):
  base pool P0  = B2's frozen copy ∪ B4's exposed literals ∪ every value of the 38 historical sources, read by the historical
                  loader (`edfc93c:b4/host/b4_seeds.py`) against their pinned digests; the registry of the hermetic tree empty.
  V1 … V7       = `b4-sim-1`, S = 2, the k-th set drawn against P0 ∪ {master} ∪ the values of sets 1 … k-1 (one tree, batches
                  archived one after the other: CompleteBatch 1, InvalidStops up to 7, IncompleteStops up to 3, the smoke test 1,
                  the owner's interrupted re-run 6). Set k depends only on sets 1 … k-1, never on test order.
  V8            = `b4-sim-2`, S = 2, drawn against P0 ∪ {master_1} ∪ set 1 of `b4-sim-1` (CompleteBatch's second batch).
  V9            = `b4-sim-2`, S = 2, drawn against P0 alone (the M1 mutant: the registry ignored; the mutated copy of
                  CompleteBatch's second batch). Under M1 every `b4-sim-1` batch re-draws set 1: no further value.
  M32 (a fixture hypothesis in the formal CLI path) left `hy.HYPOTHESIS_SHA256` — the anchor the master is derived from —
                  untouched: its one batch is set 1 again. No other historical mutant changes a derivation AND runs a batch.
  control seeds = X `sha256('b4-x-control-1|<l>|<o>')[:4]`, D `sha256('b4-d-control-1|<l>|<o>')[:4]` per drawn pair (formulas
                  unchanged since `edfc93c`), classified `conservative_superset`.

Usage (from the repository root; writes only into this script's directory):
    python3 -B evidence/b4/unit_2b4a_exposure_settlement_2026_10_19/reconstruct_exposure.py
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent
R = HERE.parents[2]                                             # the repository root
HIST_COMMIT = "edfc93c"                                         # unit 2b-4a commit C: the derivation code the exposing runs used
HIST_FILES = ("b4/host/b4_seeds.py", "b4/host/b4_rng.py")
ANCHOR = "59948f9be3b4516547fbf039556d4aa6a4afd0b2dda2324619e4d40ef0651ed8"      # the formal hypothesis digest (the ruling, §1)
RETIRED = ("b4-sim-1", "b4-sim-2")
EXPOSURE_DIR = R / "evidence/b4/unit_2b4a_repair_2026_10_18/exposure"
SIM_NS = R / "evidence/b4/sim"
RECEIPT = HERE / "exposure_receipt.json"
COMPARISON = HERE / "reconstruction_comparison.json"
RULING = "build/wip/b4_exposure_owner_ruling_2026_10_19.md (copied unchanged as owner_ruling_2026_10_19.md beside this script)"
X_LABEL, D_LABEL = "b4-x-control-1", "b4-d-control-1"


class Stop(SystemExit):
    """A named uncertainty: the unit stops here (the ruling, §3) — nothing is written."""


def sha_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False)


def control_seed(label: str, l: int, o: int) -> int:
    return int.from_bytes(hashlib.sha256(f"{label}|{l}|{o}".encode("utf-8")).digest()[:4], "big")


def historical_modules(tmp: Path):
    """The derivation code at HIST_COMMIT, extracted from git and imported under its own names; its blob digests recorded."""
    blobs = {}
    for rel in HIST_FILES:
        blob_id = subprocess.run(["git", "-C", str(R), "rev-parse", f"{HIST_COMMIT}:{rel}"], capture_output=True, text=True, check=True).stdout.strip()
        raw = subprocess.run(["git", "-C", str(R), "show", f"{HIST_COMMIT}:{rel}"], capture_output=True, check=True).stdout
        (tmp / Path(rel).name).write_bytes(raw)
        blobs[rel] = {"git_blob": blob_id, "sha256": sha_bytes(raw)}
    sys.path.insert(0, str(tmp))                                 # `from b4_rng import Rng` inside the historical module resolves here
    spec = importlib.util.spec_from_file_location("hist_b4_seeds", tmp / "b4_seeds.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod                                 # dataclasses resolve their module through sys.modules
    spec.loader.exec_module(mod)
    return mod, blobs


def main() -> int:
    if SIM_NS.exists():
        raise Stop(f"{SIM_NS.relative_to(R)} exists: the historical base pool was formed with NO exploration namespace; reconstruct from a checkout without one")
    sys.path.insert(0, str(R / "b4/host"))
    import b4_ff_hypothesis as hy                                # the current pinned anchor, for the equality check only
    import b4_controls as ctl
    if hy.HYPOTHESIS_SHA256 != ANCHOR:
        raise Stop("the formal hypothesis digest is not the ruling's: the recipe's anchor cannot be bound")
    with tempfile.TemporaryDirectory(prefix="b4_hist_") as tmp:
        hist, blobs = historical_modules(Path(tmp))
        for label in RETIRED:                                    # the retired labels only — never b4-sim-3, never a gate label
            assert hist.LABEL_RE.match(label)
        ex = hist.load_exclusion_set(R)                          # the historical loader reads the 38 sources against their digests (refuses on any change)
        if len(ex.sources) != 38 or ex.registry:
            raise Stop(f"the historical base pool is not the documented one: {len(ex.sources)} sources, registry {len(ex.registry)}")
        p0 = frozenset(ex.values)
        masters = {label: hist.master_seed(label, ANCHOR) for label in RETIRED}
        m1, m2 = masters["b4-sim-1"], masters["b4-sim-2"]
        if ctl.x_control_seed(7, 11) != control_seed(X_LABEL, 7, 11) or ctl.d_shuffle_seed(7, 11) != control_seed(D_LABEL, 7, 11):
            raise Stop("the control-seed formulas are not the documented ones")

        variants = []
        sets1: list[list[list[int]]] = []
        pool = set(p0)                                           # set 1 is drawn against P0 alone; the master enters the pool only through the registry of a later batch
        for k in range(1, 8):
            pairs = hist.pair_seeds(m1, 2, pool)
            variants.append({"id": f"V{k}", "label": "b4-sim-1", "count": 2, "master_seed": m1, "pairs": [list(p) for p in pairs],
                             "recipe": f"b4-sim-1 S=2, set {k}: drawn against P0" + (f" ∪ {{master}} ∪ the values of sets 1..{k - 1} (the hermetic tree's registry after {k - 1} archived batches)" if k > 1 else " (an empty registry)"),
                             "exclusion_pooled_total": len(pool), "registry_depth": k - 1, "historical_variant": "committed recipe (edfc93c tests; the smoke test; the owner's re-run)"})
            sets1.append([list(p) for p in pairs])
            pool.add(m1)
            for p in pairs:
                pool.update(p)
        pool8 = set(p0) | {m1} | {v for p in sets1[0] for v in p}
        pairs8 = hist.pair_seeds(m2, 2, pool8)
        variants.append({"id": "V8", "label": "b4-sim-2", "count": 2, "master_seed": m2, "pairs": [list(p) for p in pairs8],
                         "recipe": "b4-sim-2 S=2, set 1: drawn against P0 ∪ {master_1} ∪ set 1 of b4-sim-1 (CompleteBatch's second batch, the registry holding the first)",
                         "exclusion_pooled_total": len(pool8), "registry_depth": 1, "historical_variant": "committed recipe (edfc93c tests)"})
        pairs9 = hist.pair_seeds(m2, 2, set(p0))
        variants.append({"id": "V9", "label": "b4-sim-2", "count": 2, "master_seed": m2, "pairs": [list(p) for p in pairs9],
                         "recipe": "b4-sim-2 S=2 under the M1 mutant: the registry ignored, drawn against P0 alone (the mutated copy of CompleteBatch's second batch)",
                         "exclusion_pooled_total": len(p0), "registry_depth": 0, "historical_variant": "mutant M1 (cdf2c53 battery); b4-sim-1 under M1 re-draws set 1"})
        for v in variants:
            v["control_seeds"] = [{"pair": i, "x_control_seed": control_seed(X_LABEL, l, o), "d_shuffle_seed": control_seed(D_LABEL, l, o)} for i, (l, o) in enumerate(v["pairs"])]

        # --- every preserved record against its recipe (label, registry depth) — a mismatch stops the unit
        records, mismatches = [], []
        by_key = {(v["label"], v["registry_depth"]): v for v in variants if v["id"] != "V9"}
        for p in sorted(EXPOSURE_DIR.rglob("seeds.json")):
            raw = p.read_bytes(); doc = json.loads(raw)
            key = (doc["label"], len(doc["exclusion"]["sim_registry"]))
            v = by_key.get(key)
            rec = {"path": str(p.relative_to(R)), "sha256": sha_bytes(raw), "label": doc["label"], "count": doc["count"], "master_seed": doc["master_seed"], "pairs": doc["pairs"],
                   "pooled_total": doc["exclusion"]["pooled_total"], "registry_depth": key[1], "anchor_hypothesis_sha256": doc["anchor"]["hypothesis_sha256"], "generated_utc": doc["generated_utc"],
                   "variant": v["id"] if v else None}
            problems = []
            if v is None:
                problems.append("no recipe for this label / registry depth")
            else:
                if doc["anchor"]["hypothesis_sha256"] != ANCHOR: problems.append("anchor")
                if doc["master_seed"] != v["master_seed"]: problems.append("master")
                if doc["pairs"] != v["pairs"]: problems.append("pairs")
                if doc["count"] != 2: problems.append("count")
                if doc["exclusion"]["pooled_total"] != v["exclusion_pooled_total"]: problems.append(f"pooled_total {doc['exclusion']['pooled_total']} != {v['exclusion_pooled_total']}")
                if len(doc["exclusion"]["sources"]) != 38: problems.append("sources")
            rec["agrees_with_recipe"] = not problems; rec["problems"] = problems
            records.append(rec)
            if problems:
                mismatches.append((rec["path"], problems))
        if mismatches:
            for path, pr in mismatches:
                print("MISMATCH", path, pr)
            raise Stop("a preserved record does not agree with its reconstructed recipe: the unit stops here (nothing written)")
        observed_ids = {r["variant"] for r in records}
        depths = sorted({r["registry_depth"] for r in records})

        # --- the values, each with its class and origins
        values: dict[int, dict] = {}
        def add(v: int, cls: str, origin: str):
            e = values.setdefault(v, {"classes": set(), "origins": []})
            e["classes"].add(cls); e["origins"].append(origin)
        for v in variants:
            cls = "observed" if v["id"] in observed_ids else "reconstructed_recipe"
            add(v["master_seed"], cls, f"{v['id']}:master")
            for i, (l, o) in enumerate(v["pairs"]):
                add(l, cls, f"{v['id']}:pair{i}.landscape"); add(o, cls, f"{v['id']}:pair{i}.operator")
            for c in v["control_seeds"]:
                add(c["x_control_seed"], "conservative_superset", f"{v['id']}:pair{c['pair']}.x_control_seed")
                add(c["d_shuffle_seed"], "conservative_superset", f"{v['id']}:pair{c['pair']}.d_shuffle_seed")
        pooled = sorted(values)
        pooled_sha = sha_bytes(canonical(pooled).encode())
        already = sorted(v for v in pooled if v in p0)
        now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        receipt = {
            "schema": "b4_exposure_receipt", "schema_version": "1.0.0",
            "status": "reconstructed — a conservative exclusion receipt, NOT a record of execution; the raw evidence of the deleted runs is lost and is not recreated",
            "ruling": RULING, "reconstruction_utc": now, "reconstruction_script": str(Path(__file__).resolve().relative_to(R)),
            "historical_inputs": {"commit": HIST_COMMIT, "files": blobs, "anchor_hypothesis_sha256": ANCHOR, "base_pool_count": len(p0), "base_pool_sha256": sha_bytes(canonical(sorted(p0)).encode()),
                                  "historical_sources": [{"path": s.path, "sha256": s.sha256, "count": len(s.values)} for s in ex.sources],
                                  "note": "the 38 sources were read by the historical loader against their pinned digests; the exploration namespace did not exist (empty registry), as in every exposing run"},
            "envelope": {"labels": list(RETIRED), "variants": [v["id"] for v in variants],
                         "rationale": "the committed recipes of edfc93c (test classes on fresh hermetic trees: CompleteBatch 1 + 1, InvalidStops 7, IncompleteStops 3; the smoke test 1; the owner's interrupted re-run 6) and the one derivation-changing mutant of the cdf2c53 battery that ran a batch (M1); M32 derives set 1 again; the k-th set of a label depends only on the k-1 sets before it, never on the order of tests",
                         "observed_registry_depths": depths, "observed_variants": sorted(observed_ids), "reconstructed_only_variants": sorted(v["id"] for v in variants if v["id"] not in observed_ids),
                         "not_covered": "uncommitted development versions of the tests and of the mutant battery that ran before edfc93c / cdf2c53 (the author's runs with 217 and 218 tests) — their recipes are not recoverable; the number of historical attempts and whether any deleted outcome was inspected cannot be shown"},
            "variants": variants,
            "preserved_records": records,
            "values": [{"value": v, "classes": sorted(values[v]["classes"]), "origins": values[v]["origins"], "already_in_base_pool": v in p0} for v in pooled],
            "pooled": pooled, "pooled_count": len(pooled), "pooled_sha256": pooled_sha,
            "already_in_base_pool": already,
            "limits": ["seed-only: no engine, fabric, cartographer, K9 / K10 or statistic was run", "the retired labels only were derived; b4-sim-3 and the gate labels were not",
                       "a value's class is the strongest claim the surviving evidence supports: observed (in a preserved seeds.json), reconstructed_recipe (the committed recipe drew it, no record survives), conservative_superset (derivable from a drawn pair; whether that run reached the control is not shown)",
                       "this receipt makes the known and the reconstructable exposure EXCLUDED; it does not make the historical exposure record complete"],
        }
        RECEIPT.write_text(json.dumps(receipt, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
        comparison = {"reconstruction_utc": now, "records": len(records), "distinct_record_digests": len({r["sha256"] for r in records}), "distinct_sets_observed": len({(r["master_seed"], canonical(r["pairs"])) for r in records}),
                      "all_agree": True, "per_record": [{k: r[k] for k in ("path", "sha256", "variant", "agrees_with_recipe", "pooled_total", "generated_utc")} for r in records],
                      "variants_observed": sorted(observed_ids), "variants_reconstructed_only": sorted(v["id"] for v in variants if v["id"] not in observed_ids),
                      "pooled_count": len(pooled), "pooled_sha256": pooled_sha, "receipt_sha256": sha_bytes(RECEIPT.read_bytes())}
        COMPARISON.write_text(json.dumps(comparison, indent=1, sort_keys=True, ensure_ascii=True) + "\n")
        print(json.dumps(comparison, indent=1, sort_keys=True))
        return 0


if __name__ == "__main__":
    sys.exit(main())
