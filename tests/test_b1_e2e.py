"""The end-to-end MODELLED B1 session (host/b1_modelled_session.py): the whole 335-record
session through the instrument's real host stack — reader, console, notary relay with the
B1 zero-table signer, collector, audit pulls of the candidates' REAL staging words — written
as the runner writes it and adjudicated by the real adjudicator with the instrument's
validators (b1_records + the audit gate + the structural/closure/rate checks). One positive
(truth fabric → PASS with the predicted metrics, 335/335 audited, chain 336), the negatives
that must not pass (a permuted fabric; served words that do not recompute; a readout the
board's own block contradicts), and the faulty channel (rel-v4 recovery). Nothing here
touches a board, a port, or the key store."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b1_adjudicate as adj  # noqa: E402
import b1_modelled_session as ms  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402
from test_b1_qualification import qualify, reseal_exports  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
MANIFEST = json.loads((R / "manifests/b1_manifest.json").read_text())
PLAN = json.loads((R / "evidence/b1/plan.json").read_text())
PRED = json.loads((R / "evidence/b1/prediction.json").read_text())


def frozen(tmp: Path) -> tuple[dict, str]:
    import os
    m = copy.deepcopy(MANIFEST)
    doc = tmp / "prereg.md"; doc.write_text("# fixture preregistration\n")
    m["prereg"]["path"] = os.path.relpath(doc, R)
    m["prereg"]["sha256"] = hashlib.sha256(doc.read_bytes()).hexdigest(); m["prereg"]["frozen"] = True
    m["image"]["board_ready"] = True
    rec, _, _, _ = qualify(tmp, m, "b1q")                       # the real chain, modelled
    m["carrier"]["qualification"] = rec; m["carrier"]["qualified"] = True
    return m, hashlib.sha256(json.dumps(m, indent=1, ensure_ascii=False).encode()).hexdigest()


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Modelled(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp())
        cls.m, cls.msha = frozen(cls.tmp)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def session(self, name: str, **kw) -> tuple[Path, dict]:
        out = self.tmp / name
        r = ms.run_modelled(self.m, PLAN, out, binding_extra={"b1_manifest_sha256": self.msha}, **kw)
        return out, r

    def adjudicate(self, out: Path) -> dict:
        return adj.adjudicate(out, self.m, PLAN, PRED, self.msha, require_git=False)

    def test_truth_fabric_passes_end_to_end(self):
        out, r = self.session("truth")
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED"); self.assertEqual(r["records"], PLAN["records"])
        for f in ("run_log.json", "audits.json", "timeline.json"):
            self.assertTrue((out / f).is_file(), f)
        res = self.adjudicate(out)
        self.assertEqual(res["outcome"], "PASS", res["findings"])
        v = res["p3"]["run_log_validation"] if "p3" in res else res["instrument"]["run_log_validation"]
        self.assertEqual((v["scored"], v["audited"], v["chain_length"]), (PLAN["records"], PLAN["records"], PLAN["records"] + 1))
        b = res["b1_result"]
        self.assertEqual((b["precision"], b["recall"], b["anomalies"], b["unobserved_claims"]), (1.0, 1.0, 0, 0))
        self.assertTrue(res["prediction_comparison"]["content_equal"])
        self.assertEqual(adj.schema_findings(res["self_map_v2"]), [])
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(log["app_identity"]["schema_version"], "1.4.0")
        self.assertTrue(all(int(t, 16) == 0 for e in log["notary_log"]["entries"] for t in e["answer"]["expected_tables"]))
        self.assertEqual(log["session_summary"]["audit"], {"audited": PLAN["records"], "total": PLAN["records"]})

    def test_a_permuted_fabric_is_a_hold(self):
        out, r = self.session("permuted", fixture="permuted", fixture_seed=4)
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED")
        res = self.adjudicate(out)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertFalse(res["prediction_comparison"]["content_equal"])
        self.assertTrue(any(f.startswith("verifier:") for f in res["findings"]))

    def test_served_words_that_do_not_recompute_are_a_kill(self):
        out, _ = self.session("tamper_words")
        a = json.loads((out / "audits.json").read_text())
        c = next(ch for ch in a["chunks"] if ch["seq"] == 40 and ch["chunk"] == 0)
        import base64
        raw = bytearray(base64.urlsafe_b64decode(c["entries"])); raw[8] ^= 0x01     # sparse-v1: (offset u16, value u32) entries; byte 8 is entry 1's value
        c["entries"] = base64.urlsafe_b64encode(bytes(raw)).decode()
        (out / "audits.json").write_text(json.dumps(a)); reseal_exports(out)
        res = self.adjudicate(out)
        self.assertTrue(res["outcome"].startswith("KILL falsified"), res["outcome"])
        self.assertIn("served raw words", res["outcome"])

    def test_a_readout_the_boards_block_contradicts_is_named(self):
        out, _ = self.session("tamper_readout")
        log = json.loads((out / "run_log.json").read_text())
        rec = next(r for r in log["loop_records"] if r["seq"] == 30)
        t = rec["evidence"]["score"]["functional_readout"]; t[0] = f"{int(t[0], 16) ^ 1:016x}"
        (out / "run_log.json").write_text(json.dumps(log)); reseal_exports(out)
        res = self.adjudicate(out)
        self.assertNotEqual(res["outcome"], "PASS")
        self.assertTrue(any("autonomy replay" in f or "carto" in f for f in res["findings"]), res["findings"])

    def test_the_faulty_channel_still_completes(self):
        out, r = self.session("faulty", p_fault=0.01, seed=3)
        self.assertEqual(r["epoch_end"]["kind"], "COMPLETED", r)
        self.assertEqual(r["records"], PLAN["records"])
        self.assertGreater(r["faults"], 0)


if __name__ == "__main__":
    unittest.main()
