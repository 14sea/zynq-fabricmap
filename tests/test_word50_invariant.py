"""Word-50 invariant: no writable content bit sits in a frame's word 50.

Word 50 of a 7-series frame holds the frame ECC (bits 0..12) and, in bits 13..31,
HCLK/clock-row configuration shared with neighbouring tiles. Fleming & Thomas
(parflip, filterWord50.py) found most configuration-fault "danger" bits there. In this
repo the exclusion is structural (CLB/INT tile offsets skip word 50) and enforced late
by the candidate gate; this file pins it directly on the frozen artifacts, so a future
map, whitelist or firmware table that lets a word-50 bit in fails here first.

Hermetic: reads tracked files only, no board, no build products.
"""
import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LOCAL_MAP = REPO_ROOT / "maps" / "clb_lut_init_v1.local_map.json"
B4Q_DATA = REPO_ROOT / "firmware" / "b4q" / "b4q_data.json"
P3_DATA = REPO_ROOT / "firmware" / "b2" / "p3_data.h"

ECC_WORD = 50
WORDS_PER_FRAME = 101


def word50_hits(words):
    """Indices of entries whose word is 50 (the invariant's whole rule)."""
    return [i for i, w in enumerate(words) if w == ECC_WORD]


def p3_whitelist_words(text):
    """Word field of every `{ frame, word, bit }` entry inside P3_WHITELIST[...] = { ... };"""
    m = re.search(r"P3_WHITELIST\[(\d+)\]\s*=\s*\{(.*?)\};", text, re.S)
    if not m:
        raise ValueError("P3_WHITELIST table not found")
    entries = re.findall(r"\{\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)\s*\}", m.group(2))
    return int(m.group(1)), [int(w) for _, w, _ in entries]


class RuleIsNotVacuous(unittest.TestCase):
    def test_the_checker_flags_a_word_50_entry(self):
        self.assertEqual(word50_hits([51, 52, 50, 49]), [2])
        self.assertEqual(word50_hits([51, 52]), [])

    def test_the_header_parser_reads_a_planted_word_50(self):
        n, words = p3_whitelist_words("static const p3_address P3_WHITELIST[2] = {\n"
                                      "    { 0, 51, 0 },\n    { 1, 50, 7 },\n};")
        self.assertEqual((n, words), (2, [51, 50]))
        self.assertEqual(word50_hits(words), [1])


class FrozenLocalMap(unittest.TestCase):
    def setUp(self):
        self.m = json.loads(LOCAL_MAP.read_text())
        self.u = self.m["universe"]

    def test_universe_has_no_word_50_address(self):
        words = [a["word"] for a in self.u["addresses"]]
        self.assertEqual(len(words), self.u["address_count"])
        self.assertEqual(word50_hits(words), [])
        self.assertNotIn(ECC_WORD, self.u["words"])
        self.assertTrue(all(0 <= w < WORDS_PER_FRAME for w in words))

    def test_ecc_collateral_is_exactly_word_50_bits_0_to_12_and_disjoint(self):
        ecc = self.m["collateral"]["frame_ecc"]
        self.assertEqual((ecc["word"], ecc["bit_low"], ecc["bit_high"]), (ECC_WORD, 0, 12))
        universe = {(a["far"].lower(), a["word"], a["bit"]) for a in self.u["addresses"]}
        self.assertFalse({k for k in universe if k[1] == ECC_WORD})


class B4QWhitelist(unittest.TestCase):
    def test_whitelist_has_no_word_50_bit(self):
        wl = json.loads(B4Q_DATA.read_text())["whitelist"]
        self.assertGreater(len(wl), 0)
        self.assertEqual(word50_hits([e["word"] for e in wl]), [])


class P3FirmwareTable(unittest.TestCase):
    def test_firmware_whitelist_has_no_word_50_bit(self):
        n, words = p3_whitelist_words(P3_DATA.read_text())
        self.assertEqual(len(words), n)
        self.assertEqual(n, json.loads(LOCAL_MAP.read_text())["universe"]["address_count"])
        self.assertEqual(word50_hits(words), [])


if __name__ == "__main__":
    unittest.main()
