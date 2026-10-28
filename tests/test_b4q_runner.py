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
        self.assertIn("uart-board", vf.verify(d)["refused"])
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
        self.assertEqual(m["transport"]["kind"], "console-pty-surrogate"); self.assertEqual(m["source"]["kind"], el.SOURCE_KIND)
        self.assertIsNone(m["backend"])                                   # no backend in the runner's process: nothing to read a board fact from
        self.assertTrue(m["emulated"])
        u = json.loads((_S["runner"] / "valid/uboot.json").read_text())
        whats = [st["what"] for st in u["uboot_steps"]]
        self.assertEqual(whats[:2], ["prompt", "loady"]); self.assertIn("crc32", whats); self.assertIn("go", whats)
        self.assertEqual(u["load_witness"]["host_crc32"], u["load_witness"]["uboot_crc32"])
        self.assertEqual(whats.count("mw.l"), w.PAGE_WORDS)
        rep = json.loads((_S["runner"] / "valid/verify.json").read_text())
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
            s = _S["runner_summary"][name]
            self.assertFalse(s["opened"]); self.assertTrue(s["stop"]["why"], name)
            if (d / "verify.json").is_file():
                rep = json.loads((d / "verify.json").read_text())
                self.assertTrue(rep["agree"] and rep.get("control_plane_stop"), (name, rep.get("refused"), rep.get("session")))

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
    def test_the_runner_reads_no_backend_and_no_private_material(self):
        src = (R / "host/b4q_runner.py").read_text()
        self.assertNotIn(".trace", src.replace("self.evidence.trace", "").replace("evidence.trace", ""))
        self.assertNotIn("pcap_log", src.replace("self.evidence.pcap_log", "").replace("evidence.pcap_log", ""))
        self.assertNotIn("private", src.lower())
        self.assertIn("self.backend = None", src)
        sur = (R / "host/b4q_device_surrogate.py").read_text()
        self.assertIn("--private-dir", sur)


if __name__ == "__main__":
    unittest.main()
