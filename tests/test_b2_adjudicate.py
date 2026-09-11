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
import shutil
import subprocess
import sys
import tempfile
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


def consistent(pred: dict) -> dict:
    """Re-derive a prediction's own accounting after one of its values is changed, so the
    document stays VALID and merely DISAGREES with the run — the distinction between a
    malformed input and a prediction the board did not reproduce."""
    for entry in pred["pairs"]:
        entry["delta_B_minus_A"] = entry["runs"]["B"]["best_train"] - entry["runs"]["A"]["best_train"]
    pred["deltas"] = [e["delta_B_minus_A"] for e in pred["pairs"]]
    pred["predicted_primary"] = bp.decision(pred["deltas"])
    return pred


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

    def test_a_record_that_is_not_scored_is_refused_before_any_replay(self):
        def mutate(log):
            self._search_records(log)[2]["outcome"] = "REFUSED"
        res = self._judge(mutate)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("only a SCORED candidate" in x for x in res["findings"]), res["findings"][:3])
        self.assertIn("not_run", res["replay"])
        self.assertNotIn("primary", res)

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
        """The prediction stays internally valid; only the run disagrees with it."""
        pred = copy.deepcopy(PREDICTION)
        pred["pairs"][0]["runs"]["A"]["best_train"] += 1
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, consistent(pred), consts=CONSTS, common=False)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("best_train" in x for x in res["findings"]), res["findings"][:4])

    def test_a_run_that_does_not_reproduce_the_predicted_moves(self):
        pred = copy.deepcopy(PREDICTION)
        pred["pairs"][2]["runs"]["A"]["moves_sha256"] = "0" * 64
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, pred, consts=CONSTS, common=False)
        self.assertTrue(any("moves_sha256" in x for x in res["findings"]), res["findings"][:4])

    def test_a_run_that_does_not_reproduce_the_predicted_primary(self):
        pred = copy.deepcopy(PREDICTION)
        for entry in pred["pairs"]:                     # a valid prediction of the opposite sign
            entry["runs"]["A"]["best_train"] = entry["runs"]["B"]["best_train"] + 5
        res = badj.adjudicate([copy.deepcopy(self.base)], PLAN, consistent(pred), consts=CONSTS, common=False)
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


class BlankBaselines(unittest.TestCase):
    """Both brackets must be the blank genome — with the instrument's common validator ENABLED,
    as the owner's review of 2026-09-11 ran it, so the case cannot be dismissed as a
    common-envelope inconsistency. The records are the model fixture wrapped in the twin's own
    envelopes: internally consistent, but synthetic — not signed or audited board evidence."""

    @classmethod
    def setUpClass(cls):
        import os
        if shutil.which(os.environ.get("CC", "cc")) is None:
            raise unittest.SkipTest("no host C compiler: the twin cannot be built")
        fw = R / "firmware/b2"
        made = subprocess.run(["make", "-s", "twin"], cwd=fw, capture_output=True, text=True)
        if made.returncode != 0:
            raise RuntimeError(made.stdout + made.stderr)
        out = subprocess.run([str(fw / "build/b2_twin"), "wire"], capture_output=True, text=True, check=True).stdout
        cls.wire = {ln.split(" ", 1)[0]: json.loads(ln.split(" ", 1)[1]) for ln in out.splitlines()}
        import claimb_r1p_instrument as inst
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as common
        cls.common = common
        cls.whole = cls.wrap(modelled_log(0, PAIRS))
        cls.split = [cls.wrap(modelled_log(0, 2)), cls.wrap(modelled_log(2, 1))]

    @classmethod
    def wrap(cls, log: dict) -> dict:
        """Give every record the twin's real rel-v4 envelope, rebound to that record."""
        ident = copy.deepcopy(cls.wire["IDENT"])
        ident.update(log["app_identity"])
        log["app_identity"] = ident
        cls.common.validate(ident)
        for i, src in enumerate(log["loop_records"]):
            rec = copy.deepcopy(cls.wire["REC"])
            rec.pop("search", None)
            rec.pop("arm", None)
            rec.update({k: copy.deepcopy(v) for k, v in src.items() if k != "evidence"})
            rec["evidence"]["score"] = copy.deepcopy(src["evidence"]["score"])
            cls.rebind(rec)
            log["loop_records"][i] = rec
        return log

    @classmethod
    def rebind(cls, rec: dict) -> None:
        """Every local commit field follows the record's own genome, so a changed genome stays
        internally consistent and still passes the common validator."""
        commit = rec["evidence"]["score"]["hw_candidate_commit"]
        rec["evidence"]["sign_reply"].update(seq=rec["seq"], commit=commit)
        rec["evidence"]["app_oracle_record"].update(seq=rec["seq"], staged_sha256=commit, readback_sha256=commit)
        cls.common.validate(rec)

    @classmethod
    def set_genome(cls, rec: dict, genome: int) -> None:
        rec["genome"] = bc.genome_to_hex(genome)
        rec["evidence"]["score"]["hw_candidate_commit"] = hashlib.sha256(rec["genome"].encode()).hexdigest()
        cls.rebind(rec)

    def _judge(self, logs) -> dict:
        return badj.adjudicate(logs, PLAN, PREDICTION, consts=CONSTS, common=True)

    def test_the_wrapped_control_passes_common_validation_and_adjudicates(self):
        res = self._judge([copy.deepcopy(self.whole)])
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["primary"], PREDICTION["predicted_primary"])

    def test_the_wrapped_split_control_also_passes(self):
        res = self._judge([copy.deepcopy(log) for log in self.split])
        self.assertEqual(res["outcome"], "PASS", res["findings"][:4])
        self.assertEqual(res["deltas"], PREDICTION["deltas"])

    def test_an_opening_baseline_that_is_not_the_blank_genome(self):
        log = copy.deepcopy(self.whole)
        self.set_genome(log["loop_records"][0], 1)
        res = self._judge([log])
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("opening baseline's genome" in x for x in res["findings"]), res["findings"][:4])
        self.assertNotIn("primary", res)

    def test_a_closing_baseline_that_is_not_the_blank_genome(self):
        log = copy.deepcopy(self.whole)
        self.set_genome(log["loop_records"][-1], 1)
        res = self._judge([log])
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("closing baseline's genome" in x for x in res["findings"]), res["findings"][:4])
        self.assertNotIn("primary", res)

    def test_a_bracket_of_one_session_of_a_split_run(self):
        for index, needle in ((0, "opening baseline's genome"), (-1, "closing baseline's genome")):
            with self.subTest(record=index):
                logs = [copy.deepcopy(log) for log in self.split]
                self.set_genome(logs[1]["loop_records"][index], 1)
                res = self._judge(logs)
                self.assertTrue(any(needle in x for x in res["findings"]), res["findings"][:4])
                self.assertNotIn("primary", res)


class Malformed(unittest.TestCase):
    """A malformed document must be NAMED — never an uncaught exception, and never a stateful
    replay over records the validator has already refused (the owner's review of 2026-09-11).
    Every case here reaches the module through its public entry point."""

    @classmethod
    def setUpClass(cls):
        cls.base = modelled_log(0, PAIRS)

    def _result(self, mutate):
        logs, plan, pred = [copy.deepcopy(self.base)], copy.deepcopy(PLAN), copy.deepcopy(PREDICTION)
        mutate(logs, plan, pred)
        try:
            return badj.adjudicate(logs, plan, pred, consts=CONSTS, common=False)
        except Exception as exc:                         # the defect this class exists for
            self.fail(f"{type(exc).__name__}: {exc}")

    def _refused(self, mutate, needle):
        res = self._result(mutate)
        self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"][:160])
        self.assertIn(needle, res["refusal"])

    def _held(self, mutate, needle):
        res = self._result(mutate)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any(needle in x for x in res["findings"]), f"{needle!r} not in {res['findings'][:4]}")
        self.assertIn("not_run", res["replay"], "a refused document was replayed anyway")
        self.assertNotIn("primary", res)
        return res

    def test_a_session_log_that_is_not_an_object(self):
        self._refused(lambda logs, p, q: logs.__setitem__(0, []), "not a JSON object")

    def test_a_seq_that_is_not_an_integer(self):
        for bad in ([], {}, "3", 3.5, True, None):
            with self.subTest(seq=bad):
                self._held(lambda logs, p, q, v=bad: logs[0]["loop_records"][2].__setitem__("seq", v),
                           "which is not an integer")

    def test_loop_records_that_are_not_an_array(self):
        for bad in (7, {}, "records"):
            with self.subTest(records=bad):
                self._held(lambda logs, p, q, v=bad: logs[0].__setitem__("loop_records", v), "not an array")

    def test_a_record_that_is_not_an_object(self):
        self._held(lambda logs, p, q: logs[0]["loop_records"].__setitem__(2, "nope"), "not a JSON object")

    def test_a_plan_field_of_the_wrong_type(self):
        for key, bad, needle in (("map", None, "is not a JSON object"), ("map", {}, "not 64 lower-case hex"),
                                 ("map", {"sha256": "ABCD" * 16}, "not 64 lower-case hex"),
                                 ("pairs", "3", f"is not 1..{bsess.MAX_PAIRS}"), ("pairs", 0, f"is not 1..{bsess.MAX_PAIRS}"),
                                 ("pairs", bsess.MAX_PAIRS + 1, f"is not 1..{bsess.MAX_PAIRS}"),
                                 ("budget_per_arm", "600", "positive integer"), ("budget_per_arm", True, "positive integer"),
                                 ("fitness", "F9", "is not one of"),
                                 ("seed_derivation", None, "no master_seed")):
            with self.subTest(key=key, given=bad):
                self._refused(lambda logs, p, q, k=key, v=bad: p.__setitem__(k, v), needle)

    def test_a_master_seed_that_is_not_an_integer(self):
        self._refused(lambda logs, p, q: p.__setitem__("seed_derivation", {"master_seed": "716169644"}),
                      "is not an integer")

    def test_a_prediction_field_of_the_wrong_type(self):
        cases = [(lambda q: q.pop("pairs"), "no array of pairs"),
                 (lambda q: q.__setitem__("pairs", None), "no array of pairs"),
                 (lambda q: q.__setitem__("pairs", []), "no array of pairs"),
                 (lambda q: q["pairs"][0].__setitem__("runs", None), "no A and B run objects"),
                 (lambda q: q["pairs"][0]["runs"].pop("B"), "no A and B run objects"),
                 (lambda q: q["pairs"].__setitem__(0, "nope"), "not an object naming an integer pair"),
                 (lambda q: q.__setitem__("deltas", None), "not an array of integers"),
                 (lambda q: q.__setitem__("deltas", ["1"]), "not an array of integers"),
                 (lambda q: q.pop("predicted_primary"), "no predicted_primary object"),
                 (lambda q: q.pop("fitness_sequence_sha256"), "is not 64 lower-case hex"),
                 (lambda q: q.__setitem__("fitness_sequence_length", "10818"), "values 3 pairs at budget"),
                 (lambda q: q.__setitem__("fitness_sequence_length", 10818), "values 3 pairs at budget")]
        for i, (mutate, needle) in enumerate(cases):
            with self.subTest(case=i, needle=needle):
                self._refused(lambda logs, p, q, f=mutate: f(q), needle)

    def test_a_fitness_that_is_not_a_string_is_never_hashed(self):
        """`plan["fitness"] not in bl.FITNESS` used to hash the value first (the owner's input
        review of 2026-09-11)."""
        for bad in ([], {}, ["F1"], {"name": "F1"}, 1, None):
            with self.subTest(fitness=bad):
                self._refused(lambda logs, p, q, v=bad: p.__setitem__("fitness", v), "is not a string")

    def test_a_master_seed_outside_the_wire_domain(self):
        """b1_carto.Rng masks to 32 bits, so master + 2**32 would replay the same stream under a
        different declaration."""
        for bad in (MASTER + 2 ** 32, -1, 2 ** 32):
            with self.subTest(master_seed=bad):
                def mutate(logs, p, q, v=bad):
                    p["seed_derivation"] = {"master_seed": v}
                    logs[0]["app_identity"]["master_seed"] = v
                self._refused(mutate, "outside 0..2**32-1")

    def test_a_map_digest_that_is_not_a_digest(self):
        def mutate(logs, p, q):
            p["map"] = {"sha256": "not-a-digest"}
            logs[0]["app_identity"].update(map_sha256="not-a-digest", operator_data_sha256="not-a-digest")
        self._refused(mutate, "not 64 lower-case hex")

    def test_a_predicted_count_that_is_a_boolean_or_a_float(self):
        """Python would compare `True` equal to 1 and `2.0` equal to 2 in values this module
        reports as EXACT."""
        cases = [(lambda q: q.__setitem__("budget_per_arm", float(BUDGET)), "is not the plan's"),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("best_train", 2.0), "is not an integer"),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("column_moves", False), "is not an integer"),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("champion_holdout", 1.0), "is not an integer"),
                 (lambda q: q["predicted_primary"].__setitem__("positives", True), "is not a count"),
                 (lambda q: q["predicted_primary"].__setitem__("ties", 2.0), "is not a count"),
                 (lambda q: q["predicted_primary"].__setitem__("sign_test_p", "0.02"), "is not a probability"),
                 (lambda q: q["predicted_primary"].__setitem__("alpha", True), "is not a probability"),
                 (lambda q: q["predicted_primary"].__setitem__("verdict", 1), "is not a string")]
        for i, (mutate, needle) in enumerate(cases):
            with self.subTest(case=i, needle=needle):
                self._refused(lambda logs, p, q, f=mutate: f(q), needle)

    def test_a_predicted_digest_that_is_not_a_digest(self):
        for k in badj.RUN_DIGESTS:
            with self.subTest(field=k):
                self._refused(lambda logs, p, q, k=k: q["pairs"][0]["runs"]["B"].__setitem__(k, "nope"),
                              "is not 64 lower-case hex")

    def test_a_predicted_value_outside_its_own_domain(self):
        ceiling = bl.CEILING["F1"]
        cases = [(lambda q: q["pairs"][0]["runs"]["A"].__setitem__("best_train", ceiling + 1), "outside 0.."),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("best_train", -1), "outside 0.."),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("column_moves", BUDGET + 1), "outside 0.."),
                 (lambda q: q["pairs"][0]["runs"]["A"].__setitem__("champion_holdout", bl.HOLDOUT_COUNT + 1),
                  "outside 0..")]
        for i, (mutate, needle) in enumerate(cases):
            with self.subTest(case=i):
                self._refused(lambda logs, p, q, f=mutate: f(q), needle)

    def test_a_contradictory_duplicate_prediction_pair(self):
        """The lookup used to overwrite it silently."""
        def mutate(logs, p, q):
            bad = copy.deepcopy(q["pairs"][0])
            bad["runs"]["A"]["best_train"] = 0
            q["pairs"].insert(0, bad)
        self._refused(mutate, "pair identities")

    def test_a_prediction_pair_outside_the_experiment(self):
        """The extra entry used to sit unvisited."""
        def mutate(logs, p, q):
            bad = copy.deepcopy(q["pairs"][0])
            bad["pair"] = p["pairs"]
            q["pairs"].append(bad)
        self._refused(mutate, "pair identities")

    def test_a_prediction_missing_one_of_the_experiments_pairs(self):
        self._refused(lambda logs, p, q: q["pairs"].pop(), "pair identities")

    def test_a_prediction_whose_pairs_are_out_of_order(self):
        def mutate(logs, p, q):
            q["pairs"].reverse()
            q["deltas"].reverse()
        self._refused(mutate, "pair identities")

    def test_a_prediction_that_does_not_account_for_itself(self):
        cases = [(lambda q: q["deltas"].__setitem__(0, q["deltas"][0] + 1), "does not account for its own"),
                 (lambda q: q["pairs"][0].__setitem__("delta_B_minus_A", 99), "does not account for its own"),
                 (lambda q: q.__setitem__("deltas", q["deltas"][:-1]), "deltas for 3 pairs"),
                 (lambda q: q["predicted_primary"].__setitem__("ties", 9), "do not account for"),
                 (lambda q: q["predicted_primary"].__setitem__("verdict", "whatever it likes"),
                  "not the sign test over its own deltas")]
        for i, (mutate, needle) in enumerate(cases):
            with self.subTest(case=i, needle=needle):
                self._refused(lambda logs, p, q, f=mutate: f(q), needle)

    def test_a_valid_prediction_that_merely_disagrees_is_a_finding_not_a_refusal(self):
        """The distinction the input guards must not erase."""
        def mutate(logs, p, q):
            q["pairs"][0]["runs"]["A"]["best_train"] += 1
            consistent(q)
        res = self._result(mutate)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:160])
        self.assertTrue(any("best_train" in x for x in res["findings"]), res["findings"][:4])

    def test_a_contradiction_collected_before_a_malformed_record_survives_it(self):
        """The measurement pass is per record and independent, so a shape finding later in the
        same log must not swallow a served readout that already contradicted its self-report."""
        def mutate(logs, p, q):
            logs[0]["loop_records"][1]["evidence"]["score"]["scores"][0] += 1
            logs[0]["loop_records"][2]["seq"] = []
        res = self._result(mutate)
        self.assertTrue(res["outcome"].startswith("KILL"), res["outcome"][:160])
        self.assertTrue(any("additive count" in x for x in res["kills"]), res["kills"][:3])
        self.assertTrue(any("which is not an integer" in x for x in res["findings"]), res["findings"][:4])
        self.assertIn("not_run", res["replay"])
        self.assertNotIn("primary", res)


class CommandLine(unittest.TestCase):
    """The CLI's contract: it always writes the result it was asked for."""

    @classmethod
    def setUpClass(cls):
        cls.dir = Path(tempfile.mkdtemp(prefix="b2-adjudicate-cli-"))
        (cls.dir / "plan.json").write_text(json.dumps(PLAN))
        (cls.dir / "prediction.json").write_text(json.dumps(PREDICTION))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, ignore_errors=True)

    def _run(self, log: dict, name: str):
        (self.dir / f"{name}.json").write_text(json.dumps(log))
        out = self.dir / f"{name}_result.json"
        p = subprocess.run([sys.executable, str(R / "host/b2_adjudicate.py"), "--no-common",
                            "--run-log", str(self.dir / f"{name}.json"), "--plan", str(self.dir / "plan.json"),
                            "--prediction", str(self.dir / "prediction.json"), "--out", str(out)],
                           text=True, capture_output=True)
        return p, out

    def test_a_correct_run_exits_zero_and_writes_its_result(self):
        p, out = self._run(modelled_log(0, PAIRS), "good")
        self.assertEqual(p.returncode, 0, p.stderr[-400:])
        self.assertTrue(out.is_file())
        self.assertEqual(json.loads(out.read_text())["outcome"], "PASS")

    def test_a_malformed_record_still_writes_a_result(self):
        log = modelled_log(0, PAIRS)
        log["loop_records"][2]["seq"] = []
        p, out = self._run(log, "bad_seq")
        self.assertEqual(p.returncode, 1, p.stderr[-400:])
        self.assertEqual(p.stderr, "", "the CLI exited through a traceback")
        self.assertTrue(out.is_file(), "the result file the caller asked for was not written")
        res = json.loads(out.read_text())
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"][:120])
        self.assertTrue(any("which is not an integer" in x for x in res["findings"]), res["findings"][:4])

    def test_an_input_error_never_takes_the_internal_error_path(self):
        """The last-resort handler exists for defects in this module, not for bad input."""
        plan = copy.deepcopy(PLAN)
        plan["fitness"] = []
        (self.dir / "plan_bad.json").write_text(json.dumps(plan))
        (self.dir / "log_ok.json").write_text(json.dumps(modelled_log(0, PAIRS)))
        out = self.dir / "plan_bad_result.json"
        p = subprocess.run([sys.executable, str(R / "host/b2_adjudicate.py"), "--no-common",
                            "--run-log", str(self.dir / "log_ok.json"), "--plan", str(self.dir / "plan_bad.json"),
                            "--prediction", str(self.dir / "prediction.json"), "--out", str(out)],
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 1, p.stderr[-400:])
        self.assertTrue(out.is_file())
        res = json.loads(out.read_text())
        self.assertNotIn("internal_error", res)
        self.assertIn("is not a string", res["refusal"])

    def test_a_file_that_is_not_json_is_refused_not_crashed(self):
        (self.dir / "broken.json").write_text("{nope")
        out = self.dir / "broken_result.json"
        p = subprocess.run([sys.executable, str(R / "host/b2_adjudicate.py"), "--no-common",
                            "--run-log", str(self.dir / "broken.json"), "--plan", str(self.dir / "plan.json"),
                            "--prediction", str(self.dir / "prediction.json"), "--out", str(out)],
                           text=True, capture_output=True)
        self.assertEqual(p.returncode, 1, p.stderr[-400:])
        self.assertTrue(out.is_file())
        self.assertIn("not readable JSON", json.loads(out.read_text())["refusal"])


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
