"""The adjudicator must reproduce a correct run from the SERVED readouts — and refuse every
way a board could deviate from the algorithm or contradict its own measurement.

The fixture is a modelled session: `b2_session.run` drives the reference engine over the
fabric model, and each record is given the readout that model would have measured for its
genome. That is the model standing in for a board **in the fixture only** — the adjudicator
itself never computes a readout; it recomputes every fitness from the bytes the record
carries. The negative cases exploit exactly that: a readout is tampered with while its
record's self-report is left alone (and the reverse), which a model-driven adjudicator would
wave through.

The instrument's common envelope is not part of these fixtures (they carry the score evidence
the adjudicator reads, not a full signed rel-v4 record), so `common=False` throughout; the
common layer is `tests/test_b2_wire.py`'s and the runner's.
"""
from __future__ import annotations

import copy
import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_adjudicate as badj  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
MAP_SHA = bmaps.sha256_of(bmaps.load_self_map())
CONSTS = json.loads(bl.CARRIER_CONSTANTS.read_text())

MASTER, BUDGET, PAIRS = 716169644, 12, 3          # 12 = one full generation of 8 and a short one of 4
SEEDS = bsess.pair_seeds(MASTER, PAIRS)
PLAN = {"schema": "b2_plan", "fitness": "F1", "budget_per_arm": BUDGET, "pairs": PAIRS,
        "map": {"sha256": MAP_SHA}, "seed_derivation": {"master_seed": MASTER}}
PREDICTION = bp.build_prediction("F1", BUDGET, SEEDS, MAP_SHA)


def identity(pair_first: int, pair_count: int) -> dict:
    return {"schema": "app_identity", "schema_version": "1.5.0", "control_plane": "standalone",
            "protocol": "rel-v4", "carrier_variant": "0x42310001", "search_version": bs.ENGINE_VERSION,
            "map_sha256": MAP_SHA, "operator_data_sha256": MAP_SHA, "fitness_id": "F1",
            "budget_per_arm": BUDGET, "master_seed": MASTER, "pairs_total": PAIRS,
            "pair_first": pair_first, "pair_count": pair_count}


def modelled_log(pair_first: int, pair_count: int) -> dict:
    """One session as a correct board would have written it: the reference's candidates, each
    with the readout the fabric model would have measured for that genome."""
    session = bsess.run(MASTER, BUDGET, PAIRS, pair_first, pair_count, FAB, VIEW, truth=TRUTH, masks=MASKS)
    records = []
    for c in session.candidates:
        tables = FAB(c.genome)
        commit = hashlib.sha256(bc.genome_to_hex(c.genome).encode()).hexdigest()
        rec = {"schema": "loop_record", "schema_version": "1.3.0", "seq": c.seq,
               "genome": bc.genome_to_hex(c.genome), "outcome": "SCORED", "verified": "audited",
               "evidence": {"score": {"functional_readout": [f"{t:016x}" for t in tables],
                                      "scores": badj.additive_scores(tables, CONSTS),
                                      "hw_candidate_commit": commit,
                                      "heartbeat": {"before": c.seq, "after": c.seq + 1}}}}
        if c.arm:
            rec["arm"] = c.arm
        if c.block:
            rec["search"] = json.loads(c.block)
        records.append(rec)
    return {"app_identity": identity(pair_first, pair_count), "loop_records": records}


def judge(logs, plan=PLAN, prediction=PREDICTION) -> dict:
    return badj.adjudicate(logs, plan, prediction, consts=CONSTS, common=False)


class Accepts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.whole = modelled_log(0, PAIRS)
        cls.split = [modelled_log(0, 2), modelled_log(2, 1)]

    def test_a_correct_single_session_run_passes(self):
        res = judge([self.whole])
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["kills"], [])
        self.assertEqual(res["deltas"], PREDICTION["deltas"])
        self.assertEqual(res["primary"], PREDICTION["predicted_primary"])
        self.assertEqual(res["fitness_sequence_sha256"], PREDICTION["fitness_sequence_sha256"])
        self.assertEqual(res["fitness_sequence_length"], PREDICTION["fitness_sequence_length"])
        self.assertEqual(res["replay"]["records_replayed"], PAIRS * (2 * BUDGET + 2))

    def test_the_same_run_split_across_sessions_gives_the_same_verdict(self):
        res = judge(self.split)
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["deltas"], PREDICTION["deltas"])
        self.assertEqual(res["fitness_sequence_sha256"], PREDICTION["fitness_sequence_sha256"])
        self.assertEqual([s["pair_count"] for s in res["sessions"]], [2, 1])

    def test_the_sessions_are_ordered_by_their_slices_not_by_the_caller(self):
        res = judge(list(reversed(self.split)))
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual([s["pair_first"] for s in res["sessions"]], [0, 2])

    def test_the_adjudicator_never_produces_a_readout_of_its_own(self):
        """Every fitness must come from the bytes the record served. With the fabric model
        made unusable, a correct run still adjudicates — and the tampered-readout cases above
        show the recomputation is real, not skipped."""
        def refuse(*a, **k):
            raise AssertionError("the adjudicator reached for the fabric model")
        saved = (bs.ModelFabric, bm.Fabric)
        bs.ModelFabric, bm.Fabric = refuse, refuse
        try:
            res = judge([self.whole])
        finally:
            bs.ModelFabric, bm.Fabric = saved
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["fitness_sequence_sha256"], PREDICTION["fitness_sequence_sha256"])

    def test_the_result_states_what_it_did_not_check(self):
        res = judge([self.whole])
        for layer in ("manifest pins", "carrier qualification", "evidence exports"):
            self.assertIn(layer, res["not_checked_here"])


class Refuses(unittest.TestCase):
    """Every deviation is ONE named finding, and the served-readout contradictions are KILLs."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(0, PAIRS)

    def _judge(self, mutate) -> dict:
        log = copy.deepcopy(self.base)
        mutate(log)
        return judge([log])

    def _kills(self, mutate, needle: str):
        res = self._judge(mutate)
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])
        self.assertTrue(any(needle in x for x in res["kills"]), f"{needle!r} not in {res['kills'][:3]}")

    def _holds(self, mutate, needle: str):
        res = self._judge(mutate)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any(needle in x for x in res["findings"]), f"{needle!r} not in {res['findings'][:4]}")

    # -------------------------------------------------- helpers over the fixture
    @staticmethod
    def _search_records(log) -> list[dict]:
        return [r for r in log["loop_records"] if isinstance(r.get("search"), dict)
                and r["search"]["holdout"] is None]

    @staticmethod
    def _holdout_records(log) -> list[dict]:
        return [r for r in log["loop_records"] if isinstance(r.get("search"), dict)
                and r["search"]["holdout"] is not None]

    @staticmethod
    def _landscape(rec) -> bl.Landscape:
        return bl.Landscape("F1", SEEDS[rec["search"]["pair"]][0], masks=MASKS, truth=TRUTH)

    @classmethod
    def _readout_with_another_train_fitness(cls, rec, want: int) -> list[int]:
        """F1 is a small integer, so a readout picked blind can collide with the fitness it is
        meant to contradict; this finds one that actually differs."""
        land = cls._landscape(rec)
        base = int(rec["genome"], 16)
        for i in range(bc.N):
            tables = FAB(base ^ (1 << i))
            if land.train_fitness(tables) != want:
                return tables
        raise AssertionError("no neighbouring genome measures a different train F1")

    @staticmethod
    def _set_readout(rec, tables):
        rec["evidence"]["score"]["functional_readout"] = [f"{t:016x}" for t in tables]
        rec["evidence"]["score"]["scores"] = badj.additive_scores(tables, CONSTS)

    # -------------------------------------------------- the measurement pass (KILL)
    def test_a_tampered_readout_contradicts_the_self_reported_fitness(self):
        """The readout alone is changed — the record keeps its own fitness claim. A module that
        recomputed from the MODEL instead of from the served bytes would see nothing here."""
        def mutate(log):
            rec = self._search_records(log)[5]
            self._set_readout(rec, self._readout_with_another_train_fitness(rec, rec["search"]["fitness"]))
        self._kills(mutate, "the train F1 of the readout the board served")

    def test_a_swapped_readout_is_caught_by_the_additive_known_answer(self):
        """When the swapped readout's F1 collides with the fitness it replaces, the PL scorer's
        own count over the same bytes still does not."""
        def mutate(log):
            rec = self._search_records(log)[5]
            land = self._landscape(rec)
            base = int(rec["genome"], 16)
            for i in range(bc.N):
                tables = FAB(base ^ (1 << i))
                if land.train_fitness(tables) == rec["search"]["fitness"] \
                        and badj.additive_scores(tables, CONSTS) != rec["evidence"]["score"]["scores"]:
                    rec["evidence"]["score"]["functional_readout"] = [f"{t:016x}" for t in tables]
                    return
            raise AssertionError("no colliding readout to swap in")
        self._kills(mutate, "additive count")

    def test_a_tampered_fitness_contradicts_the_served_readout(self):
        def mutate(log):
            self._search_records(log)[3]["search"]["fitness"] += 1
        self._kills(mutate, "the train F1 of the readout the board served")

    def test_a_tampered_holdout_value_contradicts_its_re_measurement(self):
        def mutate(log):
            self._holdout_records(log)[0]["search"]["holdout"] += 1
        self._kills(mutate, "the holdout F1 of the readout the board served")

    def test_a_tampered_additive_score_contradicts_the_same_readout(self):
        def mutate(log):
            self._search_records(log)[2]["evidence"]["score"]["scores"][0] += 1
        self._kills(mutate, "additive count")

    def test_every_contradicting_record_is_named_not_only_the_first(self):
        def mutate(log):
            for rec in self._search_records(log)[:4]:
                rec["search"]["fitness"] += 1
        res = self._judge(mutate)
        self.assertEqual(len([x for x in res["kills"] if "train F1" in x]), 4, res["kills"])

    def test_a_wall_of_contradictions_is_capped_with_a_count(self):
        def mutate(log):
            for rec in self._search_records(log):
                rec["search"]["fitness"] += 1
        res = self._judge(mutate)
        self.assertEqual(len(res["kills"]), badj.MAX_NAMED_PER_PASS + 1)
        self.assertIn("more measurement findings", res["kills"][-1])

    # -------------------------------------------------- the replay (HOLD)
    def test_a_genome_the_reference_would_not_have_proposed(self):
        def mutate(log):
            rec = self._search_records(log)[4]
            rec["genome"] = bc.genome_to_hex(int(rec["genome"], 16) ^ 1)
        self._holds(mutate, "autonomy replay failed")

    def test_a_move_kind_the_reference_did_not_draw(self):
        def mutate(log):
            rec = next(r for r in self._search_records(log) if r["search"]["arm"] == "B")
            rec["search"]["move"]["kind"] = "column" if rec["search"]["move"]["kind"] == "random" else "random"
        self._holds(mutate, "is not the reference's")

    def test_a_parent_the_reference_did_not_draw(self):
        def mutate(log):
            rec = self._search_records(log)[9]
            rec["search"]["parent_born"] = 99
        self._holds(mutate, "the reference drew index")

    def test_a_commitment_that_is_not_the_replayed_state(self):
        def mutate(log):
            self._search_records(log)[6]["search"]["state_sha256"] = "0" * 64
        self._holds(mutate, "state_sha256")

    def test_a_generation_closed_on_the_wrong_record(self):
        def mutate(log):
            recs = self._search_records(log)
            recs[0]["search"]["selected"] = True
        self._holds(mutate, "selected")

    def test_a_population_the_selection_would_not_have_left(self):
        def mutate(log):
            recs = self._search_records(log)
            recs[bs.LAMBDA - 1]["search"]["population"][0]["born"] = 77
        self._holds(mutate, "population")

    def test_a_best_so_far_that_went_its_own_way(self):
        def mutate(log):
            self._search_records(log)[7]["search"]["best"] += 3
        self._holds(mutate, "best")

    def test_a_column_move_counter_the_reference_did_not_reach(self):
        def mutate(log):
            rec = next(r for r in self._search_records(log) if r["search"]["arm"] == "B")
            rec["search"]["column_moves"] += 1
        self._holds(mutate, "column_moves")

    def test_a_holdout_record_that_re_measures_something_else(self):
        def mutate(log):
            rec = self._holdout_records(log)[0]
            rec["genome"] = bc.genome_to_hex(int(rec["genome"], 16) ^ 1)
        self._holds(mutate, "not the champion the replayed selection left")

    def test_a_champion_that_re_measures_to_a_different_train_fitness(self):
        """The re-measurement is made self-consistent — its own holdout claim is updated — so
        only the known answer that the same genome measures the same way can catch it."""
        def mutate(log):
            rec = self._holdout_records(log)[0]
            champion_fit = self._landscape(rec).train_fitness(
                [int(w, 16) for w in rec["evidence"]["score"]["functional_readout"]])
            other = self._readout_with_another_train_fitness(rec, champion_fit)
            self._set_readout(rec, other)
            rec["search"]["holdout"] = self._landscape(rec).holdout_fitness(other)
        self._holds(mutate, "measured when it was evaluated")

    def test_a_record_that_is_not_scored_stops_the_replay(self):
        def mutate(log):
            self._search_records(log)[2]["outcome"] = "REFUSED"
        self._holds(mutate, "not SCORED")

    def test_a_baseline_that_measured_something(self):
        def mutate(log):
            self._set_readout(log["loop_records"][0], FAB(1 << 3))
        self._holds(mutate, "a baseline's readout is not all-zero")

    def test_a_record_that_served_no_readout(self):
        def mutate(log):
            del self._search_records(log)[1]["evidence"]["score"]["functional_readout"]
        self._holds(mutate, "no six-word functional_readout was served")

    def test_a_record_that_served_no_scores(self):
        def mutate(log):
            del self._search_records(log)[1]["evidence"]["score"]["scores"]
        self._holds(mutate, "serves no six per-LUT scores")

    def test_records_that_end_before_the_closing_baseline(self):
        self._holds(lambda log: log["loop_records"].pop(), "the order requires")

    # -------------------------------------------------- the prediction and the primary
    def test_a_run_that_does_not_reproduce_the_predicted_champion(self):
        pred = copy.deepcopy(PREDICTION)
        pred["pairs"][1]["runs"]["B"]["champion_holdout"] += 1
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, pred, consts=CONSTS, common=False)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("champion_holdout" in x for x in res["findings"]), res["findings"][:4])

    def test_a_run_that_does_not_reproduce_the_predicted_best(self):
        pred = copy.deepcopy(PREDICTION)
        pred["pairs"][0]["runs"]["A"]["best_train"] += 1
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, pred, consts=CONSTS, common=False)
        self.assertTrue(any("best_train" in x for x in res["findings"]), res["findings"][:4])

    def test_a_run_that_does_not_reproduce_the_predicted_moves(self):
        pred = copy.deepcopy(PREDICTION)
        pred["pairs"][2]["runs"]["A"]["moves_sha256"] = "0" * 64
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, pred, consts=CONSTS, common=False)
        self.assertTrue(any("moves_sha256" in x for x in res["findings"]), res["findings"][:4])

    def test_a_run_that_does_not_reproduce_the_predicted_primary(self):
        pred = copy.deepcopy(PREDICTION)
        pred["deltas"] = [-9] * PAIRS
        pred["predicted_primary"] = bp.decision(pred["deltas"])
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, pred, consts=CONSTS, common=False)
        self.assertTrue(any("deltas are not the preregistered" in x for x in res["findings"]), res["findings"][:4])
        self.assertTrue(any("is not the preregistered" in x for x in res["findings"]), res["findings"][:4])

    def test_a_partial_run_computes_no_primary(self):
        res = judge([modelled_log(0, 2)])
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("no primary is computed from a partial run" in x for x in res["findings"]),
                        res["findings"][:4])
        self.assertNotIn("primary", res)
        self.assertNotIn("fitness_sequence_sha256", res)

    def test_a_diverged_replay_claims_no_metrics(self):
        def mutate(log):
            self._search_records(log)[4]["search"]["state_sha256"] = "1" * 64
        res = self._judge(mutate)
        self.assertNotIn("primary", res)
        self.assertNotIn("deltas", res)


class Refusals(unittest.TestCase):
    """Inputs that are not a run this module can adjudicate at all — not a verdict on a board."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(0, PAIRS)

    def _refused(self, logs, plan, prediction, needle):
        res = badj.adjudicate(logs, plan, prediction, consts=CONSTS, common=False)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"][:160])
        self.assertIn(needle, res["refusal"])

    def test_no_session_at_all(self):
        self._refused([], PLAN, PREDICTION, "no session log")

    def test_a_plan_without_the_frozen_experiment(self):
        for key in ("budget_per_arm", "fitness", "pairs", "seed_derivation", "map"):
            with self.subTest(key=key):
                plan = {k: v for k, v in PLAN.items() if k != key}
                self._refused([copy.deepcopy(self.base)], plan, PREDICTION, key)

    def test_a_plan_whose_seed_derivation_names_no_master_seed(self):
        plan = copy.deepcopy(PLAN)
        plan["seed_derivation"] = {}
        self._refused([copy.deepcopy(self.base)], plan, PREDICTION, "no master_seed")

    def test_a_document_that_is_not_the_prediction(self):
        self._refused([copy.deepcopy(self.base)], PLAN, {"schema": "something_else"}, "not a b2_prediction")

    def test_a_prediction_for_another_experiment(self):
        for key in ("fitness", "budget_per_arm"):
            with self.subTest(key=key):
                pred = copy.deepcopy(PREDICTION)
                pred[key] = "F3" if key == "fitness" else 601
                self._refused([copy.deepcopy(self.base)], PLAN, pred, f"the prediction's {key}")

    def test_two_sessions_claiming_the_same_pair(self):
        self._refused([modelled_log(0, 2), modelled_log(1, 2)], PLAN, PREDICTION, "claimed by two sessions")

    def test_a_session_whose_identity_declares_no_slice(self):
        log = copy.deepcopy(self.base)
        log["app_identity"].pop("pair_first")
        self._refused([log], PLAN, PREDICTION, "declares the slice")

    def test_a_session_without_an_identity(self):
        log = copy.deepcopy(self.base)
        log.pop("app_identity")
        self._refused([log], PLAN, PREDICTION, "no app_identity object")


if __name__ == "__main__":
    unittest.main()
