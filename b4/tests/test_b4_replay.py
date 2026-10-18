"""b4/host/b4_replay.py — replay as RE-EXECUTION: from the declared inputs and the recorded observations the engine runs
again against a ledger-backed port and the whole result must reconstruct EXACTLY. Held on complete R / O / F / X / D
runs, on runs terminated at the base, in the probe pass, mid-generation and at the holdout, and on the formal F run
that terminates at the LATCH probe. Every tamper the owner's probes on 2eae943 listed — the terminal candidate, its
identity fields, both generator states forged together, the pending children, the population, a forged parent /
move, a fabricated champion, the counts / cost / final map state, a corrupted probe-pass map history — and the
earlier ones is a named finding; a result whose observation-source provenance is missing or altered likewise. The
authenticity limit is stated in the module and asserted nowhere else. No skip."""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
import b4_replay as br  # noqa: E402
from b4_test_fixtures import InjectingPort, mechanics_fabric  # noqa: E402


class Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fab = mechanics_fabric()
        cls.m = cls.fab.mapping
        cls.task = bl.make_task(7, cls.m.addresses)
        port = lambda: ex.ObservationPort(cls.fab)  # noqa: E731
        cls.o = be.run("O", cls.task, port(), 11, 24).as_dict()
        cls.t = be.run("O", cls.task, InjectingPort(cls.fab, 6), 11, 24).as_dict()
        cls.h = be.run("O", cls.task, InjectingPort(cls.fab, 26), 11, 24).as_dict()
        cls.ff = be.run("F", cls.task, ex.ObservationPort(fm.Fabric(cls.m, hy.load())), 11, 24).as_dict()      # the formal hypothesis: terminates in the probe pass
        cls.perm = bc.derangement(5)

    def named(self, edit, needle: str, base=None, x_perm=None):
        d = copy.deepcopy(base if base is not None else self.o)
        edit(d)
        f = br.replay(d, self.task, x_perm=x_perm)
        self.assertTrue(any(needle in x for x in f), f"{needle!r} not among {f[:6]}")

    def test_the_clean_runs_replay_with_no_finding(self):
        port = lambda: ex.ObservationPort(self.fab)  # noqa: E731
        for name, result, perm in (
            ("O", self.o, None), ("terminated O", self.t, None), ("holdout-terminated O", self.h, None), ("formal F", self.ff, None),
            ("R", be.run("R", self.task, port(), 11, 24).as_dict(), None),
            ("F", be.run("F", self.task, port(), 11, 24).as_dict(), None),
            ("base-terminated R", be.run("R", self.task, InjectingPort(self.fab, 1), 11, 24).as_dict(), None),
            ("probe-terminated F", be.run("F", self.task, InjectingPort(self.fab, 5), 11, 24).as_dict(), None),
            ("other refusal", be.run("R", self.task, InjectingPort(self.fab, 3, exc=fm.ModelRefusal("boom")), 11, 24).as_dict(), None),
            ("D from oracle", be.run("F", self.task, port(), 11, 16, view=bc.shuffled_view(bc.oracle_view(self.m), 2)).as_dict(), None),
            ("A0", be.run("F", self.task, port(), 11, 16, view=bc.address_only_view(self.m.addresses)).as_dict(), None),
            ("X", be.run("X", self.task, port(), 11, 24, x_perm=self.perm).as_dict(), self.perm),
        ):
            with self.subTest(run=name):
                self.assertEqual(br.replay(result, self.task, x_perm=perm), [])
        self.assertNotEqual(br.replay(self.o, bl.make_task(8, self.task.addresses)), [])

    def test_the_owner_s_nine_tampers_are_named(self):
        t, o, ff = self.t, self.o, self.ff
        self.named(lambda d: d["terminal"].update(genome=0, config_sha256=ex.sha256_json(ex.genome_to_config(0, self.task.addresses))), "the terminal candidate / stimulus is not what the re-execution asked for", base=t)
        self.named(lambda d: d["terminal"].update(code="NOT_DOMAIN", phase="base", operator_seed=42, landscape_seed=42, budget=999, stimulus_sha256="0" * 64, map_version=999), "the terminal code is 'NOT_DOMAIN'", base=t)
        self.named(lambda d: d["terminal"].update(phase="base"), "result.terminal.phase", base=t)
        self.named(lambda d: d["terminal"].update(map_version=999), "result.terminal.map_version", base=t)
        self.named(lambda d: (d["terminal"].__setitem__("rng_state", 0), d.__setitem__("rng_state_final", 0)), "result.rng_state_final", base=t)
        self.named(lambda d: d.__setitem__("pending_children", []), "result.pending_children", base=t)
        self.named(lambda d: d.__setitem__("population", []), "result.population", base=t)
        self.named(lambda d: d["ledger"][1].update(bits=[], parent_born=999, move_kind="oracle"), "result.ledger[1]", base=o)
        self.named(lambda d: d.__setitem__("champion", {"genome": 0, "fit": 999, "born": 999}), "result.champion", base=o)
        self.named(lambda d: d.update(evals=999, cost={"base": 0, "probes": 0, "search": 0, "holdout": 0}, map_version_final=999, map_specimens_final=999, map_commitment_final="0" * 64), "result.evals", base=o)
        self.named(lambda d: d["ledger"][1].update(map_version_before=999, map_version_after=999, map_commitment_after="0" * 64), "result.ledger[1].map_commitment_after", base=ff)

    def test_the_earlier_tampers_are_still_named(self):
        self.named(lambda d: d["ledger"][3].__setitem__("fitness", d["ledger"][3]["fitness"] + 1), "fitness recomputed")
        self.named(lambda d: d["ledger"][2]["q_grid"][1].__setitem__(0, 1 - (d["ledger"][2]["q_grid"][1][0] or 0)), "does not hash to the recorded trace digest")
        self.named(lambda d: d["ledger"][3].__setitem__("best", 0), "result.ledger[3].best")
        self.named(lambda d: d["generation_closes"][0]["population"][0].__setitem__(1, 999), "result.generation_closes[0].population")
        self.named(lambda d: d["ledger"].pop(), "a completed run's last entry is not the holdout")
        self.named(lambda d: d.__setitem__("observations", 3), "result.observations")
        self.named(lambda d: d["ledger"][1].__setitem__("seq", 9), "seq 9 is not 2")
        self.named(lambda d: d["best_trace"].append(1), "result.best_trace")
        self.named(lambda d: d.__setitem__("completed", True), "a terminated run is marked completed", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("successful_observations", 2), "counts 2 observations", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("map_commitment", "0" * 64), "result.terminal.map_commitment", base=self.t)
        self.named(lambda d: d["terminal"].__setitem__("population_commitment", "0" * 64), "result.terminal.population_commitment", base=self.t)
        self.named(lambda d: d.__setitem__("champion", {"genome": 0, "fit": 0, "born": 0}), "a champion is carried if and only if", base=self.t)
        self.named(lambda d: d["ledger"].append(copy.deepcopy(d["ledger"][-1]) | {"seq": len(d["ledger"]) + 1}), "the terminal attempt is not the observation after the ledger's last", base=self.t)
        self.named(lambda d: d.pop("provenance"), "keys differ from the engine's")
        self.named(lambda d: d.__setitem__("search_completed", False), "completed without the search completed")

    def test_provenance_is_bound_and_checked(self):
        o = self.o
        self.assertEqual((o["provenance"]["hypothesis"]["fixture"], o["provenance"]["hypothesis"]["sha256"], o["provenance"]["mapping"]["certificate_sha256"]),
                         (True, self.fab.hypothesis.sha256, self.m.certificate_sha256))
        self.assertEqual({e["provenance_sha256"] for e in o["ledger"]}, {ex.sha256_json(o["provenance"])})
        self.assertIs(o["fixture"], True, "the fixture marker is a top-level key of the result")
        self.assertEqual({e["fixture"] for e in o["ledger"]}, {True}, "and of every ledger entry")
        self.assertIs(self.ff["fixture"], False)
        self.named(lambda d: d.__setitem__("fixture", False), "the result's fixture marker is not its provenance's")
        self.named(lambda d: d["ledger"][2].__setitem__("fixture", False), "seq 3: the entry's fixture marker")
        self.assertIs(self.ff["provenance"]["hypothesis"]["fixture"], False, "the formal hypothesis is not a fixture")
        self.assertEqual(self.ff["provenance"]["hypothesis"]["sha256"], hy.HYPOTHESIS_SHA256)
        self.named(lambda d: d["provenance"]["hypothesis"].__setitem__("fixture", False), "the entry's provenance digest is not the result's")
        self.named(lambda d: d.__setitem__("provenance", None), "no complete observation-source provenance")
        self.named(lambda d: d["ledger"][0].__setitem__("provenance_sha256", "0" * 64), "seq 1: the entry's provenance digest")

    def test_the_holdout_contract(self):
        h = self.h
        self.assertEqual((h["completed"], h["search_completed"], h["terminal"]["phase"], h["terminal"]["attempt"], h["champion_holdout"]), (False, True, "holdout", 26, None))
        self.assertIsNotNone(h["champion"], "the search's champion is kept")
        self.assertEqual(br.replay(h, self.task), [])
        self.named(lambda d: d.__setitem__("champion", None), "a champion is carried if and only if", base=h)
        self.named(lambda d: d.__setitem__("champion_holdout", 3), "carries a holdout score", base=h)
        self.named(lambda d: d.__setitem__("completed", True), "a terminated run is marked completed", base=h)

    def test_the_replay_port_serves_only_the_ledger(self):
        port = br.ReplayPort(self.t, self.task)
        for e in self.t["ledger"]:
            port.observe(ex.genome_to_config(e["genome"], self.task.addresses), list(self.task.stimulus))
        with self.assertRaises(fm.DomainRefusal):
            port.observe(ex.genome_to_config(self.t["terminal"]["genome"], self.task.addresses), list(self.task.stimulus))
        with self.assertRaises(br.ReplayMismatch):
            port.observe(ex.genome_to_config(0, self.task.addresses), list(self.task.stimulus))
        self.assertTrue(any("beyond the ledger" in m for m in port.mismatches))
        port = br.ReplayPort(self.o, self.task)
        with self.assertRaises(br.ReplayMismatch):
            port.observe(ex.genome_to_config(1, self.task.addresses), list(self.task.stimulus))     # the first entry is the base, genome 0
        self.assertEqual(sorted(n for n in dir(port) if not n.startswith("_")), ["addresses", "calls", "ledger", "mismatches", "observe", "other", "provenance", "terminal"])


if __name__ == "__main__":
    unittest.main()
