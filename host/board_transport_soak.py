#!/usr/bin/env python3
"""The board-side transport control (B1Q transport line, stage 1½).

The question the entry point cannot answer offline: does the REAL console path — the CH340 on
`17A6`, through usbipd into WSL — drop bytes under load, and at what rate? The self-loopback
measured the host path with no board on the line (1 loss in 2.26 MB under host TX); this
measures the SAME adapter and USB/IP path with the board powered and transmitting, which is the
path a B2Q console session's frames actually cross.

It does so WITHOUT a qualification session and WITHOUT the B2 image: at the board's `Zynq>`
U-Boot prompt (bootdelay = -1), it repeatedly reads a fixed DDR window with `md.l` — no `mw`,
no write, no DMA, no PL, no JTAG, no image load. `md.l` output is deterministic for a window
U-Boot is not touching, so the FIRST clean read is the KNOWN answer and every later read is
compared to it byte-exact per line. A line that parses short, at the wrong address, or with any
word differing from the baseline is one damaged frame — the same failure class the three lost
B1Q sessions showed, now measured on the copper with a denominator.

It attributes nothing and qualifies nothing (plan §5, §6). Its exit code is the tool's state,
not a verdict; it does not lift the transport stop-loss or authorise B2Q. Running it needs the
board powered, the wiring returned to J7, and the owner's ruling (`whole-of-probe transport
soak`); this file is host-only and proved offline against a fake board that emits `md.l` lines.

Why it bears on B2Q: a B2Q console session is ~543 rel-v4 frames under a CRC drop budget of 3
(the instrument's `ceil(4 x 543 / 1000)`). This measures drops per received byte on the same
path over a much larger exposure, so the budget arithmetic can be checked against a real rate
instead of the loopback's optimistic one.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
# The proven transport machinery is reused verbatim, never re-implemented: the exclusive port,
# the counter attempts, the fresh-destination claim, the identity gate and the provenance.
from transport_rig import (  # noqa: E402
    Port, serial_port, read_icounters, counter_delta, claim_destination, _write_evidence,
    device_identity, identity_matches, provenance, self_sha256,
)

MD_LINE_RE = re.compile(rb"^([0-9a-fA-F]{8}):((?:\s+[0-9a-fA-F]{8}){1,4})", re.MULTILINE)
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)> ?$")
BOOT_BANNER_RE = re.compile(rb"U-Boot SPL|\r?\nU-Boot \d|Trying to boot from|Model: Ebang")

EXPECT_USB = "1a86:7523"                # the CH340 on 17A6
DEFAULT_ADDR = 0x00100000              # a low-DDR window U-Boot is not writing at an idle prompt
DEFAULT_WORDS = 0x100                  # 256 words = 64 md.l lines ~ 4.2 KB per repetition
DEFAULT_REPS = 200                     # >= one B2Q session's byte volume many times over
DEFAULT_SECONDS = 3600.0
STOP_AT_DAMAGE = 3                     # damaged lines within one repetition: the failure reproduces

# B2Q's console arithmetic, stated so the result can be read against it (never enforced here).
B2Q_FRAMES = 543
B2Q_CRC_BUDGET = 3

EXIT_MEANING = {
    0: "the soak returned",
    2: "a tool error — in the preflight or a board-level disruption mid-soak; the evidence is exported",
    3: "refused before the soak — the declared identity, or no U-Boot prompt / no clean baseline",
    4: "the device would not open",
    5: "the evidence destination could not be claimed or written — nothing was spent",
}


def parse_md(reply: bytes, addr: int, words: int) -> tuple[list[int] | None, str | None]:
    """`md.l <addr> <words>` → the `words` values at exactly the requested addresses, or a reason
    it is not that. A short count, a line at an unexpected address, or no lines at all makes the
    reply STRUCTURALLY damaged — reported, never silently accepted as a partial buffer."""
    out: list[int] = []
    expect = addr
    for line_addr, body in MD_LINE_RE.findall(reply):
        if int(line_addr, 16) != expect:
            return None, f"md line at {int(line_addr, 16):#010x}, expected {expect:#010x}"
        vals = [int(w, 16) for w in body.split()]
        out.extend(vals)
        expect += 4 * len(vals)
    if not out:
        return None, "no md lines in the reply"
    if len(out) != words:
        return None, f"returned {len(out)} words, not {words}"
    return out, None


class UBoot:
    """A thin U-Boot console over a `Port`: send a line, read until the prompt, watch for a boot
    banner (a reset under the command) — the transport is instrumented, the board is only read."""

    def __init__(self, port: Port, read_timeout: float = 0.05, command_timeout: float = 3.0,
                 clock=time.monotonic, sleep=time.sleep):
        self.port, self.read_timeout, self.command_timeout = port, read_timeout, command_timeout
        self.clock, self.sleep = clock, sleep

    def _read_until_prompt(self, timeout: float) -> tuple[bytes, bool]:
        buf, t0 = bytearray(), self.clock()
        while self.clock() - t0 < timeout:
            chunk = self.port.read(self.read_timeout)
            if chunk:
                buf += chunk
                if PROMPT_RE.search(bytes(buf[-64:])):
                    return bytes(buf), True
        return bytes(buf), False

    def sync(self) -> bytes:
        """One bare CR to clear the power-on RX garbage (the 17A6 answers `Unknown command`),
        then read to a prompt. The reply is returned raw for the record."""
        self.port.write(b"\r", self.command_timeout)
        reply, _ = self._read_until_prompt(self.command_timeout)
        return reply

    def command(self, line: str, timeout: float | None = None) -> tuple[bytes, str | None]:
        """Send `line`, read to the prompt. A boot banner in the reply is a board reset under the
        command (a disruption, not a transport line-drop); no prompt is a session refusal."""
        self.port.write((line + "\r").encode(), self.command_timeout)
        reply, saw_prompt = self._read_until_prompt(timeout or self.command_timeout)
        if BOOT_BANNER_RE.search(reply):
            return reply, "board reset: a U-Boot boot banner appeared under the command"
        if not saw_prompt:
            return reply, f"no U-Boot prompt within {timeout or self.command_timeout} s"
        return reply, None


def _counters(fd) -> dict:
    try:
        return read_icounters(fd)
    except Exception as exc:                              # noqa: BLE001
        return {"available": False, "reason": f"{type(exc).__name__}: {exc}",
                "note": "no counter is reported; absence of a count is not a count of zero"}


def run_soak(a) -> int:
    """Order (the transport line's conventions, mirrored from the rig entry point):
      1. claim a fresh destination and write the invocation before any port opens;
      2. gate on `--expect-usb` (the CH340) unless disabled;
      3. open the port exclusively;
      4. sync to a prompt and take a clean baseline read — no baseline, no soak (exit 3);
      5. repeat the window read under the exposure/stop rules, comparing each to the baseline;
      6. close the port on every path, archive `soak.json` and `entry.json`, print the brief.
    """
    out = Path(a.out)
    export_errors: list[str] = []

    def attempt(what, fn):
        try:
            return fn()
        except Exception as exc:                          # noqa: BLE001
            export_errors.append(f"{what}: {type(exc).__name__}: {exc}")
            return None

    port_holder: list[Port] = []
    closed: list[str] = []
    try:
        code, stage, more = _soak_steps(a, out, attempt, port_holder)
    finally:
        for p in port_holder:
            try:
                p.close()
                closed.append(p.name)
            except Exception as exc:                      # noqa: BLE001
                export_errors.append(f"close {p.name}: {type(exc).__name__}: {exc}")
    brief = {"label": a.label, "exit": code, "exit_meaning": EXIT_MEANING[code], "stage": stage,
             "device": a.device, "exported_to": str(out),
             "ports_closed": closed, "entry_export_errors": list(export_errors), **more}
    brief["export_complete"] = not export_errors
    if stage != "destination":
        brief["entry_record"] = "entry.json"
        if attempt("entry.json", lambda: _write_evidence(
                out / "entry.json", json.dumps(brief, indent=1, sort_keys=True) + "\n")) is None:
            brief["entry_record"] = None
            brief["entry_export_errors"] = list(export_errors)
    print(json.dumps(brief, sort_keys=True))
    return code


def _soak_steps(a, out: Path, attempt, port_holder: list) -> tuple[int, str, dict]:
    fd, refused = claim_destination(out)
    if fd is None:
        return 5, "destination", {"refusal": "destination", "refused": refused}
    identity = attempt("identity", lambda: device_identity(a.device))
    invocation = {"argv": list(a.argv), "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                  "label": a.label, "device": a.device, "baud": a.baud, "expect_usb": a.expect_usb,
                  "addr": a.addr, "words": a.words, "repetitions": a.repetitions, "seconds": a.seconds,
                  "stop_at_damage": STOP_AT_DAMAGE, "identity": identity,
                  "identity_note": "the kernel's record of what was opened — metadata, not acceptance",
                  "b2q_reference": {"frames": B2Q_FRAMES, "crc_budget": B2Q_CRC_BUDGET,
                                    "note": "this soak measures drops/byte on the path B2Q's console frames cross"},
                  "provenance": attempt("provenance", provenance)}
    if a.expect_usb:
        ok, why = identity_matches(identity or {}, a.expect_usb)
        invocation["identity_check"] = {"expected_usb": a.expect_usb, "matched": ok, "reason": why}
    if attempt("invocation.json", lambda: _fd_write(fd, invocation)) is None:
        return 5, "invocation", {}
    if a.expect_usb and not invocation["identity_check"]["matched"]:
        return 3, "identity", {"refusal": "identity", "refused": invocation["identity_check"]["reason"]}
    try:
        port = serial_port(a.device, a.baud)
        port_holder.append(port)
    except Exception as exc:                              # noqa: BLE001
        error = f"{type(exc).__name__}: {exc}"
        attempt("open_error.json", lambda: _write_evidence(
            out / "open_error.json", json.dumps({"error": error, "device": a.device}, indent=1) + "\n"))
        return 4, "open", {"error": error}

    fdno = port.fileno()
    ub = UBoot(port)
    sync = ub.sync()
    cmd = f"md.l {a.addr:#010x} {a.words:#x}"
    before = _counters(fdno)
    base_reply, base_err = ub.command(cmd)
    baseline, parse_err = (None, base_err) if base_err else parse_md(base_reply, a.addr, a.words)
    base_record = {"command": cmd, "sync_reply_tail": sync[-200:].hex(), "reply_bytes": len(base_reply),
                   "reply_sha256": __import__("hashlib").sha256(base_reply).hexdigest(),
                   "parsed": baseline is not None, "error": parse_err, "counters_before": before}
    attempt("baseline.bin", lambda: _write_evidence(out / "baseline.bin", base_reply))
    attempt("baseline.json", lambda: _write_evidence(
        out / "baseline.json", json.dumps(base_record, indent=1, sort_keys=True) + "\n"))
    if baseline is None:
        return 3, "baseline", {"refusal": "baseline",
                               "refused": f"no clean baseline read: {parse_err}"}

    reads: list[dict] = []
    damaged_total = 0
    started = time.monotonic()
    terminal = None
    for i in range(a.repetitions):
        if time.monotonic() - started >= a.seconds:
            terminal = {"reason": "exposure_seconds", "detail": f"{a.seconds} s reached after {i} reads"}
            break
        reply, err = ub.command(cmd)
        rec = {"i": i, "reply_bytes": len(reply),
               "sha256": __import__("hashlib").sha256(reply).hexdigest()}
        attempt(f"read_{i:04d}.bin", lambda r=reply, n=i: _write_evidence(out / f"read_{n:04d}.bin", r))
        if err:                                           # a board-level disruption, not a line-drop
            rec["disruption"] = err
            reads.append(rec)
            terminal = {"reason": "board_disruption", "detail": err, "at_read": i}
            break
        words, perr = parse_md(reply, a.addr, a.words)
        if words is None:                                 # structural transport damage
            rec.update(damaged=1, damage="structural", detail=perr)
        else:
            diffs = [j for j, (x, y) in enumerate(zip(words, baseline)) if x != y]
            rec.update(damaged=1 if diffs else 0,
                       **({"damage": "word_mismatch", "diff_indices": diffs[:16],
                           "diff_count": len(diffs)} if diffs else {}))
        damaged_total += rec.get("damaged", 0)
        reads.append(rec)
        if rec.get("damaged"):
            # count damaged lines within this repetition; here one repetition is one window read,
            # so a single structural failure or any word mismatch is the reproduction signal
            if damaged_total >= STOP_AT_DAMAGE:
                terminal = {"reason": "stop_rule_damage",
                            "detail": f"{damaged_total} damaged reads (>= {STOP_AT_DAMAGE})", "at_read": i}
                break
    else:
        terminal = {"reason": "exposure_repetitions", "detail": f"{a.repetitions} reads completed"}

    after = _counters(fdno)
    received = sum(r["reply_bytes"] for r in reads) + len(base_reply)
    per100k = None if received == 0 else damaged_total * 100000 / received
    result = {"label": a.label, "command": cmd, "tool_sha256": self_sha256(),
              "reads_done": len(reads), "damaged_reads": damaged_total,
              "received_bytes": received, "damaged_per_100k_bytes": per100k,
              "terminal": terminal, "counters_before": before, "counters_after": after,
              "counters_delta": counter_delta(before, after),
              "b2q_reference": {"frames": B2Q_FRAMES, "crc_budget": B2Q_CRC_BUDGET,
                                "note": ("compare damaged_per_100k_bytes here against B2Q's budget of "
                                         f"{B2Q_CRC_BUDGET} damaged frames over ~543 frames; this soak does "
                                         "not qualify, attribute, or lift the stop-loss")},
              "scope": "a transport soak under one path; it attributes nothing and authorises no session",
              "reads": reads}
    attempt("soak.json", lambda: _write_evidence(
        out / "soak.json", json.dumps(result, indent=1, sort_keys=True) + "\n"))
    exit_code = 2 if (terminal or {}).get("reason") == "board_disruption" else 0
    return exit_code, "soak", {
        "terminal": (terminal or {}).get("reason"), "detail": (terminal or {}).get("detail"),
        "reads_done": len(reads), "damaged_reads": damaged_total, "received_bytes": received,
        "damaged_per_100k_bytes": per100k, "counters_delta": result["counters_delta"],
        "soak_record": "soak.json"}


def _fd_write(fd: int, obj: dict) -> bool:
    import os
    try:
        f = os.fdopen(fd, "w")
    except Exception:
        os.close(fd)
        raise
    with f:
        f.write(json.dumps(obj, indent=1, sort_keys=True) + "\n")
    return True


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--device", required=True, help="the console port; on 17A6 the CH340 /dev/ebaz-uart")
    ap.add_argument("--label", required=True)
    ap.add_argument("--out", required=True, help="evidence directory, claimed fresh")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--expect-usb", default=EXPECT_USB, metavar="VID:PID",
                    help=f"refuse unless the node's USB identity is this (default {EXPECT_USB}); '' to disable")
    ap.add_argument("--addr", type=lambda s: int(s, 0), default=DEFAULT_ADDR,
                    help="the DDR window base read read-only with md.l")
    ap.add_argument("--words", type=lambda s: int(s, 0), default=DEFAULT_WORDS)
    ap.add_argument("--repetitions", type=int, default=DEFAULT_REPS)
    ap.add_argument("--seconds", type=float, default=DEFAULT_SECONDS)
    a = ap.parse_args(argv)
    a.argv = list(argv if argv is not None else sys.argv[1:])
    if not a.expect_usb:
        a.expect_usb = None
    return run_soak(a)


if __name__ == "__main__":
    sys.exit(main())
