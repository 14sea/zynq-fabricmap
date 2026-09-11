"""Build a modelled B2 run at the REAL pinned plan (budget 600, 9 pairs) — the model standing
in for a board — so the adjudicator can be run end to end against the pinned prediction."""
import hashlib, json, sys, time
from pathlib import Path
R = Path("/home/test/zynq_fabricmap"); sys.path.insert(0, str(R / "host"))
import b1_carto as bc, b1_model as bm, b2_adjudicate as badj, b2_landscape as bl, b2_maps as bmaps, b2_search as bs, b2_session as bsess

plan = json.loads((R / "evidence/b2/plan.json").read_text())
MASTER = plan["seed_derivation"]["master_seed"]; BUDGET = plan["budget_per_arm"]; PAIRS = plan["pairs"]
TRUTH = bm.truth_mapping(); MASKS = bl.universe_mask(TRUTH); FAB = bs.ModelFabric(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors()); MAP_SHA = bmaps.sha256_of(bmaps.load_self_map())
CONSTS = badj.instrument_constants()

def log_for(first, count):
    t = time.time()
    sess = bsess.run(MASTER, BUDGET, PAIRS, first, count, FAB, VIEW, truth=TRUTH, masks=MASKS)
    recs = []
    for c in sess.candidates:
        tab = FAB(c.genome)
        r = {"schema": "loop_record", "schema_version": "1.3.0", "seq": c.seq, "genome": bc.genome_to_hex(c.genome),
             "outcome": "SCORED", "verified": "audited",
             "evidence": {"score": {"functional_readout": [f"{x:016x}" for x in tab],
                                    "scores": badj.additive_scores(tab, CONSTS),
                                    "hw_candidate_commit": hashlib.sha256(bc.genome_to_hex(c.genome).encode()).hexdigest(),
                                    "heartbeat": {"before": c.seq, "after": c.seq + 1}}}}
        if c.arm: r["arm"] = c.arm
        if c.block: r["search"] = json.loads(c.block)
        recs.append(r)
    ident = {"schema": "app_identity", "schema_version": "1.5.0", "control_plane": "standalone", "protocol": "rel-v4",
             "carrier_variant": "0x42310001", "search_version": bs.ENGINE_VERSION, "map_sha256": MAP_SHA,
             "operator_data_sha256": MAP_SHA, "fitness_id": plan["fitness"], "budget_per_arm": BUDGET,
             "master_seed": MASTER, "pairs_total": PAIRS, "pair_first": first, "pair_count": count}
    print(f"  session {first}+{count}: {len(recs)} records in {time.time()-t:.1f}s", file=sys.stderr)
    return {"app_identity": ident, "loop_records": recs}

# Usage: python3 evidence/b2/b2_adjudicate_2026_09_11/modelled_run.py <out-dir>
# then:  python3 host/b2_adjudicate.py --no-common --run-log <out-dir>/run_log_{0,1,2}.json
out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
# 4+4+1 is an ILLUSTRATIVE planning scenario, not the plan: evidence/b2/plan.json says the
# split is UNDETERMINED until B2Q measures the all-self-reporting rate, and lists candidates.
for i, (first, count) in enumerate([(0, 4), (4, 4), (8, 1)]):
    (out / f"run_log_{i}.json").write_text(json.dumps(log_for(first, count)))
print("done", file=sys.stderr)
