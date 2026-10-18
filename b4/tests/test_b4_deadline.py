"""b4/host/b4_deadline.py and b4/host/b4_observe.py — the soft monotonic deadline (a fake clock, no sleep) and the per-seed
observation memo (true calls vs hits, the source identity held, DOMAIN propagated). No skip."""
from __future__ import annotations

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
import b4_landscape as bl  # noqa: E402
from b4_deadline import Deadline, StopWork  # noqa: E402
from b4_observe import Memo  # noqa: E402
from b4_test_fixtures import InjectingPort, mechanics_fabric  # noqa: E402


class FakeClock:
    def __init__(self):
        self.t = 100.0

    def __call__(self):
        return self.t


class TheDeadline(unittest.TestCase):
    def test_monotonic_soft_and_recorded(self):
        c = FakeClock()
        d = Deadline(10, clock=c)
        d.check(); c.t += 9.999; d.check()
        self.assertFalse(d.expired())
        c.t += 0.001
        with self.assertRaises(StopWork):
            d.check()
        self.assertEqual(d.checks, 3)
        rec = d.record()
        self.assertEqual((rec["seconds"], rec["expired"], rec["clock"]), (10, True, "time.monotonic"))
        self.assertAlmostEqual(rec["first_expired_at_s"], 10.0)
        with self.assertRaises(StopWork):
            d.check()

    def test_only_a_positive_int(self):
        for bad in (0, -1, True, 1.5, "10", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                Deadline(bad)


class TheMemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = bl.make_task(7, cls.m.addresses)

    def test_hits_change_the_call_count_only(self):
        port = ex.ObservationPort(self.fab)
        memo = Memo(port)
        id0, g0, hit0 = memo.observe(0, self.task.stimulus)
        id1, g1, hit1 = memo.observe(0, self.task.stimulus)
        id2, g2, hit2 = memo.observe(1, self.task.stimulus)
        self.assertEqual((id0, id1, id2, hit0, hit1, hit2), (0, 0, 1, False, True, False))
        self.assertEqual(g0, g1)
        self.assertEqual((memo.calls, memo.hits, port.calls), (2, 1, 2))
        recs = memo.records()
        self.assertEqual([r["genome"] for r in recs], [0, 1])
        self.assertEqual(recs[0]["q_grid"], g0)
        self.assertEqual(recs[0]["trace_sha256"], ex.sha256_json(g0))
        self.assertEqual((recs[0]["fixture"], recs[0]["fabric_kind"]), (False, "truth"))
        self.assertEqual(memo.summary()["unique_observations"], 2)
        g0[0][0] = 7
        self.assertNotEqual(memo.records()[0]["q_grid"][0][0], 7, "the caller's copy is not the memo's record")
        _, _, hit = memo.observe(0, self.task.holdout_stimulus)
        self.assertFalse(hit, "another stimulus is another key")

    def test_domain_propagates_and_a_bad_genome_is_refused(self):
        memo = Memo(InjectingPort(self.fab, 1))
        with self.assertRaises(fm.DomainRefusal):
            memo.observe(0, self.task.stimulus)
        self.assertEqual(memo.records(), [], "a refused observation is not a record")
        with self.assertRaises(ValueError):
            Memo(ex.ObservationPort(self.fab)).observe(1 << 21, self.task.stimulus)

    def test_the_source_identity_is_held(self):
        memo = Memo(ex.ObservationPort(self.fab))
        memo.observe(0, self.task.stimulus)
        memo.port = ex.ObservationPort(mechanics_fabric())
        with self.assertRaises(ex.SourceRefusal):
            memo.observe(1, self.task.stimulus)


if __name__ == "__main__":
    unittest.main()
