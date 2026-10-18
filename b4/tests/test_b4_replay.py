"""b4/host/b4_replay.py — the ledger replay is EXACT and fail-closed: a complete R / O / F run and a terminated run
replay with no finding; every tamper — a fitness, a q cell, a best-so-far, a population at a generation close, a map
commitment, a removed holdout, a terminated run marked completed, a terminal count / commitment / generator state —
is named. No skip."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
from b4_test_fixtures import InjectingPort  # noqa: E402


class Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        m, h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(m, h.with_reading("clock_mode", "not_inverted", "not_inverted", "mechanics", context="latch"))
        cls.task = bl.make_task(7, m.addresses)
        cls.o = be.run("O", cls.task, ex.ObservationPort(cls.fab), 11, 24).as_dict()
        cls.t = be.run("O", cls.task, InjectingPort(cls.fab, refuse_at=6), 11, 24).as_dict()

    def named(self, edit, needle: str, base=None):
        d = copy.deepcopy(base if base is not None else self.o)
        edit(d)
        f = br.replay(d, self.task)
        self.assertTrue(any(needle in x for x in f), f"{needle!r} not among {f}")

    def test_the_clean_runs_replay_with_no_finding(self):
        self.assertEqual(br.replay(self.o, self.task), [])
        self.assertEqual(br.replay(self.t, self.task), [])
        with self.assertRaises(AssertionError):
            self.assertEqual(br.replay(self.o, bl.make_task(8, self.task.addresses)), [])

    def test_every_tamper_is_named(self):
        self.named(lambda d: d["ledger"][3].__setitem__("fitness", d["ledger"][3]["fitness"] + 1), "fitness recomputed")
        self.named(lambda d: d["ledger"][2]["q_grid"][1].__setitem__(0, 1 - (d["ledger"][2]["q_grid"][1][0] or 0)), "does not hash to the recorded trace digest")
        self.named(lambda d: d["ledger"][3].__setitem__("best", 0), "best-so-far")
        self.named(lambda d: d["generation_closes"][0]["population"][0].__setitem__(1, 999), "the population after selection differs")
        self.named(lambda d: d["ledger"][4].__setitem__("map_commitment_after", "0" * 64), "the map version / commitment differ")
        self.named(lambda d: d["ledger"].pop(), "a completed run's last entry is not the holdout")
        self.named(lambda d: d.__setitem__("observations", 3), "observations 3 != ledger entries")
        self.named(lambda d: d["ledger"][1].__setitem__("seq", 9), "seqs are not 1..N")
        self.named(lambda d: d["best_trace"].append(1), "the best-so-far prefix differs")
        self.named(lambda d: d.__setitem__("completed", True), "a terminated run is marked completed", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("successful_observations", 2), "counts 2 observations", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("map_commitment", "0" * 64), "terminal event's map commitment", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("population_commitment", "0" * 64), "terminal event's population commitment", base=self.t)
        self.named(lambda d: d.__setitem__("rng_state_final", 1), "the generator advanced after the terminal event", base=self.t)
        self.named(lambda d: d.__setitem__("champion", {"genome": 0, "fit": 0, "born": 0}), "carries a champion", base=self.t)
        self.named(lambda d: d["ledger"].append(copy.deepcopy(d["ledger"][-1]) | {"seq": len(d["ledger"]) + 1}), "the terminal attempt is not the observation after the ledger's last", base=self.t)


if __name__ == "__main__":
    unittest.main()
