"""b4/host/b4_engine.py — the derived (mu, lambda) engine over the FF universe with the execution boundary at every
observation. Complete runs are exercised under a MARKED mechanics fixture (the latch's clock bit 0 read as not
inverted, so the domain has no hole — it says nothing about the fabric); the DOMAIN semantics under injection at the
base, in the probe pass and mid-generation; the fact that under the FORMAL hypothesis F's probe pass from the all-zero
base terminates at the LATCH single flip whatever the probe order; the given views' provenance. No skip."""
from __future__ import annotations

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


from b4_test_fixtures import InjectingPort  # noqa: E402


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.hfix = cls.h.with_reading("clock_mode", "not_inverted", "not_inverted", "mechanics", context="latch")
        cls.fab = fm.Fabric(cls.m, cls.hfix)
        cls.task = bl.make_task(7, cls.m.addresses)

    def port(self):
        return ex.ObservationPort(self.fab)


class CompleteRuns(Base):
    def test_r_runs_to_its_budget_with_the_invariants(self):
        r = be.run("R", self.task, self.port(), 11, 24)
        self.assertTrue(r.completed)
        self.assertIsNone(r.terminal)
        self.assertEqual((r.evals, len(r.best_trace), r.observations), (24, 24, 1 + 24 + 1))
        self.assertEqual(r.best_trace, sorted(r.best_trace), "best-so-far never decreases")
        self.assertEqual(r.cost, {"base": 1, "probes": 0, "search": 24, "holdout": 1})
        self.assertEqual(len(r.population), be.MU)
        fits = [p[1] for p in r.population]
        self.assertEqual(fits, sorted(fits, reverse=True))
        self.assertEqual(r.champion["fit"], max(fits))
        self.assertEqual(r.champion["fit"], r.best_trace[-1])
        self.assertIsInstance(r.champion_holdout, int)
        self.assertEqual(len(r.generation_closes), 3)
        self.assertEqual([e["phase"] for e in r.ledger][:2] + [r.ledger[-1]["phase"]], ["base", "search", "holdout"])
        for e in r.ledger:
            if e["phase"] == "search":
                self.assertTrue(1 <= len(e["bits"]) <= be.KMAX)
                self.assertEqual(e["move_kind"], "random")
        self.assertEqual(r.group_moves, 0)
        self.assertEqual((r.map_origin, r.map_privileged, r.map_version_final), ("none", False, 0))
        self.assertEqual(br.replay(r.as_dict(), self.task), [])
        again = be.run("R", self.task, self.port(), 11, 24)
        self.assertEqual(r.as_dict(), again.as_dict(), "deterministic")
        self.assertNotEqual(be.run("R", self.task, self.port(), 12, 24).ledger, r.ledger)

    def test_f_learns_its_map_by_a_probe_pass_then_freezes(self):
        r = be.run("F", self.task, self.port(), 11, 24)
        self.assertTrue(r.completed)
        self.assertEqual((r.cost["probes"], r.map_origin), (21, "learned"))
        probes = [e for e in r.ledger if e["phase"] == "probe"]
        self.assertEqual(sorted(e["genome"] for e in probes), [1 << i for i in range(21)], "every address probed once from the base, in a seeded order")
        self.assertNotEqual([e["genome"] for e in probes], [1 << i for i in range(21)], "not in address order")
        self.assertIsNotNone(r.frozen_view)
        self.assertTrue(r.frozen_view, "the probe pass learned at least one group")
        search = [e for e in r.ledger if e["phase"] == "search"]
        self.assertEqual({e["map_version_after"] for e in search}, {r.map_version_final}, "the map does not move during the frozen search")
        self.assertIn("group", {e["move_kind"] for e in search})
        self.assertEqual(r.group_moves, sum(e["move_kind"] == "group" for e in search))
        self.assertEqual(br.replay(r.as_dict(), self.task), [])

    def test_o_learns_online_and_x_stays_isomorphic(self):
        r = be.run("O", self.task, self.port(), 11, 32)
        self.assertTrue(r.completed)
        self.assertGreaterEqual(r.map_version_final, 1)
        search = [e for e in r.ledger if e["phase"] == "search"]
        self.assertTrue(any(e["map_version_after"] > e["map_version_before"] for e in search), "a specimen moved the map")
        self.assertEqual(r.map_origin, "online")
        self.assertEqual(r.map_specimens_final, len([e for e in r.ledger if e["phase"] != "holdout"]))
        self.assertEqual(br.replay(r.as_dict(), self.task), [])
        perm = bc.derangement(5)
        x = be.run("X", self.task, self.port(), 11, 32, x_perm=perm)
        self.assertTrue(x.completed)
        self.assertEqual(x.x_isomorphism_findings, [])
        self.assertEqual(br.replay(x.as_dict(), self.task, x_perm=perm), [])
        self.assertNotEqual(x.map_commitment_final, r.map_commitment_final, "X's map is over permuted lanes")

    def test_given_views_carry_their_provenance(self):
        omega = be.run("F", self.task, self.port(), 11, 16, view=bc.oracle_view(self.m))
        self.assertEqual((omega.map_origin, omega.map_privileged, omega.cost["probes"]), ("oracle", True, 0))
        self.assertEqual((omega.given_view["provenance"], omega.given_view["privileged"]), (["oracle"], True))
        a0 = be.run("F", self.task, self.port(), 11, 16, view=bc.address_only_view(self.m.addresses))
        self.assertEqual((a0.map_origin, a0.map_privileged, a0.given_view["provenance"]), ("address_only", False, ["address_only"]))
        d = be.run("F", self.task, self.port(), 11, 16, view=bc.shuffled_view(bc.oracle_view(self.m), 2))
        self.assertEqual((d.map_origin, d.map_privileged, d.given_view["provenance"]), ("shuffled", True, ["oracle", "shuffled"]), "a shuffled oracle is still oracle-derived")
        self.assertEqual(d.given_view["base_commitment"], bc.oracle_view(self.m).commitment)
        learned = be.run("F", self.task, self.port(), 11, 16)
        self.assertIsNone(learned.given_view)
        self.assertEqual(learned.map_origin, "learned")
        with self.assertRaises(ValueError):
            be.run("O", self.task, self.port(), 11, 16, view=bc.oracle_view(self.m))
        with self.assertRaises(ValueError):
            be.run("X", self.task, self.port(), 11, 16)
        with self.assertRaises(ValueError):
            be.run("Q", self.task, self.port(), 11, 16)


class Termination(Base):
    def test_domain_at_the_base(self):
        port = InjectingPort(self.fab, refuse_at=1)
        r = be.run("R", self.task, port, 11, 24)
        self.assertFalse(r.completed)
        t = r.terminal
        self.assertEqual((t["code"], t["phase"], t["attempt"], t["successful_observations"]), ("DOMAIN", "base", 1, 0))
        self.assertEqual((r.ledger, r.population, r.pending_children, r.best_trace, r.evals, r.champion, r.champion_holdout), ([], [], [], [], 0, None, None))
        self.assertEqual(port.calls, 1, "nothing was observed after the refusal")
        self.assertEqual(r.rng_state_final, t["rng_state"], "the generator did not move after the refusal")
        self.assertEqual(br.replay(r.as_dict(), self.task), [])

    def test_domain_in_the_probe_pass(self):
        port = InjectingPort(self.fab, refuse_at=5)                     # base + 3 probes succeed; the 4th probe is refused
        r = be.run("F", self.task, port, 11, 24)
        self.assertFalse(r.completed)
        self.assertEqual((r.terminal["phase"], r.terminal["attempt"], r.terminal["successful_observations"]), ("probe", 5, 4))
        self.assertEqual([e["phase"] for e in r.ledger], ["base", "probe", "probe", "probe"])
        self.assertIsNone(r.frozen_view, "no frozen map: the pass did not complete")
        self.assertEqual((r.evals, r.best_trace, r.pending_children), (0, [], []))
        self.assertEqual(r.terminal["map_commitment"], r.ledger[-1]["map_commitment_after"])
        self.assertEqual(r.terminal["population_commitment"], be.population_commitment([be.Individual(0, r.base_fit, i) for i in range(be.MU)]))
        self.assertEqual(port.calls, 5)
        self.assertEqual(br.replay(r.as_dict(), self.task), [])

    def test_domain_mid_generation_keeps_the_prefix_and_the_pending_children(self):
        port = InjectingPort(self.fab, refuse_at=6)                     # base + 4 children succeed; the 5th child of generation 1 is refused
        r = be.run("O", self.task, port, 11, 24)
        self.assertFalse(r.completed)
        self.assertEqual((r.terminal["phase"], r.terminal["attempt"], r.terminal["successful_observations"]), ("search", 6, 5))
        self.assertEqual(r.evals, 4)
        self.assertEqual(len(r.best_trace), 4, "the measured prefix, nothing added")
        self.assertEqual(len(r.pending_children), 4, "the generation's successful children stay pending")
        self.assertEqual(r.generation_closes, [], "no selection pretended the generation closed")
        self.assertEqual(r.population, [[0, r.base_fit, i] for i in range(be.MU)], "the population is the one before the generation")
        self.assertEqual(r.terminal["population_commitment"], be.population_commitment([be.Individual(0, r.base_fit, i) for i in range(be.MU)]))
        self.assertEqual(r.terminal["map_commitment"], r.ledger[-1]["map_commitment_after"])
        self.assertEqual(r.terminal["map_version"], r.ledger[-1]["map_version_after"])
        self.assertEqual(r.map_version_final, r.ledger[-1]["map_version_after"], "no map update after the refusal")
        self.assertEqual(r.map_specimens_final, len(r.ledger), "the cartographer holds exactly the ledger's specimens: the refused candidate never reached it")
        self.assertEqual(r.rng_state_final, r.terminal["rng_state"], "the generator is not rolled back and does not advance")
        self.assertEqual(port.calls, 6)
        self.assertIsNone(r.champion)
        self.assertEqual(br.replay(r.as_dict(), self.task), [])
        full = be.run("O", self.task, self.port(), 11, 24)
        self.assertEqual([e["q_grid"] for e in full.ledger[:5]], [e["q_grid"] for e in r.ledger], "the prefix is the same run's prefix")

    def test_domain_at_the_holdout_keeps_the_search_s_champion_without_a_holdout_score(self):
        """The owner's P2: budget 24 = base + 24 search observations; the 26th attempt is the holdout."""
        port = InjectingPort(self.fab, refuse_at=26)
        r = be.run("O", self.task, port, 11, 24)
        self.assertEqual((r.completed, r.search_completed, r.terminal["phase"], r.terminal["attempt"], r.terminal["successful_observations"]), (False, True, "holdout", 26, 25))
        self.assertIsNotNone(r.champion)
        self.assertEqual((r.champion_holdout, r.champion_holdout_nones, r.cost["holdout"]), (None, None, 0))
        self.assertEqual(len(r.ledger), 25)
        self.assertEqual(len(r.generation_closes), 3, "the search completed every generation")
        self.assertEqual(r.rng_state_final, r.terminal["rng_state"])
        self.assertEqual(br.replay(r.as_dict(), self.task), [])
        full = be.run("O", self.task, self.port(), 11, 24)
        self.assertEqual(full.champion, r.champion, "the same search gives the same champion")
        self.assertTrue(full.completed)

    def test_the_observation_source_is_bound_into_the_result(self):
        r = be.run("R", self.task, self.port(), 11, 8)
        self.assertEqual(r.provenance["hypothesis"]["fixture"], True, "the mechanics fixture is marked in the result")
        self.assertEqual(r.provenance["hypothesis"]["sha256"], self.hfix.sha256)
        self.assertEqual(r.provenance["mapping"]["certificate_sha256"], self.m.certificate_sha256)
        formal = be.run("R", self.task, ex.ObservationPort(fm.Fabric(self.m, self.h)), 11, 8)
        self.assertEqual((formal.provenance["hypothesis"]["fixture"], formal.provenance["hypothesis"]["sha256"]), (False, hy.HYPOTHESIS_SHA256))
        self.assertNotEqual(r.provenance, formal.provenance, "the fixture and the formal hypothesis are told apart by the result alone")

        class Drifting(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                t = super().observe(config, stimulus)
                if self.calls == 3:
                    t = dict(t); t["hypothesis"] = dict(t["hypothesis"], sha256="0" * 64)
                return t
        r = be.run("R", self.task, Drifting(self.fab), 11, 8)
        self.assertFalse(r.completed)
        self.assertEqual(r.other_refusal["kind"], "SourceRefusal")
        self.assertIn("identity changed between observations", r.other_refusal["message"])
        self.assertEqual(set(r.provenance), {"hypothesis", "mapping", "fabric"})
        self.assertEqual((r.fixture, r.fabric_fixture), (True, False), "a hypothesis fixture over the truth fabric")

    def test_another_refusal_is_recorded_by_name_not_as_domain(self):
        port = InjectingPort(self.fab, refuse_at=3, exc=fm.ModelRefusal("boom"))
        r = be.run("R", self.task, port, 11, 24)
        self.assertFalse(r.completed)
        self.assertIsNone(r.terminal)
        self.assertEqual((r.other_refusal["kind"], r.other_refusal["message"], r.other_refusal["phase"], r.other_refusal["attempt"]), ("ModelRefusal", "boom", "search", 3))
        self.assertEqual(len(r.ledger), 2)

    def test_under_the_formal_hypothesis_f_s_probe_pass_terminates_at_the_latch_flip(self):
        """A fact, not a defect: from the all-zero base (CLKINV clear, in the domain) the single flip of the LATCH
        address is outside the domain, so a probe pass that covers every address terminates there — in whatever order."""
        formal = ex.ObservationPort(fm.Fabric(self.m, self.h))
        latch = 1 << self.m.genome_bit(self.m.address_of(None, "storage_kind"))
        for seed in (11, 12, 13):
            port = ex.ObservationPort(fm.Fabric(self.m, self.h))
            r = be.run("F", self.task, port, seed, 24)
            self.assertFalse(r.completed, seed)
            self.assertEqual((r.terminal["code"], r.terminal["phase"], r.terminal["genome"]), ("DOMAIN", "probe", latch), seed)
            self.assertEqual(br.replay(r.as_dict(), self.task), [])
        self.assertEqual(formal.calls, 0)


if __name__ == "__main__":
    unittest.main()
