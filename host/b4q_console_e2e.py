#!/usr/bin/env python3
"""B4Q — the OFFLINE END-TO-END driver of the CONSOLE path: the board application's host harness (the image's own sources)
driven through its framed console by host/b4q_console_session.py over the emulated backend, in the scenarios the PS-image unit
names — the valid session (open / root / three candidates / QUIT), the A5 protocol, a notary refusal through the console, a
corrupted SIGNREPLY (refused, re-requested, then signed), a dropped reply (re-requested), every reply dropped (the bound, a
STOP_SIGN), a silent host (the idle bound: END STOPPED), a malformed host line (NACK, then the command), a bad identity page
(no IDENT, nothing signed), a watchdog that cannot be armed (nothing signed), a corrupted readback inside a transaction
(the executing side's own stop, reported through the console), an external interruption. Every scenario is its own
session in its own directory; host/b4q_verify.py re-reads each in a fresh process. Nothing physical: the console is a pipe."""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_console_session as cs  # noqa: E402
import b4q_session as ss  # noqa: E402
import b4q_e2e as ee  # noqa: E402
import b4q_qual as ql  # noqa: E402

stim, task_for = ee.stim, ee.task_for
G_BASE, G_CESR, G_SYNC = ee.G_BASE, ee.G_CESR, ee.G_SYNC
FIX0, FIX1, FIX2 = ee.FIX0, ee.FIX1, ee.FIX2


def run_session(root: Path, name: str, body, **kw) -> dict:
    out = root / name
    s = cs.ConsoleSession(out, label=f"B4Q-console-{name}", **kw)
    t0 = time.time()
    try:
        extra = body(s) or {}
    finally:
        s.stop()
    m = s.write()
    halt = [e["line"] for e in s.events if e["line"].startswith("HALT kicks=")]
    summary = {"name": name, "wall_s": round(time.time() - t0, 3), "records": m["records"], "chain_findings": m["chain_findings"], "accesses": m["accesses"],
               "end": s.ended, "stats": s.stats, "console_lines": len(s.console), "halted": s.halted, "open_findings": (s.session_open or {}).get("findings"),
               "platform_kicks": int(halt[-1].split("=")[1]) if halt else None, **extra}     # the harness's own count of watchdog restarts (the platform's, not the application's claim)
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary


def _tx(s, kind, g, steps, task=None):
    e = s.transaction(kind, g, stim(steps), task)
    return {"status": e["firmware"]["status"], "reason": e["firmware"]["reason"], "phase": e["firmware"].get("phase"), "o": e["o"] is not None, "x": e["x"]["status"] if e["x"] else None, "findings": e["findings"]}


def scenario_valid(s):
    so = s.open(); assert so["findings"] == [], so["findings"]
    s.transaction("root", 0, stim([]))
    s.transaction("normal", G_BASE, stim(FIX0), task_for(7, "fix0"))
    s.transaction("normal", G_CESR, stim(FIX1), task_for(7, "fix1"))
    s.transaction("normal", G_SYNC, stim(FIX2), task_for(7, "fix2"))
    return {"ident": s.ident}


def scenario_a5(s):
    s.open(); s.transaction("root", 0, stim([]))
    j1 = s.transaction("normal", G_CESR, stim(FIX1))
    j2 = s.transaction("inject", G_CESR, stim([(1, 1, 0, 0x00)]))
    j3 = s.transaction("a5", G_CESR, stim(FIX1))
    s.transaction("normal", G_BASE, stim(FIX0), task_for(7, "after-a5"))
    v = ql.a5_verdict(j1["o"], j2["o"], j3["o"], j1["x"], j3["x"], j2["x"])
    s.qual_plan["a5"].append({"J1": j1["seq"], "J2": j2["seq"], "J3": j3["seq"], "conclusion_file": "a5_verdict.json"})
    (s.out / "a5_verdict.json").write_text(json.dumps(v, indent=1) + "\n")
    return {"a5": v["verdict"]}


def scenario_notary_refuses(s):
    s.open(); s.transaction("root", 0, stim([]))
    r = _tx(s, "normal", G_CESR, FIX1)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"tx": r, "next_refused": refused, "sign_events": [e["line"] for e in s.events if e["line"].startswith("EV sign")]}


def scenario_reply_corrupt(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["corrupt_replies"] = 1                       # the fault aimed at the candidate, after the root signed cleanly
    r = _tx(s, "normal", G_CESR, FIX1, task_for(7, "fix1"))
    return {"tx": r}


def scenario_reply_dropped_once(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["drop_replies"] = 1                       # the fault aimed at the candidate, after the root signed cleanly
    return {"tx": _tx(s, "normal", G_CESR, FIX1)}


def scenario_replies_dropped(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["drop_replies"] = 3                       # the fault aimed at the candidate, after the root signed cleanly
    r = _tx(s, "normal", G_CESR, FIX1)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"tx": r, "next_refused": refused, "sign_events": [e["line"] for e in s.events if e["line"].startswith("EV sign")]}


def scenario_silent_host(s):
    s.open(); s.transaction("root", 0, stim([]))
    r = s.serve()                              # the host sends nothing: the program's idle bound ends the session by name
    return {"served": r.get("status"), "end": r.get("end")}


def scenario_garbage_command(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["garbage_before_tx"] = 1                       # the fault aimed at the candidate, after the root signed cleanly
    return {"tx": _tx(s, "normal", G_CESR, FIX1)}


def scenario_wrong_token(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["wrong_token_lines"] = 1
    r = _tx(s, "normal", G_CESR, FIX1)
    return {"tx": r, "nacks": [e["line"] for e in s.events if e["line"].startswith("NACK")]}


def scenario_stale_reply(s):
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["stale_reply_first"] = 1
    return {"tx": _tx(s, "normal", G_CESR, FIX1)}


def scenario_duplicate_tx(s):
    """the previous TX frame re-sent byte for byte (the same host sequence): NACK stale sequence, nothing signed, nothing run"""
    s.open(); s.transaction("root", 0, stim([]))
    first = _tx(s, "normal", G_BASE, FIX0)
    s.knobs["replay_tx"] = 1                                   # the next TX goes out as the previous TX line, byte for byte
    signs, trace = s.stats["signreq"], len(s.backend.trace)
    second = _tx(s, "normal", G_BASE, FIX0)
    return {"first": first, "second": second, "new_signreqs": s.stats["signreq"] - signs, "new_trace_events": len(s.backend.trace) - trace, "halted": s.halted}


def scenario_after_stop_tx(s):
    """after a transaction that did not close (the notary refused), a valid TX injected at the console boundary — bypassing the
    high-level API's latch — must be NACKed by the application: nothing signed, nothing run (the host's own refusal of an
    unsolicited SIGNREQ while halted is tests/test_b4q_app.py's unit case: the application never sends one)"""
    s.open(); s.transaction("root", 0, stim([]))
    failed = _tx(s, "normal", G_CESR, FIX1)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); api_refused = False
    except ss.SessionRefusal:
        api_refused = True
    signs, trace = s.stats["signreq"], len(s.backend.trace)
    words = [ss.step_word(x) for x in stim(FIX0)[1:]]
    s._send(f"TX normal {G_BASE:08x} {len(words)} " + " ".join(f"{w:07x}" for w in words))
    r = s.serve()
    return {"failed": failed, "api_refused": api_refused, "raw_next": {k: r.get(k) for k in ("status", "reason")}, "new_signreqs": s.stats["signreq"] - signs,
            "new_trace_events": len(s.backend.trace) - trace, "halted": s.halted}


def scenario_malformed_tx(s):
    """TX lines that do not match the grammar: NACK malformed TX, no SIGNREQ, no DMA, no RESULT for another transaction"""
    s.open(); s.transaction("root", 0, stim([]))
    out = []
    for cmd in ("TX mystery 00000000 0", "TX normal 100000000 0", "TX normal 00000000 1 2000000", "TX normal 00000000 0 GARBAGE",
                "TX normal 00000000 0 TASK " + "a" * 64 + " 2 1 0 0 1", "TX normal 00000000 1 0000001 TASK " + "a" * 64 + " 1 257 256 256 65537"):
        signs, trace, submits = s.stats["signreq"], len(s.backend.trace), sum(1 for e in s.backend.pcap_log if e.get("pcap") == "submit")
        s._send(cmd)
        r = s.serve()
        out.append({"cmd": cmd, "status": r.get("status"), "reason": r.get("reason"), "new_signreqs": s.stats["signreq"] - signs, "new_trace_events": len(s.backend.trace) - trace,
                    "new_submits": sum(1 for e in s.backend.pcap_log if e.get("pcap") == "submit") - submits})
    ok = _tx(s, "normal", G_BASE, FIX0, task_for(7, "fix0"))               # a legitimate one still runs
    return {"malformed": out, "then": ok}


def scenario_host_seq_gap(s):
    """a gap in the host's sequence (a dropped frame) is legitimate: strict increase, not contiguity"""
    s.open(); s.transaction("root", 0, stim([]))
    s.knobs["seq_gap"] = 5
    return {"tx": _tx(s, "normal", G_CESR, FIX1), "host_seq_last": s.host_seq}


def scenario_sequence_cut(s):
    """the line sequence cut to its limit inside the root transaction, right before its EV P4 (the seqcut twin, the owner's fixture): the
    terminal END goes out, the executing side's next write is refused by the HAL and it stops — no register write, no DMA submission,
    no RESULT after the END (R2); the session halts on the unsealed outcome"""
    s.open()
    trace0 = len(s.backend.trace)
    r = s.transaction("root", 0, stim([]))
    drained = s.drain_after_end() if r["firmware"].get("status") == cs.END_STATUS else {}   # the owner's method: keep answering MMIO after the END and look
    end_entry = next((e for e in s.console if e["dir"] == "board" and e.get("type") == "END"), None)
    i_end = end_entry["i"] if end_entry else None
    after = s.backend.trace[i_end:] if i_end is not None else []
    n_pcap_at_end = end_entry.get("pcap_n") if end_entry else None
    return {"tx": {"status": r["firmware"]["status"], "reason": r["firmware"]["reason"], "o": r["o"] is not None}, "end": s.ended, "end_trace_index": i_end,
            "writes_after_end": sum(1 for e in after if e.get("op") == "wr"), "reads_after_end": sum(1 for e in after if e.get("op") == "rd"),
            "submits_after_end": (sum(1 for e in s.backend.pcap_log[n_pcap_at_end:] if e.get("pcap") == "submit") if n_pcap_at_end is not None else None),
            "trace_events_in_tx": len(s.backend.trace) - trace0, "halted": s.halted, **drained}


def scenario_bad_page(s):
    so = s.open()
    try:
        s.transaction("root", 0, stim([])); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"open_status": so["record"]["status"], "root_refused": refused, "signatures": len(s.notary.log), "ident": s.ident}


def scenario_watchdog_fail(s):
    so = s.open()
    try:
        s.transaction("root", 0, stim([])); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"open_status": so["record"]["status"], "root_refused": refused, "signatures": len(s.notary.log), "ident": s.ident}


def scenario_pre_event_corrupt(s):
    s.corrupt_frame_reads.add(33)
    s.open(); s.transaction("root", 0, stim([]))
    r = _tx(s, "normal", G_CESR, FIX1)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"tx": r, "next_refused": refused}


def scenario_interrupt(s):
    s.open(); s.transaction("root", 0, stim([]))
    return {"tx": _tx(s, "normal", G_CESR, FIX1)}


SCENARIOS = {
    "valid": (scenario_valid, {}),
    "a5": (scenario_a5, {}),
    "notary_refuses": (scenario_notary_refuses, {"notary_deny": {G_CESR}}),
    "reply_corrupt": (scenario_reply_corrupt, {}),
    "reply_dropped_once": (scenario_reply_dropped_once, {}),
    "replies_dropped": (scenario_replies_dropped, {}),
    "silent_host": (scenario_silent_host, {}),
    "garbage_command": (scenario_garbage_command, {}),
    "wrong_token": (scenario_wrong_token, {}),
    "stale_reply": (scenario_stale_reply, {}),
    "duplicate_tx": (scenario_duplicate_tx, {}),
    "after_stop_tx": (scenario_after_stop_tx, {"notary_deny": {G_CESR}}),
    "malformed_tx": (scenario_malformed_tx, {}),
    "host_seq_gap": (scenario_host_seq_gap, {}),
    "sequence_cut": (scenario_sequence_cut, {"binary": R / "build/b4q_firmware/b4q_seqcut_twin"}),
    "bad_page": (scenario_bad_page, {"bad_page": "checksum"}),
    "watchdog_fail": (scenario_watchdog_fail, {"watchdog_fail": True}),
    "pre_event_corrupt": (scenario_pre_event_corrupt, {}),
    "interrupt": (scenario_interrupt, {"interrupt_after_accesses": 3000, "interrupt_tx": 2}),
}


def main(argv=None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    root = Path(argv[0]) if argv else R / "build/b4q_console_e2e"
    root.mkdir(parents=True, exist_ok=True)
    names = argv[1:] or list(SCENARIOS)
    summaries = []
    for name in names:
        body, kw = SCENARIOS[name]
        print("==", name, flush=True)
        summaries.append(run_session(root, name, body, **kw))
        print(json.dumps({k: v for k, v in summaries[-1].items() if k not in ("records", "ident")})[:600], flush=True)
    (root / "e2e_summary.json").write_text(json.dumps(summaries, indent=1) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
