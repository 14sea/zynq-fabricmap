"""b3/host/b3_adjudicate.py — the adjudicator must reproduce a correct run from the SERVED readouts
in all three arms — the O arm's cartographer included, from deltas recomputed from the served
parent and child readouts — and refuse or hold every way a board could deviate from the algorithm,
contradict its own measurement, or fail to reproduce the prediction.

The fixture is a modelled session: `b3_session.run_context` drives the reference over the fabric
model, and each record is given the readout that model would have measured for its genome and the
PL scorer's additive counts over it. That is the model standing in for a board **in the fixture
only** — the adjudicator itself never computes a readout. The negative cases exploit exactly that:
a readout is tampered with while its record's self-report is left alone (and the reverse), which a
model-driven adjudicator would wave through; a delta is tampered with in the record AND the
prediction, so only a recomputation from the served bytes can see it.

The instrument's common envelope is not part of these fixtures (`common=False` throughout).
"""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_adjudicate as badj  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_gate as b3g  # noqa: E402
import b3_online_arm as oa  # noqa: E402
import b3_online_map as om  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_session as bsess  # noqa: E402
import b3_test_fixtures as fx  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
SELF_MAP = bmaps.load_self_map()
VIEW = bmaps.MapView(SELF_MAP, bl.train_vectors())
MAP_SHA = bmaps.sha256_of(SELF_MAP)
CONSTS = json.loads(bl.CARRIER_CONSTANTS.read_text())
BUDGET, PAIRS = 12, 3                      # 12 = one full generation of 8 and a short one of 4; three pairs = RFO, FOR, ORF
SEEDS = [(1000, 5000), (1001, 5001), (1002, 5002)]
MASTER = 716169644


def make_plan(budget=BUDGET, pairs=PAIRS, session="B3") -> dict:
    return {"schema": "b3_plan", "schema_version": pl.SCHEMA_VERSION, "lifecycle": pl.LIFECYCLE, "session": session,
            "fitness": "F1", "budget_per_arm": budget, "pairs": pairs, "seed_derivation": {"master_seed": MASTER},
            "map": {"sha256": MAP_SHA}, "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST}


PLAN = make_plan()
PRED = pl.build_prediction("F1", BUDGET, SEEDS)


def modelled_log(plan, pred, pair_first: int, pair_count: int, fabric=FAB, truth=TRUTH, masks=MASKS) -> dict:
    """One session as a correct board would have written it: the reference's candidates, each with
    the readout the fabric model would have measured for that genome and the scorer's counts."""
    ctx = brec.context_from(plan, pred, pair_first, pair_count)
    s = bsess.run_context(ctx, fabric, VIEW, truth, masks)
    log = fx.run_log(ctx, s)
    for rec, c in zip(log["loop_records"], s.candidates):
        tables = fabric(c.genome)
        rec["evidence"] = {"score": {"functional_readout": [f"{t:016x}" for t in tables], "scores": badj.additive_scores(tables, CONSTS),
                                     "hw_candidate_commit": hashlib.sha256(bc.genome_to_hex(c.genome).encode()).hexdigest(),
                                     "heartbeat": {"before": c.seq, "after": c.seq + 1}}}
    return log


def consistent(pred: dict) -> dict:
    """Re-derive a prediction's own accounting after one of its values is changed, so the document
    stays VALID and merely DISAGREES with the run."""
    for e in pred["pairs"]:
        o = e["runs"]["O"]
        o["ledger_sha256"] = om.canonical_sha256(o["ledger"])
        o["ledger_entries"] = len(o["ledger"])
        e["delta1_O_minus_R"] = o["best_train"] - e["runs"]["R"]["best_train"]
        e["delta2_O_minus_endtoend_F"] = o["best_train"] - e["runs"]["F"]["end_to_end_at_budget"]
    pred["deltas1"] = [e["delta1_O_minus_R"] for e in pred["pairs"]]
    pred["deltas2"] = [e["delta2_O_minus_endtoend_F"] for e in pred["pairs"]]
    pred["predicted_primary"] = pl.decision(pred["deltas1"], "online > random-safe")
    pred["secondary_outcome"] = pl.secondary_report(pred["deltas2"])
    return pred


def judge(logs, plan=PLAN, prediction=PRED, scope="run") -> dict:
    return badj.adjudicate(logs, plan, prediction, consts=CONSTS, common=False, scope=scope)


def search_records(log, arm=None, pair=None):
    return [r for r in log["loop_records"] if isinstance(r.get("search"), dict) and r["search"]["holdout"] is None
            and (arm is None or r["arm"] == arm) and (pair is None or r["search"]["pair"] == pair)]


def holdout_records(log, arm=None, pair=None):
    return [r for r in log["loop_records"] if isinstance(r.get("search"), dict) and r["search"]["holdout"] is not None
            and (arm is None or r["arm"] == arm) and (pair is None or r["search"]["pair"] == pair)]


def set_readout(rec, tables):
    rec["evidence"]["score"]["functional_readout"] = [f"{t:016x}" for t in tables]
    rec["evidence"]["score"]["scores"] = badj.additive_scores(tables, CONSTS)


def readout(rec) -> list[int]:
    return [int(w, 16) for w in rec["evidence"]["score"]["functional_readout"]]


def landscape(pair: int) -> bl.Landscape:
    return bl.Landscape("F1", SEEDS[pair][0], masks=MASKS, truth=TRUTH)


def readout_with_another_train_fitness(rec, want: int) -> list[int]:
    land = landscape(rec["search"]["pair"])
    base = int(rec["genome"], 16)
    for i in range(bc.N):
        tables = FAB(base ^ (1 << i))
        if land.train_fitness(tables) != want:
            return tables
    raise AssertionError("no neighbouring genome measures a different train F1")


METRIC_KEYS = ("primary", "secondary_outcome", "deltas1", "deltas2", "fitness_sequence_sha256", "fitness_sequence_length")


def prediction_from_log(pred: dict, log: dict) -> dict:
    """A prediction that expects exactly what a (modelled) board wrote — every value copied from the
    records, the online map rendered from a cartographer replayed over the records' ledger — for a
    fixture whose fabric the plan tool would refuse to predict (a test seam only)."""
    out = copy.deepcopy(pred)
    seq: list[int] = []
    for e in out["pairs"]:
        r = e["pair"]
        for a in "RFO":
            arm = brec.ARM_WIRE[a]
            se, ho = search_records(log, arm, r), holdout_records(log, arm, r)[0]
            run = e["runs"][a]
            run["best_train"] = json.loads(json.dumps(se[-1]["search"]["best"]))
            run["champion_holdout"] = ho["search"]["holdout"]
            run["column_moves"] = se[-1]["search"]["column_moves"]
            run["champion_genome_sha256"] = hashlib.sha256(ho["genome"].encode()).hexdigest()
            if a == "O":
                ledger = [x["search"]["ledger"] for x in se]
                carto, f = oa.replay_cartographer_only(ledger)
                assert not f, f
                doc = om.render(carto, {"landscape_seed": e["landscape_seed"], "operator_seed": e["operator_seed"], "fitness": "F1", "budget": BUDGET}, ledger)
                run.update({"ledger": ledger, "moves_sha256": pl.sha256_json([[x["parent_born"], x["move_kind"], x["intervention"], x["fitness"]] for x in ledger]),
                            "decoded_final": len(carto.decoded), "map_version_final": carto.version, "anomalies": carto.anomalies,
                            "wrong_decodes": om.accuracy(doc, TRUTH)["wrong"], "final_state_sha256": se[-1]["search"]["state_sha256"],
                            "online_map_sha256": om.canonical_sha256(doc)})
        for a in bsess.arm_order(r):
            seq.extend(x["search"]["fitness"] for x in search_records(log, brec.ARM_WIRE[a], r))
        for a in bsess.arm_order(r):
            seq.append(holdout_records(log, brec.ARM_WIRE[a], r)[0]["search"]["holdout"])
    out["fitness_sequence_sha256"] = pl.sha256_json(seq)
    out["fitness_sequence_length"] = len(seq)
    return consistent(out)


class Accepts(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.whole = modelled_log(PLAN, PRED, 0, PAIRS)
        cls.split = [modelled_log(PLAN, PRED, 0, 2), modelled_log(PLAN, PRED, 2, 1)]

    def test_a_correct_single_session_run_passes_with_the_predicted_metrics(self):
        res = judge([self.whole])
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual((res["kills"], res["session"], res["scope"]), ([], "B3", "run"))
        self.assertEqual(res["deltas1"], PRED["deltas1"])
        self.assertEqual(res["deltas2"], PRED["deltas2"])
        self.assertEqual(res["primary"], PRED["predicted_primary"])
        self.assertEqual(res["secondary_outcome"], PRED["secondary_outcome"])
        self.assertEqual(res["fitness_sequence_sha256"], PRED["fitness_sequence_sha256"])
        self.assertEqual(res["fitness_sequence_length"], PRED["fitness_sequence_length"])
        self.assertEqual(res["replay"], {"records_replayed": PAIRS * (3 * BUDGET + 3), "pairs": [0, 1, 2]})
        self.assertEqual(res["measurement"], {"records_checked": PAIRS * (3 * BUDGET + 3), "readouts_served": PAIRS * (3 * BUDGET + 3) + 2})
        for r in range(PAIRS):
            o = PRED["pairs"][r]["runs"]["O"]
            self.assertEqual(res["online_maps"][str(r)], {"decoded": o["decoded_final"], "map_version": o["map_version_final"],
                                                          "anomalies": 0, "sha256": o["online_map_sha256"]})
        self.assertEqual(res["pair_seeds"], [list(x) for x in SEEDS])
        self.assertNotIn("qualification", res)

    def test_the_same_run_split_across_sessions_gives_the_same_verdict(self):
        res = judge(self.split)
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["deltas1"], PRED["deltas1"])
        self.assertEqual(res["fitness_sequence_sha256"], PRED["fitness_sequence_sha256"])
        self.assertEqual([s["pair_count"] for s in res["sessions"]], [2, 1])

    def test_the_sessions_are_ordered_by_their_slices_not_by_the_caller(self):
        res = judge(list(reversed(self.split)))
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual([s["pair_first"] for s in res["sessions"]], [0, 2])

    def test_the_adjudicator_never_produces_a_readout_of_its_own(self):
        def refuse(*a, **k):
            raise AssertionError("the adjudicator reached for the fabric model")
        with mock.patch.object(bs, "ModelFabric", refuse), mock.patch.object(bm, "Fabric", refuse):
            res = judge([self.whole])
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["fitness_sequence_sha256"], PRED["fitness_sequence_sha256"])

    def test_the_result_states_what_it_did_not_check(self):
        res = judge([self.whole])
        for what in ("manifest pins", "B2 authority", "instrument rate / deadline / CRC", "evidence exports", "ruling binding"):
            self.assertTrue(any(what in x for x in res["not_checked_here"]), what)


class Scope(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.first = modelled_log(PLAN, PRED, 0, 2)
        cls.whole = modelled_log(PLAN, PRED, 0, PAIRS)

    def test_a_session_of_a_longer_run_is_not_held_for_being_partial(self):
        res = judge([self.first], scope="session")
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["replay"]["pairs"], [0, 1])

    def test_a_session_scope_never_claims_the_experiments_verdict(self):
        for logs in ([self.first], [self.whole]):
            res = judge(logs, scope="session")
            self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
            for k in METRIC_KEYS:
                self.assertNotIn(k, res)

    def test_a_session_scope_still_compares_its_own_pairs_with_the_prediction(self):
        pred = consistent(copy.deepcopy(PRED))
        pred["pairs"][1]["runs"]["O"]["best_train"] += 1
        pred = consistent(pred)
        res = judge([self.first], PLAN, pred, scope="session")
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("pair 1 arm O: best_train is" in x for x in res["findings"]), res["findings"][:4])

    def test_a_partial_run_computes_no_primary(self):
        res = judge([self.first])
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("no primary is computed from a partial run" in x for x in res["findings"]), res["findings"][:4])
        for k in METRIC_KEYS:
            self.assertNotIn(k, res)

    def test_an_unknown_scope_is_refused(self):
        res = judge([self.whole], scope="pair")
        self.assertTrue(res["outcome"].startswith("REFUSED: scope 'pair'"), res["outcome"])

    def test_the_run_scope_is_the_default(self):
        self.assertEqual(badj.adjudicate([self.whole], PLAN, PRED, consts=CONSTS, common=False)["scope"], "run")


class Qualification(unittest.TestCase):
    """B3Q through the PRODUCTION plan and prediction builders: 123 fitness values, 40 ledger entries,
    two baselines verified against its own prediction; never a primary."""

    @classmethod
    def setUpClass(cls):
        cls.saved = b3g.THRESHOLDS["H2_bootstrap_experiments"]
        b3g.THRESHOLDS["H2_bootstrap_experiments"] = 100
        cls.tmp = Path(tempfile.mkdtemp())
        gate = fx.write_gate_fixture(cls.tmp / "gate_2")
        g = pl.gate_inputs(gate)
        _m, seeds, _s, _e = pl.session_seeds(g["pairs"], gate)
        cls.qplan = pl.build_qualification_plan("F1", MAP_SHA, seeds, gate)
        cls.qpred = pl.build_qualification_prediction("F1", MAP_SHA, seeds, gate)
        cls.log = modelled_log(cls.qplan, cls.qpred, 0, 1)

    @classmethod
    def tearDownClass(cls):
        b3g.THRESHOLDS["H2_bootstrap_experiments"] = cls.saved
        shutil.rmtree(cls.tmp, True)

    def test_a_correct_qualification_session_passes_without_a_primary(self):
        for scope in ("run", "session"):
            res = judge([self.log], self.qplan, self.qpred, scope=scope)
            self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
            self.assertEqual(res["session"], "B3Q")
            self.assertEqual(res["qualification"], {"fitness_values": 123, "ledger_entries": 40, "baselines": 2,
                                                    "fitness_sequence_sha256": self.qpred["fitness_sequence_sha256"]})
            self.assertEqual(res["replay"]["records_replayed"], 123)
            self.assertEqual(len(self.log["loop_records"]), 125)
            for k in METRIC_KEYS:
                self.assertNotIn(k, res)

    def test_a_qualification_contradiction_is_a_kill(self):
        log = copy.deepcopy(self.log)
        rec = search_records(log, "online")[3]
        rec["search"]["fitness"] = rec["search"]["ledger"]["fitness"] = (rec["search"]["fitness"] + 1) % 41
        res = judge([log], self.qplan, self.qpred)
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])

    def test_a_b3_plan_that_calls_itself_b3q_is_refused(self):
        plan = dict(PLAN, session="B3Q")
        res = judge([modelled_log(PLAN, PRED, 0, PAIRS)], plan, PRED)
        self.assertTrue(res["outcome"].startswith("REFUSED: a B3Q plan has 1 pair"), res["outcome"])


class Kills(unittest.TestCase):
    """A served readout contradicting a self-report is a KILL, per record."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(PLAN, PRED, 0, PAIRS)

    def _judge(self, mutate, pred=PRED) -> dict:
        log = copy.deepcopy(self.base)
        mutate(log)
        return judge([log], PLAN, pred)

    def _kills(self, mutate, needle: str, pred=PRED) -> dict:
        res = self._judge(mutate, pred)
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])
        self.assertTrue(any(needle in x for x in res["kills"]), f"{needle!r} not in {res['kills'][:3]}")
        return res

    def test_a_tampered_readout_contradicts_the_self_reported_fitness(self):
        for arm in ("random_safe", "map_guided", "online"):
            with self.subTest(arm=arm):
                def mutate(log, arm=arm):
                    rec = search_records(log, arm)[2]
                    set_readout(rec, readout_with_another_train_fitness(rec, rec["search"]["fitness"]))
                self._kills(mutate, "is not")

    def test_a_tampered_fitness_contradicts_the_served_readout(self):
        def mutate(log):
            rec = search_records(log, "random_safe")[1]
            rec["search"]["fitness"] = (rec["search"]["fitness"] + 1) % 41
        self._kills(mutate, "the train F1 of the readout the board served for it")

    def test_a_tampered_holdout_value_contradicts_its_re_measurement(self):
        def mutate(log):
            rec = holdout_records(log, "online")[0]
            rec["search"]["holdout"] = (rec["search"]["holdout"] + 1) % 25
        self._kills(mutate, "the holdout F1 of the readout the board served for it")

    def test_a_tampered_additive_score_contradicts_the_same_readout(self):
        def mutate(log):
            rec = search_records(log, "map_guided")[0]
            rec["evidence"]["score"]["scores"][2] += 1
        self._kills(mutate, "the PL's additive scores")

    def test_a_behaviour_delta_the_served_readouts_contradict(self):
        """The record's delta and the prediction's entry are changed TOGETHER, so the record layer
        accepts them; only a recomputation from the served child and parent readouts can see it."""
        def mutate(log):
            rec = search_records(log, "online", 0)[2]
            d = rec["search"]["ledger"]["behaviour_delta"]
            d[0] = [d[0][0], (d[0][1] + 1) % 64]
        pred = copy.deepcopy(PRED)
        e = pred["pairs"][0]["runs"]["O"]["ledger"][2]
        e["behaviour_delta"][0] = [e["behaviour_delta"][0][0], (e["behaviour_delta"][0][1] + 1) % 64]
        res = self._kills(mutate, "behaviour_delta", consistent(pred))
        self.assertTrue(any("is not the child ⊕ parent readout the board served" in x for x in res["kills"]), res["kills"][:2])
        for k in METRIC_KEYS:
            self.assertNotIn(k, res)

    def test_a_readout_bit_in_a_holdout_column_leaves_the_fitness_but_not_the_delta(self):
        """A readout tampered where the train fitness and the scores cannot see it: the self-reported
        fitness still verifies, the behaviour delta no longer does — recomputed from readouts, not
        replayed from the board's report."""
        v = bl.holdout_vectors()[0]
        def mutate(log):
            rec = search_records(log, "online", 1)[0]
            tables = readout(rec)
            tables[1] ^= 1 << v
            words = [f"{t:016x}" for t in tables]
            rec["evidence"]["score"]["functional_readout"] = words
            self.assertEqual(badj.additive_scores(tables, CONSTS), rec["evidence"]["score"]["scores"])
        res = self._kills(mutate, "behaviour_delta")
        self.assertFalse(any("the train F1 of the readout" in x for x in res["kills"]), res["kills"][:3])

    def test_every_contradicting_record_is_named_not_only_the_first(self):
        def mutate(log):
            for rec in search_records(log, "random_safe")[:3]:
                rec["search"]["fitness"] = (rec["search"]["fitness"] + 1) % 41
        res = self._kills(mutate, "the train F1")
        self.assertEqual(len([x for x in res["kills"] if "the train F1" in x]), 3)


class Holds(unittest.TestCase):
    """Every deviation from the algorithm is ONE named finding (a HOLD), the replay stops there,
    and no metric is published after it."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(PLAN, PRED, 0, PAIRS)

    def _judge(self, mutate, pred=PRED) -> dict:
        log = copy.deepcopy(self.base)
        mutate(log)
        return judge([log], PLAN, pred)

    def _holds(self, mutate, needle: str, pred=PRED) -> dict:
        res = self._judge(mutate, pred)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any(needle in x for x in res["findings"]), f"{needle!r} not in {res['findings'][:4]}")
        self.assertEqual(res["kills"], [])
        return res

    def _entry_and_prediction(self, pair, n, mutate_entry) -> tuple:
        """Tamper an O ledger entry in the record AND in the prediction (so the record layer accepts
        it): only the replay's own cartographer can then refuse it."""
        def mutate(log):
            mutate_entry(search_records(log, "online", pair)[n]["search"]["ledger"])
        pred = copy.deepcopy(PRED)
        mutate_entry(pred["pairs"][pair]["runs"]["O"]["ledger"][n])
        return mutate, consistent(pred)

    # -- the search replay (all three arms)
    def test_a_genome_the_reference_would_not_have_proposed(self):
        for arm in ("random_safe", "map_guided", "online"):
            with self.subTest(arm=arm):
                def mutate(log, arm=arm):
                    rec = search_records(log, arm)[3]
                    rec["genome"] = bc.genome_to_hex(int(rec["genome"], 16) ^ 1)
                self._holds(mutate, "a genome the reference would not have proposed")

    def test_a_move_the_reference_did_not_draw(self):
        def mutate(log):
            rec = search_records(log, "online")[1]
            rec["search"]["move"]["kind"] = "column" if rec["search"]["move"]["kind"] == "random" else "random"
            rec["search"]["ledger"]["move_kind"] = rec["search"]["move"]["kind"]
        pred = copy.deepcopy(PRED)
        e = pred["pairs"][0]["runs"]["O"]["ledger"][1]
        e["move_kind"] = "column" if e["move_kind"] == "random" else "random"
        self._holds(mutate, "is not the reference's", consistent(pred))

    def test_a_parent_the_reference_did_not_draw(self):
        def mutate(log):
            rec = search_records(log, "random_safe")[2]
            rec["search"]["parent_born"] = (rec["search"]["parent_born"] + 1) % 4
        self._holds(mutate, "the board names parent born")

    def test_a_commitment_that_is_not_the_replayed_state(self):
        for arm in ("random_safe", "online"):
            with self.subTest(arm=arm):
                def mutate(log, arm=arm):
                    search_records(log, arm)[4]["search"]["state_sha256"] = "1" * 64
                res = self._holds(mutate, "the block's state_sha256 is")
                for k in METRIC_KEYS:
                    self.assertNotIn(k, res)

    def test_a_population_the_selection_would_not_have_left(self):
        def mutate(log):
            rec = search_records(log, "map_guided")[7]           # closes the first generation
            rec["search"]["population"][0]["born"] = 99
        self._holds(mutate, "the block's population is")

    def test_a_best_so_far_that_went_its_own_way(self):
        def mutate(log):                                       # the run's last search record and its holdout: monotone for the record layer
            search_records(log, "online", 1)[-1]["search"]["best"] += 1
            holdout_records(log, "online", 1)[0]["search"]["best"] += 1
        self._holds(mutate, "the block's best is")

    def test_a_holdout_record_that_re_measures_something_else(self):
        def mutate(log):
            rec = holdout_records(log, "online")[0]
            rec["genome"] = bc.genome_to_hex(int(rec["genome"], 16) ^ 1)
        self._holds(mutate, "a genome that is not the champion the replayed selection left")

    def test_an_o_holdout_commitment_that_is_not_the_final_state(self):
        def mutate(log):
            holdout_records(log, "online")[1]["search"]["state_sha256"] = holdout_records(log, "online")[0]["search"]["state_sha256"]
        self._holds(mutate, "state_sha256")

    # -- the ledger replay (arm O): the record and the prediction tampered together
    def test_a_decode_the_reference_cartographer_did_not_make(self):
        n = next(i for i, e in enumerate(PRED["pairs"][0]["runs"]["O"]["ledger"]) if e["decoded"])
        def tamper(e):
            e["decoded"] = e["decoded"] + [[291, 5, 63]]
        mutate, pred = self._entry_and_prediction(0, n, tamper)
        res = self._holds(mutate, "the ledger's decoded is", pred)
        self.assertTrue(any("ledger replay failed" in x for x in res["findings"]), res["findings"][:3])
        self.assertNotIn("online_maps", res)

    def test_a_decoded_position_the_reference_did_not_decode_is_a_hold_not_a_kill(self):
        """A wrong decode the replay does NOT reproduce: the image is at fault (a HOLD), never the
        certificate."""
        n = next(i for i, e in enumerate(PRED["pairs"][0]["runs"]["O"]["ledger"]) if e["decoded"])
        def tamper(e):
            i, k, v = e["decoded"][0]
            e["decoded"][0] = [i, k, (v + 1) % 64]
        mutate, pred = self._entry_and_prediction(0, n, tamper)
        res = self._holds(mutate, "the ledger's decoded is", pred)
        self.assertFalse(any("wrong decode" in x for x in res["findings"] + res["kills"]))

    def test_a_map_version_or_anomaly_the_record_layer_names_is_never_replayed(self):
        """The record layer's continuity rules name a version jump or an anomaly first, and the
        stateful replay does not run over a session it named."""
        for key, needle in (("map_version_after", "the version bumps only on a decode"), ("anomalies", "an anomaly — the board's cartographer refused")):
            with self.subTest(key=key):
                def mutate(log, key=key):
                    e = search_records(log, "online", 2)[BUDGET - 1]["search"]["ledger"]
                    e[key] += 1
                res = self._holds(mutate, needle)
                self.assertIn("not_run", res["replay"])

    def test_the_replays_own_ledger_guards_do_not_rest_on_the_record_layer(self):
        """With the record layer bypassed (a test seam only), the reference cartographer itself
        refuses a map version it did not reach and an anomaly it did not count."""
        for key, needle in (("map_version_after", "the ledger's map_version_after is"), ("anomalies", "the ledger's anomalies is")):
            with self.subTest(key=key):
                def mutate(log, key=key):
                    search_records(log, "online", 1)[0]["search"]["ledger"][key] += 1
                with mock.patch.object(brec, "validate_run_log", lambda *a, **k: []):
                    res = self._holds(mutate, needle)
                self.assertTrue(any("ledger replay failed" in x for x in res["findings"]), res["findings"][:3])

    # -- the shape of the run
    def test_a_record_that_is_not_scored_stops_before_any_replay(self):
        def mutate(log):
            rec = search_records(log, "map_guided")[5]
            rec.pop("search")
            rec["outcome"] = "REFUSED_BY_GATE"
        res = self._holds(mutate, "ran 11 evaluations, not 12")
        self.assertIn("not_run", res["replay"])

    def test_a_baseline_that_measured_something(self):
        def mutate(log):
            set_readout(log["loop_records"][0], [1, 0, 0, 0, 0, 0])
        res = self._judge(mutate)
        self.assertTrue(any("a baseline's readout is not all-zero" in x for x in res["findings"]), res["findings"][:4])
        self.assertNotEqual(res["outcome"], "PASS")

    def test_a_baseline_that_is_not_the_blank_genome(self):
        def mutate(log):
            log["loop_records"][-1]["genome"] = bc.genome_to_hex(1)
        self._holds(mutate, "the closing baseline's genome is")

    def test_a_record_that_served_no_readout(self):
        def mutate(log):
            search_records(log, "online")[0]["evidence"]["score"].pop("functional_readout")
        self._holds(mutate, "no six-word functional_readout was served")

    # -- the prediction
    def test_a_run_that_does_not_reproduce_a_predicted_value(self):
        for arm, key in (("R", "best_train"), ("F", "end_to_end_at_budget"), ("O", "decoded_final"), ("O", "online_map_sha256"),
                         ("F", "champion_genome_sha256"), ("R", "moves_sha256"), ("O", "moves_sha256")):
            with self.subTest(arm=arm, key=key):
                pred = copy.deepcopy(PRED)
                run = pred["pairs"][2]["runs"][arm]
                run[key] = run[key] + 1 if isinstance(run[key], int) else "f" * 64
                res = self._holds(lambda log: None, f"pair 2 arm {arm}: {key} is", consistent(pred))
                if key in ("best_train", "end_to_end_at_budget"):
                    self.assertTrue(any("not the preregistered" in x for x in res["findings"]), res["findings"][:6])

    def test_a_predicted_final_commitment_the_run_does_not_reproduce_is_named_at_the_record_layer(self):
        pred = copy.deepcopy(PRED)
        pred["pairs"][2]["runs"]["O"]["final_state_sha256"] = "f" * 64
        res = judge([self.base], PLAN, consistent(pred))
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("is not the predicted search + cartographer commitment" in x for x in res["findings"]), res["findings"][:3])
        self.assertIn("not_run", res["replay"])

    def test_a_run_that_does_not_reproduce_the_predicted_ledger(self):
        pred = copy.deepcopy(PRED)
        pred["pairs"][1]["runs"]["O"]["ledger"][3]["fitness"] += 1
        res = judge([self.base], PLAN, consistent(pred))
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("not the predicted entry" in x for x in res["findings"]), res["findings"][:3])
        self.assertIn("not_run", res["replay"], "a session the record layer named is never replayed")

    def test_a_diverged_replay_claims_no_metrics(self):
        def mutate(log):
            search_records(log, "random_safe")[4]["search"]["state_sha256"] = "1" * 64
        res = self._judge(mutate)
        for k in METRIC_KEYS + ("online_maps",):
            self.assertNotIn(k, res)


class DecodeAudit(unittest.TestCase):
    """The decode audit over the REPLAYED cartographer (preregistration §5 item 2): a wrong decode
    the reference reproduced from verified readouts is a KILL (a certificate / fabric / model
    contradiction); an anomaly it reproduces is a HOLD. Both fixtures make the board AND the
    prediction follow a fabric the certificate does not describe, so every record verifies and the
    replay agrees — only the audit against the certificate can object."""

    @staticmethod
    def _free_holdout_position() -> tuple[int, int]:
        used = {tuple(v) for v in TRUTH["mapping"].values()}
        for v in bl.holdout_vectors():
            for k in range(bl.LUTS):
                if (k, v) not in used:
                    return k, v
        raise AssertionError("no free holdout position")

    def _prediction_under(self, fabric_cls, truth):
        with mock.patch.object(bs, "ModelFabric", fabric_cls), mock.patch.object(bm, "truth_mapping", lambda *a, **k: truth):
            pl._PREDICT_CACHE.clear()
            pred = pl.build_prediction("F1", BUDGET, SEEDS)
        pl._PREDICT_CACHE.clear()
        return pred

    def test_a_wrong_decode_reproduced_from_verified_readouts_is_a_kill(self):
        base_pred = PRED
        decoded = [i for e in base_pred["pairs"][0]["runs"]["O"]["ledger"] for i, _, _ in e["decoded"]]
        self.assertTrue(decoded, "the fixture decodes nothing in pair 0")
        for i in decoded:
            j = next(a for a in TRUTH["mapping"] if a != i)
            swapped = {"mapping": dict(TRUTH["mapping"])}
            swapped["mapping"][i], swapped["mapping"][j] = TRUTH["mapping"][j], TRUTH["mapping"][i]
            fab = bs.ModelFabric(swapped)
            pred = self._prediction_under(lambda t, _f=fab: _f, swapped)
            if not any(x in (i, j) for e in pred["pairs"][0]["runs"]["O"]["ledger"] for x, _, _ in e["decoded"]):
                continue
            log = modelled_log(PLAN, pred, 0, PAIRS, fabric=fab, truth=swapped, masks=bl.universe_mask(swapped))
            res = judge([log], PLAN, pred)
            self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:200])
            self.assertTrue(any("wrong decode reproduced from verified readouts" in x and "certificate / fabric / model contradiction" in x
                                for x in res["kills"]), res["kills"][:2])
            self.assertEqual(res["replay"]["records_replayed"], PAIRS * (3 * BUDGET + 3), "the replay agreed record for record")
            return
        self.fail("no swap produced a decode of a swapped address")

    def test_a_reproducible_anomaly_is_a_hold(self):
        k_x, v_x = self._free_holdout_position()

        class ParityFabric(bs.ModelFabric):
            """Additive, plus one position outside the universe (in a holdout column: the train fitness and
            the scores cannot see it) that toggles with the parity of the genome — every single-bit
            specimen then shows two toggled positions and is refused by the cartographer."""
            def __call__(self, genome):
                t = list(super().__call__(genome))
                if bin(genome).count("1") % 2:
                    t[k_x] ^= 1 << v_x
                return t

            def toggle(self, tables, bits):
                t = list(super().toggle(tables, bits))
                if len(bits) % 2:
                    t[k_x] ^= 1 << v_x
                return t
        fab = ParityFabric(TRUTH)
        # the plan tool refuses to predict a map with anomalies (b3_plan.predict raises), so the prediction
        # that "expects" the parity board is synthesised from that board's own records
        log = modelled_log(PLAN, PRED, 0, PAIRS, fabric=fab)
        pred = prediction_from_log(PRED, log)
        self.assertTrue(any(e["anomalies"] for r in pred["pairs"] for e in r["runs"]["O"]["ledger"]), "the parity fabric produced no anomaly")
        # (a) as adjudicated: the record layer names every anomaly the board reports, the replay does not run — a HOLD, never a KILL
        res = judge([log], PLAN, pred)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:200])
        self.assertEqual(res["kills"], [])
        self.assertTrue(any("an anomaly — the board's cartographer refused this specimen" in x for x in res["findings"]), res["findings"][:4])
        self.assertIn("not_run", res["replay"])
        # (b) the audit's own classification, with the record layer bypassed (a test seam only): the reference cartographer
        # reproduces the anomalies from the served readouts and the audit names them as a finding about the fabric — a HOLD
        with mock.patch.object(brec, "validate_run_log", lambda *a, **k: []):
            res = judge([log], PLAN, pred)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:200])
        self.assertEqual(res["kills"], [])
        self.assertTrue(any("anomaly(ies) reproduced by the reference cartographer" in x for x in res["findings"]), res["findings"][:4])
        self.assertEqual(res["replay"]["records_replayed"], PAIRS * (3 * BUDGET + 3))
        self.assertTrue(all(res["online_maps"][str(r)]["anomalies"] == pred["pairs"][r]["runs"]["O"]["anomalies"] for r in range(PAIRS)))


class Malformed(unittest.TestCase):
    """A plan, prediction or record document that is not the shape this module reads is REFUSED
    by name — never a finding about a board, never a Python exception."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(PLAN, PRED, 0, PAIRS)

    def _refused(self, logs=None, plan=PLAN, pred=PRED, needle: str = "", scope="run") -> dict:
        try:
            res = judge(logs if logs is not None else [self.base], plan, pred, scope)
        except Exception as exc:
            self.fail(f"{type(exc).__name__}: {exc}")
        self.assertTrue(res["outcome"].startswith("REFUSED: "), res["outcome"][:160])
        self.assertIn(needle, res["outcome"])
        for k in METRIC_KEYS + ("replay", "measurement"):
            self.assertNotIn(k, res)
        return res

    def test_no_logs(self):
        self._refused([], needle="no session log was given")

    def test_a_session_log_that_is_not_an_object(self):
        self._refused([[]], needle="a session log is list, not a JSON object")
        self._refused([{"loop_records": []}], needle="carries no app_identity object")

    def test_records_that_are_malformed(self):
        log = copy.deepcopy(self.base); log["loop_records"] = {}
        self._refused([log], needle="loop_records is dict, not an array")
        log = copy.deepcopy(self.base); log["loop_records"][3] = 5
        self._refused([log], needle="record 4 is not a JSON object")
        log = copy.deepcopy(self.base); log["loop_records"][3]["seq"] = "4"
        self._refused([log], needle="record 4 carries seq '4'")
        log = copy.deepcopy(self.base); log.pop("loop_records")
        self._refused([log], needle="the log carries no loop_records")

    def test_two_sessions_claiming_a_pair(self):
        self._refused([self.base, modelled_log(PLAN, PRED, 2, 1)], needle="pair 2 is claimed by two sessions")

    def test_a_slice_the_identity_declares_badly(self):
        log = copy.deepcopy(self.base); log["app_identity"]["pair_count"] = 0
        self._refused([log], needle="declares the slice (0, 0)")
        log = copy.deepcopy(self.base); log["app_identity"]["pair_first"] = 3
        self._refused([log], needle="does not lie inside the experiment")

    def test_a_malformed_plan(self):
        self._refused(plan=[], needle="the plan is not a JSON object")
        self._refused(plan=dict(PLAN, schema="b2_plan"), needle="the plan's schema 'b2_plan' is not b3_plan")
        self._refused(plan=dict(PLAN, lifecycle=1), needle="not schema 2.0.0 of lifecycle 2")
        self._refused(plan=dict(PLAN, session="B2"), needle="the plan's session 'B2'")
        self._refused(plan=dict(PLAN, budget_per_arm=True), needle="budget_per_arm True is not a positive integer")
        self._refused(plan=dict(PLAN, fitness=1), needle="the plan's fitness 1 is not a string")
        self._refused(plan=dict(PLAN, fitness="F2"), needle="the plan's fitness 'F2' is not the preregistered 'F1'")
        self._refused(plan=dict(PLAN, pairs=17), needle="the plan's pairs 17 is not 1..16")
        self._refused(plan=dict(PLAN, map={"sha256": "abc"}), needle="the plan's map sha256 is not 64 lower-case hex")
        self._refused(plan=dict(PLAN, seed_derivation={"master_seed": 2 ** 32}), needle="carries no 32-bit master_seed")
        self._refused(plan=dict(PLAN, carto_version="specimen-carto-v1.0"), needle="the plan's carto_version")
        self._refused(plan=dict(PLAN, b1_map_cost=0), needle="the plan's b1_map_cost 0 is not 333")
        p = dict(PLAN); p.pop("b1_map_cost")
        self._refused(plan=p, needle="the plan carries no 'b1_map_cost'")

    def test_a_malformed_prediction(self):
        def with_(mut):
            pred = copy.deepcopy(PRED)
            mut(pred)
            return pred
        self._refused(pred={"schema": "b2_prediction"}, needle="not a b3_prediction document")
        self._refused(pred=with_(lambda p: p.__setitem__("fitness", "F2")), needle="the prediction's fitness ('F2') is not the plan's")
        self._refused(pred=with_(lambda p: p.__setitem__("budget_per_arm", 2.0)), needle="budget_per_arm (2.0) is not the plan's")
        self._refused(pred=with_(lambda p: p["pairs"].reverse()), needle="not the experiment's 0..2 exactly once in order")
        self._refused(pred=with_(lambda p: p["pairs"].pop()), needle="not the experiment's 0..2 exactly once in order")
        self._refused(pred=with_(lambda p: p["pairs"][0]["runs"].pop("O")), needle="carries no R, F and O run objects")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["R"].__setitem__("best_train", True)), needle="pair 1 arm R: best_train True is not an integer")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["R"].__setitem__("best_train", 41)), needle="pair 1 arm R: best_train 41 is outside 0..40")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["F"].__setitem__("moves_sha256", "x")), needle="pair 1 arm F: moves_sha256 'x' is not 64")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["O"].__setitem__("anomalies", -1)), needle="pair 1 arm O: anomalies -1 is not a count")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["O"]["ledger"].pop()), needle="the ledger is not 12 entries")
        self._refused(pred=with_(lambda p: p["pairs"][1]["runs"]["O"]["ledger"][0].__setitem__("fitness", 0)), needle="ledger_sha256 is not the digest of its own ledger")
        self._refused(pred=with_(lambda p: p["pairs"][1].__setitem__("delta1_O_minus_R", 99)), needle="delta1_O_minus_R does not account for its own runs")
        self._refused(pred=with_(lambda p: p.__setitem__("deltas2", [0, 0, 0])), needle="the prediction's deltas2 are not its pairs'")
        self._refused(pred=with_(lambda p: p["predicted_primary"].__setitem__("positives", 1.0)), needle="primary positives 1.0 is not a count")
        self._refused(pred=with_(lambda p: p["predicted_primary"].__setitem__("verdict", "x")), needle="not the sign test over its own deltas1")
        self._refused(pred=with_(lambda p: p["secondary_outcome"].__setitem__("mean", 0.0)), needle="not the report over its own deltas2")
        self._refused(pred=with_(lambda p: p.__setitem__("fitness_sequence_length", 117.0)), needle="fitness_sequence_length 117.0 is not the 117 values")

    def test_a_prediction_the_context_refuses_is_refused_by_name(self):
        pred = copy.deepcopy(PRED)
        pred["pairs"][2]["runs"]["O"]["ledger_schema_version"] = "1.0.0"
        self._refused(pred=pred, needle="ledger_schema_version '1.0.0' is not 1.1.0")

    def test_a_valid_prediction_that_merely_disagrees_is_a_finding_not_a_refusal(self):
        pred = copy.deepcopy(PRED)
        pred["pairs"][0]["runs"]["R"]["best_train"] += 1
        res = judge([self.base], PLAN, consistent(pred))
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])

    def test_a_contradiction_collected_before_a_record_layer_refusal_survives_it(self):
        log = copy.deepcopy(self.base)
        rec = search_records(log, "random_safe")[1]
        rec["search"]["fitness"] = (rec["search"]["fitness"] + 1) % 41
        log["app_identity"]["arms"] = "RF"                         # a record-layer finding elsewhere in the same log
        res = judge([log])
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])
        self.assertIn("not_run", res["replay"])


class CommandLine(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        (cls.tmp / "plan.json").write_text(json.dumps(PLAN))
        (cls.tmp / "prediction.json").write_text(json.dumps(PRED))
        (cls.tmp / "run_log.json").write_text(json.dumps(modelled_log(PLAN, PRED, 0, PAIRS)))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, True)

    def _run(self, *args):
        return subprocess.run([sys.executable, "-B", str(R / "b3/host/b3_adjudicate.py"), *args], capture_output=True, text=True)

    def test_a_correct_run_exits_zero_and_writes_its_result(self):
        out = self.tmp / "result.json"
        p = self._run("--run-log", str(self.tmp / "run_log.json"), "--plan", str(self.tmp / "plan.json"),
                      "--prediction", str(self.tmp / "prediction.json"), "--no-common", "--out", str(out))
        self.assertEqual(p.returncode, 0, p.stdout[-800:] + p.stderr[-800:])
        res = json.loads(out.read_text())
        self.assertEqual(res["outcome"], "PASS")
        self.assertEqual(res["primary"], PRED["predicted_primary"])
        self.assertEqual(res["inputs"], [str(self.tmp / "run_log.json")])

    def test_a_session_scope_exits_zero_without_a_primary(self):
        p = self._run("--run-log", str(self.tmp / "run_log.json"), "--plan", str(self.tmp / "plan.json"),
                      "--prediction", str(self.tmp / "prediction.json"), "--no-common", "--scope", "session")
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        self.assertNotIn("primary", json.loads(p.stdout))

    def test_a_refusal_exits_one_and_names_it(self):
        p = self._run("--run-log", str(self.tmp / "run_log.json"), "--plan", str(self.tmp / "prediction.json"),
                      "--prediction", str(self.tmp / "prediction.json"), "--no-common")
        self.assertEqual(p.returncode, 1)
        self.assertTrue(json.loads(p.stdout)["outcome"].startswith("REFUSED: the plan's schema"))

    def test_no_inputs_exits_two(self):
        self.assertEqual(self._run("--no-common").returncode, 2)


if __name__ == "__main__":
    unittest.main()
