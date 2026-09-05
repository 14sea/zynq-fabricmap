"""host/b1_records.py — the B1 successor of the instrument's record validator: ONE rule
changed. Rule (iii) no longer compares the readout with the reply's tables; it refuses a
reply whose signed table words are not zero (the host attested semantics — the contract
violation), and checks the readout for shape only. Everything else must behave as the
instrument's validator on the same record."""
from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()
S3 = inst.DEFAULT_ROOT / "evidence/l6_17A6_2026-09-04-01-S/run_log.json"


@unittest.skipUnless(HAVE and S3.is_file(), "the instrument checkout (and S #3's log as a record fixture) is not present")
class RuleThreeB1(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records
        from validators import records
        cls.b1, cls.p3 = b1_records, records
        log = json.loads(S3.read_text())
        cls.rec = next(r for r in log["loop_records"] if r["outcome"] == "SCORED" and r["seq"] == 2)

    def b1_version(self, rec: dict) -> dict:
        """The same record under the B1 contract: the signed tables are the zero words."""
        r = copy.deepcopy(rec)
        r["evidence"]["sign_reply"]["expected_tables"] = ["0" * 16] * 6
        return r

    def test_the_instrument_accepts_its_own_record_and_the_b1_validator_refuses_it_as_attested(self):
        self.p3.validate(self.rec)
        with self.assertRaises(self.b1.RecordError) as cm:
            self.b1.validate(self.rec)
        self.assertIn("(iii-B1)", str(cm.exception))

    def test_the_b1_validator_accepts_the_zero_table_reply_with_any_readout(self):
        r = self.b1_version(self.rec)
        self.b1.validate(r)
        r2 = copy.deepcopy(r)
        r2["evidence"]["score"]["functional_readout"][3] = "ffffffffffffffff"      # the fabric read something else: fine
        self.b1.validate(r2)
        with self.assertRaises(Exception):
            self.p3.validate(r)                 # the instrument's rule (iii) would refuse the zero-table reply

    def test_readout_shape_is_still_checked(self):
        r = self.b1_version(self.rec)
        r["evidence"]["score"]["functional_readout"] = ["00"] * 6
        with self.assertRaises(self.b1.RecordError):
            self.b1.validate(r)
        r = self.b1_version(self.rec)
        r["evidence"]["score"]["functional_readout"] = ["0" * 16] * 5
        with self.assertRaises(self.b1.RecordError):
            self.b1.validate(r)

    def test_every_other_rule_is_the_instruments(self):
        r = self.b1_version(self.rec)
        r["evidence"]["score"]["hw_candidate_commit"] = "0" * 64
        with self.assertRaises(self.b1.Falsified):
            self.b1.validate(r)                 # (ii) commit mismatch is still a falsification
        r = self.b1_version(self.rec)
        r["evidence"]["arm"]["nonce_after"] = r["evidence"]["arm"]["nonce_before"]
        with self.assertRaises(Exception):
            self.b1.validate(r)                 # the nonce chain rule


if __name__ == "__main__":
    unittest.main()
