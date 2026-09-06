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

    # ---- the owner's review of v2.4 (2026-09-06): completeness and component isolation, over
    # REAL completed modelled-session objects and the REAL B1Q adjudicator
    def completed_objects(self, name):
        """A completed modelled B1Q session's live objects (collector, console, relay, timeline,
        reader) and the plan the exports take, for re-exporting with injected faults."""
        import b1_adjudicate as adj
        cands = self.ms.Candidates(self.ms.bind_instrument(False), self.plan, self.m, self.ms.bm.fixture("truth"),
                                   "a13f38b53355fd4c1cac3145244727f8", self.tmp / "K.bin") if False else None
        # simplest: run the session and keep its B1Session
        M = self.ms.bind_instrument(False)
        key = self.tmp / "K.bin"
        if not key.is_file():
            key.write_bytes(bytes(range(16))); key.chmod(0o400)
        token = "a13f38b53355fd4c1cac3145244727f8"
        cands = self.ms.Candidates(M, self.plan, self.m, self.ms.bm.fixture("truth"), token, key)
        import b1_runner
        s = self.ms.B1Session(M, cands, self.plan, self.m, token, identity_check=b1_runner.identity_check_for(self.plan, self.m))
        s.run()
        self.assertEqual(s.collector.epoch_end["kind"], "COMPLETED")
        session_plan = {**{k: self.plan[k] for k in ("session", "master_seed", "budget", "audit_seqs", "crc_budget", "bad_frame_budget",
                                                     "session_timeout_s", "flags", "protocol")}, "n": self.plan["budget"],
                        "binding": {"image_sha256": self.m["image"]["sha256"], "prereg_sha256": self.m["prereg"]["sha256"], "protocol": "rel-v4",
                                    "session": "B1Q", "schedule_mode": "carto-v1", "master_seed": self.plan["master_seed"],
                                    "psoracle_commit": self.m["instrument"]["psoracle_commit"], "b1_manifest_sha256": self.sha},
                        "inputs": adj.expected_inputs(self.m, "B1Q")}
        return s, session_plan

    def finalize_with(self, name, s, session_plan, adjudicator=None):
        import b1_session, b1q_adjudicate as qadj
        from test_b1_qualification import QPRED
        out = self.tmp / name; out.mkdir(exist_ok=True)
        judge = adjudicator or (lambda d: qadj.adjudicate(d, self.m, self.plan, QPRED, self.sha, require_git=False))
        summary = {"outcome": None}
        b1_session.finalize(out, summary, session_plan, s.collector, s.cs, s.relay, s.timeline, s.reader, s.t_go, judge)
        return out, summary

    def test_completed_objects_finalize_to_pass_through_the_real_adjudicator(self):
        s, plan = self.completed_objects("base")
        out, summary = self.finalize_with("complete", s, plan)
        self.assertEqual(summary["outcome"], "PASS", summary.get("outcome")); self.assertTrue(json.loads((out / "exports.json").read_text())["complete"])

    def test_a_failed_raw_console_export_is_a_hold_and_the_adjudicator_refuses(self):
        """The owner's counter-example: an OSError injected only into console.log's write."""
        import b1_session, b1q_adjudicate as qadj
        from test_b1_qualification import QPRED
        s, plan = self.completed_objects("console")
        for name in ("console.log", "console.ts.log"):
            out = self.tmp / f"fail_{name}"; out.mkdir(exist_ok=True)
            summary = {"outcome": None}
            real_write = Path.write_bytes
            def failing_write(self_, data, _n=name):
                if self_.name == _n:
                    raise OSError(f"injected {_n} write failure")
                return real_write(self_, data)
            with mock.patch.object(Path, "write_bytes", failing_write):
                b1_session.finalize(out, summary, plan, s.collector, s.cs, s.relay, s.timeline, s.reader, s.t_go,
                                    lambda d: qadj.adjudicate(d, self.m, self.plan, QPRED, self.sha, require_git=False))
            self.assertTrue(summary["outcome"].startswith("HOLD host-side: evidence export incomplete"), summary["outcome"])
            self.assertIn(f"{name}=INCOMPLETE", summary["outcome"]); self.assertFalse((out / name).exists())
            self.assertFalse((out / "adjudication.json").exists())                          # the adjudicator was not consulted
            ex = json.loads((out / "exports.json").read_text()); self.assertFalse(ex["complete"])
            # and the adjudicator, asked directly over that directory, refuses
            res = qadj.adjudicate(out, self.m, self.plan, QPRED, self.sha, require_git=False)
            self.assertTrue(res["outcome"].startswith("REFUSED"), res["outcome"]); self.assertIn("exports incomplete", res["outcome"])

    def test_a_missing_export_status_key_is_incomplete(self):
        import b1_session
        s, plan = self.completed_objects("keys")
        out = self.tmp / "missing_key"; out.mkdir(exist_ok=True)
        summary = {"outcome": None}
        real = b1_session.export_evidence
        def dropping(*a, **k):
            ex = real(*a, **k); ex.pop("session_summary"); return ex
        with mock.patch.object(b1_session, "export_evidence", dropping):
            b1_session.finalize(out, summary, plan, s.collector, s.cs, s.relay, s.timeline, s.reader, s.t_go, lambda d: {"outcome": "PASS"})
        self.assertTrue(summary["outcome"].startswith("HOLD host-side: evidence export incomplete")); self.assertIn("session_summary=INCOMPLETE: not attempted", summary["outcome"])

    def test_each_enrichment_failure_keeps_the_base_data_and_is_a_partial_hold(self):
        """Timing, the notary rendering, each ledger renderer, the summary construction: the
        records / chunks are on disk, the missing component is marked, the export is PARTIAL,
        the outcome a HOLD, the adjudicator refuses."""
        import b1_session, b1q_adjudicate as qadj, l6_timing as lt
        from test_b1_qualification import QPRED
        s, plan = self.completed_objects("components")
        cases = [
            ("timing", lambda: mock.patch.object(lt, "record_timing", side_effect=RuntimeError("timing broke")), "run_log.json", "timing"),
            ("notary", lambda: mock.patch.object(s.relay, "notary_log", side_effect=RuntimeError("notary broke")), "run_log.json", "notary_log"),
            ("recs", lambda: mock.patch.object(s.cs, "rec_ledgers_json", side_effect=RuntimeError("recs broke")), "audits.json", "recs"),
            ("rel", lambda: mock.patch.object(s.cs, "rel_ledgers_json", side_effect=RuntimeError("rel broke")), "audits.json", "rel"),
            ("pulls", lambda: mock.patch.object(type(s.cs), "pull_ledgers", new_callable=mock.PropertyMock, side_effect=RuntimeError("pulls broke")), "audits.json", "pulls"),
        ]
        for name, patcher, file, comp in cases:
            out = self.tmp / f"comp_{name}"; out.mkdir(exist_ok=True)
            summary = {"outcome": None}
            with patcher():
                b1_session.finalize(out, summary, plan, s.collector, s.cs, s.relay, s.timeline, s.reader, s.t_go,
                                    lambda d: qadj.adjudicate(d, self.m, self.plan, QPRED, self.sha, require_git=False))
            self.assertTrue(summary["outcome"].startswith("HOLD host-side: evidence export incomplete"), (name, summary["outcome"]))
            self.assertIn(f"{file}=PARTIAL", summary["outcome"], name); self.assertIn(comp, summary["outcome"], name)
            doc = json.loads((out / file).read_text())
            if file == "run_log.json":
                self.assertEqual(len(doc["loop_records"]), 11); self.assertEqual(doc["session_summary"]["epoch_end"]["kind"], "COMPLETED")
                self.assertIn("INCOMPLETE", doc[comp])
                if comp == "timing":
                    self.assertEqual(len(doc["notary_log"]["entries"]), 11)
            else:
                self.assertEqual(len(doc["chunks"]), 88); self.assertIn("INCOMPLETE", doc[comp] if comp != "rel" else doc["rel"])
            self.assertIn(comp, " ".join(doc["INCOMPLETE"]))
            res = qadj.adjudicate(out, self.m, self.plan, QPRED, self.sha, require_git=False)
            self.assertTrue(res["outcome"].startswith("REFUSED"), (name, res["outcome"]))
        # the summary construction itself
        s2, plan2 = self.completed_objects("summary")
        s2.collector.session_summary = None
        out = self.tmp / "comp_summary"; out.mkdir(exist_ok=True); summary = {"outcome": None}
        with mock.patch.object(b1_session, "collector_summary", side_effect=RuntimeError("summary broke")):
            b1_session.finalize(out, summary, plan2, s2.collector, s2.cs, s2.relay, s2.timeline, s2.reader, s2.t_go, lambda d: {"outcome": "PASS"})
        self.assertTrue(summary["outcome"].startswith("HOLD host-side: evidence export incomplete")); self.assertIn("session_summary=INCOMPLETE", summary["outcome"])
        doc = json.loads((out / "run_log.json").read_text())
        self.assertEqual(len(doc["loop_records"]), 11); self.assertIsNone(doc["session_summary"]); self.assertTrue(any("session_summary" in x for x in doc["INCOMPLETE"]))

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
        with mock.patch.object(b1_session, "export_evidence", lambda *a, **k: {k: "ok" for k in b1_session.REQUIRED_EXPORTS}):
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

    def _fake_board(self, tmp: Path):
        """The dependencies b1_session.run needs to reach the console: a session whose
        preamble succeeds (identity, dcache, clock, carrier, provisioning, page, image, go)
        against a transport that never speaks, plus the plan and cfg the runner builds."""
        import types
        class Serial:
            in_waiting = 0
            def __init__(self): self.written = []
            def read(self, n): return b""
            def write(self, b): self.written.append(b); return len(b)
        class Transport:
            def __init__(self): self._serial = Serial()
        page = [0] * 24
        class Session:
            log = []; disruptions = []; rereads = []; epoch = 0
            def __init__(self): self.transport = Transport()
            def verify_identity(self): return {"idcode": "0x13722093"}
            def read_word(self, addr): return 0x1F000200
            def load_carrier(self, cap, bit, sha, log): return {"sha256": sha}
            def command(self, s): return ""
            def read_words(self, addr, n): return list(page)
            def begin_ymodem(self, addr): pass
            def finish_ymodem(self, path, log, size): pass
        image = tmp / "image.bin"; image.write_bytes(b"\0" * 64)
        pk = tmp / "p3k.json"; pk.write_text("{}")
        plan = {"session": "B1Q", "mode": "carto-v1", "master_seed": 1, "n": 9, "audit_seqs": {1}, "crc_budget": 4, "bad_frame_budget": 2,
                "session_timeout_s": 5.0, "flags": 0x32, "protocol": "rel-v4"}
        cfg = {"carrier": {"bitstream_sha256": "c" * 64}, "token": "ab" * 16, "plan": plan, "manifest_sha256": "m", "instrument": {},
               "heartbeat_s": 10, "signer": types.SimpleNamespace(sign_genome=lambda r: {}, provision=lambda **k: {"rc": 0}),
               "bitstream": tmp / "b.bit", "image": image, "image_sha256": "i" * 64, "provision_execute": False, "provision_ruling": pk}
        return Session(), plan, cfg, page

    def _run_with(self, tmp: Path, session, cfg, page, loop_behaviour):
        """b1_session.run with the instrument's preamble helpers patched to succeed and the
        console loop replaced by `loop_behaviour` (raise, or end)."""
        import b1_session, board_session as bsn, l3_runner as l3, l5_runner as l5, l6_runner as l6, p2_observe as ob, pcap_probe_runner as pr
        class Plane:
            def __init__(self, s): pass
            def read(self, off): return (1 << 11) if off == 0x2004 else 0
        out = tmp / "out"; out.mkdir(exist_ok=True)
        with mock.patch.object(pr, "precheck", lambda s: {"ok": True}), mock.patch.object(l3, "ensure_dcache_off", lambda s: "off"), \
             mock.patch.object(l3, "Plane", Plane), mock.patch.object(ob, "fclk0_mhz", lambda *a: {"mhz": 50.0, "ok": True}), \
             mock.patch.object(l5, "build_page", lambda *a: list(page)), mock.patch.object(l6, "session_loop_continues", loop_behaviour):
            s = b1_session.run(session, out, {"ruling": "t"}, cfg, lambda i: [], lambda d: {"outcome": "PASS", "findings": []}, "test")
        return out, s

    def test_a_host_exception_at_the_console_exports_what_exists_and_keeps_the_primary_cause(self):
        """The REAL run(): the preamble succeeds against a fake board, the console exists,
        then a host exception is raised inside the console loop — the finally exports the
        collected evidence (empty records, the raw console, the timeline, the collector's
        summary for the actual end), the summary carries the host error beside the primary
        end, no success outcome, summary.json persisted."""
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        tmp = Path(tempfile.mkdtemp())
        session, plan, cfg, page = self._fake_board(tmp)
        def boom(*a, **k):
            raise RuntimeError("console loop exploded (simulated)")
        out, s = self._run_with(tmp, session, cfg, page, boom)
        self.assertEqual(s["outcome"], "CRASHED host-side: RuntimeError: console loop exploded (simulated)")
        self.assertEqual(s["host_error"]["where"], "session"); self.assertIn("exploded", s["host_error"]["error"])
        self.assertIn("exports", s)
        for name in ("console.log", "console.ts.log", "timeline.json", "run_log.json", "audits.json", "exports.json", "summary.json"):
            self.assertTrue((out / name).is_file(), name)
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(log["session_summary"]["written_by"], "collector")
        self.assertEqual(log["session_summary"]["epoch_end"]["kind"], "CRASHED")          # the collector saw no end: CRASHED, said so
        self.assertEqual(s["epoch_end"]["kind"], "CRASHED"); self.assertIn("no epoch end", s["epoch_end"]["reason"])
        self.assertFalse((out / "adjudication.json").exists())
        self.assertEqual(json.loads((out / "summary.json").read_text())["outcome"], s["outcome"])

    def test_a_protocol_end_seen_by_the_console_then_a_host_exception_keeps_the_protocol_cause(self):
        """The session-1 shape through the REAL run(): the collector ended PROTOCOL, then the
        host raised — the exported summary is the collector's PROTOCOL one, the host error is
        secondary, nothing says COMPLETED."""
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        tmp = Path(tempfile.mkdtemp())
        session, plan, cfg, page = self._fake_board(tmp)
        def end_then_boom(collector, console, now, deadline):
            collector.epoch_end = {"kind": "PROTOCOL", "last_seq": 11, "reason": "PROTOCOL_CRC_BUDGET: 3 > 2"}
            raise RuntimeError("summary builder crashed (simulated)")
        out, s = self._run_with(tmp, session, cfg, page, end_then_boom)
        self.assertTrue(s["outcome"].startswith("CRASHED host-side")); self.assertEqual(s["epoch_end"]["reason"], "PROTOCOL_CRC_BUDGET: 3 > 2")
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(log["session_summary"]["epoch_end"], {"kind": "PROTOCOL", "last_seq": 11, "reason": "PROTOCOL_CRC_BUDGET: 3 > 2"})
        self.assertEqual(log["session_summary"]["written_by"], "collector"); self.assertEqual(log["session_summary"]["closing"]["baseline"], "not_reached")
        self.assertEqual(s["exports"]["run_log.json"], "ok"); self.assertEqual(s["exports"]["audits.json"], "ok")

    def test_a_console_loop_that_ends_without_an_epoch_end_finalizes_as_crashed(self):
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        tmp = Path(tempfile.mkdtemp())
        session, plan, cfg, page = self._fake_board(tmp)
        out, s = self._run_with(tmp, session, cfg, page, lambda *a: False)
        self.assertEqual(s["epoch_end"]["kind"], "CRASHED"); self.assertIn("bound elapsed", s["epoch_end"]["reason"])
        self.assertTrue((out / "exports.json").is_file()); self.assertTrue(json.loads((out / "exports.json").read_text())["complete"])
        log = json.loads((out / "run_log.json").read_text())
        self.assertEqual(log["session_summary"]["epoch_end"]["kind"], "CRASHED"); self.assertEqual(log["session_summary"]["written_by"], "collector")
        self.assertTrue((out / "adjudication.json").is_file())          # a complete export IS adjudicated (the fake judge here says PASS;
        # the real adjudicators hold a CRASHED end on its findings — tests/test_b1_transport.py, test_b1_adjudicate.py)


if __name__ == "__main__":
    unittest.main()
