"""b4/host/b4_execution.py — the execution boundary: a port exposes observe and the addresses and nothing else (no
fabric, mapping, hypothesis, decode, diagnose reachable); an engine run touches only those two names (the call spy);
DOMAIN becomes a terminal event carrying the state as it stood before the refused call; any other refusal keeps its
own name; the public task's digest is deterministic. No skip."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402


from b4_test_fixtures import mechanics_fabric, v021_hole_fabric, v02_task  # noqa: E402


class ThePort(unittest.TestCase):
    def test_it_exposes_observe_and_addresses_only(self):
        port = ex.ObservationPort(mechanics_fabric())
        public = [n for n in dir(port) if not n.startswith("_")]
        self.assertEqual(sorted(public), ["addresses", "calls", "observe"])
        for leak in ("fabric", "mapping", "hypothesis", "diagnose", "decode", "effect", "step_diagnostics"):
            self.assertFalse(hasattr(port, leak), leak)
        self.assertEqual(ex.ObservationPort.__slots__, ("addresses", "_observe", "calls"))
        with self.assertRaises(AttributeError):
            port.fabric = None                                  # no new attributes either

    def test_an_engine_run_touches_only_observe_and_addresses(self):
        fab = mechanics_fabric()
        spy = ex.SpyPort(fab)
        task = v02_task(7, fab)
        for arm, kw in (("R", {}), ("O", {}), ("F", {})):
            spy.touched.clear()
            be.run(arm, task, spy, 11, 16, **kw)
            self.assertEqual(set(spy.touched), {"observe", "addresses"}, f"arm {arm} touched {set(spy.touched)}")
        spy.touched.clear()
        _ = spy.calls                                                # a read from outside IS recorded
        self.assertEqual(spy.touched, ["calls"])

    def test_domain_becomes_a_terminal_event_with_the_state_before_the_call(self):
        m = bm.site_mapping()
        port = ex.ObservationPort(v021_hole_fabric())                          # the kept 0.2.1 reading: its domain has the hole
        latch_only = 1 << m.genome_bit(m.address_of(None, "storage_kind"))     # CLKINV clear: outside the 0.2.1 domain (in v0.3's)
        ctx = {"task_digest": "t" * 64, "operator_seed": 11, "budget": 40, "successful_observations": 3, "rng_state": 12345,
               "population_commitment": "p" * 64, "map_commitment": "m" * 64, "map_version": 2}
        with self.assertRaises(ex.Terminated) as cm:
            ex.observe_candidate(port, latch_only, [{"kind": "init"}], "search", 4, ctx)
        e = cm.exception.event
        self.assertEqual((e.code, e.phase, e.attempt, e.genome, e.successful_observations, e.rng_state, e.map_version), ("DOMAIN", "search", 4, latch_only, 3, 12345, 2))
        self.assertEqual((e.population_commitment, e.map_commitment), ("p" * 64, "m" * 64))
        self.assertEqual(len(e.config_sha256), 64)
        self.assertEqual(set(e.as_dict()), {"code", "phase", "attempt", "genome", "config_sha256", "stimulus_sha256", "task_digest", "operator_seed", "budget",
                                            "successful_observations", "rng_state", "population_commitment", "map_commitment", "map_version"})
        for word in ("clock", "latch", "unknown", "reading"):
            self.assertNotIn(word, str(e.as_dict()).lower())
        with self.assertRaises(ValueError):
            ex.observe_candidate(port, 0, [{"kind": "init"}], "mapping", 1, ctx)

    def test_another_refusal_keeps_its_name(self):
        class Bad(ex.ObservationPort):
            __slots__ = ()
            def observe(self, config, stimulus):
                raise fm.ModelRefusal("boom")
        port = Bad(mechanics_fabric())
        with self.assertRaises(fm.ModelRefusal) as cm:
            ex.observe_candidate(port, 0, [{"kind": "init"}], "base", 1, {"task_digest": "t" * 64, "operator_seed": 0, "budget": 1, "successful_observations": 0,
                                                                            "rng_state": 0, "population_commitment": "", "map_commitment": "", "map_version": 0})
        self.assertEqual(str(cm.exception), "boom")
        self.assertNotIsInstance(cm.exception, fm.DomainRefusal)

    def test_the_source_identity_validator_is_exact(self):
        fab = mechanics_fabric()
        t = fab.observe({a: 0 for a in fab.mapping.addresses}, [fm.init()])
        hdr = {k: t[k] for k in ("hypothesis", "mapping", "fabric")}
        self.assertEqual(ex.provenance_findings(hdr), [])
        self.assertEqual(set(hdr["fabric"]), {"kind", "effect_sha256", "dropout_sha256", "dropout_count", "seed"})
        import copy
        for edit, needle in (
            (lambda h: h.pop("fabric"), "exactly hypothesis, mapping and fabric"),
            (lambda h: h["hypothesis"].__setitem__("sha256", "x"), "hypothesis identity: sha256 is not a 64-hex digest"),
            (lambda h: h["hypothesis"].__setitem__("fixture", 1), "fixture is not a bool"),
            (lambda h: h["hypothesis"].pop("version"), "hypothesis identity: exactly path, sha256, version, fixture"),
            (lambda h: h["mapping"].__setitem__("certificate_sha256", "Y" * 64), "certificate_sha256 is not a 64-hex digest"),
            (lambda h: h["fabric"].__setitem__("kind", "oracle"), "fabric identity: kind 'oracle'"),
            (lambda h: h["fabric"].__setitem__("dropout_count", True), "fabric identity: dropout_count"),
            (lambda h: h["fabric"].__setitem__("seed", "5"), "fabric identity: seed"),
        ):
            h = copy.deepcopy(hdr); edit(h)
            self.assertTrue(any(needle in x for x in ex.provenance_findings(h)), needle)
        self.assertEqual([ex.refusal_kind(e) for e in (ex.SourceRefusal("s"), fm.ModelRefusal("m"), ValueError("v"), fm.DomainRefusal(), KeyError("k"))], ["SourceRefusal", "ModelRefusal", "ValueError", None, None])
        for kind, cls in (("SourceRefusal", ex.SourceRefusal), ("ModelRefusal", fm.ModelRefusal), ("ValueError", ValueError)):
            with self.assertRaises(cls) as cm:
                ex.raise_refusal(kind, "msg")
            self.assertEqual(str(cm.exception), "msg")
        with self.assertRaises(ValueError):
            ex.raise_refusal("KeyError", "msg")

    def test_the_task_and_the_genome_helpers(self):
        fab = mechanics_fabric()
        task = v02_task(3, fab)
        self.assertEqual(task.digest(), v02_task(3, fab).digest())
        cfg = ex.genome_to_config(0b101, task.addresses)
        self.assertEqual([cfg[a] for a in task.addresses[:3]], [1, 0, 1])
        self.assertEqual(ex.genome_hex(0b101, 21), "000005")


if __name__ == "__main__":
    unittest.main()
