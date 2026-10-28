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
import time
import os
import select
import subprocess
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_regmap as rm  # noqa: E402
import b4q_evidence_log as el  # noqa: E402
import b4q_session as ss  # noqa: E402
import b4q_wire as wire  # noqa: E402
import b4q_notary as nt  # noqa: E402
import b4q_frames as fr  # noqa: E402

APPHOST = R / "build/b4q_firmware/b4q_apphost"
PROTOCOL = "b4q-v2"                            # the image's console protocol this host implements (v2: the evidence log and its pull)
END_STATUS = 6                                 # the executing side's session ended (an END line) where a RESULT was expected
NACK_STATUS = 7                                # the application refused the command by name (a NACK where a RESULT was expected): no transaction ran
SEQ_LIMIT = 0xFFFFFFF0                         # this host's line sequence never wraps: it refuses to frame beyond this


class PsEvidence:
    """The PS SOURCE of the records (docs/b4q_source_audit.md §3): the trace / PCAP log / accesses derived (b4q_evidence_log.derive,
    `ps-evidence-log-v1`) from the evidence log the board application appended to its DDR and this host pulled through the console
    — nothing from a backend, a model or an expected genome. The lists are replaced in place at every acquisition: an entry is emitted
    at the log record that completes it, so the derivation of a prefix of the log is a prefix of the derivation of the whole (a group
    digest is amended on its entries once the eighth frame is read; trace positions never move)."""

    def __init__(self):
        self.deriver = el.Deriver()
        self.trace, self.pcap_log = self.deriver.trace, self.deriver.pcap
        self.accesses, self.host_marks = [], []

    @property
    def derived_bytes(self) -> int:
        return self.deriver.fed_bytes

    @property
    def records(self) -> int:
        return self.deriver.fed_records

    def mark(self, name: str):
        self.host_marks.append({"i": len(self.trace), "mark": name})         # a host-side event (an interruption this host saw): never in the PS's trace

    def refresh(self, data: bytes):
        n = len(self.deriver.accesses)
        self.deriver.feed_bytes(data)                                        # incremental: only the bytes beyond the last acquisition are parsed and derived
        self.accesses.extend((e["op"], e["addr"], e["resp"]) for e in self.deriver.accesses[n:])


class ConsoleSession(ss.Session):
    def __init__(self, out_dir: Path, label: str = "B4Q-console", binary: Path = APPHOST, token: str | None = None, page_flags: int = wire.PAGE_FLAG_WATCHDOG,
                 corrupt_replies: int = 0, drop_replies: int = 0, bad_page: str | None = None, garbage_before_tx: int = 0, watchdog_fail: bool = False,
                 wrong_token_lines: int = 0, stale_reply_first: int = 0, seq_gap: int = 0, replay_tx: int = 0, uboot_epoch: int = 1700000000,
                 source: str = "emulated", **kw):
        """`source`: "emulated" — the records from the backend's own trace / PCAP log (the host-only source, as before); "ps-evidence-log-v1"
        — the records from the PS's evidence log pulled through the console after every result (the backend, where one exists on this
        process's pipe, answers MMIO only: its trace is never read for a record)."""
        super().__init__(out_dir, label=label, binary=binary, **kw)
        if source not in ("emulated", el.SOURCE_KIND):
            raise ss.SessionRefusal(f"unknown source {source!r}")
        self.ps = source == el.SOURCE_KIND
        if self.ps:
            self.evidence = PsEvidence()
        self.token = token or wire.new_token()
        self.page_flags = page_flags
        self.knobs = {"corrupt_replies": corrupt_replies, "drop_replies": drop_replies, "bad_page": bad_page, "garbage_before_tx": garbage_before_tx, "watchdog_fail": watchdog_fail,
                      "wrong_token_lines": wrong_token_lines, "stale_reply_first": stale_reply_first, "seq_gap": seq_gap, "replay_tx": replay_tx}
        self.uboot_epoch = uboot_epoch
        self.host_seq = 0
        self.console = []                      # every console line, both directions, with the trace index: the retained console log
        self.page_words = None
        self.ident = None                      # the IDENT's object once seen
        self.ended = None                      # the END line's payload once seen
        self.stats = {"hb": 0, "nack": 0, "signreq": 0, "signreply": 0, "corrupted": 0, "dropped": 0, "garbage": 0, "wrong_token": 0, "stale": 0,
                      "stale_board": 0, "refused_halted": 0, "replayed": 0}
        self._last_tx_line = None
        self.board_seq = None                  # the last board sequence accepted (R2: a duplicate or decreasing one is refused by name)
        self.board_token = None                # the token of the last board frame accepted (the export after an END before any IDENT is asked under it)
        self.tail_unobtainable = None          # the PS source: why the log's tail beyond the last pull could not be pulled (a terminal END)
        self.findings = []                     # this host's console findings (a non-fresh board frame): recomputed by the verifier from console.jsonl
        self.refused_commands = []             # commands the application NACKed (nothing ran; no record): declared in the transport summary
        self.log_bytes = bytearray()           # the evidence log as pulled (protocol v2), verbatim
        self.pull_infos = []                   # every RING answer with the pulled digest beside it
        self.pull_stats = {"pulls": 0, "chunks": 0, "bad_chunks": 0}
        self._expected_nacks = 0               # NACKs this host provoked on purpose (its declared fault knobs); any other NACK while awaiting a RESULT is the application's refusal
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
        self.console.append({"t": round(time.time(), 6), "i": len(self.evidence.trace), "pcap_n": len(self.evidence.pcap_log), "dir": "host", "line": line.rstrip("\n"), "note": note})

    def _frame_out(self, kind: str, payload: str = "") -> str:
        if self.host_seq >= SEQ_LIMIT:
            raise ss.SessionRefusal("this host's line sequence is exhausted: nothing further is framed")
        self.host_seq += 1 + self.knobs.get("seq_gap", 0)        # a declared gap (a dropped frame) is legitimate: freshness is strict increase, not contiguity
        token = self.token
        if kind in ("RINGINFO", "PULL", "QUIT") and self.ident is None and self.board_token is not None:
            token = self.board_token                              # no IDENT came (the program never read a page): its frames carry its own token (the zero token); the export is asked under it
        return wire.frame(kind, self.host_seq, token, payload)

    def _send(self, line: str):
        """TX / QUIT go to the console as frames (the board host's lines); MMIO replies go to the program's stdin."""
        if line.startswith("TX ") or line == "QUIT":
            if line.startswith("TX ") and self.stats["garbage"] < self.knobs["garbage_before_tx"]:
                self.stats["garbage"] += 1; self._expected_nacks += 1
                self._console_write("B4Q1 TX 0 " + self.token + " AAAA deadbeef\n", "a malformed host line (bad crc): the bench's fault knob")
            if line.startswith("TX ") and self.stats["wrong_token"] < self.knobs["wrong_token_lines"]:
                self.stats["wrong_token"] += 1; self._expected_nacks += 1
                self._console_write(wire.frame("TX", 0, "f" * wire.TOKEN_HEX, line), "a well-formed host line under another session's token: the bench's fault knob")
            if line.startswith("TX ") and self._last_tx_line and self.stats["replayed"] < self.knobs["replay_tx"]:
                self.stats["replayed"] += 1; self._expected_nacks += 0        # the application's NACK is the result this host must see, not one it discounts
                self._console_write(self._last_tx_line, "the previous TX line replayed byte for byte (a duplicate host sequence): the bench's fault knob")
                return
            out = self._frame_out("TX" if line.startswith("TX ") else "QUIT", line if line.startswith("TX ") else "")
            if line.startswith("TX "):
                self._last_tx_line = out
            self._console_write(out)
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
        if self.halted is not None:                       # R3: a halted session signs nothing more, whatever the application asks
            self.stats["refused_halted"] += 1
            self.notary.log.append({"genome_hex": g, "nonce": n, "refused": "the session is halted: " + self.halted})
            self._console_write(self._frame_out("SIGNREPLY", f"REFUSED {req} the session is halted: nothing further is signed without a ruling"))
            return
        if self.stats["dropped"] < self.knobs["drop_replies"]:
            self.stats["dropped"] += 1
            self.console.append({"t": round(time.time(), 6), "i": len(self.evidence.trace), "dir": "host", "line": None, "note": f"SIGNREQ req={req} left unanswered: the bench's fault knob"})
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
            self._console_write(self._frame_out("SIGNREPLY", f"OK {req - 1} " + " ".join("deadbeef" for _ in range(24))), "a stale SIGNREPLY (another request's, garbage words): the bench's fault knob")   # a fresh host sequence, another request id
        line = self._frame_out("SIGNREPLY", reply)
        if self.stats["corrupted"] < self.knobs["corrupt_replies"]:
            self.stats["corrupted"] += 1; self._expected_nacks += 1
            line = line[:-3] + ("1" if line[-3] != "1" else "2") + "\n"      # one CRC character changed: the line must be refused and re-requested
            self._console_write(line, "the SIGNREPLY corrupted in transit: the bench's fault knob")
            return
        self.stats["signreply"] += 1                                           # a reply the application can accept (the corrupted one above is not)
        self._console_write(line)

    def serve(self, awaiting: str = "RESULT") -> dict:
        """Answer the program's MMIO requests and its console lines until a RESULT (or the IDENT at the opening) — or an END."""
        self._awaiting = awaiting
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
                    self.events.append({"i": len(self.evidence.trace), "line": line})
                else:
                    self.events.append({"i": len(self.evidence.trace), "line": "?? " + line})
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
        return self._handle_console_line(line)

    def _handle_console_line(self, line: str) -> dict | None:
        """One console line (without its newline) parsed and dispatched: None when it was a HB / NACK / EV / SIGNREQ (handled), the result
        when it was an IDENT / RESULT / END / RING / CHUNK. Shared by the pipe session and the runner (which owns its own byte buffer)."""
        if True:
            try:
                f = wire.parse(line, None)
                # the session latch: a board frame under another token is refused — except, before any IDENT, a frame under the ZERO token: a
                # program that could not read its page (none written, or corrupted after the host's witness) frames its END under it
                if self.page_words and self.knobs["bad_page"] is None and f["token"] != self.token and not (self.ident is None and f["token"] == wire.ZERO_TOKEN):
                    raise wire.WireError("wrong token")
            except wire.WireError as e:
                self.console.append({"t": round(time.time(), 6), "i": len(self.evidence.trace), "dir": "board", "line": line, "note": f"unparsable: {e}"})
                m = f"board line at line {len(self.console) - 1}: {e}"
                if m not in self.findings:
                    self.findings.append(m)                                   # worded as the verifier's console decoder words it (the agreement rule compares strings)
                raise ss.SessionRefusal(f"the console produced a line this host cannot parse ({e}): {line[:80]}")
            if self.board_seq is not None and f["seq"] <= self.board_seq:        # R2: a duplicate or decreasing board sequence has no effect
                self.stats["stale_board"] += 1
                m = f"console: board frame {f['type']} with sequence {f['seq']} after {self.board_seq}: not fresh, refused"
                self.console.append({"t": round(time.time(), 6), "i": len(self.evidence.trace), "dir": "board", "line": line, "note": "stale sequence: refused"})
                if m not in self.findings:
                    self.findings.append(m)
                self.halt(m)
                return None
            self.board_seq = f["seq"]; self.board_token = f["token"]
            self.console.append({"t": round(time.time(), 6), "i": len(self.evidence.trace), "pcap_n": len(self.evidence.pcap_log), "dir": "board", "line": line, "type": f["type"], "seq": f["seq"]})
            kind, payload = f["type"], f["payload"].decode("utf-8", "replace")
            if kind == "HB":
                self.stats["hb"] += 1
            elif kind == "NACK":
                self.stats["nack"] += 1; self.events.append({"i": len(self.evidence.trace), "line": "NACK " + payload})
                if self._expected_nacks > 0:
                    self._expected_nacks -= 1                              # the NACK this host provoked on purpose
                elif self._awaiting == "RESULT":
                    self.refused_commands.append({"at_console_line": len(self.console) - 1, "reason": payload})
                    return {"status": NACK_STATUS, "reason": "the application refused the command: " + payload, "phase": "?"}
            elif kind == "EV":
                if payload.startswith("MARK "):
                    self.evidence.mark(payload[5:])
                self.events.append({"i": len(self.evidence.trace), "line": payload})
            elif kind == "SIGNREQ":
                self._note_log(payload)
                self._answer_sign(f)
            elif kind == "IDENT":
                ident = json.loads(payload)
                self._note_log(payload)
                return {**ident["open"], "ident": ident}
            elif kind in ("RING", "CHUNK"):
                return {"status": 8, "kind": kind, "text": payload}       # an answer to RINGINFO / PULL
            elif kind == "RESULT":
                self._note_log(payload)
                return json.loads(payload)
            elif kind == "END":
                self.ended = json.loads(payload)
                self._note_log(payload)
                self.events.append({"i": len(self.evidence.trace), "line": "END " + payload})
                return {"status": END_STATUS, "reason": "the session ended: " + self.ended.get("kind", "?") + ": " + self.ended.get("reason", ""), "phase": "?", "end": self.ended}
            else:
                self.events.append({"i": len(self.evidence.trace), "line": f"?? {kind} {payload}"})
        return None

    # ---------------------------------------------------------------- the PS source's hooks
    def _nonce_before_tx(self):
        return None if self.ps else super()._nonce_before_tx()

    def _nonce_from_evidence(self, t_begin: int):
        return el.nonce_read(self.evidence.trace, t_begin)                    # None when the PS read no nonce: the link is then empty and the transaction halts on it

    def _acquire(self, r: dict) -> dict:
        """The PS source: pull the log up to the position the board reported with this result (RESULT.log; the IDENT's; the END's —
        the application answers RINGINFO / PULL after its END, export-only), hold the bytes to the board's digest, re-derive."""
        if not self.ps:
            return r
        if r.get("status") == 5 or not self._transport_alive():
            return r                                                           # the transport is cut: nothing more can be pulled; the records are built from what was pulled
        pos = r.get("log")
        if pos is None and isinstance(r.get("ident"), dict):
            pos = r["ident"].get("log")
        if pos is None and isinstance(r.get("end"), dict):
            pos = r["end"].get("log")
            e = r["end"]
            if e.get("kind") == "PROTOCOL" and "sequence is exhausted" in (e.get("reason") or ""):
                # the terminal END: nothing is framed after it (the emitter's last usable sequence), so the log beyond the last pull is unobtainable — named, never asked for
                self.tail_unobtainable = {"why": "the terminal END (the executing side's sequence is exhausted): no export epilogue exists after it", "end_log": pos, "pulled": len(self.log_bytes)}
                return r
        try:
            info = self.pull_log(upto=pos)
        except ss.SessionRefusal as e:
            self.halt(f"the evidence log could not be pulled: {e}")
            return r
        finally:
            self.evidence.refresh(bytes(self.log_bytes))                   # whatever was pulled is derived — a partial pull (a cut) leaves a partial, consistent derivation
        if pos is not None and info["used"] < pos:
            self.halt(f"the board reported log position {pos} with this result but its log holds {info['used']} bytes")
        return r

    def _backend_manifest(self):
        if not self.ps or self.backend is None:
            return super()._backend_manifest()
        return {**super()._backend_manifest(), "role": "MMIO answered on this process's pipe (the surrogate device): its trace / PCAP log are NOT read for any record — declared knobs only"}

    def _standing(self) -> str:
        if not self.ps:
            return super()._standing()
        return ("the records built from the PS's OWN evidence log (b4q_ring, pulled through the console, held to the board's digest): the carrier-window events, the DMA tuples, the staged words "
                "and the frames the PS read back are what the executing side did and received; a device effect (a frame store, a bus response beyond the PS's own abort flag) is not "
                "witnessed; " + ("the MMIO was answered by an emulation on this host — not silicon, not a physical link" if self.emulated else "the MMIO was a board's — this session's standing is the transport's"))

    def _resolve_console_positions(self):
        """The PS source: a console entry's trace / PCAP position is the one the board's own `log` field maps to (IDENT / SIGNREQ / RESULT /
        END carry the log offset at emission); a line without one (HB, EV, NACK, RING, CHUNK, a host line) takes the last known position."""
        i = p = 0
        for e in self.console:
            if e.get("log") is not None:
                i, p = el.trace_index_at(self.evidence.trace, e["log"]), len([x for x in self.evidence.pcap_log if x["log"] < e["log"]])
            e["i"], e["pcap_n"] = i, p

    def _note_log(self, payload: str):
        """The board's `log` field of this line (its log offset at emission), kept on the console entry for the PS source's positions."""
        try:
            obj = json.loads(payload)
            if isinstance(obj, dict) and type(obj.get("log")) is int:
                self.console[-1]["log"] = obj["log"]
        except ValueError:
            pass

    # ---------------------------------------------------------------- the evidence log (protocol v2): pulled through the console, retained verbatim
    def ring_info(self) -> dict:
        self._console_write(self._frame_out("RINGINFO", ""))
        r = self.serve("RING")
        if r.get("status") != 8 or r.get("kind") != "RING":
            raise ss.SessionRefusal(f"no RING answer: {r}")
        parts = r["text"].split()
        if len(parts) != 5 or parts[0] != "RING":
            raise ss.SessionRefusal(f"malformed RING answer: {r['text'][:80]}")
        return {"used": int(parts[1]), "capacity": int(parts[2]), "overflow": int(parts[3]), "sha256": parts[4]}

    def pull_log(self, chunk: int = 768, upto: int | None = None) -> dict:
        """Pull the evidence log's bytes not yet held (re-asking a chunk that did not arrive whole), hold the whole to the board's
        digest, and retain the raw bytes: the only source of the records on a board (docs/b4q_source_audit.md §3.2). `upto`: the
        position the board reported with a result — the pull stops there when the log grew past it meanwhile (the digest is then over
        the board's whole log as RING reports it, held at the next pull)."""
        import base64
        import hashlib
        info = self.ring_info()
        while len(self.log_bytes) < info["used"]:
            off = len(self.log_bytes); n = min(chunk, info["used"] - off)
            self._console_write(self._frame_out("PULL", f"{off} {n}"))
            try:
                r = self.serve("CHUNK")
            except ss.SessionRefusal as e:
                if "cannot parse" not in str(e) or self.halted is not None and "transport:" in self.halted:
                    raise
                self.pull_stats["bad_chunks"] += 1                          # a CHUNK corrupted in transit (its CRC fails): re-asked, bounded — the one re-askable exchange
                if self.pull_stats["bad_chunks"] > 8:
                    raise ss.SessionRefusal("the log could not be pulled: too many bad chunks")
                continue
            if r.get("status") != 8 or r.get("kind") != "CHUNK":
                raise ss.SessionRefusal(f"no CHUNK answer: {r}")
            parts = r["text"].split(" ")
            if len(parts) != 3 or parts[0] != "CHUNK" or not parts[1].isdigit() or int(parts[1]) != off:
                self.pull_stats["bad_chunks"] += 1
                if self.pull_stats["bad_chunks"] > 8:
                    raise ss.SessionRefusal("the log could not be pulled: too many bad chunks")
                continue
            data = base64.urlsafe_b64decode(parts[2])
            if len(data) != n:
                self.pull_stats["bad_chunks"] += 1
                continue
            self.log_bytes += data; self.pull_stats["chunks"] += 1
        self.pull_stats["pulls"] += 1
        digest = hashlib.sha256(bytes(self.log_bytes[:info["used"]])).hexdigest()
        info["pulled_sha256"] = digest; info["digest_equal"] = (digest == info["sha256"])
        if upto is not None:
            info["upto"] = upto
        self.pull_infos.append(info)
        if not info["digest_equal"]:
            self.halt(f"the pulled evidence log does not hash to the board's digest ({digest[:12]} vs {info['sha256'][:12]})")
        elif info["overflow"]:
            self.halt("the evidence log overflowed on the board: nothing after the overflow is observed; nothing further is signed")   # named; the application NACKs the next TX too
        return info

    def drain_after_end(self, cap: int = 200000) -> dict:
        """After an END: keep answering the program's MMIO requests (nothing on the console) until it exits or `cap` requests passed — the
        owner's observation method for the effect boundary: whatever the program still does after its END lands in the trace / PCAP log."""
        n = 0
        while n < cap:
            line = self._readline("mmio")
            if line is None:
                break
            n += 1
            if line.startswith("R "):
                data, resp, x = self.backend.rd32(int(line[2:], 16)); self._send(f"{data:08x} {resp}")
            elif line.startswith("W "):
                a, d = line[2:].split(); self._send(str(self.backend.wr32(int(a, 16), int(d, 16))))
            elif line.startswith("HALT "):
                self.events.append({"i": len(self.evidence.trace), "line": line})
        return {"mmio_after_end": n}

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                if self.ended is None:
                    self._send("QUIT")
                    r = self.serve("END")                 # the END COMPLETED (or whatever the program ends with)
                    if r.get("status") != END_STATUS:
                        self.events.append({"i": len(self.evidence.trace), "line": "?? a RESULT where the END was expected"})
                    else:
                        if self.ps:
                            self._acquire(r)              # the PS source: the log's tail at the END's own position, through the export epilogue
                        self._console_write(self._frame_out("QUIT", ""))   # the epilogue closed by the host (under either source: nothing is left spinning on a budget)
                elif self.proc.poll() is None:
                    self._console_write(self._frame_out("QUIT", ""))       # an END already seen (a stop, an idle bound): the epilogue closed the same way
            except (BrokenPipeError, ValueError, OSError, ss.SessionRefusal):
                pass
            try:
                self.proc.stdin.close()
            except OSError:
                pass
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
        if self.proc is not None:
            try:                                                   # the harness's last stdout line (HALT kicks=N: the platform's own count), whether it exited on its own or on QUIT
                while True:
                    line = self._readline("mmio")
                    if line is None:
                        break
                    self.events.append({"i": len(self.evidence.trace), "line": line if line.startswith("HALT ") else "?? " + line})
            except OSError:
                pass
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
        r = self.serve("IDENT")
        if r.get("status") == END_STATUS:                 # the program ended before an IDENT (a bad page, a watchdog that could not be armed)
            r = {"status": 1, "reason": r["reason"], "startup_readback": "", "end": r.get("end")}
        r = self._acquire(r)
        self.ident = r.get("ident")
        if self.ps and self.ident is not None and type(self.ident.get("open", {}).get("timing")) is int:
            self.timing = {**rm.decode_timing(self.ident["open"]["timing"]), "pulse": (self.timing or {}).get("pulse", 2)}   # the timing word the PS read at its opening (the pulse count is the carrier design's constant, b4q_emu.TIMING)
        so = self._opened(r)
        if self.ident is not None:
            findings = so["findings"]
            if self.ident.get("protocol") != PROTOCOL:
                findings.append(f"the image speaks {self.ident.get('protocol')!r}, not the protocol this host implements ({PROTOCOL})")
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

    def transaction(self, kind: str, genome: int, stimulus: list, task: dict | None = None) -> dict:
        """As the parent's; a command the application REFUSED by name (a NACK where the RESULT was expected: a stale sequence, a
        halted session, a malformed command) ran nothing and is not a transaction record — it stays in the console log and the
        transport summary (and the session halts on it, as on any unsealed outcome); the previous close remains the last one."""
        prev_x, n_before = self.prev_x, len(self.records)
        e = super().transaction(kind, genome, stimulus, task)
        if e["firmware"].get("status") == NACK_STATUS and len(self.records) == n_before + 1:
            self.records.pop(); self.seq -= 1; self.prev_x = prev_x
        return e

    def write(self) -> dict:
        if self.ps:
            self._resolve_console_positions()
            last = self.pull_infos[-1] if self.pull_infos else None
            self.source = {"kind": el.SOURCE_KIND, "raw": "raw/evidence_log.bin", "bytes": len(self.log_bytes), "sha256": el.digest(bytes(self.log_bytes)), "records": self.evidence.records,
                           "board": ({"used": last["used"], "capacity": last["capacity"], "overflow": last["overflow"], "sha256": last["sha256"]} if last else None),
                           "digest_equal": bool(last and last["digest_equal"] and last["used"] == len(self.log_bytes)),
                           "end_log": (self.ended or {}).get("log"), "end_log_sha256": (self.ended or {}).get("log_sha256"), "tail_unobtainable": self.tail_unobtainable,
                           "adapter": "host/b4q_evidence_log.py", "adapter_sha256": ss.sha256_file(R / "host/b4q_evidence_log.py"),
                           "derived": ["trace.jsonl", "pcap_log.jsonl", "accesses.jsonl"], "host_marks": self.evidence.host_marks, "pull_stats": self.pull_stats}
        m = super().write()
        (self.out / "console.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.console))
        if self.log_bytes or self.pull_infos:
            (self.out / "raw").mkdir(exist_ok=True)
            (self.out / "raw/evidence_log.bin").write_bytes(bytes(self.log_bytes))
            (self.out / "raw/pulls.json").write_text(json.dumps({"infos": self.pull_infos, "stats": self.pull_stats}, indent=1) + "\n")
        m["transport"] = {"kind": "console-emulated", "standing": "the board application's host harness on a pipe: its framed console lines are the bytes the image would put on UART1; not a board, not on-target evidence",
                          "protocol": PROTOCOL, "token": self.token, "page_words": [f"{w:08x}" for w in (self.page_words or [])], "page_flags": self.page_flags,
                          "time_origin": "console entries' `t`: this host's wall clock (time.time()) at the line's receipt / send — a host timestamp, never a device time",
                          "knobs": self.knobs, "stats": self.stats, "end": self.ended, "ident": self.ident, "console_lines": len(self.console),
                          "findings": list(self.findings), "host_seq_last": self.host_seq, "board_seq_last": self.board_seq, "refused_commands": self.refused_commands,
                          "evidence_log": {"pulled_bytes": len(self.log_bytes), "pulls": self.pull_infos, "stats": self.pull_stats} if (self.log_bytes or self.pull_infos) else None}
        (self.out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
        return m
