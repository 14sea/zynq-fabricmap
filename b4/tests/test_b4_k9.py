"""b4/host/b4_k9.py — the fixed comparison set by hand (64 backgrounds; 32 forced pairs per slice-wide address, 64 per
per-element address; the applicable denominators 384 / 384 / 32 / 32 / 16 / 32 / 32), applicability from the configuration
and never from the traces, the differences on hand grids (value, presence, none), the whole computation on the formal
model for the exposed seeds 7 and 8 (the denominators equal), the memo's calls vs hits, the offline recomputation, the
deadline between pairs. Mechanics only: no coverage value is compared across seeds or read as a result. No skip."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_k9 as k9  # noqa: E402
import b4_landscape as bl  # noqa: E402
from b4_deadline import StopWork  # noqa: E402

HAND_APPLICABLE = {"ff_init": 384, "ff_srval": 384, "ce_mode": 32, "sr_mode": 32, "sr_kind": 16, "storage_kind": 32, "clock_mode": 32}


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = bl.make_task(7, cls.m.addresses)


class ThePanel(Base):
    def test_64_backgrounds_32_mode_combinations_times_all_zero_all_one(self):
        bgs = k9.panel(self.m)
        self.assertEqual(len(bgs), 64)
        self.assertEqual(bgs, sorted(set(bgs)))
        mode_bits = [self.m.genome_bit(self.m.address_of(None, s)) for s in k9.MODE_SEMANTICS]
        elem_bits = [self.m.genome_bit(self.m.address_of(e, s)) for e in k9.ELEMENTS for s in k9.PER_ELEMENT]
        combos = set()
        for g in bgs:
            combos.add(tuple((g >> b) & 1 for b in mode_bits))
            vals = {(g >> b) & 1 for b in elem_bits}
            self.assertEqual(len(vals), 1, "INIT / SRVAL all 0 or all 1")
            self.assertEqual(g >> 21, 0)
        self.assertEqual(len(combos), 32)

    def test_forced_pairs_by_hand(self):
        pairs = k9.forced_pairs(self.m, k9.panel(self.m))
        self.assertEqual(len(pairs), 5 * 32 + 16 * 64)
        per_bit = {}
        for p in pairs:
            per_bit[p["bit"]] = per_bit.get(p["bit"], 0) + 1
            self.assertEqual(p["g1"], p["g0"] | (1 << p["bit"]))
            self.assertEqual(p["g0"] & (1 << p["bit"]), 0)
            self.assertTrue(all(((g | (1 << p["bit"])) == p["g1"]) for g in p["backgrounds"]), "every listed background forces to this pair")
        for bit, c in per_bit.items():
            self.assertEqual(c, 32 if self.m.entries[self.m.addresses[bit]].element is None else 64, bit)
        self.assertEqual(pairs, sorted(pairs, key=lambda p: (p["bit"], p["g0"], p["g1"])))
        self.assertEqual(len({(p["g0"], p["g1"]) for p in pairs}), len(pairs), "de-duplicated")

    def test_applicability_denominators_by_hand_and_from_the_configuration(self):
        pairs = k9.forced_pairs(self.m, k9.panel(self.m))
        counts = {s: 0 for s in k9.SEMANTICS}
        for p in pairs:
            a = k9.applicability(self.fab, p)
            if a["applicable"]:
                counts[p["semantic"]] += 1
                if p["semantic"] in k9.PER_ELEMENT:
                    self.assertEqual(a["scope"], [p["element"]])
                elif p["semantic"] == "storage_kind":
                    self.assertEqual(a["scope"], list(k9.ELEMENTS)); self.assertTrue(a["presence_allowed"])
                else:
                    self.assertTrue(a["scope"])
            else:
                self.assertIn("latch", a["reason"])
                self.assertEqual(a["scope"], [])
        self.assertEqual(counts, HAND_APPLICABLE)


class Differences(unittest.TestCase):
    def test_on_hand_grids(self):
        g0 = [[0, 1, None, 0, 0, 0, 0, 0], [1, 1, None, 0, 0, 0, 0, 0]]
        g1 = [[0, 0, None, 0, 0, 0, 0, 0], [1, 1, 1, 0, 0, 0, 0, 0]]
        self.assertEqual(k9.differences(g0, g1, ["A5FF"]), [{"step": 0, "element": "A5FF", "kind": "value", "q0": 1, "q1": 0}])
        self.assertEqual(k9.differences(g0, g1, ["BFF"]), [{"step": 1, "element": "BFF", "kind": "presence", "q0": None, "q1": 1}])
        self.assertEqual(k9.differences(g0, g1, ["AFF", "DFF"]), [], "identical in scope: no difference, still a pair")
        self.assertEqual(len(k9.differences(g0, g1, list(k9.ELEMENTS))), 2)
        with self.assertRaises(ValueError):
            k9.differences(g0, g1[:1], ["AFF"])


class TheComputation(Base):
    def test_the_formal_model_end_to_end_on_an_exposed_seed(self):
        port = ex.ObservationPort(self.fab)
        r = k9.coverage(self.task, port, self.m, self.fab)
        self.assertTrue(r["complete"]); self.assertIsNone(r["stopped"])
        self.assertEqual((r["pairs_total"], r["pairs_done"]), (1184, 1184))
        s = r["summary"]["per_semantic"]
        self.assertEqual({k: v["applicable"] for k, v in s.items()}, HAND_APPLICABLE)
        for k, v in s.items():
            self.assertTrue(v["assessable"]); self.assertLessEqual(v["covered"], v["applicable"])
            self.assertEqual(v["fraction"], v["covered"] / v["applicable"])
        self.assertTrue(s["ff_init"]["conditional_on_A8"]); self.assertFalse(s["ff_srval"]["conditional_on_A8"])
        for k, v in s.items():
            self.assertTrue(v["positive_control"], f"{k}: covered > 0 on the exposed seed is a positive control — ff_init counts as the other six do")
        self.assertTrue(r["summary"]["all_seven_positive_controls"]); self.assertEqual(r["summary"]["semantics_without_positive_control"], [])
        self.assertEqual(s["ff_init"]["covered"], 384, "INIT differs at the init readout for every applicable element (atomic init, conditional on A8)")
        self.assertEqual(s["storage_kind"]["covered"], 32, "a latch endpoint removes the x5FF readouts: a presence difference")
        self.assertEqual(r["memo"]["port_calls"], port.calls)
        self.assertEqual(r["memo"]["port_calls"] + r["memo"]["cache_hits"], r["logical_observations"], "every applicable pair made two logical observations")
        self.assertEqual(len(r["observations"]), r["memo"]["unique_observations"])
        self.assertTrue(all(o["fixture"] is False and o["fabric_kind"] == "truth" for o in r["observations"]))
        for p in r["pairs"]:
            if p["applicable"]:
                self.assertEqual(p["covered"], bool(p["differences"]))
                self.assertIsNotNone(p["obs0"]); self.assertIsNotNone(p["obs1"])
            else:
                self.assertIsNone(p["covered"]); self.assertEqual(p["differences"], [])
        identical = [p for p in r["pairs"] if p["applicable"] and not p["covered"]]
        self.assertTrue(identical, "some applicable pair has identical traces under this stimulus")
        self.assertIn(identical[0]["semantic"], [u["semantic"] for u in r["summary"]["uncovered_applicable_pairs"]], "it stays in the denominator and is listed")
        json.dumps(r, allow_nan=False)
        self.assertEqual(k9.recompute(r, self.task, self.fab), [])

    def test_summarise_by_hand_an_empty_denominator_is_not_assessable_and_never_a_positive_control(self):
        """Hand pairs over the 21 addresses: sr_kind has no applicable pair (fraction None, not assessable, no positive control, so
        not all seven); clock_mode is applicable but never covered (fraction 0.0, assessable, no positive control); the other
        five — ff_init among them, counted as the others are — are covered once each (fraction 1.0, positive control)."""
        pairs = []
        for a in self.m.addresses:
            sem = self.m.entries[a].semantic
            applicable = sem != "sr_kind"
            covered = (sem != "clock_mode") if applicable else None
            pairs.append({"semantic": sem, "address": a, "applicable": applicable, "covered": covered, "g0": 0, "g1": 1})
        s = k9.summarise(pairs, self.m)
        ps = s["per_semantic"]
        self.assertEqual((ps["sr_kind"]["applicable"], ps["sr_kind"]["fraction"], ps["sr_kind"]["assessable"], ps["sr_kind"]["positive_control"]), (0, None, False, False))
        self.assertGreater(ps["sr_kind"]["not_applicable"], 0)
        self.assertEqual((ps["clock_mode"]["fraction"], ps["clock_mode"]["assessable"], ps["clock_mode"]["positive_control"]), (0.0, True, False))
        for sem in ("ff_init", "ff_srval", "ce_mode", "sr_mode", "storage_kind"):
            self.assertEqual((ps[sem]["fraction"], ps[sem]["assessable"], ps[sem]["positive_control"]), (1.0, True, True), sem)
            self.assertEqual(ps[sem]["covered"], ps[sem]["applicable"])
        self.assertFalse(s["all_seven_positive_controls"])
        self.assertEqual(s["semantics_without_positive_control"], ["sr_kind", "clock_mode"], "in the order of the seven")
        self.assertEqual(sorted(u["semantic"] for u in s["uncovered_applicable_pairs"]), ["clock_mode"] * ps["clock_mode"]["applicable"])
        for a, c in s["per_address"].items():
            self.assertEqual(c["fraction"], None if c["semantic"] == "sr_kind" else (0.0 if c["semantic"] == "clock_mode" else 1.0))

    def test_a_refusal_inside_a_pair_carries_the_partial_and_a_truncated_complete_record_is_named(self):
        """F6 of the owner's review: a DOMAIN at the second observation raises with `k9_partial` — the first observation and
        the pairs before are kept, `invalid` names the pair; F3: a complete record with the pairs removed is named by
        `recompute` and by `canonical_findings`."""
        from b4_test_fixtures import InjectingPort
        port = InjectingPort(self.fab, 2)
        with self.assertRaises(fm.DomainRefusal) as cm:
            k9.coverage(self.task, port, self.m, self.fab)
        p = cm.exception.k9_partial
        self.assertEqual((p["complete"], p["stopped"], p["pairs_done"], len(p["observations"]), p["summary"]), (False, None, 0, 1, None))
        self.assertEqual((p["invalid"]["pair_index"], p["invalid"]["exception"]), (0, "DomainRefusal"))
        self.assertEqual(port.calls, 2, "nothing was observed after the refusal")
        self.assertEqual(k9.recompute(p, self.task, self.fab), [], "a partial record recomputes clean")
        port = InjectingPort(self.fab, 3, KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt) as cm:
            k9.coverage(self.task, port, self.m, self.fab)
        p = cm.exception.k9_partial
        self.assertEqual((p["invalid"], p["stopped"]["before_pair_index"], p["pairs_done"], len(p["observations"])), (None, 1, 1, 2), "an interrupt is a stop, not an invalid event")
        full = k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab)
        bad = json.loads(json.dumps(full)); bad["pairs"] = []; bad["pairs_done"] = 0; bad["summary"] = k9.summarise([], self.m); bad["logical_observations"] = 0
        self.assertTrue(any("fixed set has 1184" in f for f in k9.recompute(bad, self.task, self.fab)), "an emptied complete record is named")
        bad = json.loads(json.dumps(full)); bad["pairs"] = bad["pairs"][:10] + bad["pairs"][11:]; bad["pairs_done"] -= 1
        self.assertTrue(any("not the fixed set's pair" in f for f in k9.canonical_findings(bad, self.m)), "an omitted pair shifts the sequence and is named")
        bad = json.loads(json.dumps(full)); bad["pairs"].append(bad["pairs"][0]); bad["pairs_done"] += 1
        self.assertTrue(any("more than the fixed set" in f for f in k9.recompute(bad, self.task, self.fab)), "a duplicated pair is named")

    def test_the_denominators_do_not_depend_on_the_seed(self):
        r7 = k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab)
        r8 = k9.coverage(bl.make_task(8, self.m.addresses), ex.ObservationPort(self.fab), self.m, self.fab)
        a7 = {k: v["applicable"] for k, v in r7["summary"]["per_semantic"].items()}
        a8 = {k: v["applicable"] for k, v in r8["summary"]["per_semantic"].items()}
        self.assertEqual(a7, a8)
        self.assertEqual([(p["applicable"], p["scope"]) for p in r7["pairs"]], [(p["applicable"], p["scope"]) for p in r8["pairs"]])

    def test_recompute_names_a_tampered_record(self):
        r = k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab)
        bad = json.loads(json.dumps(r))
        p = next(p for p in bad["pairs"] if p["applicable"] and p["covered"])
        p["covered"] = False; p["differences"] = []
        self.assertTrue(any("coverage recomputed" in f for f in k9.recompute(bad, self.task, self.fab)))
        bad = json.loads(json.dumps(r))
        o = bad["observations"][3]
        o["q_grid"][1][0] = 1 - o["q_grid"][1][0] if o["q_grid"][1][0] in (0, 1) else 0
        self.assertTrue(any("does not hash" in f for f in k9.recompute(bad, self.task, self.fab)))
        bad = json.loads(json.dumps(r))
        q = next(p for p in bad["pairs"] if not p["applicable"])
        q["applicable"] = True
        self.assertTrue(any("applicability" in f for f in k9.recompute(bad, self.task, self.fab)))
        bad = json.loads(json.dumps(r))
        bad["summary"]["per_semantic"]["sr_kind"]["applicable"] = 32
        self.assertTrue(any("summary" in f for f in k9.recompute(bad, self.task, self.fab)))

    def test_the_deadline_stops_between_pairs_and_the_partial_is_kept(self):
        budget = {"left": 5}

        def check():
            if budget["left"] == 0:
                raise StopWork("expired")
            budget["left"] -= 1
        r = k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab, check=check)
        self.assertEqual((r["complete"], r["pairs_done"], r["stopped"]["before_pair_index"]), (False, 5, 5))
        self.assertIsNone(r["summary"], "nothing is judged on a partial set")
        full = k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab, check=lambda: None)
        self.assertEqual([p["covered"] for p in r["pairs"]], [p["covered"] for p in full["pairs"][:5]], "the chunk computed is the unchunked value")
        self.assertEqual(full["summary"], k9.coverage(self.task, ex.ObservationPort(self.fab), self.m, self.fab)["summary"], "a never-raising check changes nothing")
        self.assertEqual(k9.recompute(r, self.task, self.fab), [])
        bad = json.loads(json.dumps(r)); bad["summary"] = {}
        self.assertTrue(any("incomplete" in f for f in k9.recompute(bad, self.task, self.fab)))


if __name__ == "__main__":
    unittest.main()
