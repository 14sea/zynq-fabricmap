"""The candidate gate judges the byte stream, and the two frame roles differ.

Every case here builds a real sequence with `icap_sequence.build_sequence`, corrupts it at
the **word level**, and requires the gate to refuse. Nothing is asserted against the
builder's inputs: §6 item 5 makes the serialized stream the thing under judgement, so a
test that handed the gate a description would be testing the wrong object.

The pair that matters most is `test_a_flush_frame_may_not_differ_at_all` against
`test_a_whitelisted_bit_is_accepted_in_a_target_frame`: the *same* single-bit edit is
legal in a target frame and a refusal in a flush frame. A gate with one rule for all 15
frames passes the first and fails the second — which is precisely the bug the two-semantics
ruling exists to prevent, and it cannot be caught by any correct candidate.

The known-bad composition fixture required before device writes is
`KnownBadCompositionTests`: a sequence that is well-formed, correctly addressed, and
carries a valid ECC, yet must still be refused.
"""

from __future__ import annotations

import copy
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import build_phenotype_manifest as bpm  # noqa: E402
import frame_ecc as fe  # noqa: E402
import gate_candidate as gc  # noqa: E402
import icap_sequence as iseq  # noqa: E402

MAP_PATH = REPO_ROOT / "maps/clb_lut_init_v1.local_map.json"
BASE_BIT = REPO_ROOT / "build/specimen_locked/spec_0000000000000000.bit"


class GateFixture(unittest.TestCase):
    """Shared: a real manifest, and the identity candidate built from its own base."""

    @classmethod
    def setUpClass(cls):
        if not BASE_BIT.exists():
            raise unittest.SkipTest(f"{BASE_BIT} absent (build/ is gitignored)")
        cls.manifest = bpm.build_manifest(MAP_PATH, BASE_BIT, "probe", None)
        cls.base_frames, cls.roles = gc.pinned_frames(cls.manifest)
        cls.targets = [f for f, r in cls.roles.items() if r == "target"]
        cls.flushes = [f for f, r in cls.roles.items() if r == "flush"]
        cls.allowed = gc.whitelist_by_far(cls.manifest)

    def identity_candidate(self) -> dict[int, list[int]]:
        return {far: list(self.base_frames[far]) for far in self.targets}

    def build(self, candidate: dict[int, list[int]]) -> list[list[int]]:
        return iseq.build_sequence(self.manifest, candidate)

    def judge(self, envelopes) -> dict:
        return gc.gate_candidate(self.manifest, envelopes)

    def flip_whitelisted(self, frames: dict[int, list[int]], far: int) -> tuple[int, int]:
        word, bit = sorted(self.allowed[far])[0]
        frames[far][word] ^= 1 << bit
        frames[far] = fe.update_ecc(frames[far])
        return word, bit


class HappyPathTests(GateFixture):
    def test_the_identity_candidate_is_writable(self):
        verdict = self.judge(self.build(self.identity_candidate()))
        self.assertTrue(verdict["writable"], verdict["findings"])
        self.assertEqual(verdict["envelopes"], 3)

    def test_a_whitelisted_bit_is_accepted_in_a_target_frame(self):
        frames = self.identity_candidate()
        far = self.targets[0]
        self.flip_whitelisted(frames, far)
        verdict = self.judge(self.build(frames))
        self.assertTrue(verdict["writable"], verdict["findings"])

    def test_every_target_frame_is_transmitted_even_when_unchanged(self):
        """§6 item 1: a candidate depends on the pinned base, not on the previous one."""
        envelopes = self.build(self.identity_candidate())
        total = 0
        for words in envelopes:
            record = iseq.parse_sequence(words)
            total += record["fdri"][0]["words"]
        self.assertEqual(total, 15 * bf.FRAME_WORDS)

    def test_transfer_size_matches_the_pinned_envelope(self):
        envelopes = self.build(self.identity_candidate())
        self.assertEqual(
            sum(len(w) for w in envelopes),
            self.manifest["write_envelope"]["total_words"],
        )


class TargetFrameSemanticsTests(GateFixture):
    def test_a_non_whitelisted_bit_is_refused(self):
        frames = self.identity_candidate()
        far = self.targets[0]
        allowed = self.allowed[far]
        word, bit = next(
            (w, b)
            for w in (51, 52)
            for b in range(32)
            if (w, b) not in allowed
        )
        frames[far][word] ^= 1 << bit
        frames[far] = fe.update_ecc(frames[far])
        verdict = self.judge(self.build(frames))
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["target_frame"], 1)

    def test_a_stale_ecc_is_refused(self):
        frames = self.identity_candidate()
        far = self.targets[0]
        word, bit = sorted(self.allowed[far])[0]
        frames[far][word] ^= 1 << bit  # no update_ecc: the ECC now belongs to the base
        verdict = self.judge(self.build(frames))
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["ecc"], 1)

    def test_a_merely_different_ecc_is_refused(self):
        """Not 'the ECC changed' but 'the ECC is not the correct recomputation'."""
        frames = self.identity_candidate()
        far = self.targets[0]
        self.flip_whitelisted(frames, far)
        frames[far][fe.ECC_WORD] ^= 0x1  # perturb a correct ECC
        verdict = self.judge(self.build(frames))
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["ecc"], 1)

    def test_word_50_outside_the_ecc_field_is_refused(self):
        frames = self.identity_candidate()
        far = self.targets[0]
        frames[far][fe.ECC_WORD] ^= 1 << 20
        frames[far] = fe.update_ecc(frames[far])
        verdict = self.judge(self.build(frames))
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["target_frame"], 1)


class FlushFrameSemanticsTests(GateFixture):
    """The rule that a single 'matches outside the whitelist' check would get wrong."""

    def corrupt_flush(self, envelopes, envelope_index, mutate):
        spec = self.manifest["write_envelope"]["envelopes"][envelope_index]
        words = list(envelopes[envelope_index])
        record = iseq.parse_sequence(words)
        block = record["fdri"][0]
        flush_start = block["start"] + 4 * bf.FRAME_WORDS
        frame = words[flush_start: flush_start + bf.FRAME_WORDS]
        mutate(frame)
        words[flush_start: flush_start + bf.FRAME_WORDS] = frame
        out = list(envelopes)
        out[envelope_index] = words
        return out, spec

    def test_a_flush_frame_may_not_differ_at_all(self):
        """The same edit that is legal in a target frame is a refusal here."""
        envelopes = self.build(self.identity_candidate())
        flush_far = int(self.manifest["write_envelope"]["envelopes"][0]["flush_far"], 16)
        # a bit that IS whitelisted somewhere in the run — still illegal in a flush frame
        word, bit = sorted(self.allowed[self.targets[0]])[0]
        corrupted, _ = self.corrupt_flush(
            envelopes, 0, lambda f: f.__setitem__(word, f[word] ^ (1 << bit))
        )
        verdict = self.judge(corrupted)
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["flush_frame"], 1)
        self.assertNotIn(flush_far, self.targets)

    def test_even_a_correctly_recomputed_ecc_is_refused_in_a_flush_frame(self):
        """The tempting exception: 'the ECC is right, so the frame is fine'."""
        envelopes = self.build(self.identity_candidate())

        def mutate(frame):
            word, bit = 51, 0
            frame[word] ^= 1 << bit
            frame[:] = fe.update_ecc(frame)

        corrupted, _ = self.corrupt_flush(envelopes, 0, mutate)
        verdict = self.judge(corrupted)
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["flush_frame"], 1)
        self.assertEqual(verdict["buckets"]["ecc"], 0)

    def test_the_flush_frame_comes_from_the_manifest_not_the_candidate(self):
        """A candidate cannot supply a flush frame even by naming its FAR."""
        frames = self.identity_candidate()
        flush_far = int(self.manifest["write_envelope"]["envelopes"][0]["flush_far"], 16)
        frames[flush_far] = [0] * bf.FRAME_WORDS
        with self.assertRaises(iseq.SequenceError) as ctx:
            self.build(frames)
        self.assertIn("unexpected", str(ctx.exception))


class SequenceStructureTests(GateFixture):
    def test_a_missing_target_frame_is_refused_before_a_sequence_exists(self):
        frames = self.identity_candidate()
        frames.pop(self.targets[0])
        with self.assertRaises(iseq.SequenceError) as ctx:
            self.build(frames)
        self.assertIn("missing", str(ctx.exception))

    def test_a_second_far_set_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        words = list(envelopes[0])
        insert_at = words.index(iseq.type1(2, iseq.REG_FAR, 1))
        words[insert_at + 2:insert_at + 2] = [iseq.type1(2, iseq.REG_FAR, 1), 0x00400C1A]
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["addressing"], 1)

    def test_a_forbidden_command_is_refused(self):
        for cmd in (0x0000000A, 0x0000000B):
            with self.subTest(cmd=cmd):
                envelopes = self.build(self.identity_candidate())
                words = list(envelopes[0])
                at = words.index(iseq.CMD_DESYNC)
                words[at - 1:at - 1] = [iseq.type1(2, iseq.REG_CMD, 1), cmd]
                verdict = self.judge([words] + envelopes[1:])
                self.assertFalse(verdict["writable"])
                self.assertGreaterEqual(verdict["buckets"]["forbidden"], 1)

    def test_a_wrong_idcode_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        words = list(envelopes[0])
        at = words.index(iseq.type1(2, iseq.REG_IDCODE, 1))
        words[at + 1] = 0x0362D093  # a different 7-series part
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["addressing"], 1)

    def test_a_wrong_far_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        words = list(envelopes[0])
        at = words.index(iseq.type1(2, iseq.REG_FAR, 1))
        words[at + 1] = 0x00400C20
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["addressing"], 1)

    def test_an_unrecognised_packet_is_refused(self):
        """A word that is neither a type-1 nor a type-2 header must be reported.

        The parser records what it does not understand instead of skipping it: an unknown
        packet is the most interesting thing a gate can be told about, and a parser that
        dropped it would hand the gate a clean record of a stream it did not read.
        """
        envelopes = self.build(self.identity_candidate())
        words = list(envelopes[0])
        at = words.index(iseq.CMD_DESYNC)
        words.insert(at - 1, 0xE0000000)  # htype 7: not a header at all
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["structure"], 1)

    def test_a_missing_sync_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        words = [w for w in envelopes[0] if w != iseq.SYNC]
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["structure"], 1)

    def test_an_extra_envelope_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        verdict = self.judge(envelopes + [envelopes[0]])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["structure"], 1)

    def test_a_lengthened_fdri_is_refused(self):
        envelopes = self.build(self.identity_candidate())
        words = list(envelopes[0])
        at = words.index(iseq.type2(5 * bf.FRAME_WORDS))
        words[at] = iseq.type2(6 * bf.FRAME_WORDS)
        words[at + 1:at + 1] = [0] * bf.FRAME_WORDS
        verdict = self.judge([words] + envelopes[1:])
        self.assertFalse(verdict["writable"])
        self.assertGreaterEqual(verdict["buckets"]["addressing"], 1)


class KnownBadCompositionTests(GateFixture):
    """The fixture §7 requires: well-formed, correctly addressed, valid ECC — and refused.

    A gate that has never refused anything has not been shown to work, and the dangerous
    class is not a malformed stream (any parser catches that) but a *plausible* one.
    """

    def test_a_plausible_but_out_of_scope_write_is_refused(self):
        frames = self.identity_candidate()
        far = self.targets[0]
        # Flip an entire word of LUT content and fix the ECC properly. Structurally this
        # is indistinguishable from a legitimate candidate; only the whitelist says no.
        frames[far][51] ^= 0xFFFFFFFF
        frames[far] = fe.update_ecc(frames[far])

        envelopes = self.build(frames)
        record = iseq.parse_sequence(envelopes[0])
        self.assertTrue(record["synced"])
        self.assertEqual(len(record["far_sets"]), 1)
        self.assertEqual(record["unknown"], [])
        block = record["fdri"][0]
        written = iseq.split_frames(block["payload"])[0]
        self.assertTrue(fe.frame_is_consistent(written))  # the ECC really is correct

        verdict = self.judge(envelopes)
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["ecc"], 0)  # not an ECC problem
        self.assertEqual(verdict["buckets"]["forbidden"], 0)
        self.assertEqual(verdict["buckets"]["structure"], 0)
        self.assertEqual(verdict["buckets"]["addressing"], 0)
        self.assertEqual(verdict["buckets"]["target_frame"], 1)


class FindingShapeTests(unittest.TestCase):
    """Findings are bucketed by kind; nothing branches on message text."""

    def test_kind_must_be_known(self):
        with self.assertRaises(ValueError):
            gc.finding("whatever", "x")

    def test_every_kind_is_representable(self):
        for kind in gc.KINDS:
            self.assertEqual(gc.finding(kind, "m")["kind"], kind)


if __name__ == "__main__":
    unittest.main()
