"""The B4 carrier v2 benches (sim/b4/run.sh): the verbatim SipHash bench, the 27 core scenarios over the hypothesis model,
the vendor-model bench over the RTL core and over the GSR-aware netlist of the core (the GSR pulse PULSE clocks on both), and
the PS path through the pinned AXI3 shim — all must pass when iverilog, the instrument and the netlist are present."""
from __future__ import annotations

import shutil
import subprocess
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
HAVE = shutil.which("iverilog") is not None and shutil.which("vvp") is not None and Path("/home/test/zynq_psoracle").is_dir()
SCENARIOS = ("regs", "flow", "fault_not_armed", "fault_nokey", "fault_unsigned", "fault_wrong_commit", "fault_wrong_key",
             "fault_sequence", "fault_double_arm", "fault_realisable", "a5", "a5_persist", "a5_wrong_context",
             "a5_flag_without_injection", "open_close_refused", "p9", "p9_ok", "busy_refused", "step_atomic", "backpressure",
             "read_during_window", "read_at_launch", "session", "post_fault", "w_first", "w_first_early", "early_cleanup")


@unittest.skipUnless(HAVE, "iverilog or the instrument absent")
class Benches(unittest.TestCase):
    def test_all_benches_pass(self):
        p = subprocess.run(["bash", str(R / "sim/b4/run.sh")], capture_output=True, text=True, timeout=900)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        for s in SCENARIOS:
            self.assertIn(f"TB_PASS {s}", p.stdout, s)
        self.assertIn("tb_b4_unisim (RTL core):     TB_PASS unisim", p.stdout)
        self.assertIn("tb_b4_unisim (NETLIST core): TB_PASS unisim", p.stdout)      # the GSR-aware post-synthesis netlist (vivado/b4/netlist_core.tcl)
        self.assertIn("tb_b4_axi3 (shim):           TB_PASS axi3", p.stdout)
        self.assertIn("tb_p3_siphash (verbatim): TB_PASS", p.stdout)
        widths = [l for l in p.stdout.splitlines() if l.startswith("GSR_PULSE_WIDTHS_NS")]
        self.assertTrue(widths and all(w.split()[1:] == ["40.0", "40.0", "40.0"] for w in widths), widths)   # PULSE = 2 clocks on both benches


if __name__ == "__main__":
    unittest.main()
