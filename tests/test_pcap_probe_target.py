"""The PCAP probe's positive control is machine-checked, not asserted.

`docs/pcap_readback_probe_spec.md` §4 pins five frame hashes, a discriminating-power
argument that rests on one number (the minimum Hamming distance to the neighbours), and a
reverse-lookup contract that turns on how many FARs share a hash.  If any of those drifts
from the frozen bitstream, the spec is quoting something that no longer exists — and the
reverse lookup in particular would go from "returns a candidate set" to "names a FAR",
which is the false claim an earlier draft made.
"""

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import diag_pcap_target_select as T  # noqa: E402

SPEC = REPO_ROOT / "docs/pcap_readback_probe_spec.md"

PINNED = {
    "0x00000b97": ("e4d5335eb8a4b1332e4449384627088a"
                   "25d57d2b4c87f2b41be271d0656b166c", 100),
    "0x00000b98": ("09e6542e15d2236ef806ab934ff70db9"
                   "67cde6d248bda996b753d6542839351c", 101),
    "0x00000b99": ("9029c9d032e0287453cb5c02cd18be42"
                   "bc03acef38b17ef7295ee0d16beb6b1f", 101),
    "0x00000b9a": ("80f782b962888a97d6a663d116d3b615"
                   "8ff4d7408626ce6b83f43ba855356477", 84),
    "0x00000b9b": ("83e824b6b26107265390cb0a51b7f22d"
                   "447bdbe45cf3842853a146eecfa7e760", 83),
}
PINNED_TARGET = "0x00000b99"
PINNED_MIN_HAMMING = 822
PINNED_BASE_SHA = ("8c3369e8e4755da5aceeb7844690d5e1"
                   "32b2e65647004c0a46c0e868e34f0b8a")
PINNED_FRAME_TABLE_SHA = ("5039aab0c39411251fb3d405788fe511"
                          "9236d2159528c85bd3bd280e65d6ad21")
PINNED_FRAME_COUNT = 5144
# The reverse lookup CANNOT name a FAR in general: 4,716 frames are all zero
# (claimb_findings.md 2.3 F1) and four non-blank pairs collide.
PINNED_REVERSE = {
    "frames": 5144,
    "unique_hashes": 425,
    "duplicate_groups": 5,
    "frames_in_duplicate_groups": 4724,
    "blank_group_size": 4716,
}
PINNED_NONBLANK_COLLISIONS = [
    ["0x0040118a", "0x0040118d"],
    ["0x00000d0b", "0x00000d0f"],
    ["0x0040118b", "0x0040118c"],
    ["0x0000139d", "0x0040139d"],
]
# The spec quotes these three words of the target frame by value.
PINNED_WORDS = {0: 0x4756BEA7, 50: 0x000009BB, 100: 0x00800001}


class PinnedPositiveControl(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frames = bf.parse_frames(T.DEFAULT_BIT)["frames"]
        cls.target, cls.min_distance, _ = T.select_target(cls.frames)

    def test_selection_reproduces_the_pinned_target(self):
        self.assertEqual(f"{self.target:#010x}", PINNED_TARGET)

    def test_pinned_hashes_and_nonzero_counts_match_the_bitstream(self):
        for row in T.table(self.frames, self.target):
            sha, nonzero = PINNED[row["far"]]
            self.assertEqual(row["sha256"], sha, row["far"])
            self.assertEqual(row["nonzero_words"], nonzero, row["far"])

    def test_the_discriminating_power_number_is_the_measured_one(self):
        self.assertEqual(self.min_distance, PINNED_MIN_HAMMING)

    def test_the_target_cannot_be_confused_with_blank(self):
        self.assertEqual(T.nonzero_words(self.frames[self.target]), 101)

    def test_every_neighbour_hash_is_distinct_from_the_target(self):
        hashes = [row["sha256"] for row in T.table(self.frames, self.target)]
        self.assertEqual(len(set(hashes)), 5,
                         "a repeated hash would make a misaddress undetectable")

    def test_pinned_base_bitstream_hash(self):
        import hashlib
        self.assertEqual(hashlib.sha256(T.DEFAULT_BIT.read_bytes()).hexdigest(),
                         PINNED_BASE_SHA)

    def test_the_three_named_words_are_what_the_spec_says(self):
        words = self.frames[self.target]
        for index, value in PINNED_WORDS.items():
            self.assertEqual(words[index], value, f"word {index}")

    def test_frame_table_digest(self):
        digest, count = T.frame_table_digest(self.frames)
        self.assertEqual(count, PINNED_FRAME_COUNT)
        self.assertEqual(digest, PINNED_FRAME_TABLE_SHA)

    def test_reverse_lookup_multiplicity_is_what_the_spec_says(self):
        stats = T.reverse_index_stats(self.frames)
        for key, value in PINNED_REVERSE.items():
            self.assertEqual(stats[key], value, key)
        self.assertEqual(sorted(stats["nonblank_duplicate_groups"]),
                         sorted(PINNED_NONBLANK_COLLISIONS))

    def test_a_reverse_lookup_returns_a_set_not_a_far(self):
        index = T.reverse_index(self.frames)
        blank = T.frame_sha256([0] * 101)
        self.assertGreater(len(index[blank]), 1,
                           "collapsing the blank group to one FAR would name a frame "
                           "the bytes cannot identify")
        self.assertTrue(all(isinstance(v, list) for v in index.values()))

    def test_target_and_neighbours_are_globally_unique(self):
        index = T.reverse_index(self.frames)
        for row in T.table(self.frames, self.target):
            self.assertEqual(len(index[row["sha256"]]), 1,
                             f"{row['far']} must be unique across ALL frames, not just "
                             "against its neighbours")

    def test_the_spec_quotes_these_same_constants(self):
        text = SPEC.read_text()
        for far, (sha, _) in PINNED.items():
            self.assertIn(sha, text, f"{far} hash missing from the spec")
        self.assertIn(str(PINNED_MIN_HAMMING), text)
        self.assertIn(PINNED_BASE_SHA, text)
        self.assertIn(PINNED_FRAME_TABLE_SHA, text)
        for value in ("425", "4,716", "4,724"):
            self.assertIn(value, text, f"spec must quote {value}")
        self.assertIn("MISADDRESS_AMBIGUOUS", text)
        lowered = text.lower()
        for value in PINNED_WORDS.values():
            self.assertIn(f"{value:#010x}".lower(), lowered)


class SpecContracts(unittest.TestCase):
    """Two contracts the spec states in prose, checked mechanically.

    Prose can drift; these are the two places where drift would change what a run is
    allowed to do — the order of the verdict table, and whether the session's only
    configuration write happens before the board has been identified.
    """

    @classmethod
    def setUpClass(cls):
        cls.text = SPEC.read_text()

    def _section(self, start: str, end: str) -> str:
        return self.text[self.text.index(start):self.text.index(end)]

    @staticmethod
    def _rows(block: str, header: str) -> list[tuple[str, str]]:
        """(condition, verdict) for each row of the markdown table under `header`."""
        lines = block[block.index(header):].splitlines()
        rows, started = [], False
        for line in lines:
            stripped = line.strip()
            if not stripped.startswith("|"):
                if started:
                    break
                continue
            cells = [c.strip() for c in stripped.strip("|").split("|")]
            if len(cells) < 2 or set(cells[0]) <= set("-: "):
                continue
            if not started:            # the header row itself
                started = True
                continue
            rows.append((cells[0], cells[1]))
        return rows

    def test_sentinel_table_is_judged_on_the_whole_buffer(self):
        block = self._section("## 7. Stop conditions", "## 8. Stages")
        rows = self._rows(block, "| condition on all 202 words |")
        verdicts = [self._verdict(v) for _, v in rows]
        self.assertEqual(verdicts, ["SENTINEL_INTACT", "PARTIAL_WRITE", ""],
                         "the sentinel check must run on all 202 words, and a partial "
                         "survival must be an instrument failure, not a content verdict")

    @staticmethod
    def _verdict(cell: str) -> str:
        import re
        found = re.findall(r"`([A-Z_]+)`", cell)
        return found[0] if found else ""

    def test_frame_verdict_table_maps_each_condition_exactly(self):
        """Exact row-by-row mapping.

        A substring check passes when the unique-hit row is relabelled
        MISADDRESS_AMBIGUOUS or when PASS is moved ahead of the sentinel step —
        both demonstrated — so the mapping and the order are compared literally.
        """
        block = self._section("## 7. Stop conditions", "## 8. Stages")
        rows = self._rows(block, "| condition on `words[101:202]` |")
        expected = [
            ("equals the **pinned target hash**", "PASS"),
            ("all zero", "BLANK"),
            ("reverse lookup hits **exactly one** FAR", "MISADDRESS"),
            ("reverse lookup hits **more than one** FAR", "MISADDRESS_AMBIGUOUS"),
            ("no hit anywhere in the table", "NO_MATCH"),
        ]
        self.assertEqual([(c, self._verdict(v)) for c, v in rows], expected)

    def test_identity_is_verified_before_the_setup_load(self):
        block = self._section("### 5a.", "### 5b.")
        identity = block.index("Verify board identity")
        load = block.index("Load the canonical carrier")
        self.assertLess(identity, load,
                        "the session's only configuration write must not precede "
                        "establishing that this is the right board")
        self.assertIn("board_uboot_fpga_load.py` performs **no identity check", block,
                      "the spec must keep saying that this ordering is a change to "
                      "deliver, not a description of the tools today")

    def test_only_the_sentinel_ordering_is_normative(self):
        block = self._section("### 5b.", "### 5c.")
        self.assertIn("NORMATIVE: the destination sentinel", block)
        self.assertIn("illustrative and S0 owns it", block,
                      "the DMA order is class 2c and may not be pinned here")


if __name__ == "__main__":
    unittest.main()
