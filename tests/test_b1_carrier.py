"""The B1 carrier — host-verifiable qualification (docs/b1_carrier_qualification.md §2).

The B1 RTL is the instrument's with the parameterised gate and the VARIANT register; the
carrier's own files must be the ones the instrument imported, byte for byte; the build
record must say routed, isolation passed, ICAPE2 = 0, positive slack, top b1_top; the
carrier manifest (the instrument's own generator over the new bitstream) must validate,
name the same twelve blank target frames, and hash to the bitstream; the MMIO allowlist of
the B1 application must not exceed the B1 register file's decode (the instrument's rule,
ported); and the iverilog benches must pass when iverilog is present."""
from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

BUILD = R / "builds/b1"
HAVE_INSTRUMENT = inst.DEFAULT_ROOT.is_dir()
HAVE_IVERILOG = shutil.which("iverilog") is not None and shutil.which("vvp") is not None
APP = (R / "firmware/b1/b1_app.c").read_text()
RTL = (R / "rtl/b1/b1_axil.v").read_text()
KEY_WINDOW = frozenset(range(0x2160, 0x2170, 4))


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


class CarrierSources(unittest.TestCase):
    @unittest.skipUnless(HAVE_INSTRUMENT, "instrument absent")
    def test_carrier_files_are_the_instruments_imports(self):
        for rel in ("carrier_axi3_lite.v", "carrier_scorer.v", "carrier.xdc", "isolation_checks.tcl",
                    "generated/carrier_base_init.vh", "generated/carrier_constants.json",
                    "generated/carrier_targets.hex", "generated/carrier_vector_order.hex"):
            here = R / "vivado/carrier" / rel
            theirs = inst.DEFAULT_ROOT / "imported/fabricmap/vivado/carrier" / rel
            self.assertEqual(sha(here), sha(theirs), rel)

    @unittest.skipUnless(HAVE_INSTRUMENT, "instrument absent")
    def test_siphash_is_verbatim_and_the_gate_is_the_instruments_plus_the_parameter(self):
        self.assertEqual(sha(R / "rtl/b1/p3_siphash.v"), sha(inst.DEFAULT_ROOT / "rtl/p3_siphash.v"))
        gate = (R / "rtl/b1/b1_arm_gate.v").read_text()
        base = (inst.DEFAULT_ROOT / "rtl/p3_arm_gate.v").read_text()
        self.assertIn("parameter integer SEMANTIC_GATE = 0", gate)
        self.assertIn("SEMANTIC_GATE == 0 || functional_readout == expected_tables", gate)
        # everything of the instrument's gate below its header survives except the compare block
        for needle in ("F_ARM_NOKEY", "F_ARM_AUTH", "nonce <= xorshift(nonce);", "sh_tag == tag_in", "functional_readout[(LUTS-1-i)*64 + sweep_vector] <= lut_q[i]"):
            self.assertIn(needle, gate); self.assertIn(needle, base)
        axil = RTL
        self.assertIn("16'h2034", axil)
        self.assertIn("VARIANT_WORD = 32'h42310001", axil)
        self.assertIn("wr_key", axil)          # the write-once key window is intact


class BuildRecord(unittest.TestCase):
    @unittest.skipUnless((BUILD / "b1_build.json").is_file(), "no B1 build in builds/b1 (Vivado output is not committed)")
    def test_build_json_and_bitstream(self):
        b = json.loads((BUILD / "b1_build.json").read_text())
        self.assertEqual(b["top"], "b1_top")
        self.assertTrue(b["routed"])
        self.assertEqual(b["cell_isolation"], "passed")
        self.assertEqual(b["icape2_cells"], 0)
        self.assertGreater(b["wns_ns"], 0)
        self.assertEqual(b["bitstream_sha256"], sha(BUILD / "b1.bit"))
        iso = (BUILD / "isolation.txt").read_text()
        self.assertIn("target cells: 6", iso)
        self.assertIn("flush cells:  0", iso)

    @unittest.skipUnless((BUILD / "carrier_manifest.json").is_file() and HAVE_INSTRUMENT, "no carrier manifest or instrument absent")
    def test_carrier_manifest_validates_and_matches(self):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        from validators import records
        m = json.loads((BUILD / "carrier_manifest.json").read_text())
        records.validate(m)
        self.assertEqual(m["bitstream_sha256"], sha(BUILD / "b1.bit"))
        self.assertTrue(m["no_icap"])
        self.assertTrue(all(v == 0 for v in m["target_frames_nonzero_words"].values()))
        self.assertEqual(len(m["target_frames_nonzero_words"]), 12)
        self.assertTrue(m["positive_control"]["globally_unique"])
        ref = json.loads((inst.DEFAULT_ROOT / "builds/p3/carrier_manifest.json").read_text())
        self.assertEqual(sorted(m["target_frames_nonzero_words"]), sorted(ref["target_frames_nonzero_words"]))
        self.assertEqual(m["nonce_seed"], ref["nonce_seed"])


class MmioAllowlist(unittest.TestCase):
    """The instrument's test_axi_map_vs_rtl, ported: app decode ⊆ RTL decode on read and on
    write; RTL − app is closed (the key window on write; VARIANT is read by the app)."""
    DEFINES = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"#define (P3_\w+) (0x[0-9A-Fa-f]+)u", APP)}

    def _fn(self, name):
        start = APP.index(f"static int {name}(uint32_t off)")
        return APP[start:APP.index("\n}", start)]

    def app_offsets(self, fn):
        body = self._fn(fn)
        out = set()
        for m in re.finditer(r"off == (P3_\w+)", body):
            out.add(self.DEFINES[m.group(1)])
        for m in re.finditer(r"off >= (P3_\w+) && off < P3_\w+ \+ (\d+)u \* 4u", body):
            base, n = self.DEFINES[m.group(1)], int(m.group(2))
            out.update(base + 4 * i for i in range(n))
        return out

    def rtl_reads(self):
        out = set()
        for m in re.finditer(r"ra == 16'h([0-9A-Fa-f]{4})", RTL):
            out.add(int(m.group(1), 16))
        for m in re.finditer(r"ra >= 16'h([0-9A-Fa-f]{4}) && ra < 16'h([0-9A-Fa-f]{4})", RTL):
            out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
        return out

    def rtl_writes(self):
        out = {0x2000}
        for m in re.finditer(r"wire wr_\w+\s*=\s*\(wa >= 16'h([0-9A-Fa-f]{4})\) && \(wa < 16'h([0-9A-Fa-f]{4})\)", RTL):
            out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
        return out

    def test_read_allowlist_within_rtl_and_variant_present(self):
        app, rtl = self.app_offsets("axi_readable"), self.rtl_reads()
        self.assertEqual(sorted(hex(x) for x in app - rtl), [])
        self.assertEqual(sorted(hex(x) for x in rtl - app), [])
        self.assertIn(0x2034, app)

    def test_write_allowlist_within_rtl_and_only_the_key_window_beyond(self):
        app, rtl = self.app_offsets("axi_writable"), self.rtl_writes()
        self.assertEqual(sorted(hex(x) for x in app - rtl), [])
        self.assertEqual(rtl - app, KEY_WINDOW)


class Benches(unittest.TestCase):
    @unittest.skipUnless(HAVE_IVERILOG and HAVE_INSTRUMENT, "iverilog or the instrument absent")
    def test_siphash_and_b1_core_benches_pass(self):
        p = subprocess.run(["bash", str(R / "sim/b1/run.sh")], capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("tb_b1_core:               TB_PASS", p.stdout)


if __name__ == "__main__":
    unittest.main()
