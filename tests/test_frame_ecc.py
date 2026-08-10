"""The frame-ECC port reproduces Vivado, or nothing goes to a board.

Preregistration §6 item 4 makes this a gate rather than a unit test: *"frame ECC after an
INIT change may not be assumed. The ECC generation path must be cross-validated
independently against multiple Vivado known-answer frames."*

The oracle is Vivado's own output. Two different questions are asked of it, and only the
second one is the one that matters:

1. **verification** — recompute the ECC of an unmodified frame and require it to equal the
   word Vivado wrote. Cheap, and covers tens of thousands of frames.
2. **edit-and-regenerate** — take a *base* frame, apply the content words of a variant that
   differs only in a LUT INIT or FF INIT, regenerate the ECC, and require the result to
   equal Vivado's variant frame **byte for byte, including word 50**. This is the exact
   operation the evolution loop performs, and it is the one an implementation that folds
   the stale ECC into its own input would fail while still passing (1).

The distinction is the trap here: an implementation that forgets to mask the ECC field out
of its own input is *stable* on unmodified frames — it reproduces whatever is already
there — and wrong on every frame it edits.
"""

from __future__ import annotations

import glob
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc as fe  # noqa: E402

LOCKED = REPO_ROOT / "build/specimen_locked"
FF_BUILD = REPO_ROOT / "build/gate_ff_formal"


def parse(path: Path) -> dict:
    return bf.parse_frames(path)["frames"]


class AlgorithmShapeTests(unittest.TestCase):
    """Properties that hold without any bitstream, so they run on a cold tree."""

    def frame(self, fill: int = 0) -> list[int]:
        return [fill] * bf.FRAME_WORDS

    def test_refuses_a_short_frame(self):
        with self.assertRaises(ValueError):
            fe.calculate_ecc([0] * 10)

    def test_update_touches_only_word_50(self):
        frame = [0x5A5A5A5A] * bf.FRAME_WORDS
        out = fe.update_ecc(frame)
        differing = [i for i in range(bf.FRAME_WORDS) if frame[i] != out[i]]
        self.assertEqual(differing, [fe.ECC_WORD])

    def test_update_does_not_disturb_the_upper_bits_of_word_50(self):
        frame = self.frame()
        frame[fe.ECC_WORD] = 0xABCD_E000 | 0x1FFF
        out = fe.update_ecc(frame)
        self.assertEqual(out[fe.ECC_WORD] & fe.ECC_KEEP, 0xABCD_E000)

    def test_the_ecc_field_is_masked_out_of_its_own_input(self):
        """The single property that separates a correct port from a plausible one.

        Two frames identical except for a stale ECC field must produce the same ECC; an
        implementation that folds the old value in produces two different answers and is
        wrong on every frame it edits.
        """
        a = [0x11111111] * bf.FRAME_WORDS
        b = list(a)
        a[fe.ECC_WORD] = 0x0000_0000
        b[fe.ECC_WORD] = 0x0000_1FFF
        self.assertEqual(fe.calculate_ecc(a) & fe.ECC_MASK, fe.calculate_ecc(b) & fe.ECC_MASK)

    def test_update_is_idempotent(self):
        frame = [0x0F0F0F0F] * bf.FRAME_WORDS
        once = fe.update_ecc(frame)
        self.assertEqual(fe.update_ecc(once), once)

    def test_a_consistent_frame_is_recognised(self):
        frame = fe.update_ecc([0x1234_5678] * bf.FRAME_WORDS)
        self.assertTrue(fe.frame_is_consistent(frame))

    def test_a_single_flipped_content_bit_invalidates_the_ecc(self):
        frame = fe.update_ecc([0] * bf.FRAME_WORDS)
        frame[51] ^= 1
        self.assertFalse(fe.frame_is_consistent(frame))

    def test_parity_bit_participates(self):
        """idx 0x64 folds a parity bit into position 12; without it the top bit is dead."""
        seen = set()
        for word in (0x1, 0x3, 0x7, 0xF, 0x1F):
            frame = [0] * bf.FRAME_WORDS
            frame[bf.FRAME_WORDS - 1] = word
            seen.add((fe.calculate_ecc(frame) >> 12) & 1)
        self.assertEqual(seen, {0, 1})


class VivadoVerificationTests(unittest.TestCase):
    """Question 1: unmodified frames, against real Vivado bitstreams."""

    def setUp(self):
        self.bits = sorted(glob.glob(str(REPO_ROOT / "build/**/*.bit"), recursive=True))
        if not self.bits:
            self.skipTest("no built bitstreams on this tree (build/ is gitignored)")

    def test_every_frame_of_a_real_bitstream_verifies(self):
        report = fe.validate_bitstream(Path(self.bits[0]))
        self.assertGreater(report["frames_checked"], 1000)
        self.assertEqual(report["mismatched"], 0, report["examples"])


class VivadoEditRegenerateTests(unittest.TestCase):
    """Question 2 — the one that matters: edit content, regenerate, match Vivado exactly."""

    def known_answer(self, base_path: Path, variant_path: Path) -> tuple[int, int]:
        base, variant = parse(base_path), parse(variant_path)
        differing = [far for far in base if base[far] != variant[far]]
        reproduced = 0
        for far in differing:
            edited = list(base[far])
            for i in range(bf.FRAME_WORDS):
                if i != fe.ECC_WORD:
                    edited[i] = variant[far][i]
            if fe.update_ecc(edited) == variant[far]:
                reproduced += 1
        return len(differing), reproduced

    def test_lut_init_specimens_reproduce_byte_for_byte(self):
        base = LOCKED / "spec_0000000000000000.bit"
        if not base.exists():
            self.skipTest(f"{LOCKED} absent (build/ is gitignored)")
        checked = 0
        for other in ("spec_0000000000000002.bit", "spec_0000000000000010.bit"):
            variant = LOCKED / other
            if not variant.exists():
                continue
            differing, reproduced = self.known_answer(base, variant)
            self.assertGreater(differing, 0, "the pair does not differ — wrong fixture")
            self.assertEqual(reproduced, differing, f"{other}: Vivado's ECC not reproduced")
            checked += differing
        self.assertGreater(checked, 0)

    def test_ff_variant_specimens_reproduce_byte_for_byte(self):
        sites = sorted(glob.glob(str(FF_BUILD / "SLICE_*")))
        if not sites:
            self.skipTest(f"{FF_BUILD} absent (build/ is gitignored)")
        total = reproduced_total = 0
        for site in sites[:4]:
            base = Path(site) / "base" / "spec.bit"
            if not base.exists():
                continue
            for variant_dir in sorted(glob.glob(site + "/zini_*"))[:1]:
                variant = Path(variant_dir) / "spec.bit"
                if not variant.exists():
                    continue
                differing, reproduced = self.known_answer(base, variant)
                total += differing
                reproduced_total += reproduced
        if total == 0:
            self.skipTest("no base/variant pair available")
        self.assertEqual(reproduced_total, total)

    def test_a_stale_ecc_would_not_have_matched(self):
        """Negative control: keeping the base ECC fails the same comparison.

        Without this, the test above would pass for an implementation that copied the
        variant's word 50 across instead of computing it.
        """
        base_path = LOCKED / "spec_0000000000000000.bit"
        variant_path = LOCKED / "spec_0000000000000002.bit"
        if not (base_path.exists() and variant_path.exists()):
            self.skipTest("locked specimens absent")
        base, variant = parse(base_path), parse(variant_path)
        differing = [far for far in base if base[far] != variant[far]]
        self.assertTrue(differing)
        for far in differing:
            stale = list(base[far])
            for i in range(bf.FRAME_WORDS):
                if i != fe.ECC_WORD:
                    stale[i] = variant[far][i]
            # no update_ecc() call: word 50 keeps the BASE frame's ECC
            self.assertNotEqual(
                stale, variant[far], f"FAR {far:#x}: base and variant ECC coincide"
            )


if __name__ == "__main__":
    unittest.main()
