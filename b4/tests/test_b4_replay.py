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
from b4_test_fixtures import InjectingPort, mechanics_fabric, v02_task  # noqa: E402


class Replay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fab = mechanics_fabric()
        cls.m = cls.fab.mapping
        cls.task = v02_task(7, cls.fab)
        port = lambda: ex.ObservationPort(cls.fab)  # noqa: E731
        cls.o = be.run("O", cls.task, port(), 11, 24).as_dict()
        cls.t = be.run("O", cls.task, InjectingPort(cls.fab, 6), 11, 24).as_dict()
        cls.h = be.run("O", cls.task, InjectingPort(cls.fab, 26), 11, 24).as_dict()
        cls.ff = be.run("F", cls.task, ex.ObservationPort(fm.Fabric(cls.m, hy.load())), 11, 24).as_dict()      # the formal hypothesis: terminates in the probe pass
        cls.x = be.run("X", cls.task, port(), 11, 24, control_seed=5).as_dict()

    def named(self, edit, needle: str, base=None):
        d = copy.deepcopy(base if base is not None else self.o)
        edit(d)
        f = br.replay(d, self.task)
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
            ("X", self.x, None),
            ("base-terminated X", be.run("X", self.task, InjectingPort(self.fab, 1), 11, 24, control_seed=5).as_dict(), None),
            ("mid-generation-terminated X", be.run("X", self.task, InjectingPort(self.fab, 7), 11, 24, control_seed=6).as_dict(), None),
        ):
            with self.subTest(run=name):
                self.assertEqual(br.replay(result, self.task), [])
        self.assertNotEqual(br.replay(self.o, v02_task(8, self.fab)), [])

    def test_the_owner_s_nine_tampers_are_named(self):
        t, o, ff = self.t, self.o, self.ff
        self.named(lambda d: d["terminal"].update(genome=0, config_sha256=ex.sha256_json(ex.genome_to_config(0, self.task.addresses))), "the terminal candidate / stimulus is not what the re-execution asked for", base=t)
        self.named(lambda d: d["terminal"].update(code="NOT_DOMAIN", phase="base", operator_seed=42, task_digest="0" * 64, budget=999, stimulus_sha256="0" * 64, map_version=999), "the terminal code is 'NOT_DOMAIN'", base=t)
        self.named(lambda d: d["terminal"].update(phase="base"), "result.terminal.phase", base=t)
        self.named(lambda d: d["terminal"].update(task_digest="0" * 64), "the terminal event's task / seed / budget are not the run's", base=t)
        self.named(lambda d: d["terminal"].update(map_version=999), "result.terminal.map_version", base=t)
        self.named(lambda d: (d["terminal"].__setitem__("rng_state", 0), d.__setitem__("rng_state_final", 0)), "result.rng_state_final", base=t)
        self.named(lambda d: d.__setitem__("pending_children", []), "result.pending_children", base=t)
        self.named(lambda d: d.__setitem__("population", []), "result.population", base=t)
        self.named(lambda d: d["ledger"][1].update(bits=[], parent_born=999, move_kind="oracle"), "ledger[1]: a field has the wrong type or range", base=o)
        self.named(lambda d: d["ledger"][1].update(bits=[0], parent_born=999, move_kind="random"), "result.ledger[1]", base=o)
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
        self.named(lambda d: d.__setitem__("provenance", None), "observations were made but no source identity is recorded")
        self.named(lambda d: d["ledger"][0].__setitem__("provenance_sha256", "0" * 64), "seq 1: the entry's provenance digest")

    def test_the_holdout_contract(self):
        h = self.h
        self.assertEqual((h["completed"], h["search_completed"], h["terminal"]["phase"], h["terminal"]["attempt"], h["champion_holdout"]), (False, True, "holdout", 26, None))
        self.assertIsNotNone(h["champion"], "the search's champion is kept")
        self.assertEqual(br.replay(h, self.task), [])
        self.named(lambda d: d.__setitem__("champion", None), "a champion is carried if and only if", base=h)
        self.named(lambda d: d.__setitem__("champion_holdout", 3), "carries a holdout score", base=h)
        self.named(lambda d: d.__setitem__("completed", True), "a terminated run is marked completed", base=h)

    def test_legitimate_non_domain_refusals_replay_by_their_recorded_kind(self):
        """The owner's P2 on 8d2757a: a provenance drift (SourceRefusal), a ValueError and a ModelRefusal each replay to the
        same recorded kind, message, phase and attempt."""
        class Drifting(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                t = super().observe(config, stimulus)
                if self.calls == 3:
                    t = dict(t); t["hypothesis"] = dict(t["hypothesis"], sha256="0" * 64)
                return t
        drift = be.run("R", self.task, Drifting(self.fab), 11, 8).as_dict()
        self.assertEqual((drift["other_refusal"]["kind"], drift["other_refusal"]["phase"], drift["other_refusal"]["attempt"]), ("SourceRefusal", "search", 3))
        self.assertIn("identity changed between observations", drift["other_refusal"]["message"])
        self.assertEqual(br.replay(drift, self.task), [])
        val = be.run("R", self.task, InjectingPort(self.fab, 3, exc=ValueError("value refusal")), 11, 8).as_dict()
        self.assertEqual(val["other_refusal"]["kind"], "ValueError")
        self.assertEqual(br.replay(val, self.task), [])
        mod = be.run("R", self.task, InjectingPort(self.fab, 3, exc=fm.ModelRefusal("boom")), 11, 8).as_dict()
        self.assertEqual(mod["other_refusal"]["kind"], "ModelRefusal")
        self.assertEqual(br.replay(mod, self.task), [])
        self.named(lambda d: d["other_refusal"].__setitem__("kind", "KeyError"), "other_refusal is not a typed refusal of a finite kind", base=val)
        self.named(lambda d: d["other_refusal"].__setitem__("attempt", 2), "the refusal's attempt is not the observation after the ledger's last", base=val)
        # the authenticity limit, stated: a record that relabels a ValueError as a ModelRefusal, or rewrites the message, is a
        # CONSISTENT record — the re-execution re-raises what is recorded and reconstructs it; the replay cannot tell what the
        # port really raised, as it cannot tell what a fabric really returned
        d = copy.deepcopy(val); d["other_refusal"]["kind"] = "ModelRefusal"
        self.assertEqual(br.replay(d, self.task), [], "a consistent relabelling of the refusal's kind is within the authenticity limit")

    def test_a_malformed_source_identity_is_a_named_refusal_and_replays(self):
        """The owner's P1 on 8d2757a: a port returning {"sha256": "x", "fixture": false} … must not complete."""
        class Incomplete(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                t = dict(super().observe(config, stimulus))
                t["hypothesis"] = {"sha256": "x", "fixture": False}; t["mapping"] = {"certificate_sha256": "y"}
                return t
        r = be.run("R", self.task, Incomplete(self.fab), 11, 8).as_dict()
        self.assertFalse(r["completed"])
        self.assertEqual((r["other_refusal"]["kind"], r["other_refusal"]["phase"], r["other_refusal"]["attempt"], r["provenance"], r["ledger"]), ("SourceRefusal", "base", 1, None, []))
        self.assertIn("is malformed", r["other_refusal"]["message"])
        self.assertEqual(br.replay(r, self.task), [])

        class NoFabric(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                t = dict(super().observe(config, stimulus)); t.pop("fabric"); return t
        r = be.run("R", self.task, NoFabric(self.fab), 11, 8).as_dict()
        self.assertEqual(r["other_refusal"]["kind"], "SourceRefusal")

        class BoolCoerced(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                t = dict(super().observe(config, stimulus)); t["hypothesis"] = dict(t["hypothesis"], fixture=1); return t
        r = be.run("R", self.task, BoolCoerced(self.fab), 11, 8).as_dict()
        self.assertIn("fixture is not a bool", r["other_refusal"]["message"])

    def test_the_fabric_identity_tells_truth_permuted_and_dropout_apart(self):
        """The owner's P1 on 8d2757a: under the same formal hypothesis three fabrics must declare three identities — as
        digests, never the effect table."""
        import json
        m, h = self.m, hy.load()
        results = {k: be.run("R", self.task, ex.ObservationPort(fm.fixture(k, m, h, seed=5)), 11, 8).as_dict() for k in ("truth", "permuted", "dropout")}
        provs = {k: r["provenance"] for k, r in results.items()}
        self.assertEqual({p["hypothesis"]["fixture"] for p in provs.values()}, {False}, "the hypothesis is the formal one in all three")
        self.assertEqual({k: p["fabric"]["kind"] for k, p in provs.items()}, {"truth": "truth", "permuted": "permuted", "dropout": "dropout"})
        self.assertEqual(len({ex.sha256_json(p) for p in provs.values()}), 3, "three different identities")
        self.assertEqual({k: r["fabric_fixture"] for k, r in results.items()}, {"truth": False, "permuted": True, "dropout": True})
        self.assertEqual(provs["truth"]["fabric"]["effect_sha256"], provs["dropout"]["fabric"]["effect_sha256"], "dropout keeps the truth's effect table")
        self.assertNotEqual(provs["truth"]["fabric"]["dropout_sha256"], provs["dropout"]["fabric"]["dropout_sha256"])
        self.assertEqual(provs["dropout"]["fabric"]["dropout_count"], 5)
        for r in results.values():
            text = json.dumps(r)
            for leak in ("ff_init", "ff_srval", "ce_mode", "clock_mode", "AFF", "A5FF", "SLICEL"):
                self.assertNotIn(leak, text, "the effect table never reaches a result")
            self.assertEqual(br.replay(r, self.task), [])
        self.named(lambda d: d["provenance"]["fabric"].__setitem__("kind", "truth"), "the result's fabric_fixture marker is not its provenance's", base=results["permuted"])
        self.named(lambda d: d["provenance"]["fabric"].__setitem__("effect_sha256", "0" * 64), "the entry's provenance digest is not the result's", base=results["permuted"])

    def test_malformed_records_are_named_findings_never_exceptions(self):
        """The owner's P2 on 8d2757a, and more: every malformed value is a named finding, type-exact."""
        cases = [
            (lambda d: d.__setitem__("terminal", [1]), "terminal is not a complete, typed terminal event"),
            (lambda d: d["ledger"][0].__setitem__("q_grid", []), "ledger[0]: the q grid is not 9 rows of 8 cells"),
            (lambda d: d["ledger"][0]["q_grid"][1].__setitem__(2, 2), "ledger[0]: the q grid is not"),
            (lambda d: d["ledger"][0]["q_grid"][1].__setitem__(2, True), "ledger[0]: the q grid is not"),
            (lambda d: d["ledger"][0].__setitem__("genome", "bad"), "ledger[0]: a field has the wrong type or range"),
            (lambda d: d["ledger"][0].__setitem__("genome", 1 << 21), "ledger[0]: a field has the wrong type or range"),
            (lambda d: d["ledger"][0].__setitem__("move_kind", "oracle"), "ledger[0]: a field has the wrong type or range"),
            (lambda d: d.__setitem__("given_view", {"groups": []}), "given_view is not a complete, typed view record"),
            (lambda d: d.__setitem__("completed", 1), "completed is not a bool"),
            (lambda d: d.__setitem__("search_completed", "yes"), "search_completed is not a bool"),
            (lambda d: d.__setitem__("evals", True), "evals is not a non-negative integer"),
            (lambda d: d.__setitem__("best_trace", [1, None]), "best_trace is not a list"),
            (lambda d: d.__setitem__("population", [[0, 1]]), "population is not a list of [genome, fit, born]"),
            (lambda d: d.__setitem__("cost", {"base": 1}), "cost"),
            (lambda d: d.__setitem__("provenance", {"hypothesis": {"sha256": "x", "fixture": False}, "mapping": {"certificate_sha256": "y"}}), "provenance: the source identity must carry exactly"),
            (lambda d: d["provenance"]["fabric"].__setitem__("kind", "oracle"), "provenance: fabric identity: kind 'oracle'"),
            (lambda d: d["provenance"]["hypothesis"].__setitem__("sha256", "x"), "provenance: hypothesis identity: sha256 is not a 64-hex digest"),
            (lambda d: d.__setitem__("ledger", None), "the ledger is not a list"),
            (lambda d: d.__setitem__("other_refusal", {"kind": "ValueError"}), "other_refusal is not a typed refusal"),
            (lambda d: d["generation_closes"].append({"generation": 9}), "generation_closes[3]"),
        ]
        for edit, needle in cases:
            with self.subTest(needle=needle):
                self.named(edit, needle)
        self.assertEqual(br.replay("not a dict", self.task), ["the result is not an object"])
        self.assertIn("the result's keys differ from the engine's", br.replay({"arm": "R"}, self.task)[0])

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
        for leak in ("ff_init", "AFF", "0x00400a", "SLICEL"):
            self.assertNotIn(leak, str(port.provenance), "the port holds digests, not the effect table")


class ControlXARecords(Replay):
    """Control X-A's record: π re-derived from the control seed, the control fields X's only, the control failure typed."""

    def test_pi_not_derived_from_the_control_seed_is_named(self):
        self.named(lambda d: d.__setitem__("x_perm", d["x_perm"][1:] + d["x_perm"][:1]), "not the ones B3's rule derives from the control seed", base=self.x)
        self.named(lambda d: d.__setitem__("x_perm_attempts", [d["x_perm"]]), "not the ones B3's rule derives from the control seed", base=self.x)
        self.named(lambda d: d.__setitem__("x_control_seed", 6), "not the ones B3's rule derives from the control seed", base=self.x)
        self.named(lambda d: d.__setitem__("x_control_seed", None), "carries no control seed", base=self.x)
        self.named(lambda d: d.__setitem__("x_perm", list(range(len(self.task.addresses)))[::-1] + [0]), "x_perm is not a permutation", base=self.x)
        self.named(lambda d: d.__setitem__("x_perm_attempts", []), "x_perm_attempts is not a non-empty list", base=self.x)

    def test_control_fields_on_another_arm_are_named(self):
        self.named(lambda d: d.__setitem__("x_control_seed", 5), "x_control_seed on an arm other than X")
        self.named(lambda d: d.__setitem__("x_residual", self.x["x_residual"]), "x_residual on an arm other than X")
        self.named(lambda d: d.__setitem__("control_failure", {"phase": "search", "attempt": 1, "seq": 1, "findings": ["x"], "successful_observations": 1, "rng_state": 1,
                                                               "population_commitment": "0" * 64, "map_version": 0, "map_commitment": "0" * 64, "shadow_commitment": "0" * 64}), "control_failure on an arm other than X")

    def test_a_malformed_residual_or_control_failure_is_a_named_finding(self):
        self.named(lambda d: d["x_residual"].__setitem__("partition_preserved", 1), "x_residual is not a complete", base=self.x)
        self.named(lambda d: d["x_residual"].pop("groups_moved"), "x_residual is not a complete", base=self.x)
        self.named(lambda d: d.__setitem__("control_failure", {"phase": "search"}), "control_failure is not a complete", base=self.x)
        self.named(lambda d: d.__setitem__("control_failure", {"phase": "search", "attempt": 1, "seq": 1, "findings": [], "successful_observations": 1, "rng_state": 1,
                                                               "population_commitment": "0" * 64, "map_version": 0, "map_commitment": "0" * 64, "shadow_commitment": "0" * 64}), "control_failure is not a complete", base=self.x)
        # a well-typed but inconsistent control failure on a completed record
        cf = {"phase": "search", "attempt": 3, "seq": 3, "findings": ["x"], "successful_observations": 3, "rng_state": self.x["rng_state_final"],
              "population_commitment": "0" * 64, "map_version": 0, "map_commitment": "0" * 64, "shadow_commitment": "0" * 64}
        self.named(lambda d: d.__setitem__("control_failure", cf), "a run with a control failure is marked completed", base=self.x)
        self.named(lambda d: (d.__setitem__("control_failure", cf), d.__setitem__("completed", False), d.__setitem__("search_completed", False), d.__setitem__("champion", None), d.__setitem__("champion_holdout", None)),
                   "exposing observation is not the ledger's last entry", base=self.x)


if __name__ == "__main__":
    unittest.main()
