"""b4/host/b4_controls.py — the two control seeds (by hand), F's frozen view REBUILT from the record and refused on anything
that is not a complete, replayable, formal, learned F result, D as the seeded relabelling of that view with its permutation
and residual recorded. Runs are small (budget 16) under the FORMAL v0.3 hypothesis on the truth fabric, with the exposed
landscape seed 7 and operator seed 11 only (mechanics; no arm advantage read, no seed scanned). No skip."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host", R / "b4/tests"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_carto as bc  # noqa: E402
import b4_controls as ctl  # noqa: E402
import b4_engine as be  # noqa: E402
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402
import b4_landscape as bl  # noqa: E402
from b4_test_fixtures import InjectingPort, mechanics_fabric  # noqa: E402

L, O, B = 7, 11, 16


def copy(d: dict) -> dict:
    return json.loads(json.dumps(d))


class Base(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.m, cls.h = bm.site_mapping(), hy.load()
        cls.fab = fm.Fabric(cls.m, cls.h)
        cls.task = bl.make_task(L, cls.m.addresses)
        cls.F = be.run("F", cls.task, ex.ObservationPort(cls.fab), O, B).as_dict()
        assert cls.F["completed"] and cls.F["fixture"] is False

    def port(self):
        return ex.ObservationPort(self.fab)


class ControlSeeds(unittest.TestCase):
    def test_the_two_formulas_by_hand(self):
        want_x = int.from_bytes(hashlib.sha256(b"b4-x-control-1|7|11").digest()[:4], "big")
        want_d = int.from_bytes(hashlib.sha256(b"b4-d-control-1|7|11").digest()[:4], "big")
        self.assertEqual(ctl.x_control_seed(7, 11), want_x)
        self.assertEqual(ctl.d_shuffle_seed(7, 11), want_d)
        self.assertNotEqual(want_x, want_d)
        self.assertTrue(0 <= want_x <= 0xFFFFFFFF and 0 <= want_d <= 0xFFFFFFFF)

    def test_only_32_bit_ints_never_bools(self):
        for bad in ((True, 11), (7, False), (-1, 11), (7, 1 << 32), (7.0, 11), ("7", 11)):
            with self.assertRaises(ValueError, msg=bad):
                ctl.x_control_seed(*bad)
            with self.assertRaises(ValueError, msg=bad):
                ctl.d_shuffle_seed(*bad)


class FrozenView(Base):
    def test_the_rebuilt_view_is_the_record_s_and_formal(self):
        fv = ctl.f_frozen_view(self.F, self.task)
        self.assertEqual([list(g) for g in fv.groups], self.F["frozen_view"])
        self.assertEqual((fv.version, fv.commitment), (self.F["map_version_final"], self.F["map_commitment_final"]))
        self.assertEqual((fv.origin, fv.provenance, fv.privileged, fv.base_commitment), ("learned", ("learned",), False, ""))
        again = be.run("F", self.task, self.port(), O, B, view=fv)
        self.assertTrue(again.completed)
        self.assertEqual(again.given_view, fv.as_dict(), "the rebuilt view can be handed to the frozen arm and is recorded whole")

    def test_not_an_f_result_or_not_learned_is_refused(self):
        o = be.run("O", self.task, self.port(), O, B).as_dict()
        with self.assertRaises(ctl.ControlInputRefusal):
            ctl.f_frozen_view(o, self.task)
        given = be.run("F", self.task, self.port(), O, B, view=bc.address_only_view(self.m.addresses)).as_dict()
        with self.assertRaises(ctl.ControlInputRefusal) as cm:
            ctl.f_frozen_view(given, self.task)
        self.assertIn("given view", str(cm.exception))
        other = bl.make_task(8, self.m.addresses)
        with self.assertRaises(ctl.ControlInputRefusal):
            ctl.f_frozen_view(self.F, other)

    def test_a_fixture_source_is_refused(self):
        fx = be.run("F", self.task, ex.ObservationPort(mechanics_fabric()), O, B).as_dict()
        self.assertTrue(fx["completed"] and fx["fixture"] is True)
        with self.assertRaises(ctl.ControlInputRefusal) as cm:
            ctl.f_frozen_view(fx, self.task)
        self.assertIn("formal", str(cm.exception))

    def test_an_incomplete_run_is_refused(self):
        r = be.run("F", self.task, InjectingPort(self.fab, 30), O, B).as_dict()
        self.assertFalse(r["completed"])
        with self.assertRaises(ctl.ControlInputRefusal):
            ctl.f_frozen_view(r, self.task)

    def test_a_tampered_record_is_refused(self):
        t = copy(self.F)
        probe = next(e for e in t["ledger"] if e["phase"] == "probe")
        row = probe["q_grid"][1]
        row[0] = 1 - row[0] if row[0] in (0, 1) else 0
        with self.assertRaises(ctl.ControlInputRefusal) as cm:
            ctl.f_frozen_view(t, self.task)
        self.assertIn("replay", str(cm.exception))
        t = copy(self.F)
        t["frozen_view"] = t["frozen_view"][1:]
        with self.assertRaises(ctl.ControlInputRefusal) as cm:
            ctl.f_frozen_view(t, self.task)
        self.assertIn("frozen_view", str(cm.exception))
        t = copy(self.F)
        t["map_origin"] = "oracle"
        with self.assertRaises(ctl.ControlInputRefusal):
            ctl.f_frozen_view(t, self.task)


class ControlD(Base):
    def test_d_is_the_seeded_relabelling_of_f_s_view_with_its_parent_kept(self):
        dv, info = ctl.d_view(self.F, self.task)
        fv = ctl.f_frozen_view(self.F, self.task)
        self.assertEqual((dv.origin, dv.provenance, dv.privileged, dv.base_commitment, dv.version), ("shuffled", ("learned", "shuffled"), False, fv.commitment, fv.version))
        self.assertEqual(sorted(len(g) for g in dv.groups), sorted(len(g) for g in fv.groups), "group sizes kept")
        self.assertEqual(sorted(b for g in dv.groups for b in g), sorted(b for g in fv.groups for b in g), "the same bits")
        self.assertEqual(info["d_shuffle_seed"], ctl.d_shuffle_seed(L, O))
        self.assertEqual(info["parent_commitment"], fv.commitment)
        self.assertEqual(set(info["permutation"]), {str(b) for g in fv.groups for b in g})
        self.assertEqual(set(info["residual_structure"]), {"partition_preserved", "groups_moved", "groups_true", "groups_x", "true_groups", "x_groups"})
        self.assertEqual((info["logical_cost_probes"], info["reobserved"]), (21, 0))
        dv2, _ = ctl.d_view(self.F, self.task)
        self.assertEqual(dv.as_dict(), dv2.as_dict(), "deterministic from the record and the seed")
        d_run = be.run("F", self.task, self.port(), O, B, view=dv).as_dict()
        self.assertEqual(ctl.verify_d_view(d_run["given_view"], self.F, self.task), [])
        self.assertTrue(ctl.verify_d_view(bc.oracle_view(self.m).as_dict(), self.F, self.task))

    def test_an_identity_or_partition_preserving_shuffle_is_reported_never_redrawn(self):
        one = bc.MapView(((3,),), 1, bc.sha256_json([[3]]), False, "learned", ("learned",))
        sv = bc.shuffled_view(one, 5)
        self.assertEqual(sv.groups, one.groups, "one bit can only map to itself")
        self.assertEqual(ctl.shuffle_permutation(one, 5), {3: 3})
        self.assertTrue(bc.residual_structure(sv, one)["partition_preserved"])

    def test_the_permutation_is_shuffled_view_s(self):
        fv = ctl.f_frozen_view(self.F, self.task)
        for seed in (5, 6, 9):
            sv = bc.shuffled_view(fv, seed)
            rel = ctl.shuffle_permutation(fv, seed)
            self.assertEqual(sv.groups, tuple(tuple(sorted(rel[b] for b in g)) for g in fv.groups), seed)


if __name__ == "__main__":
    unittest.main()
