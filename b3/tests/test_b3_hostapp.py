"""The REAL b3/firmware/b3_app.c executed off-board (B3 lifecycle 2, image stage 6; the discipline of B2's
tests/test_b2_hostapp.py; the owner's rulings of 2026-10-12 on the stage-6 scope).

`b3/tb/hostapp` compiles b3_app.c itself — with the image's compile branch (-DB3_EMIT_SHA) and the units the image
links — against stub BSP headers, a fake memory map, a scripted host and a MINIMAL fake of the PL and the DevC DMA
(see hostapp.c): the fabric is the additive truth model over the genome the host signed, the PCAP keeps the frames
a WRITE_ENVELOPE carries and reads them back, and every DMA submission records its four registers, its phase
(CANDIDATE while the epoch runs, AFTER_STOP once it has stopped) and the candidate's seq. Nothing is primed: every
candidate before the one a test is about runs the application's whole path.

  * THE WHOLE PAIR: the application's real main() — identity, the three arms of pair 2 (1 000 evaluations each),
    the three champions' holdouts, both baselines, the closing unsigned control — ends COMPLETED, and the run log
    passes `b3_records.validate_run_log` WITH the instrument's common contract: no finding (every O-arm ledger entry
    is held to the prediction field by field). The search-block rules are checked record by record.
  * REFUSALS at the opening baseline, the first candidate of each arm, a candidate that closes a generation, the
    first champion holdout and the closing baseline; an unacknowledged record; pages that propose nothing; the
    startup identity. Every record validates incrementally; the refused record carries no search block.
  * F-WIN FAULT INJECTION (the owner's ruling: a simulation, NEVER evidence that the hardware stopped a DMA): a
    status that never completes, each bit of INT_STS_ERROR_MASK in turn, completion on the last allowed poll and on the first poll past it,
    DMA_DONE without D_P_DONE, data written after the stop, D_P_DONE before the data lands, a device that stays
    stuck, and a pending transfer's late completion arriving during the cleanup. In each: after the fault no
    candidate is proposed and no candidate DMA or ARM follows; the restore-only cleanup's DMAs are counted APART
    (b3_session_finish queues them — they are neither omitted nor counted as the candidate continuing); late data is
    never reported as a SCORED result; the TERM keeps the stop's reason.

No skip: a missing compiler or a failed build is a FAILURE. The compiler's path, version line and command are in
build/hostapp_b3/build.json; each scenario's measured wall time is written to build/hostapp_b3/timings.json. Every
scenario runs under a timeout; the firmware's poll limits are the image's own (DMA_SPIN_LIMIT = 1 000 000).
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b3_records as brec  # noqa: E402
import claimb_r1p_instrument as inst  # noqa: E402

HARNESS = R / "b3/tb/hostapp"
OUT = R / "build/hostapp_b3"
BIN = OUT / "hostapp"
FABRIC = OUT / "fabric_truth.txt"
PLAN = json.loads((R / "evidence/b3/plan.json").read_text())
PRED = json.loads((R / "evidence/b3/prediction.json").read_text())
PAIR = 2                                    # its frozen arm order is O, R, F: the O arm's first search is seq 2
SCENARIO_TIMEOUT_S = 300
SPIN_LIMIT = 1_000_000                      # b3_app.c DMA_SPIN_LIMIT: devcfg_wait_done reads INT_STS at most this often
REFUSAL = "REFUSED_BY_GATE: an unscored candidate ends the epoch"
TIMEOUT = "DEVCFG D_P_DONE never asserted"
ERROR_MASK = int(re.search(r"#define INT_STS_ERROR_MASK (0x[0-9A-Fa-f]+)u", (R / "b3/firmware/b3_app.c").read_text()).group(1), 16)
ERROR_BITS = [b for b in range(32) if ERROR_MASK >> b & 1]
SENTINEL = "a5a5a5a5"                       # b3_app.c P3_SENTINEL: readback_frame's prefill of DST_BUF
TIMINGS: dict[str, float] = {}
_STATE: dict = {}


def setUpModule():
    p = subprocess.run(["bash", str(HARNESS / "build.sh"), str(OUT)], capture_output=True, text=True)
    if p.returncode != 0:
        raise AssertionError(f"the host harness did not build (a failure, never a skip):\n{p.stdout}{p.stderr}")
    _STATE["build_log"] = p.stdout + p.stderr
    truth = bm.truth_mapping()["mapping"]
    FABRIC.write_text("".join(f"{i} {truth[i][0]} {truth[i][1]}\n" if truth.get(i) is not None else f"{i} -\n"
                              for i in range(bc.N)))
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    import b1_records as br  # noqa: E402  (needs the bound instrument package)
    _STATE["br"] = br


def tearDownModule():
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "timings.json").write_text(json.dumps(dict(sorted(TIMINGS.items())), indent=1) + "\n")
    sys.stderr.write(f"\nhostapp scenarios: {len(TIMINGS)}, {sum(TIMINGS.values()):.1f} s in all, "
                     f"slowest {max(TIMINGS.values(), default=0):.2f} s (build/hostapp_b3/timings.json)\n")


class Run:
    def __init__(self, result: dict, frames: list[dict], dmas: list[dict]):
        self.result, self.frames, self.dmas = result, frames, dmas

    def payloads(self, kind: str) -> list[dict]:
        return [f["payload"] for f in self.frames if f["frame"] == kind and f["payload"] is not None]

    @property
    def records(self) -> list[dict]:
        return self.payloads("REC")

    @property
    def term(self) -> dict:
        (t,) = self.payloads("TERM")
        return t


def run(mode: str, name: str, **kw) -> Run:
    args = [str(BIN), mode, str(FABRIC)] + [f"{k}={v}" for k, v in kw.items()]
    t0 = time.monotonic()
    p = subprocess.run(args, capture_output=True, text=True, timeout=SCENARIO_TIMEOUT_S)
    TIMINGS[name] = round(time.monotonic() - t0, 3)
    if p.returncode != 0:
        raise AssertionError(f"{name}: the harness exited {p.returncode}: {p.stderr[-800:]}")
    frames, dmas, result = [], [], None
    for line in p.stdout.splitlines():
        if line.startswith("RESULT "):
            result = json.loads(line[len("RESULT "):])
        elif line.startswith('{"frame"'):
            frames.append(json.loads(line))
        elif line.startswith('{"dma"'):
            dmas.append(json.loads(line))
    if result is None:
        raise AssertionError(f"{name}: no RESULT line: {p.stdout[-500:]}")
    return Run(result, frames, dmas)


def session(name: str, **kw) -> Run:
    kw.setdefault("first", PAIR)
    kw.setdefault("count", 1)
    return run("session", name, **kw)


def findings(r: Run, first: int = PAIR, count: int = 1) -> list[str]:
    """Every document the application emitted, through the instrument's common contract, and every record through
    the B3 rules in seq order with one running state (a stopped session's missing tail is not a finding here)."""
    br = _STATE["br"]
    ctx = brec.context_from(PLAN, PRED, first, count)
    order = brec.expected_order(ctx)
    out: list[str] = []
    for kind in ("IDENT", "REC", "TERM"):
        for doc in r.payloads(kind):
            try:
                br.validate(doc)
            except Exception as exc:                        # the instrument's own refusal
                out.append(f"common {kind} {doc.get('seq', '')}: {exc}")
    for ident in r.payloads("IDENT"):
        out += brec.identity_findings(ident, ctx) if ident.get("findings") == [] else []
    state: dict = {}
    for i, rec in enumerate(r.records):
        if rec.get("seq") != i + 1:
            out.append(f"record {i + 1} carries seq {rec.get('seq')}")
        out += brec.record_findings(rec, ctx, order[rec["seq"] - 1] if 0 < rec.get("seq", 0) <= len(order) else None, state)
    return out


def candidate_dma_after(r: Run, seq: int) -> list[dict]:
    return [d for d in r.dmas if d["phase"] == "candidate" and d["seq"] > seq]


class TheBuild(unittest.TestCase):
    def test_the_harness_is_built_by_the_system_compiler_with_the_image_s_compile_branch(self):
        b = json.loads((OUT / "build.json").read_text())
        self.assertTrue(Path(b["compiler"]).is_file(), b["compiler"])
        self.assertTrue(b["version"].strip(), "the compiler's version line is recorded")
        cmd = b["command"]
        self.assertEqual(cmd[0], b["compiler"])
        self.assertIn("-DB3_EMIT_SHA", cmd, "the image's compile branch (bsp/build.sh) — not the twins'")
        for unit in ("p3_derive.c", "b2_search.c", "b3_orch.c", "b3_record.c", "b3_online_view.c", "b3_carto.c",
                     "b3_wire.c", "p3_rectx.c", "p3_pull.c"):
            self.assertIn(str(R / "b3/firmware" / unit), cmd, unit)
        self.assertTrue(BIN.is_file())
        self.assertNotIn("warning", _STATE["build_log"].lower())

    def test_a_missing_compiler_is_a_failure(self):
        with tempfile.TemporaryDirectory() as d:
            p = subprocess.run(["bash", str(HARNESS / "build.sh"), d], capture_output=True, text=True,
                               env={"PATH": "/usr/bin:/bin", "CC": "/nonexistent/cc"})
        self.assertNotEqual(p.returncode, 0)
        self.assertIn("no host C compiler", p.stderr)


class TheWholePair(unittest.TestCase):
    """The success control: nothing primed, nothing refused — the application's real main()."""

    @classmethod
    def setUpClass(cls):
        cls.r = run("startup", "whole_pair", first=PAIR, count=1)

    def test_the_session_completes(self):
        res = self.r.result
        self.assertEqual((res["kind"], res["reason"], res["seq"]), ("COMPLETED", "budget", 3005))
        self.assertEqual((res["ident"], res["identack"], res["ident_slice"], res["ident_findings_empty"]), (1, 1, [8, PAIR, 1], 1))
        self.assertEqual((res["scored"], res["refused"], res["rec"]), (3005, 0, 3005))
        self.assertEqual((res["closing_restore"], res["closing_baseline"], res["closing_unsigned"], res["close"]), (1, 1, 1, 1))
        self.assertEqual(res["arms_refused"], 1, "the closing unsigned control — and only it — is refused by the PL")
        self.assertEqual(res["arms_candidate"], 3006, "one ARM per scored candidate and the closing control")
        self.assertEqual(sum(res["dma_after_stop"].values()), 0, "a completed epoch has no restore-only cleanup")
        self.assertEqual(res["dma_candidate"], {"env": 3 * 3005, "cmd": 12 * 3005, "frame": 12 * 3005, "clean": 12 * 3005, "other": 0})
        self.assertEqual(self.r.term["epoch_end"], {"kind": "COMPLETED", "last_seq": 3005, "reason": "budget"})

    def test_the_run_log_passes_the_b3_validator_with_the_common_contract(self):
        ctx = brec.context_from(PLAN, PRED, PAIR, 1)
        (ident,) = self.r.payloads("IDENT")
        log = {"app_identity": ident, "loop_records": self.r.records}
        self.assertEqual(brec.validate_run_log(log, ctx, common=True), [])
        self.assertEqual(findings(self.r), [])

    def test_the_search_blocks(self):
        """SCORED non-baseline records carry a search block; the ledger rides only on O-arm SEARCH records — never on
        an R / F search, a holdout, a baseline."""
        recs = self.r.records
        order = brec.expected_order(brec.context_from(PLAN, PRED, PAIR, 1))
        n_ledger = 0
        for rec in recs:
            want = order[rec["seq"] - 1]
            self.assertEqual(rec["outcome"], "SCORED")
            if want is None:
                self.assertNotIn("search", rec, rec["seq"])
                continue
            _pair, arm, holdout = want
            block = rec["search"]
            has = "ledger" in block
            self.assertEqual(has, arm == "online" and not holdout, (rec["seq"], arm, holdout))
            n_ledger += has
        self.assertEqual(n_ledger, 1000)
        self.assertEqual([r["arm"] for r in recs if r["seq"] in (2, 1002, 2002)], ["online", "random_safe", "map_guided"])
        self.assertEqual(recs[0]["seq"], 1)
        self.assertNotIn("search", recs[-1], "the closing baseline")


class TheRefusals(unittest.TestCase):
    """A refused candidate ends the epoch (B1's contract, unchanged): the record, the stop, the restore-only cleanup
    (its DMAs counted after the stop), the TERM. Every candidate before it was really scored."""

    POINTS = {"the opening baseline": 1, "the O arm's first search": 2, "a candidate that closes a generation": 9,
              "the R arm's first search": 1002, "the F arm's first search": 2002, "the first champion holdout": 3002,
              "the closing baseline": 3005}

    def test_a_refusal_at_each_point(self):
        for what, seq in self.POINTS.items():
            with self.subTest(what):
                r = session(f"refuse_{seq}", refuse=seq)
                res = r.result
                self.assertEqual((res["kind"], res["reason"], res["seq"]), ("STOPPED", REFUSAL, seq))
                self.assertEqual((res["signreq"], res["rec"], res["term"]), (seq, seq, 1))
                self.assertEqual(res["outcomes"][-1] if seq <= 64 else r.records[-1]["outcome"], "REFUSED_BY_GATE")
                self.assertEqual((res["scored"], res["refused"]), (seq - 1, 1))
                self.assertEqual(res["arms_candidate"], seq - 1, "the refused candidate is never ARMed")
                self.assertEqual((res["signreq_after_stop"], res["arms_after_stop"]), (0, 0))
                self.assertEqual(candidate_dma_after(r, seq - 1), [], "the refused candidate stages nothing")
                self.assertEqual(res["dma_after_stop"], {"env": 3, "cmd": 0, "frame": 0, "clean": 0, "other": 0},
                                 "the restore-only cleanup, recorded apart")
                self.assertEqual((res["closing_restore"], res["closing_baseline"], res["closing_unsigned"]), (1, 0, 0))
                self.assertNotIn("search", r.records[-1], "a refused record carries no search block")
                self.assertIn("sign_refusal", r.records[-1]["evidence"])
                self.assertEqual(r.term["epoch_end"]["reason"], REFUSAL)
                self.assertEqual(findings(r), [])

    def test_the_generation_point_is_a_generation_s_last_child(self):
        r = session("refuse_10", refuse=10)
        self.assertTrue(r.records[8]["search"]["selected"], "seq 9 closed the O arm's first generation")
        self.assertFalse(any(x["search"]["selected"] for x in r.records[1:8]))

    def test_an_unacknowledged_record_stops_the_epoch(self):
        r = session("ack_fail", ackrec=0)
        res = r.result
        self.assertEqual(res["kind"], "STOPPED")
        self.assertIn("STOP_REC", res["reason"])
        self.assertEqual((res["signreq"], res["term"]), (1, 1))
        self.assertEqual(res["arms_candidate"], 1, "the candidate was scored; its record was never confirmed")
        self.assertEqual(candidate_dma_after(r, 1), [])
        self.assertEqual(r.term["epoch_end"]["reason"], res["reason"])

    def test_a_page_that_proposes_nothing(self):
        for name, kw, why in (("reserved_bit", {"reserved": 1}, "pair slice is not inside the experiment"),
                              ("slice_outside", {"first": 8}, "pair slice is not inside the experiment"),
                              ("wrong_profile", {"budget": 40}, "session parameters were refused")):
            with self.subTest(name):
                r = session(name, **kw)
                res = r.result
                self.assertEqual(res["kind"], "STOPPED")
                self.assertTrue(res["reason"].startswith("STOP_PAGE: ") and why in res["reason"], res["reason"])
                self.assertEqual((res["signreq"], res["rec"], res["term"], res["ctrl_writes"]), (0, 0, 1, 0))
                self.assertEqual(sum(res["dma_candidate"].values()), 0)
                self.assertEqual(res["dma_after_stop"]["env"], 3, "the restore-only cleanup still runs")
                self.assertEqual(findings(r, 0, 1), [])


class TheStartup(unittest.TestCase):
    """The application's real main(): establish_identity decodes the slice BEFORE the identity declares it."""

    def test_a_strict_host_can_start_the_session(self):
        r = run("startup", "startup_strict", first=PAIR, count=1, strict=1, refuse=2)
        res = r.result
        self.assertEqual((res["ident"], res["identack"], res["ident_slice"], res["ident_findings_empty"]), (1, 1, [8, PAIR, 1], 1))
        self.assertEqual((res["signreq"], res["reason"]), (2, REFUSAL))
        self.assertEqual(findings(r), [])

    def test_an_unacknowledged_identity_stops_before_any_candidate(self):
        r = run("startup", "startup_no_ack", first=PAIR, count=1, ackident=0)
        res = r.result
        self.assertEqual((res["ident"], res["identack"], res["signreq"], res["rec"], res["term"]), (3, 0, 0, 0, 1))
        self.assertIn("STOP_IDENT", res["reason"])

    def test_a_refused_page_is_a_finding_on_the_identity_and_proposes_nothing(self):
        for name, kw, slice_ in (("startup_reserved_bit", {"reserved": 1}, [0, 0, 0]),
                                 ("startup_slice_outside", {"first": 8}, [0, 0, 0]),
                                 ("startup_wrong_profile", {"budget": 40}, [8, 0, 1])):
            with self.subTest(name):
                r = run("startup", name, **{"first": 0, "count": 1, **kw})
                res = r.result
                self.assertEqual(res["ident_slice"], slice_)
                self.assertEqual(res["ident_findings_empty"], 0, "the refusal is a finding on the identity")
                self.assertEqual((res["signreq"], res["rec"], res["term"], res["kind"]), (0, 0, 1, "STOPPED"))
                for doc in r.payloads("IDENT") + r.payloads("TERM"):
                    _STATE["br"].validate(doc)


class TheDmaFaults(unittest.TestCase):
    """F-WIN fault injection — a SIMULATION of the DevC's status and data, never evidence that the hardware stopped
    a DMA. The fault sits on a real candidate; the cleanup's DMAs are counted apart."""

    def stopped(self, r: Run, seq: int, reason: str, scored_before: int):
        res = r.result
        self.assertEqual((res["kind"], res["reason"], res["seq"]), ("STOPPED", reason, seq))
        self.assertEqual(res["signreq"], seq, "no candidate is proposed after the fault")
        self.assertEqual(candidate_dma_after(r, seq), [], "no candidate DMA after the faulted candidate")
        self.assertEqual(res["arms_candidate"], scored_before, "the faulted candidate is never ARMed")
        self.assertEqual((res["signreq_after_stop"], res["arms_after_stop"]), (0, 0))
        self.assertNotIn("SCORED", [x["outcome"] for x in r.records if x["seq"] == seq], "never reported SCORED")
        self.assertEqual(res["scored"], scored_before)
        self.assertEqual(r.term["epoch_end"]["reason"], reason, "the TERM keeps the stop's reason")
        self.assertTrue(all(d["phase"] == "after_stop" for d in r.dmas if d["dma"] > max(x["dma"] for x in r.dmas if x["phase"] == "candidate")))
        self.assertEqual(findings(r), [])

    def test_a_status_that_never_completes(self):
        for name, kw, seq, scored in (("frame_never_at_1", {"fault": "frame@1:never"}, 1, 0),
                                      ("frame_never_at_2", {"fault": "frame@13:never"}, 2, 1),
                                      ("env_never_at_1", {"fault": "env@1:never"}, 1, 0)):
            with self.subTest(name):
                r = session(name, **kw)
                self.stopped(r, seq, TIMEOUT, scored)
                self.assertEqual(r.result["dma_after_stop"], {"env": 3, "cmd": 0, "frame": 0, "clean": 0, "other": 0},
                                 "the restore-only cleanup queues its three envelopes — recorded, not omitted")
                self.assertEqual(r.result["closing_restore"], 1)
                self.assertEqual([x["seq"] for x in r.records], list(range(1, seq)),
                                 "observed: a DMA fault in link 2 / link 3 ends the epoch with no record for that candidate")

    def test_each_error_bit(self):
        """Every bit of the firmware's own INT_STS_ERROR_MASK, one at a time, on a candidate's first readback: the stop
        and its reason, nothing proposed / staged / ARMed after it, the cleanup's three envelopes apart, the TERM."""
        self.assertEqual(ERROR_BITS, [6, 11, 14, 15, 18, 20, 21, 22, 23], "the mask the scope draft enumerated")
        for bit in ERROR_BITS:
            with self.subTest(bit=bit):
                r = session(f"frame_error_bit_{bit}", fault=f"frame@1:error:{bit}")
                self.stopped(r, 1, "DEVCFG error bit after a DMA", 0)
                (faulted,) = [d for d in r.dmas if d["error_bit"] >= 0]
                self.assertEqual((faulted["kind"], faulted["phase"], faulted["seq"], faulted["error_bit"]),
                                 ("frame", "candidate", 1, bit), "the bit injected is the bit named")
                self.assertEqual(int(faulted["last_status"], 16) & ERROR_MASK, 1 << bit,
                                 "the application read exactly that error bit, and no other")
                self.assertEqual(faulted["polls"], 1, "it stopped on the first status read that showed it")
                self.assertEqual(r.result["dma_after_stop"], {"env": 3, "cmd": 0, "frame": 0, "clean": 0, "other": 0})
                self.assertEqual(r.result["closing_restore"], 1)

    def test_an_error_rule_must_name_its_bit(self):
        p = subprocess.run([str(BIN), "session", str(FABRIC), "fault=frame@1:error"], capture_output=True, text=True)
        self.assertEqual(p.returncode, 2)
        self.assertIn("needs a bit", p.stderr)

    def test_the_first_cause_survives_a_cleanup_that_fails_for_another(self):
        """The error bit stops the epoch; the device then stays stuck, so the cleanup's own wait times out — a second,
        different cause. The TERM keeps the first."""
        r = session("frame_error_sticky", fault="frame@1:error:18", sticky=1)
        self.stopped(r, 1, "DEVCFG error bit after a DMA", 0)
        self.assertEqual((r.result["dma_after_stop"]["env"], r.result["closing_restore"]), (1, 0))

    def test_completion_on_the_last_allowed_poll_and_one_past_it(self):
        ok = session("frame_poll_last", fault=f"frame@1:poll:{SPIN_LIMIT}", refuse=2)
        self.assertEqual(ok.result["outcomes"], ["SCORED", "REFUSED_BY_GATE"], "the last allowed poll completes")
        self.assertEqual(findings(ok), [])
        over = session("frame_poll_past", fault=f"frame@1:poll:{SPIN_LIMIT + 1}")
        self.stopped(over, 1, TIMEOUT, 0)

    def test_dma_done_without_d_p_done_is_not_completion(self):
        r = session("frame_dmadone", fault="frame@1:dmadone")
        self.stopped(r, 1, TIMEOUT, 0)

    def test_data_written_after_the_stop_is_never_reported(self):
        r = session("frame_late_data", fault="frame@1:never", late="term")
        self.stopped(r, 1, TIMEOUT, 0)
        self.assertEqual(r.result["late_applied"], 1, "the pending transfer's data did land — after the TERM was sent")
        self.assertNotEqual(r.result["dst_target_word0"], SENTINEL, "the late frame is in DST_BUF at the end of the run")
        self.assertEqual(r.records, [])
        quiet = session("frame_never_no_late", fault="frame@1:never")
        self.assertEqual(quiet.result["dst_target_word0"], SENTINEL, "without the late event the prefill is untouched")

    def test_d_p_done_before_the_data_lands_is_a_link3_stop_not_a_score(self):
        r = session("frame_defer", fault="frame@1:defer")
        res = r.result
        self.assertEqual((res["kind"], res["reason"]), ("STOPPED", "STOP_LINK3: the fabric did not read back as the candidate"))
        self.assertEqual(res["outcomes"], ["STOP_LINK3"])
        self.assertEqual(res["arms_candidate"], 0)
        self.assertEqual(candidate_dma_after(r, 1), [])
        self.assertEqual(res["audit_ready"], 1, "a link-3 stop is audited whether asked or not; the scripted host aborts")
        self.assertEqual(r.term["epoch_end"]["reason"], res["reason"])
        self.assertEqual(findings(r), [])

    def test_a_device_that_stays_stuck(self):
        r = session("frame_never_sticky", fault="frame@1:never", sticky=1)
        self.stopped(r, 1, TIMEOUT, 0)
        self.assertEqual(r.result["dma_after_stop"]["env"], 1, "the cleanup's first envelope times out; it stops there")
        self.assertEqual(r.result["closing_restore"], 0)
        # the instrument's contract has two words for a closing step, done | not_reached (b1_records CLOSING_STEPS):
        # a restore that was ATTEMPTED and did not complete is "not_reached" — the TERM cannot tell it from one never
        # attempted; the attempt is visible here only in the harness's DMA log (observed, reported, not judged)
        self.assertEqual(r.term["closing"]["restore"], "not_reached")
        self.assertEqual([d["kind"] for d in r.dmas if d["phase"] == "after_stop"], ["env"])

    def test_a_pending_transfer_s_late_completion_during_the_cleanup(self):
        """Observed (recorded, not judged): INT_STS does not name the transfer, so the timed-out candidate DMA's late
        D_P_DONE is taken as the cleanup's first envelope completing. With the device still stuck the second envelope
        times out and the TERM reports the restore as not reached."""
        r = session("frame_late_completion_in_cleanup", fault="frame@1:never", sticky=1, late="cleanpoll")
        self.stopped(r, 1, TIMEOUT, 0)
        self.assertEqual(r.result["late_applied"], 1)
        self.assertEqual(r.result["dma_after_stop"]["env"], 2, "the first envelope was accepted on the stale completion")
        self.assertEqual(r.result["closing_restore"], 0)
        self.assertEqual(r.term["closing"]["restore"], "not_reached")


if __name__ == "__main__":
    unittest.main()
