#!/usr/bin/env python3
"""B4Q — the CONSOLE session: the board application's host harness (build/b4q_firmware/b4q_apphost — the same b4q_app.c /
b4q_wire.c / b4q_psmap.c / b4q_tx.c / b4q_cmd.c sources the image links) driven the way a board would be, through its framed
console (fd 3 in / fd 4 out of the harness; UART1 on the board) while its MMIO is answered from the emulated backend on
stdin / stdout exactly as host/b4q_session.py answers the host-only program. The host's acts here are the board host's: the
identity page written into DDR before the program starts (`mw.l` before `go` on a board), the IDENT line read, every TX /
QUIT framed, every SIGNREQ answered by the bench notary as a SIGNREPLY, every EV / HB / NACK / END logged. The records are
built by the parent class from the same register trace; the manifest declares the transport and the console log is retained
(console.jsonl). The fault knobs are the ENVIRONMENT's (a corrupted or dropped reply, a silent host, a malformed command,
a bad page, a watchdog that cannot be armed) and are declared in the manifest. Nothing here is on-target evidence: the console
is a pipe, the UART, the DMA and the fabric are emulated."""
from __future__ import annotations

import json
import os
import select
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_session as ss  # noqa: E402
import b4q_wire as wire  # noqa: E402
import b4q_notary as nt  # noqa: E402
import b4q_frames as fr  # noqa: E402

APPHOST = R / "build/b4q_firmware/b4q_apphost"
END_STATUS = 6                                 # the executing side's session ended (an END line) where a RESULT was expected


class ConsoleSession(ss.Session):
    def __init__(self, out_dir: Path, label: str = "B4Q-console", binary: Path = APPHOST, token: str | None = None, page_flags: int = wire.PAGE_FLAG_WATCHDOG,
                 corrupt_replies: int = 0, drop_replies: int = 0, bad_page: str | None = None, garbage_before_tx: int = 0, watchdog_fail: bool = False,
                 wrong_token_lines: int = 0, stale_reply_first: int = 0, uboot_epoch: int = 1700000000, **kw):
        super().__init__(out_dir, label=label, binary=binary, **kw)
        self.token = token or wire.new_token()
        self.page_flags = page_flags
        self.knobs = {"corrupt_replies": corrupt_replies, "drop_replies": drop_replies, "bad_page": bad_page, "garbage_before_tx": garbage_before_tx, "watchdog_fail": watchdog_fail,
                      "wrong_token_lines": wrong_token_lines, "stale_reply_first": stale_reply_first}
        self.uboot_epoch = uboot_epoch
        self.host_seq = 0
        self.console = []                      # every console line, both directions, with the trace index: the retained console log
        self.page_words = None
        self.ended = None                      # the END line's payload once seen
        self.stats = {"hb": 0, "nack": 0, "signreq": 0, "signreply": 0, "corrupted": 0, "dropped": 0, "garbage": 0, "wrong_token": 0, "stale": 0}
        self._fds = None
        self._mmio_buf = b""
        self._con_buf = b""

    # ---------------------------------------------------------------- the host's acts before `go`
    def write_page(self):
        image_sha = self.instrument["image_sha256"]
        bad = self.knobs["bad_page"]
        words = wire.page_words(self.token, self.uboot_epoch, image_sha, self.base["bitstream_sha256"], self.backend.carrier.nonce, 0, self.page_flags)
        if bad == "checksum":
            words[-1] ^= 1
        elif bad == "magic":
            words[0] = 0
        elif bad == "reserved":
            words[20] = 7
        elif bad == "absent":
            words = [0] * wire.PAGE_WORDS
        for i, w in enumerate(words):
            self.backend.mem.wr(wire.PAGE_ADDR + 4 * i, w)   # the host's write into DDR (mw.l before go): not a program access, not logged as one
        self.page_words = words

    # ---------------------------------------------------------------- the transport
    def start(self):
        if self.page_words is None:
            self.write_page()
        h2c_r, h2c_w = os.pipe(); c2h_r, c2h_w = os.pipe()
        env = dict(os.environ)
        env["B4Q_CON_IN"], env["B4Q_CON_OUT"] = str(h2c_r), str(c2h_w)   # the pipe ends keep their numbers across the exec (pass_fds); the harness reads them
        if self.knobs["watchdog_fail"]:
            env["B4Q_APP_HOST_WDT_FAIL"] = "1"
        self.proc = subprocess.Popen([str(self.binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, pass_fds=(h2c_r, c2h_w), env=env)
        os.close(h2c_r); os.close(c2h_w)
        self._fds = {"h2c_w": h2c_w, "c2h_r": c2h_r}

    def _console_write(self, line: str, note: str = ""):
        os.write(self._fds["h2c_w"], line.encode("utf-8"))
        self.console.append({"i": len(self.backend.trace), "dir": "host", "line": line.rstrip("\n"), "note": note})

    def _frame_out(self, kind: str, payload: str = "") -> str:
        self.host_seq += 1
        return wire.frame(kind, self.host_seq, self.token, payload)

    def _send(self, line: str):
        """TX / QUIT go to the console as frames (the board host's lines); MMIO replies go to the program's stdin."""
        if line.startswith("TX ") or line == "QUIT":
            if line.startswith("TX ") and self.stats["garbage"] < self.knobs["garbage_before_tx"]:
                self.stats["garbage"] += 1
                self._console_write("B4Q1 TX 0 " + self.token + " AAAA deadbeef\n", "a malformed host line (bad crc): the bench's fault knob")
            if line.startswith("TX ") and self.stats["wrong_token"] < self.knobs["wrong_token_lines"]:
                self.stats["wrong_token"] += 1
                self._console_write(wire.frame("TX", 0, "f" * wire.TOKEN_HEX, line), "a well-formed host line under another session's token: the bench's fault knob")
            self._console_write(self._frame_out("TX" if line.startswith("TX ") else "QUIT", line if line.startswith("TX ") else ""))
        else:
            self.proc.stdin.write((line + "\n").encode("utf-8")); self.proc.stdin.flush()

    def _readline(self, which: str) -> str | None:
        """One line from the program's stdout (MMIO requests) or the console; None when that end closed."""
        fd = self.proc.stdout.fileno() if which == "mmio" else self._fds["c2h_r"]
        buf = self._mmio_buf if which == "mmio" else self._con_buf
        while b"\n" not in buf:
            chunk = os.read(fd, 65536)
            if not chunk:
                return None
            buf += chunk
        line, _, rest = buf.partition(b"\n")
        if which == "mmio":
            self._mmio_buf = rest
        else:
            self._con_buf = rest
        return line.decode("utf-8", "replace")

    def _answer_sign(self, f: dict):
        p = json.loads(f["payload"].decode("utf-8"))
        g, n, req = p["genome"], p["nonce"], p["req"]
        self.stats["signreq"] += 1
        if self.stats["dropped"] < self.knobs["drop_replies"]:
            self.stats["dropped"] += 1
            self.console.append({"i": len(self.backend.trace), "dir": "host", "line": None, "note": f"SIGNREQ req={req} left unanswered: the bench's fault knob"})
            return
        try:
            if int(g, 16) in self.notary_deny:
                raise nt.NotaryRefusal("the bench notary refuses this genome (a configured refusal)")
            s = self.notary.sign(int(g, 16), int(n, 16))
            reply = f"OK {req} " + " ".join(f"{w:08x}" for w in s["words"])
        except (nt.NotaryRefusal, fr.DeriveRefusal) as e:
            self.notary.log.append({"genome_hex": g, "nonce": n, "refused": str(e)})
            reply = f"REFUSED {req} {e}"
        if self.stats["stale"] < self.knobs["stale_reply_first"]:
            self.stats["stale"] += 1                                   # a reply to ANOTHER request with other words, before the right one: must be ignored
            self._console_write(self._frame_out("SIGNREPLY", f"OK {req - 1} " + " ".join("deadbeef" for _ in range(24))), "a stale SIGNREPLY (another request's, garbage words): the bench's fault knob")
        self.stats["signreply"] += 1
        line = self._frame_out("SIGNREPLY", reply)
        if self.stats["corrupted"] < self.knobs["corrupt_replies"]:
            self.stats["corrupted"] += 1
            line = line[:-3] + ("1" if line[-3] != "1" else "2") + "\n"      # one CRC character changed: the line must be refused and re-requested
            self._console_write(line, "the SIGNREPLY corrupted in transit: the bench's fault knob")
            return
        self._console_write(line)

    def serve(self) -> dict:
        """Answer the program's MMIO requests and its console lines until a RESULT (or the IDENT at the opening) — or an END."""
        mmio_fd, con_fd = self.proc.stdout.fileno(), self._fds["c2h_r"]
        while True:
            ready_m = b"\n" in self._mmio_buf; ready_c = b"\n" in self._con_buf
            if not ready_m and not ready_c:
                r, _, _ = select.select([mmio_fd, con_fd], [], [])
                ready_m, ready_c = mmio_fd in r, con_fd in r
            if ready_c:
                r = self._console_line()
                if r is not None:
                    return r
                continue
            if ready_m:
                line = self._readline("mmio")
                if line is None:                       # the program exited: whatever it wrote on the console last (its END) is read before judging
                    while True:
                        r = self._console_line()
                        if r is not None:
                            return r
                        if b"\n" not in self._con_buf:
                            chunk = os.read(con_fd, 65536)
                            if not chunk:
                                break
                            self._con_buf += chunk
                    if self.ended:
                        return {"status": END_STATUS, "reason": "the session ended: " + self.ended.get("kind", "?") + ": " + self.ended.get("reason", ""), "phase": "?", "end": self.ended}
                    raise ss.SessionRefusal("the executing-side program ended without a RESULT")
                if (self.interrupt_after is not None and self._tx_accesses is not None and self._tx_accesses >= self.interrupt_after and line[:2] in ("R ", "W ")
                        and (self.interrupt_tx is None or self.interrupt_tx == self.seq + 1)):
                    self.proc.stdin.close(); self.proc.wait(timeout=10)
                    self.interrupted = {"after_accesses": self._tx_accesses, "last_request": line}
                    return {"status": 5, "reason": "interrupted: the transport closed mid-transaction", "phase": "?"}
                if self._tx_accesses is not None and line[:2] in ("R ", "W "):
                    self._tx_accesses += 1
                if line.startswith("R "):
                    data, resp, x = self.backend.rd32(int(line[2:], 16))
                    self._send(f"{data:08x} {resp}")
                elif line.startswith("W "):
                    a, d = line[2:].split()
                    self._send(str(self.backend.wr32(int(a, 16), int(d, 16))))
                elif line.startswith("HALT "):
                    self.events.append({"i": len(self.backend.trace), "line": line})
                else:
                    self.events.append({"i": len(self.backend.trace), "line": "?? " + line})
                continue
            raise ss.SessionRefusal("the console closed")

    def _console_line(self) -> dict | None:
        """One console line consumed: None when it was a HB / NACK / EV / SIGNREQ (handled), the result when it was an IDENT / RESULT / END."""
        if b"\n" not in self._con_buf:
            chunk = os.read(self._fds["c2h_r"], 65536)
            if not chunk:
                raise ss.SessionRefusal("the console closed")
            self._con_buf += chunk
            if b"\n" not in self._con_buf:
                return None
        line = self._readline("console")
        if line is None:
            raise ss.SessionRefusal("the console closed")
        if True:
            try:
                f = wire.parse(line, self.token if self.page_words and self.knobs["bad_page"] is None else None)
            except wire.WireError as e:
                self.console.append({"i": len(self.backend.trace), "dir": "board", "line": line, "note": f"unparsable: {e}"})
                raise ss.SessionRefusal(f"the console produced a line this host cannot parse ({e}): {line[:80]}")
            self.console.append({"i": len(self.backend.trace), "dir": "board", "line": line, "type": f["type"], "seq": f["seq"]})
            kind, payload = f["type"], f["payload"].decode("utf-8", "replace")
            if kind == "HB":
                self.stats["hb"] += 1
            elif kind == "NACK":
                self.stats["nack"] += 1; self.events.append({"i": len(self.backend.trace), "line": "NACK " + payload})
            elif kind == "EV":
                if payload.startswith("MARK "):
                    self.backend.mark(payload[5:])
                self.events.append({"i": len(self.backend.trace), "line": payload})
            elif kind == "SIGNREQ":
                self._answer_sign(f)
            elif kind == "IDENT":
                ident = json.loads(payload)
                return {**ident["open"], "ident": ident}
            elif kind == "RESULT":
                return json.loads(payload)
            elif kind == "END":
                self.ended = json.loads(payload)
                self.events.append({"i": len(self.backend.trace), "line": "END " + payload})
                return {"status": END_STATUS, "reason": "the session ended: " + self.ended.get("kind", "?") + ": " + self.ended.get("reason", ""), "phase": "?", "end": self.ended}
            else:
                self.events.append({"i": len(self.backend.trace), "line": f"?? {kind} {payload}"})
        return None

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                if self.ended is None:
                    self._send("QUIT")
                    r = self.serve()                      # the END COMPLETED (or whatever the program ends with)
                    if r.get("status") != END_STATUS:
                        self.events.append({"i": len(self.backend.trace), "line": "?? a RESULT where the END was expected"})
            except (BrokenPipeError, ValueError, OSError, ss.SessionRefusal):
                pass
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:                                                   # the harness's last stdout line (HALT kicks=N: the platform's own count) before it exits
                while True:
                    line = self._readline("mmio")
                    if line is None:
                        break
                    self.events.append({"i": len(self.backend.trace), "line": line if line.startswith("HALT ") else "?? " + line})
            except OSError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        for k in ("h2c_w", "c2h_r"):
            if self._fds and self._fds.get(k) is not None:
                try:
                    os.close(self._fds[k])
                except OSError:
                    pass
                self._fds[k] = None

    # ---------------------------------------------------------------- the opening: the program opens by itself after the page
    def open(self) -> dict:
        if self.session_open is not None:
            raise ss.SessionRefusal("the session is already opened (or refused): one opening per session")
        if self.proc is None:
            self.start()
        r = self.serve()
        if r.get("status") == END_STATUS:                 # the program ended before an IDENT (a bad page, a watchdog that could not be armed)
            r = {"status": 1, "reason": r["reason"], "startup_readback": "", "end": r.get("end")}
        self.ident = r.get("ident")
        so = self._opened(r)
        if self.ident is not None:
            findings = so["findings"]
            if self.ident.get("protocol") != "b4q-v1":
                findings.append(f"the image speaks {self.ident.get('protocol')!r}, not the protocol this host implements (b4q-v1)")
            if self.ident.get("token") != self.token:
                findings.append("the IDENT's token is not the page's")
            if self.ident.get("app_image_sha_lo32") != int(self.instrument["image_sha256"][:8], 16):
                findings.append("the IDENT's image digest echo is not the page's")
            if not self.ident.get("nonce_echo_equal"):
                findings.append("the nonce the program read at its opening is not the one the host saw before `go`")
            if (self.page_flags & wire.PAGE_FLAG_WATCHDOG) and self.ident.get("watchdog") != "armed":
                findings.append("the page asked for the watchdog and the IDENT does not say it is armed")
            if findings and self.halted is None:
                self.halt("the session did not open: " + "; ".join(findings))
        return so

    def write(self) -> dict:
        m = super().write()
        (self.out / "console.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.console))
        m["transport"] = {"kind": "console-emulated", "standing": "the board application's host harness on a pipe: its framed console lines are the bytes the image would put on UART1; not a board, not on-target evidence",
                          "protocol": "b4q-v1", "token": self.token, "page_words": [f"{w:08x}" for w in (self.page_words or [])], "page_flags": self.page_flags,
                          "knobs": self.knobs, "stats": self.stats, "end": self.ended, "ident": self.ident, "console_lines": len(self.console)}
        (self.out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
        return m
