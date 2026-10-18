"""b4/host/b4_k10.py — the two fixed backgrounds (by hand from the salted generator's first call; equal backgrounds kept),
2 x 210 four-corner units on the formal model (exposed seed 7), every corner kept and recomputable, the memo's calls vs
hits, tau's boundary through the real classifier, a DOMAIN refusal INSIDE the real `four_corner` escalated to
`K10Invalid` with the corners obtained kept, the deadline between units. Mechanics only; no outcome is read as a result. No skip."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_k10 as k10  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_stats as st  # noqa: E402
from b4_deadline import StopWork  # noqa: E402
from b4_rng import Rng  # noqa: E402


class RefusingPort(ex.ObservationPort):
    """Refuses with DOMAIN for one exact configuration (genome), the real fabric otherwise."""

    def __init__(self, fabric, refuse_genome: int):
        super().__init__(fabric)
        self.refuse = ex.genome_to_config(refuse_genome, fabric.mapping.addresses)

    def observe(self, config, stimulus):
        self.calls += 1
        if config == self.refuse:
            raise fm.DomainRefusal()
        return self._observe(config, stimulus)


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = bl.make_task(7, cls.m.addresses)


class Backgrounds(unittest.TestCase):
    def test_by_hand_from_the_salted_generator_s_first_call(self):
        want = Rng((7 ^ 0x4C0A4E55) & 0xFFFFFFFF).uniform(1 << 21)
        self.assertEqual(k10.backgrounds(7), [0, want])
        self.assertEqual(k10.SALT, 0x4C0A4E55)
        self.assertNotEqual(k10.backgrounds(7)[1], k10.backgrounds(8)[1])
        for bad in (True, -1, 1 << 32, 7.0):
            with self.assertRaises(ValueError):
                k10.backgrounds(bad)

    def test_equal_backgrounds_are_both_kept(self):
        class Zero:
            def __init__(self, seed):
                pass
            def uniform(self, n):
                return 0
        with mock.patch.object(k10, "Rng", Zero):
            self.assertEqual(k10.backgrounds(7), [0, 0])


class TheComputation(Base):
    def test_the_formal_model_end_to_end_on_an_exposed_seed(self):
        port = ex.ObservationPort(self.fab)
        r = k10.seed_k10(self.task, port)
        self.assertTrue(r["complete"]); self.assertIsNone(r["stopped"]); self.assertIsNone(r["invalid"])
        self.assertEqual((r["units_total"], len(r["units"]), r["tau"]), (420, 420, 2))
        self.assertEqual(r["backgrounds"], k10.backgrounds(7))
        self.assertEqual(r["comparable_pairs"], 420); self.assertEqual(r["not_comparable_pairs"], 0)
        self.assertIn(r["outcome"], st.OUTCOMES)
        self.assertEqual(r["outcome"], st.classify(r["max_abs_index"], 2))
        self.assertEqual(r["memo"]["port_calls"], port.calls)
        self.assertEqual(r["logical_corners"], 1680)
        self.assertEqual(r["memo"]["port_calls"] + r["memo"]["cache_hits"], 1680, "every corner was a logical observation")
        self.assertLess(r["memo"]["port_calls"], 1680, "repeated corner configurations are served from the memo")
        pairs = {(u["background_index"], u["a"], u["b"]) for u in r["units"]}
        self.assertEqual(len(pairs), 420)
        self.assertTrue(all(u["a"] < u["b"] for u in r["units"]))
        u = r["units"][0]
        self.assertEqual(u["index"], u["corners"]["11"]["score"] - u["corners"]["10"]["score"] - u["corners"]["01"]["score"] + u["corners"]["00"]["score"])
        json.dumps(r, allow_nan=False)
        self.assertEqual(k10.recompute(r, self.task), [])

    def test_recompute_names_a_tampered_record(self):
        r = k10.seed_k10(self.task, ex.ObservationPort(self.fab))
        bad = json.loads(json.dumps(r)); bad["units"][5]["corners"]["11"]["score"] += 1
        self.assertTrue(any("score recomputed" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(r)); bad["units"][5]["index"] += 1
        self.assertTrue(any("index" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(r)); bad["outcome"] = st.NOT_ASSESSABLE
        self.assertTrue(any("outcome" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(r)); bad["observations"][0]["q_grid"][1][0] = None
        self.assertTrue(any("does not hash" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(r)); bad["backgrounds"][1] ^= 1
        self.assertTrue(any("backgrounds" in f for f in k10.recompute(bad, self.task)))

    def test_tau_s_boundary_through_the_real_classifier(self):
        self.assertEqual(st.classify(2, 2), st.NONZERO_BELOW_THRESHOLD, "exactly 2 is not interacting")
        self.assertEqual(st.classify(3, 2), st.INTERACTING)
        self.assertEqual(st.classify(0, 2), st.NO_INTERACTION_SEEN)
        self.assertEqual(st.classify(None, 2), st.NOT_ASSESSABLE)

    def test_a_domain_refusal_inside_the_real_four_corner_is_invalid_with_the_corners_kept(self):
        bg0 = 0
        refuse = bg0 | (1 << 3) | (1 << 5)                 # the "11" corner of the unit (a = 3, b = 5) in background 0
        port = RefusingPort(self.fab, refuse)
        probe = st.four_corner(lambda g: 0 if g != refuse else (_ for _ in ()).throw(fm.DomainRefusal()), bg0, 3, 5)
        self.assertFalse(probe["comparable"], "b4_stats.four_corner itself absorbs DOMAIN into comparable = False — the driver must not")
        with self.assertRaises(k10.K10Invalid) as cm:
            k10.seed_k10(self.task, port)
        p = cm.exception.partial
        self.assertFalse(p["complete"]); self.assertIsNotNone(p["invalid"])
        self.assertEqual(p["invalid"]["illegal_corners"], ["11"])
        last = p["units"][-1]
        self.assertEqual((last["background_index"], last["a"], last["b"], last["comparable"]), (0, 3, 5, False))
        self.assertEqual(p["invalid"]["unit_index"], len(p["units"]) - 1)
        self.assertTrue(all(u["comparable"] for u in p["units"][:-1]), "the units before it are kept, comparable")
        self.assertIsNone(last["corners"]["11"]["obs"]); self.assertIsNotNone(last["corners"]["00"]["obs"], "the corners obtained are kept")
        self.assertLess(len(p["units"]), 420)

    def test_no_corner_is_observed_after_the_first_refused_one(self):
        """F5 of the owner's review: a DOMAIN at the first corner of the first unit leaves port calls at 1 (not 4), no
        observation kept, the unit recorded with its refused corner named; at the second corner: 2 calls, 1 observation."""
        from b4_test_fixtures import InjectingPort
        for at, obs_kept, corner in ((1, 0, "00"), (2, 1, "01"), (4, 3, "11")):
            port = InjectingPort(self.fab, at)
            with self.assertRaises(k10.K10Invalid) as cm:
                k10.seed_k10(self.task, port)
            p = cm.exception.partial
            self.assertEqual(port.calls, at, f"refused at call {at}: no further corner observed")
            self.assertEqual((len(p["observations"]), len(p["units"]), p["units"][0]["comparable"], p["units"][0]["illegal_corners"]), (obs_kept, 1, False, [corner]))
            self.assertIsNone(p["units"][0]["corners"][corner]["score"]); self.assertIsNone(p["units"][0]["corners"][corner]["obs"])
            self.assertEqual((p["invalid"]["unit_index"], p["invalid"]["exception"], p["complete"], p["outcome"]), (0, "DomainRefusal", False, None))
            self.assertEqual(k10.recompute(p, self.task), [], "the partial recomputes clean")
        port = InjectingPort(self.fab, 6, KeyboardInterrupt())
        with self.assertRaises(KeyboardInterrupt) as cm:
            k10.seed_k10(self.task, port)
        p = cm.exception.k10_partial
        self.assertEqual((p["invalid"], p["stopped"]["before_unit_index"], len(p["units"]), len(p["observations"])), (None, 1, 1, 5), "an interrupt inside the second unit: a stop, the first unit kept")
        port = InjectingPort(self.fab, 6, ex.SourceRefusal("injected"))
        with self.assertRaises(ex.SourceRefusal) as cm:
            k10.seed_k10(self.task, port)
        self.assertEqual(cm.exception.k10_partial["invalid"]["exception"], "SourceRefusal")

    def test_duplicated_or_missing_units_in_a_complete_record_are_named(self):
        """F3 of the owner's review: the fixed comparison set is enforced — the first unit repeated 420 times, a unit dropped,
        or an empty complete record are all named by `recompute`."""
        full = k10.seed_k10(self.task, ex.ObservationPort(self.fab))
        self.assertEqual(k10.recompute(full, self.task), [])
        self.assertEqual([(u["background_index"], u["a"], u["b"]) for u in full["units"]], k10.canonical_units())
        bad = json.loads(json.dumps(full)); bad["units"] = [json.loads(json.dumps(bad["units"][0])) for _ in range(420)]
        m, counts = st.seed_max(bad["units"]); bad.update(max_abs_index=m, comparable_pairs=counts["comparable_pairs"], not_comparable_pairs=counts["not_comparable_pairs"], outcome=st.classify(m, bad["tau"]))
        self.assertTrue(any("not the fixed set's unit 1" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(full)); del bad["units"][5]; bad["logical_corners"] -= 4
        self.assertTrue(any("fixed set has 420" in f for f in k10.recompute(bad, self.task)))
        bad = json.loads(json.dumps(full)); bad["units"] = []; bad["logical_corners"] = 0
        self.assertTrue(any("fixed set has 420" in f for f in k10.recompute(bad, self.task)))

    def test_the_deadline_stops_between_units_and_the_partial_is_kept(self):
        budget = {"left": 7}

        def check():
            if budget["left"] == 0:
                raise StopWork("expired")
            budget["left"] -= 1
        r = k10.seed_k10(self.task, ex.ObservationPort(self.fab), check=check)
        self.assertEqual((r["complete"], len(r["units"]), r["stopped"]["before_unit_index"], r["outcome"], r["max_abs_index"]), (False, 7, 7, None, None))
        full = k10.seed_k10(self.task, ex.ObservationPort(self.fab), check=lambda: None)
        self.assertEqual([u["index"] for u in r["units"]], [u["index"] for u in full["units"][:7]])
        self.assertEqual(full["units"], k10.seed_k10(self.task, ex.ObservationPort(self.fab))["units"], "a never-raising check changes nothing")
        self.assertEqual(k10.recompute(r, self.task), [])


if __name__ == "__main__":
    unittest.main()
