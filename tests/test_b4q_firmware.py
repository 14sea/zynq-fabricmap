"""B4Q — the executing-side program: it builds under the strict flags (a failure, never a skip), the generated regmap header
equals a fresh generation, and A7 on its ACTUAL accesses: over an offline session every carrier-window read / write it made is
decoded by the RTL and allowed to the application, the key window is never written, every DMA submission is one of the four
legal transactions, nothing outside the carrier window / the DevC / the three buffers / the IDCODE is touched. The source
audit: the transaction logic reaches the outside world through the HAL's five calls only (no Xil_*, no direct pointer access)."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import b4q_a7 as a7  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402

FW = R / "firmware/b4q"
SMOKE = R / "build/b4q_e2e/valid"


def setUpModule():
    import b4q_fixture
    b4q_fixture.ensure(SMOKE)


class Build(unittest.TestCase):
    def test_build_record_and_generated_headers(self):
        b = json.loads((R / "build/b4q_firmware/build.json").read_text())
        self.assertIn("-Werror", b["flags"]); self.assertIn("-Wconversion", b["flags"])
        for s in ("host/b4q_gen_regmap.py", "host/b4q_gen_data.py"):
            p = subprocess.run([sys.executable, "-B", str(R / s), "--check"], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stdout)

    def test_source_audit_the_hal_is_the_only_way_out(self):
        tx = (FW / "b4q_tx.c").read_text()
        for forbidden in ("Xil_In32", "Xil_Out32", "volatile", "mmap", "fopen"):
            self.assertNotIn(forbidden, tx, forbidden)
        self.assertNotRegex(tx, r"(?<![a-z])printf\(")                        # no console output from the logic (snprintf into a buffer is fine)
        self.assertNotIn("B4Q_KEY0", tx.split("static int axi_writable")[1].split("}")[0] if "B4Q_KEY0" in tx else "")
        for call in ("b4q_rd32(", "b4q_wr32(", "b4q_sign(", "b4q_emit("):
            self.assertIn(call, tx)
        # every carrier-window access goes through axi_rd / axi_wr (the allowlist at the accessor): the base appears in exactly those two calls
        self.assertEqual(tx.count("b4q_rd32(B4Q_AXI_BASE"), 1); self.assertEqual(tx.count("b4q_wr32(B4Q_AXI_BASE"), 1)
        self.assertEqual(tx.count("B4Q_AXI_BASE"), 3)                                 # the define and the two accessors


class A7(unittest.TestCase):
    def test_actual_accesses_against_the_rtl_decode_and_the_table(self):
        acc = [json.loads(l) for l in (SMOKE / "accesses.jsonl").read_text().splitlines() if l.strip()]
        pcap = [json.loads(l) for l in (SMOKE / "pcap_log.jsonl").read_text().splitlines() if l.strip()]
        rep = a7.check(acc, pcap)
        self.assertEqual(rep["findings"], [])
        self.assertGreater(rep["accesses"], 10000)
        self.assertEqual(rep["slverr"], 0)
        self.assertNotIn(f"{rm.KEY[0]:#06x}", rep["carrier_writes"])
        self.assertIn(f"{rm.CTRL:#06x}", rep["carrier_writes"]); self.assertIn(f"{rm.SLOT_IN_READ:#06x}", rep["carrier_reads"])
        self.assertEqual(rep["rtl_writes_untouched"], sorted(f"{o:#06x}" for o in rm.KEY_WINDOW))          # the RTL decodes one more write region: the key window, never touched
        self.assertEqual(set(rep["devc_writes"]), {"INT_STS", "DMA_SRC_ADDR", "DMA_DEST_ADDR", "DMA_SRC_LEN", "DMA_DEST_LEN"})
        self.assertEqual(set(rep["buffer_writes"]), {"CMD_BUF", "DST_BUF", "WR_BUF"})

    def test_dma_tuples_are_classified_from_their_registers(self):
        """R4: both endpoints, both lengths, the HOLD tag and the alignment; the logged kind is never authority"""
        base = {"pcap": "submit", "n": 0, "kind": "env", "src": a7.bk.WR_BUF | 1, "dst": a7.bk.PCAP_ENDPOINT, "src_len": a7.fr.STREAM_WORDS, "dst_len": 0}
        self.assertEqual(a7.check([], [base])["findings"], [])
        self.assertEqual(a7.check([], [{**base, "src": a7.bk.WR_BUF + 4 * a7.fr.STREAM_WORDS + 1}])["findings"], [])        # the second envelope's slot
        for name, change in (("alien source", {"src": 0xDEAD0001}), ("no HOLD tag", {"src": a7.bk.WR_BUF}), ("unaligned", {"src": a7.bk.WR_BUF | 3}),
                             ("a third envelope slot", {"src": a7.bk.WR_BUF + 2 * 4 * a7.fr.STREAM_WORDS + 1}), ("wrong length", {"src_len": 533}),
                             ("a destination length on a write", {"dst_len": 4}), ("mislabelled command", {"src": a7.bk.CMD_BUF | 1, "src_len": a7.fr.READBACK_CMD_WORDS})):
            self.assertTrue(a7.check([], [{**base, **change}])["findings"], name)
        frame = {"pcap": "submit", "n": 1, "kind": "frame", "src": a7.bk.PCAP_ENDPOINT, "dst": a7.bk.DST_BUF | 1, "src_len": 0, "dst_len": a7.fr.READBACK_WORDS}
        self.assertEqual(a7.check([], [frame])["findings"], [])
        for name, change in (("no HOLD tag on the read", {"dst": a7.bk.DST_BUF}), ("another destination", {"dst": a7.bk.CMD_BUF | 1}), ("short read", {"dst_len": 101}), ("a source length on a read", {"src_len": 1})):
            self.assertTrue(a7.check([], [{**frame, **change}])["findings"], name)
        pcap = [json.loads(l) for l in (SMOKE / "pcap_log.jsonl").read_text().splitlines() if l.strip()]
        self.assertEqual(a7.check([], pcap)["findings"], [])                                                                 # the executing side's actual submissions all legal

    def test_a_tampered_access_log_is_found(self):
        acc = [json.loads(l) for l in (SMOKE / "accesses.jsonl").read_text().splitlines() if l.strip()]
        self.assertTrue(a7.check(acc + [{"op": "wr", "addr": a7.bk.AXI_BASE + rm.KEY[0], "resp": 0}])["findings"])
        self.assertTrue(a7.check(acc + [{"op": "rd", "addr": a7.bk.AXI_BASE + 0x2240, "resp": 0}])["findings"])     # the gone sweep window
        self.assertTrue(a7.check(acc + [{"op": "wr", "addr": 0xF8000530, "resp": 0}])["findings"])
        self.assertTrue(a7.check(acc + [{"op": "rd", "addr": 0x20000000, "resp": 0}])["findings"])


if __name__ == "__main__":
    unittest.main()
