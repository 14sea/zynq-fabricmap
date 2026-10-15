"""b3/host/b3_records.py — the B3 record validator must REFUSE, by name, what the instrument's
validator waves through, and must hold every O-arm search record to its ledger entry and to the
prediction.

The fixture is a well-formed B3 session from the reference orchestrator `b3_session.run_context`
(`b2_search.run` for the R and F arms, `b3_online_arm.run_online` for the O arm — every block the
arm's own run produced, the 1.4.0 shape of docs/b3_architecture.md v0.3 §7), the prediction from
`b3_plan.build_prediction` over the same seeds. The session is checked to be accepted with no finding, then one mutation is driven
at a time — every case must be NAMED in the findings, and no malformed value may raise.

Held here: the ledger sub-block is on O-arm SEARCH records only (an O champion's holdout record, an
R / F search record, any holdout record and a baseline are refused when they carry one; an O search
record without one is refused); every entry is bound to its block, chained to the previous entry
(the map version; the running anomaly count; a decode bumps the version exactly once; an anomaly
changes nothing else; no address decoded twice, no position taken twice) and compared field for
field with the prediction's entry for that evaluation; the last O search record's and the O
holdout record's `state_sha256` equal the predicted final search + cartographer commitment; the
order, the arm per record, the seq run, the record count and the identity 1.6.0 fields.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host", R / "b3/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_online_arm as oa  # noqa: E402
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
BUDGET, PAIRS = 8, 3                  # three pairs: RFO, FOR, ORF — every arm once in every position
SEEDS = [(1000, 5000), (1001, 5001), (1002, 5002)]
MASTER = 716169644


def make_plan(budget=BUDGET, pairs=PAIRS, session="B3") -> dict:
    return {"schema": "b3_plan", "schema_version": pl.SCHEMA_VERSION, "lifecycle": pl.LIFECYCLE, "session": session,
            "fitness": "F1", "budget_per_arm": budget, "pairs": pairs,
            "seed_derivation": {"label": pl.SESSION_LABEL, "master_seed": MASTER},
            "map": {"sha256": MAP_SHA}, "carto_version": carto_mod.CARTO_VERSION, "b1_map_cost": oa.B1_MAP_COST}


PLAN = make_plan()
PRED = pl.build_prediction("F1", BUDGET, SEEDS)
CTX = brec.context_from(PLAN, PRED, 0, PAIRS)
CTX_SLICE = brec.context_from(PLAN, PRED, 1, 2)


def run_log(ctx: brec.Context = CTX) -> dict:
    """A well-formed B3 session from the reference orchestrator (b3_session over the fabric model), as
    loop_record 1.4.0 documents — the O-arm blocks are run_online's own production blocks."""
    return fx.run_log(ctx, bsess.run_context(ctx, FAB, VIEW, TRUTH, MASKS))


BASE = run_log()


def o_search(log, pair=0, n=0) -> dict:
    """The n-th (0-based) O-arm search record of `pair`."""
    return [r for r in log["loop_records"] if r.get("arm") == "online" and r["search"]["pair"] == pair and r["search"]["holdout"] is None][n]


def o_holdout(log, pair=0) -> dict:
    return next(r for r in log["loop_records"] if r.get("arm") == "online" and r["search"]["pair"] == pair and r["search"]["holdout"] is not None)


def search_of(log, arm, pair=0, n=0) -> dict:
    return [r for r in log["loop_records"] if r.get("arm") == arm and r["search"]["pair"] == pair and r["search"]["holdout"] is None][n]


def holdout_of(log, arm, pair=0) -> dict:
    return next(r for r in log["loop_records"] if r.get("arm") == arm and r["search"]["pair"] == pair and r["search"]["holdout"] is not None)


def decoding_entry_index(log, pair=0) -> int:
    """The index (0-based) of an O search record of `pair` whose entry decoded something."""
    for n in range(BUDGET):
        if o_search(log, pair, n)["search"]["ledger"]["decoded"]:
            return n
    raise AssertionError("the fixture has no decoding specimen in this pair — raise BUDGET")


def renumber(log) -> None:
    for i, r in enumerate(log["loop_records"], start=1):
        r["seq"] = i


class Fixture(unittest.TestCase):
    """The fixture is what the tests below mutate: its shape must be the preregistered one."""

    def test_the_fixture_has_a_decoding_specimen_and_a_non_decoding_one(self):
        entries = [o_search(BASE, 0, n)["search"]["ledger"] for n in range(BUDGET)]
        self.assertTrue(any(e["decoded"] for e in entries), "no decode in pair 0: the version-bump rules are not exercised")
        self.assertTrue(any(not e["decoded"] for e in entries))
        self.assertEqual([e["anomalies"] for e in entries], [0] * BUDGET)

    def test_the_fixture_o_blocks_carry_the_predicted_ledger_and_commitment(self):
        for r in range(PAIRS):
            self.assertEqual([o_search(BASE, r, n)["search"]["ledger"] for n in range(BUDGET)], PRED["pairs"][r]["runs"]["O"]["ledger"])
            self.assertEqual(o_search(BASE, r, BUDGET - 1)["search"]["state_sha256"], PRED["pairs"][r]["runs"]["O"]["final_state_sha256"])

    def test_only_o_search_records_carry_a_ledger(self):
        with_ledger = [r for r in BASE["loop_records"] if "search" in r and "ledger" in r["search"]]
        self.assertEqual(len(with_ledger), PAIRS * BUDGET)
        self.assertTrue(all(r["arm"] == "online" and r["search"]["holdout"] is None for r in with_ledger))


class Accepts(unittest.TestCase):
    def test_a_well_formed_session_has_no_findings(self):
        self.assertEqual(brec.validate_run_log(run_log(), CTX, common=False), [])

    def test_a_well_formed_slice_has_no_findings(self):
        log = run_log(CTX_SLICE)
        self.assertEqual(brec.validate_run_log(log, CTX_SLICE, common=False), [])
        self.assertEqual(len(log["loop_records"]), CTX_SLICE.records)
        self.assertNotEqual(brec.validate_run_log(log, CTX, common=False), [], "the full-experiment context must not accept the slice")

    def test_the_expected_order_is_the_preregistered_one(self):
        order = brec.expected_order(CTX)
        self.assertEqual(len(order), pl.session_records(PAIRS, BUDGET))
        self.assertIsNone(order[0])
        self.assertIsNone(order[-1])
        for r, letters in enumerate(("RFO", "FOR", "ORF")):
            pair = [x for x in order[1:-1] if x[0] == r]
            self.assertEqual(len(pair), 3 * BUDGET + 3)
            for i, a in enumerate(letters):
                self.assertEqual([x[1] for x in pair[i * BUDGET:(i + 1) * BUDGET]], [brec.ARM_WIRE[a]] * BUDGET)
            self.assertEqual([x[1] for x in pair[3 * BUDGET:]], [brec.ARM_WIRE[a] for a in letters])
            self.assertEqual([x[2] for x in pair], [False] * 3 * BUDGET + [True] * 3)

    def test_the_record_count_is_the_preregistrations(self):
        self.assertEqual(CTX.records, 2 + PAIRS * (3 * BUDGET + 3))
        self.assertEqual(CTX_SLICE.records, 2 + 2 * (3 * BUDGET + 3))

    def test_the_arm_order_is_the_plan_tools(self):
        for r in range(12):
            self.assertEqual("".join(brec.arm_order(r)), pl.ARM_SEQUENCE[r % 6])


class Refuses(unittest.TestCase):
    """One mutation at a time; every case named, none raising."""

    def _findings(self, mutate, ctx=CTX) -> list[str]:
        log = copy.deepcopy(BASE)
        mutate(log)
        try:
            return brec.validate_run_log(log, ctx, common=False)
        except Exception as exc:                       # the defect this class exists for
            self.fail(f"{type(exc).__name__}: {exc}")

    def _refuses(self, mutate, *needles, ctx=CTX) -> list[str]:
        findings = self._findings(mutate, ctx)
        self.assertTrue(findings, "the mutated session was accepted")
        for needle in needles:
            self.assertTrue(any(needle in x for x in findings), f"{needle!r} not named in {findings[:6]}")
        return findings

    # -- the arm and the order
    def test_a_wrong_arm_is_named(self):
        self._refuses(lambda log: search_of(log, "random_safe").__setitem__("arm", "online"), "arm 'online' is not the 'random_safe' the order requires")
        self._refuses(lambda log: o_search(log).__setitem__("arm", "map_guided"), "arm 'map_guided' is not the 'online' the order requires")

    def test_the_arms_out_of_the_pairs_order_are_named(self):
        def swap_r_and_f_of_pair_0(log):
            recs = log["loop_records"]
            r_run, f_run = recs[1:1 + BUDGET], recs[1 + BUDGET:1 + 2 * BUDGET]
            recs[1:1 + 2 * BUDGET] = f_run + r_run
            renumber(log)
        f = self._refuses(swap_r_and_f_of_pair_0, "arm 'map_guided' is not the 'random_safe' the order requires",
                          "arm 'random_safe' is not the 'map_guided' the order requires")
        self.assertGreaterEqual(len(f), 2 * BUDGET)

    def test_a_block_arm_letter_disagreeing_with_the_record_is_named(self):
        self._refuses(lambda log: o_search(log)["search"].__setitem__("arm", "B"), "the block's arm 'B' disagrees with the record's 'online'")

    # -- the phase
    def test_a_holdout_block_in_a_search_position_is_named(self):
        def holdout_where_search_is_due(log):
            o_search(log, 0, 0)["search"] = copy.deepcopy(o_holdout(log)["search"])
        self._refuses(holdout_where_search_is_due, "a search record carries no holdout value", "must carry its move", "must carry its ledger sub-block")

    def test_a_search_block_in_a_holdout_position_is_named(self):
        def search_where_holdout_is_due(log):
            o_holdout(log)["search"] = copy.deepcopy(o_search(log, 0, BUDGET - 1)["search"])
        self._refuses(search_where_holdout_is_due, "must carry its holdout value", "a holdout record carries no move, fitness or parent",
                      "a ledger sub-block on an O champion's holdout record")

    # -- the ledger: where it may and may not be
    def test_an_o_search_record_without_its_ledger_is_named(self):
        self._refuses(lambda log: o_search(log, 1, 3)["search"].pop("ledger"), "record", "an O-arm search record must carry its ledger sub-block")

    def test_a_ledger_on_an_r_search_record_is_named(self):
        self._refuses(lambda log: search_of(log, "random_safe")["search"].__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "a ledger sub-block on a random-safe search record (only O-arm search records carry one)")

    def test_a_ledger_on_an_f_search_record_is_named(self):
        self._refuses(lambda log: search_of(log, "map_guided")["search"].__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "a ledger sub-block on a frozen-map search record (only O-arm search records carry one)")

    def test_a_ledger_on_an_o_holdout_record_is_named(self):
        self._refuses(lambda log: o_holdout(log)["search"].__setitem__("ledger", copy.deepcopy(o_search(log, 0, BUDGET - 1)["search"]["ledger"])),
                      "a ledger sub-block on an O champion's holdout record (only O-arm search records carry one)")

    def test_a_ledger_on_an_r_or_f_holdout_record_is_named(self):
        self._refuses(lambda log: holdout_of(log, "random_safe")["search"].__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "a ledger sub-block on a random-safe champion's holdout record")
        self._refuses(lambda log: holdout_of(log, "map_guided")["search"].__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "a ledger sub-block on a frozen-map champion's holdout record")

    def test_a_ledger_on_a_baseline_or_at_the_top_level_is_named(self):
        self._refuses(lambda log: log["loop_records"][0].__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "record 1: a top-level `ledger`")
        self._refuses(lambda log: o_search(log).__setitem__("ledger", copy.deepcopy(o_search(log)["search"]["ledger"])),
                      "a top-level `ledger`: the ledger sub-block lives inside an O-arm search record's search block")
        self._refuses(lambda log: log["loop_records"][-1].__setitem__("search", copy.deepcopy(o_search(log)["search"])),
                      "a baseline carries no search block")

    # -- the ledger entry against its block
    def test_an_entry_unbound_from_its_block_is_named(self):
        self._refuses(lambda log: o_search(log, 0, 2)["search"]["ledger"].__setitem__("seq", 7), "ledger.seq 7 is not the record's eval 3", "is not this run's entry 3")
        self._refuses(lambda log: o_search(log, 0, 2)["search"]["move"].__setitem__("bits", [0]), "ledger.intervention", "is not the move's bits [0]")
        self._refuses(lambda log: o_search(log, 0, 2)["search"]["move"].__setitem__("kind", "column"), "is not the move's kind 'column'")
        self._refuses(lambda log: o_search(log, 0, 2)["search"].__setitem__("fitness", 39), "is not the record's fitness 39")
        self._refuses(lambda log: o_search(log, 0, 2)["search"].__setitem__("parent_born", 0), "is not the record's parent_born 0")

    # -- the ledger entry against the run's continuity
    def test_a_version_jump_is_named(self):
        n = decoding_entry_index(BASE)
        self._refuses(lambda log: o_search(log, 0, n)["search"]["ledger"].__setitem__("map_version_after", o_search(log, 0, n)["search"]["ledger"]["map_version"] + 2),
                      "is not map_version", "+ 1 for a specimen that decoded")
        m = next(i for i in range(BUDGET) if not o_search(BASE, 0, i)["search"]["ledger"]["decoded"])
        self._refuses(lambda log: o_search(log, 0, m)["search"]["ledger"].__setitem__("map_version_after", o_search(log, 0, m)["search"]["ledger"]["map_version"] + 1),
                      "for a specimen that decoded nothing (the version bumps only on a decode)")

    def test_a_broken_version_chain_is_named(self):
        self._refuses(lambda log: o_search(log, 0, 3)["search"]["ledger"].__setitem__("map_version", 9), "ledger.map_version 9 is not the previous entry's map_version_after")
        self._refuses(lambda log: o_search(log, 0, 0)["search"]["ledger"].__setitem__("map_version", 1), "the first ledger entry's map_version 1 is not 0 (the online map starts empty)")

    def test_an_anomaly_is_named(self):
        self._refuses(lambda log: o_search(log, 1, 2)["search"]["ledger"].__setitem__("anomalies", 1),
                      "record", "an anomaly — the board's cartographer refused this specimen (anomalies 0 -> 1)", "ledger.anomalies went backwards (1 -> 0)")
        n = decoding_entry_index(BASE)
        self._refuses(lambda log: o_search(log, 0, n)["search"]["ledger"].__setitem__("anomalies", 1), "a refused specimen changes nothing else")
        self._refuses(lambda log: o_search(log, 1, 2)["search"]["ledger"].__setitem__("anomalies", 2), "ledger.anomalies jumped (0 -> 2)")

    def test_an_address_decoded_twice_or_a_position_taken_twice_is_named(self):
        n = decoding_entry_index(BASE)
        self.assertLess(n, BUDGET - 1, "the decode must not be the run's last entry for this test")

        def redecode(log):
            e0 = o_search(log, 0, n)["search"]["ledger"]
            e1 = o_search(log, 0, n + 1)["search"]["ledger"]
            e1["decoded"] = copy.deepcopy(e0["decoded"])
            e1["map_version_after"] = e1["map_version"] + 1
            for k in range(n + 2, BUDGET):
                e = o_search(log, 0, k)["search"]["ledger"]
                e["map_version"] += 1
                e["map_version_after"] += 1
        self._refuses(redecode, "decoded twice in this run", "taken twice in this run")

    # -- the ledger entry against the prediction
    def test_an_entry_drifting_from_the_prediction_is_named_by_path(self):
        def flip_delta(log):
            d = o_search(log, 2, 4)["search"]["ledger"]["behaviour_delta"]
            d[0] = [d[0][0], (d[0][1] + 1) % 64]
        self._refuses(flip_delta, "ledger.behaviour_delta[0][1]:", "not the predicted entry")

        def more_decodes(log):
            e = o_search(log, 2, 4)["search"]["ledger"]
            e["decoded"] = e["decoded"] + [[291, 5, 63]]
        self._refuses(more_decodes, "ledger.decoded:", "not the predicted entry")

    def test_a_drifting_fitness_is_named_against_the_block_and_the_prediction(self):
        def fit(log):
            r = o_search(log, 2, 4)["search"]
            r["fitness"] = r["ledger"]["fitness"] = 39
        self._refuses(fit, "ledger.fitness: 39, expected", "not the predicted entry")

    # -- the state commitment
    def test_a_final_commitment_drifting_from_the_prediction_is_named(self):
        self._refuses(lambda log: o_search(log, 0, BUDGET - 1)["search"].__setitem__("state_sha256", "1" * 64),
                      "the final O-arm state_sha256 111111111111… is not the predicted search + cartographer commitment")
        self._refuses(lambda log: o_holdout(log, 1)["search"].__setitem__("state_sha256", "2" * 64),
                      "the O champion's holdout record's state_sha256 222222222222… is not the predicted final commitment")

    def test_a_malformed_commitment_is_named(self):
        self._refuses(lambda log: o_search(log, 0, BUDGET - 1)["search"].__setitem__("state_sha256", o_search(log, 0, BUDGET - 1)["search"]["state_sha256"] + "\n"),
                      "state_sha256 is not 64 hex")

    # -- the sequence and the count
    def test_a_seq_drift_is_named(self):
        self._refuses(lambda log: log["loop_records"][5].__setitem__("seq", 7), "session: record 6 carries seq 7")

    def test_a_wrong_record_count_is_named(self):
        self._refuses(lambda log: log["loop_records"].pop(4), f"records, the order requires {CTX.records}")
        self._refuses(lambda log: log["loop_records"].insert(4, copy.deepcopy(log["loop_records"][4])), f"records, the order requires {CTX.records}")

    def test_a_whole_run_replaced_by_unscored_records_is_named(self):
        """The owner's P2 on 989bac5: every search and holdout record of one arm of pair 0 replaced by a
        non-SCORED record without a search block (the same count, the same seq run) — the run then
        creates no state, and the session must still name it as missing, for R, F and O alike."""
        for arm, text in (("random_safe", "random-safe"), ("map_guided", "frozen-map"), ("online", "online")):
            with self.subTest(arm=arm):
                def erase_run(log, arm=arm):
                    for rec in log["loop_records"]:
                        if rec.get("arm") == arm and rec["search"]["pair"] == 0:
                            rec.pop("search")
                            rec["outcome"] = "REFUSED_BY_GATE"
                findings = self._refuses(erase_run, f"has no records at all — the whole {text} run of pair 0 is missing")
                self.assertEqual(len(findings), 1, findings)          # the erased run is named exactly once; nothing else is wrong
                key = (0, brec.ARM_LETTER[arm])
                self.assertTrue(any(f"{key} has no records at all" in x for x in findings), findings)

    def test_one_unscored_record_in_a_run_is_named_by_the_run_counts(self):
        """One record of a run replaced by a non-SCORED record without a search block (the count and
        the seq run intact): the record itself carries nothing to refuse, so the session's per-run
        counts must name it — a search record as a short evaluation count, the holdout as a missing
        holdout, an O search record also as a short ledger."""
        def unscore(rec):
            rec.pop("search")
            rec["outcome"] = "REFUSED_BY_GATE"
        self._refuses(lambda log: unscore(search_of(log, "random_safe", 0, BUDGET - 1)), f"session: (0, 'A') ran {BUDGET - 1} evaluations, not {BUDGET}")
        self._refuses(lambda log: unscore(search_of(log, "map_guided", 0, 2)), f"session: (0, 'B') ran {BUDGET - 1} evaluations, not {BUDGET}")
        self._refuses(lambda log: unscore(o_search(log, 1, 5)), f"session: (1, 'O') ran {BUDGET - 1} evaluations, not {BUDGET}",
                      f"session: (1, 'O') carries {BUDGET - 1} ledger entries, not {BUDGET}")
        for arm, letter in (("random_safe", "A"), ("map_guided", "B"), ("online", "O")):
            self._refuses(lambda log, arm=arm: unscore(holdout_of(log, arm, 2)), f"session: (2, '{letter}') has no champion holdout record")

    def test_a_missing_ledger_entry_count_is_named(self):
        def drop_last_o_search(log):
            log["loop_records"].remove(o_search(log, 2, BUDGET - 1))
            log["loop_records"].insert(1, copy.deepcopy(search_of(log, "random_safe", 0, 0)))
            renumber(log)
        self._refuses(drop_last_o_search, f"carries {BUDGET - 1} ledger entries, not {BUDGET}")

    # -- the search block (B2's rules, kept)
    def test_a_column_move_on_the_random_safe_arm_is_named(self):
        self._refuses(lambda log: search_of(log, "random_safe")["search"]["move"].__setitem__("kind", "column"), "a column move on the random-safe arm")

    def test_a_wrong_seed_or_pair_is_named(self):
        self._refuses(lambda log: o_search(log)["search"].__setitem__("landscape_seed", 1), "the block's seeds are not pair 0's seeds")
        self._refuses(lambda log: o_search(log)["search"].__setitem__("pair", 2), "the block's pair 2 is not 0")

    def test_a_wrong_record_schema_is_named(self):
        self._refuses(lambda log: o_search(log).__setitem__("schema_version", "1.3.0"), "schema_version '1.3.0' is not 1.4.0")
        self._refuses(lambda log: o_search(log).__setitem__("schema", "carto_record"), "schema 'carto_record' is not loop_record")
        self._refuses(lambda log: o_search(log).__setitem__("carto", {}), "a `carto` block belongs to stage B1")

    # -- the identity
    def test_the_identity_1_6_0_fields_are_held(self):
        self._refuses(lambda log: log["app_identity"].__setitem__("schema_version", "1.5.0"), "schema_version '1.5.0' is not 1.6.0")
        self._refuses(lambda log: log["app_identity"].__setitem__("carto_version", "specimen-carto-v1.0"), "carto_version 'specimen-carto-v1.0' is not 'specimen-carto-v1.1'")
        self._refuses(lambda log: log["app_identity"].__setitem__("arms", "RF"), "arms 'RF' is not 'RFO'")
        self._refuses(lambda log: log["app_identity"].__setitem__("b1_map_cost", 0), "b1_map_cost 0 is not the constant 333")
        self._refuses(lambda log: log["app_identity"].__setitem__("probe_budget", 333), "'probe_budget' is declared, but this image issues no probes")
        for k in brec.IDENTITY_B3_KEYS:
            self._refuses(lambda log, k=k: log["app_identity"].pop(k), f"the B3 field {k!r} is absent")
        self._refuses(lambda log: log["app_identity"].__setitem__("pair_count", 2), "the pair slice (0, 2) is not this session's (0, 3)")
        self._refuses(lambda log: log["app_identity"].__setitem__("master_seed", 1), "master_seed is not the frozen one")


class Types(unittest.TestCase):
    """A malformed value must be NAMED, never raise, and nothing may compare, index, sort, hash or
    count it before its type is known."""

    def _refuses(self, mutate, needle: str):
        log = copy.deepcopy(BASE)
        mutate(log)
        try:
            findings = brec.validate_run_log(log, CTX, common=False)
        except Exception as exc:
            self.fail(f"{type(exc).__name__}: {exc}")
        self.assertTrue(findings, "the malformed session was accepted")
        self.assertTrue(any(needle in x for x in findings), f"{needle!r} not named in {findings[:4]}")

    def test_refuses_every_ledger_value_of_the_wrong_type(self):
        wrong = {"a string": 5, "an integer": "1", "a list of integers": "12", "a list of [lut, vector] integer pairs": [[1]],
                 "a list of [address, lut, vector] integer triples": [[1, 2]]}
        for k, _ok, what in brec.LEDGER_TYPES:
            with self.subTest(field=k, given=wrong[what]):
                self._refuses(lambda log, k=k, v=wrong[what]: o_search(log, 1, 1)["search"]["ledger"].__setitem__(k, v), f"ledger.{k} is not {what}")

    def test_a_json_boolean_is_not_a_ledger_integer(self):
        for k, _ok, what in brec.LEDGER_TYPES:
            if what == "an integer":
                with self.subTest(field=k):
                    self._refuses(lambda log, k=k: o_search(log, 1, 1)["search"]["ledger"].__setitem__(k, True), f"ledger.{k} is not an integer")
        self._refuses(lambda log: o_search(log, 1, 1)["search"]["ledger"].__setitem__("intervention", [True]), "ledger.intervention is not a list of integers")
        self._refuses(lambda log: o_search(log, 1, 1)["search"]["ledger"].__setitem__("behaviour_delta", [[True, 1]]), "ledger.behaviour_delta is not a list")

    def test_refuses_a_ledger_that_is_not_an_entry(self):
        self._refuses(lambda log: o_search(log)["search"].__setitem__("ledger", [1]), "the ledger sub-block is not a JSON object")
        self._refuses(lambda log: o_search(log)["search"].__setitem__("ledger", None), "the ledger sub-block is not a JSON object")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].pop("anomalies"), "the ledger entry's keys are not exactly")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("extra", 1), "the ledger entry's keys are not exactly")

    def test_refuses_a_ledger_domain_error(self):
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("move_kind", "probe"), "ledger.move_kind 'probe'")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("confidence", 3), "ledger.confidence 3 is not")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("behaviour_delta", [[6, 0]]), "ledger.behaviour_delta is not a set of distinct")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("behaviour_delta", [[1, 1], [1, 1]]), "ledger.behaviour_delta is not a set of distinct")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("decoded", [[292, 0, 0]]), "ledger.decoded is not a set of distinct")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("intervention", [300]), "ledger.intervention is not 1..4 distinct sorted universe indices")
        self._refuses(lambda log: o_search(log)["search"]["ledger"].__setitem__("anomalies", -1), "a ledger counter is negative")

    def test_refuses_every_block_value_of_the_wrong_type(self):
        wrong = {"a string": 5, "an integer": "1", "a boolean": "yes", "an integer or null": "1"}
        for k, _ok, what in brec.BLOCK_TYPES:
            with self.subTest(field=k):
                self._refuses(lambda log, k=k, v=wrong[what]: o_search(log)["search"].__setitem__(k, v), f"{k} is not {what}")

    def test_refuses_every_identity_value_of_the_wrong_type(self):
        wrong = {"a string": 5, "an integer": "1"}
        for k, _ok, what in brec.IDENTITY_TYPES:
            with self.subTest(field=k):
                self._refuses(lambda log, k=k, v=wrong[what]: log["app_identity"].__setitem__(k, v), f"{k} is not {what}")

    def test_never_raises_on_garbage(self):
        for log in ({}, {"loop_records": 5}, {"loop_records": [1, "x", None]}, {"app_identity": 3, "loop_records": [{"seq": 1, "search": 5}]},
                    {"app_identity": fx.identity(CTX), "loop_records": [{"seq": 1}, {"seq": 2, "arm": "online", "outcome": "SCORED", "search": {"ledger": 1}}]}):
            with self.subTest(log=str(log)[:40]):
                try:
                    findings = brec.validate_run_log(log, CTX, common=False)
                except Exception as exc:
                    self.fail(f"{type(exc).__name__}: {exc}")
                self.assertTrue(findings)
        self.assertEqual(brec.validate_run_log([], CTX, common=False), ["session: not a JSON object"])


class ContextRefusals(unittest.TestCase):
    """A plan or prediction that is not the shape the validator reads is refused by name before any
    record is judged — never a finding about a board, never a Python exception of another kind."""

    def _refuses(self, mutate_plan=None, mutate_pred=None, first=0, count=PAIRS, needle: str = ""):
        plan, pred = copy.deepcopy(PLAN), copy.deepcopy(PRED)
        if mutate_plan:
            mutate_plan(plan)
        if mutate_pred:
            mutate_pred(pred)
        with self.assertRaises(brec.ContextError) as cm:
            brec.context_from(plan, pred, first, count)
        self.assertIn(needle, str(cm.exception))

    def test_accepts_the_fixture_and_binds_its_seeds(self):
        self.assertEqual(CTX.seeds, SEEDS)
        self.assertEqual((CTX.budget, CTX.pairs_total, CTX.fitness, CTX.map_sha256), (BUDGET, PAIRS, "F1", MAP_SHA))
        self.assertEqual(CTX.predicted_o(1)["final_state_sha256"], PRED["pairs"][1]["runs"]["O"]["final_state_sha256"])
        q = brec.context_from(make_plan(session="B3Q"), PRED, 0, PAIRS)
        self.assertEqual(q.budget, BUDGET)

    def test_refuses_a_wrong_schema_version_or_lifecycle(self):
        self._refuses(mutate_plan=lambda p: p.__setitem__("schema", "b2_plan"), needle="the plan's schema 'b2_plan' is not b3_plan")
        self._refuses(mutate_pred=lambda p: p.__setitem__("schema", "b2_prediction"), needle="the prediction's schema 'b2_prediction' is not b3_prediction")
        self._refuses(mutate_plan=lambda p: p.__setitem__("schema_version", "1.0.0"), needle="the plan's schema_version '1.0.0' is not 2.0.0")
        self._refuses(mutate_pred=lambda p: p.__setitem__("lifecycle", 1), needle="the prediction's lifecycle 1 is not 2")
        self._refuses(mutate_plan=lambda p: p.__setitem__("budget_per_arm", True), needle="the plan: budget_per_arm is not an integer")
        self._refuses(mutate_plan=lambda p: p.__setitem__("budget_per_arm", 0), needle="the plan's budget_per_arm 0 is not positive")

    def test_refuses_a_plan_and_prediction_that_disagree(self):
        self._refuses(mutate_pred=lambda p: p.__setitem__("budget_per_arm", BUDGET + 1), needle=f"the prediction's budget_per_arm {BUDGET + 1} is not the plan's {BUDGET}")
        self._refuses(mutate_pred=lambda p: p.__setitem__("fitness", "F2"), needle="the prediction's fitness 'F2' is not the plan's 'F1'")
        self._refuses(mutate_pred=lambda p: p["pairs"].pop(), needle=f"the prediction has {PAIRS - 1} pairs, the plan {PAIRS}")
        self._refuses(mutate_pred=lambda p: p.__setitem__("carto_version", "x"), needle="the prediction's carto_version 'x' is not the plan's")
        self._refuses(mutate_pred=lambda p: p.__setitem__("b1_map_cost", 0), needle="the prediction's b1_map_cost 0 is not the plan's 333")

    def test_refuses_a_prediction_pair_that_is_not_the_frozen_shape(self):
        self._refuses(mutate_pred=lambda p: p["pairs"][1].__setitem__("arm_order", ["R", "F", "O"]), needle="the prediction's pair 1: arm_order ['R', 'F', 'O'] is not the frozen sequence's FOR")
        self._refuses(mutate_pred=lambda p: p["pairs"][2]["runs"]["O"]["ledger"].pop(), needle=f"the prediction's pair 2's O run: {BUDGET - 1} ledger entries, the budget is {BUDGET}")
        self._refuses(mutate_pred=lambda p: p["pairs"][2]["runs"]["O"].__setitem__("ledger_schema_version", "1.0.0"), needle="ledger_schema_version '1.0.0' is not 1.1.0")
        self._refuses(mutate_pred=lambda p: p["pairs"][2]["runs"]["O"].__setitem__("final_state_sha256", "abc"), needle="final_state_sha256 is not 64 hex")
        self._refuses(mutate_pred=lambda p: p["pairs"][2]["runs"].pop("O"), needle="the prediction's pair 2: no run for arm O")
        self._refuses(mutate_pred=lambda p: p["pairs"][0].__setitem__("landscape_seed", "1000"), needle="the prediction's pair 0: landscape_seed is not an integer")
        self._refuses(mutate_pred=lambda p: p["pairs"][0].__setitem__("operator_seed", 2 ** 32), needle="a seed is outside 0..2^32-1")
        self._refuses(mutate_pred=lambda p: p["pairs"][0].__setitem__("pair", 1), needle="the prediction's pair 0 carries pair 1")

    def test_refuses_a_slice_outside_the_experiment(self):
        self._refuses(first=2, count=2, needle="the slice (2, 2) does not lie inside the experiment's 3 pairs")
        self._refuses(first=0, count=0, needle="the slice (0, 0)")
        self._refuses(first=-1, count=1, needle="the slice (-1, 1)")

    def test_refuses_inputs_that_are_not_objects(self):
        with self.assertRaises(brec.ContextError):
            brec.context_from([], PRED, 0, PAIRS)
        with self.assertRaises(brec.ContextError):
            brec.context_from(PLAN, None, 0, PAIRS)


if __name__ == "__main__":
    unittest.main()
