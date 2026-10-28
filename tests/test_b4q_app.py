"""B4Q PS image — the board application's host harness (the image's own sources: target/b4q_app.c, b4q_wire.c, b4q_psmap.c
with b4q_tx.c / b4q_cmd.c / b4q_derive.c) driven through its framed console by host/b4q_console_session.py over the emulated
backend, in the console scenarios of host/b4q_console_e2e.py; every archive fresh-verified by host/b4q_verify.py; the pure
allowlist (b4q_psmap.c) held to the A7 regions and the register table of record; A7 on the program's actual accesses; the
source audits (no key-window symbol, the MMIO confined to the board HAL, one kick site, B1's BSP files byte for byte); the
image built with the pinned toolchain and its layout read from the ELF. Nothing here is on-target evidence: the console is
a pipe, the DMA and the fabric are emulated; the image is compiled, never loaded."""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    sys.path.insert(0, str(p))
import b4q_wire as w  # noqa: E402
import b4q_verify as vf  # noqa: E402
import b4q_a7 as a7  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_frames as fr  # noqa: E402

_S: dict = {}
TC = Path("/home/test/zynq_psoracle/toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1/bin")


def setUpModule():
    for target in ("host", "apphost", "wiretwin", "waittwin"):
        p = subprocess.run(["make", "-C", str(R / "firmware/b4q"), f"BUILD={R / 'build/b4q_firmware'}", target], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(p.stdout[-2000:] + p.stderr[-2000:])
    root = Path(tempfile.mkdtemp(prefix="b4q_console_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_console_e2e.py"), str(root)], capture_output=True, text=True, timeout=1200)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    _S["root"] = root
    _S["summary"] = {s["name"]: s for s in json.loads((root / "e2e_summary.json").read_text())}
    _S["verify"] = {}
    for name in _S["summary"]:
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(root / name), "--json", str(root / name / "verify.json")], capture_output=True, text=True, timeout=600)
        _S["verify"][name] = (q.returncode, json.loads((root / name / "verify.json").read_text()), q.stderr)
    _S["tw"] = subprocess.Popen([str(R / "build/b4q_firmware/b4q_wire_twin")], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)


def tearDownModule():
    tw = _S.get("tw")
    if tw:
        tw.stdin.close(); tw.wait(timeout=10)


def psmap(addr: int) -> tuple[int, int]:
    tw = _S["tw"]
    tw.stdin.write(f"PSMAP {addr:x}\n"); tw.stdin.flush()
    m = re.match(r"r=(\d) w=(\d)", tw.stdout.readline())
    return int(m.group(1)), int(m.group(2))


def console_lines(name: str) -> list:
    return [json.loads(l) for l in (_S["root"] / name / "console.jsonl").read_text().splitlines() if l.strip()]


class ConsoleScenarios(unittest.TestCase):
    def summary(self, name):
        return _S["summary"][name]

    def test_every_console_scenario_verifies_in_agreement_with_the_session(self):
        for name, (rc, rep, err) in _S["verify"].items():
            self.assertNotIn("Traceback", err, name)
            self.assertTrue(rep["agree"], (name, rep["session"], rep.get("session_only_here"), [(t["dir"], t.get("only_here"), t.get("only_stored")) for t in rep["transactions"] if not t["agrees"]]))
            self.assertEqual(rc, 0, name)
            self.assertEqual(rep["a7"]["findings"], [], name)        # the program's actual accesses, the identity page's reads included

    def test_valid_paths_clean_and_every_console_line_is_the_twins(self):
        for name in ("valid", "a5", "reply_corrupt", "reply_dropped_once", "garbage_command", "silent_host", "wrong_token", "stale_reply", "host_seq_gap", "malformed_tx", "duplicate_tx"):
            rep = _S["verify"][name][1]
            self.assertTrue(rep["clean"], (name, rep["session"], [t["findings"] for t in rep["transactions"]]))
            m = json.loads((_S["root"] / name / "manifest.json").read_text())
            tok = m["transport"]["token"]
            board_seq, host_seq = -1, 0
            for e in console_lines(name):
                if e.get("line") is None or e.get("note"):          # a bench-corrupted / malformed line (noted) is not the twin's
                    continue
                f = w.parse(e["line"] + "\n", tok)
                if e["dir"] == "board":
                    self.assertIn(f["type"], w.BOARD_TYPES, name); self.assertGreater(f["seq"], board_seq); board_seq = f["seq"]
                else:
                    self.assertIn(f["type"], w.HOST_TYPES, name); self.assertGreater(f["seq"], host_seq); host_seq = f["seq"]
            end = self.summary(name)["end"]
            self.assertEqual(end["kicks"], end["lines"], name)         # the watchdog is kicked once per emitted line and nowhere else
            self.assertEqual(self.summary(name)["platform_kicks"], end["lines"] + 1, name)   # the platform's own count: every line incl. the END itself (its payload is fixed before it goes out)
            self.assertEqual(end["hb"], self.summary(name)["stats"]["hb"], name)
            self.assertEqual(m["transport"]["kind"], "console-emulated")
        self.assertEqual(self.summary("a5")["a5"], "pass")
        ident = self.summary("valid")["ident"]
        self.assertEqual((ident["protocol"], ident["watchdog"], ident["nonce_echo_equal"]), ("b4q-v1", "armed", True))
        self.assertEqual(ident["open"]["status"], 0)

    def test_the_console_notary_is_bounded_and_fail_closed(self):
        s = self.summary("notary_refuses")
        self.assertEqual((s["tx"]["status"], s["tx"]["phase"], s["tx"]["o"]), (1, "P1", False)); self.assertIn("STOP_SIGN", s["tx"]["reason"])
        self.assertTrue(any("refused" in e for e in s["sign_events"]), s["sign_events"]); self.assertIsNotNone(s["next_refused"])
        s = self.summary("replies_dropped")
        self.assertEqual((s["tx"]["status"], s["tx"]["o"]), (1, False)); self.assertEqual(s["stats"]["dropped"], 3)
        self.assertTrue(any("no valid SIGNREPLY after 3 attempts" in e for e in s["sign_events"]), s["sign_events"]); self.assertIsNotNone(s["halted"])
        self.assertEqual(s["end"]["sign_requests"], 1 + 3)            # the root's one, the candidate's three attempts
        s = self.summary("reply_corrupt")
        self.assertEqual((s["tx"]["status"], s["tx"]["x"]), (0, "closed")); self.assertEqual((s["stats"]["corrupted"], s["end"]["nacks"]), (1, 1))
        self.assertEqual(s["end"]["sign_requests"], 1 + 2)            # the corrupted reply refused (NACK bad crc), the request re-sent once
        self.assertEqual(s["tx"]["status"], 0)
        self.assertTrue(any(e.get("type") == "NACK" for e in console_lines("reply_corrupt")))
        s = self.summary("reply_dropped_once")
        self.assertEqual((s["tx"]["status"], s["stats"]["dropped"], s["end"]["sign_requests"]), (0, 1, 1 + 2))

    def test_a_silent_host_and_a_malformed_line(self):
        s = self.summary("wrong_token")
        self.assertEqual((s["tx"]["status"], s["end"]["nacks"], s["stats"]["wrong_token"]), (0, 1, 1)); self.assertIn("NACK wrong token", s["nacks"])
        s = self.summary("stale_reply")
        self.assertEqual((s["tx"]["status"], s["tx"]["x"], s["stats"]["stale"]), (0, "closed", 1))     # the stale reply (garbage words) ignored, the right one used
        s = self.summary("silent_host")
        self.assertEqual((s["served"], s["end"]["kind"]), (6, "STOPPED")); self.assertIn("idle bound", s["end"]["reason"]); self.assertGreater(s["end"]["hb"], 0)
        s = self.summary("garbage_command")
        self.assertEqual((s["tx"]["status"], s["end"]["nacks"], s["stats"]["garbage"]), (0, 1, 1))

    def test_a_bad_page_and_an_unarmed_watchdog_sign_nothing(self):
        for name, needle in (("bad_page", "identity page does not parse"), ("watchdog_fail", "watchdog could not be armed")):
            s = self.summary(name)
            self.assertEqual((s["open_status"], s["signatures"], s["ident"], s["end"]["kind"]), ("refused", 0, None, "STOPPED"), name)
            self.assertIn(needle, s["end"]["reason"], name); self.assertIsNotNone(s["root_refused"], name)
            self.assertFalse(any(e.get("type") == "IDENT" for e in console_lines(name)), name)
            rep = _S["verify"][name][1]
            self.assertTrue(any("refused to open" in x for x in rep["session"]), rep["session"])

    def test_r1_the_receive_budget_is_one_per_wait_and_never_replenished(self):
        """the owner's R1 (2026-10-28): the application's own b4q_sign / command wait under injected console fixtures (the budget twin,
        built with REPLY_POLLS 10 000 / IDLE_POLLS 20 000 / HB 2 000): a silent peer, a flood of stale replies, an endless overlong line and
        a flood of malformed lines each end within the budget — every poll charged, nothing replenished; the fixture caps at 50x so that a
        missing bound is an OVER_BUDGET exit, never a hang"""
        tw = R / "build/b4q_firmware/b4q_wait_twin"
        out = {}
        for mode in range(7):
            p = subprocess.run([str(tw), str(mode)], capture_output=True, text=True, timeout=120)
            self.assertEqual(p.returncode, 0, (mode, p.stdout, p.stderr))
            out[mode] = dict(kv.split("=") for kv in p.stdout.split())
        self.assertEqual((out[0]["ret"], out[0]["polls"], out[0]["requests"]), ("-1", "30000", "3"))          # three attempts x 10 000, exactly
        self.assertEqual((out[1]["ret"], out[1]["polls"], out[1]["requests"]), ("-1", "30000", "3"))          # a flood of stale replies charged, not replenished
        self.assertGreater(int(out[1]["frames"]), 100)
        self.assertEqual((out[2]["ret"], out[2]["polls"], out[2]["requests"]), ("-1", "30000", "3"))          # an endless overlong line charged byte by byte
        self.assertEqual(out[3]["ret"], "-1"); self.assertLessEqual(int(out[3]["polls"]), 30000)              # malformed flood: the per-wait NACK cap ends it earlier
        self.assertEqual(out[4]["ret"], "-1"); self.assertLessEqual(int(out[4]["polls"]), 20000)              # non-command flood on the command wait: one budget, the NACK cap
        self.assertEqual((out[5]["ret"], out[5]["polls"], out[5]["spent"]), ("0", "20000", "20000"))         # a silent host: the idle budget, exactly
        self.assertEqual((out[6]["ret"], out[6]["polls"], out[6]["requests"]), ("-1", "30000", "3"))          # a flood of fresh frames of another type: charged, never a reply
        self.assertGreater(int(out[5]["hb"]), 0)

    def test_r2_freshness_in_both_directions(self):
        """the owner's R2: a replayed TX (the same host sequence) is NACKed 'stale sequence' — nothing signed, nothing run, the session
        halted on the named non-success and no record made; a gap is legitimate; the host refuses duplicate / decreasing board frames"""
        s = self.summary("duplicate_tx")
        self.assertEqual((s["first"]["status"], s["second"]["status"], s["new_signreqs"], s["new_trace_events"]), (0, 7, 0, 0))
        self.assertIn("stale sequence", s["second"]["reason"]); self.assertIn("stale sequence", s["halted"] or "")
        self.assertEqual(s["end"]["stale_frames"], 1); self.assertEqual(len(s["records"]), 2)     # the root and the first candidate; the replay made no record
        s = self.summary("host_seq_gap")
        self.assertEqual((s["tx"]["status"], s["tx"]["x"]), (0, "closed")); self.assertGreater(s["host_seq_last"], 10)
        import b4q_console_session as cs
        sess = cs.ConsoleSession(_S["root"] / "unit_board_seq", label="unit")
        sess._fds = {"c2h_r": -1}
        sess._con_buf = (w.frame("HB", 7, sess.token) + w.frame("HB", 7, sess.token) + w.frame("HB", 6, sess.token) + w.frame("HB", 9, sess.token)).encode()
        for _ in range(4):
            sess._console_line()
        self.assertEqual((sess.stats["hb"], sess.stats["stale_board"]), (2, 2))                   # 7 accepted; 7 and 6 refused (the session halted on the first); 9 is fresh and still counted
        self.assertIsNotNone(sess.halted); self.assertTrue(any("not fresh" in m for m in sess.findings))

    def test_r3_nothing_is_signed_after_a_transaction_that_did_not_close(self):
        """the owner's R3: after a failed transaction, a valid TX injected at the console boundary (bypassing the API's latch) is NACKed
        'halted' by the application — no signature, no trace; the host's notary refuses an unsolicited SIGNREQ while halted"""
        s = self.summary("after_stop_tx")
        self.assertEqual((s["failed"]["status"], s["api_refused"], s["raw_next"]["status"], s["new_signreqs"], s["new_trace_events"]), (1, True, 7, 0, 0))
        self.assertIn("halted", s["raw_next"]["reason"]); self.assertEqual(s["end"]["refused_tx"], 1); self.assertIn("STOP_SIGN", s["end"]["halted"])
        import b4q_console_session as cs
        sess = cs.ConsoleSession(_S["root"] / "unit_halted_sign", label="unit")
        sess._fds = {"h2c_w": -1}
        written = []
        sess._console_write = lambda line, note="": written.append(line)
        sess.halt("a test halt")
        n = len(sess.notary.log)
        sess._answer_sign({"payload": json.dumps({"genome": "00000000", "nonce": "0" * 16, "req": 5}).encode(), "seq": 5})
        self.assertEqual(len(written), 1); self.assertIn("REFUSED 5", w.parse(written[0], sess.token)["payload"].decode())
        self.assertEqual(len(sess.notary.log), n + 1); self.assertIn("refused", sess.notary.log[-1]); self.assertEqual(sess.stats["refused_halted"], 1)

    def test_r4_the_console_evidence_is_verified_offline(self):
        """the owner's R4: the console source's retained lines are evidence — dropped, corrupted or edited material is never clean"""
        import shutil
        src = _S["root"] / "valid"
        def copy(name):
            d = _S["root"] / f"valid_console_{name}"; shutil.rmtree(d, ignore_errors=True); shutil.copytree(src, d); return d
        def edit_line(d, pred, change):
            lines = [json.loads(l) for l in (d / "console.jsonl").read_text().splitlines() if l.strip()]
            for e in lines:
                if e.get("line") and pred(e):
                    e["line"] = change(e["line"]); break
            else:
                raise AssertionError("no line matched")
            (d / "console.jsonl").write_text("".join(json.dumps(e) + "\n" for e in lines))
        def reframe(line, edit_payload):
            f = w.parse(line + "\n"); return w.frame(f["type"], f["seq"], f["token"], edit_payload(f["payload"].decode())).rstrip("\n")
        d = copy("dropped"); (d / "console.jsonl").unlink()
        rep = vf.verify(d); self.assertIn("console.jsonl: missing", rep["refused"] or "")
        cases = [("ident_crc", lambda e: e["dir"] == "board" and " IDENT " in e["line"], lambda l: l[:-1] + ("0" if l[-1] != "0" else "1"), "bad crc"),
                 ("result_fitness", lambda e: e["dir"] == "board" and " RESULT " in e["line"] and '"has_fitness": 1' in w.parse(e["line"] + "\n")["payload"].decode(),
                  lambda l: reframe(l, lambda p: p.replace('"has_fitness": 1, "fitness": ', '"has_fitness": 1, "fitness": 999, "fitness_was": ')), "not the retained transaction result"),
                 ("ident_token", lambda e: e["dir"] == "board" and " IDENT " in e["line"], lambda l: reframe(l, lambda p: p.replace('"token": "', '"token": "ff')[:len(p)] if False else __import__("re").sub(r'"token": "[0-9a-f]{32}"', '"token": "' + "f" * 32 + '"', p)), "token"),
                 ("end_transactions", lambda e: e["dir"] == "board" and " END " in e["line"], lambda l: reframe(l, lambda p: __import__("re").sub(r'"transactions": \d+', '"transactions": 999', p)), "END.transactions"),
                 ("result_dropped", lambda e: e["dir"] == "board" and " RESULT " in e["line"], lambda l: w.frame("HB", w.parse(l + "\n")["seq"], w.parse(l + "\n")["token"]).rstrip("\n"), "RESULT lines for"),
                 ("signreply_words", lambda e: e["dir"] == "host" and " SIGNREPLY " in e["line"] and not e.get("note"), lambda l: reframe(l, lambda p: p[:-8] + ("00000000" if p[-8:] != "00000000" else "00000001")), "not the notary's"),
                 ("board_seq_dup", lambda e: e["dir"] == "board" and " HB " in e["line"] or (e["dir"] == "board" and " EV " in e["line"] and "MARK transaction_begin" in w.parse(e["line"] + "\n")["payload"].decode()),
                  lambda l: w.frame(w.parse(l + "\n")["type"], 0, w.parse(l + "\n")["token"], w.parse(l + "\n")["payload"]).rstrip("\n"), "not fresh")]
        for name, pred, change, needle in cases:
            d = copy(name); edit_line(d, pred, change)
            rep = vf.verify(d)
            self.assertIsNone(rep["refused"], name); self.assertFalse(rep["clean"], name); self.assertFalse(rep["agree"], name)
            self.assertTrue(any(needle in m for m in rep["session"]), (name, rep["session"]))
        for name, pred, change, edit_tr, needle in (("coord_ident_token", lambda e: e["dir"] == "board" and " IDENT " in e["line"],
                                                      lambda l: reframe(l, lambda p: __import__("re").sub(r'"token": "[0-9a-f]{32}"', '"token": "' + "f" * 32 + '"', p)), lambda tr: tr["ident"].update({"token": "f" * 32}), "IDENT's token is not the page's"),
                                                     ("coord_end_transactions", lambda e: e["dir"] == "board" and " END " in e["line"],
                                                      lambda l: reframe(l, lambda p: __import__("re").sub(r'"transactions": \d+', '"transactions": 999', p)), lambda tr: tr["end"].update({"transactions": 999}), "END.transactions")):
            d = copy(name); edit_line(d, pred, change)
            m = json.loads((d / "manifest.json").read_text()); edit_tr(m["transport"]); (d / "manifest.json").write_text(json.dumps(m))
            rep = vf.verify(d)
            self.assertFalse(rep["clean"], name); self.assertFalse(rep["agree"], name); self.assertTrue(any(needle in x for x in rep["session"]), (name, rep["session"]))
        for name, edit, needle in (("cached_ident", lambda tr: tr["ident"].update({"token": "f" * 32}), "cached IDENT"), ("cached_end", lambda tr: tr["end"].update({"transactions": 999}), "cached END"),
                                   ("page_magic", lambda tr: tr["page_words"].__setitem__(0, "00000000"), "page"), ("stats", lambda tr: tr["stats"].update({"signreq": 99}), "stats.signreq"),
                                   ("lines", lambda tr: tr.update({"console_lines": 1}), "console lines")):
            d = copy("m_" + name)
            m = json.loads((d / "manifest.json").read_text()); edit(m["transport"]); (d / "manifest.json").write_text(json.dumps(m))
            rep = vf.verify(d)
            self.assertFalse(rep["clean"], name); self.assertFalse(rep["agree"], name); self.assertTrue(any(needle in x for x in rep["session"]), (name, rep["session"]))
        for name in ("valid", "a5", "reply_corrupt", "stale_reply", "duplicate_tx", "after_stop_tx", "malformed_tx"):   # the untouched archives: the console contract agrees
            rep = _S["verify"][name][1]
            self.assertTrue(rep["agree"], (name, rep["session"])); self.assertEqual(rep["console"]["findings"], [], name)

    def test_r5_the_command_grammar_is_checked_before_anything_runs(self):
        """the owner's R5: the six reproduced malformed commands and the width / count / index boundaries are refused whole by the
        parser twin; through the console they are NACKed 'malformed TX' with no signature, no trace and no DMA; legitimate commands parse"""
        tw = _S["tw"]
        def tx(cmd):
            tw.stdin.write(cmd + "\n"); tw.stdin.flush(); return tw.stdout.readline().rstrip("\n")
        D = "a" * 64
        for cmd in ("TX mystery 0 0", "TX normal 100000000 0", "TX normal 0 1 100000000", "TX normal 0 0 GARBAGE", f"TX normal 0 0 TASK {D} 2 1 0 0 1", f"TX normal 0 0 TASK {D} 1 257 256 256 65537",
                    "TX normal 00200000 0", "TX normal 0 1 2000000", "TX normal 0 29 " + " ".join(["0"] * 29), "TX root 0 1 0", "TX normal 0 0 TASK " + "a" * 63 + " 0", f"TX normal 0 1 0 TASK {D} 1 2 0 0 1",
                    f"TX normal 0 1 0 TASK {D} 1 1 8 0 1", f"TX normal 0 1 0 TASK {D} 1 1 0 2 1", f"TX normal 0 1 0 TASK {D} 1 1 0 0 65536", f"TX normal 0 1 0 TASK {D} 257 " + " ".join(["1 0 0 1"] * 257),
                    "TX normal -1 0", "TX normal 0x18 0", "TX NORMAL 0 0", "TX normal 0 0 TASK", "TXnormal 0 0", "TX normal 0 1", "TX normal 0 0 1", "TX normal 0 00000000001 0", "TX normal 000000001 0", f"TX normal 0 1 0 TASK {D} 2 1 0 0 1"):
            self.assertEqual(tx(cmd), "REFUSED", cmd)
        self.assertEqual(tx("TX root 00000000 0"), "OK kind=1 genome=00000000 n=0 steps= task=0 -")
        self.assertEqual(tx("TX normal 001fffff 2 1ffffff 0   "), "OK kind=0 genome=001fffff n=2 steps=1ffffff,0000000 task=0 -")
        self.assertEqual(tx(f"TX a5 18 1 1000001 TASK {D} 2 1 0 0 1 1 7 1 65535"), f"OK kind=3 genome=00000018 n=1 steps=1000001 task=2 {D} 1/0/0/1 1/7/1/65535")
        self.assertEqual(tx(f"TX inject 18 1 1000001 TASK {D} 0"), f"OK kind=2 genome=00000018 n=1 steps=1000001 task=0 -")
        for e in console_lines("valid"):                                                   # every TX the host-only path ever framed parses
            if e["dir"] == "host" and e.get("line") and " TX " in e["line"] and not e.get("note"):
                self.assertTrue(tx(w.parse(e["line"] + "\n")["payload"].decode()).startswith("OK "), e["line"][:60])
        s = self.summary("malformed_tx")
        self.assertEqual(len(s["malformed"]), 6)
        for c in s["malformed"]:
            self.assertEqual((c["status"], c["new_signreqs"], c["new_trace_events"], c["new_submits"]), (7, 0, 0, 0), c["cmd"]); self.assertIn("malformed TX", c["reason"])
        self.assertEqual((s["then"]["status"], s["then"]["x"]), (0, "closed")); self.assertEqual(s["end"]["nacks"], 6)

    def test_the_executing_sides_own_stop_reaches_the_host_through_the_console(self):
        s = self.summary("pre_event_corrupt")
        self.assertEqual((s["tx"]["status"], s["tx"]["phase"], s["tx"]["o"]), (1, "P2", False)); self.assertIn("STOP_LINK3", s["tx"]["reason"]); self.assertIsNotNone(s["next_refused"])
        s = self.summary("interrupt")
        self.assertEqual(s["tx"]["status"], 5); self.assertIsNone(s["end"])


class Allowlist(unittest.TestCase):
    def test_psmap_equals_the_register_table_and_the_a7_regions(self):
        for off in sorted(rm.APP_READABLE):
            self.assertEqual(psmap(bk.AXI_BASE + off)[0], 1, f"{off:#06x} readable")
        for off in sorted(rm.APP_WRITABLE):
            self.assertEqual(psmap(bk.AXI_BASE + off)[1], 1, f"{off:#06x} writable")
        for off in sorted(rm.KEY_WINDOW):
            self.assertEqual(psmap(bk.AXI_BASE + off), (0, 0), f"{off:#06x} the key window")
        for off in range(0, bk.AXI_SIZE, 4):
            r, wr = psmap(bk.AXI_BASE + off)
            self.assertEqual(bool(r), off in rm.APP_READABLE, f"{off:#06x} read")
            self.assertEqual(bool(wr), off in rm.APP_WRITABLE, f"{off:#06x} write")
        for a in a7.DEVC_REGS:
            self.assertEqual(psmap(a), (1, 1), f"devc {a:#010x}")
        self.assertEqual(psmap(bk.DEVCFG_BASE + 0x04), (0, 0))        # a DevC register the program never uses
        for name, (base, size) in a7.BUFFERS.items():
            self.assertEqual(psmap(base), (1, 1), name); self.assertEqual(psmap(base + size - 4), (1, 1), name); self.assertEqual(psmap(base + size), (0, 0), name)
            self.assertEqual(psmap(base + 2), (0, 0), name + " unaligned")
        base, size = a7.READ_ONLY_REGIONS["PAGE"]
        self.assertEqual(psmap(base), (1, 0)); self.assertEqual(psmap(base + size - 4), (1, 0)); self.assertEqual(psmap(base + size), (0, 0))
        self.assertEqual(psmap(bk.SLCR_PSS_IDCODE), (1, 0))
        for a in (0x00000000, 0x02000000, 0x10100000, 0x10500000, 0xE0001000, 0xF8000000, 0xF8000180, 0xF8F00620, 0xFFFFFFFC):
            self.assertEqual(psmap(a), (0, 0), f"{a:#010x}")

    def test_a7_on_the_console_programs_accesses(self):
        d = _S["root"] / "valid"
        acc = [json.loads(l) for l in (d / "accesses.jsonl").read_text().splitlines() if l.strip()]
        pcap = [json.loads(l) for l in (d / "pcap_log.jsonl").read_text().splitlines() if l.strip()]
        rep = a7.check(acc, pcap)
        self.assertEqual(rep["findings"], []); self.assertEqual(rep["buffer_reads"].get("PAGE"), 24)
        rep = a7.check(acc + [{"op": "wr", "addr": w.PAGE_ADDR + 4, "resp": 0}], pcap)
        self.assertTrue(any("PAGE region is the host's" in m for m in rep["findings"]), rep["findings"])


class SourceAudit(unittest.TestCase):
    def test_the_target_units_name_no_key_window_and_confine_the_mmio(self):
        tdir = R / "firmware/b4q/target"
        for p in sorted(tdir.glob("*.c")) + sorted(tdir.glob("*.h")):
            t = p.read_text()
            for bad in ("0x2160", "0x2164", "0x2168", "0x216c", "B4Q_KEY", "KEY0", "key_commit"):
                self.assertNotIn(bad, t, (p.name, bad))
        app = (tdir / "b4q_app.c").read_text()
        self.assertNotIn("Xil_", app); self.assertNotIn("0x43C", app); self.assertNotIn("0xF80", app)
        self.assertEqual(app.count("b4q_plat_kick()"), 1)                    # one kick site: after a framed line went out
        hal = (tdir / "b4q_board_hal.c").read_text()
        self.assertEqual(hal.count("Xil_In32("), 1); self.assertEqual(hal.count("Xil_Out32("), 1)
        self.assertIn("if (!b4q_psmap_readable(addr))", hal); self.assertIn("if (!b4q_psmap_writable(addr))", hal)
        for name in ("b4q_board_console.c", "b4q_app.c", "b4q_wire.c", "b4q_psmap.c", "b4q_app_host.c"):
            self.assertNotIn("Xil_In32", (tdir / name).read_text(), name)
        for s, b in (("bsp/lscript.ld", "firmware/b1/bsp/lscript.ld"), ("bsp/src/console.c", "firmware/b1/bsp/src/console.c"), ("bsp/include/bspconfig.h", "firmware/b1/bsp/include/bspconfig.h"),
                     ("bsp/include/xmem_config.h", "firmware/b1/bsp/include/xmem_config.h"), ("bsp/include/xparameters.h", "firmware/b1/bsp/include/xparameters.h")):
            self.assertEqual((R / "firmware/b4q" / s).read_bytes(), (R / b).read_bytes(), s)
        main = (tdir / "b4q_board_main.c").read_text()
        self.assertEqual(main.count("Xil_SetTlbAttributes("), 4)
        self.assertIn("B4Q_WDT_LOAD 1250000035u", main); self.assertIn("B4Q_WDT_PRESCALER 7u", main)   # B1's pinned values
        for h in ("XIL_EXCEPTION_ID_DATA_ABORT_INT", "XIL_EXCEPTION_ID_PREFETCH_ABORT_INT", "XIL_EXCEPTION_ID_UNDEFINED_INT"):
            self.assertIn(h, main)


class Image(unittest.TestCase):
    def test_the_image_builds_with_the_pinned_toolchain_and_its_layout_is_the_declared_one(self):
        if not (TC / "arm-none-eabi-gcc").is_file():
            raise AssertionError("the pinned cross toolchain is absent: the image cannot be built here (a named limitation, never a skip)")
        out = Path(tempfile.mkdtemp(prefix="b4q_image_"))
        p = subprocess.run(["bash", str(R / "firmware/b4q/bsp/build.sh")], capture_output=True, text=True, env={"OUT": str(out), "PATH": "/usr/bin:/bin"})
        self.assertEqual(p.returncode, 0, p.stdout[-1500:] + p.stderr[-1500:])
        elf = out / "b4q_app.elf"
        self.assertTrue(elf.is_file() and (out / "b4q_app.bin").is_file() and (out / "b4q_app.map").is_file())
        rh = subprocess.run([str(TC / "arm-none-eabi-readelf"), "-h", "-l", "-W", str(elf)], capture_output=True, text=True).stdout
        entry = int(re.search(r"Entry point address:\s+(0x[0-9a-f]+)", rh).group(1), 16)
        self.assertTrue(0x02000000 <= entry < 0x02001000, hex(entry))     # inside the first page: the vector table's reset path
        syms = {}
        for line in subprocess.run([str(TC / "arm-none-eabi-nm"), str(elf)], capture_output=True, text=True).stdout.splitlines():
            parts = line.split()
            if len(parts) == 3:
                syms[parts[2]] = int(parts[0], 16)
        self.assertEqual(syms["_vector_table"], 0x02000000)
        for s in ("main", "b4q_app_run", "b4q_transaction", "b4q_session_open", "b4q_sign", "b4q_rd32", "b4q_wr32", "outbyte", "inbyte"):
            self.assertIn(s, syms, s)
        loads = [(int(m.group(1), 16), int(m.group(2), 16)) for m in re.finditer(r"^\s+LOAD\s+0x[0-9a-f]+\s+(0x[0-9a-f]+)\s+0x[0-9a-f]+\s+0x[0-9a-f]+\s+(0x[0-9a-f]+)", rh, re.M)]
        self.assertTrue(loads)
        for vaddr, memsz in loads:
            self.assertTrue(0x02000000 <= vaddr and vaddr + memsz <= 0x0FF00000, (hex(vaddr), hex(memsz)))   # inside lscript's DDR region
            self.assertTrue(vaddr + memsz <= 0x10200000 or vaddr >= 0x10440060)                           # never over the DMA buffers / the page
        self.assertLessEqual(syms["_end"], 0x0FF00000)
        q = subprocess.run(["make", "-C", str(R / "firmware/b4q"), f"BUILD={R / 'build/b4q_firmware'}", "xcheck"], capture_output=True, text=True)
        self.assertEqual(q.returncode, 0, q.stdout + q.stderr)

    def test_the_build_evidence_names_every_input(self):
        out = Path(tempfile.mkdtemp(prefix="b4q_be_")) / "be.json"
        p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_build_evidence.py"), "--out", str(out)], capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        ev = json.loads(out.read_text())
        self.assertEqual(ev["schema"], "b4q_build_evidence")
        self.assertTrue(all(v["equal"] for v in ev["b1_verbatim"].values()), ev["b1_verbatim"])
        if ev["inputs_available"]["toolchain"]:
            self.assertGreater(len(ev["bsp_inputs"]["translation_units"]), 40); self.assertGreater(len(ev["bsp_inputs"]["headers"]), 60)
            self.assertTrue(all(v["sha256"] for v in ev["bsp_inputs"]["toolchain_objects"].values()))
        self.assertEqual(ev["image"]["ddr"]["PAGE"]["addr"], f"{w.PAGE_ADDR:#010x}")
        for s, h in ev["sources"].items():
            import hashlib
            self.assertEqual(h, hashlib.sha256((R / "firmware/b4q" / s).read_bytes()).hexdigest(), s)


if __name__ == "__main__":
    unittest.main()
