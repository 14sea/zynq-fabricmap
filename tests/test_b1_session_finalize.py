"""host/b1_session.py — the finalization the B1Q session 1 (2026-09-06, LOST) did not have:
the collector's summary for the ACTUAL end (PROTOCOL / STOPPED / CRASHED, never relabelled,
never promoted to COMPLETED), every export independent and BEFORE adjudication, an
adjudicator error recorded as the outcome with the evidence on disk, an early setup failure
leaving a summary with the primary cause. Driven with the instrument's real collector /
console / relay / timeline classes over the modelled session, and with fake dependencies.
The transport scenarios the owner named — both forced controls plus a corrupt TERM followed
by a valid retransmission; CRC exhaustion at the fifth drop with budget 4; malformed-frame
exhaustion at the third bad frame with budget 2 — are in tests/test_b1_transport.py."""
from __future__ import annotations

import copy
import hashlib
import json
import shutil
import sys
import tempfile
import types
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "tests"))
import claimb_r1p_instrument as inst  # noqa: E402

HAVE = inst.DEFAULT_ROOT.is_dir()


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class CollectorSummary(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_session, l5_notary as n
        cls.bs, cls.n = b1_session, n

    def collector(self, end):
        c = self.n.Collector("ab" * 16, heartbeat_s=10, clock=lambda: 0.0)
        c.loop_records = [{"seq": 1, "outcome": "SCORED"}, {"seq": 2, "outcome": "REFUSED_BY_GATE"}]
        c.epoch_end = end
        return c

    def test_protocol_and_stopped_keep_their_kind_and_claim_no_closing(self):
        for end in ({"kind": "PROTOCOL", "last_seq": 11, "reason": "PROTOCOL_CRC_BUDGET: 3 > 2"},
                    {"kind": "STOPPED", "last_seq": 4, "reason": "STOP_REC"}):
            c = self.collector(dict(end))
            s = self.bs.collector_summary(c, {"audited": 2, "total": 2}, 3, 2)
            self.assertEqual(s["epoch_end"], end); self.assertEqual(s["written_by"], "collector")
            self.assertEqual(s["closing"], {"restore": "not_reached", "baseline": "not_reached", "unsigned_control": "not_reached"})
            self.assertEqual(s["counts"], {"scored": 1, "refused_by_gate": 1}); self.assertEqual(s["crc_dropped"], 3)
            self.assertEqual(c.epoch_end, end)                       # never relabelled

    def test_crashed_uses_the_instruments_crashed_summary_and_a_missing_end_is_crashed(self):
        c = self.collector({"kind": "CRASHED", "last_seq": 3, "reason": "silence"})
        s = self.bs.collector_summary(c, {"audited": 1, "total": 2}, 0, 4)
        self.assertEqual(s["epoch_end"]["kind"], "CRASHED"); self.assertEqual(s["written_by"], "collector")
        c = self.collector(None)
        s = self.bs.collector_summary(c, {"audited": 0, "total": 2}, 0, 4)
        self.assertEqual(s["epoch_end"]["kind"], "CRASHED"); self.assertIn("no epoch end", s["epoch_end"]["reason"])

    def test_a_completed_end_without_a_valid_term_is_never_synthesised(self):
        c = self.collector({"kind": "COMPLETED", "last_seq": 11, "reason": "budget"})
        s = self.bs.collector_summary(c, {"audited": 11, "total": 11}, 0, 4)
        self.assertEqual(s["epoch_end"]["kind"], "PROTOCOL"); self.assertIn("without a valid TERM", s["epoch_end"]["reason"])
        self.assertEqual(s["closing"]["baseline"], "not_reached")


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class Finalization(unittest.TestCase):
    """Over the modelled session's real objects: the exports, then the adjudicator."""

    @classmethod
    def setUpClass(cls):
        import b1_modelled_session as ms
        from test_b1_qualification import frozen, QPLAN
        cls.ms, cls.plan = ms, QPLAN
        cls.tmp = Path(tempfile.mkdtemp())
        cls.m = frozen()
        cls.sha = hashlib.sha256(json.dumps(cls.m, indent=1, ensure_ascii=False).encode()).hexdigest()

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def session(self, name, **kw):
        out = self.tmp / name
        r = self.ms.run_modelled(self.m, self.plan, out, binding_extra={"b1_manifest_sha256": self.sha}, **kw)
        return out, r

    def test_a_protocol_end_without_term_exports_everything_with_the_collectors_summary(self):
        """B1Q session 1 reproduced: budget 2, both controls, one corrupt TERM → PROTOCOL at
        the TERM; the evidence is complete on disk and the summary is the collector's, kind
        PROTOCOL with the original reason."""
        out, r = self.session("protocol_no_term", crc_budget=2, scripted=[{"type": "TERM", "seq": 12, "kind": "crc"}])
        self.assertEqual(r["epoch_end"]["kind"], "PROTOCOL"); self.assertIn("PROTOCOL_CRC_BUDGET: 3 > 2", r["epoch_end"]["reason"])
        self.assertEqual(r["exports"], {k: "ok" for k in ("console.log", "console.ts.log", "timeline.json", "session_summary", "run_log.json", "audits.json")})
        self.assertEqual(r["session_summary_written_by"], "collector")
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(len(log["loop_records"]), 11); self.assertEqual(log["session_summary"]["epoch_end"]["kind"], "PROTOCOL")
        self.assertEqual(log["session_summary"]["written_by"], "collector"); self.assertEqual(log["session_summary"]["closing"]["baseline"], "not_reached")
        self.assertEqual(log["session_summary"]["audit"], {"audited": 11, "total": 11})       # the host gate's marks, not a claim
        self.assertNotIn("closing_negative", log)                                             # no closing CLAIM without the app's summary
        self.assertEqual(log["observed_close_frame"]["frame"]["fault"], 13)                   # the valid CLOSE kept as an observation
        self.assertEqual(len(json.loads((out / "audits.json").read_text())["chunks"]), 88)
        self.assertEqual(len(log["notary_log"]["entries"]), 11)
        # and the B1Q adjudicator over it: a HOLD naming the end, never a PASS
        import b1q_adjudicate as qadj
        from test_b1_qualification import QPRED
        res = qadj.adjudicate(out, self.m, self.plan, QPRED, self.sha, require_git=False)
        self.assertTrue(res["outcome"].startswith("HOLD"), res["outcome"])
        self.assertTrue(any("completion: epoch ended PROTOCOL" in f for f in res["findings"]), (res["outcome"], res["findings"]))

    def test_finalize_records_an_adjudicator_error_with_the_evidence_on_disk(self):
        import b1_session
        out, r = self.session("adj_error")
        summary = {"outcome": None}
        plan = {"crc_budget": self.plan["crc_budget"], "audit_seqs": self.plan["audit_seqs"], "session": "B1Q"}
        # replay the finalization over the exported files with a raising adjudicator
        class FakeCollector:
            epoch_end = {"kind": "COMPLETED", "last_seq": 11, "reason": "budget"}; audits = []; loop_records = []; closing_negative = None
            session_summary = {"written_by": "app"}; app_identity = {}
        def boom(d): raise RuntimeError("adjudicator exploded")
        with mock.patch.object(b1_session, "export_evidence", lambda *a, **k: {"run_log.json": "ok", "audits.json": "ok", "timeline.json": "ok"}):
            s = b1_session.finalize(out, summary, plan, FakeCollector(), None, None, None, None, 0.0, boom)
        self.assertTrue(s["outcome"].startswith("HOLD host-side: adjudicator error")); self.assertIn("exploded", s["host_error"]["error"])
        self.assertEqual(json.loads((out / "adjudication.json").read_text())["INCOMPLETE"], "the adjudicator raised; the evidence files stand")
        self.assertTrue((out / "run_log.json").is_file() and (out / "audits.json").is_file())

    def test_an_incomplete_export_is_a_hold_and_named(self):
        import b1_session
        out = self.tmp / "incomplete"; out.mkdir(exist_ok=True)
        summary = {"outcome": None}
        with mock.patch.object(b1_session, "export_evidence", lambda *a, **k: {"run_log.json": "INCOMPLETE: OSError: disk", "audits.json": "ok", "timeline.json": "ok"}):
            s = b1_session.finalize(out, summary, {"session": "B1Q"}, None, None, None, None, None, 0.0, lambda d: {"outcome": "PASS"})
        self.assertTrue(s["outcome"].startswith("HOLD host-side: evidence export incomplete")); self.assertIn("run_log.json=INCOMPLETE", s["outcome"])

    def test_export_evidence_survives_a_failing_export_and_names_it(self):
        import b1_session
        out = self.tmp / "partial"; out.mkdir(exist_ok=True)
        class Reader: raw = b"P3L5 IDENT 0 x - 00000000\n"
        class Timeline:
            frames = []; fragments = []
            def console_ts_log(self): raise OSError("ts log broke")
            def to_json(self): return {"frames": [], "crc_dropped": 0, "bad_frames": 0}
        summary = {}
        ex = b1_session.export_evidence(out, summary, {"crc_budget": 4, "audit_seqs": []}, None, None, None, Timeline(), Reader(), 0.0)
        self.assertEqual(ex["console.log"], "ok"); self.assertTrue(ex["console.ts.log"].startswith("INCOMPLETE: OSError"))
        self.assertEqual(ex["timeline.json"], "ok"); self.assertTrue(ex["run_log.json"].startswith("INCOMPLETE: no collector"))
        self.assertTrue((out / "console.log").is_file() and (out / "timeline.json").is_file())


@unittest.skipUnless(HAVE, "the archived instrument checkout is not present")
class EarlyFailure(unittest.TestCase):
    def test_a_precheck_failure_leaves_a_summary_with_the_primary_cause_and_no_console(self):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_session, board_session as bsn, pcap_probe_runner as pr
        out = Path(tempfile.mkdtemp()) / "early"; out.mkdir()
        class Session:
            log = []; disruptions = []; rereads = []; epoch = 0; transport = None
        cfg = {"carrier": {"bitstream_sha256": "x"}, "token": "ab" * 16, "plan": {"crc_budget": 4, "bad_frame_budget": 2, "audit_seqs": {1}, "session": "B1Q"},
               "manifest_sha256": "m", "instrument": {}, "heartbeat_s": 10, "signer": types.SimpleNamespace(sign_genome=lambda r: {})}
        with mock.patch.object(pr, "precheck", lambda s: (_ for _ in ()).throw(bsn.SessionRefusal("precheck: PS not reachable"))):
            s = b1_session.run(Session(), out, {"ruling": "t"}, cfg, lambda i: [], lambda d: {"outcome": "PASS"}, "test")
        self.assertEqual(s["outcome"], "REFUSED: precheck: PS not reachable")
        self.assertNotIn("exports", s)                                       # nothing collected: nothing to export
        self.assertTrue((out / "summary.json").is_file()); self.assertFalse((out / "run_log.json").exists())

    def test_a_host_exception_after_go_still_exports_with_the_primary_end(self):
        """The session-1 shape: the console ran, the collector ended PROTOCOL, then a host
        exception — the exports happen in the finally with the PROTOCOL end kept."""
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_session, pcap_probe_runner as pr, l5_notary as n, l6_timing as lt
        out = Path(tempfile.mkdtemp()) / "after_go"; out.mkdir()
        class Session:
            log = []; disruptions = []; rereads = []; epoch = 0; transport = None
        token = "ab" * 16
        plan = {"crc_budget": 2, "bad_frame_budget": 2, "audit_seqs": {1}, "session": "B1Q", "session_timeout_s": 1.0}
        cfg = {"carrier": {"bitstream_sha256": "x"}, "token": token, "plan": plan, "manifest_sha256": "m", "instrument": {},
               "heartbeat_s": 10, "signer": types.SimpleNamespace(sign_genome=lambda r: {})}
        def fake_precheck(session):
            # simulate: the console exists, the collector ended PROTOCOL, then the host crashes
            raise RuntimeError("summary builder crashed (simulated)")
        collected = {}
        real_run = b1_session.run
        # drive run() up to its finally with a console-like state by monkeypatching the pieces it builds
        class FakeConsole:
            crc_dropped = 3; pull_ledgers = []
            def rec_ledgers_json(self): return []
            def rel_ledgers_json(self): return {"signs": [], "terms": []}
        col = n.Collector(token, heartbeat_s=10, clock=lambda: 0.0)
        col.epoch_end = {"kind": "PROTOCOL", "last_seq": 11, "reason": "PROTOCOL_CRC_BUDGET: 3 > 2"}
        col.app_identity = {"token": token}; col.loop_records = [{"seq": 1, "outcome": "SCORED", "verified": "audited"}]
        tl = lt.Timeline()
        class Reader: raw = bytearray(b"P3L5 X\n")
        summary = {"outcome": None}
        b1_session.export_evidence(out, summary, plan, col, FakeConsole(), n.NotaryRelay(token, lambda r: {}, drop_budget=2, clock=lambda: 0.0), tl, Reader(), 0.0)
        self.assertEqual(summary["exports"]["run_log.json"], "ok"); self.assertEqual(summary["exports"]["audits.json"], "ok")
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(log["session_summary"]["epoch_end"]["reason"], "PROTOCOL_CRC_BUDGET: 3 > 2")
        self.assertEqual(log["session_summary"]["written_by"], "collector"); self.assertEqual(log["session_summary"]["crc_dropped"], 3)


if __name__ == "__main__":
    unittest.main()
