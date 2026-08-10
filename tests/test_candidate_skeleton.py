"""The control skeleton is fixed, and an OMISSION is a refusal.

Regression for the consumer's review v1 blocker. The previous gate checked commands by
membership — "DESYNC is present" and "nothing forbidden appears" — which is structurally
unable to notice a command that is *missing* or a value that is *wrong*. Three streams
that are recognised, correctly addressed and carry correct frames were accepted with zero
findings:

* the CMD/WCFG packet removed;
* the CMD/RCRC packet removed;
* the post-FDRI CRC write changed from 0 to a non-zero value.

Every case here is built from the **consumer's** literal `independent_envelope`, not from
`icap_sequence.build_sequence`. That matters: a regression written on the producer's
builder would compare the gate against the very code whose shape is in question, and both
could drift together. The fixture is a transcription of the preregistered envelope, so a
disagreement between it and the gate is a real disagreement.

`expected_trace` in the gate is likewise written out independently rather than obtained by
calling the builder — a gate that asked the builder what to expect would agree with it by
construction, including when the builder is wrong.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))
sys.path.insert(0, str(REPO_ROOT / "tests"))

import gate_candidate as gc  # noqa: E402
import icap_sequence as iseq  # noqa: E402
from test_claimb_consumer_fixtures import (  # noqa: E402
    DESYNC,
    NOOP,
    RCRC,
    TYPE2_WRITE_202,
    WCFG,
    WRITE_CMD_1,
    WRITE_CRC_1,
    WRITE_FAR_1,
    WRITE_IDCODE_1,
    independent_envelope,
    manifest,
)

CLEAN = [0] * 101


def judge(words: list[int]) -> dict:
    return gc.gate_candidate(manifest(), [words])


def without(words: list[int], header: int, value: int) -> list[int]:
    """Delete one two-word write packet, leaving everything else untouched."""
    out = list(words)
    for i in range(len(out) - 1):
        if out[i] == header and out[i + 1] == value:
            del out[i: i + 2]
            return out
    raise AssertionError(f"packet {header:#010x}/{value:#010x} not in the fixture")


class BaselineTests(unittest.TestCase):
    def test_the_untouched_fixture_is_accepted(self):
        """Without this, every case below could pass for the wrong reason."""
        verdict = judge(independent_envelope(CLEAN, CLEAN))
        self.assertTrue(verdict["writable"], verdict["findings"])
        self.assertEqual(verdict["buckets"]["skeleton"], 0)


class OmissionTests(unittest.TestCase):
    """The class the old gate could not express: a packet that is not there."""

    def test_removing_wcfg_is_refused(self):
        verdict = judge(without(independent_envelope(CLEAN, CLEAN), WRITE_CMD_1, WCFG))
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)

    def test_removing_rcrc_is_refused(self):
        verdict = judge(without(independent_envelope(CLEAN, CLEAN), WRITE_CMD_1, RCRC))
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)

    def test_removing_desync_is_refused(self):
        verdict = judge(without(independent_envelope(CLEAN, CLEAN), WRITE_CMD_1, DESYNC))
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)


class ValueTests(unittest.TestCase):
    def test_a_non_zero_crc_write_is_refused(self):
        words = list(independent_envelope(CLEAN, CLEAN))
        at = words.index(WRITE_CRC_1)
        words[at + 1] = 0x12345678
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertEqual(verdict["buckets"]["skeleton"], 1)

    def test_the_crc_value_is_checked_not_merely_its_presence(self):
        """0 passes and 1 does not; a presence check cannot tell them apart."""
        words = list(independent_envelope(CLEAN, CLEAN))
        at = words.index(WRITE_CRC_1)
        self.assertTrue(judge(words)["writable"])
        words[at + 1] = 1
        self.assertFalse(judge(words)["writable"])


class OrderAndExtraTests(unittest.TestCase):
    def test_swapping_rcrc_and_wcfg_is_refused(self):
        """Both commands present, neither forbidden — only order distinguishes them."""
        words = list(independent_envelope(CLEAN, CLEAN))
        a, b = words.index(RCRC), words.index(WCFG)
        words[a], words[b] = words[b], words[a]
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)

    def test_an_extra_write_after_desync_is_refused(self):
        words = list(independent_envelope(CLEAN, CLEAN))
        words.extend([WRITE_CRC_1, 0])
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)

    def test_an_extra_noop_is_refused(self):
        """The skeleton is exact: padding is part of the pinned envelope, not slack."""
        words = list(independent_envelope(CLEAN, CLEAN))
        words.insert(words.index(WRITE_CRC_1), NOOP)
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)

    def test_a_duplicated_command_is_refused(self):
        words = list(independent_envelope(CLEAN, CLEAN))
        at = words.index(WCFG)
        words[at + 1: at + 1] = [WRITE_CMD_1, WCFG]
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["skeleton"], 0)


class TruncationTests(unittest.TestCase):
    """review.v2: a recognised but truncated packet must REFUSE, never throw.

    The parser used to slice a declared payload and index it immediately, so a header
    claiming one word with nothing after it raised IndexError and the gate returned no
    verdict at all. The fix is one rule applied before ANY payload is read — patching the
    four `payload[0]` sites would have fixed four symptoms of one defect, and left type 2
    silently truncating instead.
    """

    def truncated_tail(self, header: int) -> dict:
        words = independent_envelope(CLEAN, CLEAN)
        words.append(header)  # a header whose declared payload is not there
        return judge(words)

    def test_a_truncated_crc_write_refuses(self):
        verdict = self.truncated_tail(WRITE_CRC_1)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_a_truncated_cmd_write_refuses(self):
        verdict = self.truncated_tail(WRITE_CMD_1)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_a_truncated_far_write_refuses(self):
        verdict = self.truncated_tail(WRITE_FAR_1)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_a_truncated_idcode_write_refuses(self):
        verdict = self.truncated_tail(WRITE_IDCODE_1)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_a_type2_overrun_refuses(self):
        """The rule is total, not four special cases: type 2 declares a length too."""
        verdict = self.truncated_tail(TYPE2_WRITE_202)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_a_type2_overrun_inside_the_stream_refuses(self):
        """Not only at the tail: a declared length that overruns anywhere is malformed."""
        words = independent_envelope(CLEAN, CLEAN)
        at = words.index(TYPE2_WRITE_202)
        words[at] = iseq.type2(100_000)
        verdict = judge(words)
        self.assertFalse(verdict["writable"])
        self.assertGreater(verdict["buckets"]["structure"], 0)

    def test_the_parser_reports_truncation_as_data(self):
        """It must be observable in the record, not only in the gate's verdict."""
        words = independent_envelope(CLEAN, CLEAN)
        words.append(WRITE_CRC_1)
        record = iseq.parse_sequence(words)
        self.assertEqual(len(record["truncated"]), 1)
        entry = record["truncated"][0]
        self.assertEqual(entry["declared"], 1)
        self.assertEqual(entry["available"], 0)
        self.assertEqual(record["trace"][-1]["kind"], "truncated")

    def test_no_exception_escapes_for_any_recognised_header(self):
        """The class, not the four instances: every count-one header, one assertion."""
        for header in (WRITE_CRC_1, WRITE_CMD_1, WRITE_FAR_1, WRITE_IDCODE_1):
            with self.subTest(header=hex(header)):
                words = independent_envelope(CLEAN, CLEAN) + [header]
                try:
                    verdict = gc.gate_candidate(manifest(), [words])
                except Exception as exc:  # noqa: BLE001 - the whole point
                    self.fail(f"{header:#010x} raised {type(exc).__name__}: {exc}")
                self.assertFalse(verdict["writable"])


class ExpectedTraceTests(unittest.TestCase):
    """The skeleton the gate expects, checked against the fixture's own parse."""

    def test_the_fixture_parses_to_exactly_the_expected_trace(self):
        record = iseq.parse_sequence(independent_envelope(CLEAN, CLEAN))
        spec = manifest()["write_envelope"]["envelopes"][0]
        idcode = int(manifest()["base_bitstream"]["idcode"], 16)
        self.assertEqual(
            record["trace"],
            gc.expected_trace(
                int(spec["far_set"], 16), idcode, spec["payload_words"]
            ),
        )

    def test_the_gate_does_not_ask_the_builder_what_to_expect(self):
        source = (REPO_ROOT / "scripts/gate_candidate.py").read_text()
        body = source[source.index("def expected_trace"): source.index("def describe")]
        for banned in ("build_envelope", "build_sequence"):
            self.assertNotIn(banned, body)


if __name__ == "__main__":
    unittest.main()
