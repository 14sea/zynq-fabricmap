#!/usr/bin/env python3
"""B4Q — the OFFLINE END-TO-END driver of the PHYSICAL RUNNER over the DEVICE SURROGATE (the runner unit of 2026-10-28): every
scenario starts its own surrogate (host/b4q_device_surrogate.py) on a fresh PTY, runs the runner (host/b4q_runner.py) against it
from the U-Boot prompt through the image load, the page, `go`, the session and the stop, and re-reads the archive with
host/b4q_verify.py in a fresh process. The host-side scenarios are the console e2e's own bodies (host/b4q_console_e2e.py): the
runner answers the same protocol; the device-side faults are the surrogate's declared knobs — an interrupted load, a wrong load
witness, a page corrupted after its witness, a missed autoboot, no prompt, an unknown image, silence mid-session, a reset
(banner) mid-transaction, a corrupted CHUNK (re-asked), a tiny evidence log (its overflow), a watchdog that cannot be armed, the
seqcut twin as the image, a DevC fault, a corrupted frame read. Each scenario declares what the runner MUST do (`expect`), and
the summary says whether it did. Nothing physical: the endpoint is a PTY, the device a process."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_console_e2e as ce  # noqa: E402
import b4q_runner as rn  # noqa: E402
import b4q_session as ss  # noqa: E402

stim, G_BASE, G_CESR, FIX0, FIX1 = ce.stim, ce.G_BASE, ce.G_CESR, ce.FIX0, ce.FIX1
SURROGATE = R / "host/b4q_device_surrogate.py"
SEQCUT = R / "build/b4q_firmware/b4q_seqcut_twin"
IMAGE_SHA = hashlib.sha256(rn.IMAGE.read_bytes()).hexdigest() if rn.IMAGE.is_file() else ""


def scenario_pre_event_corrupt(s):
    """The console e2e's body minus its backend knob (the surrogate's --corrupt-frame-read 33 plays it)."""
    s.open(); s.transaction("root", 0, stim([]))
    r = ce._tx(s, "normal", G_CESR, FIX1)
    try:
        s.transaction("normal", G_BASE, stim(FIX0)); refused = None
    except ss.SessionRefusal as ex:
        refused = str(ex)
    return {"tx": r, "next_refused": refused}


def scenario_two(s):
    s.open(); s.transaction("root", 0, stim([]))
    return {"tx": ce._tx(s, "normal", G_CESR, FIX1)}


def scenario_three(s):
    s.open(); s.transaction("root", 0, stim([]))
    a = ce._tx(s, "normal", G_CESR, FIX1)
    b = ce._tx(s, "normal", G_BASE, FIX0)
    return {"tx": [a, b]}


def expect_stop(prefix: str):
    return {"stop_prefix": prefix, "opened": False}


# name: (body, surrogate args, runner kw, expect)
SCENARIOS = {
    # the console e2e's scenarios over the PTY (the host-side knobs are the runner session's; the device-side ones the surrogate's)
    "valid": (ce.scenario_valid, [], {}, {"opened": True, "records": 4, "closed": 4, "verify": 0, "digest_equal": True}),
    "a5": (ce.scenario_a5, [], {}, {"opened": True, "verify": 0}),
    "notary_refuses": (ce.scenario_notary_refuses, [], {"notary_deny": {G_CESR}}, {"opened": True, "verify": 0}),
    "reply_corrupt": (ce.scenario_reply_corrupt, [], {}, {"opened": True, "verify": 0}),
    "reply_dropped_once": (ce.scenario_reply_dropped_once, [], {}, {"opened": True, "verify": 0}),
    "replies_dropped": (ce.scenario_replies_dropped, [], {}, {"opened": True, "verify": 0}),
    "silent_host": (ce.scenario_silent_host, [], {}, {"opened": True, "verify": 0}),
    "garbage_command": (ce.scenario_garbage_command, [], {}, {"opened": True, "verify": 0}),
    "wrong_token": (ce.scenario_wrong_token, [], {}, {"opened": True, "verify": 0}),
    "stale_reply": (ce.scenario_stale_reply, [], {}, {"opened": True, "verify": 0}),
    "duplicate_tx": (ce.scenario_duplicate_tx, [], {}, {"opened": True, "verify": 0}),
    "after_stop_tx": (ce.scenario_after_stop_tx, [], {"notary_deny": {G_CESR}}, {"opened": True, "verify": 0}),
    "malformed_tx": (ce.scenario_malformed_tx, [], {}, {"opened": True, "verify": 0}),
    "host_seq_gap": (ce.scenario_host_seq_gap, [], {}, {"opened": True, "verify": 0}),
    "bad_page": (ce.scenario_bad_page, [], {"bad_page": "checksum"}, {"opened": False, "verify": 0, "end_kind": "STOPPED"}),
    "sequence_cut": (ce.scenario_sequence_cut, [f"--image-table={IMAGE_SHA}={SEQCUT}"], {}, {"opened": True, "verify": 0, "end_kind": "PROTOCOL", "tail_unobtainable": True}),
    "watchdog_fail": (ce.scenario_watchdog_fail, ["--fault=wdt-fail"], {}, {"opened": False, "verify": 0, "end_kind": "STOPPED"}),
    "pre_event_corrupt": (scenario_pre_event_corrupt, ["--corrupt-frame-read=33"], {}, {"opened": True, "verify": 0, "halted": True}),
    # the runner's own: the control plane and the transport under the surrogate's faults
    "interrupted_load": (scenario_two, ["--fault=interrupted-load=20"], {}, expect_stop("loady: the ymodem transfer failed")),
    "wrong_crc": (scenario_two, ["--fault=wrong-crc"], {}, expect_stop("load witness:")),
    "md_garbage": (scenario_two, ["--fault=md-garbage"], {}, expect_stop("md.l")),
    "corrupt_page": (scenario_two, ["--fault=corrupt-page"], {}, {"opened": False, "verify": 0, "end_kind": "STOPPED", "page_witness": True}),
    "page_witness_fails": (scenario_two, ["--fault=corrupt-mw"], {}, expect_stop("page witness:")),
    "missed_autoboot": (scenario_two, ["--fault=missed-autoboot"], {"break_s": 4.0}, expect_stop("no U-Boot prompt: a boot banner was seen")),
    "no_prompt": (scenario_two, ["--fault=no-prompt"], {"break_s": 4.0}, expect_stop("no U-Boot prompt")),
    "unknown_image": (scenario_two, ["--fault=unknown-image"], {"silence_s": 3.0}, {"opened": False, "transport_stop": "the console was silent"}),
    "silence_mid_session": (scenario_three, ["--fault=silence-after=40"], {"silence_s": 3.0}, {"opened": True, "transport_stop": "the console was silent", "verify": 0}),
    "reset_mid_session": (scenario_three, ["--fault=reset-after-lines=40"], {"silence_s": 5.0}, {"opened": True, "transport_stop": "a boot banner on the console mid-session", "verify": 0}),
    "corrupt_chunk": (ce.scenario_valid, ["--fault=corrupt-chunk=2"], {}, {"opened": True, "records": 4, "closed": 4, "verify": 0, "bad_chunks": 1, "digest_equal": True}),
    "log_overflow": (scenario_three, ["--fault=ring-bytes=16384"], {}, {"opened": True, "verify": 0, "halted": True}),
    "devc_never": (scenario_three, ["--devc-fault=env:1:never"], {}, {"opened": True, "verify": 0, "halted": True}),
}


def start_surrogate(link: Path, out: Path, args: list) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-B", str(SURROGATE), "--link", str(link), "--boot-on-input", "--private-dir", str(out / "private"), *args],
                         stdout=subprocess.PIPE, stderr=(out / "private" / "surrogate.err").open("wb"), text=True)
    line = p.stdout.readline()
    if not line.startswith("PTY "):
        p.kill()
        raise RuntimeError(f"the surrogate did not announce its PTY: {line!r}")
    return p


def check(expect: dict, summary: dict, verify_rc: int, verify: dict) -> list[str]:
    bad = []
    stop = (summary.get("stop") or {}).get("why", "")
    if "stop_prefix" in expect and not stop.startswith(expect["stop_prefix"]):
        bad.append(f"stop: {stop[:80]!r} does not start with {expect['stop_prefix']!r}")
    if "opened" in expect and bool(summary.get("opened")) != expect["opened"]:
        bad.append(f"opened: {summary.get('opened')} (expected {expect['opened']})")
    if "records" in expect and len(summary.get("records") or []) != expect["records"]:
        bad.append(f"records: {len(summary.get('records') or [])} (expected {expect['records']})")
    if "closed" in expect and sum(1 for r in summary.get("records") or [] if r.get("x") == "closed") != expect["closed"]:
        bad.append("closed records")
    if "verify" in expect and verify_rc != expect["verify"]:
        bad.append(f"verify rc {verify_rc} (expected {expect['verify']}): {verify.get('refused') or verify.get('session')}")
    if "digest_equal" in expect and bool((summary.get("source") or {}).get("digest_equal")) != expect["digest_equal"]:
        bad.append("source digest")
    if "end_kind" in expect and (summary.get("end") or {}).get("kind") != expect["end_kind"]:
        bad.append(f"end kind {(summary.get('end') or {}).get('kind')} (expected {expect['end_kind']})")
    if "halted" in expect and bool(summary.get("halted")) != expect["halted"]:
        bad.append(f"halted: {summary.get('halted')!r}")
    if "transport_stop" in expect:
        stops = [x["why"] for x in summary.get("transport_stops") or []]
        if not any(x.startswith(expect["transport_stop"]) for x in stops):
            bad.append(f"transport stop {expect['transport_stop']!r} not among {stops}")
    if "bad_chunks" in expect and (summary.get("stats_pull") or {}).get("bad_chunks") != expect["bad_chunks"]:
        bad.append(f"bad chunks {(summary.get('stats_pull') or {}).get('bad_chunks')}")
    if "tail_unobtainable" in expect and bool(summary.get("tail_unobtainable")) != expect["tail_unobtainable"]:
        bad.append("tail_unobtainable")
    if "page_witness" in expect and bool((summary.get("page_witness") or {}).get("equal")) != expect["page_witness"]:
        bad.append("page witness")
    return bad


def run_scenario(root: Path, name: str) -> dict:
    body, sargs, kw, expect = SCENARIOS[name]
    out = root / name
    (out / "private").mkdir(parents=True, exist_ok=True)
    link = Path(f"/tmp/b4q-runner-e2e-{os.getpid()}-{name}")
    sur = start_surrogate(link, out, sargs)
    t0 = time.time()
    try:
        time.sleep(0.2)
        body_kw = dict(kw)
        break_s = body_kw.pop("break_s", 20.0)
        silence_s = body_kw.pop("silence_s", 20.0)
        summary = rn.run(str(link), out, body, silence_s=silence_s, label=f"B4Q-runner-{name}", break_s=break_s, **body_kw)
    finally:
        sur.kill()
        try:
            sur.wait(timeout=5)
        except subprocess.TimeoutExpired:
            pass
        try:
            link.unlink()
        except FileNotFoundError:
            pass
    verify_rc, verify = None, {}
    if (out / "manifest.json").is_file():
        q = subprocess.run([sys.executable, "-B", str(R / "host/b4q_verify.py"), str(out), "--json", str(out / "verify.json")], capture_output=True, text=True, timeout=600)
        verify_rc = q.returncode
        try:
            verify = json.loads((out / "verify.json").read_text())
        except (OSError, ValueError):
            verify = {"refused": "no verify.json", "stderr": q.stderr[-500:]}
    m = json.loads((out / "manifest.json").read_text()) if (out / "manifest.json").is_file() else {}
    summary["stats_pull"] = ((m.get("transport") or {}).get("evidence_log") or {}).get("stats")
    summary["tail_unobtainable"] = (m.get("source") or {}).get("tail_unobtainable")
    summary.update({"name": name, "wall_s": round(time.time() - t0, 3), "surrogate_args": sargs, "verify_rc": verify_rc, "verify_agree": verify.get("agree"),
                    "verify_session": verify.get("session"), "verify_limitations": (verify.get("source") or {}).get("limitations"), "expect": expect})
    summary["expect_failures"] = check(expect, summary, verify_rc, verify)
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    return summary


def main(argv=None) -> int:
    argv = list(argv if argv is not None else sys.argv[1:])
    root = Path(argv[0]) if argv else R / "build/b4q_runner_e2e"
    root.mkdir(parents=True, exist_ok=True)
    names = argv[1:] or list(SCENARIOS)
    summaries = []
    for name in names:
        print("==", name, flush=True)
        s = run_scenario(root, name)
        summaries.append(s)
        print(json.dumps({k: s.get(k) for k in ("wall_s", "stop", "opened", "halted", "verify_rc", "expect_failures")}, default=str)[:400], flush=True)
    (root / "e2e_summary.json").write_text(json.dumps(summaries, indent=1, default=str) + "\n")
    bad = [s["name"] for s in summaries if s["expect_failures"]]
    print("expectation failures:", bad or "none")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
