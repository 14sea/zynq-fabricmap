#!/usr/bin/env python3
"""B4Q — the Python TWIN of the board application's console framing (firmware/b4q/target/b4q_wire.c) and the host side of its
identity page: the framed line, its CRC (IEEE 802.3, zlib's) over everything before the final field, the padded base64url
payload (the instrument's alphabet), the parse with the same refusal codes, and the 24-word page the host writes at
B4Q_PAGE_ADDR before `go`. tests/test_b4q_wire.py holds the C unit to this twin on fixed and random inputs; the console
session (host/b4q_console_session.py) speaks through it."""
from __future__ import annotations

import base64
import os
import zlib

MAGIC = "B4Q1"
TOKEN_HEX = 32
ZERO_TOKEN = "0" * TOKEN_HEX
PAGE_ADDR = 0x10440000
PAGE_WORDS = 24
PAGE_MAGIC = 0x42345149
PAGE_LAYOUT = 1
PAGE_FLAG_WATCHDOG = 0x2
BOARD_TYPES = ("IDENT", "HB", "SIGNREQ", "EV", "RESULT", "NACK", "END")
HOST_TYPES = ("TX", "QUIT", "SIGNREPLY")


class WireError(ValueError):
    pass


def crc32(data: bytes) -> int:
    return zlib.crc32(data) & 0xFFFFFFFF


def b64(plain: bytes) -> str:
    return base64.urlsafe_b64encode(plain).decode("ascii") if plain else "-"


def unb64(s: str) -> bytes:
    if s == "-":
        return b""
    if len(s) % 4 or any(c not in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_=" for c in s):
        raise WireError("bad payload")
    pad = s.count("=")
    if pad > 2 or (pad and not s.endswith("=" * pad)) or "=" in s[:-pad or None]:
        raise WireError("bad payload")
    try:
        return base64.urlsafe_b64decode(s)
    except ValueError as e:
        raise WireError(f"bad payload: {e}")


def frame(kind: str, seq: int, token: str, plain: bytes | str = b"") -> str:
    """The framed line, with its newline."""
    if isinstance(plain, str):
        plain = plain.encode("utf-8")
    if len(token) != TOKEN_HEX or " " in kind or not kind:
        raise WireError("bad frame fields")
    head = f"{MAGIC} {kind} {seq} {token} {b64(plain)}"
    return f"{head} {crc32(head.encode('ascii')):08x}\n"


def parse(line: str, want_token: str | None = None) -> dict:
    """{type, seq, token, payload (bytes)}; raises WireError with the C unit's reason: 'bad crc' (-1), 'not a B4Q1 frame' (-2),
    'wrong token' (-3), 'bad payload'."""
    line = line.rstrip("\r\n")
    if " " not in line:
        raise WireError("not a B4Q1 frame")
    head, _, tail = line.rpartition(" ")
    if f"{crc32(head.encode('ascii', 'replace')):08x}" != tail:
        raise WireError("bad crc")
    f = head.split(" ", 4)
    if len(f) != 5 or f[0] != MAGIC or len(f[1]) >= 16 or len(f[3]) != TOKEN_HEX or not f[2].isdigit() or len(f[2]) > 10 or int(f[2]) > 0xFFFFFFFF:
        raise WireError("not a B4Q1 frame")
    if want_token is not None and f[3] != want_token:
        raise WireError("wrong token")
    payload = unb64(f[4])
    if b"\0" in payload:
        raise WireError("bad payload")
    return {"type": f[1], "seq": int(f[2]), "token": f[3], "payload": payload}


# ---------------------------------------------------------------- the identity page (the host's act, before `go`)
def page_words(token_hex: str, uboot_epoch: int, app_image_sha256: str, carrier_sha256: str, nonce_seen: int, status_seen: int, flags: int) -> list[int]:
    """The 24 words the host writes at PAGE_ADDR (`mw.l`, one word each, as the instrument's L5 runner does): magic, layout, the
    token (4 words big-endian), the U-Boot epoch, the image's sha256 low 32 bits (big-endian of its first 4 bytes), the carrier's
    sha256 (8 words), the nonce the host saw (lo, hi), the STATUS it saw, the flags, three reserved zeros, the xor checksum."""
    if len(token_hex) != TOKEN_HEX or len(carrier_sha256) != 64 or len(app_image_sha256) != 64:
        raise WireError("bad page fields")
    w = [PAGE_MAGIC, PAGE_LAYOUT] + [int(token_hex[8 * i:8 * i + 8], 16) for i in range(4)] + [uboot_epoch & 0xFFFFFFFF, int(app_image_sha256[:8], 16)]
    w += [int(carrier_sha256[8 * i:8 * i + 8], 16) for i in range(8)]
    w += [nonce_seen & 0xFFFFFFFF, (nonce_seen >> 32) & 0xFFFFFFFF, status_seen & 0xFFFFFFFF, flags & 0xFFFFFFFF, 0, 0, 0]
    x = 0
    for v in w:
        x ^= v
    return w + [x]


def parse_page(words: list[int]) -> dict | None:
    if len(words) != PAGE_WORDS or words[0] != PAGE_MAGIC or words[1] != PAGE_LAYOUT or any(words[i] for i in (20, 21, 22)):
        return None
    x = 0
    for v in words[:-1]:
        x ^= v
    if words[-1] != x:
        return None
    return {"token": "".join(f"{v:08x}" for v in words[2:6]), "uboot_epoch": words[6], "app_image_sha_lo32": words[7],
            "carrier_sha256": "".join(f"{v:08x}" for v in words[8:16]), "nonce_seen": words[16] | (words[17] << 32), "status_seen": words[18], "flags": words[19]}


def new_token() -> str:
    return os.urandom(16).hex()


# ---------------------------------------------------------------- the command grammar (firmware/b4q/b4q_cmd.h), as the C unit checks it
_HEX = "0123456789abcdef"
_KINDS = ("normal", "root", "inject", "a5")


def _u32(tok: str, base: int, maxv: int) -> int | None:
    if not tok or len(tok) > (8 if base == 16 else 10) or any(c not in (_HEX if base == 16 else "0123456789") for c in tok):
        return None
    v = int(tok, base)
    return v if v <= maxv else None


def parse_tx(cmd: str) -> dict | None:
    """The TX grammar of b4q_cmd.h: {kind, genome, steps, task} or None when refused — held to the C parser by tests/test_b4q_app.py.
    Fields one or more spaces apart, trailing spaces allowed, nothing else."""
    if not cmd.startswith("TX ") or any(c in cmd for c in "\t\r\n"):
        return None
    toks = [t for t in cmd.split(" ") if t != ""]
    if len(toks) < 4 or toks[0] != "TX" or toks[1] not in _KINDS:
        return None
    genome = _u32(toks[2], 16, 0xFFFFFFFF)
    if genome is None or genome & ~0x001FFFFF:
        return None
    n = _u32(toks[3], 10, 28)
    if n is None or (toks[1] == "root" and n != 0) or len(toks) < 4 + n:
        return None
    steps = []
    for tok in toks[4:4 + n]:
        v = _u32(tok, 16, 0x1FFFFFF)
        if v is None:
            return None
        steps.append(v)
    rest = toks[4 + n:]
    task = None
    if rest:
        if rest[0] != "TASK" or len(rest) < 3 or len(rest[1]) != 64 or any(c not in _HEX for c in rest[1]):
            return None
        m = _u32(rest[2], 10, 256)
        if m is None or len(rest) != 3 + 4 * m:
            return None
        cells = []
        for j in range(m):
            s, e, t, w = (_u32(rest[3 + 4 * j + k], 10, mx) for k, mx in enumerate((n, 7, 1, 65535)))
            if s is None or s == 0 or e is None or t is None or w is None:
                return None
            cells.append((s, e, t, w))
        task = {"digest": rest[1], "cells": cells}
    return {"kind": toks[1], "genome": genome, "steps": steps, "task": task}
