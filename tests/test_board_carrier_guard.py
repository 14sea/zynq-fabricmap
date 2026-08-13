"""The board-side guard: a fixed range that nothing at run time can widen.

Round 1's control plane is U-Boot only, so the executor driving the session is the last
thing before the wire and that is where this guard lives. It is the third independent check
of the same bytes — the host gate parses the whole sequence, the fabric checks the control
trace word by word — and the value of a third check is entirely in its refusals.

The positive case is built with the real `icap_sequence` builder from the published
manifest, so "permitted" means a sequence this pipeline actually produces, not a fixture
shaped to pass.
"""

from __future__ import annotations

import copy
import json
import struct
import subprocess
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import board_carrier_guard as guard  # noqa: E402
import icap_sequence as iseq  # noqa: E402

RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_13_erratum005"


def manifest() -> dict:
    return json.loads((RUN / "phenotype_manifest.json").read_text(encoding="utf-8"))


def real_sequence(test: unittest.TestCase) -> bytes:
    """The bytes this pipeline actually sends, for the base (a no-op candidate)."""
    path = RUN / "carrier.bit"
    if not path.is_file():
        test.skipTest("the published carrier run is not in this tree")
    with path.open("rb") as fh:
        if fh.read(40).startswith(b"version https://git-lfs.github.com/spec/"):
            test.skipTest("carrier.bit is an unpulled Git LFS pointer: run `git lfs pull`")
    doc = manifest()
    frames = bf.parse_frames(path)["frames"]
    targets = {}
    for entry in doc["write_envelope"]["envelopes"]:
        for far_hex in entry["target_fars"]:
            far = int(far_hex, 16)
            targets[far] = list(frames[far])
    envelopes = iseq.build_sequence(doc, targets)
    return b"".join(struct.pack(f">{len(e)}I", *e) for e in envelopes)


class ManifestAgreementTests(unittest.TestCase):
    def test_the_published_manifest_agrees_with_the_fixed_bounds(self) -> None:
        self.assertEqual(guard.check_against_manifest(manifest()), [])

    def test_a_manifest_offering_an_extra_far_is_refused(self) -> None:
        """The manifest is not allowed to supply the bounds — that would make it the very
        override this guard exists to refuse. Two statements that must agree."""
        doc = copy.deepcopy(manifest())
        doc["write_envelope"]["envelopes"][0]["target_fars"][0] = "0x00400A24"
        self.assertTrue(guard.check_against_manifest(doc))

    def test_a_manifest_moving_a_flush_far_is_refused(self) -> None:
        doc = copy.deepcopy(manifest())
        doc["write_envelope"]["envelopes"][0]["flush_far"] = "0x00400A24"
        self.assertTrue(guard.check_against_manifest(doc))

    def test_a_manifest_enlarging_the_envelope_is_refused(self) -> None:
        doc = copy.deepcopy(manifest())
        doc["write_envelope"]["total_bytes"] = guard.TOTAL_BYTES + 4
        self.assertTrue(guard.check_against_manifest(doc))


class SequenceGuardTests(unittest.TestCase):
    def words_of(self, payload: bytes) -> list[int]:
        return list(struct.unpack(f">{len(payload) // 4}I", payload))

    def bytes_of(self, words: list[int]) -> bytes:
        return struct.pack(f">{len(words)}I", *words)

    def test_the_real_sequence_is_permitted(self) -> None:
        guard.guard_sequence(real_sequence(self))

    def test_a_far_outside_the_fixed_set_is_refused(self) -> None:
        words = self.words_of(real_sequence(self))
        far_at = words.index(0x30002001) + 1
        words[far_at] = 0x00400A24          # the frame that does not exist
        with self.assertRaises(guard.GuardRefusal) as caught:
            guard.guard_sequence(self.bytes_of(words))
        self.assertIn("outside the fixed set", str(caught.exception))

    def test_a_permitted_far_in_the_wrong_envelope_is_refused(self) -> None:
        """Membership is not enough: each envelope has ONE fixed FAR."""
        words = self.words_of(real_sequence(self))
        far_at = words.index(0x30002001) + 1
        words[far_at] = guard.ENVELOPE_FAR[1]
        with self.assertRaises(guard.GuardRefusal) as caught:
            guard.guard_sequence(self.bytes_of(words))
        self.assertIn("not its fixed", str(caught.exception))

    def test_an_over_long_fdri_is_refused(self) -> None:
        words = self.words_of(real_sequence(self))
        at = words.index(0x30004000) + 1
        words[at] = (2 << 29) | (guard.MAX_FDRI_WORDS + 1)
        with self.assertRaises(guard.GuardRefusal) as caught:
            guard.guard_sequence(self.bytes_of(words))
        self.assertIn("over the fixed maximum", str(caught.exception))

    def test_a_short_fdri_is_refused(self) -> None:
        """Every candidate rewrites all five frames; a shorter burst leaves some frame
        holding whatever the last candidate left there."""
        words = self.words_of(real_sequence(self))
        at = words.index(0x30004000) + 1
        words[at] = (2 << 29) | (guard.MAX_FDRI_WORDS - 1)
        with self.assertRaises(guard.GuardRefusal):
            guard.guard_sequence(self.bytes_of(words))

    def test_a_second_far_write_in_one_envelope_is_refused(self) -> None:
        words = self.words_of(real_sequence(self))
        words[9] = 0x30002001
        with self.assertRaises(guard.GuardRefusal) as caught:
            guard.guard_sequence(self.bytes_of(words))
        self.assertIn("FAR writes", str(caught.exception))

    def test_a_write_to_another_register_is_refused(self) -> None:
        """MASK, or anything else the fixed guard has no business permitting."""
        words = self.words_of(real_sequence(self))
        words[9] = 0x3000C001               # register 0x06 (MASK), one word
        with self.assertRaises(guard.GuardRefusal) as caught:
            guard.guard_sequence(self.bytes_of(words))
        self.assertIn("does not permit", str(caught.exception))

    def test_a_truncated_sequence_is_refused(self) -> None:
        with self.assertRaises(guard.GuardRefusal):
            guard.guard_sequence(real_sequence(self)[:-4])

    def test_the_guard_takes_bytes_not_a_path(self) -> None:
        """§3b's chain breaks if anything re-reads the file between the gate and the wire:
        a different artifact with the same name satisfies none of what the gate established."""
        import inspect
        signature = inspect.signature(guard.guard_sequence)
        annotation = signature.parameters["payload"].annotation
        self.assertIn("bytes", str(annotation))


class PcapPrTests(unittest.TestCase):
    """§6 item 7: restored on the failure path too, with health reported."""

    class Device:
        def __init__(self, value=0xFFFFFFFF):
            self.value = value
            self.writes: list[int] = []

        def peek(self, _address):
            return self.value

        def poke(self, _address, value):
            self.value = value
            self.writes.append(value)

    def test_it_hands_icap_to_the_pl_and_gives_it_back(self) -> None:
        device = self.Device()
        said: list[str] = []
        before = device.value
        with guard.PcapPr(device.poke, device.peek, said.append):
            self.assertEqual(device.value & guard.PCAP_PR_BIT, 0)
        self.assertEqual(device.value, before)
        self.assertTrue(any("restored" in line for line in said), said)

    def test_it_restores_on_the_failure_path(self) -> None:
        device = self.Device()
        said: list[str] = []
        before = device.value
        with self.assertRaises(RuntimeError):
            with guard.PcapPr(device.poke, device.peek, said.append):
                raise RuntimeError("the write failed")
        self.assertEqual(device.value, before)
        self.assertTrue(any("after a failure" in line for line in said), said)

    def test_a_failing_restore_is_reported_and_does_not_mask_the_original(self) -> None:
        device = self.Device()
        said: list[str] = []

        def poke_that_fails_on_restore(address, value):
            if device.writes:
                raise OSError("the transport died")
            device.poke(address, value)

        with self.assertRaises(RuntimeError):
            with guard.PcapPr(poke_that_fails_on_restore, device.peek, said.append):
                raise RuntimeError("the write failed")
        self.assertTrue(any("RESTORE FAILED" in line for line in said), said)


class NoOverrideTests(unittest.TestCase):
    def test_the_cli_exposes_nothing_that_widens_a_bound(self) -> None:
        result = subprocess.run(
            [sys.executable, str(REPO_ROOT / "scripts/board_carrier_guard.py"), "--help"],
            capture_output=True, text=True, check=True)
        for forbidden in ("--far", "--max-fdri", "--allow", "--force", "--permit"):
            self.assertNotIn(forbidden, result.stdout, forbidden)

    def test_no_environment_variable_reaches_a_bound(self) -> None:
        """`icaphw.c` took ICAPHW_FAR_LO/HI/MAX_FDRI from the environment. That pattern is
        deliberately absent, and this asserts it rather than trusting the reading."""
        source = (REPO_ROOT / "scripts/board_carrier_guard.py").read_text()
        self.assertNotIn("os.environ", source)
        self.assertNotIn("getenv", source)


if __name__ == "__main__":
    unittest.main()
