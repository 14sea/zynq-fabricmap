"""The REAL b1_app.c on the host (tb/b1/hostapp): the compatibility review of 2026-09-05
found that the application's SIGNREF branch continued the session (the P3 behaviour) and
that the twin's UNSCORED model — a break in the twin's own loop — could never see it.
These tests compile firmware/b1/b1_app.c itself against stub BSP headers and drive
b1_session_init / run / finish with a scripted host: the opening baseline, a probe after a
scored baseline, and the closing baseline each receive SIGNREF; a REFUSED_BY_GATE record
whose RECACK never comes. Every scenario must end the epoch: one SIGNREQ only, exactly the
record, no ARM (no CTRL write), no closing baseline, no closing control, the restore-only
cleanup, a STOPPED TERM — and the REC / TERM payloads must validate under the instrument's
schemas. A source audit additionally requires every non-SCORED record emission in
b1_app.c to be followed by the stop."""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

HAVE_CC = shutil.which("cc") is not None
HAVE_INST = inst.DEFAULT_ROOT.is_dir()


class HostApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not HAVE_CC:
            raise unittest.SkipTest("no host C compiler")
        cls.tmp = Path(tempfile.mkdtemp())
        p = subprocess.run(["bash", str(R / "tb/b1/hostapp/build.sh"), str(cls.tmp)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
        cls.exe = cls.tmp / "hostapp"

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def run_scenario(self, name: str) -> tuple[dict, list[dict]]:
        p = subprocess.run([str(self.exe), name], capture_output=True, text=True, timeout=600)
        self.assertEqual(p.returncode, 0, p.stderr[-1000:])
        frames, result = [], None
        for line in p.stdout.splitlines():
            if line.startswith("RESULT "):
                result = json.loads(line[7:])
            elif line.startswith("{"):
                frames.append(json.loads(line))
        self.assertIsNotNone(result, p.stdout[-2000:])
        return result, frames

    def assert_epoch_ended(self, r: dict, frames: list[dict], refused_seq: int, rec_transmissions: int = 1):
        self.assertEqual(r["kind"], "STOPPED", r)
        self.assertEqual(r["seq"], refused_seq)
        self.assertEqual(r["signreq"], 1, "a second SIGNREQ = the session went on after the refusal")
        self.assertEqual(r["rec"], rec_transmissions)
        self.assertEqual(r["last_rec_outcome"], "REFUSED_BY_GATE")
        self.assertEqual(r["ctrl_writes"], 0, "an ARM strobe after an unscored candidate")
        self.assertEqual(r["payload_writes"], 0)
        self.assertEqual((r["closing_baseline"], r["closing_unsigned"]), (0, 0))
        self.assertEqual(r["closing_restore"], 1)            # the restore-only cleanup ran (3 envelope DMAs)
        self.assertEqual(r["dma"], 3)
        self.assertEqual(r["refused"], 1)
        self.assertEqual(r["term"], 1)
        types = [f["frame"] for f in frames]
        self.assertEqual(types.count("SIGNREQ"), 1); self.assertEqual(types[-1], "TERM")
        self.assertTrue(all(f["seq"] == refused_seq for f in frames if f["frame"] in ("SIGNREQ", "REC")))
        term = frames[-1]["payload"]
        self.assertEqual(term["epoch_end"]["kind"], "STOPPED")
        self.assertEqual(term["closing"], {"restore": "done", "baseline": "not_reached", "unsigned_control": "not_reached"})
        self.assertEqual(term["counts"]["refused_by_gate"], 1)
        return term

    def validate(self, frames: list[dict]) -> None:
        if not HAVE_INST:
            return
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as records
        for f in frames:
            if f["frame"] in ("REC", "TERM"):
                records.validate(f["payload"])                     # schema + record rules of the instrument

    def test_opening_baseline_refused_ends_the_epoch(self):
        r, frames = self.run_scenario("opening")
        self.assert_epoch_ended(r, frames, 1)
        self.assertIn("REFUSED_BY_GATE", r["reason"]); self.assertEqual(r["scored"], 0)
        self.validate(frames)

    def test_a_probe_refused_after_a_scored_baseline_ends_the_epoch(self):
        r, frames = self.run_scenario("probe")
        self.assert_epoch_ended(r, frames, 2)
        self.assertEqual(r["scored"], 1)
        rec = next(f for f in frames if f["frame"] == "REC")["payload"]
        self.assertEqual(rec["outcome"], "REFUSED_BY_GATE"); self.assertEqual(rec["seq"], 2)
        self.validate(frames)

    def test_the_closing_baseline_refused_ends_the_epoch_without_the_closing_control(self):
        r, frames = self.run_scenario("closing")
        self.assertGreater(r["seq"], 2)
        self.assert_epoch_ended(r, frames, r["seq"])
        self.assertEqual(r["orch_step"], 3)                      # the closing baseline WAS proposed, and refused
        rec = next(f for f in frames if f["frame"] == "REC")["payload"]
        self.assertEqual(rec["seq"], r["seq"])
        self.validate(frames)

    def test_the_closing_baseline_mark_is_set_by_the_closing_baseline_only(self):
        """The owner's recheck of v2.3: the first version set S.closing_baseline at ANY scored
        baseline, so a refused probe's TERM claimed a closing baseline that never happened;
        the harness's priming had omitted that side effect. The priming now calls the
        application's own note_scored, and the mark is asserted both ways."""
        r, _ = self.run_scenario("state_after_opening")
        self.assertEqual((r["scored"], r["closing_baseline"], r["have_last_reply"], r["orch_step"]), (1, 0, 1, 1))
        r, _ = self.run_scenario("state_after_closing")
        self.assertEqual((r["closing_baseline"], r["orch_step"]), (1, 3)); self.assertGreater(r["scored"], 2)
        # and through the real loop: a refusal after the opening baseline leaves it not_reached
        for name in ("probe", "closing"):
            r, frames = self.run_scenario(name)
            self.assertEqual(r["closing_baseline"], 0, name)
            self.assertEqual(frames[-1]["payload"]["closing"]["baseline"], "not_reached", name)

    def test_an_unacknowledged_refusal_record_stops_after_three_attempts(self):
        r, frames = self.run_scenario("ack_fail")
        self.assert_epoch_ended(r, frames, 1, rec_transmissions=3)
        self.assertIn("STOP_REC", r["reason"]); self.assertEqual(r["rec_attempts"], 3)
        self.validate(frames)


class SourceAudit(unittest.TestCase):
    def test_every_non_scored_record_emission_is_followed_by_the_stop(self):
        src = (R / "firmware/b1/b1_app.c").read_text().splitlines()
        seen = []
        for i, line in enumerate(src):
            m = re.search(r'emit_record\(&rec, "([A-Z_0-9]+)"\)', line)
            if not m or m.group(1) == "SCORED":
                continue
            window = "\n".join(src[max(0, i - 4):i + 8])   # the stop may precede the emission (a stop path) or follow it
            self.assertTrue("p3_stop(P3_STOPPED" in window or "p3_stop(P3_PROTOCOL" in window, (m.group(1), window))
            self.assertIn("return -1", window, m.group(1))
            seen.append(m.group(1))
        self.assertEqual(sorted(seen), ["REFUSED_BY_GATE", "REFUSED_BY_PL", "STOP_ARM", "STOP_AUDIT", "STOP_AXI", "STOP_LINK2", "STOP_LINK3",
                                        "STOP_SETTLE", "STOP_SIGN"])

    def test_the_scored_bookkeeping_lives_in_note_scored_and_marks_the_closing_baseline_only_at_done(self):
        src = (R / "firmware/b1/b1_app.c").read_text()
        self.assertIn("if (is_baseline && O.step == B1_STEP_DONE)\n        S.closing_baseline = 1;", src)
        self.assertEqual(src.count("S.closing_baseline = 1"), 1)
        self.assertEqual(src.count("S.scored++"), 2)                 # note_scored, and the unacknowledged-SCORED stop path
        self.assertIn("note_scored(is_baseline, commit, (const char(*)[17])tables);", src)

    def test_main_runs_the_three_named_session_steps(self):
        src = (R / "firmware/b1/b1_app.c").read_text()
        body = src[src.index("int main(void)"):]
        self.assertTrue(body.index("b1_session_init();") < body.index("b1_session_run();") < body.index("b1_session_finish();"))


if __name__ == "__main__":
    unittest.main()
