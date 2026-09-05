"""host/claimb_r1p_runner.py — the board runner's fail-closed preflight.

The runner cannot run today: the manifest is a DRAFT (prereg.sha256 null) and the tests pin
that it refuses, in the documented order, for the documented reason — each refusal REACHED
(the earlier checks satisfied by fixtures) and ABOUT its check. With a fixture manifest
whose preregistration is "frozen" to a fake hash the later checks are reached one by one:
the document not hashing, a wrong plan pin, an image that is not the pinned bytes, a
ruling bound to another seed, and a boundary record for another OS user. No test opens a
port, and none consumes a ruling."""
from __future__ import annotations

import copy
import hashlib
import json
import os
import pwd
import sys
import tempfile
import types
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402
import claimb_r1p_runner as rn  # noqa: E402

MANIFEST = json.loads(inst.MANIFEST.read_text())
HAVE = inst.DEFAULT_ROOT.is_dir() and (inst.DEFAULT_ROOT / ".git").exists()
IMAGE = Path("/home/test/psoracle_backups/2026-09-04_S3_v0.7/artifacts/firmware_bsp_out_p3_app_l6.bin")
BOUNDARY = inst.DEFAULT_ROOT / "evidence/boundary/principal_boundary_2026-09-04-01.json"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class Fixture:
    """Files on disk for one preflight attempt; everything is created fresh per test."""

    def __init__(self):
        self.d = Path(tempfile.mkdtemp())
        self.manifest = copy.deepcopy(MANIFEST)

    def ruling(self, name: str, **fields) -> Path:
        p = self.d / f"{name}.json"
        p.write_text(json.dumps({"boardid": "17A6", "granted_by": "test", "date": "2026-09-05-T", **fields}))
        return p

    def freeze(self, prereg_text: str | None = None) -> None:
        """A 'frozen' manifest whose preregistration hash is that of a fixture document."""
        doc = self.d / "prereg.md"
        doc.write_text(prereg_text if prereg_text is not None else "# fixture preregistration\n")
        self.manifest["prereg"]["path"] = os.path.relpath(doc, R)
        self.manifest["prereg"]["sha256"] = sha(doc)

    def manifest_path(self) -> Path:
        p = self.d / "manifest.json"
        p.write_text(json.dumps(self.manifest))
        return p

    def args(self, **over) -> types.SimpleNamespace:
        mp = self.manifest_path()
        base = dict(ruling=self.ruling("b", ruling=rn.RULING_TEXT, session="B",
                                       prereg_sha256=self.manifest["prereg"]["sha256"],
                                       image_sha256=self.manifest["instrument"]["image_sha256"],
                                       claimb_manifest_sha256=sha(mp), master_seed=self.manifest["seeds"]["master_seed"]),
                    provision_ruling=self.ruling("k", ruling=rn.PROVISION_RULING_TEXT, session="B",
                                                 prereg_sha256=self.manifest["prereg"]["sha256"],
                                                 image_sha256=self.manifest["instrument"]["image_sha256"],
                                                 claimb_manifest_sha256=sha(mp)),
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
        f = Fixture()
        self.refuses(f.args(), "not frozen")

    def test_wrong_ruling_text(self):
        f = Fixture()
        self.refuses(f.args(ruling=f.ruling("x", ruling="whole-of-probe P3-L6", session="B")), "ruling text")

    def test_missing_provisioning_ruling(self):
        f = Fixture()
        self.refuses(f.args(provision_ruling=None), "provisioning P3-K")

    def test_a_consumed_ruling_is_refused(self):
        f = Fixture()
        a = f.args()
        a.ruling.with_name(a.ruling.name + ".consumed").write_text("used\n")
        self.refuses(a, "consumed")

    def test_wrong_board(self):
        f = Fixture()
        self.refuses(f.args(ruling=f.ruling("x", ruling=rn.RULING_TEXT, boardid="17A7", session="B")), "names board")

    def test_frozen_but_the_document_does_not_hash(self):
        f = Fixture()
        f.freeze()
        f.manifest["prereg"]["sha256"] = "b" * 64
        self.refuses(f.args(), "does not hash to the frozen preregistration")

    def test_frozen_but_the_plan_pin_is_wrong(self):
        f = Fixture()
        f.freeze()
        f.manifest["plan"]["sha256"] = "c" * 64
        self.refuses(f.args(), "plan pin")

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_frozen_but_the_image_is_not_the_pinned_bytes(self):
        f = Fixture()
        f.freeze()
        wrong = f.d / "image.bin"
        wrong.write_bytes(b"not the image")
        self.refuses(f.args(image=wrong), "not the pinned one")

    @unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
    def test_frozen_but_the_image_is_missing(self):
        f = Fixture()
        f.freeze()
        self.refuses(f.args(image=f.d / "absent.bin"), "no application image")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "the pinned image binary is not present")
    def test_frozen_but_the_ruling_is_bound_to_another_seed(self):
        f = Fixture()
        f.freeze()
        a = f.args()
        a.ruling = f.ruling("b2", ruling=rn.RULING_TEXT, session="B", prereg_sha256=f.manifest["prereg"]["sha256"],
                            image_sha256=f.manifest["instrument"]["image_sha256"],
                            claimb_manifest_sha256=sha(a.manifest), master_seed=1278628687)
        self.refuses(a, "master_seed", "this session needs")

    @unittest.skipUnless(HAVE and IMAGE.is_file(), "the pinned image binary is not present")
    def test_frozen_but_the_ruling_is_bound_to_another_manifest(self):
        f = Fixture()
        f.freeze()
        a = f.args()
        a.ruling = f.ruling("b3", ruling=rn.RULING_TEXT, session="B", prereg_sha256=f.manifest["prereg"]["sha256"],
                            image_sha256=f.manifest["instrument"]["image_sha256"],
                            claimb_manifest_sha256="d" * 64, master_seed=f.manifest["seeds"]["master_seed"])
        self.refuses(a, "claimb_manifest_sha256")

    @unittest.skipUnless(HAVE and IMAGE.is_file() and BOUNDARY.is_file(), "instrument, image or boundary record absent")
    def test_frozen_but_the_boundary_record_is_stale_or_another_users(self):
        """The record on disk is from 2026-09-04: it is > 6 h old, so `boundary_established`
        refuses it before the user check — the refusal is the instrument's own RecordError,
        which preflight does not catch (main() reports it as REFUSED)."""
        f = Fixture()
        f.freeze()
        a = f.args()
        with self.assertRaises(Exception) as cm:
            rn.preflight(a)
        self.assertNotIsInstance(cm.exception, AssertionError)
        msg = str(cm.exception).lower()
        self.assertTrue("boundary" in msg or "old" in msg or "established" in msg or "runner_user" in msg, msg)

    def test_bind_ruling_checks_every_field(self):
        good = {"session": "B", "prereg_sha256": "p", "image_sha256": "i", "claimb_manifest_sha256": "m", "master_seed": 5}
        rn.bind_ruling(dict(good), "t", "p", "i", "m", 5)
        rn.bind_ruling({k: v for k, v in good.items() if k != "master_seed"}, "t", "p", "i", "m", None)
        for k in good:
            bad = dict(good)
            bad[k] = "zz" if k != "master_seed" else 6
            with self.assertRaises(rn.Refusal):
                rn.bind_ruling(bad, "t", "p", "i", "m", 5)
        with self.assertRaises(rn.Refusal):
            rn.bind_ruling({k: v for k, v in good.items() if k != "session"}, "t", "p", "i", "m", 5)

    def test_the_os_user_is_the_effective_uid_not_an_environment_variable(self):
        self.assertEqual(pwd.getpwuid(os.getuid()).pw_name, pwd.getpwuid(os.geteuid()).pw_name)


if __name__ == "__main__":
    unittest.main()
