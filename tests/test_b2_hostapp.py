"""The REAL b2_app.c executed off-board (the discipline of B1's `test_b1_hostapp.py`).

`tb/b2/hostapp` compiles `firmware/b2/b2_app.c` itself against stub BSP headers, a fake
memory map and a scripted host, and runs `b2_session_init` / `b2_session_run` /
`b2_session_finish` — run_candidate, emit_record, the rel-v4 transactions, the TERM and the
restore-only cleanup are all the firmware's own code. The twin's session mode models an
unscored candidate by breaking out of its own loop; this harness makes the application take
its real SIGNREF branch.

The `startup_*` scenarios go further: they build a checksummed identity page in the fake
memory and call the application's REAL `main()`, so `establish_identity` runs and the ORDER
in which the pair slice is decoded relative to the IDENT is executed rather than skipped.
That order was wrong once — the slice was decoded in the session's init, so every identity
declared (0, 0, 0) and a host enforcing the binding could not start a valid session (the
owner's integration review of 2026-09-10, P2) — and these tests exist so it cannot recur.

Checked for every scenario: the epoch ends STOPPED with the named reason, exactly one
SIGNREQ and one TERM, the record count, that a refusal issues NO CTRL write, that the
orchestrator is not left claiming completion, and that every frame the application emitted
validates under the instrument's validator. The refusal is placed at the opening baseline,
at the first candidate of an arm, at a candidate that closes a generation, at a champion's
holdout evaluation, and at the closing baseline; a page whose pair slice is outside the
experiment, or that sets a reserved flags bit, is refused before anything is proposed.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import claimb_r1p_instrument as inst  # noqa: E402

HARNESS = R / "tb/b2/hostapp"
BIN = R / "build/hostapp_b2/hostapp"
HAVE_CC = shutil.which(os.environ.get("CC", "cc")) is not None
REFUSAL = "REFUSED_BY_GATE: an unscored candidate ends the epoch"
PAGE_REFUSAL = "STOP_PAGE: the identity page's pair slice is not inside the experiment"


def run(scenario: str) -> tuple[dict, list[dict]]:
    p = subprocess.run([str(BIN), scenario], capture_output=True, text=True, check=True)
    frames, result = [], None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            result = json.loads(line[len("RESULT "):])
        elif line.startswith("{"):
            frames.append(json.loads(line))
    assert result is not None, p.stdout[-500:]
    return result, frames


@unittest.skipUnless(HAVE_CC, "no host C compiler (CC): the harness cannot be built")
class HostApp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        p = subprocess.run(["bash", str(HARNESS / "build.sh")], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stdout + p.stderr)
        inst.bind(inst.DEFAULT_ROOT, require_git=False)
        import b1_records as br  # noqa: E402
        cls.br = br

    def _refusal(self, scenario: str, seq: int):
        result, frames = run(scenario)
        self.assertEqual(result["kind"], "STOPPED", scenario)
        self.assertEqual(result["reason"], REFUSAL, scenario)
        self.assertEqual(result["seq"], seq, scenario)
        self.assertEqual((result["signreq"], result["rec"], result["term"]), (1, 1, 1), scenario)
        self.assertEqual(result["last_rec_outcome"], "REFUSED_BY_GATE", scenario)
        self.assertEqual(result["ctrl_writes"], 0, "a refused candidate must not ARM")
        self.assertEqual(result["orch_complete"], 0, "a refused epoch is never complete")
        self.assertEqual(result["closing_baseline"], 0, scenario)
        self.assertEqual(result["closing_unsigned"], 0, "no closing control after a stop")
        self.assertEqual(result["closing_restore"], 1, "the restore-only cleanup must run")
        return result, frames

    def test_a_refusal_at_the_opening_baseline(self):
        self._refusal("opening", 1)

    def test_a_refusal_at_the_first_candidate_of_an_arm(self):
        self._refusal("probe", 2)

    def test_a_refusal_at_a_candidate_that_closes_a_generation(self):
        self._refusal("generation", 3)

    def test_a_refusal_at_a_champion_holdout_evaluation(self):
        self._refusal("holdout", 7)

    def test_a_refusal_at_the_closing_baseline(self):
        result, _ = self._refusal("closing", 8)
        self.assertEqual(result["scored"], 7, "the seven candidates before it were scored")

    def test_an_unacknowledged_record_stops_the_epoch(self):
        result, _ = run("ack_fail")
        self.assertEqual(result["kind"], "STOPPED")
        self.assertIn("STOP_REC", result["reason"])
        self.assertEqual(result["rec"], 3, "three attempts, then the stop")
        self.assertEqual(result["term"], 1)
        self.assertEqual(result["orch_complete"], 0)

    def test_a_page_outside_the_experiment_proposes_nothing(self):
        for scenario in ("bad_slice", "reserved_bit"):
            with self.subTest(scenario=scenario):
                result, _ = run(scenario)
                self.assertEqual(result["kind"], "STOPPED")
                self.assertEqual(result["reason"], PAGE_REFUSAL)
                self.assertEqual((result["signreq"], result["rec"]), (0, 0), "nothing was proposed")
                self.assertEqual(result["term"], 1, "the TERM is still sent")
                self.assertEqual(result["orch_phase"], 0)
                self.assertEqual(result["ctrl_writes"], 0)

    def test_the_state_a_scored_opening_baseline_leaves(self):
        result, _ = run("state_after_opening")
        self.assertEqual(result["kind"], "RUNNING")
        self.assertEqual(result["seq"], 1)
        self.assertEqual(result["scored"], 1)
        self.assertEqual(result["closing_baseline"], 0, "the opening baseline is not the closing one")
        self.assertEqual(result["orch_complete"], 0)
        self.assertEqual(result["have_last_reply"], 1)

    def test_the_state_a_scored_closing_baseline_leaves(self):
        result, _ = run("state_after_closing")
        self.assertEqual(result["kind"], "RUNNING")
        self.assertEqual(result["seq"], 8)
        self.assertEqual(result["scored"], 8)
        self.assertEqual(result["closing_baseline"], 1)
        self.assertEqual(result["orch_complete"], 1)

    def test_every_emitted_frame_validates(self):
        for scenario in ("opening", "probe", "generation", "holdout", "closing", "ack_fail", "bad_slice"):
            with self.subTest(scenario=scenario):
                _, frames = run(scenario)
                seen = set()
                for f in frames:
                    seen.add(f["frame"])
                    if f["payload"] is None:
                        continue
                    if f["frame"] in ("REC", "TERM", "IDENT"):
                        self.br.validate(f["payload"])
                self.assertIn("TERM", seen, scenario)

    # ------------------------------------------------------------ the real main()

    def _startup(self, scenario: str) -> dict:
        result, frames = run(scenario)
        idents = [f for f in frames if f["frame"] == "IDENT"]
        self.assertTrue(idents, "the application must emit an identity")
        return result

    def test_a_valid_slice_is_declared_and_the_session_starts(self):
        for scenario, slice_ in (("startup_valid", [9, 0, 4]), ("startup_later_slice", [9, 4, 4])):
            with self.subTest(scenario=scenario):
                r = self._startup(scenario)
                self.assertEqual(r["ident_slice"], slice_, "the identity must declare the page's slice")
                self.assertEqual(r["ident_slice_ok"], 1)
                self.assertEqual(r["ident_findings_empty"], 1, "a valid page yields a clean identity")
                self.assertEqual((r["ident"], r["identack"]), (1, 1), "one identity, acknowledged")
                self.assertEqual(r["signreq"], 1, "the session reached its first candidate")
                self.assertEqual(r["reason"], REFUSAL, "which the script deliberately refuses")

    def test_a_strict_host_can_start_the_session(self):
        """The host ACKs only an identity whose slice equals the page's."""
        r = self._startup("startup_strict")
        self.assertEqual(r["ident_slice"], [9, 4, 4])
        self.assertEqual((r["ident"], r["identack"]), (1, 1), "accepted on the first identity")
        self.assertEqual(r["signreq"], 1, "zero candidates would mean the binding blocked the session")
        self.assertEqual(r["kind"], "STOPPED")
        self.assertEqual(r["reason"], REFUSAL)

    def test_an_unacknowledged_identity_stops_before_any_candidate(self):
        r = self._startup("startup_no_ack")
        self.assertEqual(r["ident"], 3, "three attempts")
        self.assertEqual(r["identack"], 0)
        self.assertIn("STOP_IDENT", r["reason"])
        self.assertEqual((r["signreq"], r["rec"]), (0, 0))
        self.assertEqual(r["term"], 1)

    def test_an_invalid_page_is_reported_on_the_identity_and_proposes_nothing(self):
        for scenario in ("startup_bad_slice", "startup_reserved_bit"):
            with self.subTest(scenario=scenario):
                r = self._startup(scenario)
                self.assertEqual(r["ident_slice"], [0, 0, 0], "a refused slice is not invented")
                self.assertEqual(r["ident_findings_empty"], 0, "the refusal must be a finding on the identity")
                self.assertEqual((r["signreq"], r["rec"]), (0, 0), "nothing was proposed")
                self.assertEqual(r["term"], 1)
                self.assertEqual(r["kind"], "STOPPED")

    def test_the_startup_identities_validate(self):
        for scenario in ("startup_valid", "startup_strict", "startup_bad_slice", "startup_no_ack"):
            with self.subTest(scenario=scenario):
                _, frames = run(scenario)
                for f in frames:
                    if f["frame"] in ("IDENT", "REC", "TERM") and f["payload"] is not None:
                        self.br.validate(f["payload"])

    def test_the_refused_record_carries_no_search_block(self):
        _, frames = run("probe")
        recs = [f for f in frames if f["frame"] == "REC"]
        self.assertEqual(len(recs), 1)
        rec = recs[0]["payload"]
        self.assertEqual(rec["outcome"], "REFUSED_BY_GATE")
        self.assertNotIn("search", rec, "nothing was measured, so there is no search state to report")
        self.assertIn("sign_refusal", rec["evidence"])


if __name__ == "__main__":
    unittest.main()
