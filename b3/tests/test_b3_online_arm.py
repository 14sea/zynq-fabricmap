"""b3/host/b3_online_arm.py — the online arm: trace-for-trace and entry-for-entry equivalence with the
B2-pinned `host/b3_online.run_online`; the 1.1.0 ledger validates and the frozen 1.0.0 refuses it;
the holdout has no entry and no map update; the combined record commitment (B2's search state text
joined to the cartographer's text — held to B2's own function, and load-bearing in both halves); the
replay reproduces every version, decode and commitment and names a tampered entry, a tampered
commitment and a half-given commitment check; the end-to-end frozen-arm rule."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online as frozen  # noqa: E402
import b3_online_arm as oa  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
LAND = bl.Landscape("F1", 2468, masks=MASKS, truth=TRUTH)


def ledger_doc(res, budget, version="1.1.0"):
    return {"schema": "specimen_ledger", "schema_version": version,
            "binding": {"token": "00" * 16, "universe_sha256": "00" * 32, "image_sha256_lo32": "00000000", "landscape_seed": LAND.seed},
            "seed": 9, "fitness": "F1", "budget": budget, "anomalies": res.anomalies, "final_map_version": res.version_trace[-1],
            "entries": res.ledger}


def validator(schema_path: Path):
    import jsonschema
    schema = json.loads(schema_path.read_text())
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)
    return cls(schema)


class Equivalence(unittest.TestCase):
    def test_the_copy_reproduces_the_frozen_reference(self):
        mine = oa.run_online(LAND, 9, 600, FAB)
        ref = frozen.run_online(LAND, 9, 600, FAB, keep_ledger=True)
        self.assertEqual(mine.best_trace, ref.best_trace)
        self.assertEqual(mine.decoded_trace, ref.decoded_trace)
        self.assertEqual(mine.version_trace, ref.version_trace)
        self.assertEqual(mine.anomalies, ref.anomalies)
        self.assertEqual(mine.column_moves, ref.column_moves)
        self.assertEqual(len(mine.ledger), len(ref.ledger))
        for a, b in zip(mine.ledger, ref.ledger):
            a2 = dict(a)
            self.assertIn("anomalies", a2)
            del a2["anomalies"]
            self.assertEqual(a2, b)

    def test_the_committed_ideal_model_row_is_reproduced(self):
        row = json.loads((R / "evidence/b3/sim/raw_F1.json").read_text())["rows"][0]
        land = bl.Landscape("F1", row["landscape_seed"], masks=MASKS, truth=TRUTH)
        res = oa.run_online(land, row["operator_seed"], 3000, FAB, keep_ledger=False)
        grid = (100, 200, 300, 400, 600, 800, 1000, 1500, 2000, 3000)
        self.assertEqual([res.best_trace[b - 1] for b in grid], row["search"]["O"])
        self.assertEqual([res.decoded_trace[b - 1] for b in grid], row["online"]["decoded_at_grid"])
        self.assertEqual(res.anomalies, 0)


class Ledger(unittest.TestCase):
    def test_1_1_0_validates_and_the_frozen_1_0_0_refuses_the_entry(self):
        res = oa.run_online(LAND, 9, 64, FAB)
        v11 = validator(R / "b3/schemas/specimen_ledger.schema.json")
        self.assertEqual(list(v11.iter_errors(ledger_doc(res, 64))), [])
        bad = ledger_doc(res, 64)
        bad["entries"][0]["anomalies"] = -1
        self.assertTrue(list(v11.iter_errors(bad)))
        v10 = validator(R / "schemas/specimen_ledger.schema.json")
        errs = list(v10.iter_errors(ledger_doc(res, 64, version="1.0.0")))
        self.assertTrue(errs, "the frozen 1.0.0 entry must refuse the running anomaly count (that is why 1.1.0 exists)")
        self.assertTrue(any("anomalies" in e.message for e in errs))

    def test_the_holdout_has_no_entry_and_does_not_touch_the_map(self):
        res = oa.run_online(LAND, 9, 120, FAB)
        self.assertEqual(len(res.ledger), 120)
        self.assertEqual(res.ledger[-1]["map_version_after"], res.carto.version)
        self.assertEqual(res.ledger[-1]["anomalies"], res.carto.anomalies)
        self.assertEqual(res.champion_holdout, LAND.holdout_fitness(res.champion.tables))
        self.assertEqual(res.carto_state_trace[-1], res.carto.state_text())
        self.assertEqual(len(res.state_trace), 120)
        self.assertEqual(len(res.search_state_trace), 120)

    def test_the_replay_reproduces_every_version_decode_and_commitment(self):
        res = oa.run_online(LAND, 9, 400, FAB)
        c = carto_mod.SpecimenCarto()
        for e, ctext, stext, want in zip(res.ledger, res.carto_state_trace, res.search_state_trace, res.state_trace):
            self.assertEqual(c.version, e["map_version"])
            newly = c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
            self.assertEqual(sorted(newly), sorted(i for i, _, _ in e["decoded"]))
            self.assertEqual(c.version, e["map_version_after"])
            self.assertEqual(c.anomalies, e["anomalies"])
            self.assertEqual(c.state_text(), ctext)
            self.assertEqual(oa.state_sha256(stext, ctext), want)
        # the production replay, with the commitments: clean
        replayed, f = oa.replay(res.ledger, res.search_state_trace, res.state_trace)
        self.assertEqual(f, [])
        self.assertEqual(replayed.snapshot(), res.carto.snapshot())
        # a tampered commitment is named at its entry
        bad = list(res.state_trace)
        bad[77] = "0" * 64
        _, f = oa.replay(res.ledger, res.search_state_trace, bad)
        self.assertEqual(len(f), 1)
        self.assertIn("seq 78: state_sha256", f[0])
        # a tampered search state (the population) is named through the commitment
        bad_s = list(res.search_state_trace)
        bad_s[5] = bad_s[5].replace(";", ";9:9:00;", 1)
        _, f = oa.replay(res.ledger, bad_s, res.state_trace)
        self.assertEqual(len(f), 1)
        self.assertIn("seq 6: state_sha256", f[0])
        # the commitments cannot be omitted: the production replay has no optional form
        with self.assertRaises(TypeError):
            oa.replay(res.ledger)                                          # type: ignore[call-arg]
        with self.assertRaises(TypeError):
            oa.replay(res.ledger, res.search_state_trace)                  # type: ignore[call-arg]
        for args in ((res.search_state_trace, None), (None, res.state_trace), (res.search_state_trace[:-1], res.state_trace),
                     (res.search_state_trace, [1] * len(res.ledger))):
            _, f = oa.replay(res.ledger, *args)
            self.assertEqual(len(f), 1, args)
            self.assertIn("commitment check", f[0])
        # the cartographer-only helper is a different, explicitly named function
        c_only, f = oa.replay_cartographer_only(res.ledger)
        self.assertEqual(f, [])
        self.assertEqual(c_only.snapshot(), res.carto.snapshot())

    def test_the_commitment_is_b2s_text_plus_the_cartographer_and_load_bearing_in_both_halves(self):
        res = oa.run_online(LAND, 9, 96, FAB)
        # the search half is byte for byte what b2_search.state_sha256 hashes (checked through B2's own function)
        pop = [bs.Individual(3, [0] * 6, 7, born=1), bs.Individual(0, [0] * 6, 2, born=0)]
        text = oa.search_state_text(1, 11, 22, 600, 33, 4, 7, pop)
        import hashlib
        self.assertEqual(hashlib.sha256(text.encode()).hexdigest(), bs.state_sha256(1, 11, 22, 600, 33, 4, 7, pop))
        self.assertTrue(text.startswith(f"{bs.ENGINE_VERSION}|1|11|22|600|33|4|7|"))
        # control 1: the search state changes, the cartographer does not -> the digest changes
        stext, ctext = res.search_state_trace[-1], res.carto_state_trace[-1]
        self.assertEqual(oa.state_sha256(stext, ctext), res.state_trace[-1])
        other_pop = oa.search_state_text(oa.ARM_CODE, LAND.seed, 9, 96, 96, 12, res.best_trace[-1] + 1, [])
        self.assertNotEqual(oa.state_sha256(other_pop, ctext), res.state_trace[-1])
        # control 2: the cartographer changes, the search state does not -> the digest changes
        c2 = carto_mod.SpecimenCarto()
        for e in res.ledger:
            c2.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
        self.assertEqual(c2.state_text(), ctext)
        free = next(i for i in range(292) if i not in c2.decoded)
        c2.observe([free], [TRUTH["mapping"][free]])           # one more decode
        self.assertNotEqual(c2.state_text(), ctext)
        self.assertNotEqual(oa.state_sha256(stext, c2.state_text()), res.state_trace[-1])
        self.assertEqual(oa.ARM_CODE, 2)

    def test_a_tampered_ledger_is_named_by_the_replay(self):
        res = oa.run_online(LAND, 9, 200, FAB)
        for how in ("decoded", "version", "delta"):
            with self.subTest(how=how):
                ledger = json.loads(json.dumps(res.ledger))
                target = next(e for e in ledger if e["decoded"])
                if how == "decoded":
                    target["decoded"] = []
                elif how == "version":
                    target["map_version_after"] += 1
                else:
                    k, v = target["behaviour_delta"][0]
                    target["behaviour_delta"][0] = [k, (v + 1) % 64]
                _, f = oa.replay_cartographer_only(ledger)
                self.assertEqual(len(f), 1, f)
                self.assertIn(f"seq {target['seq']}", f[0])
                _, f2 = oa.replay(ledger, res.search_state_trace, res.state_trace)
                self.assertEqual(f2, f)                                    # the production replay names it too


class RecordBlocks(unittest.TestCase):
    """Lifecycle 2, the session unit: run_online emits the O arm's record blocks itself — one search
    block per evaluation carrying that evaluation's ledger entry and the combined commitment, and the
    champion's holdout block with no ledger and the FINAL commitment; only a ledger-keeping, unpermuted
    run is record-capable."""

    @classmethod
    def setUpClass(cls):
        cls.res = oa.run_online(LAND, 9, 96, FAB, pair=5)

    def test_one_search_block_per_evaluation_with_its_entry_and_commitment(self):
        res = self.res
        self.assertTrue(res.record_capable)
        self.assertEqual((len(res.blocks), len(res.genomes), len(res.state_trace)), (96, 96, 96))
        for n, raw in enumerate(res.blocks):
            b = json.loads(raw)
            self.assertEqual(sorted(b), sorted(oa.BLOCK_KEYS + ("ledger",)))
            self.assertEqual(b["ledger"], res.ledger[n])
            self.assertEqual(b["state_sha256"], res.state_trace[n])
            self.assertEqual((b["arm"], b["pair"], b["eval"], b["version"], b["holdout"]), ("O", 5, n + 1, bs.ENGINE_VERSION, None))
            self.assertEqual((b["landscape_seed"], b["operator_seed"]), (LAND.seed, 9))
            self.assertEqual(b["move"], {"bits": res.ledger[n]["intervention"], "kind": res.ledger[n]["move_kind"]})
            self.assertEqual((b["fitness"], b["parent_born"]), (res.ledger[n]["fitness"], res.ledger[n]["parent_born"]))
            self.assertEqual(b["best"], res.best_trace[n])
            self.assertEqual(len(b["population"]), bs.MU)
            self.assertEqual(raw, json.dumps(b, sort_keys=True, separators=(",", ":")), "compact JSON, sorted keys, as the image writes it")
        # B2's convention: the generation closes on its last child; the column-move counter is the running one
        selected = [json.loads(r)["selected"] for r in res.blocks]
        self.assertEqual(sum(selected), -(-96 // bs.LAMBDA))
        self.assertTrue(selected[-1])
        gens = [json.loads(r)["generation"] for r in res.blocks]
        self.assertEqual(gens[bs.LAMBDA - 1], 1)
        self.assertEqual(gens[bs.LAMBDA], 1)
        self.assertEqual(gens[bs.LAMBDA - 2], 0)
        cols = [json.loads(r)["column_moves"] for r in res.blocks]
        self.assertEqual(cols, [sum(1 for e in res.ledger[:n + 1] if e["move_kind"] == "column") for n in range(96)])
        self.assertEqual(cols[-1], res.column_moves)

    def test_the_population_per_record_is_b2s_selection_convention(self):
        """An independent oracle for every record's population (and so for the search half of every
        commitment): the population changes only at a selection; a record that closes its generation
        shows the (μ + λ) truncation of the previous population plus this generation's children (fit =
        the records' fitness, born = μ + eval − 1), ordered by (−fit, born); every other record shows the
        population as it was before the generation."""
        res = self.res
        base = LAND.train_fitness(FAB(0))
        pop = [(base, i) for i in range(bs.MU)]                       # (fit, born), the initial population
        gen_children = []
        for raw in res.blocks:
            b = json.loads(raw)
            gen_children.append((b["fitness"], bs.MU + b["eval"] - 1))
            if b["selected"]:
                pool = sorted(pop + gen_children, key=lambda x: (-x[0], x[1]))[:bs.MU]
                pop = pool
                gen_children = []
            self.assertEqual([(p["fit"], p["born"]) for p in b["population"]], pop, f"eval {b['eval']}")
        self.assertEqual(gen_children, [], "the last record closes the last generation")
        self.assertEqual([(p["fit"], p["born"]) for p in json.loads(res.champion_block)["population"]], pop)
        # and the population did change at least once, so the oracle discriminates
        self.assertNotEqual(pop, [(base, i) for i in range(bs.MU)])

    def test_the_search_state_half_of_the_commitment_is_b2s_block_text(self):
        """The block's own fields (eval, generation, best, population) are the ones the commitment hashed."""
        res = self.res
        for n, raw in enumerate(res.blocks):
            b = json.loads(raw)
            parts = res.search_state_trace[n].split("|")
            self.assertEqual((int(parts[5]), int(parts[6]), int(parts[7])), (b["eval"], b["generation"], b["best"]))
            pop = [(int(x.split(":")[0]), int(x.split(":")[1])) for x in parts[8].split(";") if x]
            self.assertEqual(pop, [(p["fit"], p["born"]) for p in b["population"]])

    def test_the_holdout_block_has_no_ledger_and_the_final_commitment(self):
        res = self.res
        hb = json.loads(res.champion_block)
        self.assertEqual(sorted(hb), sorted(oa.BLOCK_KEYS))
        self.assertNotIn("ledger", hb)
        self.assertEqual((hb["holdout"], hb["move"], hb["fitness"], hb["parent_born"], hb["selected"], hb["eval"]),
                         (res.champion_holdout, None, None, None, False, 96))
        self.assertEqual(hb["state_sha256"], res.state_trace[-1])
        last = json.loads(res.blocks[-1])
        self.assertEqual((hb["best"], hb["generation"], hb["column_moves"], hb["population"]), (last["best"], last["generation"], last["column_moves"], last["population"]))
        self.assertEqual(len(res.ledger), 96, "the holdout evaluation adds no entry")
        self.assertEqual(hb["state_sha256"], oa.state_sha256(res.search_state_trace[-1], res.carto.state_text()))

    def test_a_gate_control_is_not_record_capable(self):
        for kw in ({"keep_ledger": False}, {"delta_perm": list(range(1, 384)) + [0]}, {"keep_ledger": False, "delta_perm": list(range(1, 384)) + [0]}):
            with self.subTest(**{k: (v if not isinstance(v, list) else "perm") for k, v in kw.items()}):
                res = oa.run_online(LAND, 9, 24, FAB, **kw)
                self.assertFalse(res.record_capable)
                self.assertEqual((res.blocks, res.champion_block), ([], ""))
                self.assertEqual(len(res.best_trace), 24, "the search itself still runs")

    def test_the_blocks_change_nothing_the_prediction_reads(self):
        """The same run without and with `pair` (blocks differ only in `pair`): traces, ledger, commitments equal."""
        a, b = self.res, oa.run_online(LAND, 9, 96, FAB, pair=0)
        self.assertEqual((a.best_trace, a.ledger, a.state_trace, a.champion_holdout, a.genomes), (b.best_trace, b.ledger, b.state_trace, b.champion_holdout, b.genomes))
        self.assertNotEqual(a.blocks, b.blocks)
        self.assertEqual([dict(json.loads(x), pair=0) for x in a.blocks], [json.loads(x) for x in b.blocks])


class EndToEnd(unittest.TestCase):
    def test_the_frozen_arm_is_charged_333(self):
        trace = list(range(1, 1001))
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 100), 2)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 333), 2)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 334), 1)
        self.assertEqual(oa.end_to_end_frozen(trace, 2, 1000), 667)
        self.assertEqual(oa.B1_MAP_COST, 333)
        self.assertEqual(bc.N, 292)


if __name__ == "__main__":
    unittest.main()
