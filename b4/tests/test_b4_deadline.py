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
import b4_sim_schema as sc  # noqa: E402
from b4_deadline import Deadline, StopWork  # noqa: E402
from b4_observe import Memo  # noqa: E402
from b4_test_fixtures import InjectingPort, mechanics_fabric, v02_task  # noqa: E402


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

    def test_the_record_is_one_monotonic_sample(self):
        """The owner's review of 2026-10-19 (finding 2): with the clock crossing the deadline between two samples
        (1059.990 then 1060.010 after a start of 1000.000) a record of several samples said elapsed 59.99, expired true,
        first expiry 60.01 — refused by the record's own validator. Every record is now one sample: consistent at the
        boundary, the first expiry never later than the elapsed time beside it, the same under check()."""
        values = iter([1000.0, 1059.990, 1060.010, 1060.030, 1060.050, 1060.070])
        d = Deadline(60, clock=lambda: next(values))
        r1, r2, r3 = d.record(), d.record(), d.record()
        self.assertEqual((r1["elapsed_s"], r1["expired"], r1["first_expired_at_s"]), (59.99, False, None))
        self.assertEqual((r2["elapsed_s"], r2["expired"], r2["first_expired_at_s"]), (60.01, True, 60.01))
        self.assertEqual((r3["elapsed_s"], r3["expired"], r3["first_expired_at_s"]), (60.03, True, 60.01), "the first expiry is kept")
        for r in (r1, r2, r3):
            self.assertEqual(sc.deadline_findings(r, 60), [], r)
        with self.assertRaises(StopWork) as cm:
            d.check()
        self.assertIn("after 60.050 s", str(cm.exception), "the check's message is the sample that expired it")
        values = iter([1000.0, 1060.010, 1060.030])
        d = Deadline(60, clock=lambda: next(values))
        with self.assertRaises(StopWork):
            d.check()
        self.assertAlmostEqual(d.first_expired_at, 60.01, places=6, msg="the first expiry is the sample that expired the check, not a later one")
        r = d.record()
        self.assertEqual((r["elapsed_s"], r["expired"], r["first_expired_at_s"], r["checks"]), (60.03, True, 60.01, 1))
        self.assertEqual(sc.deadline_findings(r, 60), [])

    def test_only_a_positive_int(self):
        for bad in (0, -1, True, 1.5, "10", None):
            with self.assertRaises(ValueError, msg=repr(bad)):
                Deadline(bad)


class TheMemo(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = v02_task(7, cls.fab)

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
