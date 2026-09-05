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
import b1_runner as rn  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

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

    def freeze(self, board_ready: bool = True) -> None:
        doc = self.d / "prereg.md"
        doc.write_text("# fixture preregistration\n")
        self.manifest["prereg"]["path"] = os.path.relpath(doc, R)
        self.manifest["prereg"]["sha256"] = sha(doc)
        self.manifest["image"]["board_ready"] = board_ready

    def manifest_path(self) -> Path:
        p = self.d / "manifest.json"
        p.write_text(json.dumps(self.manifest))
        return p

    def args(self, **over) -> types.SimpleNamespace:
        mp = self.manifest_path()
        base = dict(ruling=self.ruling("b1", ruling=rn.RULING_TEXT, session="B1", prereg_sha256=self.manifest["prereg"]["sha256"],
                                       image_sha256=self.manifest["image"]["sha256"], b1_manifest_sha256=sha(mp),
                                       master_seed=self.manifest["seeds"]["master_seed"]),
                    provision_ruling=self.ruling("k", ruling=rn.PROVISION_RULING_TEXT, session="B1",
                                                 prereg_sha256=self.manifest["prereg"]["sha256"],
                                                 image_sha256=self.manifest["image"]["sha256"], b1_manifest_sha256=sha(mp)),
                    boundary=BOUNDARY, out=self.d / "out", manifest=mp, instrument_root=inst.DEFAULT_ROOT,
                    image=IMAGE, key=Path("/var/lib/p3signer/keys/K.bin"), signer_user="p3signer", port="/dev/null")
        base.update(over)
        return types.SimpleNamespace(**base)


class RefusalOrder(unittest.TestCase):
    def refuses(self, args, *words: str) -> str:
        with self.assertRaises(rn.Refusal) as cm:
            rn.preflight(args)
        msg = str(cm.exception)
        for w in words:
            self.assertIn(w, msg)
        return msg

    def test_the_committed_manifest_is_a_draft_and_refuses(self):
        self.refuses(Fixture().args(), "not frozen")

    def test_wrong_ruling_text_and_missing_provisioning(self):
        f = Fixture()
        self.refuses(f.args(ruling=f.ruling("x", ruling="whole-of-run Claim B round 1′", session="B1")), "ruling text")
        self.refuses(f.args(provision_ruling=None), "provisioning P3-K")

    def test_frozen_but_the_plan_pin_is_wrong(self):
        f = Fixture(); f.freeze()
        f.manifest["plan"]["sha256"] = "c" * 64
        self.refuses(f.args(), "plan pin")

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

    def test_identity_check_names_every_mismatch(self):
        plan = {"budget": 333, "master_seed": 7, "protocol": "rel-v4"}
        m = {"cartographer": {"version": "carto-v1"}, "universe": {"sha256": "u" * 64}}
        check = rn.identity_check_for(plan, m)
        good = {"carto_version": "carto-v1", "universe_sha256": "u" * 64, "probe_budget": 333, "master_seed": 7,
                "protocol": "rel-v4", "rec_retry_control": True, "sign_retry_control": True, "findings": []}
        self.assertEqual(check(good), [])
        bad = dict(good); bad["probe_budget"] = 1; bad["findings"] = ["x"]
        out = check(bad)
        self.assertEqual(len(out), 2)


if __name__ == "__main__":
    unittest.main()
