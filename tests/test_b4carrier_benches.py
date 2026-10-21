"""The B4 carrier v2 benches (sim/b4/run.sh): the verbatim SipHash bench, the twelve core scenarios over the hypothesis
model, and the vendor-model bench — all must pass when iverilog and the instrument are present."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
HAVE = shutil.which("iverilog") is not None and shutil.which("vvp") is not None and Path("/home/test/zynq_psoracle").is_dir()
SCENARIOS = ("regs", "flow", "fault_not_armed", "fault_nokey", "fault_unsigned", "fault_wrong_commit", "fault_wrong_key",
             "fault_sequence", "fault_double_arm", "fault_realisable", "a5", "a5_persist")


@unittest.skipUnless(HAVE, "iverilog or the instrument absent")
class Benches(unittest.TestCase):
    def test_all_benches_pass(self):
        p = subprocess.run(["bash", str(R / "sim/b4/run.sh")], capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for s in SCENARIOS:
            self.assertIn(f"TB_PASS {s}", p.stdout, s)
        self.assertIn("TB_PASS unisim", p.stdout)
        self.assertIn("tb_p3_siphash (verbatim): TB_PASS", p.stdout)


if __name__ == "__main__":
    unittest.main()
