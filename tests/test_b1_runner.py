"""host/b1_runner.py — the B1 board runner's fail-closed preflight.

The runner cannot run today: the manifest is a DRAFT (prereg.sha256 null, board_ready
false) and these tests pin that it refuses, in the documented order, for the documented
reason. With a fixture manifest "frozen" to a fake hash the later checks are reached one
by one: the plan pin, the image bytes, board_ready, the build evidence, the header
freshness, a ruling bound to another seed or manifest. No test opens a port or consumes a
ruling."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import sys
import tempfile
import types
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b1_runner as rn  # noqa: E402
import b1q_adjudicate as qadj  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402
from test_b1_qualification import qualify, frozen as frozen_q, HAVE as HAVE_Q  # noqa: E402

MANIFEST = json.loads(rn.MANIFEST.read_text())
HAVE = inst.DEFAULT_ROOT.is_dir() and (inst.DEFAULT_ROOT / ".git").exists()
IMAGE = R / "firmware/b1/bsp/out/b1_app.bin"
BOUNDARY = inst.DEFAULT_ROOT / "evidence/boundary/principal_boundary_2026-09-04-01.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Fixture:
    def __init__(self):
        self.d = Path(tempfile.mkdtemp())
        self.manifest = copy.deepcopy(MANIFEST)

    def ruling(self, name: str, **fields) -> Path:
        p = self.d / f"{name}.json"
        p.write_text(json.dumps({"boardid": "17A6", "granted_by": "test", "date": "2026-09-05-T", **fields}))
        return p

    def freeze(self, board_ready: bool = True, qualified: bool = True) -> None:
        doc = self.d / "prereg.md"
        doc.write_text("# fixture preregistration\n")
        self.manifest["prereg"]["path"] = os.path.relpath(doc, R)
        self.manifest["prereg"]["sha256"] = sha(doc)
        self.manifest["image"]["board_ready"] = board_ready
        if qualified:
            # a REAL qualification record: the modelled B1Q session over this very manifest
            # (bound to the bytes manifest_path() writes), adjudicated, pinned — the runner
            # re-adjudicates it and checks the transition to the manifest it reads
            self.manifest["carrier"]["qualification"] = None; self.manifest["carrier"]["qualified"] = False
            rec, _, _, _ = qualify(self.d, self.manifest, "b1q", text=json.dumps(self.manifest))
            self.manifest["carrier"]["qualification"] = rec
            self.manifest["carrier"]["qualified"] = True
        else:
            self.manifest["carrier"]["qualification"] = None
            self.manifest["carrier"]["qualified"] = False

    def manifest_path(self) -> Path:
        p = self.d / "manifest.json"
        p.write_text(json.dumps(self.manifest))
        return p

    def args(self, profile: dict = rn.MAPPING, **over) -> types.SimpleNamespace:
        mp = self.manifest_path()
        session = profile["session"]
        seed = self.manifest["seeds"]["master_seed"] if profile is rn.MAPPING else self.manifest["qualification_plan"]["master_seed"]
        base = dict(ruling=self.ruling("b1", ruling=profile["ruling_text"], session=session, prereg_sha256=self.manifest["prereg"]["sha256"],
                                       image_sha256=self.manifest["image"]["sha256"], b1_manifest_sha256=sha(mp), master_seed=seed),
                    provision_ruling=self.ruling("k", ruling=rn.PROVISION_RULING_TEXT, session=session,
                                                 prereg_sha256=self.manifest["prereg"]["sha256"],
                                                 image_sha256=self.manifest["image"]["sha256"], b1_manifest_sha256=sha(mp)),
                    boundary=BOUNDARY, out=self.d / "out", manifest=mp, instrument_root=inst.DEFAULT_ROOT,
                    image=IMAGE, key=Path("/var/lib/p3signer/keys/K.bin"), signer_user="p3signer", port="/dev/null")
        base.update(over)
        return types.SimpleNamespace(**base)


class RefusalOrder(unittest.TestCase):
    def refuses(self, args, *words: str, profile: dict = rn.MAPPING) -> str:
        with self.assertRaises(rn.Refusal) as cm:
            rn.preflight(args, profile)
        msg = str(cm.exception)
        for w in words:
            self.assertIn(w, msg)
        return msg

    def test_the_committed_manifest_is_frozen_to_the_documents_bytes_and_board_ready(self):
        """Since the owner's freeze (2026-09-06) the committed manifest is FROZEN and
        board_ready. Its qualification state is NOT asserted here: it changes when a B1Q
        record is pinned, and a test that pinned it would have to change — a pinned-file
        change that invalidates the very qualification (docs/b1q_transition_decision_2026_09_06.md).
        "Not qualified → refused" is tested on an explicit fixture below."""
        m = json.loads(rn.MANIFEST.read_text())
        self.assertTrue(m["prereg"]["frozen"]); self.assertTrue(m["image"]["board_ready"])
        self.assertEqual(hashlib.sha256((R / m["prereg"]["path"]).read_bytes()).hexdigest(), m["prereg"]["sha256"])
        self.assertIn(m["carrier"]["qualified"], (True, False))
        if m["carrier"]["qualified"]:
            self.assertEqual(m["carrier"]["qualification"]["schema"], "b1_carrier_qualification")
        else:
            self.assertIsNone(m["carrier"]["qualification"])

    def test_a_draft_manifest_refuses_before_any_pin(self):
        f = Fixture(); f.manifest["prereg"]["sha256"] = None; f.manifest["prereg"]["frozen"] = None
        self.refuses(f.args(), "not frozen")

    def test_wrong_ruling_text_and_missing_provisioning(self):
        f = Fixture()
        self.refuses(f.args(ruling=f.ruling("x", ruling="whole-of-run Claim B round 1′", session="B1")), "ruling text")
        self.refuses(f.args(provision_ruling=None), "provisioning P3-K")

    def test_frozen_but_the_plan_pin_is_wrong(self):
        f = Fixture(); f.freeze()
        f.manifest["plan"]["sha256"] = "c" * 64
        self.refuses(f.args(), "plan pin")

    def test_frozen_but_the_pin_table_is_wrong_or_missing(self):
        f = Fixture(); f.freeze()
        f.manifest["pins"]["sha256"] = "9" * 64
        self.refuses(f.args(), "pins")
        f = Fixture(); f.freeze()
        f.manifest["pins"]["sha256"] = None
        self.refuses(f.args(), "pins")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_frozen_and_board_ready_but_the_carrier_is_not_qualified(self):
        f = Fixture(); f.freeze(qualified=False)
        self.refuses(f.args(), "not qualified", "no carrier.qualification")
        f.manifest["carrier"]["qualified"] = True                   # the bare flag changes nothing
        self.refuses(f.args(), "not qualified")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_a_qualification_bound_to_another_carrier_or_with_tampered_evidence_refuses(self):
        f = Fixture(); f.freeze()
        f.manifest["carrier"]["qualification"]["binding"]["carrier_sha256"] = "a" * 64
        self.refuses(f.args(), "not qualified", "carrier_sha256")
        f = Fixture(); f.freeze()
        f.manifest["carrier"]["qualification"]["files"]["audits.json"] = "0" * 64
        self.refuses(f.args(), "not qualified", "does not hash")
        f = Fixture(); f.freeze()
        f.manifest["carrier"]["qualified"] = False                  # evidence stands, flag disagrees
        self.refuses(f.args(), "disagrees")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_the_qualification_profile_needs_no_qualification_but_its_own_plan_and_rulings(self):
        f = Fixture(); f.freeze(qualified=False)
        a = f.args(profile=rn.QUALIFICATION)
        with self.assertRaises(Exception) as cm:                    # reaches the boundary check, past every pin and ruling
            rn.preflight(a, rn.QUALIFICATION)
        msg = str(cm.exception).lower()
        self.assertNotIsInstance(cm.exception, AssertionError)
        self.assertTrue("boundary" in msg or "old" in msg or "runner_user" in msg, msg)
        self.assertNotIn("qualif", msg)
        # the mapping ruling texts do not open the qualification profile, and vice versa
        f2 = Fixture(); f2.freeze(qualified=False)
        self.refuses(f2.args(profile=rn.MAPPING), "ruling text", profile=rn.QUALIFICATION)
        # a B1Q provisioning ruling bound to session B1 is refused (one provisioning ruling per session)
        f3 = Fixture(); f3.freeze(qualified=False)
        a = f3.args(profile=rn.QUALIFICATION)
        a.provision_ruling = f3.ruling("k2", ruling=rn.PROVISION_RULING_TEXT, session="B1", prereg_sha256=f3.manifest["prereg"]["sha256"],
                                       image_sha256=f3.manifest["image"]["sha256"], b1_manifest_sha256=sha(a.manifest))
        self.refuses(a, "session", profile=rn.QUALIFICATION)
        # a missing qualification plan pin
        f4 = Fixture(); f4.freeze(qualified=False); f4.manifest["qualification_plan"]["sha256"] = "0" * 64
        self.refuses(f4.args(profile=rn.QUALIFICATION), "qualification plan", profile=rn.QUALIFICATION)

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_frozen_but_a_carrier_pin_is_wrong(self):
        for key, words in (("carrier_manifest", "carrier manifest"), ("build_record", "build record"), ("bitstream", "bitstream")):
            f = Fixture(); f.freeze()
            if key == "bitstream":
                f.manifest["carrier"]["bitstream_sha256"] = "a" * 64
            else:
                f.manifest["carrier"][key]["sha256"] = "a" * 64
            self.refuses(f.args(), words)
        f = Fixture(); f.freeze(); f.manifest["carrier"]["variant"] = "0x00000000"
        self.refuses(f.args(), "variant")

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_frozen_but_the_image_is_not_the_pinned_bytes(self):
        f = Fixture(); f.freeze()
        wrong = f.d / "image.bin"; wrong.write_bytes(b"not the image")
        self.refuses(f.args(image=wrong), "not the pinned one")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_frozen_but_not_board_ready(self):
        f = Fixture(); f.freeze(board_ready=False)
        self.refuses(f.args(), "board_ready")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_frozen_but_the_build_evidence_pin_is_wrong(self):
        f = Fixture(); f.freeze()
        f.manifest["image"]["build_evidence"]["sha256"] = "d" * 64
        self.refuses(f.args(), "build evidence")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "instrument or built image absent")
    def test_frozen_but_the_ruling_is_bound_to_another_seed_or_manifest(self):
        f = Fixture(); f.freeze()
        a = f.args()
        a.ruling = f.ruling("b2", ruling=rn.RULING_TEXT, session="B1", prereg_sha256=f.manifest["prereg"]["sha256"],
                            image_sha256=f.manifest["image"]["sha256"], b1_manifest_sha256=sha(a.manifest), master_seed=1281816666)
        self.refuses(a, "master_seed")
        a = f.args()
        a.ruling = f.ruling("b3", ruling=rn.RULING_TEXT, session="B1", prereg_sha256=f.manifest["prereg"]["sha256"],
                            image_sha256=f.manifest["image"]["sha256"], b1_manifest_sha256="e" * 64,
                            master_seed=f.manifest["seeds"]["master_seed"])
        self.refuses(a, "b1_manifest_sha256")

    @unittest.skipUnless(HAVE and IMAGE.is_file() and BOUNDARY.is_file(), "instrument, image or boundary absent")
    def test_frozen_but_the_boundary_record_is_stale(self):
        f = Fixture(); f.freeze()
        with self.assertRaises(Exception) as cm:
            rn.preflight(f.args())
        self.assertNotIsInstance(cm.exception, AssertionError)
        msg = str(cm.exception).lower()
        self.assertTrue("boundary" in msg or "old" in msg or "established" in msg or "runner_user" in msg, msg)

    def test_bind_ruling_checks_every_field(self):
        good = {"session": "B1", "prereg_sha256": "p", "image_sha256": "i", "b1_manifest_sha256": "m", "master_seed": 5}
        rn.bind_ruling(dict(good), "t", "p", "i", "m", 5)
        for k in good:
            bad = dict(good); bad[k] = "zz" if k != "master_seed" else 6
            with self.assertRaises(rn.Refusal):
                rn.bind_ruling(bad, "t", "p", "i", "m", 5)
        with self.assertRaises(rn.Refusal):
            rn.bind_ruling(dict(good), "t", "p", "i", "m", 5, session="B1Q")

    def test_the_profiles_are_distinct_and_the_b1q_runner_is_the_qualification_profile(self):
        self.assertEqual(rn.QUALIFICATION["session"], "B1Q"); self.assertEqual(rn.QUALIFICATION["ruling_text"], qadj.RULING_TEXT)
        self.assertIs(rn.QUALIFICATION["adjudicate"], qadj.adjudicate); self.assertFalse(rn.QUALIFICATION["require_qualification"])
        self.assertTrue(rn.MAPPING["require_qualification"])
        src = (R / "host/b1q_runner.py").read_text()
        self.assertIn("rn.main(profile=rn.QUALIFICATION)", src)

    def test_identity_check_names_every_mismatch(self):
        plan = {"budget": 333, "master_seed": 7, "protocol": "rel-v4"}
        m = {"cartographer": {"version": "carto-v1"}, "universe": {"sha256": "u" * 64}, "carrier": {"bitstream_sha256": "c" * 64}}
        check = rn.identity_check_for(plan, m)
        good = {"carto_version": "carto-v1", "universe_sha256": "u" * 64, "probe_budget": 333, "master_seed": 7,
                "protocol": "rel-v4", "rec_retry_control": True, "sign_retry_control": True, "findings": [],
                "carrier_variant": "0x42310001", "carrier_sha256": "c" * 64}
        self.assertEqual(check(good), [])
        bad = dict(good); bad["probe_budget"] = 1; bad["findings"] = ["x"]
        self.assertEqual(len(check(bad)), 2)
        for k, v in (("carrier_variant", "0x42310000"), ("carrier_sha256", "d" * 64)):
            bad = dict(good); bad[k] = v
            out = check(bad)
            self.assertEqual(len(out), 1); self.assertIn(k, out[0])


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Order(unittest.TestCase):
    """The order after preflight is FIXED: archive the session artifacts → claim the ruling →
    open the serial port → the session. An archive failure consumes nothing and opens
    nothing (owner's review 2026-09-05)."""

    def run_execute(self, archive_ok: bool):
        from unittest import mock
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import board_session as bsn
        import l3_runner as l3
        import pcap_probe_runner as pr
        import b1_qualification as bq
        calls: list[str] = []
        d = Path(tempfile.mkdtemp())
        a = types.SimpleNamespace(out=d / "out", ruling=d / "r.json", provision_ruling=d / "p.json", port="/dev/null")
        a.ruling.write_text("{}"); a.provision_ruling.write_text("{}")
        cfg = {"manifest_path": d / "m.json", "ruling_path": a.ruling, "provision_ruling_path": a.provision_ruling,
               "manifest_sha256": "x", "ruling": {}, "provision_ruling_parsed": {}}
        def archive(*args, **kw):
            calls.append("archive")
            if not archive_ok:
                raise bq.QualificationRefusal("forced")
        class Transport:
            def __init__(self, port): calls.append("open")
            def close(self): calls.append("close")
        with mock.patch.object(bq, "write_session_artifacts", archive), \
             mock.patch.object(pr, "claim_ruling", lambda p: calls.append("claim") or d / "consumed"), \
             mock.patch.object(pr, "record_outcome", lambda c, o: calls.append("record")), \
             mock.patch.object(l3, "_install_sigterm", lambda: None), \
             mock.patch.object(l3, "_record_pk", lambda p, o: None), \
             mock.patch.object(bsn, "SerialTransport", Transport), \
             mock.patch.object(bsn, "BoardSession", lambda t: t), \
             mock.patch.object(rn, "run_session", lambda s, o, r, c: calls.append("session") or {"outcome": "PASS"}):
            rc, outcome = rn.execute(a, cfg)
        return calls, rc, outcome

    def test_archive_precedes_claim_precedes_port_precedes_session(self):
        calls, rc, outcome = self.run_execute(True)
        self.assertEqual(calls, ["archive", "claim", "open", "session", "close", "record"])
        self.assertEqual((rc, outcome), (0, "PASS"))

    def test_an_archive_failure_consumes_nothing_and_opens_nothing(self):
        calls, rc, outcome = self.run_execute(False)
        self.assertEqual(calls, ["archive"])
        self.assertEqual(rc, 2); self.assertIn("not archived", outcome)

    def test_the_session_function_refuses_without_the_archived_artifacts(self):
        d = Path(tempfile.mkdtemp())
        with self.assertRaises(RuntimeError):
            rn.run_session(None, d, {}, {"profile": rn.MAPPING})


if __name__ == "__main__":
    unittest.main()
