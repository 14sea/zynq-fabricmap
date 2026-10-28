#!/usr/bin/env python3
"""B4Q — the RUNNER ARCHIVE contract and its fresh verification (the owner's R1 / R4 on dad9e4de): a runner archive (transport
`console-pty-surrogate` — a host fixture — or `uart-board` — the device format) carries its raw streams (`raw/console.bin`: every
byte received; `raw/console_tx.bin`: every byte sent) and `uboot.json` (the control plane's steps, the admission, the load and page
witnesses, the execution phase). Nothing in uboot.json is an authority: every witness is RECOMPUTED here from the raw streams —

  * the image: the YMODEM blocks in the sent stream are re-assembled; their sha256 IS the transferred image, held to the archive's
    instrument / executing-side identity and to the context's pin; the device's `crc32 for <start> ... <end> ==> <v>` line is held to
    the crc32 of those bytes over exactly the loaded range; U-Boot's `## Total Size` to their length;
  * the page: the 24 `mw.l` commands in the sent stream (their addresses the page's, their words the transport's page words) and the
    `md.l` dump of the page in the received stream, equal;
  * the admission: the banner's `Model:` / `DRAM:` lines (or `bdinfo`) against the context's permitted models / minimum DRAM; the
    VARIANT word read at 0x43C02034 against the context's; FPGA0_CLK_CTRL recorded (held when the context holds it);
  * the execution phase: `go <addr>` in the sent stream and `## Starting application` in the received one, both or neither, as the
    declared phase says; a control-plane-only archive (no session) is accepted only when the streams show NO `go`, no board frames,
    no transaction directories, and — when it stopped — the named stop is DEMONSTRATED by the streams (a crc that differs, a page
    that differs, a model outside the permitted, a variant word that differs, no prompt, a cancelled transfer);
  * the console linkage: every board line the session retained occurs in the received stream after the `go` line, in order; every
    host line in the sent stream after the `go` command, in order.

Provenance (R4) is reported APART from consistency: a PTY archive is a declared host fixture; a `uart-board` archive is the device
FORMAT — its internal consistency is held, but nothing here establishes that anything was observed on a device (that is a later
ruling's claim, not this verifier's); a synthetic device-format fixture says so in its manifest and is reported as such; a device-format
archive that carries emulator-only witnesses (a surrogate banner, a backend, a private directory, `emulated: true`) is found."""
from __future__ import annotations

import hashlib
import json
import re
import sys
import zlib
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_regmap as rm  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_wire as wire  # noqa: E402
import b4q_zynq_clk as zc  # noqa: E402

ROLES_CONTENT = ("verify", "sacrificial")                                # the fixed content-class policy (docs/board_roles.md): a context narrows it, never widens it

RUNNER_KINDS = ("console-pty-surrogate", "uart-board")
PRE_GO_PHASES = ("init", "prompt", "admitted", "loaded", "page-written", "pre-go")
POST_GO_PHASES = ("go-issued", "application", "ended")
VARIANT_ADDR = bk.AXI_BASE + rm.VARIANT
SLCR_FPGA0_CLK_CTRL = 0xF8000170
SLCR_ARM_PLL_CTRL, SLCR_DDR_PLL_CTRL, SLCR_IO_PLL_CTRL = 0xF8000100, 0xF8000104, 0xF8000108
PS_CLK_MHZ = 33.333333
ENV_RE = re.compile(rb"^(boardid|role)=([^\r\n]*)", re.M)
PL_READ_RE = re.compile(rb"md\.l 43c[0-9a-f]{5} [0-9a-f]+\r")


fclk0_from_words = zc.fclk0_from_words                                   # the arithmetic helper; the eligibility is zc.fclk0_eligibility (one module, written against UG585)


def first_pl_reply_offset(rx: bytes) -> int | None:
    """The earliest receive-side boundary of a PL access: its command echo or data reply. Admission inputs must precede the
    command being handled, not merely its eventual data reply. The existing helper name is retained for compatibility."""
    offsets = [off for off, a, _ in md_dumps(rx) if bk.AXI_BASE <= a < bk.AXI_BASE + 0x10000]
    echo = PL_READ_RE.search(rx)
    if echo is not None:
        offsets.append(echo.start())
    return min(offsets) if offsets else None
PROMPT_RE = re.compile(rb"(?:zynq-uboot|Zynq)> ")
MODEL_RE = re.compile(rb"^Model: (.+?)\r?$", re.M)
DRAM_RE = re.compile(rb"^DRAM: +(?:ECC [a-z]+ )?(\d+) MiB", re.M)
BDINFO_SIZE_RE = re.compile(rb"-> size += 0x([0-9a-fA-F]+)")
MD_LINE_RE = re.compile(rb"^([0-9a-fA-F]{8}):((?: [0-9a-fA-F]{8}){1,4}) +[^\n]*$", re.M)
CRC_RE = re.compile(rb"crc32 for ([0-9a-fA-F]{8}) \.\.\. ([0-9a-fA-F]{8}) ==> ([0-9a-fA-F]{8})")
TOTAL_RE = re.compile(rb"## Total Size = 0x([0-9a-fA-F]+)")
STARTING_RE = re.compile(rb"## Starting application[^\n]*\n")      # the whole start line: what follows it is the application's
READY_RE = re.compile(rb"## Ready for binary \(ymodem\) download")
CMD_RE = re.compile(rb"(loady [0-9a-f]{8}|crc32 [0-9a-f]{8} [0-9a-f]+|mw\.l [0-9a-f]{8} [0-9a-f]{8} 1|md\.l [0-9a-f]{8} [0-9a-f]+|go [0-9a-f]{8}|bdinfo|version|printenv [a-z]+)\r")
FRAME_RE = re.compile(rb"B4Q1 [A-Z]+ \d+ [0-9a-f]{32} [^\n]*\n")
SURROGATE_MARK = b"(surrogate)"
SOH, STX, EOT, ACK, NAK, CAN = 0x01, 0x02, 0x04, 0x06, 0x15, 0x18


class RunnerRefusal(ValueError):
    pass


def _need(cond: bool, why: str):
    if not cond:
        raise RunnerRefusal(why)


def _fields(obj, where: str, spec: dict):
    _need(isinstance(obj, dict), f"{where}: not an object")
    for k, typ in spec.items():
        _need(k in obj, f"{where}.{k}: missing")
        if typ is not None:
            _need(isinstance(obj[k], typ), f"{where}.{k}: not a {typ.__name__}")


def load_runner(d: Path, manifest: dict) -> dict:
    """The runner material's SHAPE (refused by name): uboot.json's typed fields, the raw streams present and the bytes the manifest's
    runner record declares (digest / length)."""
    d = Path(d)
    tr = manifest.get("transport") or {}
    _need(tr.get("kind") in RUNNER_KINDS, f"transport.kind {tr.get('kind')!r} is not a runner transport")
    for f in ("uboot.json", "raw/console.bin", "raw/console_tx.bin"):
        _need((d / f).is_file(), f"{f}: missing (a runner archive retains its control plane and both raw streams)")
    try:
        u = json.loads((d / "uboot.json").read_text())
    except ValueError as e:
        raise RunnerRefusal(f"uboot.json: not JSON ({e})")
    _fields(u, "uboot.json", {"schema": str, "schema_version": int, "kind": str, "phase": str, "context": dict, "stops": list, "uboot_steps": list, "raw": dict, "admission": None, "load_witness": None, "page_witness": None, "go": None})
    _need(u["schema"] == "b4q_runner_uboot" and u["schema_version"] == 2, f"uboot.json: schema {u['schema']} v{u['schema_version']} is not b4q_runner_uboot v2")
    _need(u["kind"] == tr["kind"], "uboot.json.kind is not the transport's kind")
    _need(u["phase"] in PRE_GO_PHASES + POST_GO_PHASES + ("stopped",), f"uboot.json.phase {u['phase']!r} unknown")
    _fields(u["context"], "uboot.json.context", {"image_sha256": str, "image_path": str, "pin_source": str, "board_models": list, "dram_min_mib": int, "variant_word": int, "load_addr": int,
                                                 "allowed_roles": list, "purpose": str})
    _need(u["context"].get("expected_boardid") is None or isinstance(u["context"]["expected_boardid"], str), "uboot.json.context.expected_boardid: not a string or null")
    _need(isinstance(u["raw"].get("incomplete_writes", []), list), "uboot.json.raw.incomplete_writes: not a list")
    rx, tx = (d / "raw/console.bin").read_bytes(), (d / "raw/console_tx.bin").read_bytes()
    _fields(u["raw"], "uboot.json.raw", {"console_bin_sha256": str, "console_bin_bytes": int, "console_tx_bin_sha256": str, "console_tx_bin_bytes": int})
    _need(hashlib.sha256(rx).hexdigest() == u["raw"]["console_bin_sha256"] and len(rx) == u["raw"]["console_bin_bytes"], "raw/console.bin: not the bytes uboot.json declares")
    _need(hashlib.sha256(tx).hexdigest() == u["raw"]["console_tx_bin_sha256"] and len(tx) == u["raw"]["console_tx_bin_bytes"], "raw/console_tx.bin: not the bytes uboot.json declares")
    rtr = tr.get("runner")
    _need(isinstance(rtr, dict) and rtr.get("raw") == u["raw"] and rtr.get("phase") == u["phase"], "manifest.transport.runner is not uboot.json (raw digests / phase)")
    return {"u": u, "rx": rx, "tx": tx}


# ---------------------------------------------------------------- the streams, parsed
def commands(tx: bytes) -> list[tuple[int, str]]:
    return [(m.start(), m.group(1).decode("ascii")) for m in CMD_RE.finditer(tx)]


def ymodem_payload(tx: bytes, start: int) -> tuple[bytes | None, dict]:
    """The file the sender put on the line after `start` (the loady command): the header block's name / size, the data blocks in order
    (their CRC-16 held), trimmed to the declared size. None when no header block follows."""
    k = tx.find(bytes([SOH, 0x00, 0xFF]), start)
    if k < 0:
        return None, {"error": "no ymodem header block"}
    hdr = tx[k + 3:k + 3 + 128]
    name, _, rest = hdr.partition(b"\x00")
    size_s = rest.split(b"\x00", 1)[0].split(b" ")[0]
    size = int(size_s) if size_s.isdigit() else None
    pos = k + 3 + 128 + 2
    out = bytearray()
    n = 1
    blocks = 0
    while pos + 3 <= len(tx) and tx[pos] == STX:
        blk, inv = tx[pos + 1], tx[pos + 2]
        if (blk ^ inv) != 0xFF:
            break
        payload = tx[pos + 3:pos + 3 + 1024]
        crc = int.from_bytes(tx[pos + 3 + 1024:pos + 3 + 1026], "big")
        if _crc16(payload) != crc:
            return None, {"error": f"block {n}: a CRC-16 that does not match its payload"}
        if blk == (n & 0xFF):
            out += payload; blocks += 1; n += 1
        pos += 3 + 1024 + 2
    if size is not None:
        out = out[:size]
    return bytes(out), {"name": name.decode("ascii", "replace"), "size": size, "blocks": blocks, "end": pos}


def _crc16(data: bytes) -> int:
    c = 0
    for b in data:
        c ^= b << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
    return c


def md_dumps(rx: bytes) -> list[tuple[int, int, list[int]]]:
    """Every md.l line of the received stream: (offset, address, words)."""
    return [(m.start(), int(m.group(1), 16), [int(w, 16) for w in m.group(2).split()]) for m in MD_LINE_RE.finditer(rx)]


def md_value(rx: bytes, addr: int, before: int | None = None, after: int = 0) -> int | None:
    """The LAST word the received stream shows for `addr` (an md.l line starting at it) between `after` and `before`."""
    v = None
    for off, a, words in md_dumps(rx):
        if off < after or (before is not None and off >= before):
            continue
        if a <= addr < a + 4 * len(words):
            v = words[(addr - a) // 4]
    return v


def page_dump(rx: bytes, page_addr: int, n: int, after: int = 0, before: int | None = None) -> list[int] | None:
    """The last complete dump of the page (n words from page_addr, consecutive lines) in the window."""
    lines = [(off, a, w) for off, a, w in md_dumps(rx) if off >= after and (before is None or off < before)]
    best = None
    for i, (off, a, w) in enumerate(lines):
        if a != page_addr:
            continue
        words, expect, j = [], page_addr, i
        while j < len(lines) and lines[j][1] == expect and len(words) < n:
            words += lines[j][2]; expect += 4 * len(lines[j][2]); j += 1
        if len(words) >= n:
            best = words[:n]
    return best


# ---------------------------------------------------------------- the verification
def verify_runner(d: Path, manifest: dict, console: list | None, no_session: bool) -> dict:
    """The runner archive's consistency, recomputed from the raw streams; the provenance reported apart."""
    d = Path(d)
    F, L = [], []
    rep = {"findings": F, "limitations": L, "kind": (manifest.get("transport") or {}).get("kind"), "provenance": None, "phase": None, "witnesses": {}, "stop": None}
    try:
        A = load_runner(d, manifest)
    except RunnerRefusal as e:
        rep["refused"] = str(e)
        return rep
    u, rx, tx = A["u"], A["rx"], A["tx"]
    ctx, tr = u["context"], manifest["transport"]
    rep["phase"] = u["phase"]
    cmds = commands(tx)
    go_cmds = [(o, c) for o, c in cmds if c.startswith("go ")]
    loady_cmds = [(o, c) for o, c in cmds if c.startswith("loady ")]
    starting = STARTING_RE.search(rx)
    go_tx_off = go_cmds[0][0] if go_cmds else None
    go_rx_off = starting.end() if starting else None
    # ---- the provenance (R4), apart from everything below
    kind = tr["kind"]
    synthetic = manifest.get("synthetic")
    prov = {"kind": kind, "observed_on_device": False, "qualification": False, "synthetic": synthetic,
            "fixture": ctx.get("fixture"),
            "standing": ("a declared host fixture on a PTY: the device surrogate; never physical provenance" if kind == "console-pty-surrogate" else
                         ("a SYNTHETIC device-format fixture (the manifest says so): structural consistency only; never board evidence" if synthetic else
                          "the device format: this archive's internal consistency is held; that anything was observed on a device is NOT established here (a later ruling's claim)"))}
    rep["provenance"] = prov
    if kind == "console-pty-surrogate":
        if manifest.get("emulated") is not True:
            F.append("provenance: a PTY fixture archive not labelled emulated")
        if not ctx.get("fixture"):
            F.append("provenance: a PTY endpoint without a declared fixture profile in the context")
    else:
        if manifest.get("emulated") is not False:
            F.append("provenance: a device-format archive labelled emulated")
        if manifest.get("backend") is not None:
            F.append("provenance: a device-format archive carrying an emulated backend record (an emulator-only witness)")
        if SURROGATE_MARK in rx:
            F.append("provenance: a device-format archive whose received stream carries the surrogate's banner (an emulator-only witness: a downgraded fixture, not a device)")
        if (d / "private").exists():
            F.append("provenance: a device-format archive carrying a private/ directory (the surrogate's)")
        if ctx.get("fixture"):
            F.append("provenance: a device-format archive whose context declares a host fixture")
    # ---- the prompt and the board identity
    model = MODEL_RE.search(rx); dram = DRAM_RE.search(rx)
    model_s = model.group(1).decode("utf-8", "replace").strip() if model else None
    dram_mib = int(dram.group(1)) if dram else None
    if dram_mib is None:
        sizes = [int(x, 16) for x in BDINFO_SIZE_RE.findall(rx)]
        dram_mib = sum(sizes) // (1024 * 1024) if sizes else None
    prompt_seen = PROMPT_RE.search(rx) is not None
    adm = u.get("admission")
    if adm is not None and not isinstance(adm, dict):
        F.append("admission: not an object"); adm = {}
    adm = adm or {}
    board = adm.get("board") or {}
    model_ok = model_s is not None and any(m in model_s for m in ctx["board_models"])
    dram_ok = dram_mib is not None and dram_mib >= ctx["dram_min_mib"]
    rep["witnesses"]["board"] = {"model": model_s, "dram_mib": dram_mib, "prompt_seen": prompt_seen, "model_ok": model_ok, "dram_ok": dram_ok}
    if board:
        if board.get("model") != model_s or board.get("dram_mib") != dram_mib:
            F.append(f"admission.board: uboot.json says model {board.get('model')!r} / {board.get('dram_mib')} MiB, the received stream shows {model_s!r} / {dram_mib}")
        if bool(board.get("model_ok")) != model_ok or bool(board.get("dram_ok")) != dram_ok:
            F.append("admission.board: the recorded verdicts are not what the stream and the context give")
    # ---- the board's own identity and role (printenv in the streams), held to the context
    pl_off = first_pl_reply_offset(rx)
    prefix_end = pl_off if pl_off is not None else (go_rx_off if go_rx_off is not None else len(rx))   # admission inputs precede the first PL command echo or reply
    env = {}
    for m in ENV_RE.finditer(rx[:prefix_end]):
        env[m.group(1).decode()] = m.group(2).decode("utf-8", "replace").strip()
    boardid, role = env.get("boardid"), env.get("role")
    boardid_ok = ctx.get("expected_boardid") is not None and boardid == ctx["expected_boardid"]
    roles_in_floor = all(r in ROLES_CONTENT for r in ctx["allowed_roles"]) and bool(ctx["allowed_roles"])
    if not roles_in_floor:
        F.append(f"context: allowed_roles {ctx['allowed_roles']} widens the fixed content-class policy {list(ROLES_CONTENT)} (a context narrows it, never widens it)")
    role_ok = role in ROLES_CONTENT and role in ctx["allowed_roles"]      # the floor first, independently of the context
    rep["witnesses"]["identity"] = {"boardid": boardid, "role": role, "boardid_ok": boardid_ok, "role_ok": role_ok, "prefix_end": prefix_end}
    ident = adm.get("identity")
    if ident:
        if ident.get("boardid") != boardid or ident.get("role") != role or bool(ident.get("boardid_ok")) != boardid_ok or bool(ident.get("role_ok")) != role_ok:
            F.append(f"admission.identity: uboot.json says boardid {ident.get('boardid')!r} / role {ident.get('role')!r}, the received stream shows {boardid!r} / {role!r} against the context")
    # ---- the clock, derived from the PS words in the stream (BEFORE any PL read), held to the context
    words = {k: md_value(rx, zc.ADDR[k], before=prefix_end) for k in zc.WORDS}   # every input from the prefix BEFORE the first PL reply: a later good state is no earlier admission
    f0 = words["fpga0"]
    el_ = zc.fclk0_eligibility(words, ctx.get("ps_clk_mhz", PS_CLK_MHZ))
    mhz = (el_.get("nominal") or {}).get("mhz")
    clock = adm.get("clock")
    clock_ok = (el_["eligible"] and mhz is not None and (ctx.get("fclk0_mhz") is None or abs(mhz - ctx["fclk0_mhz"]) < 0.5)
                and (ctx.get("fclk0_ctrl_expected") is None or f0 == ctx["fclk0_ctrl_expected"]))
    rep["witnesses"]["clock"] = {"inputs": {k: (f"{v:08x}" if v is not None else None) for k, v in words.items()}, "eligibility": el_, "ok": clock_ok, "prefix_end": prefix_end}
    if clock:
        rec_in = {k: (v or {}).get("word") for k, v in (clock.get("inputs") or {}).items()}
        if rec_in != {k: (f"{v:08x}" if v is not None else None) for k, v in words.items()} or bool((clock.get("eligibility") or {}).get("eligible")) != el_["eligible"] or bool(clock.get("ok")) != clock_ok:
            F.append("admission.clock: the recorded inputs / eligibility / verdict are not what the stream's prefix before the first PL read and the context give")
    # the sent commands and their echoes in the received stream are one sequence (U-Boot echoes what it is sent): a stream reordered alone is found
    pre_go_tx = tx[:go_tx_off] if go_tx_off is not None else tx
    sent_cmds = [c for _, c in commands(pre_go_tx)]
    echoed = [m.group(1).decode("ascii") for m in re.finditer(rb"(?:^|> )(loady [0-9a-f]{8}|crc32 [0-9a-f]{8} [0-9a-f]+|mw\.l [0-9a-f]{8} [0-9a-f]{8} 1|md\.l [0-9a-f]{8} [0-9a-f]+|bdinfo|version|printenv [a-z]+)\r?$", rx[:go_rx_off] if go_rx_off is not None else rx, re.M)]   # U-Boot echoes the command after its prompt on the same line
    sent_cmp = [c for c in sent_cmds if not c.startswith("go ")]
    if echoed != sent_cmp:
        k = next((i for i, (x, y) in enumerate(zip(echoed, sent_cmp)) if x != y), min(len(echoed), len(sent_cmp)))
        F.append(f"the command echoes in the received stream are not the sent commands in order (they differ at command {k}: echoed {echoed[k] if k < len(echoed) else '(end)'!r}, sent {sent_cmp[k] if k < len(sent_cmp) else '(end)'!r})")
    # the order: every identity / clock command (printenv boardid / role, the six words) before the first PL read command in the sent stream
    first_pl = PL_READ_RE.search(tx)
    if first_pl is not None:
        required = [b"printenv boardid\r", b"printenv role\r"] + [f"md.l {zc.ADDR[k]:08x} 1\r".encode() for k in zc.WORDS]
        late = [c.decode().strip() for c in required if tx.find(c) < 0 or tx.find(c) > first_pl.start()]
        if late:
            F.append(f"admission: a PL read was issued before the identity / clock inputs were all read ({', '.join(late)} missing or later): the order a stopped clock forbids")
    # ---- the carrier (VARIANT)
    carrier = adm.get("carrier")
    v = md_value(rx, VARIANT_ADDR, before=go_rx_off)
    rep["witnesses"]["variant"] = f"{v:08x}" if v is not None else None
    variant_ok = v is not None and v == ctx["variant_word"]
    if carrier:
        if v is None:
            F.append("admission.carrier: no md.l of the VARIANT word (0x43C02034) in the received stream")
        elif f"{v:08x}" != carrier.get("variant") or (v == ctx["variant_word"]) != bool(carrier.get("equal")):
            F.append(f"admission.carrier: uboot.json says {carrier.get('variant')} equal={carrier.get('equal')}, the stream shows {v:08x} against the context's {ctx['variant_word']:08x}")
    # ---- the image: the transferred bytes, the device's crc over the range, U-Boot's total
    lw = u.get("load_witness")
    image_sha = None
    if loady_cmds:
        payload, info = ymodem_payload(tx, loady_cmds[-1][0])
        complete = payload is not None and info.get("size") is not None and len(payload) == info["size"] and info.get("blocks", 0) >= (info["size"] + 1023) // 1024
        if payload is None:
            F.append(f"load: the sent stream holds no re-assemblable ymodem transfer after `loady` ({info.get('error')})")
        elif not complete:
            # an INCOMPLETE transfer (cancelled, cut): no identity of the transferred bytes is claimed or held; a load witness recorded for it is a finding
            rep["witnesses"]["image"] = {"complete": False, "blocks": info.get("blocks"), "size": info.get("size"), "bytes": len(payload), "cancelled": bytes([CAN, CAN]) in rx}
            if lw is not None:
                F.append("load witness recorded for a transfer the sent stream shows incomplete")
        else:
            image_sha = hashlib.sha256(payload).hexdigest()
            host_crc = zlib.crc32(payload) & 0xFFFFFFFF
            addr = int(loady_cmds[-1][1].split()[1], 16)
            total = TOTAL_RE.search(rx, 0)
            crc_m = None
            for m in CRC_RE.finditer(rx):
                if go_rx_off is None or m.start() < go_rx_off:
                    crc_m = m
            rep["witnesses"]["image"] = {"transferred_sha256": image_sha, "bytes": len(payload), "host_crc32": f"{host_crc:08x}", "ymodem": info,
                                         "total": int(total.group(1), 16) if total else None,
                                         "device_crc": {"range": [crc_m.group(1).decode(), crc_m.group(2).decode()], "value": crc_m.group(3).decode()} if crc_m else None}
            if image_sha != manifest["instrument"]["image_sha256"]:
                F.append("load: the transferred bytes are not the archive's executing-side image (instrument.image_sha256)")
            if image_sha != ctx["image_sha256"]:
                F.append("load: the transferred bytes are not the context's pinned image")
            if total is None or int(total.group(1), 16) != len(payload):
                F.append("load: U-Boot's `## Total Size` is absent or not the transferred length")
            if crc_m is None:
                F.append("load: no `crc32 for <start> ... <end> ==> <value>` line before `go`")
            else:
                start, end, val = int(crc_m.group(1), 16), int(crc_m.group(2), 16), int(crc_m.group(3), 16)
                if (start, end) != (addr, addr + len(payload) - 1):
                    F.append(f"load: the device's crc32 is over {start:08x}..{end:08x}, not the loaded range {addr:08x}..{addr + len(payload) - 1:08x}")
                equal = val == host_crc
                if lw is None:
                    F.append("load: a transfer and a crc32 in the streams but no load witness recorded")
                else:
                    if lw.get("host_crc32") != f"{host_crc:08x}" or lw.get("uboot_crc32") != f"{val:08x}" or bool(lw.get("equal")) != equal or lw.get("bytes") != len(payload):
                        F.append(f"load witness: uboot.json says host {lw.get('host_crc32')} / device {lw.get('uboot_crc32')} equal={lw.get('equal')}; the streams give host {host_crc:08x} / device {val:08x}")
                    if lw.get("image_sha256") != image_sha:
                        F.append("load witness: its image sha256 is not the transferred bytes'")
                rep["witnesses"]["image"]["equal"] = equal
    elif lw is not None:
        F.append("load witness recorded but no `loady` in the sent stream")
    # ---- the page: the mw.l words sent, the md.l dump received
    pw = u.get("page_witness")
    mws = [(o, c) for o, c in cmds if c.startswith("mw.l ")]
    page_mw = [(int(c.split()[1], 16), int(c.split()[2], 16)) for o, c in mws if wire.PAGE_ADDR <= int(c.split()[1], 16) < wire.PAGE_ADDR + 4 * wire.PAGE_WORDS and (go_tx_off is None or o < go_tx_off)]
    if page_mw or pw is not None:
        written = [None] * wire.PAGE_WORDS
        for a, v in page_mw:
            written[(a - wire.PAGE_ADDR) // 4] = v
        back = page_dump(rx, wire.PAGE_ADDR, wire.PAGE_WORDS, before=go_rx_off)
        rep["witnesses"]["page"] = {"written": [f"{w:08x}" if w is not None else None for w in written], "read_back": [f"{w:08x}" for w in back] if back else None}
        if None in written:
            F.append(f"page: only {sum(1 for w in written if w is not None)} of the {wire.PAGE_WORDS} page words were written with mw.l before `go`")
        if back is None:
            F.append("page: no md.l dump of the page in the received stream before `go`")
        if pw is None:
            F.append("page: mw.l commands in the sent stream but no page witness recorded")
        elif None not in written and back is not None:
            equal = back == written
            if pw.get("written") != [f"{w:08x}" for w in written] or pw.get("read_back") != [f"{w:08x}" for w in back] or bool(pw.get("equal")) != equal:
                F.append("page witness: uboot.json's written / read_back / equal are not what the streams show")
            if tr.get("page_words") and tr["page_words"] != [f"{w:08x}" for w in written]:
                F.append("page: the transport's page words are not the ones written with mw.l")
            if equal:
                nonce_lo, nonce_hi = md_value(rx, bk.AXI_BASE + rm.NONCE_LO, before=go_rx_off), md_value(rx, bk.AXI_BASE + rm.NONCE_HI, before=go_rx_off)
                page = wire.parse_page(written)
                if page is not None and (nonce_lo is None or nonce_hi is None or page["nonce_seen"] != ((nonce_hi << 32) | nonce_lo)):
                    F.append("page: the nonce the page carries is not the one md.l showed for NONCE_LO / NONCE_HI before `go`")
            rep["witnesses"]["page"]["equal"] = equal
    # ---- the execution phase against the streams
    phase = u["phase"]; at_stop = u.get("phase_at_stop")
    effective = at_stop if phase == "stopped" else phase
    go_declared = effective in POST_GO_PHASES
    if bool(go_cmds) != go_declared:
        F.append(f"phase: uboot.json says {effective!r} but the sent stream {'holds' if go_cmds else 'holds no'} `go`")
    # ---- the state machine (C1): a `go` requires every prerequisite RECOMPUTED true, not merely recorded — the admission complete and ok
    # (the image equal to the pin, the board class, the identity, the clock, the carrier), the load witness equal, the page witness equal;
    # and the addresses bound: the context's load address = `loady`'s = the crc range's start = `go`'s = U-Boot's start line
    if go_cmds:
        img_w = rep["witnesses"].get("image") or {}
        pg_w = rep["witnesses"].get("page") or {}
        missing = []
        if not adm:
            missing.append("no admission recorded")
        else:
            if not adm.get("ok"):
                missing.append("admission.ok is not true")
            if not (adm.get("image") or {}).get("equal") or (adm.get("image") or {}).get("pin") != ctx["image_sha256"]:
                missing.append("the admitted image is not the pinned one")
        if not model_ok or not dram_ok:
            missing.append("the board class (model / DRAM) does not admit this image")
        if not boardid_ok or not role_ok:
            missing.append("the board's identity / role does not admit this run")
        if not clock_ok:
            missing.append("the clock derivation does not admit a PL access")
        if not variant_ok:
            missing.append("the carrier's variant word is not the pinned one")
        if img_w.get("complete") is False or img_w.get("equal") is not True or img_w.get("transferred_sha256") != ctx["image_sha256"]:
            missing.append("the load witness is not a complete, equal transfer of the pinned image")
        if pg_w.get("equal") is not True:
            missing.append("the page witness is not equal")
        if missing:
            F.append("state: `go` was issued although " + "; ".join(missing) + " (execution after a failed or missing prerequisite)")
        addrs = {"context": ctx["load_addr"], "go": int(go_cmds[0][1].split()[1], 16)}
        if loady_cmds:
            addrs["loady"] = int(loady_cmds[-1][1].split()[1], 16)
        if img_w.get("device_crc"):
            addrs["crc_start"] = int(img_w["device_crc"]["range"][0], 16)
        sm = re.search(rb"## Starting application at 0x([0-9a-fA-F]{8})", rx)
        if sm:
            addrs["started_at"] = int(sm.group(1), 16)
        if len(set(addrs.values())) != 1:
            F.append("state: the load / crc / go / start addresses are not one address bound to the context: " + ", ".join(f"{k}={v:#010x}" for k, v in addrs.items()))
        rep["witnesses"]["addresses"] = {k: f"{v:#010x}" for k, v in addrs.items()}
    if (starting is not None) and not go_cmds:
        F.append("phase: `## Starting application` in the received stream without a `go` command sent")
    if go_cmds and effective == "go-issued" and starting is None:
        L.append("the `go` command was issued and U-Boot's start line never came: an unknown execution state (the phase persisted before the command says so)")
    g = u.get("go")
    if go_cmds and not (isinstance(g, dict) and g.get("issued")):
        F.append("phase: `go` in the sent stream but uboot.json.go does not say it was issued")
    # ---- a control-plane-only archive (no session)
    tx_dirs = sorted(p.name for p in d.iterdir() if p.is_dir() and p.name.startswith("tx_"))
    board_frames = [e for e in (console or []) if e.get("dir") == "board" and e.get("line")]
    if no_session:
        stops = u.get("stops") or []
        if tx_dirs:
            F.append(f"no session: transaction directories present ({tx_dirs})")
        if board_frames:
            F.append(f"no session: {len(board_frames)} board console line(s) retained")
        if effective in PRE_GO_PHASES:
            # a control-plane-only archive: the streams must show NO `go`
            if go_cmds or starting is not None:
                F.append("no session: the streams show `go` / the application's start — not a control-plane-only archive")
            if stops:
                why = stops[0].get("why", "")
                rep["stop"] = {"why": why, "demonstrated": _demonstrated(why, rx, tx, ctx, rep["witnesses"], prompt_seen, loady_cmds, model_s, dram_mib)}
                if rep["stop"]["demonstrated"] is False:
                    F.append(f"no session: the named stop ({why[:60]}…) is not demonstrated by the raw streams")
                elif rep["stop"]["demonstrated"] is None:
                    F.append(f"no session: the named stop ({why[:60]}…) is of a class this verifier cannot demonstrate from the streams: unverified")
            elif effective != "pre-go":
                F.append(f"no session, no stop, and the phase is {effective!r}: an incomplete control plane without a named stop")
        else:
            # `go` was issued and no opening followed (the application silent, a reset): the streams must show the `go`, nothing framed after it,
            # and the named transport stop
            if not go_cmds:
                F.append(f"no session: the phase {effective!r} is past the control plane but the sent stream holds no `go`")
            after = rx[go_rx_off:] if go_rx_off is not None else rx[-0:]
            if FRAME_RE.search(after):
                F.append("no session: framed board lines follow `go` in the received stream, yet no opening was recorded")
            if not stops:
                F.append(f"no session, no stop, and the phase is {effective!r}: an opening that never came and was never named")
            else:
                why = stops[0].get("why", "")
                dem = None
                if why.startswith("the console was silent"):
                    dem = not FRAME_RE.search(after)
                elif why.startswith("a boot banner"):
                    dem = re.search(rb"^(?:U-Boot SPL|U-Boot \d|Trying to boot from|Model: Ebang)", after, re.M) is not None
                elif why.startswith("go:"):
                    dem = starting is None
                rep["stop"] = {"why": why, "demonstrated": dem}
                if dem is False:
                    F.append(f"no session: the named stop after `go` ({why[:60]}…) is not demonstrated by the raw streams")
                elif dem is None:
                    F.append(f"no session: the named stop after `go` ({why[:60]}…) is of a class this verifier cannot demonstrate: unverified")
    else:
        if not go_cmds:
            F.append("a session archive whose sent stream holds no `go`")
        # ---- the console ACCOUNTING: the application's exchange as the raw streams hold it, line by line after `go`, must BE the retained
        # console — every received line is a retained board entry (a frame, a noted unparsable line, a noted banner), in order, and every
        # sent frame a retained host entry; nothing observed disappears from the interpreted exchange (an END before the IDENT included)
        rx_lines = [ln for ln in rx[go_rx_off or 0:].split(b"\n")[:-1]]
        rx_lines = [ln.rstrip(b"\r") for ln in rx_lines]
        rx_lines = [ln for ln in rx_lines if ln.strip()]                           # the empty lines (U-Boot's CR LF after `go`) are not console lines
        retained = [e["line"].encode("utf-8") for e in (console or []) if e.get("dir") == "board" and e.get("line")]
        cut_at = next((i for i, e in enumerate([x for x in (console or []) if x.get("dir") == "board" and x.get("line")]) if (e.get("note") or "").startswith("a boot banner")), None)
        if cut_at is not None and len(rx_lines) > cut_at + 1 and rx_lines[:cut_at + 1] == retained[:cut_at + 1]:
            rep["witnesses"]["after_cut"] = {"lines": len(rx_lines) - cut_at - 1, "note": "the received lines after the noted boot banner: the PS's reset boot output, accounted as after the cut, not the session's"}
            rx_lines = rx_lines[:cut_at + 1]                                     # the cut: what follows the banner is the device booting again, retained raw, not console
        if rx_lines != retained:
            k = next((i for i, (a_, b_) in enumerate(zip(rx_lines, retained)) if a_ != b_), min(len(rx_lines), len(retained)))
            what = rx_lines[k][:50] if k < len(rx_lines) else b"(end)"
            F.append(f"console accounting: the received stream after `go` holds {len(rx_lines)} line(s), the retained console {len(retained)} board line(s); they differ at line {k}: stream {what!r}")
        tx_frames = [m.group(0).rstrip(b"\n") for m in FRAME_RE.finditer(tx[go_tx_off or 0:])]
        sent = [e["line"].encode("utf-8") for e in (console or []) if e.get("dir") == "host" and e.get("line")]
        if tx_frames != sent:
            F.append(f"console accounting: the sent stream after `go` holds {len(tx_frames)} framed line(s), the retained console {len(sent)} host line(s), or their order differs")
        tx_tail = tx[go_tx_off or 0:]
        tx_tail = tx_tail[tx_tail.find(b"\r") + 1:] if b"\r" in tx_tail else b""      # after the go command itself
        other = FRAME_RE.sub(b"", tx_tail)
        if other.strip():
            F.append(f"console accounting: {len(other.strip())} sent byte(s) after `go` that are not framed host lines")
    # ---- the admission's image pin held to what was transferred (or, before any load, to the context)
    img = adm.get("image")
    if img:
        if img.get("pin") != ctx["image_sha256"] or bool(img.get("equal")) != (img.get("file_sha256") == ctx["image_sha256"]):
            F.append("admission.image: the recorded pin / verdict are not the context's")
        if image_sha is not None and img.get("file_sha256") != image_sha:
            F.append("admission.image: the file's sha256 recorded is not the transferred bytes'")
    return rep


def _demonstrated(why: str, rx: bytes, tx: bytes, ctx: dict, W: dict, prompt_seen: bool, loady_cmds: list, model_s, dram_mib) -> bool | None:
    """Is the named control-plane stop what the streams show? True / False, or None for a stop class this verifier does not know."""
    if why.startswith("no U-Boot prompt"):
        return not prompt_seen
    if why.startswith("image: the selected file"):
        return not loady_cmds                                                 # refused before any load: nothing more the streams can show
    if why.startswith("board: the model"):
        return model_s is None or not any(m in model_s for m in ctx["board_models"])
    if why.startswith("board: DRAM"):
        return dram_mib is not None and dram_mib < ctx["dram_min_mib"]
    if why.startswith("carrier: the VARIANT"):
        v = W.get("variant")
        return v is not None and int(v, 16) != ctx["variant_word"]
    if why.startswith("clock:"):
        return W.get("clock", {}).get("ok") is False
    if why.startswith("context:"):
        return True                                                           # a refused context: nothing was issued (the streams hold the prompt alone)
    if why.startswith("identity: the board's boardid") or why.startswith("identity: the board's role") or why.startswith("identity: the context pins no boardid"):
        ide = W.get("identity", {})
        return not (ide.get("boardid_ok") and ide.get("role_ok"))
    if why.startswith("persistence failed") or why.startswith("load refused") or " refused: persistence failed" in why:
        return True                                                           # the host's own barrier: the streams show nothing guarded after it (held elsewhere)
    if why.startswith("load witness:"):
        return W.get("image", {}).get("equal") is False
    if why.startswith("loady:"):
        return bool(loady_cmds) and (bytes([CAN, CAN]) in rx or TOTAL_RE.search(rx) is None or W.get("image", {}).get("total") != W.get("image", {}).get("bytes"))
    if why.startswith("page witness:"):
        return W.get("page", {}).get("equal") is False
    if why.startswith("md.l") or why.startswith("crc32:"):
        return True                                                           # a malformed reply: the stream holds whatever came; the runner's refusal is the record
    return None
