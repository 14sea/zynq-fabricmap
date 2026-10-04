#!/usr/bin/env python3
"""B3 lifecycle 2 — the image's stack assessment, from the FINAL linked ELF (image stage 5; the owner's ruling of
2026-10-01).

    b3_image_stack.py [--elf b3/firmware/bsp/out/b3_app.elf] [--json]

The compiler's -fstack-usage covers what it compiled; the image also links the toolchain's prebuilt libc / libgcc
and hand-written BSP assembly. So the bound is taken from the image itself: the pinned toolchain's objdump
disassembles the ELF and every function's stack pointer is TRACKED ALONG EVERY PATH (not read off its prologue):

  * a worklist of (address, SP offset) states per function; every instruction that writes SP is modelled —
    push / pop, stmdb sp! / ldmia sp!, vpush / vpop, sub / add sp by an immediate (all encodings present), the
    pre-indexed str / post-indexed ldr on sp — and a CONDITIONAL one forks the path (executed / not);
  * control flow: conditional and unconditional branches, cbz / cbnz, a branch out of the function or a fall-
    through into the next symbol (a tail transfer, charged at the SP offset it is taken with), bl / blx to a
    label (a call), bx lr / pop {…, pc} / ldm {…, pc} (a return — its SP offset must be 0), subs pc, lr (an
    exception return), the ARM jump table `add pc, pc, rN, lsl #2` (its successors the branch table after it);
  * indirect calls (blx rN, bx rN that is not a return): the exception dispatchers' `bx` through
    XExc_VectorTable resolve to that table's INITIAL entries, read from the ELF's .data — checked to be the table's
    only users, none of which writes it; every other indirect call resolves to EVERY address-taken function (any
    32-bit word of a loaded section, any movw / movt constant, any pc-relative address equal to a function's
    entry) — a named, checkable, conservative set;
  * a function's bound is its deepest SP offset plus, at each call, the callee's bound; recursion through any
    edge, an SP write the model does not know, a state explosion, an unbalanced return, a path off the end of a
    function, or an unresolvable transfer is a FINDING — and a finding is never replaced by an estimate.

The modes: boot.S is read for the stack it gives each mode (`ldr sp, [pc, #…]` after each CPSR mode switch, its
literal resolved to the linker symbols) and for the mode it hands to _start; the main path's entry is _start in
that mode; each exception entry of the vector table is bounded against its own mode's stack (the abort entries
share the abort stack). The CPSR writes the image makes are reported: which bits any of them can CLEAR.

This module analyses; it decides nothing about thresholds — b3/host/b3_build_evidence.py records its result in
the build evidence's `stack` block and b3/tests/test_b3_image_stack.py holds the bounds.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import struct
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host", REPO_ROOT / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_build_evidence as b2be  # noqa: E402  (the pinned toolchain's path; a frozen B2 module, read only)

TOOL_VERSION = "b3-image-stack 1.0.0"
UNKNOWN = ("UNKNOWN",)                    # a callback field whose contents the points-to cannot pin — read = Finding
ELF_DEFAULT = REPO_ROOT / "b3/firmware/bsp/out/b3_app.elf"
TC_BIN = Path(b2be.TC) / "bin"
MAIN_LIMIT = 0x2000                     # the owner's ruling: the main path's verified bound is at most 0x2000 bytes
APP_DIR = "b3/firmware/"                # the image's own C units (DWARF names, repository-relative)
MAX_OFFSETS_PER_ADDRESS = 8
VECTOR_TABLE = "_vector_table"
EXC_TABLE = "XExc_VectorTable"
DISPATCHERS = ("IRQInterrupt", "FIQInterrupt", "UndefinedException", "SWInterrupt", "DataAbortInterrupt",
               "PrefetchAbortInterrupt")
MODE_NAMES = {0x11: "FIQ", 0x12: "IRQ", 0x13: "SVC", 0x17: "ABT", 0x1B: "UND", 0x1F: "SYS"}
# the vector table's slots: offset -> (the exception, the mode it runs in)
VECTOR_SLOTS = {0x04: ("undefined", "UND"), 0x08: ("svc", "SVC"), 0x0C: ("prefetch_abort", "ABT"),
                0x10: ("data_abort", "ABT"), 0x18: ("irq", "IRQ"), 0x1C: ("fiq", "FIQ")}
# each mode's stack top symbol and the symbol of the region's bottom (the next lower top), from lscript.ld
STACK_TOPS = {"SYS": ("__stack", "_stack_end"), "IRQ": ("__irq_stack", "__stack"), "SVC": ("__supervisor_stack", "__irq_stack"),
              "ABT": ("__abort_stack", "__supervisor_stack"), "FIQ": ("__fiq_stack", "__abort_stack"),
              "UND": ("__undef_stack", "__fiq_stack")}
COND = r"(?:eq|ne|cs|hs|cc|lo|mi|pl|vs|vc|hi|ls|ge|lt|gt|le)"
# the stage-4 stack exceptions (the owner's ruling of 2026-10-01) — their call chains as linked into the image
NAMED_CHAINS = ("select_generation", "b2_search_state_hex")


class Finding(Exception):
    pass


def tool(name: str) -> str:
    return str(TC_BIN / f"arm-none-eabi-{name}")


def runtime_archives() -> dict[str, Path]:
    """libc.a and libgcc.a at the paths the BUILD's own -print-file-name resolves (b3_build_evidence, which runs the
    pinned compiler with build.sh's flags) — the archives the link actually used."""
    import b3_build_evidence as be                    # late: b3_build_evidence records this module's result
    objs = be.resolved_runtime_objects()
    return {k: Path(objs[k]["path"]) for k in ("libc.a", "libgcc.a")}


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


# ------------------------------------------------------------------ reading the ELF


def symbols(elf: Path) -> dict:
    """name -> (value, size, type) for every defined symbol, from nm."""
    out = subprocess.run([tool("nm"), "-S", "--defined-only", str(elf)], capture_output=True, text=True, check=True).stdout
    syms = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) == 4:
            syms.setdefault(parts[3], (int(parts[0], 16), int(parts[1], 16), parts[2]))
        elif len(parts) == 3:
            syms.setdefault(parts[2], (int(parts[0], 16), 0, parts[1]))
    return syms


def sections(elf: Path) -> list[dict]:
    """The loaded PROGBITS sections: name, address, size, file offset."""
    out = subprocess.run([tool("readelf"), "-S", "-W", str(elf)], capture_output=True, text=True, check=True).stdout
    secs = []
    for m in re.finditer(r"\]\s+(\S+)\s+(\w+)\s+([0-9a-f]{8})\s+([0-9a-f]+)\s+([0-9a-f]+)\s+\S+\s+(\S*)", out):
        name, typ, addr, off, size, flags = m.groups()
        if typ in ("PROGBITS", "INIT_ARRAY", "FINI_ARRAY", "PREINIT_ARRAY") and "A" in flags:
            secs.append({"name": name, "addr": int(addr, 16), "offset": int(off, 16), "size": int(size, 16)})
    return secs


def read_words(elf: Path, secs: list[dict]) -> dict[int, int]:
    """Every aligned 32-bit little-endian word of every loaded section, by address."""
    blob = Path(elf).read_bytes()
    words = {}
    for s in secs:
        data = blob[s["offset"]:s["offset"] + s["size"]]
        for i in range(0, len(data) - 3, 4):
            words[s["addr"] + i] = struct.unpack_from("<I", data, i)[0]
    return words


INSN = re.compile(r"^\s*([0-9a-f]+):\t([0-9a-f ]+?)\s*\t([^\t]+)(?:\t(.*))?$")
HEAD = re.compile(r"^([0-9a-f]+) <([^>]+)>:$")


def disassemble(elf: Path) -> dict[str, list[dict]]:
    """name -> instructions (addr, size, mnemonic, operands, thumb) in address order; data words (.word / .short)
    are kept with mnemonic '.data' so that no path may fall into them."""
    out = subprocess.run([tool("objdump"), "-d", "--no-show-raw-insn" if False else "-d", str(elf)],
                         capture_output=True, text=True, check=True).stdout
    funcs: dict[str, list[dict]] = {}
    cur = None
    for line in out.splitlines():
        h = HEAD.match(line)
        if h:
            cur = h.group(2)
            funcs.setdefault(cur, [])
            continue
        m = INSN.match(line)
        if not m or cur is None:
            continue
        addr, raw, mnem, ops = int(m.group(1), 16), m.group(2), m.group(3).strip(), (m.group(4) or "").strip()
        ops = ops.split("@")[0].split(";")[0].strip()
        groups = raw.split()
        size = sum(len(g) // 2 for g in groups)
        thumb = all(len(g) == 4 for g in groups)
        if mnem.startswith("."):
            mnem = ".data"
        funcs[cur].append({"addr": addr, "size": size, "mnem": mnem, "ops": ops, "thumb": thumb})
    return funcs


# ------------------------------------------------------------------ one instruction's effect


def reglist(ops: str) -> list[str]:
    m = re.search(r"\{([^}]*)\}", ops)
    if not m:
        raise Finding(f"no register list in {ops!r}")
    regs = []
    for part in m.group(1).split(","):
        part = part.strip()
        r = re.fullmatch(r"([a-z]+)(\d+)-[a-z]+(\d+)", part)
        if r:
            regs += [f"{r.group(1)}{i}" for i in range(int(r.group(2)), int(r.group(3)) + 1)]
        elif part:
            regs.append(part)
    return regs


def vbytes(regs: list[str]) -> int:
    n = 0
    for r in regs:
        if r.startswith("d"):
            n += 8
        elif r.startswith("s"):
            n += 4
        elif r.startswith("q"):
            n += 16
        else:
            raise Finding(f"a vector register list with {r!r}")
    return n


def imm(text: str) -> int:
    m = re.search(r"#(-?(?:0x[0-9a-f]+|\d+))", text)
    if not m:
        raise Finding(f"no immediate in {text!r}")
    return int(m.group(1), 0)


def base_mnem(mnem: str) -> tuple[str, bool]:
    """(the mnemonic without its condition / width suffixes, whether it is conditional)."""
    m = mnem.split(".")[0]
    for b in ("push", "pop", "vpush", "vpop", "stmdb", "stmfd", "ldmia", "ldmfd", "ldm", "stm", "sub", "add", "subw",
              "addw", "subs", "adds", "str", "ldr", "bx", "blx", "bl", "b", "cbz", "cbnz", "mov", "movs"):
        if m == b:
            return b, False
        if re.fullmatch(b + COND, m):
            return b, True
    return m, False


def sp_effect(ins: dict) -> int | None:
    """The change in the SP offset (bytes BELOW the entry SP; positive = deeper) the instruction makes, or None if
    it does not write SP. Raises Finding for an SP write the model does not know."""
    mn, ops = ins["mnem"], ins["ops"]
    b, _cond = base_mnem(mn)
    o = ops.replace(" ", "")
    if b in ("push", "stmdb", "stmfd") and (b == "push" or o.startswith("sp!,")):
        return 4 * len(reglist(ops))
    if b == "vpush":
        return vbytes(reglist(ops))
    if b in ("pop", "ldmia", "ldmfd", "ldm") and (b == "pop" or o.startswith("sp!,")):
        return -4 * len(reglist(ops))
    if b == "vpop":
        return -vbytes(reglist(ops))
    if b in ("sub", "subw") and (o.startswith("sp,sp,#") or re.fullmatch(r"sp,#.*", o)):
        return imm(ops)
    if b in ("add", "addw") and (o.startswith("sp,sp,#") or re.fullmatch(r"sp,#.*", o)):
        return -imm(ops)
    fam = mn.split(".")[0]
    if re.match(r"(v?ldr|v?str)", fam):                  # any load / store with SP writeback (str, strd, ldrd, …)
        pre = re.search(r"\[sp,#(-?(?:0x[0-9a-f]+|\d+))\]!$", o)
        post = re.search(r"\[sp\],#(-?(?:0x[0-9a-f]+|\d+))$", o)
        if pre:
            return -int(pre.group(1), 0)
        if post:
            return -int(post.group(1), 0)
        if "[sp]!" in o or re.search(r"\[sp,r\d+\]!|\[sp\],r\d+", o):
            raise Finding(f"an SP writeback the model does not know: {mn} {ops}")
        return None
    if re.match(r"(stm|ldm)", mn) and o.startswith("sp,"):
        return None                                # stm / ldm on sp WITHOUT writeback (any addressing mode)
    dest = o.split(",")[0] if o else ""
    if dest == "sp" or (b in ("stm", "stmdb", "ldm", "ldmia") and o.startswith("sp!")):
        raise Finding(f"an SP write the model does not know: {mn} {ops}")
    return None


NEGATE = {"eq": "ne", "ne": "eq", "cs": "cc", "cc": "cs", "hs": "lo", "lo": "hs", "mi": "pl", "pl": "mi", "vs": "vc",
          "vc": "vs", "hi": "ls", "ls": "hi", "ge": "lt", "lt": "ge", "gt": "le", "le": "gt"}
CANON = {"hs": "cs", "lo": "cc"}


def cond_of(mnem: str) -> str:
    m = mnem.split(".")[0]
    c = re.search(COND + "$", m)
    if not c:
        raise Finding(f"a conditional instruction without a condition: {mnem}")
    return CANON.get(c.group(0), c.group(0))


FLAG_OPS = ("add", "sub", "rsb", "rsc", "adc", "sbc", "and", "orr", "orn", "eor", "bic", "mov", "mvn", "lsl", "lsr", "asr",
            "ror", "rrx", "mul", "mla", "neg", "umull", "smull", "umlal", "smlal")


def sets_flags(ins: dict) -> bool:
    """Whether the instruction may write the condition flags (conservative: when in doubt, yes)."""
    m = ins["mnem"].split(".")[0]
    m = re.sub(COND + "$", "", m) if m not in ("teq", "bls", "bhs", "bcs", "bcc", "blo") else m
    if m in ("cmp", "cmn", "tst", "teq") or m.startswith(("cmp", "cmn", "tst", "teq")):
        return True
    if m.endswith("s") and m[:-1] in FLAG_OPS:
        return True
    if m in ("vmrs", "msr") and ("APSR" in ins["ops"] or "CPSR" in ins["ops"] or "SPSR" in ins["ops"]):
        return True
    if m in ("bl", "blx"):
        return True
    return False


def branch_target(ops: str) -> tuple[int, str] | None:
    m = re.match(r"(?:[a-z0-9]+,\s*)?([0-9a-f]+)\s+<([^>]+)>", ops)
    if not m:
        return None
    return int(m.group(1), 16), m.group(2)


# ------------------------------------------------------------------ the analysis


def symbol_types(elf: Path) -> dict[int, str]:
    """address -> 'FUNC' for every STT_FUNC symbol (Thumb bit cleared): the function entries. Assembly labels are
    NOTYPE and are continuations of the code around them, not entries."""
    out = subprocess.run([tool("readelf"), "-s", "-W", str(elf)], capture_output=True, text=True, check=True).stdout
    funcs = {}
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 8 and parts[3] == "FUNC" and parts[6] != "UND":
            funcs[int(parts[1], 16) & ~1] = parts[7]
    return funcs


def compile_units(elf: Path) -> list[tuple[int, int, str]]:
    """(start, size, unit) for every address range of every DWARF compile unit of the ELF (.debug_aranges, keyed to
    each unit's DW_AT_name): the unit a code address was compiled from — an image source by its repository-relative
    path (b3/firmware/…), any other unit (the BSP's C and assembly) by its basename. The link map is a build
    intermediate and is NOT read: the ELF alone decides."""
    info = subprocess.run([tool("readelf"), "--debug-dump=info", "--dwarf-depth=1", str(elf)], capture_output=True,
                          text=True, check=True).stdout
    names: dict[int, str] = {}
    cu = None
    for line in info.splitlines():
        m = re.match(r"\s*Compilation Unit @ offset (0x[0-9a-f]+|\d+):", line)
        if m:
            cu = int(m.group(1), 0)
            continue
        m = re.search(r"DW_AT_name\s*:\s*(?:\(indirect (?:line )?string, offset: (?:0x)?[0-9a-f]+\):\s*)?(\S+)\s*$", line)
        if m and cu is not None and cu not in names:
            names[cu] = m.group(1)
    ar = subprocess.run([tool("readelf"), "--debug-dump=aranges", str(elf)], capture_output=True, text=True, check=True).stdout
    rows = []
    cu = None
    for line in ar.splitlines():
        m = re.search(r"Offset into \.debug_info:\s*(0x[0-9a-f]+|\d+)", line)
        if m:
            cu = int(m.group(1), 0)
            continue
        m = re.fullmatch(r"\s+([0-9a-f]{8})\s+([0-9a-f]{8})\s*", line)
        if m and cu is not None and int(m.group(2), 16):
            if cu not in names:
                raise Finding(f"a DWARF address range of the unit at {cu:#x}, which has no name")
            rows.append((int(m.group(1), 16), int(m.group(2), 16), unit_name(names[cu])))
    if not rows:
        raise Finding("the ELF has no DWARF address ranges: no unit can be told")
    return sorted(rows)


def unit_name(dw_name: str) -> str:
    p = Path(dw_name)
    if p.is_absolute() and p.is_relative_to(REPO_ROOT):
        return str(p.relative_to(REPO_ROOT))
    return p.name


# ------------------------------------------------------------------ the toolchain's archives, member by member


class Archive:
    """One prebuilt archive the link used (libc.a / libgcc.a, at the path the build's own -print-file-name resolves,
    with its digest): which members define a function name, and each member's function bytes with every relocated
    word masked — so a routine of the image is shown to BE that member's code, not merely to share its name."""

    def __init__(self, label: str, path: Path):
        self.label, self.path = label, Path(path)
        self.sha256 = sha256_file(self.path)
        out = subprocess.run([tool("nm"), "-A", "--defined-only", str(self.path)], capture_output=True, text=True, check=True).stdout
        self.defs: dict[str, list[str]] = {}
        for line in out.splitlines():
            parts = line.split()
            if len(parts) >= 3 and parts[-2] in ("T", "t", "W"):
                member = parts[0].split(":")[-2]
                self.defs.setdefault(parts[-1], []).append(member)
        self._members: dict[str, dict] = {}

    def member(self, name: str) -> dict:
        if name in self._members:
            return self._members[name]
        import tempfile
        raw = subprocess.run([tool("ar"), "p", str(self.path), name], capture_output=True, check=True).stdout
        with tempfile.TemporaryDirectory(prefix="b3_stack_member_") as d:
            f = Path(d) / name
            f.write_bytes(raw)
            secs_t = subprocess.run([tool("readelf"), "-S", "-W", str(f)], capture_output=True, text=True, check=True).stdout
            syms_t = subprocess.run([tool("readelf"), "-s", "-W", str(f)], capture_output=True, text=True, check=True).stdout
            rel_t = subprocess.run([tool("readelf"), "-r", "-W", str(f)], capture_output=True, text=True, check=True).stdout
        secs = {}
        for m in re.finditer(r"\[\s*(\d+)\]\s+(\S+)\s+(\w+)\s+[0-9a-f]{8}\s+([0-9a-f]+)\s+([0-9a-f]+)", secs_t):
            secs[int(m.group(1))] = {"name": m.group(2), "offset": int(m.group(4), 16), "size": int(m.group(5), 16)}
        funcs = {}
        for line in syms_t.splitlines():
            parts = line.split()
            if len(parts) >= 8 and parts[3] == "FUNC" and parts[6].isdigit():
                funcs.setdefault(parts[7], []).append((int(parts[6]), int(parts[1], 16) & ~1, int(parts[2])))
        relocs: dict[str, list[int]] = {}
        cur = None
        for line in rel_t.splitlines():
            m = re.match(r"Relocation section '\.rel(\S+)'", line)
            if m:
                cur = m.group(1)
                continue
            m = re.match(r"([0-9a-f]{8})\s+[0-9a-f]{8}\s+(R_ARM_\w+)(?:\s+[0-9a-f]{8}\s+(\S+))?", line)
            if m and cur is not None:
                relocs.setdefault(cur, []).append((int(m.group(1), 16), m.group(2), m.group(3)))
        self._members[name] = {"raw": raw, "secs": secs, "funcs": funcs, "relocs": relocs}
        return self._members[name]

    CALL_RELOCS = ("R_ARM_THM_CALL", "R_ARM_THM_JUMP24", "R_ARM_CALL", "R_ARM_JUMP24", "R_ARM_THM_XPC22")

    def is_code_of(self, member: str, func: str, image_bytes: bytes, branch_name=None) -> bool:
        """The image's bytes of `func` equal the member's, every relocated word (4 bytes at each relocation) masked,
        AND every call / jump relocation of the member lands, in the image, on a routine of the relocation's symbol
        name (`branch_name(offset)` gives the image's) — two members with the same code calling different routines
        (newlib's two __sbprintf) are told apart."""
        m = self.member(member)
        hits = m["funcs"].get(func, [])
        if len(hits) != 1:
            return False
        shndx, value, size = hits[0]
        sec = m["secs"].get(shndx)
        if sec is None or size != len(image_bytes):
            return False
        mine = bytearray(m["raw"][sec["offset"] + value:sec["offset"] + value + size])
        theirs = bytearray(image_bytes)
        if len(mine) != size:
            return False
        for r, typ, sym in m["relocs"].get(sec["name"], []):
            for k in range(r - value, r - value + 4):
                if 0 <= k < size:
                    mine[k] = theirs[k] = 0
            if typ in self.CALL_RELOCS and 0 <= r - value < size:
                want = sym[len(".text."):] if sym and sym.startswith(".text.") else sym
                if branch_name is None or branch_name(r - value) != want:
                    return False
        return mine == theirs


class Image:
    def __init__(self, elf: Path, archives: dict[str, Path] | None = None):
        self.elf = Path(elf)
        self.syms = symbols(self.elf)
        self.secs = sections(self.elf)
        self.words = read_words(self.elf, self.secs)
        self.blob = Path(self.elf).read_bytes()
        self.funcs = disassemble(self.elf)
        self.ins_at: dict[int, dict] = {}
        self.label_at: dict[int, str] = {}
        for name, ins in self.funcs.items():
            if ins:
                self.label_at.setdefault(ins[0]["addr"], name)
            for i in ins:
                self.ins_at[i["addr"]] = i
        self.func_entries = symbol_types(self.elf)
        self.at = dict(self.label_at)
        self.edges: dict[int, list[dict]] = {}
        self.local: dict[int, int] = {}
        self.resets: list[dict] = []
        self.computed_jumps: list[dict] = []
        self.own_return: dict[int, bool] = {}
        self.sp_at: dict[int, dict[int, frozenset]] = {}
        self.stack_tops = {v[0]: n for n, v in self.syms.items() if n in {t for t, _ in STACK_TOPS.values()}}
        self.address_taken = self._address_taken()
        self.exc_targets = self._exception_table()
        self.units = compile_units(self.elf)
        if archives is None:
            archives = runtime_archives()
        self.archives = {k: Archive(k, v) for k, v in archives.items()}
        self._member_of: dict[int, str | None] = {}
        self.site_rules: dict[str, dict] = {}
        self.producers: dict[int, frozenset] | None = None
        self.produced: list[dict] = []
        self._newlib: dict | None = None
        self._pt_cache: dict[int, dict] = {}
        self._pt_state: dict[int, dict] = {}
        self._pt_eval_memo: dict = {}
        self._rsucc_cache: dict = {}
        self._rw_cache: dict = {}

    def name(self, addr: int) -> str:
        return self.label_at.get(addr, f"{addr:#x}")

    # -- address-taken code: literal words, movw/movt constants, pc-relative addresses equal to a code label
    def _address_taken(self) -> list[int]:
        entries = set(self.label_at)
        taken = set()

        def hit(v):
            for c in (v, v & ~1):
                if c in entries:
                    taken.add(c)
        for w in self.words.values():
            hit(w)
        for ins in self.funcs.values():
            lo: dict[str, int] = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                if i["mnem"].startswith("movw") and ",#" in o:
                    r, v = o.split(",#")
                    lo[r] = int(v, 0)
                elif i["mnem"].startswith("movt") and ",#" in o:
                    r, v = o.split(",#")
                    hit((int(v, 0) << 16) | lo.get(r, 0))
                elif base_mnem(i["mnem"])[0] in ("add", "adr") and re.fullmatch(r"\w+,pc,#-?\w+", o):
                    pc = i["addr"] + (4 if i["thumb"] else 8)
                    if i["thumb"]:
                        pc &= ~3
                    hit(pc + imm(o))
        return sorted(taken)

    # -- XExc_VectorTable: its initial handlers, its only users, nobody writes it
    def _exception_table(self) -> list[int]:
        if EXC_TABLE not in self.syms:
            raise Finding(f"no {EXC_TABLE}")
        base, size, _ = self.syms[EXC_TABLE]
        targets = []
        for off in range(0, size, 8):                  # {handler, data} pairs
            w = self.words.get(base + off)
            if w is None:
                raise Finding(f"{EXC_TABLE}+{off:#x} is not in a loaded section")
            if (w & ~1) not in self.label_at:
                raise Finding(f"{EXC_TABLE}+{off:#x} = {w:#x} is not code")
            targets.append(w & ~1)
        users = set()
        for name, ins in self.funcs.items():
            lo: dict[str, int] = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                if i["mnem"].startswith("movw") and ",#" in o:
                    r, v = o.split(",#")
                    lo[r] = int(v, 0)
                elif i["mnem"].startswith("movt") and ",#" in o:
                    r, v = o.split(",#")
                    if ((int(v, 0) << 16) | lo.get(r, 0)) == base:
                        users.add(name)
        for a, w in self.words.items():
            if w == base:
                users.add(f"a literal word at {a:#x}")
        if sorted(users) != sorted(DISPATCHERS):
            raise Finding(f"{EXC_TABLE} is materialised by {sorted(users)}, not exactly the dispatchers")
        for d in DISPATCHERS:
            for i in self.funcs[d]:
                if base_mnem(i["mnem"])[0].startswith(("str", "stm")):
                    raise Finding(f"{d} stores ({i['mnem']} {i['ops']}): the table could be written")
        return sorted(set(targets))

    def analyse(self, entry: int) -> None:
        if entry in self.edges:
            return
        self._analyse_paths(entry)

    def region(self, entry: int) -> list[dict]:
        """The instructions from `entry` up to the next FUNC entry (labels inside are part of it)."""
        stop = min([a for a in self.func_entries if a > entry] + [max(self.ins_at) + 4])
        return [self.ins_at[a] for a in sorted(x for x in self.ins_at if entry <= x < stop)]

    # -- one routine, from its entry: every path's SP; inline across labels, a transfer to another FUNC is a tail.
    # A state is (address, SP offset, what is known of the current condition flags): a conditional instruction or
    # branch forks into "condition true" / "condition false" and RECORDS it, so a later instruction under the same
    # (or the opposite) condition, with no flag write between, follows the same decision — `ldrmi sl, [sp], #32`
    # followed by `bmi` is one path, never "popped but not branched".
    def _analyse_paths(self, entry: int) -> None:
        if entry not in self.ins_at:
            raise Finding(f"{self.name(entry)}: no instruction at {entry:#x}")
        nm = self.name(entry)
        edges: list[dict] = []
        deepest = 0
        returns = False
        seen: dict[int, set] = {}
        offsets: dict[int, set[int]] = {}
        work = [(entry, 0, frozenset())]

        def decide(cond: str, known: frozenset):
            if (cond, True) in known or (NEGATE[cond], False) in known:
                return [(True, known)]
            if (cond, False) in known or (NEGATE[cond], True) in known:
                return [(False, known)]
            return [(True, known | {(cond, True)}), (False, known | {(cond, False)})]

        def go(a, off, known):
            work.append((a, off, known))

        while work:
            addr, off, known = work.pop()
            if addr not in self.ins_at:
                raise Finding(f"{nm}: a path reaches {addr:#x}, which is no instruction")
            key = (off, known)
            sset = seen.setdefault(addr, set())
            if key in sset:
                continue
            sset.add(key)
            oset = offsets.setdefault(addr, set())
            oset.add(off)
            if len(oset) > MAX_OFFSETS_PER_ADDRESS or len(sset) > 64:
                raise Finding(f"{nm}: more than {MAX_OFFSETS_PER_ADDRESS} SP offsets (or 64 states) at {addr:#x}")
            i = self.ins_at[addr]
            nxt = addr + i["size"]
            if i["mnem"] == ".data":
                raise Finding(f"{nm}: a path executes data at {addr:#x}")
            deepest = max(deepest, off)
            b, condflag = base_mnem(i["mnem"])
            cond = cond_of(i["mnem"]) if condflag else None
            o = i["ops"].replace(" ", "")
            branches = [(True, known)] if cond is None else decide(cond, known)
            for executes, kn in branches:
                if not executes:
                    go(nxt, off, kn)                       # the instruction is skipped
                    continue
                after_known = frozenset() if sets_flags(i) else kn
                self._step(nm, entry, i, b, o, nxt, off, after_known, go, edges)
                if self._returned:
                    returns = True
                    self._returned = False
        self.local[entry] = deepest
        self.edges[entry] = edges
        self.own_return[entry] = returns
        self.sp_at[entry] = {a: frozenset(v) for a, v in offsets.items()}

    _returned = False

    def _step(self, nm, entry, i, b, o, nxt, off, kn, go, edges) -> None:
        """One EXECUTED instruction: its successors and edges."""
        addr = i["addr"]
        if b in ("pop", "ldmia", "ldmfd", "ldm") and (b == "pop" or o.startswith("sp!,")) and "pc" in reglist(i["ops"]):
            after = off - 4 * len(reglist(i["ops"]))
            if after != 0:
                raise Finding(f"{nm}: a return at {addr:#x} with SP offset {after}")
            self._returned = True
            return
        if b == "bx" and o == "lr":
            if off != 0:
                raise Finding(f"{nm}: bx lr at {addr:#x} with SP offset {off}")
            self._returned = True
            return
        if b in ("subs", "movs") and o.startswith("pc,lr"):
            if off != 0:
                raise Finding(f"{nm}: an exception return at {addr:#x} with SP offset {off}")
            self._returned = True
            return
        if b == "add" and o.startswith("pc,pc,"):
            succ = []
            a2 = nxt
            while a2 in self.ins_at and base_mnem(self.ins_at[a2]["mnem"])[0] == "b" and branch_target(self.ins_at[a2]["ops"]):
                succ.append(a2)
                a2 += self.ins_at[a2]["size"]
            if len(succ) < 2:                              # not a branch table: the exact value set of its index
                succ = self._jump_targets(entry, addr)
            for a2 in succ:
                go(a2, off, frozenset())
            return
        if i["mnem"].split(".")[0] in ("tbb", "tbh"):
            for t in self._table_branch(addr, i):
                go(t, off, frozenset())
            return
        if b in ("bl", "blx") and branch_target(i["ops"]):
            tgt = branch_target(i["ops"])[0]
            if tgt not in self.ins_at:
                raise Finding(f"{nm}: a call at {addr:#x} to {tgt:#x}, which is no instruction")
            if (nxt in self.func_entries and nxt != entry) or nxt not in self.ins_at:
                edges.append({"kind": "call_noreturn", "to": tgt, "at": off, "site": f"{addr:#x}"})   # it must never return
                return
            edges.append({"kind": "call", "to": tgt, "at": off, "site": f"{addr:#x}"})
            go(nxt, off, frozenset())                      # a call clobbers the flags
            return
        if b == "blx":
            edges.append({"kind": "indirect_call", "to": None, "at": off, "site": f"{addr:#x}", "set": self.site_set(nm)})
            go(nxt, off, frozenset())
            return
        if b == "bx":
            edges.append({"kind": "indirect_tail", "to": None, "at": off, "site": f"{addr:#x}", "set": self.site_set(nm)})
            return
        if b in ("b", "cbz", "cbnz"):
            bt = branch_target(i["ops"])
            if bt is None:
                raise Finding(f"{nm}: a branch at {addr:#x} with no resolvable target: {i['ops']}")
            tgt = bt[0]
            if tgt != entry and tgt in self.func_entries:
                edges.append({"kind": "tail", "to": tgt, "at": off, "site": f"{addr:#x}"})
            else:
                go(tgt, off, kn)
            if b in ("cbz", "cbnz"):
                go(nxt, off, kn)
            return
        if b == "mov" and re.fullmatch(r"pc,r\d+", o):
            for a2 in self._jump_targets(entry, addr):
                go(a2, off, frozenset())
            return
        if o.startswith("pc,") or (b in ("ldm", "ldmia", "ldmfd") and "pc" in i["ops"]):
            raise Finding(f"{nm}: a write to pc the model does not know at {addr:#x}: {i['mnem']} {i['ops']}")
        if b == "ldr" and o.startswith("sp,[pc,#"):
            lit = addr + (4 if i["thumb"] else 8) + imm(o)
            val = self.words.get(lit)
            if val not in self.stack_tops:
                raise Finding(f"{nm}: an absolute stack load at {addr:#x} of {val!r}, not a stack top")
            self.resets.append({"routine": nm, "at": f"{addr:#x}", "to": self.stack_tops[val], "offset_before": off})
            go(nxt, 0, kn)
            return
        d = sp_effect(i)
        nxt_off = off if d is None else off + d
        if nxt in self.func_entries and nxt != entry:
            edges.append({"kind": "fallthrough", "to": nxt, "at": nxt_off, "site": f"{addr:#x}"})
            return
        go(nxt, nxt_off, kn)

    def unit_of(self, addr: int) -> str | None:
        """The DWARF compile unit the code at `addr` was compiled from (None: no unit — the prebuilt archives)."""
        for start, size, unit in self.units:
            if start <= addr < start + size:
                return unit
        return None

    def member_of(self, addr: int) -> str | None:
        """`libc.a(member)` / `libgcc.a(member)` when the routine at `addr` IS that member's code: a member defining
        its name whose function bytes equal the image's, relocations masked — exactly one, or a Finding."""
        if addr in self._member_of:
            return self._member_of[addr]
        name = self.name(addr)
        out = None
        if self.unit_of(addr) is None and name in self.syms:
            size = self.syms[name][1]
            hits = []
            for label, arc in self.archives.items():
                for mem in arc.defs.get(name, []):
                    if size and arc.is_code_of(mem, name, self.read_bytes(addr, size), lambda k: self._branch_name(addr + k)):
                        hits.append(f"{label}({mem})")
            if len(hits) > 1:
                raise Finding(f"{name}: the image's code matches more than one archive member: {hits}")
            out = hits[0] if hits else None
        self._member_of[addr] = out
        return out

    def _branch_name(self, at: int) -> str | None:
        i = self.ins_at.get(at)
        bt = branch_target(i["ops"]) if i and base_mnem(i["mnem"])[0] in ("b", "bl", "blx") else None
        return self.name(bt[0]) if bt else None

    def object_of(self, addr: int) -> str | None:
        """The unit (from DWARF) or the archive member (by its code) the routine at `addr` comes from."""
        return self.unit_of(addr) or self.member_of(addr)

    def defined_in(self, *members: str) -> list[int]:
        """The ADDRESS-TAKEN code entries that are the code of any of these archive members (`libc_a-stdio.o`)."""
        want = {f"libc.a({m})" for m in members} | {f"libgcc.a({m})" for m in members}
        return sorted(a for a in self.address_taken if self.object_of(a) in want)

    def _callers(self, names: tuple) -> list[str]:
        """Every routine with a direct call or branch to any of these symbols, and any literal / movw-movt reference."""
        addrs = {self.syms[n][0] for n in names if n in self.syms}
        out = []
        for i in self.ins_at.values():
            b, _ = base_mnem(i["mnem"])
            if b in ("b", "bl", "blx") and branch_target(i["ops"]) and branch_target(i["ops"])[0] in addrs:
                out.append(f"{i['addr']:#x}")
        out += [f"{x:#x} (address-taken)" for x in addrs if x in self.address_taken]
        return out

    def _only_reader(self, var: str, reader: str) -> bool:
        """`var` (a data symbol) is materialised by `reader` alone, never stored by it, and starts as 0."""
        if var not in self.syms:
            return False
        base = self.syms[var][0]
        users = set()
        for name, ins in self.funcs.items():
            lo: dict[str, int] = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                if i["mnem"].startswith("movw") and ",#" in o:
                    r, v = o.split(",#")
                    lo[r] = int(v, 0)
                elif i["mnem"].startswith("movt") and ",#" in o:
                    r, v = o.split(",#")
                    if ((int(v, 0) << 16) | lo.get(r, 0)) == base:
                        users.add(name)
        if any(w == base for w in self.words.values()):
            return False
        if users != {reader}:
            return False
        for i in self.funcs[reader]:
            if base_mnem(i["mnem"])[0].startswith(("str", "stm")):
                return False
        initial = self.words.get(base)
        return initial in (None, 0)                    # .bss (no file word) or an explicit zero

    def _arrays(self) -> list[int]:
        out = []
        for sec in self.secs:
            if sec["name"] in (".preinit_array", ".init_array", ".fini_array"):
                for a in range(sec["addr"], sec["addr"] + sec["size"], 4):
                    w = self.words.get(a)
                    if w is None or (w & ~1) not in self.label_at:
                        raise Finding(f"{sec['name']}+{a - sec['addr']:#x} = {w!r} is not code")
                    out.append(w & ~1)
        return sorted(set(out))

    # every reachable indirect call / tail resolves through ONE named rule, chosen by the routine — or, for the image's
    # own units, the unit — that contains it; each rule is computed from the image and recorded with what it was
    # checked against. A rule keyed by a newlib routine's name applies only when that routine IS the libc's code.
    APP_POINTER_UNITS = tuple(APP_DIR + u for u in ("p3_pull.c", "p3_rectx.c", "b3_wire.c", "b3_carto.c", "b3_record.c"))
    LIBC_KEYED = ("init_fini_arrays", "newlib_file_ops", "newlib_locale_conversions", "newlib_stdio_exit_handler",
                  "atexit_registrations", "fwalk_callers")
    SITE_RULES = (
        ("exception_table", lambda r, o: r in DISPATCHERS),
        ("init_fini_arrays", lambda r, o: r in ("__libc_init_array", "__libc_fini_array")),
        ("app_function_pointers", lambda r, o: o in Image.APP_POINTER_UNITS),
        ("newlib_file_ops", lambda r, o: r in ("__sflush_r", "__sfvwrite_r", "_fclose_r")),
        ("newlib_locale_conversions", lambda r, o: r in ("_svfprintf_r", "_vfiprintf_r", "_wcrtomb_r", "_wcsnrtombs_l")),
        ("newlib_stdio_exit_handler", lambda r, o: r == "exit"),
        ("atexit_registrations", lambda r, o: r == "__call_exitprocs"),
        ("fwalk_callers", lambda r, o: r == "_fwalk_sglue"),
        ("xil_assert_callback", lambda r, o: r == "Xil_Assert"),
    )

    def site_set(self, routine: str) -> str:
        entry = self.syms.get(routine, (None,))[0]
        obj = self.object_of(entry) if entry is not None else None
        for name, match in self.SITE_RULES:
            if match(routine, obj):
                if name in self.LIBC_KEYED and not (obj or "").startswith("libc.a("):
                    raise Finding(f"{routine}: the rule {name!r} is for the libc's routine, and this is {obj}'s code")
                self.rule_targets(name)
                return name
        raise Finding(f"{routine}: an indirect call or tail with no named target set (defined in {obj})")

    # ---- register dataflow, shared by the rules

    REG = r"\b(r1[0-2]|r[0-9]|sl|fp|ip|sp|lr|pc)\b"
    CALLER_SAVED = frozenset({"r0", "r1", "r2", "r3", "ip", "lr"})
    ARG_REGS = frozenset({"r0", "r1", "r2", "r3"})
    # the mnemonic families the dataflow knows, so a condition suffix is stripped only from a real family
    # (`movs` is movs, `bls` is b + ls, `ldrhi` is ldr + hi)
    KNOWN = frozenset("""add adds adc adcs sub subs sbc sbcs rsb rsbs and ands orr orrs orn orns eor eors bic bics mov
        movs mvn mvns movw movt lsl lsls lsr lsrs asr asrs ror rors rrx mul muls mla mls umull smull umlal smlal udiv
        sdiv cmp cmn tst teq clz rbit rev rev16 uxtb uxth sxtb sxth ubfx sbfx bfi bfc neg negs addw subw adr ldr ldrb
        ldrh ldrsb ldrsh ldrd ldrex ldrexb ldrexh str strb strh strd strex strexb strexh ldm ldmia ldmdb ldmfd stm
        stmia stmdb stmfd stmea push pop b bl blx bx cbz cbnz tbb tbh vpush vpop vstr vldr vmov vmrs vmsr vadd vsub
        vmul vdiv vcmp vcmpe vcvt vneg vabs vsqrt vstmia vldmia vstmdb vldmdb vmla vmls vnmul vfma mrs msr nop dmb
        dsb isb svc bkpt cpsid cpsie mcr mrc pld wfi wfe sev udf""".split())
    NO_DEST = frozenset("""str strb strh strd stm stmia stmdb stmfd stmea push cmp cmn tst teq b bx cbz cbnz tbb tbh
        nop dmb dsb isb pld vstr vpush vstmia vstmdb msr svc bkpt wfi wfe sev cpsid cpsie vcmp vcmpe vmsr udf
        mcr""".split())

    def _regs(self, text: str) -> list[str]:
        return re.findall(self.REG, text)

    def _family(self, i: dict) -> str:
        """The mnemonic without width suffix and condition: `strd`, `ldmia`, `add`, `b` (for `bne.n`) …"""
        f = i["mnem"].split(".")[0]
        if f in self.KNOWN or f.startswith("it"):
            return f
        if re.search(COND + "$", f) and f[:-2] in self.KNOWN:
            return f[:-2]
        return f

    def written(self, i: dict) -> set[str]:
        """The core registers the instruction may write (a call: the AAPCS caller-saved ones)."""
        fam = self._family(i)
        o = i["ops"].replace(" ", "")
        b, _ = base_mnem(i["mnem"])
        out: set[str] = set()
        if b in ("bl", "blx"):
            return set(self.CALLER_SAVED)
        if fam.startswith(("pop", "ldm")) and "{" in o:
            out |= set(reglist(i["ops"]))
        elif fam.startswith(("ldrd",)):
            rs = self._regs(o.split("[")[0])
            out |= set(rs) if len(rs) >= 2 else ({rs[0], self._next_reg(rs[0])} if rs else set())
        elif fam.startswith(("umull", "smull", "umlal", "smlal")):
            out |= set(self._regs(o)[:2])
        elif fam not in self.NO_DEST and not fam.startswith("it"):
            rs = self._regs(o.split(",")[0]) if o else []
            out |= set(rs[:1])
        if re.search(r"\[(\w+)(?:,[^\]]*)?\]!", o):
            out.add(re.search(r"\[(\w+)", o).group(1))
        if re.search(r"\[(\w+)\],", o):
            out.add(re.search(r"\[(\w+)\]", o).group(1))
        if fam.startswith(("ldm", "stm")) and re.match(r"(\w+)!", o):
            out.add(re.match(r"(\w+)!", o).group(1))
        return out

    @staticmethod
    def _next_reg(r: str) -> str:
        names = ["r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "sl", "fp", "ip", "sp", "lr", "pc"]
        alias = {"r10": "sl", "r11": "fp", "r12": "ip"}
        r = alias.get(r, r)
        return names[names.index(r) + 1]

    def _straight_back(self, entry: int, site: int, reg: str) -> dict | None:
        """The last instruction before `site` that writes `reg`, found walking back through a STRAIGHT run: no branch
        of the routine ENTERS between it and the site and no unconditional transfer lies there (a conditional branch
        out is passed: the site is on its fallthrough), so it is the value on every path to the site. None
        when the run reaches the entry with no write."""
        region = self.region(entry)
        addrs = [i["addr"] for i in region]
        if site not in addrs:
            raise Finding(f"{self.name(entry)}: the site {site:#x} is not in the routine")
        targets = self.branch_targets_of(entry)
        k = addrs.index(site)
        while k > 0:
            if addrs[k] in targets:
                raise Finding(f"{self.name(entry)}: a branch enters the run before {site:#x}; the value of {reg} there is not one")
            k -= 1
            i = region[k]
            b, cond = base_mnem(i["mnem"])
            # a CONDITIONAL branch out leaves the values on its fallthrough unchanged; an unconditional transfer or a
            # table branch ends the run (the site would not follow it)
            if (b == "b" and not cond) or b == "bx" or i["mnem"].split(".")[0] in ("tbb", "tbh"):
                raise Finding(f"{self.name(entry)}: an unconditional transfer at {i['addr']:#x} lies in the run before {site:#x}")
            if reg in self.written(i):
                return i
        return None

    def reaching_writers(self, entry: int, at: int, reg: str) -> list[dict | None]:
        """Every instruction that can be the LAST writer of `reg` before `at`, over every path of the routine's
        over-approximate CFG (a conditional write counts as written and as not); None in the list = a path from the
        entry on which nothing writes it (the incoming value)."""
        ck = (entry, at, reg)
        if ck in self._rw_cache:
            return self._rw_cache[ck]
        succ = self._region_succ(entry)
        pred: dict[int, list[int]] = {}
        for a, ts in succ.items():
            for t in ts:
                pred.setdefault(t, []).append(a)
        out: dict = {}
        seen = set()
        stack = list(pred.get(at, []))
        if at == entry:
            out[None] = None
        while stack:
            a = stack.pop()
            if a in seen:
                continue
            seen.add(a)
            i = self.ins_at[a]
            if reg in self.written(i):
                out[a] = i
                if not base_mnem(i["mnem"])[1] or base_mnem(i["mnem"])[0] in ("bl", "blx"):
                    continue
            if a == entry:
                out[None] = None
            stack += pred.get(a, [])
        res = [out[k] for k in sorted(out, key=lambda k: -1 if k is None else k)]
        self._rw_cache[ck] = res
        return res

    def const_at(self, entry: int, site: int, reg: str) -> int:
        """The constant `reg` holds at `site`: movw / movt, a pc-relative literal load, or a copy of a register that
        holds one — found through a straight run, or a Finding."""
        w = self._straight_back(entry, site, reg)
        if w is None:
            raise Finding(f"{self.name(entry)}: {reg} at {site:#x} is the routine's own argument, not a constant")
        o = w["ops"].replace(" ", "")
        fam = self._family(w)
        if fam == "movt" and o.startswith(reg + ",#"):
            lo = self._straight_back(entry, w["addr"], reg)
            if lo is None or self._family(lo) != "movw" or not lo["ops"].replace(" ", "").startswith(reg + ",#"):
                raise Finding(f"{self.name(entry)}: a movt at {w['addr']:#x} without its movw")
            return (imm(o) << 16) | imm(lo["ops"])
        if fam == "movw" and o.startswith(reg + ",#"):
            return imm(o)
        if fam == "ldr" and o.startswith(reg + ",[pc,#"):
            lit = ((w["addr"] + 4) & ~3 if w["thumb"] else w["addr"] + 8) + imm(o)
            if lit not in self.words:
                raise Finding(f"{self.name(entry)}: a literal load at {w['addr']:#x} outside the loaded sections")
            return self.words[lit]
        if fam == "mov" and re.fullmatch(reg + r",(r\d+|ip|lr|sl|fp)", o):
            return self.const_at(entry, w["addr"], o.split(",")[1])
        raise Finding(f"{self.name(entry)}: {reg} at {site:#x} comes from {w['mnem']} {w['ops']}, not a constant")

    def direct_sites(self, target: int) -> list[tuple[int, int, str]]:
        """(routine entry, site, kind) of every direct call or branch to `target` from another routine."""
        out = []
        for i in self.ins_at.values():
            b, _ = base_mnem(i["mnem"])
            bt = branch_target(i["ops"]) if b in ("b", "bl", "blx") else None
            if bt and bt[0] == target:
                owner = max(a for a in self.func_entries if a <= i["addr"])
                if owner != target:
                    out.append((owner, i["addr"], "call" if b in ("bl", "blx") else "tail"))
        return sorted(out)

    def forwarded(self, entry: int, reg: str, arg: str) -> int:
        """`reg` is written ONCE in the routine — not counting the restoring pop of a return — by `mov reg, arg` in the
        routine's straight entry run, with `arg` not written before it: `reg` holds the routine's incoming `arg` from
        that point on (a callee-saved `reg` survives every call). Returns the write's address."""
        region = self.region(entry)
        targets = self.branch_targets_of(entry)
        writes = []
        for i in region:
            b, _ = base_mnem(i["mnem"])
            if b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in i["ops"]:
                continue
            if reg in self.written(i):
                writes.append(i)
        if len(writes) != 1 or writes[0]["ops"].replace(" ", "") != f"{reg},{arg}" or self._family(writes[0]) != "mov":
            raise Finding(f"{self.name(entry)}: {reg} is not written once, as a copy of its argument {arg}")
        for i in region:
            if i["addr"] == writes[0]["addr"]:
                return i["addr"]
            b, _ = base_mnem(i["mnem"])
            if i["addr"] in targets and i["addr"] != entry or b in ("b", "cbz", "cbnz", "bx", "bl", "blx") or arg in self.written(i):
                raise Finding(f"{self.name(entry)}: {arg} may change before it is copied to {reg}")
        raise Finding(f"{self.name(entry)}: the copy of {arg} is not in the routine")

    def stack_pointers(self, entry: int) -> dict[int, frozenset]:
        """MUST-analysis over the routine's over-approximate CFG: the registers that hold an address in the routine's
        own stack frame (sp itself; `add rD, sp|rS, #k` / `mov rD, sp|rS` of one) BEFORE each instruction."""
        succ = self._region_succ(entry)
        ins = {i["addr"]: i for i in self.region(entry)}
        inn: dict[int, frozenset | None] = {a: None for a in ins}     # None: not reached yet (the lattice's top)
        inn[entry] = frozenset({"sp"})
        work = [entry]
        while work:
            a = work.pop()
            i = ins[a]
            cur = set(inn[a])
            o = i["ops"].replace(" ", "")
            fam = self._family(i)
            rs = self._regs(o)
            gen = None
            if fam in ("add", "addw") and len(rs) == 2 and rs[1] in cur and ",#" in o:
                gen = rs[0]
            elif fam == "mov" and len(rs) == 2 and "#" not in o and rs[1] in cur:
                gen = rs[0]
            cond = base_mnem(i["mnem"])[1]
            for r in self.written(i):
                if r != "sp":
                    cur.discard(r)
            if gen and not cond:
                cur.add(gen)
            out = frozenset(cur | {"sp"})
            for t in succ.get(a, []):
                if t not in ins or t == entry:
                    continue
                new = out if inn[t] is None else inn[t] & out
                if new != inn[t]:
                    inn[t] = new
                    work.append(t)
        return {a: (v or frozenset({"sp"})) for a, v in inn.items()}

    def escapes(self, entry: int, at: int, reg: str) -> list[str]:
        """Where the code address materialised into `reg` at `at` goes, followed over every path of the routine (a
        may-analysis: a copy carries it on; a write of the register ends it): the ALLOWED uses are a store into the
        routine's own stack frame (base sp or a register the must-analysis shows holds a frame address), a call or a
        tail with it in an argument register, and a copy. Returns every other use, as text (empty = contained)."""
        succ = self._region_succ(entry)
        ins = {i["addr"]: i for i in self.region(entry)}
        frame = self.stack_pointers(entry)
        bad: list[str] = []
        seen = set()
        work = [(t, frozenset({reg})) for t in succ.get(at, [])]
        while work:
            a, car = work.pop()
            if (a, car) in seen or a not in ins:
                continue
            seen.add((a, car))
            i = ins[a]
            o = i["ops"].replace(" ", "")
            fam = self._family(i)
            b, cond = base_mnem(i["mnem"])
            rs = self._regs(o)
            here = f"{a:#x} {i['mnem']} {i['ops']}"
            new = set(car)
            if fam.startswith(("str", "stm", "push", "vst")):
                if fam == "push":
                    base, data = "sp", rs
                elif "[" in o:
                    base = re.search(r"\[(\w+)", o).group(1)
                    data = self._regs(o[:o.index("[")])
                    if fam.startswith("strd") and len(data) == 1:
                        data = data + [self._next_reg(data[0])]
                else:
                    base = o.split(",")[0].rstrip("!")
                    data = self._regs(o[o.index("{"):]) if "{" in o else []
                if base in car or (re.search(r"\[\w+,(\w+)", o) and re.search(r"\[\w+,(\w+)", o).group(1) in car):
                    bad.append(f"used as an address: {here}")
                if set(data) & car and not (base == "sp" or base in frame.get(a, frozenset())):
                    bad.append(f"stored outside the frame: {here}")
            elif b in ("bl", "blx") and branch_target(i["ops"]):
                pass                                   # an argument (r0–r3) or a callee-saved survivor: allowed
            elif b == "b" and branch_target(i["ops"]) and branch_target(i["ops"])[0] not in ins:
                continue                               # a tail with it as an argument: allowed; nothing follows
            elif fam.startswith(("pop", "ldm")) and "pc" in o:          # a return: the popped regs are restored
                killed = car - set(reglist(i["ops"]))                       # (the pointer in one of them is discarded)
                if "r0" in killed:
                    bad.append(f"returned: {here}")                         # still in r0 (not popped): returned
                continue
            elif b == "bx":
                if "lr" not in rs and set(rs) & car:
                    bad.append(f"called or branched to: {here}")
                elif "lr" in rs and "r0" in car:
                    bad.append(f"returned: {here}")
                continue
            elif b == "blx":
                if set(rs) & car:
                    bad.append(f"called or branched to: {here}")
            elif fam == "mov" and len(rs) == 2 and "#" not in o:
                if rs[1] in car:
                    new.add(rs[0])
                elif not cond:
                    new.discard(rs[0])
            else:
                srcs = rs[1:] if (rs and rs[0] in self.written(i)) else rs
                if set(srcs) & car:
                    bad.append(f"used: {here}")
            if not cond or b in ("bl", "blx"):
                for r in self.written(i):
                    if not (fam == "mov" and len(rs) == 2 and rs[1] in car and r == rs[0]):
                        new.discard(r)
            if not new:
                continue
            for t in succ.get(a, []):
                work.append((t, frozenset(new)))
        return sorted(set(bad))

    def app_producers(self) -> dict[int, frozenset]:
        """routine entry -> the code addresses it MATERIALISES, for every routine of the image's own units (b3/firmware):
        the only places an application function pointer is born. Each materialisation must be a movw / movt pair
        whose value only goes into the routine's own frame, a call's argument, or a copy (`escapes`); no such
        address may also be a literal word of the image or be materialised outside the image's units — so the
        pointer a consumer calls can only have been produced by a routine ACTIVE on the call path (its frame or its
        argument). Computed once."""
        if self.producers is not None:
            return self.producers
        entries = set(self.label_at)
        prod: dict[int, set] = {}
        records = []
        for name, ins in self.funcs.items():
            if not ins:
                continue
            owner = ins[0]["addr"]
            unit = self.unit_of(owner) or ""
            lo: dict[str, int] = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                fam = self._family(i)
                if fam == "movw" and ",#" in o:
                    lo[o.split(",")[0]] = imm(o)
                elif fam == "movt" and ",#" in o:
                    r = o.split(",")[0]
                    v = ((imm(o) << 16) | lo.get(r, 0))
                    if (v & ~1) in entries:
                        if not unit.startswith(APP_DIR):
                            if (v & ~1) in getattr(self, "_app_code", set()):
                                raise Finding(f"{name} ({unit or self.object_of(owner)}) materialises the image's {self.name(v & ~1)}")
                            continue
                        func = owner if owner in self.func_entries else max(a for a in self.func_entries if a <= i["addr"])
                        bad = self.escapes(func, i["addr"], r)
                        if bad:
                            raise Finding(f"{name}: the pointer to {self.name(v & ~1)} materialised at {i['addr']:#x} escapes: {bad[:3]}")
                        prod.setdefault(func, set()).add(v & ~1)
                        records.append({"routine": self.name(func), "at": f"{i['addr']:#x}", "pointer": self.name(v & ~1)})
        made = set().union(*prod.values()) if prod else set()
        for a, w in self.words.items():
            if (w & ~1) in made:
                raise Finding(f"the application pointer {self.name(w & ~1)} is also a literal word at {a:#x}")
        for name, ins in self.funcs.items():                 # pc-relative materialisations (adr / add rD, pc, #k)
            for i in ins:
                o = i["ops"].replace(" ", "")
                if base_mnem(i["mnem"])[0] in ("add", "adr") and re.fullmatch(r"\w+,pc,#-?\w+", o):
                    pc = (i["addr"] + 4) & ~3 if i["thumb"] else i["addr"] + 8
                    if (pc + imm(o)) & ~1 in made:
                        raise Finding(f"{name} materialises the application pointer {self.name((pc + imm(o)) & ~1)} pc-relatively")
        # the image's pointers are materialised by the image's units only
        for name, ins in self.funcs.items():
            if not ins or (self.unit_of(ins[0]["addr"]) or "").startswith(APP_DIR):
                continue
            lo = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                fam = self._family(i)
                if fam == "movw" and ",#" in o:
                    lo[o.split(",")[0]] = imm(o)
                elif fam == "movt" and ",#" in o:
                    v = (imm(o) << 16) | lo.get(o.split(",")[0], 0)
                    if (v & ~1) in made:
                        raise Finding(f"{name}, outside the image's units, materialises the application pointer {self.name(v & ~1)}")
        self.producers = {k: frozenset(v) for k, v in prod.items()}
        self.produced = records
        return self.producers

    # ---- per-call-site, per-field points-to for application callbacks (the owner's ruling of 2026-10-04, option 1)
    #
    # An OBJECT is a struct built in a routine's own stack frame, named (routine, A) where A is its base as a byte
    # offset relative to the routine's ENTRY stack pointer (A = immediate - the SP offset there, as `_frame_stores`
    # counts). A routine fills an object's fields by storing callbacks at frame slots and hands &object to a consumer
    # as an argument; the consumer calls `blx [objptr, #off]`. So each indirect call resolves to the callbacks the
    # building routine stored at that object's slot A + off — not the union of every active pointer. The object
    # binding travels in the depth context, so the SAME consumer called with different objects is analysed and
    # memoised apart. An unknown pointer source, a store the analysis cannot read, an aliased or callee write to the
    # slot, or a field with no recorded callback is a Finding; several callbacks reaching one slot are ALL kept.
    APP_UNITS = tuple(APP_DIR + u for u in ("b3_app.c", "p3_pull.c", "p3_rectx.c", "b3_wire.c", "b3_carto.c", "b3_record.c"))

    def _pointsto(self, entry: int) -> dict:
        """For one routine: `reads` {indirect-call site -> (arg index, field offset)} it dereferences of an incoming
        object; `passes` {call site -> {arg index -> object spec}} it hands to a callee (('frame', A) of its own
        frame, or ('arg', n) forwarding its own n-th argument); `fields` {slot A -> set of callback addrs, or the
        sentinel UNKNOWN} it stores. Computed with a condition-sensitive forward analysis over the object atoms."""
        if entry in self._pt_cache:
            return self._pt_cache[entry]
        if (self.unit_of(entry) or "") not in self.APP_UNITS:
            # application callback objects are built, passed and dereferenced only in the image's own units; a
            # library routine neither builds nor forwards one (escapes() forbids an app pointer leaving the units),
            # so its points-to is empty — and a binding that fails to reach a consumer is then a Finding, not a guess
            self._pt_state[entry] = {}
            self._pt_cache[entry] = {"passes": {}, "fields": {}, "reads": {}, "needs": frozenset()}
            return self._pt_cache[entry]
        self.analyse(entry)
        succ = self._region_succ(entry)
        ins = {i["addr"]: i for i in self.region(entry)}
        allr = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "sl", "fp", "ip", "lr")
        start = {r: frozenset({("other",)}) for r in allr}
        for n in range(4):
            start[f"r{n}"] = frozenset({("arg", n)})
        inn: dict[int, dict | None] = {a: None for a in ins}
        inn[entry] = start
        work = [entry]
        rounds = 0
        while work:
            rounds += 1
            if rounds > 2_000_000:
                raise Finding(f"{self.name(entry)}: the object points-to did not converge")
            a = work.pop()
            st = inn[a]
            out = self._pt_step(entry, ins[a], dict(st), {})
            for t in succ.get(a, []):
                if t not in ins:
                    continue
                keys = set(out) | (set(inn[t]) if inn[t] is not None else set())
                merged = {k: self._pt_join(out.get(k, frozenset({("other",)})), inn[t].get(k, frozenset({("other",)})) if inn[t] else frozenset({("other",)})) for k in keys}
                if inn[t] is None or merged != inn[t]:
                    inn[t] = merged
                    work.append(t)
        at = {a: (inn[a] if inn[a] is not None else start) for a in ins}
        fields = {}
        for a, i in ins.items():
            fam = self._family(i)
            o = i["ops"].replace(" ", "")
            if not fam.startswith(("str", "stm", "push")):
                continue
            if fam == "push" or (fam in ("stmdb", "stmfd", "stm", "stmia") and o.startswith("sp")):
                regs = reglist(i["ops"])
                down = (fam in ("stmdb", "stmfd") or fam == "push")
                for k, r in enumerate(regs):
                    slot = self._pt_slot(entry, a, (4 * k - 4 * len(regs)) if down else 4 * k)
                    self._fields_put(entry, fields, slot, self._pt_eval(entry, a, r, at))
                continue
            mr = re.search(r"\[(\w+),(\w+)(?:,lsl#\d+)?\]", o)         # register-indexed store
            if mr:
                base = mr.group(1)
                if base == "sp" or any(x[0] == "frame" for x in self._pt_eval(entry, a, base, at)):
                    fields["ALIAS"] = UNKNOWN              # a frame store at a variable index: may hit any field
                continue
            m = re.search(r"\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
            if not m:
                continue
            off = int(m.group(2), 0) if m.group(2) else 0
            bases = ({("frame", self._pt_slot(entry, a, off))} if m.group(1) == "sp"
                     else self._pt_eval(entry, a, m.group(1), at))
            data = self._regs(o.split("[")[0])
            if fam.startswith("strd") and len(data) == 1:
                data.append(self._next_reg(data[0]))
            for base in bases:
                if base[0] != "frame" or base[1] is None:
                    continue
                slot0 = base[1] if m.group(1) == "sp" else base[1] + off
                for d, r in enumerate(data):
                    self._fields_put(entry, fields, slot0 + 4 * d, self._pt_eval(entry, a, r, at))
        passes = {}
        for a, i in ins.items():
            st = at.get(a)
            if st is None or base_mnem(i["mnem"])[0] != "bl" or not branch_target(i["ops"]):
                continue
            spoff = self.sp_at[entry].get(a, frozenset())
            spoff = next(iter(spoff)) if len(spoff) == 1 else None
            p = {}
            for n in range(4):
                for atom in st.get(f"r{n}", frozenset({("other",)})):
                    if atom[0] == "frame":
                        p[n] = ("frame", atom[1])
                    elif atom[0] == "arg":
                        p[n] = ("arg", atom[1])
            for k, atoms in st.items():
                if not (isinstance(k, tuple) and k[0] == "m" and spoff is not None):
                    continue
                stk = k[1] + spoff
                if not (0 <= stk < 128):
                    continue
                for atom in atoms:
                    if atom[0] == "frame":
                        p[("stk", stk)] = ("frame", atom[1])
                    elif atom[0] == "arg":
                        p[("stk", stk)] = ("arg", atom[1])
            if p:
                passes[a] = p
        reads = {}
        for e in self.edges[entry]:
            if e["kind"] in ("indirect_call", "indirect_tail") and e.get("set") == "app_function_pointers":
                site = int(e["site"], 16)
                rT = self._regs(self.ins_at[site]["ops"])[0]
                try:
                    reads[site] = self._pt_read(entry, site, rT, at)
                except Finding as exc:
                    reads[site] = exc                      # surfaced only if this call is actually on a counted path
        needs = {v[0] for v in reads.values() if not isinstance(v, Finding) and not (isinstance(v[0], tuple) and v[0][0] == "self")}
        for p in passes.values():
            for spec in p.values():
                if spec[0] == "arg":
                    needs.add(spec[1])
        out = {"passes": passes, "reads": reads, "needs": frozenset(needs),
               "fields": {A: (UNKNOWN if v is UNKNOWN else frozenset(v)) for A, v in fields.items()}}
        self._pt_state[entry] = at
        self._pt_cache[entry] = out
        return out

    def _pointsto_state(self, entry: int) -> dict:
        self._pointsto(entry)
        return self._pt_state[entry]

    def _pt_join(self, x, y):
        u = x | y
        return frozenset({("other",)}) if len(u) > 8 else u

    def _pt_slot(self, entry: int, addr: int, imm: int) -> int | None:
        offs = self.sp_at[entry].get(addr, frozenset())
        return (imm - next(iter(offs))) if len(offs) == 1 else None

    def _pt_slot_via(self, entry: int, addr: int, base: str, off: int, st: dict) -> int | None:
        """The entry-relative frame slot (A) the address [base, #off] denotes: via sp, or via any register that
        holds a single frame address ('frame', B) → B + off. None when it is not a frame address."""
        if base == "sp":
            return self._pt_slot(entry, addr, off)
        atoms = st.get(base, frozenset({("other",)}))
        if len(atoms) == 1 and next(iter(atoms))[0] == "frame":
            return next(iter(atoms))[1] + off
        return None

    def _pt_atom(self, entry: int, i: dict, st: dict) -> frozenset:
        o = i["ops"].replace(" ", "")
        fam = self._family(i)
        rs = self._regs(o)
        if fam == "mov" and len(rs) >= 1 and o == f"{rs[0]},sp":
            A = self._pt_slot(entry, i["addr"], 0)
            return frozenset({("frame", A)}) if A is not None else frozenset({("other",)})
        if fam in ("add", "addw") and len(rs) == 2 and rs[1] == "sp" and ",#" in o:
            A = self._pt_slot(entry, i["addr"], imm(o))
            return frozenset({("frame", A)}) if A is not None else frozenset({("other",)})
        if fam in ("add", "addw") and len(rs) == 2 and ",#" in o:          # add rd, <frame ptr>, #k
            base = st.get(rs[1], frozenset({("other",)}))
            if len(base) == 1 and next(iter(base))[0] == "frame":
                return frozenset({("frame", next(iter(base))[1] + imm(o))})
            return frozenset({("other",)})
        if fam == "mov" and len(rs) == 2 and "#" not in o:
            return st.get(rs[1], frozenset({("other",)}))
        mld = re.fullmatch(r"\w+(?:,\w+)?,\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
        if fam in ("ldr", "ldrd") and mld:
            A = self._pt_slot_via(entry, i["addr"], mld.group(1), int(mld.group(2), 0) if mld.group(2) else 0, st)
            if A is None:
                return frozenset({("other",)})
            if ("m", A) in st:
                return st[("m", A)]
            return frozenset({("arg", ("stk", A))}) if A >= 0 else frozenset({("other",)})
        if fam in ("movw",) and ",#" in o and len(rs) == 1:
            return frozenset({("const", imm(o))})
        if fam == "movt" and ",#" in o and len(rs) == 1:
            out = set()
            for atom in st.get(rs[0], frozenset({("other",)})):
                if atom[0] == "const":
                    v = (imm(o) << 16) | atom[1]
                    out.add(("cb", v & ~1) if (v & ~1) in self.label_at and (self.unit_of(v & ~1) in self.APP_UNITS) else ("other",))
                else:
                    out.add(("other",))
            return frozenset(out)
        return frozenset({("other",)})

    def _pt_step(self, entry: int, i: dict, st: dict, fields: dict) -> dict:
        o = i["ops"].replace(" ", "")
        fam = self._family(i)
        b, cond = base_mnem(i["mnem"])
        # a store: record callbacks going into a frame slot; flag any other store that may hit a frame slot
        if fam.startswith(("str", "stm", "vst", "push")):
            data, slot = [], None
            if fam == "push" or (fam in ("stmdb", "stmfd", "stm", "stmia") and o.startswith("sp")):
                regs = reglist(i["ops"])
                down = (fam in ("stmdb", "stmfd") or fam == "push")
                for k, r in enumerate(regs):
                    A = self._pt_slot(entry, i["addr"], (4 * k - 4 * len(regs)) if down else 4 * k)
                    atoms = st.get(r, frozenset({("other",)}))
                    self._pt_put(fields, A, atoms)
                    if A is not None:
                        if any(x[0] in ("frame", "arg") for x in atoms):
                            st[("m", A)] = atoms
                        else:
                            st.pop(("m", A), None)
                return self._pt_writes(i, st)
            m = re.search(r"\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
            if m:
                slot = self._pt_slot_via(entry, i["addr"], m.group(1), int(m.group(2), 0) if m.group(2) else 0, st)
                data = self._regs(o.split("[")[0])
                if fam.startswith("strd") and len(data) == 1:
                    data.append(self._next_reg(data[0]))
                if slot is None:
                    # a store whose destination frame slot the analysis cannot place: if its base might be a frame
                    # pointer (not provably elsewhere), flag the routine's fields as possibly aliased
                    atoms = st.get(m.group(1), frozenset({("other",)}))
                    if any(x[0] == "frame" for x in atoms):
                        self._pt_put(fields, "ALIAS", {UNKNOWN})
                else:
                    for d, r in enumerate(data):
                        a = st.get(r, frozenset({("other",)}))
                        self._pt_put(fields, slot + 4 * d, a)
                        key = ("m", slot + 4 * d)
                        if any(x[0] in ("frame", "arg") for x in a):
                            st[key] = (st.get(key, frozenset()) | a) if cond else a
                        elif not cond:
                            st.pop(key, None)
            return self._pt_writes(i, st)
        if b in ("bl", "blx"):
            return self._pt_writes(i, st, call=True)
        produced = self._pt_atom(entry, i, st)
        dest = self._regs(o)[0] if self._regs(o) else None
        for r in self.written(i):
            if r in ("sp", "pc"):
                continue
            atom = produced if r == dest else frozenset({("other",)})
            st[r] = (st.get(r, frozenset({("other",)})) | atom) if cond else atom   # conditional write: keep both
        return st

    def _pt_writes(self, i, st, call=False):
        for r in (self.CALLER_SAVED if call else self.written(i)):
            if r not in ("sp", "pc"):
                st[r] = frozenset({("other",)})
        return st

    def _fields_put(self, entry: int, fields: dict, slot, atoms) -> None:
        """Record what a store puts in a frame slot, from its reaching-def value. A field may hold callbacks
        (constants), forwarded incoming arguments (('arg', n) — resolved later in the building routine's binding) or
        nested frame objects (('frame', A')). Several possibilities are kept. A meaningful value mixed with an
        opaque ('other',) is UNKNOWN (a read of it is a Finding); a purely opaque store leaves the slot a non-field."""
        if slot is None:
            return
        keep = {a for a in atoms if a[0] in ("cb", "arg", "frame")}
        if keep and any(a[0] == "other" for a in atoms):
            fields[slot] = UNKNOWN
        elif keep:
            if fields.get(slot) is UNKNOWN:
                return
            fields.setdefault(slot, set()).update(keep)

    def _pt_put(self, fields: dict, slot, atoms):
        cbs = {a[1] for a in atoms if a[0] == "cb"}
        if slot is None or slot == "ALIAS" or any(a[0] != "cb" for a in atoms):
            # a store whose slot or value is not pinned: only harmful if it could hit a callback field — mark it so a
            # read that lands on an unknown write is refused. Keyed ALIAS covers an unresolved base.
            if cbs or slot in (None, "ALIAS"):
                fields.setdefault("ALIAS" if slot in (None, "ALIAS") else slot, set())
                (fields["ALIAS"] if slot in (None, "ALIAS") else fields[slot]).add(UNKNOWN)
            if slot not in (None, "ALIAS"):
                fields.setdefault(slot, set()).update(cbs)
            return
        fields.setdefault(slot, set()).update(cbs if cbs else {UNKNOWN})

    def _pt_read(self, entry: int, site: int, rT: str, state: dict):
        """What the indirect call at `site` targets: (arg index, "DIRECT") when the pointer IS an incoming argument
        (a callback passed directly), or (arg index, field offset) when it is a field load of an incoming object. A
        Finding when it is neither on every path."""
        direct = self._pt_eval(entry, site, rT, state)
        if len(direct) == 1 and next(iter(direct))[0] == "arg":
            return (next(iter(direct))[1], "DIRECT")
        keys = set()
        for w in self.reaching_writers(entry, site, rT):
            if w is None:
                raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} is unwritten on a path")
            o = w["ops"].replace(" ", "")
            fam = self._family(w)
            m = re.fullmatch(rT + r",\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o) if fam == "ldr" else None
            if m:
                base, off = m.group(1), int(m.group(2), 0) if m.group(2) else 0
            elif fam in ("ldm", "ldmia", "ldmfd") and "{" in o:
                mb = re.match(r"(\w+)!?,\{", o)
                regs = reglist(w["ops"])
                if not mb or not regs or regs[0] != rT:
                    raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} comes from {w['mnem']} {w['ops']}, not the first loaded word")
                base, off = mb.group(1), 0                 # ldm base,{rT,...}: rT is the word at base + 0
            else:
                raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} is {w['mnem']} {w['ops']}, not a field load")
            if base == "sp":
                slot = self._pt_slot(entry, w["addr"], off)
                keys.add((("self", slot), 0) if slot is not None else None)
                continue
            batoms = self._pt_eval(entry, w["addr"], base, state)
            if len(batoms) == 1 and next(iter(batoms))[0] == "arg":
                keys.add((next(iter(batoms))[1], off))
            elif len(batoms) == 1 and next(iter(batoms))[0] == "frame":
                keys.add((("self", next(iter(batoms))[1] + off), 0))
            else:
                raise Finding(f"{self.name(entry)}: the field base {base} at {w['addr']:#x} is neither an incoming argument nor this frame ({sorted(batoms)})")
        if len(keys) != 1 or None in keys:
            raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} is not one object field ({keys})")
        return next(iter(keys))

    ARGREG = {"r0": 0, "r1": 1, "r2": 2, "r3": 3}

    def _pt_eval(self, entry: int, at: int, reg: str, state: dict, depth: int = 0) -> set:
        """`reg`'s object atoms at `at` computed purely from its REACHING DEFINITIONS (never the path-insensitive
        join, whose stale entry value would pollute a dominating definition): each last writer evaluated by its own
        form — a frame address (sp or a frame-pointer register ± an immediate), an incoming-argument / spill load, a
        movw / movt callback constant, a copy — recursively. An unwritten register is its incoming argument (r0–r3)
        or ('other',); an unmodelled writer is ('other',)."""
        key = (entry, at, reg)
        memo = self._pt_eval_memo
        if key in memo:
            return memo[key] if memo[key] is not None else set()          # a cycle contributes nothing new (bottom)
        if depth > 24:
            return {("other",)}
        memo[key] = None                                                  # mark in-progress (cycle guard)
        out: set = set()
        for w in self.reaching_writers(entry, at, reg):
            if w is None:
                out.add(("arg", self.ARGREG[reg]) if reg in self.ARGREG else ("other",))
                continue
            out |= self._pt_eval_writer(entry, w, state, depth)
        out = out or {("other",)}
        memo[key] = out
        return out

    def _pt_eval_writer(self, entry: int, w: dict, state: dict, depth: int) -> set:
        o = w["ops"].replace(" ", "")
        fam = self._family(w)
        rs = self._regs(o)
        if fam == "mov" and len(rs) == 2 and o == f"{rs[0]},sp":                  # rd = sp (frame base)
            A = self._pt_slot(entry, w["addr"], 0)
            return {("frame", A)} if A is not None else {("other",)}
        if fam == "mov" and len(rs) == 2 and "#" not in o and rs[1] != "sp":      # a copy
            return self._pt_eval(entry, w["addr"], rs[1], state, depth + 1)
        if fam in ("add", "addw") and len(rs) == 2 and rs[1] == "sp" and ",#" in o:
            A = self._pt_slot(entry, w["addr"], imm(o))
            return {("frame", A)} if A is not None else {("other",)}
        if fam in ("add", "addw") and len(rs) == 2 and ",#" in o:                # add rd, <frame ptr>, #k
            base = self._pt_eval(entry, w["addr"], rs[1], state, depth + 1)
            return {("frame", a[1] + imm(o)) if a[0] == "frame" else ("other",) for a in base}
        if fam in ("ldr", "ldrd") and re.fullmatch(r"\w+(?:,\w+)?,\[sp(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o):
            A = self._pt_slot(entry, w["addr"], imm(o) if "#" in o else 0)
            if A is None:
                return {("other",)}
            if A >= 0:
                return {("arg", ("stk", A))}                           # an incoming stack argument
            width = 8 if self._family(w) == "ldrd" else 4             # a local slot: prove it is initialised first
            if not self._must_init(entry, w["addr"], A, 4, state):
                return {("other",)}                                   # may be uninitialised / aliased: a Finding upstream
            stores, _unset = self._reaching_stores_to(entry, w["addr"], A)
            out = set()
            for st_addr in stores:
                src = self._slot_src_reg(entry, st_addr, A)
                out |= self._pt_eval(entry, st_addr, src, state, depth + 1) if src else {("other",)}
            return out or {("other",)}
        if fam == "movw" and ",#" in o and len(rs) == 1:
            return {("const", imm(o))}
        if fam == "movt" and ",#" in o and len(rs) == 1:                         # combine with the reaching movw
            out = set()
            for lo in self._pt_eval(entry, w["addr"], rs[0], state, depth + 1):
                if lo[0] == "const":
                    v = (imm(o) << 16) | lo[1]
                    out.add(("cb", v & ~1) if (v & ~1) in self.label_at and self.unit_of(v & ~1) in self.APP_UNITS else ("other",))
                else:
                    out.add(("other",))
            return out
        return set(self._pt_atom(entry, w, state.get(w["addr"], {})))

    def _pt_base_arg(self, entry: int, at: int, base: str, state: dict) -> set:
        """The incoming argument identifier whose object `base` is, at `at`, on every path — one ('arg', n)."""
        atoms = self._pt_eval(entry, at, base, state)
        if len(atoms) == 1 and next(iter(atoms))[0] == "arg":
            return {next(iter(atoms))[1]}
        raise Finding(f"{self.name(entry)}: the object base {base} at {at:#x} is not one incoming argument ({sorted(atoms)})")

    def rule_targets(self, name: str) -> list[int]:
        """The context-FREE target set of a rule (for app_function_pointers: every pointer any producer makes — the
        depth computation narrows it to the producers ACTIVE on the path)."""
        if name in self.site_rules:
            return self.site_rules[name]["targets"]
        if name == "exception_table":
            t, why = self.exc_targets, f"{EXC_TABLE}'s initial entries; materialised only by the dispatchers, which never store"
        elif name == "init_fini_arrays":
            t, why = self._arrays(), "the words of .preinit_array / .init_array / .fini_array"
        elif name == "app_function_pointers":
            prod = self.app_producers()
            t = sorted(set().union(*prod.values())) if prod else []
            why = ("the pointers materialised (movw / movt) by the routines of b3/firmware that are ACTIVE on the call "
                   "path; every materialisation goes only into its routine's own frame, a call's argument or a copy, "
                   "none is a literal word, none is materialised outside the image's units")
        elif name == "newlib_file_ops":
            t, why = self.defined_in("libc_a-stdio.o"), "the address-taken functions of libc.a(libc_a-stdio.o): the FILE read / write / seek / close"
        elif name == "newlib_locale_conversions":
            t, why = self.defined_in("libc_a-mbtowc_r.o", "libc_a-wctomb_r.o"), "the address-taken functions of libc.a(libc_a-mbtowc_r.o, libc_a-wctomb_r.o)"
        elif name == "newlib_stdio_exit_handler":
            t, why = self.defined_in("libc_a-findfp.o"), "the address-taken functions of libc.a(libc_a-findfp.o)"
        elif name == "atexit_registrations":
            t, why = self._atexit_targets()
        elif name == "fwalk_callers":
            t, why = self._fwalk_targets()
        elif name == "xil_assert_callback":
            if not self._only_reader("Xil_AssertCallbackRoutine", "Xil_Assert"):
                raise Finding("Xil_AssertCallbackRoutine is not provably 0: Xil_Assert's indirect call is unresolved")
            t, why = [], "Xil_AssertCallbackRoutine starts at 0 and only Xil_Assert, which never stores, references it"
        else:
            raise Finding(f"no rule {name!r}")
        if name not in ("xil_assert_callback",) and not t:
            raise Finding(f"the target set {name!r} is empty: the rule found nothing to call")
        self.site_rules[name] = {"targets": t, "rule": why}
        return t

    def _need(self, *names: str) -> list[int]:
        out = []
        for n in names:
            if n not in self.syms:
                raise Finding(f"no {n} in the image")
            out.append(self.syms[n][0] & ~1)
        return out

    def _atexit_targets(self) -> tuple[list[int], str]:
        """__call_exitprocs calls what __register_exitproc recorded. The image's only route there is atexit, which
        forwards its own argument (`mov r1, r0`, then the transfer, straight-line); neither is address-taken; no
        __cxa_atexit / on_exit is referenced; and every caller of atexit passes a CONSTANT code address in r0."""
        atexit, reg = self._need("atexit", "__register_exitproc")
        for n in ("__cxa_atexit", "on_exit"):
            if n in self.syms:
                raise Finding(f"{n} is in the image: __call_exitprocs' targets are not only atexit's")
        for a in (atexit, reg):
            if a in self.address_taken:
                raise Finding(f"{self.name(a)} is address-taken: a registration the call sites do not show")
        sites = self.direct_sites(reg)
        if not sites or any(s[0] != atexit for s in sites):
            raise Finding(f"__register_exitproc is reached from {[self.name(s[0]) for s in sites]}, not atexit alone")
        for _owner, site, _k in sites:
            w = self._straight_back(atexit, site, "r1")
            if w is None or w["ops"].replace(" ", "") != "r1,r0" or self._family(w) != "mov":
                raise Finding("atexit does not forward its argument to __register_exitproc as its function")
            self._straight_back(atexit, w["addr"], "r0") is None or self._raise("atexit writes r0 before forwarding it")
        out = set()
        callers = self.direct_sites(atexit)
        if not callers:
            raise Finding("atexit has no caller: __call_exitprocs has nothing to call, and the rule would be vacuous")
        for owner, site, _k in callers:
            v = self.const_at(owner, site, "r0")
            if (v & ~1) not in self.label_at:
                raise Finding(f"{self.name(owner)} registers {v:#x}, which is not code")
            out.add(v & ~1)
        why = ("the constants every caller of atexit passes (" + ", ".join(f"{self.name(o)} at {s:#x}" for o, s, _ in callers)
               + "); atexit forwards its r0 as __register_exitproc's function, and nothing else reaches __register_exitproc")
        return sorted(out), why

    def _fwalk_targets(self) -> tuple[list[int], str]:
        """_fwalk_sglue(ptr, function, sglue) calls the function it is handed: its indirect call goes through a
        callee-saved register written once, as a copy of r1, in its straight entry run; it is not address-taken; and
        every caller passes a CONSTANT code address in r1."""
        fw, = self._need("_fwalk_sglue")
        if fw in self.address_taken:
            raise Finding("_fwalk_sglue is address-taken: its callers are not all visible")
        regs = set()
        for i in self.region(fw):
            if base_mnem(i["mnem"])[0] == "blx" and not branch_target(i["ops"]):
                regs.add(i["ops"].replace(" ", ""))
        if len(regs) != 1 or not regs <= set(self.CALLEE_SAVED):
            raise Finding(f"_fwalk_sglue's indirect calls go through {sorted(regs)}, not one callee-saved register")
        self.forwarded(fw, regs.pop(), "r1")
        out = set()
        callers = self.direct_sites(fw)
        if not callers:
            raise Finding("_fwalk_sglue has no caller")
        for owner, site, _k in callers:
            v = self.const_at(owner, site, "r1")
            if (v & ~1) not in self.label_at:
                raise Finding(f"{self.name(owner)} hands _fwalk_sglue {v:#x}, which is not code")
            out.add(v & ~1)
        why = ("the constants every caller passes in r1 (" + ", ".join(f"{self.name(o)} at {s:#x}" for o, s, _ in callers)
               + "); _fwalk_sglue calls only through its copy of r1")
        return sorted(out), why

    @staticmethod
    def _raise(msg: str):
        raise Finding(msg)

    def may_return(self, entry: int, path: tuple = ()) -> bool:
        """Whether the routine can return to its caller: its own return instructions, or a tail transfer to one
        that can (an indirect tail counts as returning). Computed-jump regions are taken to return."""
        if entry in path:
            return False
        self.analyse(entry)
        if self.own_return.get(entry, True):
            return True
        for e in self.edges[entry]:
            if e["kind"] in ("tail", "fallthrough") and self.may_return(e["to"], path + (entry,)):
                return True
            if e["kind"] == "indirect_tail":
                return True
        return False

    def branch_targets_of(self, entry: int) -> set:
        """Every address a branch, a table branch or a call return of the routine's region can reach."""
        out = set()
        for i in self.region(entry):
            bb, _c = base_mnem(i["mnem"])
            if bb in ("b", "cbz", "cbnz") and branch_target(i["ops"]):
                out.add(branch_target(i["ops"])[0])
            if i["mnem"].split(".")[0] in ("tbb", "tbh"):
                out.update(self._table_branch(i["addr"], i))
        return out

    CALLEE_SAVED = ("r4", "r5", "r6", "r7", "r8", "r9", "sl", "fp")

    def _region_succ(self, entry: int) -> dict[int, list[int]]:
        """An OVER-approximate CFG of the routine's region for dominance: branches, conditional fallthroughs, table
        branches; a computed jump goes to every instruction of the region; returns and tail transfers end."""
        if entry in self._rsucc_cache:
            return self._rsucc_cache[entry]
        ins = self.region(entry)
        addrs = [i["addr"] for i in ins]
        inreg = set(addrs)
        succ = {}
        for k, i in enumerate(ins):
            a = i["addr"]
            nxt = addrs[k + 1] if k + 1 < len(addrs) else None
            b, cond = base_mnem(i["mnem"])
            o = i["ops"].replace(" ", "")
            out = []
            if i["mnem"] == ".data":
                succ[a] = []
                continue
            ret = (b == "bx") or (b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in i["ops"])
            if (b == "add" and o.startswith("pc,pc,")) or (b == "mov" and o.startswith("pc,")):
                out = list(addrs)
            elif i["mnem"].split(".")[0] in ("tbb", "tbh"):
                out = [t for t in self._table_branch(a, i) if t in inreg]
            elif b in ("b", "cbz", "cbnz") and branch_target(i["ops"]):
                t = branch_target(i["ops"])[0]
                if t in inreg:
                    out.append(t)
                if (cond or b in ("cbz", "cbnz")) and nxt is not None:
                    out.append(nxt)
            elif ret:
                if cond and nxt is not None:
                    out.append(nxt)
            elif nxt is not None:
                out.append(nxt)
            succ[a] = out
        self._rsucc_cache[entry] = succ
        return succ

    def _dominates(self, entry: int, w: int, j: int) -> bool:
        """Every path of the over-approximate region CFG from the entry to `j` passes through `w`."""
        succ = self._region_succ(entry)
        seen, stack = {entry}, [entry]
        if entry == w:
            return True
        while stack:
            a = stack.pop()
            if a == j:
                return False
            for t in succ.get(a, []):
                if t != w and t not in seen:
                    seen.add(t)
                    stack.append(t)
        return True

    def _invariants(self, entry: int, entered: set, jump: int) -> dict[str, frozenset]:
        """Callee-saved registers (AAPCS: preserved by every callee) written EXACTLY ONCE in the routine — not counting
        the restoring pop of a return — where that one write DOMINATES the computed jump and is a literal load or
        mov #k: on every path to the jump the register holds that value."""
        ins = self.region(entry)
        writes: dict[str, list[int]] = {}
        for k, i in enumerate(ins):
            o = i["ops"].replace(" ", "")
            m = i["mnem"].split(".")[0]
            mb, _ = base_mnem(i["mnem"])
            if mb in ("pop", "ldm", "ldmia", "ldmfd") and "{" in i["ops"]:
                regs_ = reglist(i["ops"])
                if "pc" in regs_:
                    continue                                 # a return: nothing after it in this routine
                for r in regs_:
                    writes.setdefault(r, []).append(k)
                continue
            parts = o.split(",")
            if parts and re.fullmatch(r"r\d+|ip|lr|sl|fp", parts[0]) and not re.match(r"(cmp|cmn|tst|teq|str|stm|push|vst|it|nop|b)", m):
                writes.setdefault(parts[0], []).append(k)
            if m in ("ldrd", "strd") or "ldrd" in m:
                pass
        out = {}
        for r in self.CALLEE_SAVED:
            w = writes.get(r, [])
            if len(w) != 1 or not self._dominates(entry, ins[w[0]]["addr"], jump):
                continue
            i = ins[w[0]]
            o = i["ops"].replace(" ", "")
            if i["mnem"] == "ldr" and ",[pc,#" in o:
                lit = ((i["addr"] + 4) & ~3 if i["thumb"] else i["addr"] + 8) + imm(o)
                if lit in self.words:
                    out[r] = frozenset([self.words[lit]])
            elif i["mnem"] in ("mov", "movs", "mov.w") and re.fullmatch(r"\w+,#-?\w+", o):
                out[r] = frozenset([imm(o)])
        return out

    def _jump_targets(self, entry: int, jump: int) -> list[int]:
        """The exact set of addresses the computed jump at `jump` can reach, by forward evaluation of POSSIBLE VALUE
        SETS over the window before it: the window reaches back while no branch of the routine can enter it (so the
        values seen are the only ones possible); a conditional branch's FALLTHROUGH is followed and refines its compared
        register (cmp rX, #N; bhi → rX ≤ N; bcs / bhs → rX < N, unsigned); an unconditional transfer or a call ends
        it. Values: literal loads (ldr rd, [pc, #k]), table loads (ldrb / ldrh rd, [rb, ri] with rb exact, read from
        the ELF), mov #k, adr, and / rsb / add / sub with immediates, sub of two sets, add with a shifted set, clz.
        Anything else that writes a register makes it unknown, and an unknown index is a finding."""
        ins = self.region(entry)
        idx = {i["addr"]: k for k, i in enumerate(ins)}
        if jump not in idx:
            raise Finding(f"the computed jump at {jump:#x} is outside its routine's region")
        k = idx[jump]
        entered = self.branch_targets_of(entry)
        start = k
        while start > 0 and k - start < 24:
            prev = ins[start - 1]
            pb, pc_ = base_mnem(prev["mnem"])
            if prev["mnem"] == ".data" or pb in ("bl", "blx", "bx") or (pb in ("b", "cbz", "cbnz") and not pc_ and pb == "b") \
                    or ins[start]["addr"] in entered:
                break
            start -= 1
        if ins[start]["addr"] in entered and start != idx.get(entry, -1):
            pass                                            # the window's first instruction may be a branch target
        LIMIT = 4096
        regs: dict[str, frozenset] = dict(self._invariants(entry, entered, jump))

        def put(r, vals):
            if vals is None or len(vals) > LIMIT:
                regs.pop(r, None)
            else:
                regs[r] = frozenset(v & 0xFFFFFFFF if v >= 0 else v for v in vals)
        last_cmp = None
        geq: set = set()                                     # (a, b): a >=u b holds on this fallthrough path
        clz_of: dict[str, str] = {}                          # rd -> rn when rd = clz(rn) and neither was redefined
        for w in ins[start:k]:
            o = w["ops"].replace(" ", "")
            parts = o.split(",")
            m = w["mnem"].split(".")[0]
            mb, mcond = base_mnem(w["mnem"])
            if m.startswith("cmp") and len(parts) == 2:
                last_cmp = (parts[0], imm(parts[1]) if parts[1].startswith("#") else parts[1])
                continue
            if mb == "b" and mcond:                          # the fallthrough of a conditional branch
                if last_cmp and isinstance(last_cmp[1], int):
                    r, n = last_cmp
                    if m == "bhi":
                        put(r, [v for v in regs[r] if 0 <= v <= n] if r in regs else range(n + 1))
                    elif m in ("bcs", "bhs"):
                        put(r, [v for v in regs[r] if 0 <= v < n] if r in regs else range(n))
                elif last_cmp:                               # cmp ra, rb: the unsigned relation on the fallthrough
                    ra, rb = last_cmp
                    if m in ("bls", "bcc", "blo"):           # taken when ra <=u rb (bls) / ra <u rb (bcc)
                        geq.add((ra, rb))
                    elif m in ("bhi", "bcs", "bhs"):
                        geq.add((rb, ra))
                continue
            if not parts or not re.fullmatch(r"r\d+|ip|lr|sl|fp", parts[0]):
                continue
            if re.match(r"(cmp|cmn|tst|teq|str|stm|push|vst|it|nop|b)", m) and m not in ("bic",):
                continue                                     # writes no register (a compare, a store, a branch, an IT)
            rd = parts[0]
            old_geq, old_clz = geq, clz_of                   # the facts BEFORE this definition are what it may use
            geq = {(x, y) for x, y in geq if rd not in (x, y)}
            clz_of = {d: n for d, n in clz_of.items() if rd not in (d, n)}
            if m.endswith("s") and m[:-1] in ("and", "rsb", "add", "sub", "mov"):
                m = m[:-1]
            vals = None
            try:
                if m == "ldr" and len(parts) >= 2 and parts[1].startswith("[pc,#"):
                    lit = ((w["addr"] + 4) & ~3 if w["thumb"] else w["addr"] + 8) + imm(o)
                    v = self.words.get(lit)
                    vals = None if v is None else [v]
                elif m in ("ldrb", "ldrh") and re.fullmatch(r"\w+,\[(\w+),(\w+)\]", o):
                    rb, ri = re.fullmatch(r"\w+,\[(\w+),(\w+)\]", o).groups()
                    if rb in regs and len(regs[rb]) == 1 and ri in regs:
                        base = next(iter(regs[rb]))
                        width = 1 if m == "ldrb" else 2
                        vals = [int.from_bytes(self.read_bytes(base + width * x, width), "little") for x in regs[ri]]
                elif m == "and" and len(parts) == 3 and parts[2].startswith("#") and imm(parts[2]) >= 0:
                    mask = imm(parts[2])
                    if parts[1] in regs:
                        vals = [x & mask for x in regs[parts[1]]]
                    elif bin(mask).count("1") <= 12:         # an unknown operand: every value x & mask can take
                        vals, sub = [], mask
                        while True:
                            vals.append(sub)
                            if sub == 0:
                                break
                            sub = (sub - 1) & mask
                    else:
                        vals = None
                elif m == "rsb" and len(parts) == 3 and parts[2].startswith("#") and parts[1] in regs:
                    vals = [imm(parts[2]) - x for x in regs[parts[1]]]
                elif m in ("add", "sub") and len(parts) == 3 and parts[1] == "pc" and parts[2].startswith("#"):
                    pc = (w["addr"] + 4) & ~3 if w["thumb"] else w["addr"] + 8
                    vals = [pc + imm(parts[2]) if m == "add" else pc - imm(parts[2])]
                elif m in ("add", "sub") and len(parts) == 3 and parts[2].startswith("#") and parts[1] in regs:
                    c = imm(parts[2]) * (1 if m == "add" else -1)
                    vals = [x + c for x in regs[parts[1]]]
                elif m == "sub" and len(parts) == 3 and parts[1] in regs and parts[2] in regs:
                    vals = sorted({a - b for a in regs[parts[1]] for b in regs[parts[2]]})
                    x, y = old_clz.get(parts[1]), old_clz.get(parts[2])
                    if x and y and (y, x) in old_geq:            # clz is non-increasing: y >=u x  =>  clz(x) - clz(y) >= 0
                        vals = [v for v in vals if v >= 0]
                elif m == "add" and len(parts) == 4 and parts[3].startswith("lsl#") and parts[1] in regs and parts[2] in regs:
                    n = int(parts[3][4:])
                    vals = sorted({a + b * (1 << n) for a in regs[parts[1]] for b in regs[parts[2]]})
                elif m == "clz":
                    vals = range(33)
                    clz_of[rd] = parts[1]
                elif m == "mov" and len(parts) == 2 and parts[1].startswith("#"):
                    vals = [imm(parts[1])]
                elif m == "mov" and len(parts) == 2 and parts[1] in regs:
                    vals = regs[parts[1]]
            except (Finding, KeyError):
                vals = None
            put(rd, vals)
        j = ins[k]
        o = j["ops"].replace(" ", "")
        b, _ = base_mnem(j["mnem"])
        if b == "add":                                     # add pc, pc, rI[, lsl #n] (ARM: pc reads as addr + 8)
            parts = o.split(",")
            n = int(parts[3][4:]) if len(parts) > 3 and parts[3].startswith("lsl#") else 0
            if parts[2] not in regs:
                raise Finding(f"the computed jump at {jump:#x}: its index {parts[2]} has no derivable value set")
            out = sorted({j["addr"] + 8 + v * (1 << n) for v in regs[parts[2]]})
        else:                                              # mov pc, rT
            r = o.split(",")[1]
            if r not in regs:
                raise Finding(f"the computed jump at {jump:#x}: its target {r} has no derivable value set")
            out = sorted({v & ~1 for v in regs[r]})
        bad = [t for t in out if t not in idx or ins[idx[t]]["mnem"] == ".data"]
        if bad:
            raise Finding(f"the computed jump at {jump:#x} can reach {bad[0]:#x}, which is no instruction of its routine")
        self.computed_jumps.append({"routine": self.name(entry), "at": f"{jump:#x}", "targets": len(out),
                                    "range": f"{out[0]:#x}..{out[-1]:#x}"})
        return out

    def read_bytes(self, addr: int, n: int) -> bytes:
        for sec in self.secs:
            if sec["addr"] <= addr and addr + n <= sec["addr"] + sec["size"]:
                o = sec["offset"] + addr - sec["addr"]
                return self.blob[o:o + n]
        raise Finding(f"{addr:#x}: not in a loaded section")

    def _table_branch(self, addr: int, i: dict) -> list[int]:
        """Thumb tbb / tbh [pc, rI(, lsl #1)]: the entry count from the bound check just before it (cmp rI, #N then
        bhi / bcs to the default), the entries read from the ELF; target = (addr + 4) + 2 * entry."""
        o = i["ops"].replace(" ", "")
        m = re.fullmatch(r"\[pc,(r\d+)(?:,lsl#1)?\]", o)
        if not m:
            raise Finding(f"a table branch at {addr:#x} that is not [pc, rI]: {i['ops']}")
        reg = m.group(1)
        prev = sorted(x for x in self.ins_at if x < addr)[-3:]
        n = None
        for k in range(len(prev) - 1):
            c, j = self.ins_at[prev[k]], self.ins_at[prev[k + 1]]
            if c["mnem"].startswith("cmp") and c["ops"].replace(" ", "").startswith(reg + ",#") and base_mnem(j["mnem"])[0] == "b" \
                    and j["mnem"].split(".")[0] in ("bhi", "bcs", "bhs"):
                n = imm(c["ops"]) + (1 if j["mnem"].startswith("bhi") else 0)
        if n is None:
            raise Finding(f"a table branch at {addr:#x} with no bound check before it")
        half = i["mnem"].startswith("tbh")
        raw = self.read_bytes(addr + 4, n * (2 if half else 1))
        ents = struct.unpack(f"<{n}{'H' if half else 'B'}", raw)
        return [addr + 4 + 2 * e for e in ents]

    def _symbol_end(self, addr: int) -> int:
        later = sorted(a for a in self.label_at if a > addr)
        return later[0] if later else max(self.ins_at) + 4

    def targets(self, e: dict) -> list[int]:
        if e["kind"] in ("call", "call_noreturn", "tail", "fallthrough"):
            return [e["to"]]
        return self.rule_targets(e["set"])

    # ---- the depth: context-carrying (the owner's ruling on the newlib recursion, option A)
    #
    # A node is (routine, context); context = (the application pointers produced by the routines ACTIVE on the path,
    # whether this is the NESTED _vfiprintf_r activation). The memo is keyed by the node. A routine already on the
    # path is recursion — a Finding — with ONE exception, the newlib bounded rule: __sbprintf's call to _vfiprintf_r,
    # entered with one _vfiprintf_r and one __sbprintf on the path, at the one site the rule verified. The nested
    # activation skips exactly one edge — its own call to __sbprintf, which the verified guard makes unreachable
    # under the fake FILE — and counts every other branch and callee. A third _vfiprintf_r, a second __sbprintf, or
    # any other cycle is a Finding.

    ROOT_CTX = (frozenset(), False)                    # ctx = (the object binding, the nested-_vfiprintf_r flag)

    def _app_targets(self, entry: int, site: int, binding: dict) -> list[int]:
        """The callbacks an application-pointer call at `site` can reach: the field it reads of the object bound to
        its argument. An unbound argument, an aliased / unknown store in the building routine, or a field with no
        recorded callback is a Finding — never silently empty, never narrowed to break a cycle."""
        r = self._pointsto(entry)["reads"][site]
        if isinstance(r, Finding):
            raise r
        argidx, off = r
        if isinstance(argidx, tuple) and argidx[0] == "self":          # a callback in this routine's OWN frame
            return sorted(self._field_callbacks(entry, argidx[1], binding))
        v = binding.get(argidx)
        if v is None:
            raise Finding(f"{self.name(entry)}: argument {argidx} of the indirect call at {site:#x} is not bound on the path")
        if off == "DIRECT":
            if v[0] != "cbs":
                raise Finding(f"{self.name(entry)}: argument {argidx} of the direct-pointer call at {site:#x} is {v[0]}, not a callback")
            return sorted(v[1])
        if v[0] != "obj":
            raise Finding(f"{self.name(entry)}: argument {argidx} of the field call at {site:#x} is {v[0]}, not an object")
        return sorted(self._field_callbacks(v[1], v[2] + off, dict(v[3])))

    def _field_callbacks(self, R: int, slot: int, builder_binding: dict, depth: int = 0) -> set:
        """The callbacks a field at `R`'s frame slot can hold: constants directly; a forwarded argument resolved in
        the binding that was active when R built the object; a nested object is not a callable target. A Finding when
        the field is unset, aliased, unknown, or resolves to a non-callback."""
        if depth > 8:
            raise Finding(f"{self.name(R)}: the field points-to nests too deep at {slot:#x}")
        fields = self._pointsto(R)["fields"]
        if "ALIAS" in fields:
            raise Finding(f"{self.name(R)} has an unplaceable store; the field at {slot:#x} may be aliased")
        content = fields.get(slot)
        if content is None:
            raise Finding(f"{self.name(R)} stores no callback at the field read (slot {slot:#x})")
        if content is UNKNOWN:
            raise Finding(f"the field read of {self.name(R)}'s object (slot {slot:#x}) has no pinned callback")
        out = set()
        for atom in content:
            if atom[0] == "cb":
                out.add(atom[1])
            elif atom[0] == "arg":
                b = builder_binding.get(atom[1])
                if b is None or b[0] != "cbs":
                    raise Finding(f"{self.name(R)}'s field at {slot:#x} forwards argument {atom[1]}, not bound to a callback")
                out |= set(b[1])
            else:
                raise Finding(f"{self.name(R)}'s field at {slot:#x} holds {atom[0]}, not a callback")
        return out

    def _covers(self, entry: int, a: int, slot: int, width: int, state: dict) -> bool:
        """Whether the instruction at `a` is a store that FULLY covers [slot, slot+width): a word-or-wider store
        (str / strd / stm / push / vstr) landing exactly on `slot` (or `slot` within a multi-word store's range at a
        4-byte stride). A byte / halfword store does not cover a 4-byte read."""
        i = self.ins_at[a]
        fam = self._family(i)
        o = i["ops"].replace(" ", "")
        if not fam.startswith(("str", "stm", "push", "vst")) or fam in ("strb", "strh"):
            return False
        if fam == "push" or (fam in ("stmdb", "stmfd", "stm", "stmia") and o.startswith("sp")):
            regs = reglist(i["ops"])
            down = (fam in ("stmdb", "stmfd") or fam == "push")
            for k in range(len(regs)):
                A = self._pt_slot(entry, a, (4 * k - 4 * len(regs)) if down else 4 * k)
                if A == slot:
                    return True
            return False
        m = re.search(r"\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
        if not m:
            return False
        off = int(m.group(2), 0) if m.group(2) else 0
        n = 2 if fam.startswith("strd") else 1
        if m.group(1) == "sp":
            A0 = self._pt_slot(entry, a, off)
            return A0 is not None and any(A0 + 4 * d == slot for d in range(n))
        batoms = self._pt_eval(entry, a, m.group(1), state)
        return any(at_[0] == "frame" and any(at_[1] + off + 4 * d == slot for d in range(n)) for at_ in batoms)

    def _clobbers(self, entry: int, a: int, slot: int, state: dict) -> bool:
        """Whether the store at `a` MIGHT write `slot` through a base the analysis cannot pin (a register-indexed
        frame store): then the slot's value is no longer known and a reload must be a Finding."""
        i = self.ins_at[a]
        o = i["ops"].replace(" ", "")
        if not self._family(i).startswith(("str", "stm", "vst")):
            return False
        mr = re.search(r"\[(\w+),(\w+)(?:,lsl#\d+)?\]", o)
        if mr and (mr.group(1) == "sp" or any(x[0] == "frame" for x in self._pt_eval(entry, a, mr.group(1), state))):
            return True
        return False

    def _must_init(self, entry: int, at: int, slot: int, width: int, state: dict) -> bool:
        """True when, on EVERY path from the entry to `at`, `slot` is fully initialised by a covering store with no
        possible aliased store in between that the analysis cannot place. A forward MUST analysis: covered = AND over
        predecessors, set by a covering store; a possible aliased store to the slot resets it (the value is then
        unknown). CFG edges are never pruned by expected behaviour — only the real over-approximate graph is used."""
        succ = self._region_succ(entry)
        pred: dict[int, list[int]] = {}
        for a, ts in succ.items():
            for t in ts:
                pred.setdefault(t, []).append(a)
        nodes = set(succ) | {t for ts in succ.values() for t in ts}
        covered_out = {n: True for n in nodes}
        covered_out[entry] = self._covers(entry, entry, slot, width, state) and not self._clobbers(entry, entry, slot, state)
        changed = True
        guard = 0
        while changed and guard < 100000:
            changed = False
            guard += 1
            for n in nodes:
                if n == entry:
                    continue
                ps = pred.get(n, [])
                cin = all(covered_out[p] for p in ps) if ps else False
                cout = (cin or self._covers(entry, n, slot, width, state)) and not self._clobbers(entry, n, slot, state)
                if cout != covered_out[n]:
                    covered_out[n] = cout
                    changed = True
        ps = pred.get(at, [])
        return bool(ps) and all(covered_out[p] for p in ps)

    def _reaching_stores_to(self, entry: int, at: int, slot: int) -> tuple[list[int], bool]:
        """The sp-based store instructions whose frame slot is `slot` and whose value reaches `at` (the last one on
        each backward path), and whether some path reaches the entry with no such store. Over the routine's
        over-approximate CFG."""
        succ = self._region_succ(entry)
        pred: dict[int, list[int]] = {}
        for a, ts in succ.items():
            for t in ts:
                pred.setdefault(t, []).append(a)
        stores, hit_entry, seen = [], False, set()
        stack = list(pred.get(at, []))
        while stack:
            a = stack.pop()
            if a in seen:
                continue
            seen.add(a)
            i = self.ins_at[a]
            if self._slot_src_reg(entry, a, slot) is not None:
                if not self._is_identity_store(entry, a, slot):
                    stores.append(a)
                    continue                               # a real definition: do not look past it
                # an identity re-store (value reloaded from the same slot): transparent, keep looking back
            if a == entry:
                hit_entry = True
            stack += pred.get(a, [])
        return stores, hit_entry

    def _slot_src_reg(self, entry: int, addr: int, slot: int) -> str | None:
        """The register whose value a store at `addr` writes into frame `slot` (sp-relative), or None if it does not
        write that slot. Handles str / strd (immediate offset) and push / stm on sp (register lists)."""
        i = self.ins_at[addr]
        fam = self._family(i)
        o = i["ops"].replace(" ", "")
        if not fam.startswith(("str", "stm", "push")):
            return None
        if fam == "push" or (fam in ("stmdb", "stmfd", "stm", "stmia") and o.startswith("sp")):
            regs = reglist(i["ops"])
            down = (fam in ("stmdb", "stmfd") or fam == "push")
            for k, r in enumerate(regs):
                A = self._pt_slot(entry, addr, (4 * k - 4 * len(regs)) if down else 4 * k)
                if A == slot:
                    return r
            return None
        m = re.search(r"\[sp(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
        if not m:
            return None
        base = self._pt_slot(entry, addr, int(m.group(1), 0) if m.group(1) else 0)
        if base is None:
            return None
        data = self._regs(o.split("[")[0])
        if fam.startswith("strd") and len(data) == 1:
            data.append(self._next_reg(data[0]))
        for d, r in enumerate(data):
            if base + 4 * d == slot:
                return r
        return None

    def _is_identity_store(self, entry: int, store_addr: int, slot: int) -> bool:
        """`str rX, [sp, #m]` where rX was just reloaded from the SAME slot (rX = ldr [sp, #m']) with slot == this
        slot: the store writes the slot's own value back, so it is transparent to what the slot holds."""
        src = self._slot_src_reg(entry, store_addr, slot)
        if src is None:
            return False
        for w in self.reaching_writers(entry, store_addr, src):
            if w is None or self._family(w) not in ("ldr", "ldrd"):
                return False
            m = re.fullmatch(src + r"(?:,\w+)?,\[sp(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", w["ops"].replace(" ", ""))
            if not m or self._pt_slot(entry, w["addr"], int(m.group(1), 0) if m.group(1) else 0) != slot:
                return False
        return True

    def _bind_one(self, caller: int, atoms: set, binding: dict):
        """A binding value for one argument from its reaching-def atoms: ('obj', caller, A) for a frame struct,
        ('cbs', frozenset) for one or more callbacks passed directly, or a forwarded argument resolved through
        `binding`. Ambiguous mixtures (object and callback, or an unknown) are left unbound (None) so the callee
        Findings rather than guess. Several callbacks are all kept."""
        kinds = {a[0] for a in atoms}
        if kinds == {"cb"}:
            return ("cbs", frozenset(a[1] for a in atoms))
        if atoms and all(a[0] == "frame" for a in atoms):
            A = {a[1] for a in atoms}
            return ("obj", caller, next(iter(A)), frozenset(binding.items())) if len(A) == 1 else None
        if atoms and all(a[0] == "arg" for a in atoms):
            vals = {binding.get(a[1]) for a in atoms}
            return next(iter(vals)) if len(vals) == 1 else None
        return None

    def _child_binding(self, caller: int, site: int, callee: int, binding: dict) -> frozenset:
        """The object binding a direct call at `site` gives its callee, PULLED by what the callee uses: for each
        argument identifier the callee dereferences or forwards (`needs`), read the caller's register or outgoing
        stack slot at the call and resolve it — a struct in the caller's own frame, or the caller's own argument
        forwarded through `binding`. An ambiguous or non-object slot is left unbound (the callee then Findings)."""
        needs = self._pointsto(callee).get("needs", frozenset())
        if not needs:
            return frozenset()
        self._pointsto(caller)
        state = self._pt_state.get(caller, {})
        offs = self.sp_at[caller].get(site, frozenset()) if caller in self.sp_at else frozenset()
        spoff = next(iter(offs)) if len(offs) == 1 else None
        cb = {}
        for arg in needs:
            if isinstance(arg, int):                                   # a register argument
                v = self._bind_one(caller, self._pt_eval(caller, site, f"r{arg}", state), binding)
            elif spoff is not None:                                    # an outgoing stack argument
                stores, unset = self._reaching_stores_to(caller, site, arg[1] - spoff)
                if unset or len(stores) != 1:
                    continue
                src = self._slot_src_reg(caller, stores[0], arg[1] - spoff)
                v = self._bind_one(caller, self._pt_eval(caller, stores[0], src, state), binding) if src else None
            else:
                v = None
            if v is not None:
                cb[arg] = v
        return frozenset(cb.items())

    def _reentry(self, entry: int, e: dict, t: int, path: tuple) -> bool:
        names = [self.name(p[0]) for p in path]
        if self.name(entry) != "__sbprintf" or self.name(t) != "_vfiprintf_r" or "_vfiprintf_r" not in names:
            return False
        rule = self.newlib_rule()
        return e.get("site") == rule["sbprintf_to_vfiprintf"]

    def depth(self, entry: int, ctx: tuple | None = None, path: tuple = (), memo: dict | None = None) -> int:
        ctx = self.ROOT_CTX if ctx is None else ctx
        binding = dict(ctx[0])
        memo = {} if memo is None else memo
        names = [self.name(p[0]) for p in path]
        if entry in [p[0] for p in path]:
            ok = (self.name(entry) == "_vfiprintf_r" and ctx[1] and names.count("_vfiprintf_r") == 1
                  and names.count("__sbprintf") == 1 and names[-1] == "__sbprintf")
            if not ok:
                raise Finding("recursion: " + " -> ".join(names + [self.name(entry)]))
        key = (entry, ctx)
        if key in memo:
            return memo[key]
        self.analyse(entry)
        skip = self.newlib_rule()["vfiprintf_to_sbprintf"] if (ctx[1] and self.name(entry) == "_vfiprintf_r") else None
        d = self.local[entry]
        here = path + ((entry, ctx),)
        for e in self.edges[entry]:
            if skip is not None and e.get("site") == skip:
                continue
            if e["kind"] == "call_noreturn" and self.may_return(e["to"]):
                raise Finding(f"{self.name(entry)}: nothing follows its call to {self.name(e['to'])}, which can return")
            if e["kind"] in ("indirect_call", "indirect_tail") and e["set"] == "app_function_pointers":
                tgts = self._app_targets(entry, int(e["site"], 16), binding)
                child = frozenset()
            elif e["kind"] in ("indirect_call", "indirect_tail"):
                tgts, child = self.rule_targets(e["set"]), frozenset()
            else:
                tgts = [e["to"]]
                child = self._child_binding(entry, int(e["site"], 16), e["to"], binding) if e.get("site") else frozenset()
            for t in tgts:
                d = max(d, e["at"] + self.depth(t, (child, self._reentry(entry, e, t, here)), here, memo))
        memo[key] = d
        return d

    # ---- the newlib bounded rule: what is checked on the image, and what is the verified source semantics

    NEWLIB = {
        "version": "4.4.0",
        "version_header": "arm-none-eabi/include/_newlib_version.h",
        "version_header_sha256": "bfc4b55e8665b5c4ae407e090a6aac2fb829905f04a5a7519686631eb1633fff",
        "libc_sha256": "920deffb255f7cd01f501a4eabae436f660b009331c6b61066ded2c628b42e44",
        "member": "libc_a-vfiprintf.o",
        "source": {
            "tarball": "https://sourceware.org/pub/newlib/newlib-4.4.0.20231231.tar.gz",
            "tarball_sha256": "0c166a39e1bf0951dfafcd68949fe0e4b6d3658081d6282f39aeefc6310f2f13",
            "files": {"newlib/libc/stdio/vfprintf.c": "9be0ae8fa83117f45c7b00b7768e0b2be3bf29778b23b54fe15a977afa40bcc8",
                      "newlib/libc/stdio/vfiprintf.c": "baef3e6067f087990c381d5012a7f4d777732ed11a1cad37a88911764dc3a958",
                      "newlib/libc/stdio/wsetup.c": "e670db7ae0427d810d26ee93cc5e8c807e4696b3b9c2dc395e443ecf6de2cbdf",
                      "newlib/libc/stdio/makebuf.c": "91bca8c3f40a8c4b01f35bbbf14687f2b6a196e368e75835438f408ad616cd9a"},
            "lines": {"vfiprintf.c:1-2": "#define INTEGER_ONLY / #include \"vfprintf.c\"",
                      "vfprintf.c:215": "fake._flags = fp->_flags & ~__SNBF;",
                      "vfprintf.c:222": "fake._bf._base = fake._p = buf;",
                      "vfprintf.c:615": "if ((fp->_flags & (__SNBF|__SWR|__SRW)) == (__SNBF|__SWR) &&",
                      "wsetup.c:69": "if (fp->_bf._base == NULL …) → __smakebuf_r"},
        },
        "semantics": ("__sbprintf hands _vfiprintf_r a FAKE FILE on its own stack: the caller's flags with __SNBF "
                      "cleared and a non-NULL buffer. _vfiprintf_r calls __sbprintf only when (flags & (__SNBF|__SWR|"
                      "__SRW)) == (__SNBF|__SWR). Before that test the flags halfword is written only by __smakebuf_r, "
                      "reached only from __swsetup_r when the FILE's buffer is NULL — never for the fake. So the "
                      "nested _vfiprintf_r cannot call __sbprintf: at most two _vfiprintf_r and one __sbprintf "
                      "activations. FILE._flags is a short; a word or wider store, or a store through memset / a "
                      "pointer argument, into a FILE's flags is excluded by the source, not by the image check."),
    }

    def file_layout(self) -> dict:
        """offsetof(FILE, _flags), offsetof(FILE, _bf._base) and __SNBF / __SWR / __SRW, from the PINNED toolchain's
        own headers, by compiling a probe with the application's flags (the layout the libc was built against is the
        layout these headers declare: same newlib version, digest-checked)."""
        import tempfile
        import b3_build_evidence as be
        _bsp, app = be.build_flags()
        src = ("#include <stdio.h>\n#include <stddef.h>\n"
               "const int b3_off_flags = offsetof(FILE, _flags);\nconst int b3_off_base = offsetof(FILE, _bf._base);\n"
               "const int b3_snbf = __SNBF;\nconst int b3_swr = __SWR;\nconst int b3_srw = __SRW;\n"
               "const int b3_size_flags = sizeof(((FILE *)0)->_flags);\n")
        with tempfile.TemporaryDirectory(prefix="b3_stack_probe_") as d:
            c = Path(d) / "probe.c"
            c.write_text(src)
            p = subprocess.run([str(be.trusted_compiler()), *app, "-S", "-o", "-", str(c)], capture_output=True, text=True)
        if p.returncode != 0:
            raise Finding(f"the FILE layout probe does not compile: {p.stderr[-300:]}")
        vals = {}
        for name in ("b3_off_flags", "b3_off_base", "b3_snbf", "b3_swr", "b3_srw", "b3_size_flags"):
            m = re.search(rf"^{name}:\s*\n\s*\.word\s+(\d+)", p.stdout, re.M)
            if not m:
                raise Finding(f"the FILE layout probe gave no {name}")
            vals[name[3:]] = int(m.group(1))
        return vals

    def _one_offset(self, entry: int, addr: int) -> int:
        offs = self.sp_at[entry].get(addr, frozenset())
        if len(offs) != 1:
            raise Finding(f"{self.name(entry)}: the SP offset at {addr:#x} is not one value ({sorted(offs)})")
        return next(iter(offs))

    def _frame_stores(self, entry: int, slot: int, width: int) -> list[dict]:
        """Every store of the routine that may write the frame bytes [slot, slot + width) — `slot` relative to the
        ENTRY SP (an SP-relative immediate k at SP offset o is the byte k - o). push / stmdb sp! / stm sp / vpush by
        their exact ranges; a store through any OTHER register the must-analysis shows holds a frame address may
        write anywhere in the frame, so it counts as overlapping."""
        out = []
        frame = self.stack_pointers(entry)
        for i in self.region(entry):
            fam = self._family(i)
            o = i["ops"].replace(" ", "")
            if not fam.startswith(("str", "stm", "push", "vst", "vpush")) or i["addr"] not in self.sp_at[entry]:
                continue
            ranges = []
            for off in self.sp_at[entry][i["addr"]]:
                if fam == "push" or (fam in ("stmdb", "stmfd") and o.startswith("sp!")):
                    n = 4 * len(reglist(i["ops"]))
                    ranges.append((-off - n, -off))
                elif fam == "vpush":
                    n = vbytes(reglist(i["ops"]))
                    ranges.append((-off - n, -off))
                elif fam.startswith(("stm", "vstm")) and o.startswith("sp"):
                    n = 4 * len(reglist(i["ops"])) if fam.startswith("stm") else vbytes(reglist(i["ops"]))
                    ranges.append((-off, -off + n))
                else:
                    m = re.search(r"\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\](!?)", o)
                    if not m:
                        base = re.match(r"(\w+)", o).group(1) if fam.startswith(("stm", "vstm")) else None
                        if base and base in frame.get(i["addr"], frozenset()):
                            ranges.append((-(1 << 30), 1 << 30))
                        continue
                    base, k = m.group(1), int(m.group(2), 0) if m.group(2) else 0
                    n = {"strb": 1, "strh": 2, "strd": 8, "vstr": 8}.get(fam, 4)
                    if base == "sp":
                        ranges.append((k - off, k - off + n))
                    elif base in frame.get(i["addr"], frozenset()):
                        ranges.append((-(1 << 30), 1 << 30))   # through a frame pointer: anywhere in the frame
            if any(lo < slot + width and slot < hi for lo, hi in ranges):
                out.append(i)
        return out

    def _pure(self, entry: int, seen: set | None = None) -> bool:
        """The routine and everything it can call contain no store instruction at all."""
        seen = set() if seen is None else seen
        if entry in seen:
            return True
        seen.add(entry)
        self.analyse(entry)
        for i in self.region(entry):
            fam = self._family(i)
            if fam.startswith(("str", "stm", "push", "vst", "vpush", "swp", "ldrex", "strex")) and not fam.startswith("push"):
                return False
            if fam == "push" or (fam in ("stmdb", "stmfd") and i["ops"].replace(" ", "").startswith("sp!")):
                continue
        for e in self.edges[entry]:
            if e["kind"] in ("indirect_call", "indirect_tail"):
                return False
            if not self._pure(e["to"], seen):
                return False
        return True

    def _reachable_without(self, entry: int, goal: int, cut=None, stop=None) -> bool:
        """Whether `goal` is reachable from the entry in the routine's over-approximate CFG with the edge `cut` (or
        every edge of a set of them) removed, never passing `stop` (an address or a set)."""
        cuts = set(cut) if isinstance(cut, (set, frozenset, list)) else ({cut} if cut else set())
        stops = set(stop) if isinstance(stop, (set, frozenset, list)) else ({stop} if stop is not None else set())
        succ = self._region_succ(entry)
        seen, stack = {entry}, [entry]
        while stack:
            a = stack.pop()
            if a == goal:
                return True
            if a in stops:
                continue
            for t in succ.get(a, []):
                if (a, t) in cuts:
                    continue
                if t not in seen:
                    seen.add(t)
                    stack.append(t)
        return False

    # ---- a small value analysis for the newlib buffer-NULL proof (the owner's ruling of 2026-10-04, option 1)
    #
    # Over __swsetup_r's over-approximate CFG, every core register's value is a SET of atoms, one of:
    #   ('file',)      the FILE __swsetup_r was handed (its r1, and copies of it)
    #   ('buffer',)    a load of [FILE, #BASE] — the FILE's _bf._base
    #   ('const', k)   the constant k
    #   ('other',)     anything else
    # A conditional write ADDS its atom to the register's set (it may or may not run); an unconditional write
    # replaces it; a call makes every caller-saved register ('other',); a store through the FILE to its buffer field
    # is a Finding (the buffer must not be overwritten before the test). The join at a merge is the per-register
    # union. The point of it: at the branch that gates __smakebuf_r, the tested register's set must be a subset of
    # {buffer} ∪ {nonzero constants} with buffer present — so the tested value being zero forces the buffer to be
    # zero. Anything else (an unknown value, a zero constant, an uncovered path) leaves ('other',) or ('const', 0)
    # in the set and the proof fails.
    VALUE_CAP = 6

    def _value_analysis(self, entry: int, BASE: int, file_reg: str = "r1") -> dict[int, dict[str, frozenset]]:
        """Condition-sensitive forward value sets, forking exactly as `_analyse_paths`: a state is (address, the
        known condition decisions) with a value map; a conditional instruction forks into "executes" (its condition
        recorded true) and "skipped" (recorded false); a flag write forgets the decisions; a conditional branch
        under a recorded-true condition is taken, under a recorded-false one falls through. So in `lsls (sets flags);
        it mi; ldrmi r2,[FILE,#BASE]; bmi T`, the state that takes the branch is the one in which the load ran, and
        T is reached with r2 the buffer. Returned: per address, the per-register union over every state reaching it."""
        succ = self._region_succ(entry)
        ins = {i["addr"]: i for i in self.region(entry)}
        allr = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "sl", "fp", "ip", "lr")
        start = {r: frozenset({("other",)}) for r in allr}
        start[file_reg] = frozenset({("file",)})
        at: dict[int, dict[str, frozenset]] = {}
        seen: set = set()
        work = [(entry, frozenset(), start)]
        while work:
            a, known, st = work.pop()
            if a not in ins:
                continue
            cur = at.get(a)
            at[a] = st if cur is None else {r: self._vjoin(cur[r], st[r]) for r in allr}
            key = (a, known, frozenset((r, st[r]) for r in allr))
            if key in seen:
                continue
            seen.add(key)
            if len(seen) > 300000:
                raise Finding(f"{self.name(entry)}: the value analysis did not converge")
            i = ins[a]
            b, condflag = base_mnem(i["mnem"])
            c = cond_of(i["mnem"]) if condflag else None
            nxt = a + i["size"]
            branches = [(True, known)] if c is None else self._decide(c, known)
            for executes, kn in branches:
                after = frozenset() if sets_flags(i) else kn
                if b in ("cbz", "cbnz") and branch_target(i["ops"]):  # register test: both ways, same decisions
                    work.append((branch_target(i["ops"])[0], after, dict(st)))
                    if nxt in ins:
                        work.append((nxt, after, dict(st)))
                    continue
                if b == "b" and branch_target(i["ops"]):
                    if executes:
                        work.append((branch_target(i["ops"])[0], after, dict(st)))
                    elif nxt in ins:
                        work.append((nxt, after, dict(st)))
                    continue
                out = self._value_step(entry, i, dict(st), BASE) if executes else dict(st)
                for t in succ.get(a, []):
                    if t in ins:
                        work.append((t, after, out))
        return {a: at.get(a, start) for a in ins}

    def _decide(self, cond: str, known: frozenset):
        if (cond, True) in known or (NEGATE[cond], False) in known:
            return [(True, known)]
        if (cond, False) in known or (NEGATE[cond], True) in known:
            return [(False, known)]
        return [(True, known | {(cond, True)}), (False, known | {(cond, False)})]

    def _vjoin(self, x: frozenset, y: frozenset) -> frozenset:
        u = x | y
        return frozenset({("other",)}) if len(u) > self.VALUE_CAP else u

    def _atom_of(self, i: dict, st: dict, BASE: int) -> frozenset | None:
        """The atom-set the instruction produces for its destination, or None when it is not a plain value-producing
        write this analysis models (the caller then makes the destination ('other',))."""
        o = i["ops"].replace(" ", "")
        fam = self._family(i)
        rs = self._regs(o)
        if fam in ("mov", "movs", "movw") and len(rs) == 1 and ",#" in o:
            return frozenset({("const", imm(o))})
        if fam == "mov" and len(rs) == 2 and "#" not in o:
            return st.get(rs[1], frozenset({("other",)}))
        if fam == "movt" and ",#" in o and len(rs) == 1:
            hi = imm(o)
            out = set()
            for atom in st.get(rs[0], frozenset({("other",)})):
                out.add(("const", (hi << 16) | atom[1]) if atom[0] == "const" else ("other",))
            return frozenset(out)
        if fam in ("ldr", "ldr.w") and re.fullmatch(r"\w+,\[(\w+),#" + str(BASE) + r"\]", o):
            rb = re.search(r"\[(\w+)", o).group(1)
            return frozenset({("buffer",)}) if st.get(rb) == frozenset({("file",)}) else frozenset({("other",)})
        return None

    def _value_step(self, entry: int, i: dict, st: dict, BASE: int) -> dict:
        """Apply one EXECUTED instruction to the value map (the caller has already decided it runs)."""
        o = i["ops"].replace(" ", "")
        fam = self._family(i)
        b, _ = base_mnem(i["mnem"])
        if fam.startswith(("str", "stm", "vst")) and "[" in o:
            m = re.search(r"\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
            if m and st.get(m.group(1)) == frozenset({("file",)}) and (int(m.group(2), 0) if m.group(2) else 0) == BASE:
                raise Finding(f"{self.name(entry)} at {i['addr']:#x} writes the FILE's buffer field before the NULL test")
        if b in ("bl", "blx"):
            for r in self.CALLER_SAVED:
                st[r] = frozenset({("other",)})
            return st
        produced = self._atom_of(i, st, BASE)
        dest = self._regs(o)[0] if self._regs(o) else None
        for r in self.written(i):
            if r in ("sp", "pc"):
                continue
            st[r] = produced if (produced is not None and r == dest) else frozenset({("other",)})
        return st

    def _buffer_null_gates(self, entry: int, site: int, BASE: int) -> dict:
        """The __smakebuf_r call at `site` in __swsetup_r runs only when the FILE's buffer is NULL: a branch whose
        ZERO outcome is required to reach the site tests a register whose value, by `_value_analysis`, is only the
        FILE's buffer field or nonzero constants — so the tested value being zero forces the buffer to be zero."""
        vals = self._value_analysis(entry, BASE)
        for i in self.region(entry):
            fam = self._family(i)
            if fam in ("cbz", "cbnz") and branch_target(i["ops"]):
                reg, zero_to = self._regs(i["ops"])[0], (branch_target(i["ops"])[0] if fam == "cbz" else i["addr"] + i["size"])
                branch, test = i, i
            elif fam == "cmp" and re.fullmatch(r"\w+,#0", i["ops"].replace(" ", "")):
                nxt = self.ins_at.get(i["addr"] + i["size"])
                c = nxt["mnem"].split(".")[0] if nxt else ""
                if c not in ("beq", "bne") or not branch_target(nxt["ops"]):
                    continue
                reg = self._regs(i["ops"])[0]
                zero_to = branch_target(nxt["ops"])[0] if c == "beq" else nxt["addr"] + nxt["size"]
                branch, test = nxt, i
            else:
                continue
            if self._reachable_without(entry, site, cut=(branch["addr"], zero_to)):
                continue                               # the site is reachable without the zero outcome: not its gate
            vset = vals.get(test["addr"], {}).get(reg, frozenset({("other",)}))
            if ("buffer",) not in vset or any(atom[0] != "buffer" and not (atom[0] == "const" and atom[1] != 0) for atom in vset):
                raise Finding(f"__swsetup_r: the value tested at {test['addr']:#x} gating __smakebuf_r is {sorted(vset)}, "
                              "not only the FILE's buffer or nonzero constants")
            return {"site": f"{site:#x}", "test": f"{test['addr']:#x}", "branch": f"{branch['addr']:#x}",
                    "tested": reg, "value": sorted(f"{atom[0]}:{atom[1]:#x}" if atom[0] == "const" else atom[0] for atom in vset)}
        raise Finding(f"__swsetup_r's call to __smakebuf_r at {site:#x} is not gated by a NULL test of the FILE's buffer")

    def _snbf_not_set(self, entry: int, at: int, reg: str, SNBF: int, FL: int) -> bool:
        """On every path to `at`, the __SNBF bit of `reg` is cleared, or equal to the FILE's own flags __SNBF bit —
        never newly set. Back through orr / bic / eor immediates (SNBF untouched → preserved; a bic that clears SNBF
        or an and whose immediate omits SNBF → cleared), sxt / copy, and a load of the flags halfword (then the bit
        is the FILE's own)."""
        for w in self.reaching_writers(entry, at, reg):
            if w is None:
                return False
            o = w["ops"].replace(" ", "")
            fam = self._family(w)
            rs = self._regs(o)
            if fam in ("ldrh", "ldrsh") and re.search(rf"\[(\w+),#{FL}\]$", o):
                continue                                             # the FILE's own flags: bit preserved
            if fam == "and" and "#" in o and not (imm(o) & SNBF):
                continue                                             # SNBF forced to 0
            if fam == "bic" and "#" in o and (imm(o) & SNBF):
                continue                                             # SNBF forced to 0
            if fam in ("mov",) and len(rs) == 2 and "#" in o and not (imm(o) & SNBF):
                continue                                             # a constant without SNBF
            if fam in ("orr", "bic", "eor") and "#" in o and not (imm(o) & SNBF) and len(rs) >= 2:
                if not self._snbf_not_set(entry, w["addr"], rs[1], SNBF, FL):
                    return False
                continue
            if fam in ("sxth", "sxtb", "uxth", "uxtb", "mov") and len(rs) == 2 and "#" not in o:
                if not self._snbf_not_set(entry, w["addr"], rs[1], SNBF, FL):
                    return False
                continue
            return False
        return True

    def newlib_rule(self) -> dict:
        """Verify the newlib bounded rule on THIS image (a Finding names the first fact that does not hold) and
        record every fact with its address. Computed once."""
        if self._newlib is not None:
            return self._newlib
        N = self.NEWLIB
        V, S = self._need("_vfiprintf_r", "__sbprintf")
        facts: dict = {}
        libc = self.archives.get("libc.a")
        if libc is None or libc.sha256 != N["libc_sha256"]:
            raise Finding(f"the linked libc.a is not the one the rule was verified for ({libc and libc.sha256})")
        hdr = Path(b2be.TC) / N["version_header"]
        if not hdr.is_file() or sha256_file(hdr) != N["version_header_sha256"]:
            raise Finding(f"{N['version_header']} is not newlib {N['version']}'s")
        for a in (V, S):
            if self.member_of(a) != f"libc.a({N['member']})":
                raise Finding(f"{self.name(a)} is not libc.a({N['member']})'s code (it is {self.member_of(a)})")
        lay = self.file_layout()
        if lay["size_flags"] != 2:
            raise Finding(f"FILE._flags is {lay['size_flags']} bytes, not a short")
        FL, BASE, SNBF, WANT, MASK = lay["off_flags"], lay["off_base"], lay["snbf"], lay["snbf"] | lay["swr"], lay["snbf"] | lay["swr"] | lay["srw"]
        facts["file_layout"] = lay
        self.analyse(V)
        self.analyse(S)
        # the two edges of the cycle, each the only one
        s_to_v = {(e["kind"], e["site"]): e for e in self.edges[S] if e["to"] == V}     # one per SITE (a site
        v_to_s = {(e["kind"], e["site"]): e for e in self.edges[V] if e["to"] == S}     # reached in several states
        if len(s_to_v) != 1 or next(iter(s_to_v))[0] != "call":                         # is one edge)
            raise Finding(f"__sbprintf reaches _vfiprintf_r at {sorted(s_to_v)}, not one call site")
        if len(v_to_s) != 1 or next(iter(v_to_s))[0] != "call":
            raise Finding(f"_vfiprintf_r reaches __sbprintf at {sorted(v_to_s)}, not one call site")
        s_to_v, v_to_s = list(s_to_v.values()), list(v_to_s.values())
        if self.direct_sites(S) != [(V, int(v_to_s[0]["site"], 16), "call")] or S in self.address_taken:
            raise Finding("__sbprintf has a caller other than the one call in _vfiprintf_r")
        C, G = int(s_to_v[0]["site"], 16), int(v_to_s[0]["site"], 16)
        # (1) the FILE passed is __sbprintf's own frame: r1 = sp at the call
        w = self._straight_back(S, C, "r1")
        if w is None or self._family(w) != "mov" or w["ops"].replace(" ", "") != "r1,sp":
            raise Finding(f"__sbprintf does not pass its own frame as the FILE at {C:#x}")
        fake = -self._one_offset(S, w["addr"])               # the fake FILE's address, as a slot below the entry SP
        facts["fake_file"] = {"pass": f"{w['addr']:#x}", "call": f"{C:#x}"}
        # (2) the fake's flags: the caller's flags with __SNBF cleared, the one store to that slot, before the call
        st = self._frame_stores(S, fake + FL, 2)
        if len(st) != 1 or self._family(st[0]) != "strh" or not self._dominates(S, st[0]["addr"], C):
            raise Finding(f"the fake FILE's flags are not written once (strh) before the call: {[x['addr'] for x in st]}")
        src = self._regs(st[0]["ops"].split("[")[0])[0]
        bic = self._straight_back(S, st[0]["addr"], src)
        if bic is None or self._family(bic) != "bic" or not (imm(bic["ops"]) & SNBF):
            raise Finding("the fake FILE's flags are not the caller's with __SNBF cleared")
        rs = self._regs(bic["ops"].replace(" ", ""))
        ld = self._straight_back(S, bic["addr"], rs[1] if len(rs) > 1 else rs[0])
        if ld is None or self._family(ld) not in ("ldrh", "ldrsh") or ld["ops"].replace(" ", "").split(",", 1)[1] != f"[r1,#{FL}]" \
                or self._straight_back(S, ld["addr"], "r1") is not None:
            raise Finding("the fake FILE's flags are not loaded from the caller's FILE (r1)")
        facts["fake_flags"] = {"load": f"{ld['addr']:#x}", "clear": f"{bic['addr']:#x}", "store": f"{st[0]['addr']:#x}"}
        # (3) the fake's buffer: a frame address (never NULL), the one store to that slot, before the call
        st = self._frame_stores(S, fake + BASE, 4)
        if len(st) != 1 or self._family(st[0]) != "str" or not self._dominates(S, st[0]["addr"], C):
            raise Finding(f"the fake FILE's buffer is not written once before the call: {[x['addr'] for x in st]}")
        src = self._regs(st[0]["ops"].split("[")[0])[0]
        frame = self.stack_pointers(S)
        if src not in frame.get(st[0]["addr"], frozenset()):
            raise Finding("the fake FILE's buffer is not an address in __sbprintf's frame")
        facts["fake_buffer"] = {"store": f"{st[0]['addr']:#x}", "frame_address_in": src}
        early = []
        for e in self.edges[S]:                               # a call before the hand-over may not write anything
            if e.get("site") and int(e["site"], 16) != C and self._reachable_without(S, int(e["site"], 16), stop=C):
                if e["kind"] != "call" or not self._pure(e["to"]):
                    raise Finding(f"__sbprintf calls {self.name(e['to']) if e['to'] else e['kind']} at {e['site']} before "
                                  "handing the fake FILE over, and that call may write memory")
                early.append(f"{self.name(e['to'])} at {e['site']} (no store in its closure)")
        facts["calls_before_the_hand_over"] = sorted(set(early))
        # (4) the guard in _vfiprintf_r: every instance of `cmp (flags & MASK), #WANT` followed by beq / bne, each
        # read from the incoming FILE's flags halfword; with ALL their "equal" outcomes cut, the call at G is unreachable
        guards, cuts = [], set()
        for i in self.region(V):
            o = i["ops"].replace(" ", "")
            if self._family(i) != "cmp" or not re.fullmatch(r"\w+,#" + str(WANT), o):
                continue
            nxt = self.ins_at.get(i["addr"] + i["size"])
            if not nxt or not branch_target(nxt["ops"]) or base_mnem(nxt["mnem"])[0] != "b":
                continue
            c = nxt["mnem"].split(".")[0]
            if c not in ("beq", "bne"):
                continue
            after = nxt["addr"] + nxt["size"]
            eq = (nxt["addr"], branch_target(nxt["ops"])[0]) if c == "beq" else (nxt["addr"], after)
            ands = self.reaching_writers(V, i["addr"], self._regs(o)[0])
            if not ands or any(a is None or self._family(a) != "and" or imm(a["ops"]) != MASK for a in ands):
                raise Finding(f"_vfiprintf_r: the compare at {i['addr']:#x} is not of (flags & (__SNBF|__SWR|__SRW)) on every path")
            files = []
            for andi in ands:
                rs = self._regs(andi["ops"].replace(" ", ""))
                files += self.flags_in_mask(V, andi["addr"], rs[1] if len(rs) > 1 else rs[0], MASK, FL)
            guards.append({"and": sorted({f"{a['addr']:#x}" for a in ands}), "cmp": f"{i['addr']:#x}",
                           "branch": f"{nxt['addr']:#x}", "equal_outcome": [f"{eq[0]:#x}", f"{eq[1]:#x}"], "file": sorted(set(files))})
            cuts.add(eq)
        if not guards or self._reachable_without(V, G, cut=cuts):
            raise Finding("no guard (flags & (__SNBF|__SWR|__SRW)) == (__SNBF|__SWR) keeps _vfiprintf_r's call to __sbprintf")
        facts["guard"] = {"instances": guards, "call": f"{G:#x}"}
        # (5) before the guard, only __smakebuf_r writes a FILE's flags halfword, and only when the buffer is NULL
        facts["before_the_guard"] = self._pre_guard(V, {int(g["cmp"], 16) for g in guards}, FL, BASE)
        self._newlib = {"rule": "newlib_bounded_sbprintf", "sbprintf_to_vfiprintf": f"{C:#x}", "vfiprintf_to_sbprintf": f"{G:#x}",
                        "max_activations": {"_vfiprintf_r": 2, "__sbprintf": 1}, "skipped_in_the_nested_activation": f"{G:#x}",
                        "facts": facts, "binding": {k: N[k] for k in ("version", "version_header_sha256", "libc_sha256", "member")},
                        "source": N["source"], "semantics": N["semantics"],
                        "statement": "a verified newlib semantic rule — the call graph does not prove itself bounded"}
        return self._newlib

    def flags_in_mask(self, V: int, at: int, reg: str, mask: int, FL: int) -> list[str]:
        """On EVERY path to `at`, the bits of `reg` in `mask` equal the incoming FILE's flags bits in `mask`. Walk
        back from each reaching writer through operations that provably preserve the masked bits: a halfword load of
        [FILE, #FL] (the flags themselves), a sign / zero extension (the flags are a short, below the mask), a copy,
        and an immediate orr / bic / eor whose set bits avoid the mask or an and whose immediate covers the mask.
        Returns, for the record, how each path reads the FILE (via `_incoming_r1` on the load's base); a Finding on
        any path that does not preserve the masked flags."""
        how: list[str] = []
        for w in self.reaching_writers(V, at, reg):
            if w is None:
                raise Finding(f"_vfiprintf_r: {reg} at {at:#x} is unwritten on some path, not the masked flags")
            o = w["ops"].replace(" ", "")
            fam = self._family(w)
            rs = self._regs(o)
            if fam in ("ldrh", "ldrsh") and o.split(",", 1)[1].endswith(f",#{FL}]") or (fam in ("ldrh", "ldrsh") and re.search(rf"\[(\w+),#{FL}\]$", o)):
                base = re.search(r"\[(\w+)", o).group(1)
                how.append(self._incoming_r1(V, w["addr"], base))
                continue
            if fam in ("sxth", "sxtb", "uxth", "uxtb") and len(rs) == 2:
                how += [self.flags_in_mask(V, w["addr"], rs[1], mask, FL)[0]]
                continue
            if fam == "mov" and len(rs) == 2 and "#" not in o:
                how += [self.flags_in_mask(V, w["addr"], rs[1], mask, FL)[0]]
                continue
            if fam in ("orr", "bic", "eor", "and") and len(rs) >= 2 and "#" in o:
                k = imm(o)
                ok = (k & mask) == 0 if fam in ("orr", "bic", "eor") else (k & mask) == mask
                if not ok:
                    raise Finding(f"_vfiprintf_r: {w['mnem']} {w['ops']} at {w['addr']:#x} changes the flags bits in the mask")
                how += [self.flags_in_mask(V, w["addr"], rs[1], mask, FL)[0]]
                continue
            raise Finding(f"_vfiprintf_r: {reg} at {at:#x} may come from {w['mnem']} {w['ops']} ({w['addr']:#x}), not the FILE's flags")
        return sorted(set(how)) or ["r1"]

    def _incoming_r1(self, V: int, at: int, reg: str) -> str:
        """`reg` at `at` holds _vfiprintf_r's incoming FILE (r1) on EVERY path: each reaching writer is a copy of the
        incoming r1, or a reload of the ONE frame slot that is stored from the incoming r1 and whose store dominates
        the reload; or no writer (reg is r1 itself, unwritten)."""
        how = []
        for w in self.reaching_writers(V, at, reg):
            if w is None:
                if reg != "r1":
                    raise Finding(f"_vfiprintf_r: {reg} at {at:#x} is an argument other than the FILE on some path")
                how.append("r1, unwritten")
                continue
            o = w["ops"].replace(" ", "")
            if self._family(w) == "mov" and o == f"{reg},r1" and self.reaching_writers(V, w["addr"], "r1") == [None]:
                how.append(f"a copy of the incoming r1 at {w['addr']:#x}")
                continue
            m = re.fullmatch(reg + r",\[sp(?:,#(\d+))?\]", o)
            if self._family(w) == "ldr" and m:
                slot = int(m.group(1) or 0) - self._one_offset(V, w["addr"])
                st = self._frame_stores(V, slot, 4)
                if len(st) != 1 or self._family(st[0]) != "str" or self._regs(st[0]["ops"].split("[")[0]) != ["r1"]:
                    raise Finding(f"_vfiprintf_r: the frame slot reloaded at {w['addr']:#x} is not stored once, from r1")
                if self.reaching_writers(V, st[0]["addr"], "r1") != [None] or not self._dominates(V, st[0]["addr"], w["addr"]):
                    raise Finding("_vfiprintf_r: the store of r1 to its frame slot is not of the incoming r1 before every reload")
                how.append(f"a reload ({w['addr']:#x}) of the frame slot the incoming r1 is stored to once ({st[0]['addr']:#x})")
                continue
            raise Finding(f"_vfiprintf_r: {reg} at {at:#x} may come from {w['addr']:#x}, not the incoming FILE")
        return "; ".join(sorted(set(how)))

    def _pre_guard(self, V: int, guard, FL: int, BASE: int, SNBF: int = 2) -> dict:
        """What the nested _vfiprintf_r can run BEFORE its guard must not SET __SNBF in the fake FILE, whose __SNBF
        __sbprintf has already cleared and whose buffer is non-NULL. So over the closure of every routine reachable
        from the entry before the guard (`guard`: the set of guard compares), every halfword store at the flags
        offset through a register other than sp either (a) is in __smakebuf_r — not address-taken, called only from
        __swsetup_r at sites a cbz on the (forwarded) FILE's NULL buffer keeps, so never for the fake — or (b)
        provably does not set __SNBF: its stored value's __SNBF bit is cleared, or preserved from the FILE's own
        flags by orr / bic / eor immediates that avoid __SNBF. No application pointer is called there."""
        before = set()
        for e in self.edges[V]:
            site = int(e["site"], 16) if e.get("site") else None
            if site is not None and self._reachable_without(V, site, stop=set(guard)):
                before |= set(self.targets(e) if e["kind"] != "indirect_call" or e["set"] != "app_function_pointers" else [])
        closure, todo = set(), list(before)
        while todo:
            a = todo.pop()
            if a in closure:
                continue
            closure.add(a)
            self.analyse(a)
            for e in self.edges[a]:
                if e["kind"] in ("indirect_call", "indirect_tail") and e["set"] == "app_function_pointers":
                    raise Finding(f"{self.name(a)}, before _vfiprintf_r's guard, calls an application pointer")
                todo += self.targets(e)
        smb = self.syms.get("__smakebuf_r", (None,))[0]
        writers, preserving = [], []
        for a in sorted(closure):
            for i in self.region(a):
                o = i["ops"].replace(" ", "")
                m = re.search(rf"\[(\w+),#{FL}\]", o)
                if self._family(i) != "strh" or not m or m.group(1) == "sp":
                    continue
                writers.append((a, i["addr"]))
                if a == smb:
                    continue
                src = self._regs(o.split("[")[0])[0]
                if not self._snbf_not_set(a, i["addr"], src, SNBF, FL):
                    raise Finding(f"{self.name(a)} at {i['addr']:#x} may set __SNBF in a FILE's flags before the guard")
                preserving.append((self.name(a), f"{i['addr']:#x}"))
        guarded = []
        if smb is not None and smb in closure:
            if smb in self.address_taken:
                raise Finding("__smakebuf_r is address-taken")
            sw = self.syms.get("__swsetup_r", (None,))[0]
            sites = self.direct_sites(smb)
            if not sites or any(o != sw for o, _s, _k in sites):
                raise Finding(f"__smakebuf_r is called from {[self.name(o) for o, _s, _k in sites]}, not __swsetup_r alone")
            for _o, site, _k in sites:
                guarded.append(self._buffer_null_gates(sw, site, BASE))
        return {"routines": sorted(self.name(a) for a in closure),
                "flag_stores": [f"{self.name(a)} {x:#x}" for a, x in writers],
                "stores_that_cannot_set_snbf": preserving,
                "smakebuf_only_when_the_buffer_is_null": guarded}

    # -- boot.S: the stack each mode gets, the calls made before any stack, the mode handed to _start
    def modes(self, memo: dict) -> dict:
        if "_boot" not in self.syms:
            raise Finding("no _boot")
        a = self.syms["_boot"][0]
        mode = None
        stacks: dict[str, int] = {}
        early_calls = []
        handoff = None
        steps = 0
        while a in self.ins_at and steps < 4096:
            i = self.ins_at[a]
            o = i["ops"].replace(" ", "")
            b, _ = base_mnem(i["mnem"])
            if i["mnem"].startswith("orr") and re.fullmatch(r"r\d+,r\d+,#\w+", o) and imm(o) in MODE_NAMES:
                mode = MODE_NAMES[imm(o)]
            elif i["mnem"] == "ldr" and o.startswith("sp,[pc,#"):
                val = self.words.get(a + 8 + imm(o))
                if val is None or mode is None:
                    raise Finding(f"_boot: a stack load at {a:#x} that cannot be resolved")
                stacks[mode] = val
            elif b == "bl" and branch_target(i["ops"]) and not stacks:
                tgt = branch_target(i["ops"])[0]
                early_calls.append({"to": self.name(tgt), "depth": self.depth(tgt, None, (), memo)})
            elif b == "b" and branch_target(i["ops"]) and branch_target(i["ops"])[1] == "_start":
                handoff = a
                break
            a += i["size"]
            steps += 1
        if handoff is None:
            raise Finding("_boot does not reach its branch to _start")
        for c in early_calls:
            if c["depth"] != 0:
                raise Finding(f"_boot calls {c['to']} before any stack is set, and it uses {c['depth']} bytes")
        return {"stacks": {m: f"{v:#x}" for m, v in stacks.items()}, "stack_values": stacks, "start_mode": mode,
                "handoff": f"{handoff:#x}", "calls_before_any_stack": early_calls}

    def cpsr_writes(self) -> list[dict]:
        """Every msr to the CPSR, classified by the dataflow just before it: which of I (0x80), F (0x40) and A
        (0x100) it can CLEAR. Patterns: mrs rX → [and/bic/orr …] → msr; a restore of a value an earlier mrs saved."""
        out = []
        for name, ins in self.funcs.items():
            saved: dict[str, int] = {}
            for k, i in enumerate(ins):
                o = i["ops"].replace(" ", "")
                if i["mnem"] == "mrs" and o.endswith(",CPSR"):
                    saved[o.split(",")[0]] = k
                if not (i["mnem"].startswith("msr") and o.startswith("CPSR")):
                    continue
                reg = o.split(",")[1]
                back = ins[max(0, k - 6):k]
                text = [f"{w['mnem']} {w['ops']}" for w in back]
                clears = None
                ops = [(w["mnem"], w["ops"].replace(" ", "")) for w in back]
                srcs = [x for x in ops if x[1].startswith(reg + ",")]
                if srcs and srcs[-1][0] == "mrs":
                    clears = 0
                elif srcs and srcs[-1][0] == "bic":
                    clears = imm(srcs[-1][1]) & 0x1C0
                elif srcs and srcs[-1][0] == "orr":
                    chain = srcs[-1][1].split(",")
                    src = chain[1]
                    prior = [x for x in ops if x[1].startswith(src + ",")]
                    if prior and prior[-1][0] == "and" and "r1" in prior[-1][1]:
                        clears = 0                       # and with mvn #31: only the mode bits are cleared, then set
                    elif prior and prior[-1][0] == "mrs" or src == reg:
                        clears = 0
                elif reg in saved and not srcs:
                    clears = 0                           # the restore of a value read by mrs on entry
                out.append({"function": name, "addr": f"{i['addr']:#x}", "insn": f"{i['mnem']} {i['ops']}",
                            "before": text, "clears_IFA_mask": None if clears is None else clears})
        return out

    def vector_entries(self) -> dict[str, tuple[int, str]]:
        if VECTOR_TABLE not in self.syms:
            raise Finding("no _vector_table")
        base = self.syms[VECTOR_TABLE][0]
        out = {}
        for off, (exc, mode) in VECTOR_SLOTS.items():
            i = self.ins_at.get(base + off)
            if i is None or base_mnem(i["mnem"])[0] != "b" or not branch_target(i["ops"]):
                raise Finding(f"_vector_table+{off:#x} ({exc}) is not a branch")
            out[exc] = (branch_target(i["ops"])[0], mode)
        nop = self.ins_at.get(base + 0x14)
        out["_reserved_0x14"] = None if nop and nop["mnem"] == "nop" else ("not a nop", "")
        return out


_ASSESS_CACHE: dict = {}


def assess(elf: Path = ELF_DEFAULT) -> dict:
    """The whole assessment: per entry its bound and its mode's stack, the frames, the edges, the indirect target
    sets, the CPSR writes, and every unresolved finding. `ok` only when there is no finding."""
    findings: list[str] = []
    elf = Path(elf)
    ck = sha256_file(elf) if elf.is_file() else None   # keyed by content: a byte-identical ELF is the same analysis
    if ck is not None and ck in _ASSESS_CACHE:
        return _ASSESS_CACHE[ck]
    img = Image(elf)
    memo: dict = {}
    result = {"tool": TOOL_VERSION,
              "objdump": subprocess.run([tool("objdump"), "--version"], capture_output=True, text=True).stdout.splitlines()[0],
              "elf": {"path": str(elf.relative_to(REPO_ROOT)) if elf.is_relative_to(REPO_ROOT) else str(elf), "sha256": sha256_file(elf)},
              "indirect_targets": {"address_taken": [img.name(a) for a in img.address_taken],
                                   "exception_table": [img.name(a) for a in img.exc_targets]}}
    capacity = {}
    for mode, (top, bottom) in STACK_TOPS.items():
        if top in img.syms and bottom in img.syms:
            capacity[mode] = img.syms[top][0] - img.syms[bottom][0]
        else:
            findings.append(f"the {mode} stack's symbols {top} / {bottom} are absent")
    try:
        modes = img.modes(memo)
    except Finding as e:
        findings.append(str(e))
        modes = {"stacks": {}, "stack_values": {}, "start_mode": None}
    for mode, (top, _bottom) in STACK_TOPS.items():
        val = modes["stack_values"].get(mode)
        if val is None:
            findings.append(f"boot gives the {mode} mode no stack")
        elif top not in img.syms or img.syms[top][0] != val:
            findings.append(f"boot gives {mode} the stack {val:#x}, not {top}")
    if modes.get("start_mode") != "SYS":
        findings.append(f"_start is entered in {modes.get('start_mode')}, not SYS")
    entries: dict[str, tuple[int, str]] = {}
    if "_start" in img.syms:
        entries["main"] = (img.syms["_start"][0], "SYS")
    else:
        findings.append("no _start")
    try:
        for exc, v in img.vector_entries().items():
            if exc == "_reserved_0x14":
                if v is not None:
                    findings.append("_vector_table+0x14 is not the reserved nop")
                continue
            entries[exc] = v
    except Finding as e:
        findings.append(str(e))
    bounds = {}
    for entry, (addr, mode) in entries.items():
        try:
            d = img.depth(addr, None, (), memo)
            bounds[entry] = {"function": img.name(addr), "mode": mode, "bound": d, "capacity": capacity.get(mode)}
            limit = MAIN_LIMIT if entry == "main" else capacity.get(mode)
            if limit is None or d > limit:
                findings.append(f"{entry} ({img.name(addr)}): bound {d} exceeds {limit}")
        except Finding as e:
            findings.append(f"{entry} ({img.name(addr)}): {e}")
            bounds[entry] = {"function": img.name(addr), "mode": mode, "bound": None, "capacity": capacity.get(mode)}
    for r in img.resets:
        if not (r["routine"] == "_start" and r["to"] == "__stack"):
            findings.append(f"an absolute stack load outside crt0's reset of the main stack: {r}")
    named = {}
    for fn in NAMED_CHAINS:                               # the stage-4 stack exceptions, now from the linked image
        copies = sorted(n for n in img.syms if (n == fn or n.startswith(fn + ".")) and (img.syms[n][0] & ~1) in img.func_entries)
        if not copies:
            findings.append(f"{fn} is not a routine of the image")
            continue
        for n in copies:
            try:
                a = img.syms[n][0] & ~1
                named[n] = {"chain": img.depth(a, None, (), memo), "local": img.local[a]}
            except Finding as e:
                findings.append(f"{n}: {e}")
    cpsr = img.cpsr_writes()
    for w in cpsr:
        if w["clears_IFA_mask"] is None:
            findings.append(f"a CPSR write whose value cannot be classified: {w['function']} {w['addr']} {w['insn']}")
    cleared = 0
    for w in cpsr:
        cleared |= w["clears_IFA_mask"] or 0
    result.update({"modes": {k: v for k, v in modes.items() if k != "stack_values"}, "capacity": capacity, "entries": bounds,
                   "stack_resets": img.resets,
                   "frames": {img.name(a): img.local[a] for a in sorted(img.local)},
                   "edges": {img.name(a): [dict(e, to=img.name(e["to"]) if e["to"] is not None else None) for e in img.edges[a]]
                             for a in sorted(img.edges)},
                   "cpsr_writes": cpsr,
                   "masks": {"cleared_by_the_image": [n for n, m in (("I", 0x80), ("F", 0x40), ("A", 0x100)) if cleared & m],
                             "note": "a bit the image never clears keeps the state the loader entered it with"},
                   "named_chains": named,
                   "rules": {n: {"rule": r["rule"], "targets": [img.name(t) for t in r["targets"]]} for n, r in sorted(img.site_rules.items())},
                   "application_pointers": img.produced,
                   "newlib": img._newlib,
                   "main_limit": MAIN_LIMIT,
                   "findings": findings, "ok": not findings})
    _ASSESS_CACHE[ck] = result
    return result


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--elf", type=Path, default=ELF_DEFAULT)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    r = assess(a.elf)
    if a.json:
        print(json.dumps(r, indent=1, sort_keys=True))
    else:
        for e, v in r["entries"].items():
            print(f"{e:16} {v['function']:24} {v['mode']}  bound {v['bound']}  capacity {v['capacity']}")
        for f in r["findings"]:
            print("FINDING", f)
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
