#!/usr/bin/env python3
"""B4Q — the PHYSICAL RUNNER (host-only preparation, the runner unit of 2026-10-28; repaired after the owner's HOLD on dad9e4de):
the B4Q console session driven over a serial endpoint — a PTY to the device surrogate (host/b4q_device_surrogate.py) in this unit;
a board's UART1 on a later, separately authorised bring-up — with the records built from the PS's OWN evidence log (source
`ps-evidence-log-v1`, host/b4q_evidence_log.py, docs/b4q_source_audit.md §3), never from an emulation this process could read:
this process constructs NO backend (`make_backend=False`).

What the runner does, in order, each step retained with its witness in uboot.json and the raw streams (raw/console.bin,
raw/console_tx.bin) — persisted after every step and before `go`, unconditionally, also on a stop or a programming error:
  0. ADMISSION under an explicit ExecutionContext (R3): the selected file IS the pinned image (its sha256 equals the pin given
     independently of the file); the board's identity from U-Boot's banner (its `Model:` line among the permitted models, its
     DRAM at least what the image's map needs — the page, the buffers and the log lie above 256 MiB); the carrier's VARIANT word
     at 0x43C02034 is the pinned carrier's BEFORE any other PL access; the SLCR FPGA0_CLK_CTRL word recorded (held when expected).
     A PTY endpoint is a host fixture (the context says so), never physical provenance.
  1. the U-Boot prompt: a bare CR first, then the break key hammered through an autoboot countdown ('d' for the EBAZ4205's miner
     U-Boot — the mainline 4203 U-Boot takes any key); the prompt held to PROMPT_RE at the very end of the reply;
  2. the image: `loady <addr>` + YMODEM-1K (this host's own sender, host/b4q_ymodem.py, one cumulative deadline), then the LOAD
     WITNESS — U-Boot's `crc32` over EXACTLY the loaded range held to the host's crc32 of the file (a different witness from the
     IDENT's `app_image_sha_lo32` echo, which is the PAGE's word read back by the program);
  3. the identity page: the PL nonce read with `md.l` (the host's own view before `go`), the 24 words written with `mw.l`, read back
     with `md.l` at exactly the page's addresses and held equal (the PAGE WITNESS);
  4. `go <addr>` — the execution phase persisted BEFORE the command is issued; the console is the application's from here: the
     ConsoleSession protocol (IDENT, TX / SIGNREQ / RESULT, RINGINFO / PULL after every result, QUIT, the END, the export
     epilogue); every byte received stays in ONE receive buffer handed from reader to reader (R2): nothing after a matched
     prompt / banner / transfer end is lost; a boot banner mid-session is a reset, named; silence beyond the host's bound is a
     named stop (the HOST may use a clock; the application counts polls).

Granted here: local files and emulated / PTY endpoints only. A serial device path that is not a PTY makes the transport kind
`uart-board`; nothing in this file powers, provisions, resets or flashes anything.

    python3 host/b4q_runner.py --port /tmp/b4q-pty --out DIR --stage control-plane|open|transaction [--image F --image-pin SHA ...]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import select
import sys
import time
import zlib
from dataclasses import asdict, dataclass
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
PIN_FILE = R / "evidence/b4/unit_b4q_runner_2026_10_28/build_evidence.json"          # the pin of record: the build evidence's image sha256, independent of the file selected
LOAD_ADDR = 0x02000000
SLCR_FPGA0_CLK_CTRL = 0xF8000170
VARIANT_ADDR = bk.AXI_BASE + rm.VARIANT                                                # 0x43C02034 (the owner's R5: not the window base)
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)> \Z")                                     # the prompt WITH its trailing space, at the very end (board_transport_soak)
BOOT_BANNER_RE = re.compile(rb"^(?:U-Boot SPL|U-Boot \d|Trying to boot from|Model: Ebang)", re.M)
BANNER_LINE_RE = re.compile(r"^(?:U-Boot SPL|U-Boot \d|Trying to boot from|Model: Ebang)")
MODEL_RE = re.compile(rb"^Model: (.+?)\r?$", re.M)
DRAM_RE = re.compile(rb"^DRAM: +(?:ECC [a-z]+ )?(\d+) MiB", re.M)
BDINFO_SIZE_RE = re.compile(rb"-> size += 0x([0-9a-fA-F]+)")
MD_LINE_RE = re.compile(rb"^([0-9a-fA-F]{8}):((?: [0-9a-fA-F]{8}){1,4}) +(.*)$")
CRC_RE = re.compile(rb"crc32 for ([0-9a-fA-F]{8}) \.\.\. ([0-9a-fA-F]{8}) ==> ([0-9a-fA-F]{8})")
READY_RE = re.compile(rb"## Ready for binary \(ymodem\) download")
TOTAL_RE = re.compile(rb"## Total Size = 0x([0-9a-fA-F]+)")
STARTING_RE = re.compile(rb"## Starting application[^\n]*\n")
BREAK_KEY = b"d"
UBOOT_SCHEMA = ("b4q_runner_uboot", 2)
PHASES = ("init", "prompt", "admitted", "loaded", "page-written", "pre-go", "go-issued", "application", "ended", "stopped")


class TransportStop(Exception):
    """A named stop of the control plane or the transport: the step, what was expected, what came (retained)."""


class AdmissionStop(TransportStop):
    """A named refusal BEFORE anything execution-sensitive: the file is not the pinned image, the board is not a permitted target, the
    carrier is not the pinned one."""


# ---------------------------------------------------------------- the execution context (R3)
@dataclass
class ExecutionContext:
    """The trusted context a run executes under — given to the runner, never derived from what the device says or from the selected
    file: the pinned image's sha256 (from the build evidence of record, or an explicit pin), the permitted board models, the DRAM the
    image's map needs, the pinned carrier's variant word, the expected SLCR FPGA0_CLK_CTRL word (when known), the granted role. A
    PTY endpoint is declared a host FIXTURE in `fixture` (its profile); a fixture is never physical provenance."""
    image_sha256: str
    image_path: str = str(IMAGE)
    pin_source: str = "explicit"
    board_models: tuple = ("Ebang EBAZ4203",)
    dram_min_mib: int = 512                        # the page (0x10440000), the buffers (0x10200000..) and the log (0x10800000..) lie above 256 MiB
    variant_word: int = rm.VARIANT_WORD
    fclk0_ctrl_expected: int | None = None         # None: recorded, not held (the bring-up's M3 pins it); an int: held equal
    load_addr: int = LOAD_ADDR
    role: str = "bringup-rehearsal"
    fixture: dict | None = None                    # {"profile": ..., "note": ...} when the endpoint is a PTY (set by the runner from the port kind)

    @staticmethod
    def pinned(image: Path = IMAGE, pin_file: Path = PIN_FILE, **kw) -> "ExecutionContext":
        """The context whose image pin comes from the build evidence of record (never from the file)."""
        if not pin_file.is_file():
            raise AdmissionStop(f"no image pin of record: {pin_file} is absent (an explicit --image-pin is the alternative)")
        ev = json.loads(pin_file.read_text())
        sha = ev.get("image", {}).get("sha256")
        if not isinstance(sha, str) or len(sha) != 64:
            raise AdmissionStop("the build evidence of record carries no image sha256")
        kw.setdefault("image_path", str(image))
        return ExecutionContext(image_sha256=sha, pin_source=f"build evidence {pin_file.relative_to(R) if pin_file.is_relative_to(R) else pin_file}", **kw)


# ---------------------------------------------------------------- the port: ONE receive buffer handed from reader to reader (R2)
class Port:
    """A serial endpoint: a PTY (the surrogate: a host fixture) or a tty device. Every byte received is appended to `buf` (and to
    `rx_log`, retained); readers CONSUME from `buf` only up to the protocol boundary they matched and leave the rest for the next
    reader — a coalesced read holding the end of one phase and the start of the next loses nothing. Every byte sent is in `tx_log`."""

    def __init__(self, path: str, baud: int = 115200):
        self.path = path
        self.real = os.path.realpath(path)
        self.kind = "console-pty-surrogate" if self.real.startswith("/dev/pts/") else "uart-board"
        self.rx_log, self.tx_log = bytearray(), bytearray()
        self.buf = bytearray()
        self.closed = False
        self.fd = os.open(self.real, os.O_RDWR | os.O_NOCTTY | os.O_NONBLOCK)
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
                tty.setraw(self.fd, termios.TCSANOW)                                      # raw, no echo, no CR/LF translation; TCSANOW: nothing already queued (a banner) is flushed
                a = termios.tcgetattr(self.fd); a[6][termios.VMIN] = 0; a[6][termios.VTIME] = 0
                termios.tcsetattr(self.fd, termios.TCSANOW, a)
            except termios.error:
                pass
        os.set_blocking(self.fd, False)

    def fill(self, timeout: float) -> int:
        """Wait up to `timeout` s for bytes; append them to `buf` (and `rx_log`); the number appended (0 on a timeout)."""
        if self.closed:
            raise TransportStop("the port is closed")
        r, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not r:
            return 0
        try:
            data = os.read(self.fd, 65536)
        except BlockingIOError:
            return 0
        except OSError as e:
            raise TransportStop(f"the port closed: {e}")
        if not data:
            raise TransportStop("the port closed (EOF)")
        self.rx_log += data
        self.buf += data
        return len(data)

    def read(self, timeout: float) -> bytes:
        """The ymodem interface: the bytes available (from `buf` first), consumed."""
        if not self.buf:
            self.fill(timeout)
        data = bytes(self.buf)
        del self.buf[:]
        return data

    def unread(self, data: bytes):
        self.buf[0:0] = data

    def write(self, data: bytes):
        if self.closed:
            raise TransportStop("the port is closed")
        self.tx_log += data
        off = 0
        deadline = time.monotonic() + 5.0
        while off < len(data):
            _, w, _ = select.select([], [self.fd], [], max(0.0, deadline - time.monotonic()))
            if not w:
                raise TransportStop(f"the port did not accept bytes for 5 s ({off} of {len(data)} sent)")
            try:
                off += os.write(self.fd, data[off:])
            except BlockingIOError:
                continue

    def close(self):
        if self.closed:
            return
        self.closed = True
        try:
            if self.ser is not None:
                self.ser.close()
            else:
                os.close(self.fd)
        except OSError:
            pass


# ---------------------------------------------------------------- the U-Boot control plane
class UBoot:
    """The U-Boot control plane over a Port: every exchange retained as a step {what, sent, reply (text), witness, ok}. Every reader
    consumes exactly up to its boundary; every wait is a monotonic deadline."""

    def __init__(self, port: Port, steps: list, on_step=None):
        self.port, self.steps, self.on_step = port, steps, on_step

    def _step(self, what: str, **kw) -> dict:
        s = {"what": what, "t": round(time.time(), 3), "rx_at": len(self.port.rx_log), "tx_at": len(self.port.tx_log), **kw}
        self.steps.append(s)
        return s

    def _done(self, s: dict):
        s["rx_end"], s["tx_end"] = len(self.port.rx_log), len(self.port.tx_log)
        if self.on_step:
            self.on_step()

    def read_until(self, pattern, timeout: float, tail: int = 4096) -> tuple[bytes, bool]:
        """The bytes up to and including the first match of `pattern` in the receive buffer (consumed; the rest stays), or, on the
        deadline, a copy of what is there (NOT consumed) and False."""
        deadline = time.monotonic() + timeout
        while True:
            base = max(0, len(self.port.buf) - tail) if tail else 0
            m = pattern.search(bytes(self.port.buf[base:]))
            if m:
                end = base + m.end()
                out = bytes(self.port.buf[:end])
                del self.port.buf[:end]
                return out, True
            left = deadline - time.monotonic()
            if left <= 0:
                return bytes(self.port.buf), False
            self.port.fill(min(0.05, left))

    def get_prompt(self, break_s: float = 20.0) -> dict:
        """The prompt from any state: a bare CR first (a prompt already waiting answers with another prompt; a surrogate booting on input
        starts its banner); else the break key hammered for `break_s` through an autoboot countdown; the prompt held to PROMPT_RE at the
        very end. The banner's identity lines (Model:, DRAM:) are kept for the admission."""
        s = self._step("prompt")
        self.port.write(b"\r")
        _, ok = self.read_until(PROMPT_RE, 0.5)
        deadline = time.monotonic() + break_s
        while not ok and time.monotonic() < deadline:
            self.port.write(BREAK_KEY)
            _, ok = self.read_until(PROMPT_RE, 0.1)
        seen = bytes(self.port.rx_log[s["rx_at"]:])
        banner = bool(BOOT_BANNER_RE.search(seen))
        m_model, m_dram = MODEL_RE.search(seen), DRAM_RE.search(seen)
        s.update({"reply": seen.decode("utf-8", "replace")[-600:], "banner_seen": banner, "ok": ok,
                  "model": m_model.group(1).decode("utf-8", "replace").strip() if m_model else None, "dram_mib": int(m_dram.group(1)) if m_dram else None})
        self._done(s)
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
        self._done(s)
        if not ok:
            raise TransportStop(f"no prompt after `{line}` within {timeout} s")
        return body

    def md_l(self, addr: int, n: int) -> list[int]:
        """`md.l addr n`: the words, held to EXACTLY the asked addresses (each line's address is the next of the range) and count."""
        body = self.cmd(f"md.l {addr:08x} {n:x}", what="md.l")
        words = []
        for ln in body.replace(b"\r", b"").split(b"\n"):
            m = MD_LINE_RE.match(ln.strip())
            if m:
                a = int(m.group(1), 16)
                if a != addr + 4 * len(words):
                    self.steps[-1]["words"] = [f"{w:08x}" for w in words]
                    raise TransportStop(f"md.l {addr:#010x} {n}: a line for address {a:#010x} where {addr + 4 * len(words):#010x} was asked")
                words += [int(w, 16) for w in m.group(2).split()]
        self.steps[-1]["words"] = [f"{w:08x}" for w in words]
        if len(words) != n:
            raise TransportStop(f"md.l {addr:#010x} {n}: {len(words)} words parsed, not {n}")
        return words

    def mw_l(self, addr: int, value: int):
        self.cmd(f"mw.l {addr:08x} {value:08x} 1", what="mw.l")

    def crc32(self, addr: int, length: int) -> int:
        """`crc32 addr len`: the value, held to EXACTLY the asked range (`crc32 for <addr> ... <addr+len-1>`)."""
        body = self.cmd(f"crc32 {addr:08x} {length:x}", timeout=20, what="crc32")
        m = CRC_RE.search(body)
        if not m:
            raise TransportStop("crc32: no 'crc32 for <start> ... <end> ==> <value>' in the reply")
        start, end, v = int(m.group(1), 16), int(m.group(2), 16), int(m.group(3), 16)
        self.steps[-1].update({"crc32": f"{v:08x}", "range": [f"{start:08x}", f"{end:08x}"]})
        if (start, end) != (addr, addr + length - 1):
            raise TransportStop(f"crc32: the reply is for {start:#010x}..{end:#010x}, not the asked {addr:#010x}..{addr + length - 1:#010x}")
        return v

    def bdinfo(self) -> dict:
        body = self.cmd("bdinfo", timeout=5, what="bdinfo")
        sizes = [int(x, 16) for x in BDINFO_SIZE_RE.findall(body)]
        self.steps[-1]["dram_bytes"] = sizes
        return {"dram_mib": sum(sizes) // (1024 * 1024) if sizes else None}

    def loady(self, addr: int, data: bytes, name: str, timeout: float = 600.0) -> dict:
        """`loady <addr>` then this host's YMODEM-1K sender on the same port under ONE deadline; U-Boot's `## Total Size` held to the
        file's length. Bytes the transfer's last read took beyond its own end stay in the port's buffer for the prompt reader."""
        s = self._step("loady", sent=f"loady {addr:08x}", bytes=len(data))
        self.port.write(f"loady {addr:08x}\r".encode("ascii"))
        reply, ok = self.read_until(READY_RE, 5.0)
        if not ok:
            s.update({"reply": reply.decode("utf-8", "replace")[-400:], "ok": False}); self._done(s)
            raise TransportStop("loady: U-Boot did not announce the ymodem download")
        try:
            stats = ym.send(self.port, data, name, timeout=timeout)
        except ym.YModemError as e:
            s.update({"ok": False, "ymodem": str(e)})
            tail, _ = self.read_until(PROMPT_RE, 3.0)
            s["reply"] = tail.decode("utf-8", "replace")[-400:]; self._done(s)
            raise TransportStop(f"loady: the ymodem transfer failed: {e}")
        reply, ok = self.read_until(PROMPT_RE, 10.0)
        m = TOTAL_RE.search(reply)
        total = int(m.group(1), 16) if m else None
        s.update({"ymodem": stats, "reply": reply.decode("utf-8", "replace")[-400:], "total": total, "ok": ok and total == len(data)}); self._done(s)
        if not ok:
            raise TransportStop("loady: no prompt after the transfer")
        if total != len(data):
            raise TransportStop(f"loady: U-Boot reports {total} bytes received, the file has {len(data)}")
        return s

    def go(self, addr: int) -> dict:
        """`go <addr>`: the reply consumed up to U-Boot's `## Starting application ...` line END; whatever follows (the application's first
        bytes) stays in the buffer for the session."""
        s = self._step("go", sent=f"go {addr:08x}")
        self.port.write(f"go {addr:08x}\r".encode("ascii"))
        reply, ok = self.read_until(STARTING_RE, 5.0)
        s.update({"reply": reply.decode("utf-8", "replace")[-300:], "ok": ok}); self._done(s)
        if not ok:
            raise TransportStop("go: U-Boot did not start the application")
        return s


# ---------------------------------------------------------------- the session over the port
class RunnerSession(cs.ConsoleSession):
    """The console session over a Port (no MMIO side: the device answers its own; no backend in this process), source = the PS's
    evidence log. The admission, the load, the page and `go` are the control plane's steps, each persisted; the page is written
    through U-Boot (mw.l), never into a backend; the nonce the page carries is the one `md.l` showed."""

    def __init__(self, out_dir: Path, port: Port, uboot: UBoot, context: ExecutionContext, silence_s: float = 30.0, label: str = "B4Q-runner", **kw):
        kw.setdefault("source", el.SOURCE_KIND)
        kw["make_backend"] = False
        self.port, self.uboot, self.context, self.silence_s = port, uboot, context, silence_s
        self.phase = "init"
        super().__init__(out_dir, label=label, binary=Path(context.image_path), **kw)
        self.evidence = cs.PsEvidence()
        self.timing = None                                                    # the IDENT's timing word, at the opening
        self.emulated = port.kind != "uart-board"
        if port.kind == "console-pty-surrogate" and context.fixture is None:
            context.fixture = {"profile": "pty-surrogate", "note": "a host fixture on a PTY (host/b4q_device_surrogate.py): never physical provenance"}
        self.runner = {"schema": UBOOT_SCHEMA[0], "schema_version": UBOOT_SCHEMA[1], "port": port.path, "port_real": port.real, "kind": port.kind, "phase": self.phase,
                       "context": asdict(context), "image": self._rel(Path(context.image_path)), "image_sha256_file": self.instrument["image_sha256"],
                       "load_addr": context.load_addr, "stops": [], "silence_s": silence_s, "admission": None, "load_witness": None, "page_witness": None,
                       "go": None, "uboot_steps": uboot.steps}
        uboot.on_step = self.persist
        self._cut = False
        self.page_nonce = None
        self.persist()

    @staticmethod
    def _rel(p: Path) -> str:
        return str(p.relative_to(R)) if p.is_relative_to(R) else str(p)

    def _set_phase(self, phase: str):
        assert phase in PHASES
        self.phase = phase; self.runner["phase"] = phase
        self.persist()

    def persist(self):
        """uboot.json and the raw streams, written now — after every step, before `go`, on every stop: the prefix is never lost."""
        try:
            (self.out / "raw").mkdir(parents=True, exist_ok=True)
            (self.out / "raw/console.bin").write_bytes(bytes(self.port.rx_log))
            (self.out / "raw/console_tx.bin").write_bytes(bytes(self.port.tx_log))
            self.runner["raw"] = {"console_bin_sha256": hashlib.sha256(bytes(self.port.rx_log)).hexdigest(), "console_bin_bytes": len(self.port.rx_log),
                                  "console_tx_bin_sha256": hashlib.sha256(bytes(self.port.tx_log)).hexdigest(), "console_tx_bin_bytes": len(self.port.tx_log)}
            (self.out / "uboot.json").write_text(json.dumps(self.runner, indent=1, default=str) + "\n")
        except OSError as e:
            self.runner["stops"].append({"t": round(time.time(), 3), "why": f"persist: {e}", "kind": "OSError"})

    def _transport_alive(self) -> bool:
        return not self._cut and not self.port.closed

    # ---------------------------------------------------------------- the control plane before `go`
    def admit(self) -> dict:
        """R3: the file is the pinned image; the board is a permitted target with enough DRAM; the carrier is the pinned one (VARIANT at
        0x43C02034, read BEFORE any other PL access); FPGA0_CLK_CTRL recorded (held when the context expects a value). Refused by name."""
        c = self.context
        adm = {"image": None, "board": None, "carrier": None, "fclk0": None, "ok": False}
        self.runner["admission"] = adm
        file_sha = self.instrument["image_sha256"]
        adm["image"] = {"file": self._rel(Path(c.image_path)), "file_sha256": file_sha, "pin": c.image_sha256, "pin_source": c.pin_source, "equal": file_sha == c.image_sha256}
        self.persist()
        if not adm["image"]["equal"]:
            raise AdmissionStop(f"image: the selected file's sha256 {file_sha[:12]}… is not the pinned image's {c.image_sha256[:12]}… ({c.pin_source}): not loaded")
        prompt = next((s for s in self.uboot.steps if s["what"] == "prompt"), {})
        model, dram = prompt.get("model"), prompt.get("dram_mib")
        if dram is None:
            dram = self.uboot.bdinfo().get("dram_mib")
        adm["board"] = {"model": model, "dram_mib": dram, "permitted_models": list(c.board_models), "dram_min_mib": c.dram_min_mib, "fixture": c.fixture,
                        "model_ok": model is not None and any(m in model for m in c.board_models), "dram_ok": dram is not None and dram >= c.dram_min_mib}
        self.persist()
        if not adm["board"]["model_ok"]:
            raise AdmissionStop(f"board: the model {model!r} is not a permitted target {list(c.board_models)} (the banner is the identity; none seen → not admitted)")
        if not adm["board"]["dram_ok"]:
            raise AdmissionStop(f"board: DRAM {dram} MiB is below the {c.dram_min_mib} MiB the image's map needs (the page, the buffers and the log lie above 256 MiB)")
        v = self.uboot.md_l(VARIANT_ADDR, 1)[0]
        adm["carrier"] = {"variant_addr": f"{VARIANT_ADDR:#010x}", "variant": f"{v:08x}", "expected": f"{c.variant_word:08x}", "equal": v == c.variant_word}
        self.persist()
        if v != c.variant_word:
            raise AdmissionStop(f"carrier: the VARIANT word {v:#010x} at {VARIANT_ADDR:#010x} is not the pinned carrier's {c.variant_word:#010x}: no further PL access")
        f = self.uboot.md_l(SLCR_FPGA0_CLK_CTRL, 1)[0]
        adm["fclk0"] = {"addr": f"{SLCR_FPGA0_CLK_CTRL:#010x}", "ctrl": f"{f:08x}", "expected": (f"{c.fclk0_ctrl_expected:08x}" if c.fclk0_ctrl_expected is not None else None),
                        "held": c.fclk0_ctrl_expected is not None, "equal": (f == c.fclk0_ctrl_expected) if c.fclk0_ctrl_expected is not None else None}
        self.persist()
        if c.fclk0_ctrl_expected is not None and f != c.fclk0_ctrl_expected:
            raise AdmissionStop(f"clock: FPGA0_CLK_CTRL {f:#010x} is not the expected {c.fclk0_ctrl_expected:#010x}")
        adm["ok"] = True
        self._set_phase("admitted")
        return adm

    def load_image(self) -> dict:
        data = self.binary.read_bytes()
        st = self.uboot.loady(self.context.load_addr, data, self.binary.name)
        host_crc = zlib.crc32(data) & 0xFFFFFFFF
        dev_crc = self.uboot.crc32(self.context.load_addr, len(data))
        w = {"host_crc32": f"{host_crc:08x}", "uboot_crc32": f"{dev_crc:08x}", "equal": host_crc == dev_crc, "bytes": len(data), "range": [f"{self.context.load_addr:08x}", f"{self.context.load_addr + len(data) - 1:08x}"],
             "image_sha256": self.instrument["image_sha256"], "ymodem": st.get("ymodem")}
        self.runner["load_witness"] = w
        self.persist()
        if not w["equal"]:
            raise TransportStop(f"load witness: U-Boot's crc32 {dev_crc:08x} over the loaded range is not the file's {host_crc:08x}: the image in DDR is not the file (not run)")
        self._set_phase("loaded")
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
        self.runner["page_witness"] = {"nonce_md": f"{self.page_nonce:016x}", "page_addr": f"{wire.PAGE_ADDR:#010x}", "written": [f"{w:08x}" for w in words], "read_back": [f"{w:08x}" for w in back], "equal": back == words}
        self.persist()
        if back != words:
            raise TransportStop("page witness: the page read back with md.l is not the one written with mw.l (not run)")
        self.page_words = words
        self._set_phase("page-written")

    def control_plane(self):
        """The admission, the load + witness, the page + witness — no `go`. The phase ends at `pre-go`."""
        if self.phase == "init":
            if not any(s["what"] == "prompt" for s in self.uboot.steps):
                self.uboot.get_prompt(break_s=self.runner.get("break_s", 20.0))
            self._set_phase("prompt")
        if self.phase == "prompt":
            self.admit()
        if self.phase == "admitted":
            self.load_image()
        if self.phase == "loaded":
            self.write_page()
        if self.phase == "page-written":
            self._set_phase("pre-go")

    def start(self):
        """The control plane, then `go`: the execution phase is persisted BEFORE the command is issued; the console is the application's after."""
        self.control_plane()
        if self.phase != "pre-go":
            raise TransportStop(f"go refused: the control plane is at phase {self.phase!r}, not pre-go")
        self.runner["go"] = {"t": round(time.time(), 3), "addr": f"{self.context.load_addr:08x}", "issued": False}
        self._set_phase("go-issued")                                          # written before the command leaves this host
        self.runner["go"]["issued"] = True
        self.uboot.go(self.context.load_addr)
        self._set_phase("application")
        self.proc = None

    # ---------------------------------------------------------------- the transport: the port's one buffer
    def _console_write(self, line: str, note: str = ""):
        self.port.write(line.encode("utf-8"))
        self.console.append({"i": len(self.evidence.trace), "pcap_n": len(self.evidence.pcap_log), "dir": "host", "line": line.rstrip("\n"), "note": note})

    def _readline(self, which: str) -> str | None:
        if which == "mmio":
            return None
        deadline = time.monotonic() + self.silence_s
        while b"\n" not in self.port.buf:
            left = deadline - time.monotonic()
            if left <= 0:
                self._stop_transport(f"the console was silent for {self.silence_s} s while awaiting {getattr(self, '_awaiting', '?')}")
            self.port.fill(min(0.2, left))
        k = self.port.buf.index(b"\n")
        line = bytes(self.port.buf[:k]); del self.port.buf[:k + 1]
        return line.decode("utf-8", "replace")

    def _stop_transport(self, why: str):
        self._cut = True
        self.runner["stops"].append({"t": round(time.time(), 3), "why": why, "awaiting": getattr(self, "_awaiting", None), "kind": "TransportStop"})
        if self.interrupted is None:
            self.interrupted = {"transport": why, "console_line": len(self.console)}   # the session is cut by its transport: the records / the verifier treat it as the interruption it is
        self.halt("transport: " + why)
        self.persist()
        raise ss.SessionRefusal(why)

    def _console_line(self) -> dict | None:
        line = self._readline("console")
        head = line.strip("\r")
        if BANNER_LINE_RE.match(head):                                       # a boot banner line on the application's console: the PS reset — the session is cut, by name
            self.console.append({"i": len(self.evidence.trace), "dir": "board", "line": head, "note": "a boot banner: the PS reset mid-session"})
            self._stop_transport("a boot banner on the console mid-session: the PS reset (the session is cut; its log is unobtainable)")
        if head.strip() == "":
            return None                                                       # an empty line (U-Boot's CR LF after `go`): not a console line
        return self._handle_console_line(head)

    def serve(self, awaiting: str = "RESULT") -> dict:
        self._awaiting = awaiting
        while True:
            r = self._console_line()
            if r is not None:
                return r

    def open(self) -> dict:
        r = super().open()
        if self.ident is not None and type(self.ident.get("open", {}).get("timing")) is int:
            self.timing = {**rm.decode_timing(self.ident["open"]["timing"]), "pulse": 2}     # the timing word the PS read at its opening; the pulse count is the carrier design's constant (b4q_emu.TIMING)
        return r

    def drain_after_end(self, cap: int = 200000) -> dict:
        return {"mmio_after_end": None}

    def stop(self):
        if self._cut or self.phase in ("init", "prompt", "admitted", "loaded", "page-written", "pre-go", "stopped"):
            return
        try:
            if self.ended is None:
                self._send("QUIT")
                r = self.serve("END")
                if r.get("status") == cs.END_STATUS:
                    self._acquire(r)                                           # the tail of the log (the END's own position) through the export epilogue
            self._console_write(self._frame_out("QUIT", ""))                   # the export epilogue closed (a QUIT after the END: the verifier's phase rule)
            self._set_phase("ended")
        except (ss.SessionRefusal, TransportStop, OSError):
            pass

    def write(self) -> dict:
        self.persist()
        if self.session_open is None:
            manifest = {"schema": "b4q_session", "label": self.label, "records": [], "transport": {"kind": self.port.kind, "runner": self.runner, "protocol": cs.PROTOCOL, "token": self.token,
                        "page_words": [f"{w:08x}" for w in (self.page_words or [])], "page_flags": self.page_flags, "knobs": self.knobs, "stats": self.stats, "console_lines": len(self.console),
                        "findings": list(self.findings), "ident": None, "end": None}, "emulated": self.emulated, "standing": "a runner archive WITHOUT a session: the control plane stopped before the opening (uboot.json names the step)",
                        "instrument": self.instrument, "executing_side": {"binary": self._rel(self.binary), "sha256": self.instrument["image_sha256"]}, "halted": self.halted, "interrupted": self.interrupted, "no_session": True}
            (self.out / "manifest.json").write_text(json.dumps(manifest, indent=1, default=str) + "\n")
            (self.out / "console.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.console))
            return manifest
        if self.timing is None:
            self.timing = {"unknown": True, "note": "no IDENT came: the timing word was never read by the program (nothing of the carrier's timing is claimed)"}
        m = super().write()
        m["transport"]["kind"] = self.port.kind
        m["transport"]["standing"] = ("the board application's host harness behind the device surrogate's emulated U-Boot on a PTY (a declared host fixture): the bytes are the ones the image would put on UART1, the MMIO is an emulation in another process this host never reads; not a board"
                                      if self.port.kind == "console-pty-surrogate" else "a board's UART: the verifier holds this archive's internal consistency; it does not establish that anything was observed on a device")
        m["transport"]["runner"] = self.runner
        (self.out / "manifest.json").write_text(json.dumps(m, indent=1, default=str) + "\n")
        return m


# ---------------------------------------------------------------- the stage bodies and the run
def body_control_plane(s: RunnerSession):
    s.control_plane()
    return {"stage": "control-plane"}


def body_open(s: RunnerSession):
    s.open()
    return {"stage": "open"}


def body_transaction(s: RunnerSession):
    import b4q_console_e2e as ce
    s.open(); s.transaction("root", 0, ce.stim([]))
    return {"stage": "transaction", "tx": ce._tx(s, "normal", ce.G_CESR, ce.FIX1)}


def run(port_path: str, out: Path, body, context: ExecutionContext | None = None, silence_s: float = 30.0, break_s: float = 20.0, label: str = "B4Q-runner", port=None, **kw) -> dict:
    """One runner session: the prompt, the admission, the image, the page, go, the body, the stop; everything retained, also on a stop
    or a programming error (which is re-raised AFTER the retention, named as such — never reported as a device finding). `port`: an
    already-open port object (the tests' fakes); else the path is opened."""
    out = Path(out); out.mkdir(parents=True, exist_ok=True)
    context = context or ExecutionContext.pinned()
    steps = []
    port = port if port is not None else Port(port_path)
    uboot = UBoot(port, steps)
    s = None
    stop = None
    error = None
    t0 = time.time()
    extra = {}
    m = None
    try:
        s = RunnerSession(out, port, uboot, context, silence_s=silence_s, label=label, **kw)
        s.runner["break_s"] = break_s
        extra = body(s) or {}
    except (TransportStop, ss.SessionRefusal) as e:
        stop = {"kind": type(e).__name__, "why": str(e)}
    except BaseException as e:                                                 # a programming / OS error: retained as such, then re-raised
        stop = {"kind": "ProgrammingError", "why": f"{type(e).__name__}: {e}"}
        error = e
    finally:
        try:
            if s is not None:
                if stop and stop["why"] not in [x["why"] for x in s.runner["stops"]]:
                    s.runner["stops"].append({"t": round(time.time(), 3), "why": stop["why"], "kind": stop["kind"]})
                if error is None:
                    s.stop()
                if s.phase != "ended" and stop:
                    s.runner["phase_at_stop"] = s.phase
                    s.phase = "stopped"; s.runner["phase"] = "stopped"
                m = s.write()
            else:
                (out / "raw").mkdir(exist_ok=True)
                (out / "raw/console.bin").write_bytes(bytes(port.rx_log)); (out / "raw/console_tx.bin").write_bytes(bytes(port.tx_log))
                (out / "uboot.json").write_text(json.dumps({"schema": UBOOT_SCHEMA[0], "schema_version": UBOOT_SCHEMA[1], "uboot_steps": steps, "stops": [stop] if stop else [], "port": port_path, "kind": port.kind, "phase": "init"}, indent=1, default=str) + "\n")
        finally:
            port.close()
    summary = {"label": label, "wall_s": round(time.time() - t0, 3), "stop": stop, "opened": bool(s and s.session_open is not None and s.session_open["record"]["status"] == "open"),
               "phase": s.phase if s else "init", "records": (m or {}).get("records", []), "chain_findings": (m or {}).get("chain_findings"), "halted": s.halted if s else None,
               "end": s.ended if s else None, "stats": s.stats if s else None, "console_lines": len(s.console) if s else 0,
               "admission": (s.runner.get("admission") if s else None), "load_witness": (s.runner.get("load_witness") if s else None),
               "page_witness": {k: v for k, v in ((s.runner.get("page_witness") or {}) if s else {}).items() if k in ("equal", "nonce_md")},
               "source": (m or {}).get("source") and {k: m["source"][k] for k in ("bytes", "records", "digest_equal")}, "transport_stops": (s.runner["stops"] if s else ([stop] if stop else [])), **extra}
    (out / "summary.json").write_text(json.dumps(summary, indent=1, default=str) + "\n")
    if error is not None:
        raise error
    return summary


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="the B4Q physical runner (host-only preparation): a stage over a serial endpoint under an explicit execution context")
    ap.add_argument("--port", required=True, help="the serial endpoint: a PTY (a host fixture) or a tty device")
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--stage", choices=("control-plane", "open", "transaction"), default="control-plane")
    ap.add_argument("--image", type=Path, default=IMAGE)
    ap.add_argument("--image-pin", help="the pinned image sha256 (default: the build evidence of record)")
    ap.add_argument("--board-model", action="append", help="a permitted Model: line (default: Ebang EBAZ4203)")
    ap.add_argument("--dram-min", type=int, default=512)
    ap.add_argument("--fclk0-ctrl", help="the expected SLCR FPGA0_CLK_CTRL word (hex); omitted: recorded, not held")
    ap.add_argument("--silence", type=float, default=30.0)
    ap.add_argument("--break-s", type=float, default=20.0)
    ap.add_argument("--label", default="B4Q-runner")
    a = ap.parse_args(argv)
    kw = {"image_path": str(a.image), "dram_min_mib": a.dram_min}
    if a.board_model:
        kw["board_models"] = tuple(a.board_model)
    if a.fclk0_ctrl:
        kw["fclk0_ctrl_expected"] = int(a.fclk0_ctrl, 16)
    ctx = ExecutionContext(image_sha256=a.image_pin, pin_source="explicit --image-pin", **kw) if a.image_pin else ExecutionContext.pinned(image=a.image, **kw)
    body = {"control-plane": body_control_plane, "open": body_open, "transaction": body_transaction}[a.stage]
    s = run(a.port, a.out, body, context=ctx, silence_s=a.silence, break_s=a.break_s, label=a.label)
    print(json.dumps({k: s.get(k) for k in ("phase", "stop", "opened", "halted", "load_witness", "page_witness", "source")}, default=str))
    return 0 if not s.get("stop") else 1


if __name__ == "__main__":
    sys.exit(main())
