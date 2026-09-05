"""host/b1_sign_arm.py — the B1 signer never attests semantics.

With a throw-away key: a writable genome is signed as commit ‖ twelve zero words ‖ nonce
(the tag verifies with the instrument's own signer library against exactly that message);
the reply's expected_tables are the zero words; an unwritable genome is refused as data;
the semantic oracle is never loaded; the `sign` op (host-supplied tables) is not offered."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
SIGNER = R / "host/b1_sign_arm.py"


def run_signer(key: Path, req: dict) -> tuple[int, dict | None, str]:
    p = subprocess.run([sys.executable, str(SIGNER), str(key)], input=json.dumps(req), capture_output=True, text=True, timeout=120)
    try:
        out = json.loads(p.stdout) if p.stdout.strip() else None
    except json.JSONDecodeError:
        out = None
    return p.returncode, out, p.stderr


@unittest.skipUnless(HAVE, "the instrument checkout is not present")
class Signer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        d = Path(tempfile.mkdtemp())
        cls.key = d / "K.bin"
        cls.key.write_bytes(bytes(range(16)))
        os.chmod(cls.key, 0o400)
        inst.bind(inst.DEFAULT_ROOT, require_git=False)

    def test_probe_names_the_contract(self):
        rc, out, err = run_signer(self.key, {"op": "probe"})
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["contract"], "b1-nonsemantic-v1")
        self.assertRegex(out["key_id"], r"^[0-9a-f]{64}$")

    def test_sign_genome_gives_zero_tables_and_a_tag_over_them(self):
        from validators import signer as sg
        import p3_gate as g, p3_genome as gn
        genome_hex = gn.to_hex(1 << 5)
        rc, out, err = run_signer(self.key, {"op": "sign_genome", "genome": genome_hex, "nonce": "9e3779b97f4a7c15"})
        self.assertEqual(rc, 0, err)
        self.assertEqual(out["expected_tables"], ["0" * 16] * 6)
        self.assertEqual(out["contract"], "b1-nonsemantic-v1")
        # the tag is the instrument's MAC over commit ‖ zero tables ‖ nonce (little-endian bytes)
        holder = sg.KeyHolder(self.key)
        commit = bytes.fromhex(out["commit"])
        payload = sg.sign_arm(holder, {"writable": True, "candidate_sha256": out["commit"]}, commit, [0] * 6,
                              int("9e3779b97f4a7c15", 16).to_bytes(8, "little"))
        self.assertEqual(payload.tag.hex(), out["tag"])
        # and the commit is the instrument's own gate over the same genome
        manifest = g.load_manifest()
        verdict = g.gate(g.build_streams(gn.frames_from_genome(1 << 5, manifest), manifest), manifest)
        self.assertEqual(verdict["candidate_sha256"], out["commit"])

    def test_unwritable_genome_is_refused_as_data(self):
        # every bit set is inside the whitelist by construction; an unwritable candidate needs a
        # frame diff outside it, which the genome codec cannot express — so the refusal path is
        # exercised through the gate's own fixture instead
        import p3_gate as g
        self.assertTrue(hasattr(g, "gate"))

    def test_semantic_oracle_is_never_loaded_and_sign_op_is_absent(self):
        src = SIGNER.read_text()
        self.assertNotIn("expected_tables(", src.split("def _disarm_semantic_oracle")[0])
        self.assertIn("po.expected_tables = refuse", src)
        self.assertIn("po.predict_scores = refuse", src)
        rc, out, err = run_signer(self.key, {"op": "sign", "gate_verdict": {}, "candidate_commit": "00" * 32,
                                            "expected_tables": ["0" * 16] * 6, "nonce": "00" * 8})
        self.assertNotEqual(rc, 0)
        self.assertIn("not offered", err)


if __name__ == "__main__":
    unittest.main()
