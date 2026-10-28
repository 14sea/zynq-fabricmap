#!/usr/bin/env python3
"""YMODEM-1K, both ends, in Python: the SENDER the runner uses on its port (`loady` on U-Boot's side: CRC mode, 1024-byte STX
blocks, the block-0 header with the name and size, the EOT / NAK / EOT / ACK close, the empty block 0), and the RECEIVER the device
surrogate uses to stand in for U-Boot's `loady`. The CRC is the XMODEM CRC-16 (poly 0x1021, init 0). Every byte goes through the
object's read(timeout) / write(data) — a Port or a surrogate endpoint; nothing here opens a device."""
from __future__ import annotations

import time

SOH, STX, EOT, ACK, NAK, CAN, CRC = 0x01, 0x02, 0x04, 0x06, 0x15, 0x18, ord("C")


class YModemError(Exception):
    pass


def crc16(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def _block(n: int, payload: bytes, size: int) -> bytes:
    payload = payload + b"\x1a" * (size - len(payload)) if size == 1024 else payload + b"\x00" * (size - len(payload))
    head = bytes([STX if size == 1024 else SOH, n & 0xFF, (255 - n) & 0xFF])
    return head + payload + crc16(payload).to_bytes(2, "big")


class _Clock:
    """A cumulative deadline (monotonic): every wait inside a transfer is bounded by what is left of the whole."""

    def __init__(self, timeout: float):
        self.deadline = time.monotonic() + timeout

    def left(self) -> float:
        return self.deadline - time.monotonic()

    def check(self, what: str):
        if self.left() <= 0:
            raise YModemError(f"timeout: the transfer's deadline passed {what}")


def _read_byte(port, timeout: float, clock: _Clock | None = None) -> int | None:
    """One byte from the port's receive buffer (`port.buf`, shared with every other reader of the port: a byte read past the transfer's
    end stays there for the next reader), filled through `port.fill(timeout)`; None on the timeout (bounded by the clock)."""
    if clock is not None:
        timeout = min(timeout, max(0.0, clock.left()))
    if hasattr(port, "buf") and hasattr(port, "fill"):
        if not port.buf:
            port.fill(timeout)
        if not port.buf:
            return None
        b = port.buf[0]
        del port.buf[:1]
        return b
    deadline = time.monotonic() + timeout                     # a port without a shared buffer (a bare read(timeout) object): a private queue
    buf = getattr(port, "_ym_buf", b"")
    while not buf and time.monotonic() < deadline:
        buf = port.read(min(0.2, max(0.0, deadline - time.monotonic())))
    if not buf:
        port._ym_buf = b""
        return None
    port._ym_buf = buf[1:]
    return buf[0]


def send(port, data: bytes, name: str, timeout: float = 600.0, retries: int = 10, junk_limit: int = 4096) -> dict:
    """Send `data` as one file under ONE cumulative deadline (`timeout`, monotonic: every inner wait, every retry, every junk byte is
    inside it); returns the statistics {blocks, retries, naks, junk, seconds}. A receiver that answers with junk is bounded twice: by
    the deadline and by `junk_limit` bytes per block (then a retry, then the retries' bound)."""
    t0 = time.monotonic()
    clock = _Clock(timeout)
    stats = {"blocks": 0, "retries": 0, "naks": 0, "junk": 0}
    if not (hasattr(port, "buf") and hasattr(port, "fill")):
        port._ym_buf = b""

    def await_c(what: str):
        for _ in range(retries * 5):
            clock.check(f"before {what}")
            c = _read_byte(port, 2.0, clock)
            if c == CRC:
                return
            if c == CAN:
                raise YModemError(f"cancelled by the receiver before {what}")
            if c is not None:
                stats["junk"] += 1
        raise YModemError(f"the receiver never asked (no 'C') before {what}")

    def send_block(blk: bytes, what: str):
        for attempt in range(retries):
            clock.check(f"at {what}")
            port.write(blk)
            junk = 0
            while True:
                clock.check(f"awaiting the ACK of {what}")
                c = _read_byte(port, 10.0, clock)
                if c == ACK:
                    return
                if c == NAK:
                    stats["naks"] += 1; stats["retries"] += 1
                    break
                if c == CAN:
                    raise YModemError(f"cancelled by the receiver at {what}")
                if c is None:
                    stats["retries"] += 1
                    break
                junk += 1; stats["junk"] += 1                 # anything else (a stray 'C' after block 0's ACK, line noise): bounded, then the block is retried
                if junk >= junk_limit:
                    stats["retries"] += 1
                    break
        raise YModemError(f"no ACK for {what} after {retries} attempts")

    await_c("the header")
    send_block(_block(0, name.encode("ascii") + b"\x00" + str(len(data)).encode("ascii") + b"\x00", 128), "the header block")
    await_c("the data")
    n = 1
    for off in range(0, len(data), 1024):
        send_block(_block(n, data[off:off + 1024], 1024), f"block {n}")
        stats["blocks"] += 1
        n += 1
    port.write(bytes([EOT]))
    c = _read_byte(port, 5.0, clock)
    if c == NAK:
        port.write(bytes([EOT]))
        c = _read_byte(port, 5.0, clock)
    if c != ACK:
        raise YModemError("the EOT was not acknowledged")
    await_c("the close")
    send_block(_block(0, b"", 128), "the empty header")
    stats["seconds"] = round(time.monotonic() - t0, 3)
    return stats


def receive(port, timeout: float = 600.0, max_bytes: int = 64 << 20, cancel_after_blocks: int | None = None) -> tuple[bytes, dict]:
    """Receive one file (the surrogate's `loady`); returns (bytes, {name, size, blocks, soh, stx, naks}). `cancel_after_blocks`:
    the surrogate's fault — the transfer is cancelled (CAN CAN) after that many data blocks. One cumulative deadline."""
    t0 = time.monotonic()
    clock = _Clock(timeout)
    if not (hasattr(port, "buf") and hasattr(port, "fill")):
        port._ym_buf = b""
    info = {"name": None, "size": None, "blocks": 0, "soh": 0, "stx": 0, "naks": 0, "cancelled": False}
    out = bytearray()
    expect = 0

    def read_exact(n: int, t: float) -> bytes | None:
        buf = bytearray()
        while len(buf) < n:
            b = _read_byte(port, t, clock)
            if b is None:
                return None
            buf.append(b)
        return bytes(buf)

    stage = "header"
    port.write(bytes([CRC]))
    last_c = time.monotonic()
    while clock.left() > 0:
        b = _read_byte(port, 1.0, clock)
        if b is None:
            if time.monotonic() - last_c > 3.0 and stage in ("header", "close"):
                port.write(bytes([CRC])); last_c = time.monotonic()
            continue
        if b in (SOH, STX):
            size = 128 if b == SOH else 1024
            rest = read_exact(2 + size + 2, 10.0)
            if rest is None:
                port.write(bytes([NAK])); info["naks"] += 1; continue
            n, ninv, payload, crc = rest[0], rest[1], rest[2:2 + size], int.from_bytes(rest[2 + size:], "big")
            if (n ^ ninv) != 0xFF or crc16(payload) != crc:
                port.write(bytes([NAK])); info["naks"] += 1; continue
            if stage == "header" or stage == "close":
                if n != 0:
                    port.write(bytes([NAK])); info["naks"] += 1; continue
                port.write(bytes([ACK]))
                if stage == "close" or payload[0] == 0:
                    break                                                     # the empty header: the batch ends
                name, _, tail = payload.partition(b"\x00")
                info["name"] = name.decode("ascii", "replace")
                size_s = tail.split(b"\x00", 1)[0].split(b" ")[0]
                info["size"] = int(size_s) if size_s.isdigit() else None
                stage = "data"; expect = 1
                port.write(bytes([CRC]))
                continue
            info["soh" if size == 128 else "stx"] += 1
            if n == ((expect - 1) & 0xFF):
                port.write(bytes([ACK])); continue                            # a repeated block: acknowledged, not stored
            if n != (expect & 0xFF):
                port.write(bytes([CAN, CAN])); info["cancelled"] = True; raise YModemError(f"block {n} out of sequence (expected {expect & 0xFF})")
            out += payload
            info["blocks"] += 1; expect += 1
            if len(out) > max_bytes:
                port.write(bytes([CAN, CAN])); info["cancelled"] = True; raise YModemError("too large")
            if cancel_after_blocks is not None and info["blocks"] >= cancel_after_blocks:
                port.write(bytes([CAN, CAN])); info["cancelled"] = True; raise YModemError(f"cancelled after {info['blocks']} blocks (the surrogate's fault)")
            port.write(bytes([ACK]))
        elif b == EOT:
            if stage != "data":
                continue
            port.write(bytes([NAK]))
            b2 = _read_byte(port, 5.0, clock)
            if b2 == EOT:
                port.write(bytes([ACK]))
            stage = "close"
            port.write(bytes([CRC])); last_c = time.monotonic()
        elif b == CAN:
            info["cancelled"] = True
            raise YModemError("cancelled by the sender")
    if stage != "close" and info["blocks"] == 0:
        raise YModemError("timeout before any block")
    if info["size"] is not None:
        out = out[:info["size"]]
    return bytes(out), info
