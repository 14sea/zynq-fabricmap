"""One number, four places, and they must agree.

The configuration-stream IDCODE is written by the host into every envelope's word 15 and
checked there by `carrier_stream`. For a whole session they disagreed: the RTL carried the
PSS/JTAG identity 0x13722093 while the host emitted 0x03722093, taken from the carrier
bitstream itself. UG470 makes IDCODE[31:28] a revision field, so a bitstream's IDCODE
register write masks it off; the JTAG read does not.

Nothing caught it because each side was tested against a copy of its own assumption. The RTL
bench typed 0x13722093 into its synthetic envelope, and the host gate judges frame content
rather than the control skeleton, so both passed while every real envelope was refused at
word 15 with F_CONTROL -- which the board answered with SLVERR, a data abort and a reboot.

This is the test that would have caught it: the published bitstream, the manifest, the
envelope the host actually builds, and the RTL parameter, compared against each other rather
than each against itself.
"""

from __future__ import annotations

import re
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import board_calibrate_noop as cal  # noqa: E402
import board_carrier_exec as ex  # noqa: E402

RUN_DIR = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_11_erratum002"
CARRIER_STREAM_V = REPO_ROOT / "vivado/carrier/carrier_stream.v"
IDCODE_WORD = 15

JTAG_IDCODE = 0x13722093       # the PSS/JTAG identity: NOT what a stream carries


def rtl_config_idcode() -> int:
    text = CARRIER_STREAM_V.read_text(encoding="utf-8")
    found = re.search(r"parameter\s*\[31:0\]\s*CONFIG_IDCODE\s*=\s*32'h([0-9A-Fa-f]{8})", text)
    if not found:
        raise AssertionError("carrier_stream.v has no CONFIG_IDCODE parameter")
    return int(found.group(1), 16)


class TheFourSourcesAgree(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not (RUN_DIR / "carrier.bit").is_file():
            raise unittest.SkipTest("the published carrier bitstream is not present")
        try:
            cls.authority = ex.PublishedCarrierAuthority.load(RUN_DIR)
        except Exception as refusal:                       # noqa: BLE001
            raise unittest.SkipTest(f"the run is not a published authority here: {refusal}")
        cls.manifest = cls.authority.manifest_copy()

    def test_the_rtl_parameter_is_the_configuration_idcode(self):
        self.assertNotEqual(rtl_config_idcode(), JTAG_IDCODE,
                            "the RTL is checking the JTAG identity again")

    def test_the_bitstream_and_the_manifest_agree(self):
        parsed = bf.parse_frames(RUN_DIR / "carrier.bit")
        self.assertEqual(parsed["idcode"],
                         int(self.manifest["base_bitstream"]["idcode"], 16))

    def test_the_manifest_and_the_rtl_agree(self):
        self.assertEqual(int(self.manifest["base_bitstream"]["idcode"], 16),
                         rtl_config_idcode())

    def test_the_envelope_word_the_host_builds_is_that_same_value(self):
        """The end of the chain: what actually goes on the wire at position 15."""
        candidate = cal.noop_candidate(self.manifest, RUN_DIR / "carrier.bit")
        payload = ex.build_sequence_bytes(self.manifest, candidate)
        words = struct.unpack(f">{len(payload) // 4}I", payload)
        self.assertEqual(words[IDCODE_WORD], rtl_config_idcode())

    def test_every_envelope_carries_it_not_just_the_first(self):
        candidate = cal.noop_candidate(self.manifest, RUN_DIR / "carrier.bit")
        payload = ex.build_sequence_bytes(self.manifest, candidate)
        words = struct.unpack(f">{len(payload) // 4}I", payload)
        env_words = len(words) // 3
        for env in range(3):
            with self.subTest(envelope=env):
                self.assertEqual(words[env * env_words + IDCODE_WORD], rtl_config_idcode())


class TheBenchFixtureIsTheHostsBytes(unittest.TestCase):
    """The Verilog benches now read this file instead of re-typing the RTL's constants."""

    FIXTURE = REPO_ROOT / "vivado/carrier/tb_envelope0.hex"

    def test_the_fixture_exists_and_is_one_envelope(self):
        words = [line for line in self.FIXTURE.read_text().split() if line]
        self.assertEqual(len(words), 536)

    def test_its_word_15_is_the_configuration_idcode(self):
        words = self.FIXTURE.read_text().split()
        self.assertEqual(int(words[IDCODE_WORD], 16), rtl_config_idcode())

    def test_no_verilog_bench_retypes_the_jtag_idcode_as_a_stream_word(self):
        """0x13722093 may appear as a negative control, never as an envelope's word 15."""
        for path in sorted((REPO_ROOT / "vivado/carrier").glob("tb_*.v")):
            text = path.read_text(encoding="utf-8")
            for line in text.splitlines():
                # Comments describing the old defect are not the old defect. Prose about a
                # call has been mistaken for the call three times in this project already.
                code = line.split("//", 1)[0]
                if "13722093" in code and "env_words[15]" in code:
                    self.fail(f"{path.name} builds word 15 from the JTAG identity: {line!r}")


if __name__ == "__main__":
    unittest.main()
