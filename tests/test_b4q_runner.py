#!/usr/bin/env python3
"""B4Q — the runner unit's tests (host-only, 2026-10-28): the evidence-log adapter (grammar, incremental derivation, the test-only
cross-check against the emulation's own logs), the PS source through the console e2e (every archive verified under the source
rules), the verifier's source rules against mutated archives, the physical runner over the device surrogate (every scenario's
declared expectations, the retention on a stop, the witnesses), the ymodem pair, and the one guard that the runner reads no
backend. Nothing here touches a board: the endpoint is a PTY, the device a process."""
from __future__ import annotations

import hashlib
import json
import os
import pty
import re
import select
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tty
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_evidence_log as el  # noqa: E402
import b4q_frames as fr  # noqa: E402
import b4q_runner_e2e as re2e  # noqa: E402
import b4q_verify as vf  # noqa: E402
import b4q_wire as w  # noqa: E402
import b4q_ymodem as ym  # noqa: E402

_S: dict = {}


def setUpModule():
    for target in ("host", "apphost", "wiretwin", "waittwin", "seqcut"):
        p = subprocess.run(["make", "-C", str(R / "firmware/b4q"), f"BUILD={R / 'build/b4q_firmware'}", target], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(p.stdout[-2000:] + p.stderr[-2000:])
    ps = Path(tempfile.mkdtemp(prefix="b4q_ps_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_console_e2e.py"), "--source", el.SOURCE_KIND, str(ps)], capture_output=True, text=True, timeout=1800)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    _S["ps"] = ps
    _S["ps_verify"] = {}
    for d in sorted(x for x in ps.iterdir() if x.is_dir()):
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(d), "--json", str(d / "verify.json")], capture_output=True, text=True, timeout=600)
        _S["ps_verify"][d.name] = (q.returncode, json.loads((d / "verify.json").read_text()))
    em = Path(tempfile.mkdtemp(prefix="b4q_em_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_console_e2e.py"), str(em), "valid"], capture_output=True, text=True, timeout=600)
    if p.returncode != 0:
        raise AssertionError(p.stdout[-3000:] + p.stderr[-3000:])
    _S["em"] = em
    rr = Path(tempfile.mkdtemp(prefix="b4q_runner_"))
    p = subprocess.run([sys.executable, "-B", str(R / "host/b4q_runner_e2e.py"), str(rr)], capture_output=True, text=True, timeout=3600)
    _S["runner_rc"], _S["runner_out"] = p.returncode, p.stdout[-3000:] + p.stderr[-3000:]
    _S["runner"] = rr
    _S["runner_summary"] = {s["name"]: s for s in json.loads((rr / "e2e_summary.json").read_text())} if (rr / "e2e_summary.json").is_file() else {}


def _jl(p: Path) -> list:
    return [json.loads(l) for l in p.read_text().splitlines() if l.strip()]


class Adapter(unittest.TestCase):
    def setUp(self):
        self.raw = (_S["ps"] / "valid/raw/evidence_log.bin").read_bytes()

    def test_the_grammar_is_refused_by_name(self):
        with self.assertRaisesRegex(el.LogRefusal, "whole number"):
            el.parse(self.raw[:-5])
        rec = bytearray(self.raw[:16]); rec[4] = 9
        with self.assertRaisesRegex(el.LogRefusal, "unknown kind"):
            el.parse(bytes(rec))
        rec = bytearray(self.raw[:16]); rec[5] = 2
        with self.assertRaisesRegex(el.LogRefusal, "unknown op"):
            el.parse(bytes(rec))
        win = next(r for r in el.parse(self.raw) if r["kind"] == el.KIND_WIN)
        rec = bytearray(self.raw[win["off"]:win["off"] + 16]); rec[6] = 0; rec[7] = 0
        with self.assertRaisesRegex(el.LogRefusal, "zero count"):
            el.parse(bytes(rec))
        rec = bytearray(self.raw[win["off"]:win["off"] + 16]); rec[6] |= 0x40
        with self.assertRaisesRegex(el.LogRefusal, "run record outside"):
            el.parse(bytes(rec))
        rec = bytearray(self.raw[:16]); rec[4] = el.KIND_MARK; rec[8:12] = (99).to_bytes(4, "big")
        with self.assertRaisesRegex(el.LogRefusal, "unknown mark"):
            el.parse(bytes(rec))

    def test_the_incremental_derivation_is_the_whole_one(self):
        whole = el.derive(el.parse(self.raw))
        d = el.Deriver()
        for cut in (16, 1024, 5000, 20000, 60000, len(self.raw)):
            d.feed_bytes(self.raw[:cut - cut % 16])
        d.feed_bytes(self.raw)
        self.assertEqual(d.trace, whole["trace"]); self.assertEqual(d.pcap, whole["pcap"]); self.assertEqual(d.accesses, whole["accesses"])
        with self.assertRaisesRegex(el.LogRefusal, "shrank"):
            d.feed_bytes(self.raw[:16])

    def test_the_ps_log_is_the_emulation_s_own_logs_test_only_cross_check(self):
        """The two witnesses of one session agree: the PS's log (what the program did) and the fake's trace / PCAP (what it answered)
        — a TEST's cross-check; no session reads the fake's logs for a record under the PS source."""
        d = _S["ps"] / "valid"
        D = el.derive(el.parse(self.raw))
        trace, acc, pcap = _jl(d / "trace.jsonl"), _jl(d / "accesses.jsonl"), _jl(d / "pcap_log.jsonl")
        self.assertEqual([vf.canon(e) for e in trace], [vf.canon(e) for e in D["trace"]])          # the archived files ARE the derivation under the PS source
        self.assertEqual([(e["op"], e["addr"], e["resp"]) for e in acc], [(e["op"], e["addr"], e["resp"]) for e in D["accesses"]])
        private = _S["em"] / "valid"                                                                 # the emulated run of the same scenario: its fake's logs
        ptrace, ppcap = _jl(private / "trace.jsonl"), _jl(private / "pcap_log.jsonl")
        key = lambda e: e.get("mark") or (e["op"], e["addr"], e["resp"])
        a = [key(e) for e in D["trace"] if e.get("mark") != "open"]
        b = [key(e) for e in ptrace]
        self.assertEqual(a, b[len(b) - len(a):])                                                   # the same program, the same accesses (after the fake's provisioning prefix); the data differ by nonce
        self.assertEqual(sorted(e["pcap"] for e in D["pcap"]), sorted(e["pcap"] for e in ppcap if e["pcap"] not in ("envelope_written", "envelope_refused")))

    def test_the_links_recomputed_from_the_log_are_the_session_s(self):
        d = _S["ps"] / "valid"
        recs = el.parse(self.raw)
        groups = el.readback_groups(el.readbacks(recs))
        st = el.stagings(recs)
        self.assertEqual(len(groups), 13)                      # the opening's one + 3 per transaction x 4
        for k in range(1, 5):
            links = json.loads((d / f"tx_{k:03d}/links.json").read_text())
            g = groups[1 + 3 * (k - 1):1 + 3 * k]
            self.assertEqual([x["frames_sha256"] for x in g], [links["fabric_readback_sha256_pre_event"], links["fabric_readback_sha256_post_event"], links["base_readback_sha256"]], k)
            self.assertEqual(el.staging_witness(st[4 * (k - 1):4 * (k - 1) + 2]), links["staging_readback_sha256"], k)   # the candidate's two envelopes (the restore's two follow)
        D = el.derive(recs)
        tx = [json.loads((d / f"tx_{k:03d}/record.json").read_text()) for k in range(1, 5)]
        for k, r in enumerate(tx, 1):
            lo, hi = r["trace_range"]
            links = json.loads((d / f"tx_{k:03d}/links.json").read_text())
            self.assertEqual(el.nonce_read(D["trace"], lo, hi), links["nonce"], k)


class PsSource(unittest.TestCase):
    def test_every_ps_source_archive_verifies_and_agrees(self):
        for name, (rc, rep) in _S["ps_verify"].items():
            self.assertEqual(rc, 0, (name, rep.get("refused"), rep.get("session"), rep.get("verifier_error")))
            self.assertTrue(rep["agree"], name)
            self.assertEqual(rep["source"]["kind"], el.SOURCE_KIND, name)
            self.assertEqual(rep["source"]["findings"], [], name)
        self.assertEqual(len(_S["ps_verify"]), 19)

    def test_the_valid_archive_is_clean_and_its_readback_digests_are_the_emulated_run_s(self):
        rc, rep = _S["ps_verify"]["valid"]
        self.assertTrue(rep["clean"], rep)
        for k in range(1, 5):
            a = json.loads((_S["ps"] / f"valid/tx_{k:03d}/links.json").read_text()); b = json.loads((_S["em"] / f"valid/tx_{k:03d}/links.json").read_text())
            for key in ("fabric_readback_sha256_pre_event", "fabric_readback_sha256_post_event", "base_readback_sha256", "staging_readback_sha256"):
                self.assertEqual(a.get(key), b.get(key), (k, key))      # the frames are the genomes': the same under both witnesses; the commit / nonce differ by run
        m = json.loads((_S["ps"] / "valid/manifest.json").read_text())
        self.assertEqual(m["source"]["kind"], el.SOURCE_KIND); self.assertTrue(m["source"]["digest_equal"])
        self.assertEqual(m["source"]["end_log"], m["source"]["bytes"])
        self.assertEqual(m["source"]["end_log_sha256"], m["source"]["sha256"])
        self.assertEqual(m["transport"]["evidence_log"]["stats"]["bad_chunks"], 0)

    def test_the_terminal_end_and_the_cut_are_named_limitations_not_filled_in(self):
        rc, rep = _S["ps_verify"]["sequence_cut"]
        self.assertTrue(any("terminal END" in x for x in rep["source"]["limitations"]), rep["source"])
        m = json.loads((_S["ps"] / "sequence_cut/manifest.json").read_text())
        self.assertTrue(m["source"]["tail_unobtainable"]); self.assertLess(m["source"]["bytes"], m["source"]["end_log"])
        rc, rep = _S["ps_verify"]["interrupt"]
        m = json.loads((_S["ps"] / "interrupt/manifest.json").read_text())
        self.assertEqual(m["records"][-1]["trace_range"][0], m["records"][-1]["trace_range"][1])   # the cut transaction: an empty range, no evidence of its own
        self.assertTrue(any("no observation sealed" in f for f in m["records"][-1]["findings"]))

    def test_the_export_epilogue_pulls_the_log_after_the_end(self):
        console = _jl(_S["ps"] / "valid/console.jsonl")
        types = [e.get("type") for e in console if e["dir"] == "board"]
        k = types.index("END")
        self.assertIn("RING", types[k + 1:])                           # the log pulled after the END (the epilogue)
        host = [e["line"] for e in console if e["dir"] == "host" and e["line"]]
        self.assertTrue(host[-1].startswith("B4Q1 QUIT "))               # the epilogue closed by the host


class SourceRules(unittest.TestCase):
    """The verifier's source rules against mutated copies of the valid PS-source archive — every mutation named."""

    def _copy(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="b4q_mut_")) / "valid"
        shutil.copytree(_S["ps"] / "valid", d)
        return d

    def _manifest(self, d: Path, fn):
        m = json.loads((d / "manifest.json").read_text()); fn(m); (d / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")

    def test_the_raw_log_missing_or_altered_is_refused(self):
        d = self._copy(); (d / "raw/evidence_log.bin").unlink()
        self.assertIn("raw", vf.verify(d)["refused"])
        d = self._copy(); raw = bytearray((d / "raw/evidence_log.bin").read_bytes()); raw[12] ^= 1; (d / "raw/evidence_log.bin").write_bytes(bytes(raw))
        self.assertIn("not the bytes the manifest's source declares", vf.verify(d)["refused"])

    def test_a_raw_log_that_matches_its_declaration_but_not_the_board_or_the_derivation_is_found(self):
        d = self._copy(); raw = bytearray((d / "raw/evidence_log.bin").read_bytes())
        win = next(r for r in el.parse(bytes(raw)) if r["kind"] == el.KIND_WIN)
        raw[win["off"] + 12] ^= 1; raw = bytes(raw)                           # a window read's data: the derivation changes with it (a mark's data would not)
        (d / "raw/evidence_log.bin").write_bytes(raw)
        self._manifest(d, lambda m: m["source"].update({"sha256": hashlib.sha256(raw).hexdigest()}))
        rep = vf.verify(d)
        self.assertIsNone(rep["refused"]); self.assertFalse(rep["agree"])
        self.assertTrue(any("last RING reported" in f for f in rep["source"]["findings"]), rep["source"])
        self.assertTrue(any("derivation" in f for f in rep["source"]["findings"]), rep["source"])

    def test_a_derived_file_not_the_derivation_is_found(self):
        for name in ("trace.jsonl", "pcap_log.jsonl", "accesses.jsonl"):
            d = self._copy()
            lines = (d / name).read_text().splitlines()
            e = json.loads(lines[len(lines) // 2])
            key = "data" if "data" in e else ("n" if "n" in e else "addr")
            e[key] = (e[key] ^ 1) if isinstance(e[key], int) else e[key]
            lines[len(lines) // 2] = json.dumps(e); (d / name).write_text("\n".join(lines) + "\n")
            rep = vf.verify(d)
            self.assertTrue(any(f"{name} is not the adapter's derivation" in f for f in rep["source"]["findings"]), (name, rep["source"], rep.get("refused")))

    def test_console_positions_not_the_board_s_log_offsets_are_found(self):
        d = self._copy()
        lines = (d / "console.jsonl").read_text().splitlines()
        k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "RESULT")
        e = json.loads(lines[k]); e["i"] += 1; lines[k] = json.dumps(e); (d / "console.jsonl").write_text("\n".join(lines) + "\n")
        rep = vf.verify(d)
        self.assertTrue(any("position is not the board's log offset" in f for f in rep["source"]["findings"]), rep["source"])

    def test_a_board_transport_and_an_unknown_source_are_refused_by_name(self):
        d = self._copy(); self._manifest(d, lambda m: m["transport"].update({"kind": "uart-board"}))
        self.assertIn("uboot.json: missing", vf.verify(d)["refused"])        # a pipe archive relabelled as a device archive has no runner material: refused by name
        d = self._copy(); self._manifest(d, lambda m: m["source"].update({"kind": "ps-evidence-log-v9"}))
        self.assertIn("not a source this verifier knows", vf.verify(d)["refused"])
        d = self._copy(); self._manifest(d, lambda m: m.update({"source": None}))
        rep = vf.verify(d)                                             # an undeclared log beside what claims to be an emulated source: held to the "emulation" (the derived files) — it agrees, since they are its derivation
        self.assertEqual(rep["source"]["kind"], "emulated")

    def test_an_emulated_archive_s_retained_log_is_held_to_the_emulation(self):
        d = Path(tempfile.mkdtemp(prefix="b4q_mut_")) / "valid"
        shutil.copytree(_S["em"] / "valid", d)
        rep = vf.verify(d)
        self.assertEqual(rep["source"]["kind"], "emulated"); self.assertTrue(rep["source"]["agrees_with_emulation"]); self.assertTrue(rep["agree"])
        raw = bytearray((d / "raw/evidence_log.bin").read_bytes())
        win = next(r for r in el.parse(bytes(raw)) if r["kind"] == el.KIND_WIN)
        raw[win["off"] + 12] ^= 1                                       # one window read's data changed: the PS log no longer says what the fake answered
        (d / "raw/evidence_log.bin").write_bytes(bytes(raw))
        rep = vf.verify(d)
        self.assertTrue(any("not the emulation's trace" in f for f in rep["source"]["findings"]), rep["source"])


class Runner(unittest.TestCase):
    def test_every_scenario_met_its_declared_expectations(self):
        self.assertTrue(_S["runner_summary"], _S["runner_out"])
        bad = {n: s["expect_failures"] for n, s in _S["runner_summary"].items() if s["expect_failures"]}
        self.assertEqual(bad, {}, bad)
        self.assertEqual(_S["runner_rc"], 0, _S["runner_out"])
        self.assertEqual(set(_S["runner_summary"]), set(re2e.SCENARIOS))

    def test_the_valid_run_over_the_pty_carries_both_witnesses_and_verifies_clean(self):
        s = _S["runner_summary"]["valid"]
        self.assertTrue(s["load_witness"]["equal"]); self.assertTrue(s["page_witness"]["equal"]); self.assertTrue(s["source"]["digest_equal"])
        self.assertEqual(s["verify_rc"], 0)
        m = json.loads((_S["runner"] / "valid/manifest.json").read_text())
        rep = json.loads((_S["runner"] / "valid/verify.json").read_text())
        self.assertEqual(m["transport"]["kind"], "console-pty-surrogate"); self.assertEqual(m["source"]["kind"], el.SOURCE_KIND)
        self.assertIsNone(m["backend"])                                   # no backend in the runner's process: nothing to read a board fact from
        self.assertTrue(m["emulated"])
        u = json.loads((_S["runner"] / "valid/uboot.json").read_text())
        whats = [st["what"] for st in u["uboot_steps"]]
        self.assertEqual(whats[0], "prompt"); self.assertEqual(whats[1:3], ["md.l", "md.l"])                 # the admission's VARIANT and FPGA0_CLK_CTRL reads come before any load
        self.assertEqual(u["uboot_steps"][1]["sent"], f"md.l {rn.VARIANT_ADDR:08x} 1"); self.assertEqual(u["uboot_steps"][1]["words"], [f"{rm.VARIANT_WORD:08x}"])
        self.assertIn("loady", whats); self.assertIn("crc32", whats); self.assertIn("go", whats)
        self.assertEqual(u["load_witness"]["host_crc32"], u["load_witness"]["uboot_crc32"])
        self.assertEqual(whats.count("mw.l"), w.PAGE_WORDS)
        self.assertTrue(u["admission"]["ok"]); self.assertEqual(u["admission"]["image"]["pin_source"][:14], "build evidence"); self.assertEqual(u["phase"], "ended")
        self.assertEqual(rep["runner"]["findings"], []); self.assertEqual(rep["provenance"]["kind"], "console-pty-surrogate"); self.assertFalse(rep["provenance"]["observed_on_device"])
        self.assertEqual(rep["runner"]["witnesses"]["image"]["transferred_sha256"], m["instrument"]["image_sha256"])   # the image re-assembled from the SENT stream is the pinned one
        self.assertTrue(rep["clean"], rep["session"])
        # the IDENT's image echo is the PAGE's word; the load witness is U-Boot's crc of the loaded bytes: two different facts, both held
        self.assertEqual(m["transport"]["ident"]["app_image_sha_lo32"], int(m["instrument"]["image_sha256"][:8], 16))
        self.assertEqual(hashlib.sha256((R / m["executing_side"]["binary"]).read_bytes()).hexdigest(), m["instrument"]["image_sha256"])

    def test_a_stop_before_go_retains_the_transcript_and_runs_nothing(self):
        for name, last in (("wrong_crc", "crc32"), ("interrupted_load", "loady"), ("md_garbage", "md.l")):
            d = _S["runner"] / name
            self.assertTrue((d / "raw/console.bin").is_file() and (d / "uboot.json").is_file(), name)
            u = json.loads((d / "uboot.json").read_text())
            whats = [st["what"] for st in u.get("uboot_steps") or u.get("steps")]
            self.assertNotIn("go", whats, name); self.assertEqual(whats[-1], last, (name, whats))
            self.assertNotIn(b"go 02000000\r", (d / "raw/console_tx.bin").read_bytes(), name)
            s = _S["runner_summary"][name]
            self.assertFalse(s["opened"]); self.assertTrue(s["stop"]["why"], name)
            rep = json.loads((d / "verify.json").read_text())
            self.assertTrue(rep["agree"], (name, rep.get("refused"), rep.get("session")))
            self.assertTrue(rep["control_plane"]["stop"]["demonstrated"], (name, rep["control_plane"]))   # the named stop is what the raw streams show

    def test_the_cut_sessions_are_interrupted_and_their_partial_export_is_a_named_limitation(self):
        for name in ("reset_mid_session", "silence_mid_session"):
            m = json.loads((_S["runner"] / name / "manifest.json").read_text())
            self.assertIn("transport", m["interrupted"], name)
            self.assertFalse(m["source"]["digest_equal"], name)
            rep = json.loads((_S["runner"] / name / "verify.json").read_text())
            self.assertTrue(rep["agree"], (name, rep["session"], rep.get("console")))
            self.assertTrue(any("cut by the transport" in x for x in rep["source"]["limitations"]), (name, rep["source"]))

    def test_a_corrupted_chunk_is_re_asked_and_a_corrupted_page_is_the_device_s_stop(self):
        s = _S["runner_summary"]["corrupt_chunk"]
        self.assertEqual(s["stats_pull"]["bad_chunks"], 1); self.assertTrue(s["source"]["digest_equal"]); self.assertEqual(s["verify_rc"], 0)
        s = _S["runner_summary"]["corrupt_page"]
        self.assertTrue(s["page_witness"]["equal"]); self.assertFalse(s["opened"]); self.assertEqual(s["end"]["kind"], "STOPPED")
        m = json.loads((_S["runner"] / "corrupt_page/manifest.json").read_text())
        self.assertIsNone(m["transport"]["ident"])


class YModem(unittest.TestCase):
    class P:
        def __init__(self, fd):
            self.fd = fd

        def read(self, t):
            r, _, _ = select.select([self.fd], [], [], t)
            return os.read(self.fd, 65536) if r else b""

        def write(self, d):
            off = 0
            while off < len(d):
                off += os.write(self.fd, d[off:])

    def test_the_pair_moves_a_file_byte_for_byte_and_a_cancel_is_an_error(self):
        m, s = pty.openpty(); tty.setraw(s); tty.setraw(m)
        data = os.urandom(10000)
        res = {}

        def rx():
            try:
                res["rx"] = ym.receive(self.P(m))
            except Exception as e:
                res["err"] = repr(e)
        t = threading.Thread(target=rx); t.start()
        st = ym.send(self.P(s), data, "x.bin"); t.join(30)
        got, info = res["rx"]
        self.assertEqual(got, data); self.assertEqual(info["blocks"], 10); self.assertEqual(st["blocks"], 10)
        m, s = pty.openpty(); tty.setraw(s); tty.setraw(m)

        def rx2():
            try:
                ym.receive(self.P(m), cancel_after_blocks=3)
            except ym.YModemError:
                pass
        t = threading.Thread(target=rx2); t.start()
        with self.assertRaises(ym.YModemError):
            ym.send(self.P(s), data, "x.bin")
        t.join(30)


class Guards(unittest.TestCase):
    def test_the_runner_constructs_no_backend(self):
        """The actual source boundary (the owner's P3): a RunnerSession is built with NO Backend object at all — the base session is asked
        not to make one — and its evidence is the PS log's; the string guard only names what the test holds."""
        import b4q_backend as bk
        import b4q_runner as rn
        made = []
        orig = bk.Backend.__init__

        def spy(self, *a, **k):
            made.append(1); return orig(self, *a, **k)
        bk.Backend.__init__ = spy
        try:
            port = FakePort(scripted_uboot())
            s = rn.RunnerSession(Path(tempfile.mkdtemp(prefix="b4q_nb_")), port, rn.UBoot(port, []), rn.ExecutionContext(image_sha256="0" * 64, image_path=str(rn.IMAGE)))
        finally:
            bk.Backend.__init__ = orig
        self.assertEqual(made, []); self.assertIsNone(s.backend); self.assertIsInstance(s.evidence, cs.PsEvidence)
        src = (R / "host/b4q_runner.py").read_text()
        self.assertNotIn("private", src.lower())
        self.assertIn("make_backend", src)


if __name__ == "__main__":
    unittest.main()


# ---------------------------------------------------------------- the repair's counterexamples (the owner's HOLD on dad9e4de): R1–R4
import b4q_console_session as cs  # noqa: E402
import b4q_runner as rn  # noqa: E402
import b4q_device_fixture as df  # noqa: E402
import b4carrier_regmap as rm  # noqa: E402


class FakePort:
    """A port with the runner's interface over scripted byte queues: `script(cmd_bytes) -> reply bytes` answers each write; `fill` delivers
    the queued replies in the chunking the script decided (coalesced or fragmented); no device, no PTY."""

    def __init__(self, script, kind="console-pty-surrogate", fail_write_at=None, chunk=None):
        self.script, self.kind, self.path, self.real = script, kind, "fake", "/dev/pts/fake"
        self.buf, self.rx_log, self.tx_log = bytearray(), bytearray(), bytearray()
        self.queue = []
        self.closed = False
        self.writes = 0
        self.fail_write_at = fail_write_at
        self.chunk = chunk

    def fill(self, timeout):
        if not self.queue:
            return 0
        data = self.queue.pop(0)
        self.buf += data; self.rx_log += data
        return len(data)

    def read(self, timeout):
        if not self.buf:
            self.fill(timeout)
        d = bytes(self.buf); del self.buf[:]
        return d

    def unread(self, data):
        self.buf[0:0] = data

    def write(self, data):
        self.writes += 1
        if self.fail_write_at is not None and self.writes >= self.fail_write_at:
            raise OSError(5, "Input/output error")
        self.tx_log += data
        reply = self.script(data)
        if reply:
            if self.chunk:
                self.queue += [reply[i:i + self.chunk] for i in range(0, len(reply), self.chunk)]
            else:
                self.queue.append(reply)

    def close(self):
        self.closed = True


def scripted_uboot(model=b"Ebang EBAZ4203 (fixture)", dram=512, variant=rm.VARIANT_WORD, fclk0=0x00200A00, page=None, crc_range=None, md_addr_shift=0):
    """A minimal scripted U-Boot: the banner on the first CR, md.l of the words it knows, mw.l accepted, crc32 answered for the asked range
    (or `crc_range` when the fixture lies), go announced. `page`: the words md.l shows for the page (None: what mw.l wrote)."""
    mem = {}
    state = {"booted": False}
    PROMPT = b"Zynq> "

    def script(data: bytes):
        if not state["booted"]:
            state["booted"] = True
            return b"\r\n\r\nU-Boot 2026.04-rc5 (fixture)\r\nModel: " + model + b"\r\nDRAM:  ECC disabled " + str(dram).encode() + b" MiB\r\n" + PROMPT
        line = data.rstrip(b"\r").decode("ascii", "replace")
        parts = line.split()
        if not parts:
            return PROMPT
        out = line.encode() + b"\r\n"
        if parts[0] == "md.l":
            addr, n = int(parts[1], 16), int(parts[2], 16) if len(parts) > 2 else 16
            words = []
            for k in range(n):
                a = addr + 4 * k
                if a == rn.VARIANT_ADDR:
                    words.append(variant)
                elif a == rn.SLCR_FPGA0_CLK_CTRL:
                    words.append(fclk0)
                elif page is not None and w.PAGE_ADDR <= a < w.PAGE_ADDR + 4 * w.PAGE_WORDS:
                    words.append(page[(a - w.PAGE_ADDR) // 4])
                else:
                    words.append(mem.get(a, 0))
            for k in range(0, n, 4):
                ws = words[k:k + 4]
                out += f"{addr + 4 * k + md_addr_shift:08x}:".encode() + b"".join(f" {x:08x}".encode() for x in ws) + b"    ....\r\n"
        elif parts[0] == "mw.l":
            mem[int(parts[1], 16)] = int(parts[2], 16)
        elif parts[0] == "crc32":
            a, n = int(parts[1], 16), int(parts[2], 16)
            s, e = crc_range or (a, a + n - 1)
            out += f"crc32 for {s:08x} ... {e:08x} ==> deadbeef\r\n".encode()
        elif parts[0] == "go":
            return out + b"## Starting application at 0x02000000 ...\r\n" + b"B4Q1 IDENT 1 " + b"0" * 32 + b" e30 00000000\n"
        return out + PROMPT
    return script


class Transport(unittest.TestCase):
    """R2: the one receive buffer handed from reader to reader; the bounds; the exact address / range checks; the retention on a write error."""

    def test_a_coalesced_go_reply_keeps_the_applications_first_line_for_the_session(self):
        port = FakePort(scripted_uboot())
        ub = rn.UBoot(port, [])
        port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
        ub.go(0x02000000)
        self.assertTrue(bytes(port.buf).startswith(b"B4Q1 IDENT 1 "), bytes(port.buf))                   # the first application line survives the `go` reader
        for chunk in (3, 17, 1000):                                                                           # fragmented deliveries: the same
            port = FakePort(scripted_uboot(), chunk=chunk); ub = rn.UBoot(port, [])
            port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0); ub.go(0x02000000)
            while b"\n" not in port.buf:
                port.fill(0.1)
            self.assertTrue(bytes(port.buf).startswith(b"B4Q1 IDENT 1 "), chunk)

    def test_the_ymodem_tail_coalesced_with_the_prompt_reaches_the_prompt_reader(self):
        data = os.urandom(3000)
        blocks = {"n": 0}

        def receiver(chunk: bytes):
            if chunk.startswith(b"loady"):
                return chunk + b"\r\n## Ready for binary (ymodem) download to 0x02000000 at 115200 bps...\r\nC"
            if chunk[:1] == bytes([ym.STX]) or chunk[:1] == bytes([ym.SOH]):
                blocks["n"] += 1
                if chunk[1] == 0 and blocks["n"] > 1:                                       # the empty header: the ACK COALESCED with U-Boot's tail and the prompt
                    return bytes([ym.ACK]) + b"\r\nxyzModem - CRC mode, 2(SOH)/3(STX)/0(CAN) packets, 0 retries\r\n## Total Size = 0x00000bb8 = 3000 Bytes\r\nZynq> "
                return bytes([ym.ACK]) + (b"C" if chunk[1] == 0 else b"")
            if chunk == bytes([ym.EOT]):
                return bytes([ym.NAK]) if blocks.get("eot", 0) == 0 or blocks.update({"eot": 1}) else bytes([ym.ACK]) + b"C"
            return b""
        state = {"eot": 0}

        def script(chunk):
            if chunk == bytes([ym.EOT]):
                state["eot"] += 1
                return bytes([ym.NAK]) if state["eot"] == 1 else bytes([ym.ACK]) + b"C"
            return receiver(chunk)
        port = FakePort(script)
        ub = rn.UBoot(port, [])
        st = ub.loady(0x02000000, data, "x.bin", timeout=10)
        self.assertEqual(st["total"], 3000); self.assertTrue(st["ok"])
        self.assertEqual(bytes(port.buf), b"")                                                               # the prompt reader consumed the tail that arrived with the last ACK

    def test_a_junk_flooding_receiver_is_bounded_by_the_transfers_deadline(self):
        port = FakePort(lambda chunk: b"zzzzzzzz" * 64)                                                       # every write answered by junk, never an ACK
        t0 = time.monotonic()
        with self.assertRaisesRegex(ym.YModemError, "never asked|deadline|timeout"):
            ym.send(port, os.urandom(2048), "x.bin", timeout=2.0, retries=50)
        self.assertLess(time.monotonic() - t0, 4.0)
        port = FakePort(lambda chunk: b"C" if chunk.startswith(b"loady") or chunk == b"" else b"q" * 100)    # the header asked for, then junk forever
        t0 = time.monotonic()
        with self.assertRaises(ym.YModemError):
            ym.send(port, os.urandom(2048), "x.bin", timeout=2.0, retries=50)
        self.assertLess(time.monotonic() - t0, 4.0)

    def test_md_l_and_crc32_hold_the_reply_to_the_asked_address_and_range(self):
        port = FakePort(scripted_uboot(md_addr_shift=4)); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
        with self.assertRaisesRegex(rn.TransportStop, "a line for address"):
            ub.md_l(w.PAGE_ADDR, 1)
        port = FakePort(scripted_uboot(crc_range=(0x02000000, 0x02000000))); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
        with self.assertRaisesRegex(rn.TransportStop, "not the asked"):
            ub.crc32(0x02000000, 100)
        port = FakePort(scripted_uboot()); ub = rn.UBoot(port, []); port.write(b"\r"); ub.read_until(rn.PROMPT_RE, 1.0)
        self.assertEqual(ub.md_l(rn.VARIANT_ADDR, 1), [rm.VARIANT_WORD]); self.assertEqual(ub.crc32(0x02000000, 100), 0xDEADBEEF)

    def test_a_write_error_persists_the_acquired_prefix_closes_the_port_and_is_a_programming_error(self):
        port = FakePort(scripted_uboot(), fail_write_at=3)                                                    # the third write (the first admission md.l) fails at the OS
        out = Path(tempfile.mkdtemp(prefix="b4q_wr_")) / "run"
        ctx = rn.ExecutionContext(image_sha256=hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest(), image_path=str(rn.IMAGE))
        with self.assertRaises(OSError):
            rn.run("fake", out, rn.body_control_plane, context=ctx, port=port)
        self.assertTrue(port.closed)
        rx = (out / "raw/console.bin").read_bytes()
        self.assertIn(b"Model: Ebang EBAZ4203", rx)                                                           # the acquired prefix is on disk
        u = json.loads((out / "uboot.json").read_text())
        self.assertEqual(u["stops"][-1]["kind"], "ProgrammingError"); self.assertIn("Input/output error", u["stops"][-1]["why"])
        s = json.loads((out / "summary.json").read_text()); self.assertEqual(s["stop"]["kind"], "ProgrammingError")


class Admission(unittest.TestCase):
    """R3: the execution context pins the image and the target; nothing execution-sensitive before the admission."""

    def _run(self, script, ctx, body=rn.body_control_plane):
        port = FakePort(script)
        out = Path(tempfile.mkdtemp(prefix="b4q_adm_")) / "run"
        s = rn.run("fake", out, body, context=ctx, port=port)
        return s, port, out

    def test_an_arbitrary_local_file_is_refused_before_any_load_whatever_its_crc(self):
        f = Path(tempfile.mkdtemp(prefix="b4q_img_")) / "not-an-image.bin"; f.write_bytes(b"\x00" * 56)
        ctx = rn.ExecutionContext(image_sha256=hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest(), image_path=str(f))
        s, port, out = self._run(scripted_uboot(), ctx, body=rn.body_open)
        self.assertEqual(s["stop"]["kind"], "AdmissionStop"); self.assertTrue(s["stop"]["why"].startswith("image: the selected file"))
        self.assertNotIn(b"loady", port.tx_log); self.assertNotIn(b"go ", port.tx_log); self.assertFalse(s["opened"])
        rep = vf.verify(out)
        self.assertTrue(rep["agree"], rep["session"]); self.assertTrue(rep["control_plane"]["stop"]["demonstrated"])

    def test_the_pin_comes_from_the_build_evidence_not_the_file(self):
        f = Path(tempfile.mkdtemp(prefix="b4q_img_")) / "b4q_app_v2.bin"; f.write_bytes(rn.IMAGE.read_bytes() + b"\x00")
        ctx = rn.ExecutionContext.pinned(image=f)
        self.assertEqual(ctx.image_sha256, json.loads(rn.PIN_FILE.read_text())["image"]["sha256"]); self.assertTrue(ctx.pin_source.startswith("build evidence"))
        s, port, out = self._run(scripted_uboot(), ctx)
        self.assertEqual(s["stop"]["kind"], "AdmissionStop"); self.assertNotIn(b"loady", port.tx_log)

    def test_the_board_the_dram_the_variant_and_the_clock_are_held_before_the_nonce_and_the_load(self):
        pin = hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest()
        cases = [(scripted_uboot(model=b"Ebang EBAZ4205 (fixture)", dram=256), {}, "board: the model"),
                 (scripted_uboot(model=b"Ebang EBAZ4205 (fixture)", dram=256), {"board_models": ("Ebang EBAZ4205",)}, "board: DRAM 256 MiB"),
                 (scripted_uboot(variant=0x42340002), {}, "carrier: the VARIANT word"),
                 (scripted_uboot(fclk0=0x00100A00), {"fclk0_ctrl_expected": 0x00200A00}, "clock: FPGA0_CLK_CTRL")]
        for script, kw, prefix in cases:
            s, port, out = self._run(script, rn.ExecutionContext(image_sha256=pin, image_path=str(rn.IMAGE), **kw))
            self.assertEqual(s["stop"]["kind"], "AdmissionStop", prefix); self.assertTrue(s["stop"]["why"].startswith(prefix), s["stop"])
            self.assertNotIn(b"loady", port.tx_log); self.assertNotIn(f"md.l {rn.VARIANT_ADDR + 0:08x}".encode().replace(b"2034", b"202c"), port.tx_log)   # no NONCE read
            rep = vf.verify(out)
            self.assertTrue(rep["agree"], (prefix, rep["session"])); self.assertTrue(rep["control_plane"]["stop"]["demonstrated"], (prefix, rep["control_plane"]))
        u = json.loads((out / "uboot.json").read_text())
        self.assertEqual(u["phase"], "stopped"); self.assertEqual(u["phase_at_stop"], "prompt")


class ArchiveContract(unittest.TestCase):
    """R1: the runner's witnesses are recomputed from the raw streams; summaries and agreeing copies are not authorities; an invented
    pre-go stop is refuted by the streams."""

    def _copy(self, name="valid") -> Path:
        d = Path(tempfile.mkdtemp(prefix="b4q_arc_")) / name
        shutil.copytree(_S["runner"] / name, d)
        return d

    def _edit(self, d: Path, fn):
        u = json.loads((d / "uboot.json").read_text()); m = json.loads((d / "manifest.json").read_text())
        fn(u, m)
        m["transport"]["runner"] = u
        (d / "uboot.json").write_text(json.dumps(u, indent=1) + "\n"); (d / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")

    def test_deleting_the_boot_evidence_is_refused(self):
        for f in ("uboot.json", "raw/console.bin", "raw/console_tx.bin"):
            d = self._copy(); (d / f).unlink()
            rep = vf.verify(d)
            self.assertIn(f.split("/")[-1], rep["refused"] or "", f)

    def test_a_forged_load_or_page_witness_is_found_against_the_streams(self):
        d = self._copy(); self._edit(d, lambda u, m: u["load_witness"].update({"host_crc32": "11111111", "uboot_crc32": "22222222", "equal": True}))
        rep = vf.verify(d); self.assertFalse(rep["agree"]); self.assertTrue(any("load witness: uboot.json says" in x for x in rep["session"]), rep["session"])
        d = self._copy(); self._edit(d, lambda u, m: u["page_witness"]["read_back"].__setitem__(0, "00000000"))
        rep = vf.verify(d); self.assertFalse(rep["agree"]); self.assertTrue(any("page witness: uboot.json's" in x for x in rep["session"]), rep["session"])
        d = self._copy()                                                                                        # the streams themselves altered: the crc line's value
        rx = (d / "raw/console.bin").read_bytes(); k = rx.find(b"==> "); rx = rx[:k + 4] + (b"0" if rx[k + 4:k + 5] != b"0" else b"1") + rx[k + 5:]
        (d / "raw/console.bin").write_bytes(rx)
        rep = vf.verify(d); self.assertIn("not the bytes uboot.json declares", rep["refused"] or "")
        self._edit(d, lambda u, m: u["raw"].update({"console_bin_sha256": hashlib.sha256(rx).hexdigest()}))
        rep = vf.verify(d); self.assertFalse(rep["agree"]); self.assertTrue(any("load witness: uboot.json says" in x for x in rep["session"]), rep["session"])

    def test_an_invented_pre_go_stop_is_refuted_by_the_streams(self):
        d = self._copy()
        (d / "session_open.json").write_text("null\n")
        self._edit(d, lambda u, m: (m.update({"records": [], "no_session": True}), u.update({"phase": "stopped", "phase_at_stop": "pre-go", "stops": [{"why": "load witness: invented", "kind": "TransportStop"}]})))
        rep = vf.verify(d)
        self.assertFalse(rep["agree"], rep)
        self.assertTrue(any("streams show `go`" in x for x in rep["session"]), rep["session"])
        self.assertTrue(any("transaction directories present" in x for x in rep["session"]), rep["session"])

    def test_a_console_line_not_in_the_stream_is_found(self):
        d = self._copy()
        lines = (d / "console.jsonl").read_text().splitlines()
        k = next(i for i, l in enumerate(lines) if json.loads(l).get("type") == "HB")
        e = json.loads(lines[k]); e["line"] = e["line"][:-8] + "00000000"; lines[k] = json.dumps(e); (d / "console.jsonl").write_text("\n".join(lines) + "\n")
        rep = vf.verify(d)
        self.assertTrue(any("console linkage" in x for x in rep["session"]), rep["session"])

    def test_the_control_plane_only_archive_is_complete_at_pre_go(self):
        rep = json.loads((_S["runner"] / "control_plane_only/verify.json").read_text())
        self.assertTrue(rep["agree"], rep["session"]); self.assertEqual(rep["control_plane"]["phase"], "pre-go"); self.assertIsNone(rep["control_plane"]["stop"])
        self.assertNotIn(b"go 02000000\r", (_S["runner"] / "control_plane_only/raw/console_tx.bin").read_bytes())


class DeviceFormat(unittest.TestCase):
    """R4: the physical-source FORMAT validated offline on synthetic fixtures; provenance apart from consistency; downgrades found."""

    def test_a_synthetic_device_format_fixture_verifies_structurally_and_is_reported_as_such(self):
        out = Path(tempfile.mkdtemp(prefix="b4q_dev_")) / "valid"
        df.make(_S["runner"] / "valid", out)
        rep = vf.verify(out)
        self.assertTrue(rep["agree"], (rep.get("refused"), rep["session"]))
        self.assertEqual(rep["provenance"]["kind"], "uart-board"); self.assertFalse(rep["provenance"]["observed_on_device"]); self.assertFalse(rep["provenance"]["qualification"])
        self.assertIsNotNone(rep["provenance"]["synthetic"]); self.assertIn("SYNTHETIC", rep["provenance"]["standing"])
        self.assertEqual(rep["runner"]["findings"], [])
        self.assertTrue(rep["clean"])                                                                          # consistent — and the standing says what that is not

    def test_downgrades_of_a_pty_archive_into_the_device_format_are_found(self):
        for dg, needle in (("keep-banner", "surrogate's banner"), ("keep-backend", "emulated backend record"), ("keep-emulated", "labelled emulated"), ("keep-private", "private/ directory"), ("keep-fixture", "declares a host fixture")):
            out = Path(tempfile.mkdtemp(prefix="b4q_dev_")) / dg
            df.make(_S["runner"] / "valid", out, downgrade=dg)
            rep = vf.verify(out)
            self.assertTrue(any(needle in x for x in rep["session"]), (dg, rep["session"], rep.get("refused")))
        out = Path(tempfile.mkdtemp(prefix="b4q_dev_")) / "nm"
        df.make(_S["runner"] / "valid", out, downgrade="no-marker")
        rep = vf.verify(out)
        self.assertIsNone(rep["provenance"]["synthetic"]); self.assertIn("NOT established", rep["provenance"]["standing"])   # the device format without the marker: consistency only, never "observed"

    def test_a_relabelled_pty_archive_is_not_a_device_archive(self):
        d = Path(tempfile.mkdtemp(prefix="b4q_dev_")) / "relabel"
        shutil.copytree(_S["runner"] / "valid", d)
        m = json.loads((d / "manifest.json").read_text()); m["transport"]["kind"] = "uart-board"; m["transport"]["runner"]["kind"] = "uart-board"
        u = json.loads((d / "uboot.json").read_text()); u["kind"] = "uart-board"; (d / "uboot.json").write_text(json.dumps(u, indent=1) + "\n")
        (d / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
        rep = vf.verify(d)
        self.assertFalse(rep["agree"]); self.assertTrue(any("surrogate's banner" in x for x in rep["session"]) and any("labelled emulated" in x for x in rep["session"]), rep["session"])
