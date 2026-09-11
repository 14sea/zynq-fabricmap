"""The B2 record validator must REFUSE what the instrument's validator waves through.

The owner's core review of 2026-09-10 showed that deleting `REC.search`, or an identity with
an invalid map digest, a zero budget and an impossible pair slice, all validate under the
instrument's validator: it ignores unknown extension fields by design. So this test builds a
well-formed B2 session from the Python reference, checks it is accepted, and then drives one
mutation at a time — every case must be named in the findings.

The fixture's records are built from `b2_session.run`, so the shapes are the ones the image
actually emits (`tests/test_b2_session.py` proves the C orchestrator produces them).
"""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_records as brec  # noqa: E402
import b2_search as bs  # noqa: E402
import b2_session as bsess  # noqa: E402

TRUTH = bm.truth_mapping()
MASKS = bl.universe_mask(TRUTH)
FAB = bs.ModelFabric(TRUTH)
VIEW = bmaps.MapView(bmaps.load_self_map(), bl.train_vectors())
MAP_SHA = bmaps.sha256_of(bmaps.load_self_map())
BUDGET, PAIRS, FIRST, COUNT = 3, 9, 0, 2
CTX = brec.Context(master_seed=716169644, budget=BUDGET, pairs_total=PAIRS, pair_first=FIRST,
                   pair_count=COUNT, fitness="F1", map_sha256=MAP_SHA)


def identity(ctx: brec.Context = CTX) -> dict:
    return {"schema": "app_identity", "schema_version": "1.5.0", "control_plane": "standalone",
            "protocol": "rel-v4", "carrier_variant": "0x42310001",
            "search_version": bs.ENGINE_VERSION, "map_sha256": ctx.map_sha256,
            "operator_data_sha256": ctx.map_sha256, "fitness_id": ctx.fitness,
            "budget_per_arm": ctx.budget, "master_seed": ctx.master_seed,
            "pairs_total": ctx.pairs_total, "pair_first": ctx.pair_first, "pair_count": ctx.pair_count}


def run_log(ctx: brec.Context = CTX) -> dict:
    session = bsess.run(ctx.master_seed, ctx.budget, ctx.pairs_total, ctx.pair_first, ctx.pair_count,
                        FAB, VIEW, truth=TRUTH, masks=MASKS)
    records = []
    for c in session.candidates:
        rec = {"schema": "loop_record", "schema_version": "1.3.0", "seq": c.seq,
               "genome": f"{c.genome:080x}", "outcome": "SCORED", "verified": "audited", "evidence": {}}
        if c.arm:
            rec["arm"] = c.arm
        if c.block:
            rec["search"] = json.loads(c.block)
        records.append(rec)
    return {"app_identity": identity(ctx), "loop_records": records}


class Accepts(unittest.TestCase):
    def test_a_well_formed_session_has_no_findings(self):
        self.assertEqual(brec.validate_run_log(run_log(), CTX, common=False), [])

    def test_the_expected_order_is_the_preregistered_one(self):
        order = brec.expected_order(CTX)
        self.assertEqual(len(order), bsess.records(COUNT, BUDGET))
        self.assertIsNone(order[0])
        self.assertIsNone(order[-1])
        pair0 = [x for x in order[1:-1] if x[0] == 0]
        self.assertEqual([x[1] for x in pair0[:BUDGET]], ["random_safe"] * BUDGET)
        self.assertEqual([x[1] for x in pair0[BUDGET:2 * BUDGET]], ["map_guided"] * BUDGET)
        self.assertEqual([x[2] for x in pair0], [False] * 2 * BUDGET + [True, True])
        pair1 = [x for x in order[1:-1] if x[0] == 1]
        self.assertEqual(pair1[0][1], "map_guided", "the odd pair runs B first")

    def test_the_record_count_is_the_preregistrations(self):
        self.assertEqual(CTX.records, 2 + COUNT * (2 * BUDGET + 2))


class WhyThisModuleExists(unittest.TestCase):
    """The instrument's validator accepts these; this one must not.

    The fixtures are the twin's `wire` mode — the bytes the image really emits, which
    `tests/test_b2_wire.py` shows validate under the instrument — so the contrast is between
    two validators over the same real document, not between two hand-written dicts."""

    @classmethod
    def setUpClass(cls):
        import os
        import shutil
        import subprocess
        if shutil.which(os.environ.get("CC", "cc")) is None:
            raise unittest.SkipTest("no host C compiler: the twin cannot be built")
        fw = R / "firmware/b2"
        p = subprocess.run(["make", "-s", "twin"], cwd=fw, capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stdout + p.stderr)
        out = subprocess.run([str(fw / "build/b2_twin"), "wire"], capture_output=True, text=True, check=True).stdout
        cls.raw = {line.split(" ", 1)[0]: json.loads(line.split(" ", 1)[1]) for line in out.splitlines()}
        import claimb_r1p_instrument as inst
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as br
        cls.br = br

    def test_the_instrument_accepts_a_record_whose_search_block_was_deleted(self):
        rec = copy.deepcopy(self.raw["REC"])
        self.br.validate(rec)                                  # the real record: valid
        rec.pop("search")
        self.br.validate(rec)                                  # and still valid without the block
        ctx = brec.Context(master_seed=716169644, budget=4, pairs_total=9, pair_first=0, pair_count=4,
                           fitness="F1", map_sha256=MAP_SHA)
        findings = brec.record_findings(rec, ctx, (0, "map_guided", False), {})
        self.assertTrue(any("must carry a search block" in x for x in findings), findings)

    def test_the_instrument_accepts_an_identity_with_nonsense_b2_fields(self):
        ident = copy.deepcopy(self.raw["IDENT"])
        self.br.validate(ident)                                # the real identity: valid
        ident.update(map_sha256="00" * 32, budget_per_arm=0, pair_first=8, pair_count=4)
        self.br.validate(ident)                                # and still valid with nonsense
        ctx = brec.Context(master_seed=ident["master_seed"], budget=600, pairs_total=9, pair_first=0,
                           pair_count=4, fitness="F1", map_sha256=MAP_SHA)
        findings = brec.identity_findings(ident, ctx)
        for needle in ("map_sha256", "budget_per_arm", "pair slice"):
            self.assertTrue(any(needle in x for x in findings), f"{needle}: {findings}")


    def test_the_instrument_accepts_a_record_with_malformed_b2_values(self):
        """The owner's initial review of 2026-09-11, on the wire REC its probe used."""
        ctx = brec.Context(master_seed=716169644, budget=4, pairs_total=9, pair_first=0, pair_count=4,
                           fitness="F1", map_sha256=MAP_SHA)
        want = (0, "map_guided", False)
        self.assertEqual(brec.record_findings(copy.deepcopy(self.raw["REC"]), ctx, want, {}), [],
                         "the twin's own record must be accepted unmutated")
        for k, v, needle in (("pair", "0", "pair is not an integer"),
                             ("population", [0] * bs.MU, "population must be"),
                             ("population", [{"born": "invalid", "fit": {}}] * bs.MU,
                              "born and fit are not integers"),
                             ("selected", "invalid", "selected is not a boolean")):
            with self.subTest(field=k, value=v):
                rec = copy.deepcopy(self.raw["REC"])
                rec["search"][k] = v
                self.br.validate(rec)                  # the instrument accepts every one of them
                findings = brec.record_findings(rec, ctx, want, {})
                self.assertTrue(any(needle in x for x in findings), findings)


class Types(unittest.TestCase):
    """A malformed B2 value must be NAMED, never raise, and nothing may compare, index, sort,
    hash or count it before its type is known (the owner's initial review of 2026-09-11)."""

    @classmethod
    def setUpClass(cls):
        cls.base = run_log()

    def _first_search(self, log) -> dict:
        return next(r for r in log["loop_records"] if "search" in r)

    def _refuses(self, mutate, needle: str):
        log = copy.deepcopy(self.base)
        mutate(log)
        try:
            findings = brec.validate_run_log(log, CTX, common=False)
        except Exception as exc:                       # the defect this class exists for
            self.fail(f"{type(exc).__name__}: {exc}")
        self.assertTrue(findings, "the malformed session was accepted")
        self.assertTrue(any(needle in x for x in findings), f"{needle!r} not named in {findings[:4]}")

    def test_refuses_the_reviews_four_extension_values(self):
        for k, v, needle in (("pair", "0", "pair is not an integer"),
                             ("population", [0] * bs.MU, "population must be"),
                             ("population", [{"born": "invalid", "fit": {}}] * bs.MU,
                              "born and fit are not integers"),
                             ("selected", "invalid", "selected is not a boolean")):
            with self.subTest(field=k, value=v):
                self._refuses(lambda log, k=k, v=v: self._first_search(log)["search"].__setitem__(k, v), needle)

    def test_refuses_every_block_value_of_the_wrong_type(self):
        wrong = {"a string": 5, "an integer": "1", "a boolean": "yes", "an integer or null": "1"}
        for k, _ok, what in brec.BLOCK_TYPES:
            with self.subTest(field=k, given=wrong[what]):
                self._refuses(lambda log, k=k, v=wrong[what]: self._first_search(log)["search"].__setitem__(k, v),
                              f"{k} is not {what}")

    def test_a_json_boolean_is_not_an_integer_field(self):
        for k, _ok, what in brec.BLOCK_TYPES:
            if what.startswith("an integer"):
                with self.subTest(field=k):
                    self._refuses(lambda log, k=k: self._first_search(log)["search"].__setitem__(k, True),
                                  f"{k} is not {what}")

    def test_refuses_a_malformed_move(self):
        for v, needle in (({"bits": [1], "kind": 5}, "kind is not a string"),
                          ({"bits": "01", "kind": "random"}, "bits are not a list of integers"),
                          ({"bits": [[1]], "kind": "random"}, "bits are not a list of integers"),
                          ({"bits": [1, "2"], "kind": "random"}, "bits are not a list of integers"),
                          ({"bits": [True], "kind": "random"}, "bits are not a list of integers"),
                          ({"kind": "random"}, "the move must be bits and kind"),
                          (5, "the move must be bits and kind")):
            with self.subTest(move=v):
                self._refuses(lambda log, v=v: self._first_search(log)["search"].__setitem__("move", v), needle)

    def test_refuses_a_malformed_population_entry(self):
        for v, needle in (([{"born": 0, "fit": 0}] * (bs.MU - 1), "population must be"),
                          ([{"born": 0}] * bs.MU, "population must be"),
                          ([[0, 0]] * bs.MU, "population must be"),
                          ([{"born": 0, "fit": True}] * bs.MU, "born and fit are not integers"),
                          ([{"born": None, "fit": 0}] * bs.MU, "born and fit are not integers")):
            with self.subTest(population=v):
                self._refuses(lambda log, v=v: self._first_search(log)["search"].__setitem__("population", v), needle)

    def test_refuses_every_identity_value_of_the_wrong_type(self):
        wrong = {"a string": 5, "an integer": "1"}
        for k, _ok, what in brec.IDENTITY_TYPES:
            with self.subTest(field=k):
                self._refuses(lambda log, k=k, v=wrong[what]: log["app_identity"].__setitem__(k, v),
                              f"{k} is not {what}")

    def test_an_identity_integer_is_not_a_json_boolean(self):
        for k, _ok, what in brec.IDENTITY_TYPES:
            if what == "an integer":
                with self.subTest(field=k):
                    self._refuses(lambda log, k=k: log["app_identity"].__setitem__(k, True),
                                  f"{k} is not an integer")

    def test_refuses_a_document_that_is_not_shaped_like_a_session(self):
        self.assertEqual(brec.validate_run_log([], CTX, common=False), ["session: not a JSON object"])
        self.assertEqual(brec.record_findings("nope", CTX, None, {}), ["record: not a JSON object"])
        self.assertEqual(brec.identity_findings([1], CTX), ["identity: not a JSON object"])
        self._refuses(lambda log: log.__setitem__("loop_records", "nope"), "loop_records is not an array")
        self._refuses(lambda log: log["loop_records"].__setitem__(3, "nope"), "record 4 is not a JSON object")
        self._refuses(lambda log: log.__setitem__("app_identity", [1]), "identity: not a JSON object")

    def test_a_value_of_unknown_type_never_reaches_the_counters(self):
        rec = copy.deepcopy(self._first_search(copy.deepcopy(self.base)))
        rec["search"]["pair"] = "0"
        state: dict = {}
        findings = brec.record_findings(rec, CTX, (0, rec["arm"], False), state)
        self.assertTrue(any("pair is not an integer" in x for x in findings), findings)
        self.assertEqual(state, {}, "the state was advanced for a record of unknown type")

    def test_refuses_a_pair_outside_the_experiments_own_pairs(self):
        """An inconsistent context must not index past the derived seeds."""
        ctx = brec.Context(master_seed=CTX.master_seed, budget=BUDGET, pairs_total=2, pair_first=0,
                           pair_count=3, fitness="F1", map_sha256=MAP_SHA)
        rec = copy.deepcopy(self._first_search(copy.deepcopy(self.base)))
        rec["search"]["pair"] = 2
        findings = brec.record_findings(rec, ctx, (2, rec["arm"], False), {})
        self.assertTrue(any("outside the experiment" in x for x in findings), findings)


class Refuses(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.base = run_log()

    def _refuses(self, mutate, needle: str):
        log = copy.deepcopy(self.base)
        mutate(log)
        findings = brec.validate_run_log(log, CTX, common=False)
        self.assertTrue(findings, "the corrupted session was accepted")
        self.assertTrue(any(needle in x for x in findings), f"{needle!r} not named in {findings[:4]}")

    def _first_search(self, log) -> dict:
        return next(r for r in log["loop_records"] if "search" in r)

    # ---- the identity: exactly what the instrument's validator waves through
    def test_refuses_a_deleted_search_block(self):
        self._refuses(lambda log: self._first_search(log).pop("search"), "must carry a search block")

    def test_refuses_an_invalid_map_digest(self):
        self._refuses(lambda log: log["app_identity"].__setitem__("map_sha256", "00" * 32), "map_sha256")

    def test_refuses_a_zero_budget(self):
        self._refuses(lambda log: log["app_identity"].__setitem__("budget_per_arm", 0), "budget_per_arm")

    def test_refuses_an_impossible_pair_slice(self):
        self._refuses(lambda log: log["app_identity"].update(pair_first=8, pair_count=4), "pair slice")

    def test_refuses_the_b1_fields_this_image_must_not_declare(self):
        for k, v in (("carto_version", "carto-v1"), ("probe_budget", 333)):
            with self.subTest(field=k):
                self._refuses(lambda log, k=k, v=v: log["app_identity"].__setitem__(k, v), k)

    def test_refuses_a_wrong_engine_or_fitness_or_seed(self):
        for k, v, needle in (("search_version", "b2-es-v2", "search_version"),
                             ("fitness_id", "F2", "fitness_id"),
                             ("master_seed", 1, "master_seed"),
                             ("carrier_variant", "0xdeadbeef", "carrier_variant"),
                             ("protocol", "rec-v3", "protocol"),
                             ("schema_version", "1.4.0", "schema_version")):
            with self.subTest(field=k):
                self._refuses(lambda log, k=k, v=v: log["app_identity"].__setitem__(k, v), needle)

    def test_refuses_a_missing_b2_identity_field(self):
        for k in brec.IDENTITY_B2_KEYS:
            with self.subTest(field=k):
                self._refuses(lambda log, k=k: log["app_identity"].pop(k), k)

    # ---- the block's shape
    def test_refuses_a_baseline_that_carries_a_block(self):
        def mutate(log):
            log["loop_records"][0]["search"] = copy.deepcopy(self._first_search(log)["search"])
        self._refuses(mutate, "a baseline carries no search block")

    def test_refuses_a_baseline_that_carries_an_arm(self):
        self._refuses(lambda log: log["loop_records"][0].__setitem__("arm", "map_guided"), "a baseline carries no arm")

    def test_refuses_a_block_with_the_wrong_keys(self):
        self._refuses(lambda log: self._first_search(log)["search"].pop("selected"), "keys are not exactly")

    def test_refuses_a_carto_block(self):
        self._refuses(lambda log: self._first_search(log).__setitem__("carto", {}), "stage B1")

    def test_refuses_a_wrong_record_schema_version(self):
        self._refuses(lambda log: self._first_search(log).__setitem__("schema_version", "1.2.0"), "schema_version")

    # ---- the block's bindings
    def test_refuses_an_arm_letter_that_contradicts_the_record(self):
        self._refuses(lambda log: self._first_search(log)["search"].__setitem__("arm", "B"), "disagrees with the record")

    def test_refuses_a_swapped_arm(self):
        self._refuses(lambda log: self._first_search(log).__setitem__("arm", "map_guided"), "is not the 'random_safe'")

    def test_refuses_a_pair_outside_the_slice(self):
        def mutate(log):
            blk = self._first_search(log)["search"]
            blk["pair"] = 7
        self._refuses(mutate, "is not 0")

    def test_refuses_seeds_that_are_not_the_pairs(self):
        for k in ("landscape_seed", "operator_seed"):
            with self.subTest(field=k):
                self._refuses(lambda log, k=k: self._first_search(log)["search"].__setitem__(k, 1), "derived seeds")

    def test_refuses_a_malformed_state_commitment(self):
        self._refuses(lambda log: self._first_search(log)["search"].__setitem__("state_sha256", "nope"), "state_sha256")

    def test_refuses_a_population_of_the_wrong_size(self):
        self._refuses(lambda log: self._first_search(log)["search"]["population"].pop(), "population must be")

    def test_refuses_a_version_that_is_not_the_engine(self):
        self._refuses(lambda log: self._first_search(log)["search"].__setitem__("version", "x"), "block's version")

    # ---- the move, the counters and the holdout
    def test_refuses_a_column_move_on_the_random_safe_arm(self):
        def mutate(log):
            blk = next(r["search"] for r in log["loop_records"] if r.get("arm") == "random_safe")
            blk["move"]["kind"] = "column"
        self._refuses(mutate, "column move on the random-safe arm")

    def test_refuses_column_moves_counted_on_the_random_safe_arm(self):
        def mutate(log):
            blk = next(r["search"] for r in log["loop_records"] if r.get("arm") == "random_safe")
            blk["column_moves"] = 1
        self._refuses(mutate, "column moves")

    def test_refuses_malformed_move_bits(self):
        for bits, needle in (([], "distinct sorted"), ([1, 1], "distinct sorted"), ([5, 2], "distinct sorted"),
                             ([292], "distinct sorted"), ([1, 2, 3, 4, 5], "distinct sorted")):
            with self.subTest(bits=bits):
                self._refuses(lambda log, b=bits: self._first_search(log)["search"]["move"].__setitem__("bits", b), needle)

    def test_refuses_an_evaluation_index_out_of_step(self):
        self._refuses(lambda log: self._first_search(log)["search"].__setitem__("eval", 7), "is not 1 for")

    def test_refuses_a_counter_going_backwards(self):
        def mutate(log):
            blocks = [r["search"] for r in log["loop_records"] if r.get("arm") == "random_safe" and r["search"]["move"]]
            blocks[-1]["best"] = -1
        self._refuses(mutate, "went backwards")

    def test_refuses_a_holdout_record_shaped_like_a_search_record(self):
        def mutate(log):
            blk = next(r["search"] for r in log["loop_records"] if r.get("search", {}).get("holdout") is not None)
            blk["move"] = {"bits": [1], "kind": "random"}
        self._refuses(mutate, "carries no move")

    def test_refuses_a_search_record_carrying_a_holdout_value(self):
        self._refuses(lambda log: self._first_search(log)["search"].__setitem__("holdout", 3), "carries no holdout")

    def test_refuses_a_missing_holdout_value(self):
        def mutate(log):
            blk = next(r["search"] for r in log["loop_records"] if r.get("search", {}).get("holdout") is not None)
            blk["holdout"] = None
        self._refuses(mutate, "must carry its holdout value")

    # ---- the session
    def test_refuses_a_record_count_that_is_not_the_orders(self):
        self._refuses(lambda log: log["loop_records"].pop(), "the order requires")

    def test_refuses_a_broken_seq_run(self):
        self._refuses(lambda log: log["loop_records"][3].__setitem__("seq", 99), "carries seq")

    def test_refuses_an_identity_slice_the_records_do_not_use(self):
        def mutate(log):
            log["app_identity"].update(pair_first=5, pair_count=2)
        self._refuses(mutate, "pair slice")

    def test_refuses_a_swapped_arm_order_within_a_pair(self):
        def mutate(log):
            recs = log["loop_records"]
            for r in recs[1:1 + 2 * BUDGET]:
                r["arm"] = "map_guided" if r["arm"] == "random_safe" else "random_safe"
        self._refuses(mutate, "the order requires")


if __name__ == "__main__":
    unittest.main()
