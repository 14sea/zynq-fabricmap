"""B4Q PS image — the console framing unit (firmware/b4q/target/b4q_wire.c) held to its Python twin (host/b4q_wire.py): the
framed line and its CRC on fixed and random payloads, the parse refusals by code, the identity page's parse and refusals, and
the three instrument functions (crc32, base64url, its decoder) byte-identical to firmware/b1/p3_derive.c's. The C unit is
driven through the wire twin driver (target/b4q_wire_twin.c), built here; nothing touches a board."""
from __future__ import annotations

import hashlib
import os
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_wire as w  # noqa: E402

TWIN = R / "build/b4q_firmware/b4q_wire_twin"
_P: dict = {}


def setUpModule():
    p = subprocess.run(["make", "-C", str(R / "firmware/b4q"), f"BUILD={R / 'build/b4q_firmware'}", "wiretwin"], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-2000:] + p.stderr[-2000:])
    _P["tw"] = subprocess.Popen([str(TWIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)


def tearDownModule():
    tw = _P.get("tw")
    if tw:
        tw.stdin.close(); tw.wait(timeout=10)


def ask(cmd: str) -> str:
    tw = _P["tw"]
    tw.stdin.write(cmd + "\n"); tw.stdin.flush()
    return tw.stdout.readline().rstrip("\n")


def c_function(src: str, name: str) -> str:
    i = src.index(name)
    j = src.index("\n}\n", i)
    return src[i:j + 3]


TOK = "0123456789abcdef0123456789abcdef"


class Verbatim(unittest.TestCase):
    def test_the_instrument_functions_are_byte_identical(self):
        b1 = (R / "firmware/b1/p3_derive.c").read_text()
        wire = (R / "firmware/b4q/target/b4q_wire.c").read_text()
        for name in ("uint32_t p3_crc32(", "size_t p3_base64url(", "size_t p3_base64url_decode(", "static int b64val("):
            self.assertEqual(hashlib.sha256(c_function(b1, name).encode()).hexdigest(), hashlib.sha256(c_function(wire, name).encode()).hexdigest(), name)
        self.assertIn("#define p3_crc32 b4q_crc32", wire)          # renamed at the symbol only

    def test_crc_vector(self):
        self.assertEqual(ask("CRC " + b"123456789".hex()), "cbf43926")
        self.assertEqual(f"{w.crc32(b'123456789'):08x}", "cbf43926")


class Framing(unittest.TestCase):
    def test_fixed_and_random_payloads_frame_and_parse_as_the_twin(self):
        rng = random.Random(20261028)
        payloads = [b"", b"hello", b'{"a": 1, "b": "x y"}', b"TX normal 00000018 7 1010101 ...", bytes(range(1, 256))]
        for _ in range(150):
            n = rng.choice([1, 2, 3, 4, 31, 32, 33, 100, 1000, 3000, 4500])
            payloads.append(bytes(rng.choice(range(1, 256)) for _ in range(n)))
        for i, plain in enumerate(payloads):
            kind = rng.choice(["RESULT", "TX", "EV", "SIGNREQ", "HB"]) if i > 4 else "RESULT"
            seq = rng.randrange(0, 1 << 31)
            c = ask(f"FRAME {kind} {seq} {TOK} {plain.hex() or '-'}")
            py = w.frame(kind, seq, TOK, plain)
            self.assertEqual(c + "\n", py, (kind, seq, len(plain)))
            r = ask(f"PARSE {TOK} {py.rstrip()}")
            self.assertTrue(r.startswith(f"OK {kind} {seq} {TOK} "), r[:80])
            self.assertEqual(bytes.fromhex(r[len(f"OK {kind} {seq} {TOK} "):]), plain)
            pr = w.parse(py, TOK)
            self.assertEqual((pr["type"], pr["seq"], pr["token"], pr["payload"]), (kind, seq, TOK, plain))

    def test_overflow_is_refused_not_truncated(self):
        self.assertEqual(ask(f"FRAME RESULT 1 {TOK} " + "ab" * 12000), "OVERFLOW")       # 12 000 bytes: beyond the unit's base64 buffer
        self.assertTrue(ask(f"FRAME RESULT 1 {TOK} " + "ab" * 7000).startswith("B4Q1 RESULT 1 "))

    def test_parse_refusals_by_code(self):
        good = w.frame("TX", 5, TOK, b"x").rstrip()
        self.assertEqual(ask(f"PARSE {TOK} {good[:-1] + ('0' if good[-1] != '0' else '1')}"), "BAD -1")        # bad crc
        with self.assertRaises(w.WireError) as cm:
            w.parse(good[:-1] + ("0" if good[-1] != "0" else "1"), TOK)
        self.assertEqual(str(cm.exception), "bad crc")
        self.assertEqual(ask(f"PARSE {'f' * 32} {good}"), "BAD -3")                                            # wrong token
        self.assertEqual(ask(f"PARSE - {good}"), f"OK TX 5 {TOK} 78")                                           # no token check asked
        def reframe(head: str) -> str:
            return f"{head} {w.crc32(head.encode()):08x}"
        for head, why in ((f"P3L5 TX 5 {TOK} eA==", "wrong magic"), (f"B4Q1 TX 5 {TOK}", "four fields"), (f"B4Q1 TX x5 {TOK} eA==", "seq not digits"),
                          (f"B4Q1 TX 12345678901 {TOK} eA==", "seq too long"), (f"B4Q1 TX 4294967296 {TOK} eA==", "seq out of range"), (f"B4Q1 TX 5 {TOK[:-1]} eA==", "token length"), (f"B4Q1 {'T' * 16} 5 {TOK} eA==", "type too long")):
            self.assertEqual(ask(f"PARSE - {reframe(head)}"), "BAD -2", why)
            with self.assertRaises(w.WireError, msg=why):
                w.parse(reframe(head))
        for head, why in ((f"B4Q1 TX 5 {TOK} eA=", "b64 length"), (f"B4Q1 TX 5 {TOK} e===", "padding"), (f"B4Q1 TX 5 {TOK} e*==", "alphabet"), (f"B4Q1 TX 5 {TOK} AAA=", "NUL inside")):
            self.assertEqual(ask(f"PARSE - {reframe(head)}"), "BAD payload", why)
            with self.assertRaises(w.WireError, msg=why):
                w.parse(reframe(head))

    def test_a_line_without_the_newline_and_with_crlf_parse_alike(self):
        good = w.frame("QUIT", 9, TOK)
        self.assertEqual(ask(f"PARSE {TOK} {good.rstrip()}"), f"OK QUIT 9 {TOK} ")
        self.assertEqual(w.parse(good.rstrip() + "\r\n", TOK)["type"], "QUIT")


class Page(unittest.TestCase):
    def test_page_round_trip_and_refusals(self):
        words = w.page_words(TOK, 1700000000, "ab" * 32, "cd" * 32, 0x1122334455667788, 0x901, 2)
        self.assertEqual(len(words), 24)
        r = ask("PAGE " + " ".join(f"{v:08x}" for v in words))
        self.assertEqual(r, f"OK {TOK} 1700000000 {int('abababab', 16)} {'cd' * 32} 1122334455667788 2305 2")
        self.assertEqual(w.parse_page(words)["token"], TOK)
        for i, v, why in ((0, 0, "magic"), (1, 2, "layout"), (23, words[23] ^ 1, "checksum"), (20, 1, "reserved"), (22, 5, "reserved")):
            bad = list(words); bad[i] = v
            if why != "checksum" and i != 23:                       # a changed word with the checksum recomputed: still refused for its own reason
                bad2 = list(bad); x = 0
                for q in bad2[:-1]:
                    x ^= q
                bad2[23] = x
                self.assertEqual(ask("PAGE " + " ".join(f"{q:08x}" for q in bad2)), "REFUSED", why)
                self.assertIsNone(w.parse_page(bad2), why)
            self.assertEqual(ask("PAGE " + " ".join(f"{q:08x}" for q in bad)), "REFUSED", why)
            self.assertIsNone(w.parse_page(bad), why)


class Constants(unittest.TestCase):
    def test_the_c_and_python_constants_agree(self):
        h = (R / "firmware/b4q/target/b4q_wire.h").read_text()
        self.assertEqual(int(re.search(r"#define B4Q_PAGE_MAGIC (0x[0-9a-fA-F]+)u", h).group(1), 16), w.PAGE_MAGIC)
        self.assertEqual(int(re.search(r"#define B4Q_PAGE_LAYOUT (\d+)u", h).group(1)), w.PAGE_LAYOUT)
        self.assertEqual(int(re.search(r"#define B4Q_PAGE_FLAG_WATCHDOG (0x[0-9a-fA-F]+)u", h).group(1), 16), w.PAGE_FLAG_WATCHDOG)
        self.assertEqual(re.search(r'#define B4Q_WIRE_MAGIC "(\w+)"', h).group(1), w.MAGIC)
        self.assertEqual(int(re.search(r"#define B4Q_PSMAP_PAGE_ADDR (0x[0-9a-fA-F]+)u", (R / "firmware/b4q/target/b4q_psmap.h").read_text()).group(1), 16), w.PAGE_ADDR)


if __name__ == "__main__":
    unittest.main()
