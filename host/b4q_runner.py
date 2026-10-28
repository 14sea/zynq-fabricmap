#!/usr/bin/env python3
"""B4Q — the PHYSICAL RUNNER (host-only preparation, the runner unit of 2026-10-28): the B4Q console session driven over a serial
endpoint — a PTY to the device surrogate (host/b4q_device_surrogate.py) in this unit; a board's UART1 on a later, separately
authorised bring-up — with the records built from the PS's OWN evidence log (source `ps-evidence-log-v1`, host/b4q_evidence_log.py,
docs/b4q_source_audit.md §3), never from an emulation this process could read.

What the runner does, in order, each step retained with its witness in uboot.json / raw/console.bin (unconditionally, also on a stop):
  1. the U-Boot prompt: the boot banner awaited (or a bare CR answered by the prompt), autoboot broken with the board's break key
     ('d' on the EBAZ4205's miner U-Boot — not Space / Ctrl-C), the prompt held to PROMPT_RE at the very end of the reply;
  2. the image: `loady <addr>` + YMODEM-1K (this host's own sender, host/b4q_ymodem.py), then the LOAD WITNESS — U-Boot's `crc32`
     over the loaded range held to the host's crc32 of the file (a different witness from the IDENT's `app_image_sha_lo32` echo,
     which is the PAGE's word read back by the program, not the loaded bytes);
  3. the identity page: the PL nonce read with `md.l` (the host's own view before `go`), the 24 words written with `mw.l`, read back
     with `md.l` and held equal (the PAGE WITNESS);
  4. `go <addr>`: the console is the application's from here — the ConsoleSession protocol (IDENT, TX / SIGNREQ / RESULT, RINGINFO /
     PULL after every result, QUIT, the END, the export epilogue); a boot banner on the console mid-session is a reset, named;
     silence beyond the host's bound is a named stop (the HOST may use a clock; the application counts polls).

Granted here: local files and emulated / PTY endpoints only. A serial device path that is not a PTY makes the transport kind
`uart-board`, which host/b4q_verify.py refuses to verify as a host-only archive (the board claims are not granted); nothing in
this file powers, provisions, resets or flashes anything."""
from __future__ import annotations

import json
import os
import re
import select
import sys
import time
import zlib
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_regmap as rm  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_console_session as cs  # noqa: E402
import b4q_evidence_log as el  # noqa: E402
import b4q_session as ss  # noqa: E402
import b4q_wire as wire  # noqa: E402
import b4q_ymodem as ym  # noqa: E402

IMAGE = R / "build/b4q_image/b4q_app_v2.bin"
LOAD_ADDR = 0x02000000
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)> \Z")                                      # the prompt WITH its trailing space, at the very end (board_transport_soak)
BOOT_BANNER_RE = re.compile(rb"^(?:U-Boot SPL|U-Boot \d|Trying to boot from|Model: Ebang)", re.M)
BANNER_LINE_RE = re.compile(r"^(?:U-Boot SPL|U-Boot \d|Trying to boot from|Model: Ebang)")
MD_LINE_RE = re.compile(rb"^([0-9a-fA-F]{8}):((?: [0-9a-fA-F]{8}){1,4}) +(.*)$")
CRC_RE = re.compile(rb"==> ([0-9a-fA-F]{8})")
READY_RE = re.compile(rb"## Ready for binary \(ymodem\) download")
TOTAL_RE = re.compile(rb"## Total Size = 0x([0-9a-fA-F]+)")
BREAK_KEY = b"d"


class TransportStop(Exception):
    """A named stop of the control plane or the transport: the step, what was expected, what came (retained)."""


class Port:
    """A serial endpoint: a PTY (the surrogate) or a tty device. Every byte received is retained in `rx_log`; every byte sent in `tx_log`."""

    def __init__(self, path: str, baud: int = 115200):
        self.path = path
        self.real = os.path.realpath(path)
        self.kind = "console-pty-surrogate" if self.real.startswith("/dev/pts/") else "uart-board"
        self.fd = os.open(self.real, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
        self.rx_log, self.tx_log = bytearray(), bytearray()
        if self.kind == "uart-board":
            import serial  # pyserial: the line settings of a real tty (8N1, no flow control)
            os.close(self.fd)
            self.ser = serial.Serial(self.real, baudrate=baud, timeout=0, write_timeout=5)
            self.fd = self.ser.fileno()
        else:
            self.ser = None
            import termios
            import tty
            try:
                tty.setraw(self.fd, termios.TCSANOW)                                      # a PTY slave: raw, no echo, no CR/LF translation; TCSANOW: nothing already queued (a banner) is flushed
                a = termios.tcgetattr(self.fd); a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 0
                termios.tcsetattr(self.fd, termios.TCSANOW, a)
            except termios.error:
                pass
        os.set_blocking(self.fd, False)

    def read(self, timeout: float) -> bytes:
        r, _, _ = select.select([self.fd], [], [], timeout)
        if not r:
            return b""
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return b""
        except OSError as e:
            raise TransportStop(f"the port closed: {e}")
        if not data:
            raise TransportStop("the port closed (EOF)")
        self.rx_log += data
        return data

    def write(self, data: bytes):
        self.tx_log += data
        off = 0
        while off < len(data):
            _, w, _ = select.select([], [self.fd], [], 5)
            if not w:
                raise TransportStop("the port did not accept bytes for 5 s")
            try:
                off += os.write(self.fd, data[off:])
            except BlockingIOError:
                continue

    def close(self):
        try:
            if self.ser is not None:
                self.ser.close()
            else:
                os.close(self.fd)
        except OSError:
            pass


class UBoot:
    """The U-Boot control plane over a Port: every exchange retained as a step {what, sent, reply (text), witness, ok}."""

    def __init__(self, port: Port, steps: list):
        self.port, self.steps = port, steps

    def _step(self, what: str, **kw) -> dict:
        s = {"what": what, "t": round(time.time(), 3), **kw}
        self.steps.append(s)
        return s

    def read_until(self, pattern, timeout: float, tail: int = 4096) -> tuple[bytes, bool]:
        """Bytes until `pattern` matches the reply's tail (PROMPT_RE: the last bytes), or the timeout."""
        buf = bytearray()
        deadline = time.time() + timeout
        while time.time() < deadline:
            buf += self.port.read(min(0.05, max(0.0, deadline - time.time())))
            if pattern.search(bytes(buf[-tail:])):
                return bytes(buf), True
        return bytes(buf), False

    def get_prompt(self, boot_timeout: float = 60.0, break_s: float = 20.0) -> dict:
        """The prompt from any state: a bare CR first (a prompt already waiting answers with another prompt); else the break key
        hammered for `break_s` (the autoboot countdown of a booting U-Boot); the prompt held to PROMPT_RE at the very end."""
        s = self._step("prompt")
        self.port.write(b"\r")                                                           # a prompt already waiting answers with another prompt; a surrogate booting on input starts its banner
        reply, ok = self.read_until(PROMPT_RE, 0.5)
        banner = bool(BOOT_BANNER_RE.search(reply))
        if not ok:
            deadline = time.time() + break_s
            while time.time() < deadline and not ok:
                self.port.write(BREAK_KEY)                                                # the break key hammered through the autoboot countdown (the miner U-Boot's 'd')
                more, ok = self.read_until(PROMPT_RE, 0.1)
                reply += more
                banner = banner or bool(BOOT_BANNER_RE.search(reply))
        s.update({"reply": reply.decode("utf-8", "replace")[-600:], "banner_seen": banner, "ok": ok})
        if not ok:
            raise TransportStop("no U-Boot prompt: " + ("a boot banner was seen but the autoboot was not broken" if banner else "nothing recognisable on the console"))
        return s

    def cmd(self, line: str, timeout: float = 5.0, what: str | None = None) -> bytes:
        """One command: the line + CR, the reply up to the next prompt (the echo of the command stripped), retained."""
        s = self._step(what or "cmd", sent=line)
        self.port.write(line.encode("ascii") + b"\r")
        reply, ok = self.read_until(PROMPT_RE, timeout)
        body = reply
        k = body.find(b"\n")
        if k >= 0 and body[:k].strip().endswith(line.encode("ascii")):
            body = body[k + 1:]
        body = PROMPT_RE.sub(b"", body)
        s.update({"reply": body.decode("utf-8", "replace")[-2000:], "ok": ok})
        if not ok:
            raise TransportStop(f"no prompt after `{line}` within {timeout} s")
        return body

    def md_l(self, addr: int, n: int) -> list[int]:
        body = self.cmd(f"md.l {addr:08x} {n:x}", what="md.l")
        words = []
        for ln in body.replace(b"\r", b"").split(b"\n"):
            m = MD_LINE_RE.match(ln.strip())
            if m:
                words += [int(w, 16) for w in m.group(2).split()]
        self.steps[-1]["words"] = [f"{w:08x}" for w in words]
        if len(words) != n:
            raise TransportStop(f"md.l {addr:#010x} {n}: {len(words)} words parsed, not {n}")
        return words

    def mw_l(self, addr: int, value: int):
        self.cmd(f"mw.l {addr:08x} {value:08x} 1", what="mw.l")

    def crc32(self, addr: int, length: int) -> int:
        body = self.cmd(f"crc32 {addr:08x} {length:x}", timeout=20, what="crc32")
        m = CRC_RE.search(body)
        if not m:
            raise TransportStop("crc32: no '==> xxxxxxxx' in the reply")
        v = int(m.group(1), 16)
        self.steps[-1]["crc32"] = f"{v:08x}"
        return v

    def loady(self, addr: int, data: bytes, name: str, timeout: float = 600.0) -> dict:
        """`loady <addr>` then this host's YMODEM-1K sender on the same port; U-Boot's `## Total Size` held to the file's length."""
        s = self._step("loady", sent=f"loady {addr:08x}", bytes=len(data))
        self.port.write(f"loady {addr:08x}\r".encode("ascii"))
        reply, ok = self.read_until(READY_RE, 5.0)
        if not ok:
            s.update({"reply": reply.decode("utf-8", "replace")[-400:], "ok": False})
            raise TransportStop("loady: U-Boot did not announce the ymodem download")
        try:
            stats = ym.send(self.port, data, name, timeout=timeout)
        except ym.YModemError as e:
            s.update({"ok": False, "ymodem": str(e)})
            tail, _ = self.read_until(PROMPT_RE, 3.0)
            s["reply"] = tail.decode("utf-8", "replace")[-400:]
            raise TransportStop(f"loady: the ymodem transfer failed: {e}")
        reply, ok = self.read_until(PROMPT_RE, 10.0)
        m = TOTAL_RE.search(reply)
        total = int(m.group(1), 16) if m else None
        s.update({"ymodem": stats, "reply": reply.decode("utf-8", "replace")[-400:], "total": total, "ok": ok and total == len(data)})
        if not ok:
            raise TransportStop("loady: no prompt after the transfer")
        if total != len(data):
            raise TransportStop(f"loady: U-Boot reports {total} bytes received, the file has {len(data)}")
        return s

    def go(self, addr: int) -> dict:
        s = self._step("go", sent=f"go {addr:08x}")
        self.port.write(f"go {addr:08x}\r".encode("ascii"))
        reply, ok = self.read_until(re.compile(rb"## Starting application"), 5.0)
        s.update({"reply": reply.decode("utf-8", "replace")[-300:], "ok": ok})
        if not ok:
            raise TransportStop("go: U-Boot did not start the application")
        return s


class RunnerSession(cs.ConsoleSession):
    """The console session over a Port (no MMIO side: the device answers its own), source = the PS's evidence log. The page is
    written through U-Boot (mw.l) before `go`, never into a backend; the nonce the page carries is the one `md.l` showed."""

    def __init__(self, out_dir: Path, port: Port, uboot: UBoot, image: Path = IMAGE, silence_s: float = 30.0, label: str = "B4Q-runner", **kw):
        kw.setdefault("source", el.SOURCE_KIND)
        super().__init__(out_dir, label=label, binary=image, **kw)
        self.port, self.uboot, self.silence_s = port, uboot, silence_s
        self.backend = None                                                   # NO backend in this process: nothing to read a board fact from
        self.evidence = cs.PsEvidence() if self.ps else self.evidence
        self.emulated = port.kind != "uart-board"
        self.runner = {"port": port.path, "port_real": port.real, "kind": port.kind, "image": str(image.relative_to(R)) if image.is_relative_to(R) else str(image),
                       "image_sha256": self.instrument["image_sha256"], "load_addr": LOAD_ADDR, "stops": [], "silence_s": silence_s}
        self._fds = {"h2c_w": port.fd, "c2h_r": port.fd}
        self._cut = False
        self.page_nonce = None

    def _transport_alive(self) -> bool:
        return not self._cut

    # ---------------------------------------------------------------- the control plane before `go`
    def load_image(self) -> dict:
        data = self.binary.read_bytes()
        st = self.uboot.loady(LOAD_ADDR, data, self.binary.name)
        host_crc = zlib.crc32(data) & 0xFFFFFFFF
        dev_crc = self.uboot.crc32(LOAD_ADDR, len(data))
        w = {"host_crc32": f"{host_crc:08x}", "uboot_crc32": f"{dev_crc:08x}", "equal": host_crc == dev_crc, "bytes": len(data), "ymodem": st.get("ymodem")}
        self.runner["load_witness"] = w
        if not w["equal"]:
            raise TransportStop(f"load witness: U-Boot's crc32 {dev_crc:08x} over the loaded range is not the file's {host_crc:08x}: the image in DDR is not the file (not run)")
        return w

    def write_page(self):
        """The page through U-Boot: the PL nonce read first (md.l over the carrier window), the 24 words written (mw.l), read back (md.l)."""
        lo, hi = self.uboot.md_l(bk.AXI_BASE + rm.NONCE_LO, 1)[0], self.uboot.md_l(bk.AXI_BASE + rm.NONCE_HI, 1)[0]
        self.page_nonce = (hi << 32) | lo
        bad = self.knobs["bad_page"]
        words = wire.page_words(self.token, self.uboot_epoch, self.instrument["image_sha256"], self.base["bitstream_sha256"], self.page_nonce, 0, self.page_flags)
        if bad == "checksum":
            words[-1] ^= 1
        elif bad == "magic":
            words[0] = 0
        elif bad == "reserved":
            words[20] = 7
        elif bad == "absent":
            words = [0] * wire.PAGE_WORDS
        for i, w in enumerate(words):
            self.uboot.mw_l(wire.PAGE_ADDR + 4 * i, w)
        back = self.uboot.md_l(wire.PAGE_ADDR, wire.PAGE_WORDS)
        self.runner["page_witness"] = {"nonce_md": f"{self.page_nonce:016x}", "written": [f"{w:08x}" for w in words], "read_back": [f"{w:08x}" for w in back], "equal": back == words}
        if back != words:
            raise TransportStop("page witness: the page read back with md.l is not the one written with mw.l (not run)")
        self.page_words = words

    def start(self):
        """loady + witness, the page + witness, go: the console is the application's after this."""
        if self.page_words is None:
            self.load_image()
            self.write_page()
        self.uboot.go(LOAD_ADDR)
        self.proc = None

    # ---------------------------------------------------------------- the transport: the port alone
    def _console_write(self, line: str, note: str = ""):
        self.port.write(line.encode("utf-8"))
        self.console.append({"i": len(self.evidence.trace), "pcap_n": len(self.evidence.pcap_log), "dir": "host", "line": line.rstrip("\n"), "note": note})

    def _readline(self, which: str) -> str | None:
        if which == "mmio":
            return None
        while b"\n" not in self._con_buf:
            chunk = self.port.read(self.silence_s)
            if not chunk:
                self._stop_transport(f"the console was silent for {self.silence_s} s")
            self._con_buf += chunk
        line, _, rest = self._con_buf.partition(b"\n")
        self._con_buf = rest
        return line.decode("utf-8", "replace")

    def _stop_transport(self, why: str):
        self._cut = True
        self.runner["stops"].append({"t": round(time.time(), 3), "why": why, "awaiting": getattr(self, "_awaiting", None)})
        if self.interrupted is None:
            self.interrupted = {"transport": why, "console_line": len(self.console)}   # the session is cut by its transport: the records / the verifier treat it as the interruption it is
        self.halt("transport: " + why)
        raise ss.SessionRefusal(why)

    def _console_line(self) -> dict | None:
        if b"\n" not in self._con_buf:
            chunk = self.port.read(self.silence_s)
            if not chunk:
                self._stop_transport(f"the console was silent for {self.silence_s} s while awaiting {getattr(self, '_awaiting', '?')}")
            self._con_buf += chunk
            if b"\n" not in self._con_buf:
                return None
        # a boot banner line on the application's console: the PS reset (a watchdog, a power event) — the session is cut, by name
        head = self._con_buf.split(b"\n", 1)[0].decode("utf-8", "replace").strip("\r")
        if BANNER_LINE_RE.match(head):
            self.console.append({"i": len(self.evidence.trace), "dir": "board", "line": head, "note": "a boot banner: the PS reset mid-session"})
            self._con_buf = self._con_buf.split(b"\n", 1)[1]
            self._stop_transport("a boot banner on the console mid-session: the PS reset (the session is cut; its log is unobtainable)")
        if not head.startswith(wire.MAGIC + " ") and head.strip() == "":
            self._con_buf = self._con_buf.split(b"\n", 1)[1]                   # an empty line (U-Boot's CR LF after `go`): not a console line
            return None
        return super()._console_line()

    def serve(self, awaiting: str = "RESULT") -> dict:
        self._awaiting = awaiting
        while True:
            r = self._console_line()
            if r is not None:
                return r

    def drain_after_end(self, cap: int = 200000) -> dict:
        return {"mmio_after_end": None}

    def stop(self):
        if self._cut:
            return
        try:
            if self.ended is None:
                self._send("QUIT")
                r = self.serve("END")
                if r.get("status") == cs.END_STATUS:
                    self._acquire(r)                                           # the tail of the log (the END's own position) through the export epilogue
            self._console_write(self._frame_out("QUIT", ""))                      # the export epilogue closed (a QUIT after the END: the verifier's phase rule)
        except (ss.SessionRefusal, TransportStop, OSError):
            pass

    def write(self) -> dict:
        self.runner["uboot_steps"] = self.uboot.steps
        m = super().write()
        m["transport"]["kind"] = self.port.kind
        m["transport"]["standing"] = ("the board application's host harness behind the device surrogate's emulated U-Boot on a PTY: the bytes are the ones the image would put on UART1, the MMIO is an emulation in another process this host never reads; not a board"
                                      if self.port.kind == "console-pty-surrogate" else "a board's UART: the claims of such an archive are not granted to this verifier version")
        m["transport"]["runner"] = self.runner
        (self.out / "raw").mkdir(exist_ok=True)
        (self.out / "raw/console.bin").write_bytes(bytes(self.port.rx_log))
        (self.out / "raw/console_tx.bin").write_bytes(bytes(self.port.tx_log))
        (self.out / "uboot.json").write_text(json.dumps(self.runner, indent=1) + "\n")
        (self.out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
        return m


def run(port_path: str, out: Path, body, image: Path = IMAGE, silence_s: float = 30.0, boot_timeout: float = 60.0, break_s: float = 20.0, label: str = "B4Q-runner", **kw) -> dict:
    """One runner session: the prompt, the image, the page, go, the body (transactions), the stop; everything retained, also on a stop."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    steps = []
    port = Port(port_path)
    uboot = UBoot(port, steps)
    s = None
    stop = None
    t0 = time.time()
    try:
        uboot.get_prompt(boot_timeout=boot_timeout, break_s=break_s)
        s = RunnerSession(out, port, uboot, image=image, silence_s=silence_s, label=label, **kw)
        extra = body(s) or {}
    except (TransportStop, ss.SessionRefusal) as e:
        stop = {"kind": type(e).__name__, "why": str(e)}
        extra = {}
    finally:
        if s is not None:
            s.stop()
    if s is None:
        (out / "raw").mkdir(exist_ok=True)
        (out / "raw/console.bin").write_bytes(bytes(port.rx_log)); (out / "raw/console_tx.bin").write_bytes(bytes(port.tx_log))
        (out / "uboot.json").write_text(json.dumps({"steps": steps, "stop": stop, "port": port_path, "kind": port.kind}, indent=1) + "\n")
        port.close()
        summary = {"label": label, "wall_s": round(time.time() - t0, 3), "stop": stop, "opened": False, "records": []}
        (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
        return summary
    if stop and stop["why"] not in [x["why"] for x in s.runner["stops"]]:
        s.runner["stops"].append({"t": round(time.time(), 3), "why": stop["why"], "kind": stop["kind"]})
    m = s.write()
    port.close()
    summary = {"label": label, "wall_s": round(time.time() - t0, 3), "stop": stop, "opened": s.session_open is not None and s.session_open["record"]["status"] == "open",
               "records": m["records"], "chain_findings": m["chain_findings"], "halted": s.halted, "end": s.ended, "stats": s.stats, "console_lines": len(s.console),
               "load_witness": s.runner.get("load_witness"), "page_witness": {k: v for k, v in (s.runner.get("page_witness") or {}).items() if k in ("equal", "nonce_md")},
               "source": m.get("source") and {k: m["source"][k] for k in ("bytes", "records", "digest_equal")}, "transport_stops": s.runner["stops"], **extra}
    (out / "summary.json").write_text(json.dumps(summary, indent=1) + "\n")
    return summary
