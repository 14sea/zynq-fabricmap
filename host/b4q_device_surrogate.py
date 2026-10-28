#!/usr/bin/env python3
"""B4Q — the DEVICE SURROGATE (host-only, the runner unit of 2026-10-28): a process that stands in for the EBAZ4205 + carrier on the
other end of a PTY, so that the physical runner (host/b4q_runner.py) can be exercised, end to end and under faults, without a board.
It is NOT a board model: its "U-Boot" answers the few commands the runner needs the way the miner's U-Boot does on the wire (the
banner, the autoboot countdown broken by 'd', the prompt, `loady` as a YMODEM-1K receiver, `mw.l` / `md.l` / `crc32` / `go` /
`reset`); its "PS" after `go` is the board application's host harness — the image's own sources — whose MMIO it answers from a
private emulated backend (host/b4q_backend.Backend) and whose console it bridges to the PTY byte for byte. The loaded bytes are
"executed" only if their sha256 is in the image table (the pinned image -> the harness built from the same sources); any other
image leaves the console silent, as an undefined program would.

Everything this process knows (its backend's trace, its PCAP log) is PRIVATE: the runner never reads it; a test may, to cross-check
the PS log against it. The faults are the bench's declared knobs: an interrupted load, a wrong crc, a corrupted page, a missed
autoboot, no prompt, silence after N lines, a corrupted CHUNK, a reset (banner) after N lines, a tiny evidence log (overflow), a
watchdog that cannot be armed, the backend's DevC / frame / write faults, another binary for the image (a twin).

    python3 host/b4q_device_surrogate.py --link /tmp/b4q-pty [--fault name[=value]]... [--image-table sha256=path]...
prints the PTY slave path on stdout (`PTY <path>`) and serves until killed."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import pty
import select
import subprocess
import sys
import termios
import time
import tty
import zlib
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4q_backend as bk  # noqa: E402
import b4q_frames as fr  # noqa: E402
import b4q_notary as nt  # noqa: E402
import b4q_wire as wire  # noqa: E402
import b4q_ymodem as ym  # noqa: E402

APPHOST = R / "build/b4q_firmware/b4q_apphost"
IMAGE = R / "build/b4q_image/b4q_app_v2.bin"
BOARDS = {   # the two host fixture profiles: what each U-Boot puts on the wire (the model line, the DRAM line, the prompt, the break key)
    "4203": {"prompt": b"Zynq> ", "break_any_key": True, "dram_mib": 512,
             "banner": (b"\r\n\r\nU-Boot SPL 2026.04-rc5 (surrogate)\r\n\r\nU-Boot 2026.04-rc5 (surrogate) (Oct 28 2026 - 00:00:00 +0000)\r\n\r\nCPU:   Zynq 7z010\r\nSilicon: v3.1\r\n"
                        b"Model: Ebang EBAZ4203 (surrogate)\r\nDRAM:  ECC disabled 512 MiB\r\nMMC:   mmc@e0100000: 0\r\nIn:    serial@e0001000\r\nOut:   serial@e0001000\r\nErr:   serial@e0001000\r\n")},
    "4205": {"prompt": b"zynq-uboot> ", "break_any_key": False, "dram_mib": 256,
             "banner": (b"\r\n\r\nU-Boot 2014.01 (surrogate) (Oct 28 2026 - 00:00:00)\r\n\r\nI2C:   ready\r\nMemory: ECC disabled\r\nDRAM:  256 MiB\r\nMMC:   zynq_sdhci: 0\r\n"
                        b"NAND:  128 MiB\r\nIn:    serial\r\nOut:   serial\r\nErr:   serial\r\nModel: Ebang EBAZ4205 (surrogate)\r\nNet:   Gem.e000b000\r\n")},
}
SLCR_FPGA0_CLK_CTRL = 0xF8000170
MINER_BOOT = (b"\r\nNAND read: device 0 offset 0x300000, size 0x500000\r\n 5242880 bytes read: OK\r\n## Booting kernel from Legacy Image at 03000000 ...\r\n"
              b"   Image Name:   Linux-3.x (surrogate)\r\n   Verifying Checksum ... OK\r\n   Loading Kernel Image ... OK\r\n\r\nStarting kernel ...\r\n\r\n")
BREAK_KEY = b"d"


class Endpoint:
    """The PTY master as a port with ONE receive buffer (`buf` / `fill`): the ymodem receiver and the prompt loop share it, so the bytes
    the transfer's last read took beyond its own end (the host's next command) reach the prompt loop."""

    def __init__(self, fd: int):
        self.fd = fd
        self.buf = bytearray()

    def fill(self, timeout: float) -> int:
        r, _, _ = select.select([self.fd], [], [], max(0.0, timeout))
        if not r:
            return 0
        try:
            data = os.read(self.fd, 65536)
        except OSError:
            return 0
        self.buf += data
        return len(data)

    def read(self, timeout: float) -> bytes:
        if not self.buf:
            self.fill(timeout)
        data = bytes(self.buf); del self.buf[:]
        return data

    def write(self, data: bytes):
        os.write(self.fd, data)


class Surrogate:
    def __init__(self, a):
        self.a = a
        self.faults = {}
        for f in a.fault or []:
            k, _, v = f.partition("=")
            self.faults[k] = int(v) if v.isdigit() else (v or True)
        self.base, self.wl = fr.load_base(), fr.whitelist()
        self.backend = bk.Backend(self.base, self.wl, power_on=a.power_on, gsr_init_effect=not a.no_gsr_init_effect)
        self.notary = nt.Notary(self.base, self.wl)                       # the fixture key: the signer principal provisions it, as the host-only session does
        self.backend.provision_key(bytes.fromhex(a.provision_key) if a.provision_key else self.notary.key)
        for spec in a.devc_fault or []:
            kind, ordinal, mode = spec.split(":")
            self.backend.devc.faults[(kind, int(ordinal))] = mode
        for n in a.corrupt_frame_read or []:
            self.backend.devc.corrupt_frame_reads.add(int(n))
        for off in a.refuse_write or []:
            self.backend.refuse_writes.add(int(off, 0))
        self.board = BOARDS[a.board]
        self.backend.mem.wr(SLCR_FPGA0_CLK_CTRL, int(a.fclk0_ctrl, 16))          # the SLCR word U-Boot's md.l shows (a fixture value: the real one is the bring-up's M3)
        self.table = {hashlib.sha256(IMAGE.read_bytes()).hexdigest(): APPHOST} if IMAGE.is_file() else {}
        for spec in a.image_table or []:
            sha, _, path = spec.partition("=")
            self.table[sha] = Path(path)
        self.master, self.slave = pty.openpty()
        tty.setraw(self.slave)
        attr = termios.tcgetattr(self.slave); attr[6][termios.VMIN] = 0; attr[6][termios.VTIME] = 0
        termios.tcsetattr(self.slave, termios.TCSANOW, attr)
        self.slave_path = os.ttyname(self.slave)
        if a.link:
            try:
                os.unlink(a.link)
            except FileNotFoundError:
                pass
            os.symlink(self.slave_path, a.link)
        self.ep = Endpoint(self.master)
        self.loaded = {}                                                     # load address -> bytes (the images `loady` received)
        self.boots = 0
        self.log = []
        self.private = Path(a.private_dir) if a.private_dir else None
        if self.private:
            self.private.mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- the console bytes
    def out(self, data: bytes):
        off = 0
        while off < len(data):
            _, w, _ = select.select([], [self.master], [], 5)
            if not w:
                return
            try:
                off += os.write(self.master, data[off:])
            except OSError:
                return

    def note(self, what: str, **kw):
        e = {"t": round(time.time(), 3), "what": what, **kw}
        self.log.append(e)
        print(json.dumps(e), file=sys.stderr, flush=True)
        if self.private:
            with (self.private / "surrogate_log.jsonl").open("a") as f:
                f.write(json.dumps(e) + "\n")

    # ---------------------------------------------------------------- memory as U-Boot sees it
    def mem_word(self, addr: int) -> int:
        if bk.AXI_BASE <= addr < bk.AXI_BASE + 0x10000:
            d, resp, _ = self.backend.rd32(addr)                              # U-Boot's own read of the PL window (a host-side read, not the PS application's)
            if self.faults.get("wrong-variant") and addr == bk.AXI_BASE + 0x2034:
                return 0x42340002                                             # another carrier's variant word
            return d if resp == 0 else 0xFFFFFFFF
        for base, data in self.loaded.items():
            if base <= addr < base + len(data):
                chunk = data[addr - base:addr - base + 4]
                return int.from_bytes(chunk + b"\x00" * (4 - len(chunk)), "little")
        return self.backend.mem.rd(addr)

    def mem_bytes(self, addr: int, n: int) -> bytes:
        out = bytearray()
        a = addr & ~3
        while len(out) < n + (addr & 3):
            out += self.mem_word(a).to_bytes(4, "little"); a += 4
        return bytes(out[(addr & 3):(addr & 3) + n])

    # ---------------------------------------------------------------- the boots
    def serve(self):
        print(f"PTY {self.slave_path}", flush=True)
        self.note("pty", path=self.slave_path, link=self.a.link)
        while True:
            self.boot()

    def boot(self):
        self.boots += 1
        if self.a.boot_on_input and self.boots == 1:
            while not self.ep.read(3600):                                    # "power-on" when the host first speaks: the first byte starts the boot (a bench convenience, not a board behaviour)
                pass
        self.note("boot", n=self.boots)
        self.out(self.board["banner"])
        broken = False
        secs = self.a.autoboot_s
        self.out(b"Hit any key to stop autoboot: ")
        for s in range(secs, 0, -1):
            self.out(f" {s} \x08\x08\x08".encode())
            deadline = time.time() + 1.0
            while time.time() < deadline:
                data = self.ep.read(max(0.0, deadline - time.time()))
                if data and (BREAK_KEY in data or (self.board["break_any_key"] and data.strip(b"\r\n"))) and not self.faults.get("missed-autoboot"):
                    broken = True; break
            if broken:
                break
        if not broken:
            self.out(b" 0 \r\n" + MINER_BOOT + b"[    0.000000] Booting Linux on physical CPU 0x0 (surrogate)\r\n")
            self.note("autoboot", broken=False)
            self.sleep_forever()
            return
        self.out(b"\r\n")
        self.note("autoboot", broken=True)
        if self.faults.get("no-prompt"):
            self.sleep_forever()
            return
        self.prompt_loop()

    def sleep_forever(self):
        while True:
            self.ep.read(3600)

    def prompt_loop(self):
        buf = b""
        PROMPT = self.board["prompt"]
        self.out(PROMPT)
        while True:
            data = self.ep.read(3600)
            for b in data:
                c = bytes([b])
                if c in (b"\r", b"\n"):
                    self.out(b"\r\n")
                    line = buf.decode("ascii", "replace").strip()
                    buf = b""
                    if line:
                        r = self.command(line)
                        if r == "reboot":
                            return
                    self.out(PROMPT)
                elif c in (b"\x08", b"\x7f"):
                    if buf:
                        buf = buf[:-1]; self.out(b"\x08 \x08")
                else:
                    buf += c
                    self.out(c)                                              # U-Boot echoes what is typed

    def command(self, line: str):
        parts = line.split()
        cmd = parts[0]
        try:
            if cmd == "loady":
                addr = int(parts[1], 16) if len(parts) > 1 else 0x02000000
                self.out(f"## Ready for binary (ymodem) download to 0x{addr:08x} at 115200 bps...\r\n".encode())
                cancel = self.faults.get("interrupted-load")
                try:
                    data, info = ym.receive(self.ep, cancel_after_blocks=int(cancel) if cancel else None)
                except ym.YModemError as e:
                    self.note("loady", error=str(e))
                    self.out(b"xyzModem - CRC mode, 0(SOH)/0(STX)/2(CAN) packets, 0 retries\r\n## Total Size = 0x00000000 = 0 Bytes\r\n")
                    return None
                self.loaded[addr] = data
                self.note("loady", addr=addr, bytes=len(data), sha256=hashlib.sha256(data).hexdigest(), info=info)
                self.out(f"xyzModem - CRC mode, {info['soh']}(SOH)/{info['stx']}(STX)/0(CAN) packets, {info['naks']} retries\r\n## Total Size = 0x{len(data):08x} = {len(data)} Bytes\r\n".encode())
            elif cmd == "mw.l":
                addr, val = int(parts[1], 16), int(parts[2], 16)
                count = int(parts[3], 16) if len(parts) > 3 else 1
                if self.faults.get("corrupt-mw") and addr == wire.PAGE_ADDR + 4 * 5:
                    val ^= 1                                                 # a DDR write that does not take (the page witness must catch it before `go`)
                for k in range(count):
                    self.backend.mem.wr(addr + 4 * k, val)
            elif cmd == "md.l":
                addr = int(parts[1], 16)
                n = int(parts[2], 16) if len(parts) > 2 else 0x10
                if self.faults.get("md-garbage"):
                    self.out(b"md.l: garbage\r\n"); return None
                lines = []
                for k in range(0, n, 4):
                    ws = [self.mem_word(addr + 4 * j) for j in range(k, min(n, k + 4))]
                    asc = "".join(chr(b) if 32 <= b < 127 else "." for w in ws for b in w.to_bytes(4, "little"))
                    lines.append(f"{addr + 4 * k:08x}:" + "".join(f" {w:08x}" for w in ws) + "    " + asc)
                self.out(("\r\n".join(lines) + "\r\n").encode())
            elif cmd == "crc32":
                addr, length = int(parts[1], 16), int(parts[2], 16)
                v = zlib.crc32(self.mem_bytes(addr, length)) & 0xFFFFFFFF
                if self.faults.get("wrong-crc"):
                    v ^= 1
                self.out(f"crc32 for {addr:08x} ... {addr + length - 1:08x} ==> {v:08x}\r\n".encode())
            elif cmd == "go":
                addr = int(parts[1], 16)
                self.out(f"## Starting application at 0x{addr:08x} ...\r\n".encode())
                return self.run_app(addr)
            elif cmd == "reset":
                self.out(b"resetting ...\r\n")
                return "reboot"
            elif cmd == "bdinfo":
                size = self.board["dram_mib"] * 1024 * 1024
                self.out(f"arch_number = 0x00000000\r\nboot_params = 0x00000100\r\nDRAM bank   = 0x00000000\r\n-> start    = 0x00000000\r\n-> size     = 0x{size:08x}\r\nbaudrate    = 115200 bps\r\n".encode())
            elif cmd == "version":
                self.out(b"U-Boot 2014.01 (surrogate)\r\n")
            elif cmd == "help":
                self.out(b"loady mw md crc32 go reset version\r\n")
            else:
                self.out(f"Unknown command '{cmd}' - try 'help'\r\n".encode())
        except (IndexError, ValueError):
            self.out(f"Usage:\r\n{cmd} - bad arguments\r\n".encode())
        return None

    # ---------------------------------------------------------------- the application after `go`
    def run_app(self, addr: int):
        data = self.loaded.get(addr)
        sha = hashlib.sha256(data).hexdigest() if data else None
        binary = self.table.get(sha) if (data and not self.faults.get("unknown-image")) else None
        self.note("go", addr=addr, image_sha256=sha, binary=str(binary) if binary else None)
        if binary is None or not Path(binary).is_file():
            self.sleep_forever()                                             # an image this surrogate cannot execute: the console stays silent, as an undefined program would
            return None
        if self.faults.get("corrupt-page"):
            self.backend.mem.wr(wire.PAGE_ADDR + 4 * 5, self.backend.mem.rd(wire.PAGE_ADDR + 4 * 5) ^ 1)
        page = wire.parse_page([self.backend.mem.rd(wire.PAGE_ADDR + 4 * i) for i in range(wire.PAGE_WORDS)])
        h2c_r, h2c_w = os.pipe(); c2h_r, c2h_w = os.pipe()
        env = dict(os.environ)
        env["B4Q_CON_IN"], env["B4Q_CON_OUT"] = str(h2c_r), str(c2h_w)
        if self.faults.get("ring-bytes"):
            env["B4Q_APP_HOST_RING_BYTES"] = str(self.faults["ring-bytes"])
        if self.faults.get("wdt-fail"):
            env["B4Q_APP_HOST_WDT_FAIL"] = "1"
        proc = subprocess.Popen([str(binary)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, pass_fds=(h2c_r, c2h_w), env=env)
        os.close(h2c_r); os.close(c2h_w)
        board_lines = 0
        chunks = 0
        silent = False
        killed = None
        mmio_buf = b""; con_buf = b""
        t_begin = len(self.backend.trace)
        while True:
            fds = [self.master, c2h_r, proc.stdout.fileno()]
            r, _, _ = select.select(fds, [], [], 1.0)
            if proc.poll() is not None and proc.stdout.fileno() not in r and c2h_r not in r:
                break
            if self.master in r:
                try:
                    data = os.read(self.master, 65536)
                except OSError:
                    data = b""
                if data:
                    try:
                        os.write(h2c_w, data)                                # host -> board bytes, verbatim
                    except OSError:
                        pass
            if c2h_r in r:
                data = os.read(c2h_r, 65536)
                if not data:
                    os.close(c2h_r); c2h_r = -1
                    if proc.poll() is not None:
                        break
                    continue
                con_buf += data
                while b"\n" in con_buf:
                    line, _, con_buf = con_buf.partition(b"\n")
                    board_lines += 1
                    line = line + b"\n"
                    if line.startswith(b"B4Q1 CHUNK "):
                        chunks += 1
                        if self.faults.get("corrupt-chunk") and chunks == int(self.faults["corrupt-chunk"]):
                            line = line[:-4] + (b"0" if line[-4:-3] != b"0" else b"1") + line[-3:]   # one CRC character changed: the host must refuse and re-ask
                    if self.faults.get("silence-after") and board_lines > int(self.faults["silence-after"]):
                        silent = True
                    if self.faults.get("reset-after-lines") and board_lines >= int(self.faults["reset-after-lines"]):
                        self.out(line)
                        proc.kill(); killed = "reset-after-lines"
                        break
                    if not silent:
                        self.out(line)
                if killed:
                    break
            if proc.stdout.fileno() in r:
                data = proc.stdout.read1(65536) if hasattr(proc.stdout, "read1") else os.read(proc.stdout.fileno(), 65536)
                if not data:
                    if proc.poll() is not None:
                        break
                    continue
                mmio_buf += data
                while b"\n" in mmio_buf:
                    line, _, mmio_buf = mmio_buf.partition(b"\n")
                    text = line.decode("utf-8", "replace")
                    if text.startswith("R "):
                        d, resp, _ = self.backend.rd32(int(text[2:], 16))
                        proc.stdin.write(f"{d:08x} {resp}\n".encode()); proc.stdin.flush()
                    elif text.startswith("W "):
                        a_, d_ = text[2:].split()
                        proc.stdin.write(f"{self.backend.wr32(int(a_, 16), int(d_, 16))}\n".encode()); proc.stdin.flush()
                    else:
                        self.note("app", line=text)
        try:
            proc.stdin.close()
        except OSError:
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        for fd in (h2c_w, c2h_r):
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
        self.note("app-exit", rc=proc.returncode, board_lines=board_lines, killed=killed, trace_events=len(self.backend.trace) - t_begin)
        if self.private:
            (self.private / f"trace_boot{self.boots}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.backend.trace[t_begin:]))
            (self.private / f"pcap_boot{self.boots}.jsonl").write_text("".join(json.dumps(e) + "\n" for e in self.backend.pcap_log))
        if killed == "reset-after-lines":
            time.sleep(0.2)
            return "reboot"                                                  # the PS reset mid-session: the banner follows
        if silent:
            self.sleep_forever()                                             # a mute device stays mute (no banner either): the host's silence bound is what stops the session
            return None
        if page and (page["flags"] & wire.PAGE_FLAG_WATCHDOG) and not self.faults.get("wdt-fail") and not self.faults.get("no-wdt-reset"):
            time.sleep(self.a.wdt_reset_s)                                   # the armed watchdog resets the PS once nothing kicks it: U-Boot's banner follows
            return "reboot"
        self.sleep_forever()
        return None


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--link", help="a symlink to the PTY slave for the runner")
    ap.add_argument("--fault", action="append", help="interrupted-load=K | wrong-crc | md-garbage | corrupt-page | corrupt-mw | missed-autoboot | no-prompt | silence-after=N | corrupt-chunk=N | reset-after-lines=N | ring-bytes=N | wdt-fail | unknown-image | no-wdt-reset | wrong-variant")
    ap.add_argument("--board", choices=sorted(BOARDS), default="4203", help="the host fixture profile: the EBAZ4203 (512 MiB, mainline U-Boot) or the EBAZ4205 (256 MiB, the miner U-Boot)")
    ap.add_argument("--fclk0-ctrl", default="0x00200A00", help="the SLCR FPGA0_CLK_CTRL word the fixture shows (hex)")
    ap.add_argument("--image-table", action="append", help="sha256=path: the binary that stands for an image (default: the pinned v2 image -> the host harness)")
    ap.add_argument("--devc-fault", action="append", help="kind:ordinal:mode on the backend's DevC fake")
    ap.add_argument("--corrupt-frame-read", action="append", help="the ordinal of a frame read the bench corrupts")
    ap.add_argument("--refuse-write", action="append", help="a window offset the bench refuses writes to")
    ap.add_argument("--provision-key", help="hex: a key other than the fixture notary's (an AUTH fault)")
    ap.add_argument("--power-on", default="init")
    ap.add_argument("--no-gsr-init-effect", action="store_true")
    ap.add_argument("--autoboot-s", type=int, default=2)
    ap.add_argument("--boot-on-input", action="store_true", help="the first boot starts when the host first sends a byte (the e2e's determinism)")
    ap.add_argument("--wdt-reset-s", type=float, default=1.0)
    ap.add_argument("--private-dir", help="where this process writes its PRIVATE trace / PCAP log (a test's cross-check only; never the runner's)")
    a = ap.parse_args(argv)
    s = Surrogate(a)
    try:
        s.serve()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
