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
import copy
import functools
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

TOOL_VERSION = "b3-image-stack 1.7.0"
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


# the value analysis recurses along a routine's chain of calls and slots (each depends on the ones before it); the
# chain is finite — a cycle is cut and iterated by the solver — but far deeper than Python's default allowance
sys.setrecursionlimit(max(sys.getrecursionlimit(), 400_000))


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


@functools.lru_cache(maxsize=None)
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
    full = ins["mnem"].split(".")[0]
    # the mnemonic as written AND with a trailing condition taken off: `lsls`, `movs`, `bics`, `adcs`, `muls` END in
    # the letters of a condition (ls, vs, cs) and are flag-setting operations, not `lsl` + ls — reading them as
    # conditional non-setters made every later conditional instruction follow a stale decision and whole paths
    # (their calls with them) were never walked. Either reading that sets flags counts.
    for m in {full, re.sub(COND + "$", "", full)}:
        if m.startswith(("cmp", "cmn", "tst", "teq")):
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
        self._pt_eval_memo: dict = {}
        self._rsucc_cache: dict = {}
        self._rw_cache: dict = {}
        self._rpred_cache: dict = {}
        self._aw_memo: dict = {}

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
        """The core registers the instruction may write. A call: the caller-saved registers its target may write
        (`_clobbers`) and lr; an indirect call, or a target the image does not hold: all the caller-saved ones."""
        fam = self._family(i)
        o = i["ops"].replace(" ", "")
        b, _ = base_mnem(i["mnem"])
        out: set[str] = set()
        if b in ("bl", "blx"):
            bt = branch_target(i["ops"])
            return (set(self._clobbers(bt[0])) | {"lr"}) if bt else set(self.CALLER_SAVED)
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

    def _clobbers(self, callee: int) -> frozenset:
        """The caller-saved registers (r0–r3, ip, lr) the routine at `callee` — with everything it calls or
        branches to — may write, read off ALL its instructions (no path analysis: a superset). GCC's inter-
        procedural register allocation relies on exactly this to keep a value in r2 across a call to a routine
        that never writes r2. An indirect call or tail, a write to pc the model does not follow, a routine the image
        does not hold, or a cycle back here (the placeholder): all of them. The callee-saved registers are taken to
        be preserved (the AAPCS), as everywhere in this analysis."""
        if callee not in self.ins_at or callee not in self.func_entries:
            return self.CALLER_SAVED
        return self._guarded("clobbers", callee, self._clobbers_compute, frozenset())

    def _clobbers_compute(self, callee: int) -> frozenset:
        out: set = set()
        region = self.region(callee)
        for k, i in enumerate(region):
            if i["mnem"] == ".data":
                continue
            b = base_mnem(i["mnem"])[0]
            o = i["ops"].replace(" ", "")
            bt = branch_target(i["ops"]) if b in ("b", "bl", "blx", "cbz", "cbnz") else None
            if b in ("bl", "blx"):
                out |= set(self._clobbers(bt[0])) | {"lr"} if bt else set(self.CALLER_SAVED)
            elif b == "bx" and o != "lr":
                return self.CALLER_SAVED                   # an indirect tail
            elif bt and bt[0] != callee and bt[0] in self.func_entries and not (callee <= bt[0] < region[-1]["addr"] + 4):
                out |= set(self._clobbers(bt[0]))          # a tail branch to another routine
            elif o.startswith("pc,") or (b in ("ldm", "ldmia", "ldmfd", "pop") and "pc" in o and b not in ("pop", "ldmia", "ldmfd")):
                return self.CALLER_SAVED
            else:
                out |= self.written(i)
            if k == len(region) - 1 and not (b == "bx" or (b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in o) or (b == "b" and bt)):
                nxt = i["addr"] + i["size"]                # it may fall through into the next routine
                if nxt in self.func_entries:
                    out |= set(self._clobbers(nxt))
                else:
                    return self.CALLER_SAVED
        return frozenset(out & self.CALLER_SAVED)

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
                if not self._cond(i):
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
        tables = self._ro_tables()
        in_table = lambda a: any(v <= a < v + s for v, (_n, s) in tables.items())
        for a, w in self.words.items():
            if (w & ~1) in made and not in_table(a):
                raise Finding(f"the application pointer {self.name(w & ~1)} is also a literal word at {a:#x}")
        for v, (tname, s) in tables.items():               # a read-only table's callbacks are produced by the table
            for k in range(0, s - 3, 4):
                w = self.words.get(v + k) or 0
                if (w & ~1) in self.label_at and self.unit_of(w & ~1) in self.APP_UNITS:
                    prod.setdefault(v, set()).add(w & ~1)
                    records.append({"routine": tname, "at": f"{v + k:#x}", "pointer": self.name(w & ~1)})
        made = set().union(*prod.values()) if prod else set()
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

    # ---- per-call-site, per-field points-to for application callbacks (the owner's ruling of 2026-10-04, option 1;
    # made flow-sensitive on the owner's HOLD of 2026-10-05)
    #
    # An OBJECT is a struct built in a routine's own stack frame, named (routine, A) where A is its base as a byte
    # offset relative to the routine's ENTRY stack pointer (A = immediate - the SP offset there, as `_frame_stores`
    # counts). A routine fills an object's fields by storing callbacks at frame slots and hands &object to a consumer
    # as an argument; the consumer calls `blx [objptr, #off]`. So each indirect call resolves to what the building
    # routine's slot A + off holds AT THE CALL THAT HANDS THE OBJECT OVER (`_field_callbacks`, `_slot_atoms`) — not
    # the union of every active pointer, and not everything the routine ever stored there. The object binding
    # (with its hand-over site) travels in the depth context, so the SAME consumer called with different objects is
    # analysed and memoised apart. An unknown pointer source, a store the analysis cannot read, a slot that is not
    # provably initialised on every path, a partial / conditional / aliased / callee write to it, or a field with no
    # callback is a Finding; several callbacks reaching one slot are ALL kept.
    APP_UNITS = tuple(APP_DIR + u for u in ("b3_app.c", "p3_pull.c", "p3_rectx.c", "b3_wire.c", "b3_carto.c", "b3_record.c"))

    def _pointsto(self, entry: int) -> dict:
        """For one routine of the image's own units: `reads` {indirect-call site -> what it targets (`_pt_read`, or
        the Finding it raised — surfaced only if the call is on a counted path)} and `needs`, the incoming arguments
        (0–3, or ('stk', A)) whose binding the routine uses: one it calls, one whose field it calls, or one it hands
        on in a direct call's argument register or outgoing stack word."""
        if entry in self._pt_cache:
            return self._pt_cache[entry]
        if (self.unit_of(entry) or "") not in self.APP_UNITS:
            # application callback objects are built, passed and dereferenced only in the image's own units; a
            # library routine neither builds nor forwards one (escapes() forbids an app pointer leaving the units),
            # so its points-to is empty — and a binding that fails to reach a consumer is then a Finding, not a guess
            self._pt_cache[entry] = {"reads": {}, "needs": frozenset()}
            return self._pt_cache[entry]
        self.analyse(entry)
        reads = {}
        for e in self.edges[entry]:
            if e["kind"] in ("indirect_call", "indirect_tail") and e.get("set") == "app_function_pointers":
                site = int(e["site"], 16)
                rT = self._regs(self.ins_at[site]["ops"])[0]
                try:
                    reads[site] = self._pt_read(entry, site, rT)
                except Finding as exc:
                    reads[site] = exc                      # surfaced only if this call is actually on a counted path
        needs = set()
        for v in reads.values():
            if isinstance(v, Finding):
                continue
            needs |= {x[1] for x in v[1] if x[0] == "arg"} if v[0] == "VAL" else {v[0]}
        reached = self.sp_at.get(entry, {})
        for i in self.region(entry):
            a = i["addr"]
            tgt = self._call_target(i)
            b = base_mnem(i["mnem"])[0]
            if a not in reached or tgt is None or not (b in ("bl", "blx") or (tgt != entry and tgt in self.func_entries)):
                continue
            for n in self._handed_regs(entry, a):          # (the registers the call hands, as `_handed` sees them)
                needs |= {x[1] for x in self._pt_eval(entry, a, f"r{n}") if x[0] == "arg"}
            sp = self._pt_slot(entry, a, 0)
            if sp is not None:                             # its outgoing stack words the callee reads (all, if unpinned)
                sreads = self._stack_use_at(entry, a)[0]
                for A in (range(sp, 0, 4) if sreads is None else [sp + k for k in sorted(sreads) if sp + k < 0]):
                    needs |= {x[1] for x in self._slot_atoms(entry, a, A) if x[0] == "arg"}
        self._pt_cache[entry] = {"reads": reads, "needs": frozenset(needs)}
        return self._pt_cache[entry]

    def _pt_slot(self, entry: int, addr: int, imm: int) -> int | None:
        offs = self.sp_at[entry].get(addr, frozenset())
        return (imm - next(iter(offs))) if len(offs) == 1 else None

    ARGREG = {"r0": 0, "r1": 1, "r2": 2, "r3": 3}

    # ---- what a register / a frame slot holds AT A POINT (the owner's HOLD on 94073b3)
    #
    # One mutually recursive MAY analysis over the routine's over-approximate CFG, solved to a FIXPOINT (a cycle is
    # iterated until nothing changes — never cut to "nothing", never memoised half-done):
    #
    #   reg(entry, at, r)     the atoms r may hold just before `at`: the union over its REACHING writers (a
    #                         conditional writer both writes and does not);
    #   slot(entry, at, A)    the atoms the 4-byte word at frame slot A (relative to the entry SP) may hold just
    #                         before `at`: walking back from `at`, the last store on EACH path — so the value is the
    #                         one at the read or hand-over, not "whatever the routine ever stored there".
    #
    # An atom is ('cb', addr) an application callback, ('arg', n) the routine's incoming argument n (('stk', A): its
    # stack word A), ('argo', n, k) argument n plus the constant k, ('frame', A) the address of its own frame slot
    # A, ('const', k), ('crange', lo, hi) one of the constants in [lo, hi] (a stepped constant address, widened on
    # the side it grows, wrapping to everything past either end), ('tab', T, k) the address T + k inside the read-
    # only callback table T (by provenance: born where T's address is materialised), ('ind', n, k) the word loaded
    # from argument n + k, ('other',) an unknown value, or ('der', x) an unknown value DERIVED from x — 'frame',
    # ('arg', n) or ('ind', n, k) — by arithmetic the model does not follow (so a store through it may still write
    # the frame / that object). More than WIDEN addresses of one kind widen to the derived unknown.
    #
    # A store is described by the BYTES it writes (`_store_desc`): its base's atoms, each element's offset and
    # width, whether it is conditional. For the word at slot A a store is
    #   exact      one unconditional word element landing on exactly [A, A+4): the definition on that path;
    #   exact, conditional   the same under a condition: its value AND whatever was there before;
    #   may        anything else that can touch any of the four bytes — a byte / halfword / vector store, a word
    #              that overlaps without coinciding, a register-indexed or frame-derived base, an ambiguous SP: the
    #              slot is then UNKNOWN on that path (and still what was there before, if it did not run);
    #   none       a store that provably writes other bytes, or through a base that is not this frame.
    # A call between the store and the read may write the slot when a pointer it is handed can reach the slot and
    # the callee's summary (below) says it may write there, write through a frame address it loads from the object,
    # or keep the pointer. A path that reaches the entry with no store leaves a local slot UNKNOWN (uninitialised).
    # What is stated rather than proved is VALUE_MODEL's (B1)–(B3).

    _solving = None
    PURE_UNARY = frozenset("mov movs mvn mvns movw clz rbit rev rev16 uxtb uxth sxtb sxth neg negs adr".split())
    STORE_BYTES = {"strb": 1, "strh": 2, "str": 4, "strd": 8, "strex": 4, "strexb": 1, "strexh": 2}

    def _cache(self, name: str) -> dict:
        return self.__dict__.setdefault(name, {})

    def _cond(self, i: dict) -> bool:
        """Whether the instruction executes under a condition (any family — `strbne`, `strdeq`, `orrne`, …)."""
        f = i["mnem"].split(".")[0]
        if f in self.KNOWN or f.startswith("it"):
            return False
        return bool(re.search(COND + "$", f)) and f[:-2] in self.KNOWN

    def _rpred(self, entry: int) -> dict[int, list[int]]:
        c = self._cache("_rpred_cache")
        if entry not in c:
            pred: dict[int, list[int]] = {}
            for a, ts in self._region_succ(entry).items():
                for t in ts:
                    pred.setdefault(t, []).append(a)
            c[entry] = pred
        return c[entry]

    def _solve(self, key: tuple) -> frozenset:
        memo = self._pt_eval_memo
        if key in memo:
            return memo[key]
        if self._solving is not None:
            return self._solve_inner(key)
        prev: dict = {}
        stage = self.__dict__.setdefault("_blk_stage", [])  # what the rounds record against cells: kept only from
        for _round in range(200):                          # the round that converged (a provisional round reads
            cur: dict = {}                                 # provisional values — its reasons are not the cell's)
            self._solving = (prev, cur, set())
            stage.append([])
            try:
                v = self._solve_inner(key)
            finally:
                self._solving = None
                staged = stage.pop()
            if cur == prev:
                memo.update(cur)                           # (final, like the values: a nested solve's keys are not
                self._blocked_commit(staged)               # computed again by the round that asked for them)
                return v
            prev = cur
        raise Finding(f"{self.name(key[1])}: the value analysis at {key[2]:#x} did not reach a fixpoint")

    def _solve_inner(self, key: tuple) -> frozenset:
        prev, cur, active = self._solving
        if key in self._pt_eval_memo:
            return self._pt_eval_memo[key]
        if key in cur:
            return cur[key]
        if key in active:
            return prev.get(key, frozenset())              # a cycle: the previous round's value, until none changes
        active.add(key)
        try:
            v = self._widen(self._reg_compute(*key[1:]) if key[0] == "reg" else self._slot_compute(*key[1:]))
        finally:
            active.discard(key)
        before = [x for x in prev.get(key, ()) if x[0] == "crange"]
        if before:                                         # an interval that grew since the previous round grows to
            b = before[0]                                  # the end of the address space on that side, and never
            v = frozenset({x if x[0] != "crange" else ("crange", 0 if x[1] < b[1] else b[1],      # shrinks: it settles
                                                       0xFFFFFFFF if x[2] > b[2] else b[2]) for x in v})
        cur[key] = v
        return v

    WIDEN = 8

    def _widen(self, v: set) -> frozenset:
        """Keep a value finite: more than WIDEN addresses of one kind become the derived unknown, and a derived
        unknown ABSORBS the specific addresses it covers (so a pointer stepped round a loop settles)."""
        v = set(v)
        for kind in ("frame", "argo"):
            many = {x for x in v if x[0] == kind}
            if len(many) > self.WIDEN:
                v = (v - many) | {("other",)} | self._derived(many)
        consts = {x for x in v if x[0] in ("const", "crange")}   # too many constants (a stepped address): their
        if len(consts) > self.WIDEN or any(x[0] == "crange" for x in consts):   # interval, which absorbs them all
            lo = min(x[1] for x in consts)
            hi = max(x[1] if x[0] == "const" else x[2] for x in consts)
            v = (v - consts) | {("crange", lo, hi)}
        many = {x for x in v if x[0] == "ind"}
        if len(many) > self.WIDEN:
            v = (v - many) | {("ind", x[1], None) for x in many}
        many = {x for x in v if x[0] == "tab"}
        if len(many) > self.WIDEN:
            v = (v - many) | {("tab", x[1], None) for x in many}
        ders = {x[1] for x in v if x[0] == "der"}
        return frozenset(x for x in v if not ((x[0] == "frame" and "frame" in ders)
                                              or (x[0] == "argo" and ("arg", x[1]) in ders)))

    # ---- facts that depend on themselves through other routines (a routine's frame, the callbacks it hands on,
    # their summaries, its frame again): SPECULATE AND VERIFY. A fact asked while it is being computed answers its
    # GUESS — on the first pass the placeholder its caller names, afterwards the value the previous pass computed
    # for it — and the read is recorded. Everything is memoised in one pass. When the pass is over, every recorded
    # read is compared with the fact's final value: if any differs, the pass is thrown away and the next starts with
    # those final values as the guesses (`settle`). A result is accepted only from a pass in which every guess was
    # what was then computed. Every placeholder is the fact's OPTIMISTIC end — no leak, no pointer slot, no register
    # clobbered, nothing written, no target reached, a proof that holds — so the passes settle on the greatest self-
    # consistent answer, which is sound by induction over the execution: computed on the assumption that nothing
    # has leaked or been overwritten YET, every fact confirms it, so the first leak or overwrite would have to come
    # from an instruction the analysis checked with values that were still valid — a contradiction.

    def _guess(self, k, default):
        return self.__dict__.get("_guesses", {}).get(k, default)

    def _guarded(self, kind: str, key, compute, placeholder):
        memo = self._cache("_memo_" + kind)
        if key in memo:
            return memo[key]
        active = self._cache("_active")
        k = (kind, key)
        if k in active:
            g = self._guess(k, placeholder)
            self._cache("_spec").setdefault(k, []).append(g)
            return g
        active[k] = True
        try:
            v = self._isolated(compute, *(key if isinstance(key, tuple) else (key,)))
        finally:
            del active[k]
        memo[key] = v
        return v

    TOP = "TOP"

    def _fixed(self, kind: str, key, compute, bottom):
        """`_guarded` for a least fixpoint (routines that call each other summarise each other): the fact's own
        re-entrant reads are iterated to agreement (from its guess, or `bottom`); no agreement in 64 rounds: TOP."""
        memo = self._cache("_memo_" + kind)
        if key in memo:
            return memo[key]
        active, it = self._cache("_active"), self._cache("_iterate")
        k = (kind, key)
        if k in active:
            g = it.get(k, self._guess(k, bottom))
            self._cache("_spec").setdefault(k, []).append(g)
            return g
        spec = self._cache("_spec")
        for rounds in range(65):
            before = len(spec.get(k, ()))
            active[k] = True
            try:
                v = self._isolated(compute, key) if rounds < 64 else self.TOP
            finally:
                del active[k]
            read = spec.get(k, [])[before:]
            if not read or all(r == v for r in read):
                break
            it[k] = v
        it.pop(k, None)
        memo[key] = v
        return v

    def _speculation_failed(self) -> dict:
        """The facts read, while they were being computed, as a value other than their final one: {fact: final}. A
        pass that returns normally has finished every fact it read, so every read is checked; one that ends in a
        Finding is checked on the facts it finished."""
        out = {}
        for k, reads in self._cache("_spec").items():
            memo = self._cache("_memo_" + k[0])
            if k[1] not in memo:                           # never finished (a Finding ended the pass): its reads
                continue                                   # cannot be checked — a refusal is fail-closed anyway
            if any(r != memo[k[1]] for r in reads):
                out[k] = memo[k[1]]
        return out

    def _isolated(self, fn, *args):
        """Run a query about ANOTHER routine (or a whole-routine summary) outside the round in progress, so that it
        is solved to its own fixpoint and what it memoises is final."""
        saved, self._solving = self._solving, None
        try:
            return fn(*args)
        finally:
            self._solving = saved

    def _raw_reg(self, entry: int, at: int, reg: str) -> frozenset:
        if entry not in self.sp_at:
            self.analyse(entry)
        return self._solve(("reg", entry, at, reg))

    def _raw_slot(self, entry: int, at: int, slot: int) -> frozenset:
        return self._solve(("slot", entry, at, slot))

    @staticmethod
    def _settled(v) -> set:
        """A solved value for a consumer: a derived unknown (or an offset argument) is an unknown; no reaching value
        at all is an unknown."""
        return {a if a[0] not in ("der", "argo", "ind", "crange") and not (a[0] == "tab" and a[2] is None) else ("other",)
                for a in v} or {("other",)}

    def _pt_eval(self, entry: int, at: int, reg: str) -> set:
        """`reg`'s atoms just before `at`, from its reaching definitions (see the block comment above)."""
        return self._settled(self._raw_reg(entry, at, reg))

    def _slot_atoms(self, entry: int, at: int, slot: int) -> set:
        """The atoms the word at frame slot `slot` may hold just before `at`. Anything but callbacks / arguments in
        it (an ('other',)) means: uninitialised on a path, partially written, overwritten, or possibly written by a
        callee — the caller refuses."""
        return self._settled(self._raw_slot(entry, at, slot))

    @staticmethod
    def _derived(atoms) -> set:
        out = set()
        for a in atoms:
            if a[0] == "frame" or a == ("der", "frame"):
                out.add(("der", "frame"))
            elif a[0] == "arg":
                out.add(("der", a))
            elif a[0] == "argo":
                out.add(("der", ("arg", a[1])))
            elif a[0] == "der":
                out.add(a)
            elif a[0] == "ind":                            # a loaded pointer with arithmetic on it: anywhere from it
                out.add(("der", ("ind", a[1], a[2])))
            elif a[0] == "tab":                            # into the table, somewhere
                out.add(("tab", a[1], None))
        return out

    def _const_atom(self, v: int) -> tuple:
        """A materialised constant: ('tab', T, offset) when it is an address inside a read-only callback table T (its
        provenance is the table: arithmetic keeps it), else ('const', v)."""
        T = self._ro_table_of(v)
        return ("tab", T, v - T) if T is not None else ("const", v)

    def _shift(self, atoms, k: int) -> set:
        """The atoms of (a value with `atoms`) + k."""
        out = set()
        for x in atoms:
            if x[0] == "frame":
                out.add(("frame", x[1] + k if x[1] is not None else None))
            elif x[0] in ("arg", "argo"):
                kk = k + (x[2] if x[0] == "argo" else 0)
                out.add(("argo", x[1], kk) if kk else ("arg", x[1]))
            elif x[0] == "const":
                out.add(("const", (x[1] + k) & 0xFFFFFFFF))
            elif x[0] == "tab":
                out.add(("tab", x[1], None if x[2] is None else x[2] + k))
            elif x[0] == "crange":                         # (32-bit: an interval pushed past either end wraps,
                lo, hi = x[1] + k, x[2] + k                # so it is then every address)
                out.add(("crange", lo, hi) if 0 <= lo and hi <= 0xFFFFFFFF else ("crange", 0, 0xFFFFFFFF))
            else:
                out |= self._derived({x}) or {("other",)}
        return out

    def _readable(self, addr: int | None) -> bool:
        """The routine's instructions are in the image, so what it does with a pointer can be read off them —
        whether it was compiled from the image's sources or linked from a prebuilt archive."""
        return addr is not None and addr in self.ins_at and addr in self.func_entries

    # What a prebuilt C-library routine does with the pointers it is handed — the C standard's contract for the
    # routine, bound to the libc member that IS the image's code (`member_of`), not derived from the image:
    # name -> (member, the argument it writes through or None, the argument holding the byte count it writes at
    # most, what it returns: 'arg0' its first argument, 'in0' a pointer into its first argument's object, None a
    # number, and — for a printf-family routine — the argument that is its FORMAT). None of them keeps a pointer or
    # writes through a pointer it finds in memory; all but the printf family take register arguments only. A printf
    # format can write through ANY later argument with %n (newlib implements it), so the contract of snprintf /
    # vsnprintf holds only where `_printf_safe` proves the actual format has none; elsewhere the call is taken to
    # write through every pointer it can see.
    LIBC_CONTRACTS = {
        "memset": ("libc_a-memset.o", 0, 2, "arg0"), "memcpy": ("libc_a-memcpy.o", 0, 2, "arg0"),
        "memmove": ("libc_a-memmove.o", 0, 2, "arg0"), "strncpy": ("libc_a-strncpy.o", 0, 2, "arg0"),
        "snprintf": ("libc_a-snprintf.o", 0, 1, None, 2), "vsnprintf": ("libc_a-vsnprintf.o", 0, 1, None, 2),
        "strlen": ("libc_a-strlen.o", None, None, None), "strcmp": ("libc_a-strcmp.o", None, None, None),
        "memcmp": ("libc_a-memcmp.o", None, None, None), "strstr": ("libc_a-strstr.o", None, None, "in0"),
        "strchr": ("libc_a-strchr.o", None, None, "in0"), "strrchr": ("libc_a-strrchr.o", None, None, "in0"),
    }
    LIBC_CONTRACTS = {k: (v + (None,))[:5] for k, v in LIBC_CONTRACTS.items()}

    # (the owner's ruling of 2026-10-08 on the arity unit) The register arguments each of them takes — its C
    # prototype: a call hands only those (`_handed_regs`), and only while the member's OWN code shows that it uses no
    # register at or above that number on entry (`_libc_arity`); else all four. snprintf names three and takes the
    # rest variadic: which registers and incoming stack words those occupy follows from each proved format by the
    # AAPCS (`_printf_layout`). vsnprintf's fourth is its va_list, a pointer it reads like any other.
    LIBC_ARITY = {"memset": 3, "memcpy": 3, "memmove": 3, "strncpy": 3, "memcmp": 3, "strlen": 1, "strcmp": 2,
                  "strstr": 2, "strchr": 2, "strrchr": 2, "snprintf": 3, "vsnprintf": 4}
    LIBC_VARIADIC = frozenset({"snprintf"})
    ALL_REGS = (0, 1, 2, 3)

    def _libc_contract(self, tgt: int | None, record: bool = True):
        if tgt is None:
            return None
        c = self.LIBC_CONTRACTS.get(self.name(tgt))
        if c is None or self.member_of(tgt) != f"libc.a({c[0]})":
            return None
        if record:
            self._cache("_libc_used")[self.name(tgt)] = c
        return c

    def _handed_regs(self, entry: int, a: int) -> tuple:
        """The argument registers the call / tail at `a` hands its callee — `_handed` and the callback needs both ask
        here: a C-library routine at its contract, its arity (fixed, shown on its code; variadic, by the proved
        format); anything else, all four. Only what the callee is HANDED: what it clobbers and returns is unchanged."""
        tgt = self._call_target(self.ins_at[a])
        c = self._libc_contract(tgt)
        if c is None:
            return self.ALL_REGS
        if self.name(tgt) in self.LIBC_VARIADIC:
            lay = self._printf_layout(entry, a, tgt)
            return self.ALL_REGS if lay is None else lay[0]
        n = self._libc_arity(tgt)
        return self.ALL_REGS if n is None else tuple(range(n))

    def _libc_arity(self, tgt: int):
        """LIBC_ARITY for the routine at `tgt` when its code shows it (`_arity_breach` finds nothing), else None — the
        reason kept for rules.libc_arity. A routine asked while it is itself being checked (a cycle) is not shown."""
        memo, busy = self._cache("_memo_libc_arity"), self._cache("_libc_arity_busy")
        if tgt in memo:
            return memo[tgt][0]
        if tgt in busy:
            return None
        busy[tgt] = True
        try:
            n = self.LIBC_ARITY[self.name(tgt)]
            why = self._isolated(self._arity_breach, tgt, n)
        finally:
            del busy[tgt]
        memo[tgt] = (None if why else n, why)
        return memo[tgt][0]

    def arity_targets(self) -> list:
        """rules.libc_arity's list: each C-library routine whose arity was asked, and each printf-family call's layout."""
        out = []
        for t, (n, why) in sorted(self._cache("_memo_libc_arity").items()):
            name = self.name(t)
            if name in self.LIBC_VARIADIC:
                continue
            out.append(f"{name}: all four registers — {why}" if not n else f"{name}: r0" if n == 1 else f"{name}: r0-r{n - 1}")
        for (e, a), lay in sorted(self._cache("_printf_layouts").items()):
            what = self.name(self._call_target(self.ins_at[a]))
            out.append(f"{self.name(e)} {a:#x} {what}: " + ("all four registers and every incoming word — its format is "
                       "not proved or not sized" if lay is None else
                       f"r{', r'.join(map(str, lay[0]))}; incoming words {sorted(lay[1])}"))
        return out

    @staticmethod
    def _mentions_arg(atoms, k: int) -> bool:
        """Whether a value with these atoms may be (derived from) argument k's entry value, or a word read through it."""
        def has(x):
            if isinstance(x, tuple) and x:
                if x[0] in ("arg", "argo", "ind") and len(x) > 1 and x[1] == k:
                    return True
                return any(has(y) for y in x[1:])
            return False
        return any(has(x) for x in atoms)

    def _read_regs(self, i: dict) -> set:
        """The core registers the instruction reads as operands (a call's arguments and a return's result are not
        operands: the arity check looks at those itself). A destination that appears once and is not a memory base
        is only written; movt / bfi / bfc keep part of theirs, so read it."""
        o = re.sub(r"<[^>]*>", "", i["ops"]).replace(" ", "")
        b = base_mnem(i["mnem"])[0]
        fam = self._family(i)
        if b in ("bl", "blx", "b") and branch_target(i["ops"]):
            return set()
        regs = self._regs(o)
        if fam.startswith("pop") or (fam.startswith("ldm") and "{" in o):
            m = re.match(r"(\w+)!?,\{", o)
            return {m.group(1)} if m else set()
        w = self.written(i)
        bases = set(re.findall(r"\[(\w+)", o))
        if fam.startswith(("stm", "ldm")) and re.match(r"(\w+)!?,", o):
            bases.add(re.match(r"(\w+)!?,", o).group(1))
        count = {r: regs.count(r) for r in regs}
        return {r for r in count if not (r in w and count[r] == 1 and r not in bases and fam not in ("movt", "bfi", "bfc"))}

    ARG_HOLDERS = ("r0", "r1", "r2", "r3", "r4", "r5", "r6", "r7", "r8", "r9", "sl", "fp", "ip", "lr")

    def _arity_breach(self, R: int, n: int):
        """Where the routine's code may USE the entry value of a register at or above `n` (r<n>..r3), or None when
        it shows none: read by an instruction; handed to a callee whose own arity is not shown to exclude that
        position (a callee taken at LIBC_ARITY only once its code is checked; any other: all four); handed to an
        indirect call; returned in r0 (by a pop / ldm into r0: what it loads); or saved where it may be read back
        unpinned. A save (push / stmdb sp!) is no use while every later load is pinned and no frame address is handed
        on, in an argument register or in an incoming word the callee reads; a restore by pop / ldm is no use."""
        if not self._readable(R):
            return "its code is not in the image"
        self.analyse(R)
        ks = range(n, 4)
        if not ks:
            return None
        region = self.region(R)
        reached = self.sp_at.get(R, {})

        def held(a, reg):
            atoms = self._raw_reg(R, a, reg)
            return [k for k in ks if self._mentions_arg(atoms, k)]
        saved = False
        for idx, i in enumerate(region):
            a = i["addr"]
            if a not in reached or i["mnem"] == ".data":
                continue
            b, cond = base_mnem(i["mnem"])
            o = i["ops"].replace(" ", "")
            tgt = self._call_target(i)
            ret = b == "bx" and o == "lr" or (b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in o)
            if idx == len(region) - 1 and (cond or self._cond(i) or not (ret or b in ("b", "bx"))):
                return f"it may fall through at {a:#x} into what follows"
            tail = b == "b" and tgt is not None and tgt != R and tgt in self.func_entries
            if (b in ("bl", "blx") and branch_target(i["ops"])) or tail:
                c_n = None
                for j in range(4):
                    hk = held(a, f"r{j}")
                    if not hk:
                        continue
                    if c_n is None:
                        c_n = (self._libc_arity(tgt) if tgt is not None and self._libc_contract(tgt, record=False) is not None
                               and self.name(tgt) not in self.LIBC_VARIADIC else None)
                        c_n = -1 if c_n is None else c_n
                    if j < c_n or c_n < 0:
                        return (f"r{hk[0]} may reach {self.name(tgt) if tgt is not None else 'a callee'} at {a:#x} as its r{j}, "
                                f"which that callee's shown arity does not exclude")
                continue
            if b in ("blx", "bx") and o != "lr":           # an indirect call / tail: it may read every argument register
                for j in range(4):
                    hk = held(a, f"r{j}")
                    if hk:
                        return f"r{hk[0]} may reach an indirect callee at {a:#x} as its r{j}"
            if ret:                                        # (its result is r0; a register merely left as it came
                if b != "bx" and "r0" in reglist(i["ops"]):     # in is not returned — the caller's view of it is the
                    atoms = self._writer_atoms(R, i, "r0")      # clobber analysis's, as for any call). A pop / ldm
                    hk = [k for k in ks if self._mentions_arg(atoms, k)]   # that loads r0 returns what it loads
                else:
                    hk = held(a, "r0")
                if hk:
                    return f"r{hk[0]} may be returned in r0 at {a:#x}"
            if b in ("push", "stmdb", "stmfd") and (b == "push" or o.startswith("sp!,")):
                if any(held(a, r) for r in reglist(i["ops"]) if r in self.ARG_HOLDERS):
                    saved = True
                continue
            for r in sorted(self._read_regs(i)):
                if r in self.ARG_HOLDERS:
                    hk = held(a, r)
                    if hk:
                        return f"its entry r{hk[0]} may be read at {a:#x}, in {r} ({i['mnem']} {i['ops']})"
        if saved:                                          # a saved argument read back where the model does not pin it,
            for i in region:                               # or a frame address handed on (a callee may read the save)
                a = i["addr"]
                if a not in reached:
                    continue
                fam = self._family(i)
                o = i["ops"].replace(" ", "")
                if fam.startswith(("ldr", "vld")):
                    m = re.search(r"\[(\w+)", o)
                    if m and m.group(1) != "sp" and self._frameish(self._base_atoms(R, a, m.group(1))):
                        return f"a saved argument may be read back at {a:#x} through an address the model does not pin"
                if self._is_call(i) or base_mnem(i["mnem"])[0] == "b" and self._call_target(i) in self.func_entries:
                    for j in range(4):
                        if self._frameish(self._raw_reg(R, a, f"r{j}")):
                            return f"a saved argument's frame is handed on at {a:#x}"
                    reads = self._stack_use_at(R, a)[0]    # (and in the incoming words the callee reads)
                    offs = reached.get(a, frozenset())
                    if reads and len(offs) != 1 or reads is None:
                        return f"a saved argument's frame may be handed on at {a:#x} in stack words the model does not pin"
                    for k in sorted(reads):
                        if self._frameish(self._raw_slot(R, a, k - next(iter(offs)))):
                            return f"a saved argument's frame is handed on at {a:#x}, in the callee's incoming word {k}"
        return None

    # A printf conversion the model sizes: %[flags][width][.precision][length]conversion, `*` an int argument each.
    PRINTF_SPEC = re.compile(r"%(?P<flags>[-+ #0']*)(?P<width>\*|\d+)?(?:\.(?P<prec>\*|\d*))?"
                             r"(?P<len>hh|h|ll|l|L|j|z|t|q)?(?P<conv>[diouxXcspeEfFgGaA%])")

    @classmethod
    def printf_args(cls, fmt: str):
        """The byte size of each variadic argument a printf format consumes, in order, after the default argument
        promotions (4: int, unsigned, char / short promoted, a pointer, long, size_t, ptrdiff_t, wint_t; 8: long long,
        intmax_t, double — float promoted — and long double, which is double on this ABI). None when a conversion is
        one the model does not size (positional %n$, L with an integer, a length the conversion does not take, a
        decorated %%, or anything else)."""
        out, k = [], 0
        while True:
            k = fmt.find("%", k)
            if k < 0:
                return out
            m = cls.PRINTF_SPEC.match(fmt, k)
            if not m:
                return None
            k = m.end()
            conv, ln = m["conv"], m["len"]
            if conv == "%":
                if m.group(0) != "%%":
                    return None
                continue
            out += [4 for part in (m["width"], m["prec"]) if part == "*"]
            if conv in "diouxX" and ln in (None, "hh", "h", "l", "z", "t"):
                out.append(4)
            elif conv in "diouxX" and ln in ("ll", "q", "j"):
                out.append(8)
            elif conv in "eEfFgGaA" and ln in (None, "l", "L"):
                out.append(8)
            elif conv in "cs" and ln in (None, "l"):
                out.append(4)
            elif conv == "p" and ln is None:
                out.append(4)
            else:
                return None

    @staticmethod
    def vararg_layout(fixed: int, sizes) -> tuple:
        """(the argument registers, the incoming stack-word offsets) a call with `fixed` named word arguments and
        variadic ones of these sizes occupies — the AAPCS base standard, which a variadic call always uses (no VFP
        registers): a word goes in the next core register while one is left, else on the stack; an 8-byte argument
        first rounds the register number up to even, and when it does not fit in r0-r3 every register is taken as
        used (NCRN = 4), it goes on the stack at an 8-byte aligned offset, and every later argument follows it there."""
        ncrn, nsaa, regs, words = fixed, 0, set(range(fixed)), set()
        for s in sizes:
            if s == 8:
                ncrn += ncrn & 1
                if ncrn + 2 <= 4:
                    regs |= {ncrn, ncrn + 1}
                    ncrn += 2
                    continue
                ncrn, nsaa = 4, (nsaa + 7) & ~7
            elif ncrn < 4:
                regs.add(ncrn)
                ncrn += 1
                continue
            words |= set(range(nsaa, nsaa + s, 4))
            nsaa += s
        return tuple(sorted(regs)), frozenset(words)

    def _printf_layout(self, entry: int, a: int, tgt: int):
        """(registers, incoming stack words) the printf-family call at `a` reads: the union over the call's proved
        formats (`_printf_safe`'s), each laid out by `vararg_layout`; None when the format is not proved or one is
        not sized — the call then reads every register and every incoming word."""
        c = self._libc_contract(tgt)
        fixed = self.LIBC_ARITY[self.name(tgt)]
        ok, info = self._guarded("printf", (entry, a, c[4]), self._printf_compute, (True, None))
        if not ok:
            lay = None
        elif info is None:                                 # read while it is being computed: its optimistic end (the
            lay = (tuple(range(fixed)), frozenset())       # pass is accepted only once that read meets the final value)
        else:
            regs, words = set(), set()
            for f in info["formats"]:
                sizes = self.printf_args(f)
                if sizes is None:
                    regs = None
                    break
                r, w = self.vararg_layout(fixed, sizes)
                regs |= set(r)
                words |= w
            lay = (tuple(sorted(regs)), frozenset(words)) if regs is not None and info["formats"] else None
        self._cache("_printf_layouts")[(entry, a)] = lay
        return lay

    def _ret_atoms(self, callee: int):
        """What a compiled routine may return in r0, as atoms of ITS OWN arguments; None when it cannot be said (a
        tail transfer, recursion)."""
        return self._guarded("ret", callee, self._ret_compute, frozenset())

    def _ret_compute(self, callee: int):
        self.analyse(callee)
        if any(e["kind"] in ("tail", "indirect_tail", "fallthrough") for e in self.edges[callee]):
            return None
        out: set = set()
        for i in self.region(callee):
            if i["addr"] not in self.sp_at.get(callee, {}):
                continue
            b = base_mnem(i["mnem"])[0]
            if b == "bx" or (b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in i["ops"]):
                out |= self._raw_reg(callee, i["addr"], "r0")
        return frozenset(out)

    def _call_result(self, entry: int, w: dict, reg: str) -> set:
        """What a call leaves in `reg`: r0 / r1 may be (derived from) an argument the callee returns."""
        if reg not in ("r0", "r1"):
            return {("other",)}
        a = w["addr"]
        tgt = self._call_target(w)
        args = [self._raw_reg(entry, a, f"r{n}") for n in range(4)]
        anything = {("other",)}
        for x in args:
            anything |= self._derived(x)
        c = self._libc_contract(tgt)
        if c is not None:
            if c[3] is None:
                return {("other",)}
            return set(args[0]) if (c[3] == "arg0" and reg == "r0") else {("other",)} | self._derived(args[0])
        if tgt is None:                                    # an indirect call: the union over what it may reach
            targets = self._indirect_targets(entry, a)
            if targets is None:
                return anything
            out = set()
            for t2 in targets:
                out |= self._result_of(entry, a, t2, reg, args, anything)
            return out or {("other",)}
        return self._result_of(entry, a, tgt, reg, args, anything)

    def _result_of(self, entry: int, a: int, tgt: int, reg: str, args, anything) -> set:
        """What a call of the routine `tgt` at `a` leaves in r0 / r1, in the caller's atoms."""
        c = self._contract(tgt)
        if c is not None:
            if c["returns"] == "in0" and reg == "r0":      # NULL, or a pointer into argument 0's object
                return {("const", 0)} | (self._derived(args[0]) or {("other",)})
            return {("other",)}
        rets = self._ret_atoms(tgt) if self._readable(tgt) else None
        if rets is None:
            return anything
        out = {("other",)} if reg == "r1" else set()
        for x in rets:
            if x[0] in ("arg", "argo") and isinstance(x[1], int):
                out |= self._shift(args[x[1]], x[2] if x[0] == "argo" else 0) if reg == "r0" else self._derived(args[x[1]])
            elif x[0] == "der" and x[1] != "frame" and x[1][0] == "ind" and isinstance(x[1][1], int):
                for y in args[x[1][1]]:                    # derived from a word the callee loaded through argument n
                    if y[0] == "frame" and y[1] is not None and x[1][2] is not None:
                        out |= {("other",)} | self._derived(self._raw_slot(entry, a, y[1] + x[1][2]))
                    elif y[0] == "frame" or y == ("der", "frame"):
                        out |= {("other",), ("der", "frame")}
                    else:
                        out |= {("other",)} | self._derived(self._through({y}, None))
            elif x[0] == "der" and x[1] != "frame" and isinstance(x[1][1], int):
                out |= {("other",)} | self._derived(args[x[1][1]])
            elif x[0] == "ind" and isinstance(x[1], int):   # a word the callee loaded through its argument
                for y in args[x[1]]:
                    if y[0] == "frame" and y[1] is not None and x[2] is not None:
                        out |= self._raw_slot(entry, a, y[1] + x[2])
                    elif y[0] == "frame" or y == ("der", "frame"):
                        out |= {("other",), ("der", "frame")}
                    else:
                        out |= {("other",)} | self._through({y}, None)
            elif x[0] in ("arg", "argo", "ind") or (x[0] == "der" and x[1] != "frame"):
                return anything                            # (derived from) a stack argument: not followed
            else:
                out.add(("other",))                        # a constant, an unknown, the callee's own (dead) frame
        return out or {("other",)}

    def _base_atoms(self, entry: int, at: int, reg: str) -> frozenset:
        if reg == "sp":
            return frozenset({("frame", self._pt_slot(entry, at, 0))})
        if reg == "pc":
            return frozenset({("other",)})
        return self._raw_reg(entry, at, reg)

    def _reg_compute(self, entry: int, at: int, reg: str) -> set:
        out: set = set()
        for w in self.reaching_writers(entry, at, reg):
            if w is None:
                out.add(("arg", self.ARGREG[reg]) if reg in self.ARGREG else ("other",))
            else:
                out |= self._writer_atoms(entry, w, reg)
        return out

    def _load_atoms(self, entry: int, a: int, base: str, off: int) -> set:
        """The word loaded from [base + off] at `a`: a frame slot's atoms when the base is ONE known frame address;
        an unknown (possibly a parked frame address) when the base may be the frame; else an unknown — or, through
        an argument, the word loaded from it (('ind', n, k))."""
        B = self._base_atoms(entry, a, base)
        if not B:
            return set()                                   # the base is still being solved (a cycle)
        if len(B) == 1 and next(iter(B))[0] == "frame" and next(iter(B))[1] is not None:
            return set(self._raw_slot(entry, a, next(iter(B))[1] + off))
        if any(x[0] == "frame" or x == ("der", "frame") for x in B):
            return self._frame_word(entry)
        return {("other",)} | self._through(B, off)

    def _frame_word(self, entry: int) -> set:
        """A word loaded from the routine's frame at a place the model does not pin: an unknown — which may be an
        address of the frame only if some store of the routine can have parked one there."""
        return {("other",)} if self._pointer_slots(entry) == frozenset() else {("other",), ("der", "frame")}

    @staticmethod
    def _through(B, off) -> set:
        """A word loaded through the atoms `B` (+ off): ('ind', n, k) the word at argument n + k; ('ind', n, None)
        a word reached through argument n at a place the model does not pin, or at a second remove."""
        out = set()
        for x in B:
            if x[0] == "arg":
                out.add(("ind", x[1], off))
            elif x[0] == "argo":
                out.add(("ind", x[1], None if off is None else x[2] + off))
            elif x[0] == "der" and x[1] != "frame":
                out.add(("ind", x[1][1], None))
            elif x[0] == "ind":
                out.add(("ind", x[1], None))
        return out

    def _writer_atoms(self, entry: int, w: dict, reg: str) -> set:
        """What the writer `w` leaves in `reg`."""
        o = w["ops"].replace(" ", "")
        fam = self._family(w)
        rs = self._regs(o)
        a = w["addr"]
        if base_mnem(w["mnem"])[0] in ("bl", "blx"):       # a call's result / leftovers: maybe one of its arguments
            return self._call_result(entry, w, reg)
        if fam in ("pop", "ldm", "ldmia", "ldmfd") and "{" in o:
            base = "sp" if fam == "pop" else re.match(r"(\w+)", o).group(1)
            regs = reglist(w["ops"])
            if reg in regs:                                # (a base in its own list is loaded, not kept)
                return self._load_atoms(entry, a, base, 4 * regs.index(reg))
            return self._derived(self._base_atoms(entry, a, base)) or {("other",)}
        mld = re.fullmatch(r"(\w+)(?:,(\w+))?,\[(\w+)(?:,#(-?(?:0x[0-9a-f]+|\d+)))?\]", o)
        if fam == "ldr" and mld and mld.group(3) == "pc" and not mld.group(2) and reg == mld.group(1):
            lit = ((a + 4) & ~3 if w["thumb"] else a + 8) + (int(mld.group(4), 0) if mld.group(4) else 0)
            return {self._const_atom(self.words[lit])} if lit in self.words else {("other",)}   # a literal-pool word
        if fam in ("ldr", "ldrd") and mld and mld.group(3) != "pc":
            data = [mld.group(1), mld.group(2) or (self._next_reg(mld.group(1)) if fam == "ldrd" else None)]
            if fam == "ldr" and mld.group(2):
                return {("other",)}
            if reg in data:
                return self._load_atoms(entry, a, mld.group(3), (int(mld.group(4), 0) if mld.group(4) else 0) + 4 * data.index(reg))
        if fam.startswith(("ldr", "ldm", "pop", "vld", "vpop")):            # any other load (and its write-back)
            mb = re.search(r"\[(\w+)", o)
            base = mb.group(1) if mb else (re.match(r"(\w+)", o).group(1) if o else "sp")
            B = self._base_atoms(entry, a, base)
            if reg == base:
                return self._derived(B) or {("other",)}
            word = fam in ("ldr", "ldrd", "pop") or fam.startswith("ldm")      # a byte / halfword is no address
            if not word:
                return {("other",)}
            if any(x[0] == "frame" or x == ("der", "frame") for x in B):
                return self._frame_word(entry)
            return {("other",)} | self._through(B, None)
        dest = rs[0] if rs else None
        if reg == dest:
            if fam in ("mov", "movs") and len(rs) == 2 and "#" not in o and o.count(",") == 1:
                return set(self._base_atoms(entry, a, rs[1]))
            if fam in ("add", "adds", "addw", "sub", "subs", "subw") and ",#" in o and len(rs) in (1, 2) and o.count(",") == len(rs):
                return self._shift(self._base_atoms(entry, a, rs[-1]), imm(o) if fam.startswith("add") else -imm(o))
            if fam in ("movw", "mov", "movs") and re.fullmatch(r"\w+,#(?:0x[0-9a-f]+|\d+)", o):
                return {("const", imm(o))}
            if fam == "movt" and ",#" in o and len(rs) == 1:
                out = set()
                for lo in self._raw_reg(entry, a, reg):
                    if lo[0] == "const":
                        v = (imm(o) << 16) | lo[1]
                        out.add(("cb", v & ~1) if (v & ~1) in self.label_at and self.unit_of(v & ~1) in self.APP_UNITS else self._const_atom(v))
                    else:
                        out |= {("other",)} | self._derived({lo})
                return out
        # anything else: an unknown, derived from whatever it read
        srcs = rs[1:] if (fam in self.PURE_UNARY or o.count(",") >= 2 or reg != dest) else rs
        out = set()
        for r in srcs:
            out |= self._derived(self._base_atoms(entry, a, r))
        return out or {("other",)}

    # ---- A1: a bounded index (the owner's ruling of 2026-10-07 — the "fewer unplaced writes" unit, first part)
    #
    # A write at `base + index` (the index a register, scaled or not: `[rb, ri, lsl #s]`, or the address computed
    # first by `add ra, rb, ri, lsl #s` and used at an immediate offset) is placed when the index has an UNSIGNED
    # range read off the image: on EVERY path from the routine's entry to the write, after the index's last
    # definition, either an unsigned comparison of the index against a constant (or a register whose own range is
    # known) with the conditional branch — or the conditional write itself — taken the way that bounds it (`_guard`),
    # or a definition that bounds it by construction (`uxtb`, `uxth`, `and #mask`, `lsr`, `ubfx`, a byte / halfword
    # load, a constant, and `mov` / `add` / `sub` / `lsl` of a bounded value without wrapping). A signed comparison
    # bounds nothing (the value may be negative: a huge unsigned offset), nor does an equality, nor a guard any path
    # reaches the write without, nor one the index is written after. The extent is [lo << s, (hi << s) + width) from
    # the base, with every addition checked against the 32-bit wrap; the base is then placed as any other pointer.

    # An upper bound that is a linear form of an INCOMING argument's value — ('lin', n, mul, add) = mul * arg_n + add —
    # (A1, the argument-bounded index): the guard compared the index with a register holding exactly the argument
    # as the routine received it (its atoms are {('arg', n)}: never redefined, only copied). It is carried into the
    # store's extent and the routine's summary, and substituted where the routine is called (`_subst_ext`).
    @staticmethod
    def _lin_add(h, k: int):
        return h + k if isinstance(h, int) else ("lin", h[1], h[2], h[3] + k)

    @staticmethod
    def _lin_shl(h, sh: int):
        return h << sh if isinstance(h, int) else ("lin", h[1], h[2] << sh, h[3] << sh)

    @staticmethod
    def _lin_text(h) -> str:
        return f"{h}" if isinstance(h, int) else f"argument {h[1]}" + (f" x {h[2]}" if h[2] != 1 else "") + (f" {h[3]:+d}" if h[3] else "")

    IDX_BOUNDED_BY_OP = {"uxtb": 0xFF, "uxth": 0xFFFF, "ldrb": 0xFF, "ldrh": 0xFFFF, "ldrsb": None, "ldrsh": None}
    UNSIGNED_LT = {("cc", True): 0, ("lo", True): 0, ("cs", False): 0, ("hs", False): 0,   # taken / not taken ⇒ reg < N
                   ("ls", True): 1, ("hi", False): 1}                                         # ⇒ reg <= N

    def _reg_range(self, entry: int, at: int, reg: str, depth: int = 0):
        """The unsigned range [lo, hi] `reg` holds just before `at`, read off the image (see the A1 comment), with
        the rules that give it — on every path back from `at`, an unsigned guard or the path's last definition;
        None when a path has neither."""
        c = self._cache("_rr_cache")
        key = (entry, at, reg)
        if key in c:
            return c[key]
        c[key] = None                                      # (a cycle in the definitions: no range)
        v = self._guard_range(entry, at, reg, depth) or self._def_range(entry, at, reg, depth)
        c[key] = v
        return v

    def _def_range(self, entry: int, at: int, reg: str, depth: int):
        """The range from `reg`'s reaching definitions alone: every one of them bounded."""
        if depth > 8:
            return None
        lo, hi, rules = 0, -1, set()
        for w in self.reaching_writers(entry, at, reg):
            if w is None or self._cond(w):
                return None
            r = self._writer_range(entry, w, reg, depth + 1)
            if r is None:
                return None
            hi = self._hi_max(hi, r[1]) if rules else r[1]
            if hi is None:
                return None
            lo = min(lo, r[0]) if rules else r[0]
            rules.add(r[2])
        return (lo, hi, " / ".join(sorted(rules))) if rules else None

    @staticmethod
    def _hi_max(a, b):
        """The larger of two upper bounds; None when they are forms of different arguments (or a form and a number)."""
        if isinstance(a, int) and isinstance(b, int):
            return max(a, b)
        if a == b:
            return a
        if not isinstance(a, int) and not isinstance(b, int) and a[1] == b[1] and a[2] == b[2]:
            return ("lin", a[1], a[2], max(a[3], b[3]))
        return None

    def _writer_range(self, entry: int, w: dict, reg: str, depth: int):
        fam = self._family(w)
        o = w["ops"].replace(" ", "")
        rs = self._regs(o)
        if not rs or rs[0] != reg:
            return None
        cr = self._count_range(entry, w, reg)
        if cr is not None:
            return cr
        if fam in ("mov", "movs", "movw") and re.fullmatch(r"\w+,#(?:0x[0-9a-f]+|\d+)", o):
            k = imm(o)
            return (k, k, "a constant")
        if fam in self.IDX_BOUNDED_BY_OP and self.IDX_BOUNDED_BY_OP[fam] is not None and len(rs) >= 1:
            return (0, self.IDX_BOUNDED_BY_OP[fam], f"a {fam}")
        if fam in ("and", "ands") and len(rs) == 2 and re.fullmatch(r"\w+,\w+,#(?:0x[0-9a-f]+|\d+)", o):
            return (0, imm(o), "an and-mask")
        if fam == "ubfx" and len(rs) == 2:
            m = re.fullmatch(r"\w+,\w+,#(\d+),#(\d+)", o)
            return (0, (1 << int(m.group(2))) - 1, "a ubfx") if m else None
        if fam in ("lsr", "lsrs") and len(rs) == 2 and re.fullmatch(r"\w+,\w+,#(\d+)", o):
            return (0, 0xFFFFFFFF >> imm(o), "an lsr")
        if fam in ("mov", "movs") and len(rs) == 2 and re.fullmatch(r"\w+,\w+", o):
            r = self._reg_range(entry, w["addr"], rs[1], depth)
            return r and (r[0], r[1], r[2])
        if fam in ("lsl", "lsls") and len(rs) == 2 and re.fullmatch(r"\w+,\w+,#(\d+)", o):
            r = self._reg_range(entry, w["addr"], rs[1], depth)
            n = imm(o)
            if r is None or (isinstance(r[1], int) and (r[1] << n) > 0xFFFFFFFF):
                return None
            return (r[0] << n, self._lin_shl(r[1], n), r[2] + f" << {n}")
        if fam in ("add", "adds", "addw", "sub", "subs", "subw") and len(rs) == 2 and re.fullmatch(r"\w+,\w+,#(?:0x[0-9a-f]+|\d+)", o):
            r = self._reg_range(entry, w["addr"], rs[1], depth)
            if r is None:
                return None
            k = imm(o)
            if fam.startswith("add"):
                if isinstance(r[1], int) and r[1] + k > 0xFFFFFFFF:
                    return None
                return (r[0] + k, self._lin_add(r[1], k), r[2] + f" + {k}")
            return None if r[0] - k < 0 else (r[0] - k, self._lin_add(r[1], -k), r[2] + f" - {k}")
        return None

    def _cond_of(self, i: dict):
        """The two-letter condition the instruction executes under (`bcs` → 'cs', `strbls` → 'ls'), or None."""
        f = i["mnem"].split(".")[0]
        return f[-2:] if self._cond(i) else None

    def _guard_range(self, entry: int, at: int, reg: str, depth: int):
        """The range an unsigned guard gives `reg` at `at` — on every path back to its definitions: [0, N) or [0, N]."""
        i = self.ins_at[at]
        pred = self._rpred(entry)
        succ = self._region_succ(entry)
        hi = None
        lo = None                                          # (a guard gives 0, unsigned; a definition its own low end)
        rules: set = set()
        start = []                                         # (node, the pending branch outcome, the node after it)
        c0 = self._cond_of(i)
        if c0:                                             # a conditional write: its own condition is the guard
            start = [(p, (c0, True), at) for p in pred.get(at, [])]
        else:
            start = [(p, None, at) for p in pred.get(at, [])]
        seen = set()
        stack = list(start)
        if not stack:
            return None
        while stack:
            p, pending, child = stack.pop()
            q = self.ins_at[p]
            b, cond = base_mnem(q["mnem"])[0], self._cond_of(q)
            if b == "b" and cond and branch_target(q["ops"]) and pending is None:
                t = branch_target(q["ops"])[0]             # (the owner's HOLD on f624c87, P1) the outcome is the
                outs = succ.get(p, [])                     # edge we came back over: each outcome is its own visit —
                if len(set(outs)) < 2 or child not in outs:   # a branch whose target IS its fallthrough says nothing
                    pending = None
                else:
                    pending = (cond, child == t)
            if (p, pending) in seen:
                continue
            seen.add((p, pending))
            if reg in self.written(q):                     # this path's last definition, before any guard: it must
                r = None if self._cond(q) else self._writer_range(entry, q, reg, depth + 1)   # bound the value itself
                if r is None:
                    return None
                hi = r[1] if hi is None else self._hi_max(hi, r[1])
                if hi is None:
                    return None
                lo = r[0] if lo is None else min(lo, r[0])
                rules.add(r[2])
                continue
            if b == "b" and cond and branch_target(q["ops"]):
                pass                                       # (decided above)
            elif sets_flags(q):
                o = q["ops"].replace(" ", "")
                m = re.fullmatch(r"(\w+),(#(?:0x[0-9a-f]+|\d+)|\w+)", o) if q["mnem"].split(".")[0] == "cmp" else None
                bound = None
                rule = "an unsigned guard"
                if pending is not None and m and m.group(1) == reg:
                    if m.group(2).startswith("#"):
                        n = imm(o)
                    else:
                        r = self._reg_range(entry, p, m.group(2), depth + 1)
                        n = None if r is None else r[1]
                        if n is None:                      # the register holds an INCOMING argument, as received
                            av = self._base_atoms(entry, p, m.group(2))
                            if len(av) == 1 and next(iter(av))[0] == "arg" and isinstance(next(iter(av))[1], int):
                                n = ("lin", next(iter(av))[1], 1, 0)
                                rule = f"an unsigned guard against argument {n[1]}"
                    k = self.UNSIGNED_LT.get(pending)
                    if n is not None and k is not None:
                        bound = self._lin_add(n, k - 1)
                        if isinstance(bound, int) and bound < 0:
                            return None
                if bound is None:
                    pending = None                         # (another flag setter, a signed or equal test: no bound)
                    if p == entry:
                        return None
                    stack += [(x, pending, p) for x in pred.get(p, [])]
                    continue
                hi = bound if hi is None else self._hi_max(hi, bound)
                if hi is None:
                    return None
                lo = 0
                rules.add(rule)
                continue                                   # this path is bounded here
            if p == entry:
                return None                                # the incoming value, no guard
            stack += [(x, pending, p) for x in pred.get(p, [])]
        return None if hi is None else (lo or 0, hi, " / ".join(sorted(rules)))

    def _indexed_address(self, entry: int, at: int, base: str, inner: str | None):
        """For `[base, inner]` with `inner` a register (scaled or not): (the base's atoms, lo, hi, the rule) when the
        index is bounded; else None."""
        m = re.fullmatch(r"(\w+)(?:,lsl#(\d+))?", inner or "")
        if not m:
            return None
        r = self._reg_range(entry, at, m.group(1))
        if r is None:
            return None
        sh = int(m.group(2)) if m.group(2) else 0
        if isinstance(r[1], int) and (r[1] << sh) > 0xFFFFFFFF:
            return None
        return (self._base_atoms(entry, at, base), r[0] << sh, self._lin_shl(r[1], sh), r[2])

    def _computed_address(self, entry: int, at: int, reg: str):
        """For a register whose one reaching writer is `add reg, rb, ri(, lsl #s)` with `ri` bounded there: (rb's
        atoms at the add, lo, hi, the rule); else None."""
        ws = self.reaching_writers(entry, at, reg)
        if len(ws) != 1 or ws[0] is None or self._cond(ws[0]):
            return None
        w = ws[0]
        o = w["ops"].replace(" ", "")
        m = re.fullmatch(r"(\w+),(\w+),(\w+)(?:,lsl#(\d+))?", o)
        if self._family(w) not in ("add", "adds") or not m or m.group(1) != reg or m.group(3).startswith("#"):
            return None
        return self._indexed_address(entry, w["addr"], m.group(2), m.group(3) + (f",lsl#{m.group(4)}" if m.group(4) else ""))

    # ---- the ÷10 digit loop, and the copy loop that follows it (the owner's ruling of 2026-10-07 on the search_render
    # unit): a specific, image-read trip-count bound.
    #
    # The unsigned decimal conversion GCC emits: `umull rL, rH, rM, q` with rM = MAGIC10, `lsr rD, rH, #3` (together
    # q // 10 — for EVERY 32-bit q, see MAGIC10), the next q is rD, and the back edge `bhi` tests `cmp q, #9` on the
    # value BEFORE that update (the dataflow decides, not the source's wording): the body runs once per decimal digit
    # of the first q, 1 to 10 times. A register stepped by a constant once per body (a post-indexed store, an add)
    # from a pinned frame address is then at A + k·step on the k-th run, k in [0, 9]; a counter stepped by one from a
    # constant is c0 + k, c0 + 1 .. c0 + 10 after the loop. The copy loop that follows (`cmp p, e; bne`, p stepped
    # by one from a pinned frame address, e = that address + the SAME count value — one reaching definition, unchanged
    # — so that p reaches e exactly after count steps) bounds every pointer of its body stepped by ±1 from a pinned
    # frame address or from one plus that same count. Everything else about such loops — another writer of q, p, c
    # or e in the body, a branch into or out of it, flags set between the compare and the branch, a different
    # multiplier, shift or word, an update that is not the quotient — leaves the pointer unpinned, as before.
    MAGIC10 = 0xCCCCCCCD          # = ceil(2^35 / 10); 10 * MAGIC10 - 2^35 = 2, so for x < 2^32: x * MAGIC10 / 2^35
    #                               = x / 10 + 2x / (10 * 2^35) < x / 10 + 1/40, and floor(x / 10)'s next integer is
    #                               at least 1/10 away: floor((x * MAGIC10) >> 35) == x // 10 (the test is exhaustive)

    def _straight_body(self, entry: int, L: int, br: int):
        """The instruction addresses from L to the back-edge branch at `br` when they form ONE straight run entered
        only at L (from the instruction before it, and from the branch) and left only by the branch; else None."""
        succ, pred = self._region_succ(entry), self._rpred(entry)
        body = [i["addr"] for i in self.region(entry) if L <= i["addr"] <= br]
        if not body or body[0] != L or body[-1] != br:
            return None
        for k, a in enumerate(body):
            if a != br and succ.get(a) != [body[k + 1]]:
                return None                                # a branch out, a return, a computed jump
            ins = set(pred.get(a, []))
            if a == L:
                outside = ins - {br}
                if len(outside) != 1 or next(iter(outside)) >= L:
                    return None                            # entered from elsewhere than straight above
            elif ins != {body[k - 1]}:
                return None                                # entered from elsewhere
        if set(succ.get(br, [])) != {L, br + self.ins_at[br]["size"]}:
            return None                                    # the branch leaves only to L or to the next instruction
        return body

    def _step_of(self, ins: dict, reg: str):
        """(The owner's HOLD on 4c9ee82) the signed constant by which `ins` ALWAYS changes `reg`, read from its opcode,
        its direction and its writeback: `add reg, reg, #k` +k, `sub reg, reg, #k` −k, a load or store post-indexed
        `[reg], #k` or pre-indexed with writeback `[reg, #k]!` +k (k signed); None for anything else — and for any
        instruction under a condition, which may not run on a given pass."""
        if self._cond(ins):
            return None
        mn = ins["mnem"].split(".")[0]
        o = ins["ops"].replace(" ", "")
        if mn in ("add", "sub"):
            m = re.fullmatch(r"(\w+),(\w+),#(-?(?:0x[0-9a-f]+|\d+))", o)
            if m and m.group(1) == reg == m.group(2):
                k = int(m.group(3), 0)
                return k if mn == "add" else -k
            return None
        if mn.startswith(("ldr", "str")) and not mn.startswith(("ldrd", "strd", "strex", "ldrex")):
            m = re.search(r"\[" + reg + r"\],#(-?(?:0x[0-9a-f]+|\d+))$", o) or re.search(r"\[" + reg + r",#(-?(?:0x[0-9a-f]+|\d+))\]!$", o)
            if m and (mn.startswith("str") or self._regs(o.split("[")[0])[:1] != [reg]):
                return int(m.group(1), 0)
        return None

    def _flag_setter_before(self, entry: int, br: int, body: list):
        """The one instruction setting the flags the branch at `br` reads, when it is in the straight body."""
        for a in reversed([x for x in body if x < br]):
            if sets_flags(self.ins_at[a]):
                return self.ins_at[a]
        return None

    def _writers_in(self, body: list, reg: str) -> list:
        return [a for a in body if reg in self.written(self.ins_at[a])]

    def _div10_loops(self, entry: int) -> dict:
        """{back-edge address: {'L', 'q', 'ptr': {register: step}, 'count': {register: c0}, 'body'}} for every ÷10
        digit loop of the routine read off its code (see the block comment)."""
        c = self._cache("_div10_cache")
        if entry in c:
            return c[entry]
        c[entry] = out = {}                                # (re-entrant reads while recognising: no loop yet)
        self.analyse(entry)
        for i in self.region(entry):
            if i["mnem"].split(".")[0] != "bhi" or not branch_target(i["ops"]):
                continue
            L, br = branch_target(i["ops"])[0], i["addr"]
            if L >= br:
                continue
            body = self._straight_body(entry, L, br)
            if body is None:
                continue
            cmp = self._flag_setter_before(entry, br, body)
            m = re.fullmatch(r"(\w+),#9", cmp["ops"].replace(" ", "")) if cmp is not None and cmp["mnem"].split(".")[0] == "cmp" else None
            if not m:
                continue
            q = m.group(1)
            um = [a for a in body if self._family(self.ins_at[a]) == "umull"]
            if len(um) != 1 or self._cond(self.ins_at[um[0]]):
                continue
            uo = self._regs(self.ins_at[um[0]]["ops"].replace(" ", ""))
            if len(uo) != 4 or q not in uo[2:]:
                continue
            rH, rM = uo[1], (uo[3] if uo[2] == q else uo[2])
            if self._raw_reg(entry, um[0], rM) != frozenset({("const", self.MAGIC10)}) or self._writers_in(body, rM):
                continue
            lsr = [a for a in body if a > um[0] and re.fullmatch(r"(\w+)," + rH + r",#3", self.ins_at[a]["ops"].replace(" ", ""))
                   and self._family(self.ins_at[a]) == "lsr"]
            if len(lsr) != 1 or self._cond(self.ins_at[lsr[0]]) or self._writers_in([a for a in body if um[0] < a < lsr[0]], rH):
                continue
            rD = self._regs(self.ins_at[lsr[0]]["ops"].replace(" ", ""))[0]
            qw = self._writers_in(body, q)                 # q is updated once, from rD, after the compare and the multiply
            upd = qw[0] if len(qw) == 1 else None
            if upd is None or upd <= max(cmp["addr"], um[0]) or upd < lsr[0] or self._cond(self.ins_at[upd]):
                continue                                   # (a conditional update may not run: the loop may not end)
            uo2 = self.ins_at[upd]["ops"].replace(" ", "")
            if not ((self._family(self.ins_at[upd]) in ("mov", "movs") and uo2 == f"{q},{rD}" and not self._writers_in([a for a in body if lsr[0] < a < upd], rD))
                    or (upd == lsr[0] and rD == q)):
                continue
            ptr, count = {}, {}
            for a in body:
                ins = self.ins_at[a]
                o = ins["ops"].replace(" ", "")
                for r in self.written(ins):
                    if r in (q, rD, rH, uo[0], "sp", "pc"):
                        continue
                    k = self._step_of(ins, r)
                    if k is None or k <= 0 or len(self._writers_in(body, r)) != 1:
                        continue
                    if ins["mnem"].split(".")[0].startswith("str") and re.search(r"\[" + r + r"\],#", o):
                        ptr[r] = k                         # a post-indexed store stepping forward
                    elif ins["mnem"].split(".")[0] == "add":
                        (count if k == 1 else ptr)[r] = k
            c0 = {}
            for r in list(count):                          # the counter's value entering the loop: one constant
                ws = [w for w in self.reaching_writers(entry, L, r) if w is None or w["addr"] not in body]
                vals = set()
                for w in ws:
                    rr = None if w is None else self._writer_range(entry, w, r, 0)
                    if rr is None or rr[0] != rr[1] or not isinstance(rr[1], int):
                        vals = None
                        break
                    vals.add(rr[0])
                if vals and len(vals) == 1:
                    c0[r] = next(iter(vals))
            out[br] = {"L": L, "q": q, "ptr": ptr, "count": {r: c0[r] for r in count if r in c0}, "count_step": {r: self._writers_in(body, r)[0] for r in count}, "body": body}
        c[entry] = dict(out)
        return c[entry]

    def _in_body(self, loops: dict, a: int):
        for br, info in loops.items():
            if a in info["body"]:
                return br, info
        return None, None

    def _count_range(self, entry: int, w: dict, reg: str):
        """(A1 hook) the writer `w` is the counter step of a ÷10 loop: the value it leaves is c0 + k, k in [1, 10]."""
        for info in self._div10_loops(entry).values():
            if reg in info["count"] and info["count_step"].get(reg) == w["addr"]:
                return (info["count"][reg] + 1, info["count"][reg] + 10, "the digit count of a ÷10 loop")
        return None

    def _loop_frame_span(self, entry: int, at: int, reg: str):
        """The pinned frame range [lo, hi] (slots relative to the entry SP) of the VALUE `reg` holds just before `at`
        — the base the access at `at` starts from; a pre-indexed access adds its own offset to it, a post-indexed
        one uses it as is — when `reg` is a pointer stepped by a ÷10 digit loop or by the copy loop after it (see
        the block comment); None otherwise."""
        c = self._cache("_lfs_cache")
        key = (entry, at, reg)
        if key in c:
            return c[key]
        c[key] = None
        v = self._div10_span(entry, at, reg) or self._copy_span(entry, at, reg)
        c[key] = v
        return v

    def _pinned_at(self, entry: int, at: int, reg: str):
        """The one pinned frame slot `reg` holds just before `at`, or None."""
        v = self._raw_reg(entry, at, reg)
        return next(iter(v))[1] if len(v) == 1 and next(iter(v))[0] == "frame" and next(iter(v))[1] is not None else None

    def _div10_span(self, entry: int, at: int, reg: str):
        loops = self._div10_loops(entry)
        br, info = self._in_body(loops, at)
        if info is None or reg not in info["ptr"]:
            return None
        ws = self.reaching_writers(entry, at, reg)
        step_at = self._writers_in(info["body"], reg)[0]
        if at != step_at:
            return None                                    # (the pointer is used at its own step only: the store)
        starts = set()
        for w in ws:
            if w is None:
                return None
            if w["addr"] == step_at:
                continue
            v = self._writer_atoms(entry, w, reg)
            if len(v) != 1 or next(iter(v))[0] != "frame" or next(iter(v))[1] is None:
                return None
            starts.add(next(iter(v))[1])
        if len(starts) != 1:
            return None
        A, step = next(iter(starts)), info["ptr"][reg]
        return (A, A + 9 * step, "a pointer stepped by a ÷10 digit loop")

    def _copy_loops(self, entry: int) -> dict:
        """{back-edge: {'L', 'p', 'e', 'count': (register, lo, hi), 'body', 'base'}}: `cmp p, e; bne L` loops, p stepped
        by +1 from a pinned frame slot A, e = A + c with c the same count value throughout (one reaching
        definition, not written in the body), c in [lo, hi], lo >= 1: p runs A .. A + c - 1."""
        c = self._cache("_copy_cache")
        if entry in c:
            return c[entry]
        out = {}
        self.analyse(entry)
        for i in self.region(entry):
            if i["mnem"].split(".")[0] != "bne" or not branch_target(i["ops"]):
                continue
            L, br = branch_target(i["ops"])[0], i["addr"]
            if L >= br:
                continue
            body = self._straight_body(entry, L, br)
            if body is None:
                continue
            cmp = self._flag_setter_before(entry, br, body)
            m = re.fullmatch(r"(\w+),(\w+)", cmp["ops"].replace(" ", "")) if cmp is not None and cmp["mnem"].split(".")[0] == "cmp" else None
            if not m:
                continue
            for p, e in ((m.group(1), m.group(2)), (m.group(2), m.group(1))):
                if self._writers_in(body, e) or len(self._writers_in(body, p)) != 1:
                    continue
                pw = self.ins_at[self._writers_in(body, p)[0]]
                if self._step_of(pw, p) != 1 or self._cond(cmp):
                    continue
                if pw["addr"] > cmp["addr"]:               # stepped after the compare: count + 1 runs, not count
                    continue
                starts = {frozenset(self._writer_atoms(entry, w, p)) for w in self.reaching_writers(entry, L, p) if w is not None and w["addr"] not in body}
                if len(starts) != 1 or any(w is None for w in self.reaching_writers(entry, L, p)):
                    continue
                v = next(iter(starts))
                if len(v) != 1 or next(iter(v))[0] != "frame" or next(iter(v))[1] is None:
                    continue
                A = next(iter(v))[1]
                ew = [w for w in self.reaching_writers(entry, L, e)]
                if len(ew) != 1 or ew[0] is None or self._cond(ew[0]):
                    continue
                eo = ew[0]["ops"].replace(" ", "")
                me = re.fullmatch(r"(\w+),(\w+),(\w+)", eo)
                if not me or self._family(ew[0]) != "add" or me.group(1) != e:
                    continue
                base, cnt = None, None
                for x, y in ((me.group(2), me.group(3)), (me.group(3), me.group(2))):
                    if self._pinned_at(entry, ew[0]["addr"], x) == A:
                        base, cnt = x, y
                if base is None:
                    continue
                cws = self.reaching_writers(entry, ew[0]["addr"], cnt)
                if len(cws) != 1 or cws[0] is None or self._writers_in(body, cnt):
                    continue
                rng = self._reg_range(entry, ew[0]["addr"], cnt)
                if rng is None or not isinstance(rng[1], int) or rng[0] < 1:
                    continue
                out[br] = {"L": L, "p": p, "e": e, "count": (cnt, rng[0], rng[1], cws[0]["addr"]), "body": body, "A": A}
                break
        c[entry] = out
        return out

    def _copy_span(self, entry: int, at: int, reg: str):
        loops = self._copy_loops(entry)
        br, info = self._in_body(loops, at)
        if info is None:
            return None
        cnt, lo, hi, cdef = info["count"]
        ws = self._writers_in(info["body"], reg)
        if len(ws) != 1 or ws[0] != at:
            return None                                    # (used at its own step only)
        step = self._step_of(self.ins_at[at], reg)          # by opcode, direction and writeback
        if step not in (1, -1):
            return None
        starts = set()
        for w in self.reaching_writers(entry, at, reg):
            if w is None:
                return None
            if w["addr"] == at:
                continue
            v = self._writer_atoms(entry, w, reg)
            if len(v) == 1 and next(iter(v))[0] == "frame" and next(iter(v))[1] is not None:
                starts.add(("A", next(iter(v))[1]))        # a pinned frame slot
            else:                                          # or one plus the SAME count: add reg, base, cnt
                o = w["ops"].replace(" ", "")
                mm = re.fullmatch(r"(\w+),(\w+),(\w+)", o)
                if not mm or self._family(w) != "add":
                    return None
                ok = False
                for x, y in ((mm.group(2), mm.group(3)), (mm.group(3), mm.group(2))):
                    if y == cnt:
                        cws = self.reaching_writers(entry, w["addr"], cnt)
                        Ab = self._pinned_at(entry, w["addr"], x)
                        if len(cws) == 1 and cws[0] is not None and cws[0]["addr"] == cdef and Ab is not None:
                            starts.add(("A+c", Ab))
                            ok = True
                if not ok:
                    return None
        if len(starts) != 1:
            return None
        kind, A = next(iter(starts))
        # p (step +1 from A) runs A .. A + c - 1 over the c iterations; a pointer from A' + c stepping -1 (pre-indexed
        # by -1: the access at A' + c - 1 - k) covers A' .. A' + c - 1; one from A' stepping +1 covers the same
        if kind == "A" and step == 1:
            return (A, A + hi - 1, "a pointer stepped by the copy loop after a ÷10 digit loop")
        if kind == "A+c" and step == -1:
            return (A + 1, A + hi, "a pointer stepped back by the copy loop after a ÷10 digit loop")
        return None

    def _store_desc(self, entry: int, a: int) -> dict | None:
        """The bytes the store at `a` writes: {'cond', 'base' (the base's atoms), 'wild' (the offset from the base is
        not one known immediate), 'elems' [(offset from the base's value, bytes, the core register stored as that
        word or None)], 'data' (the registers stored)}. None when the instruction is not a store."""
        i = self.ins_at[a]
        fam = self._family(i)
        o = i["ops"].replace(" ", "")
        if not fam.startswith(("str", "stm", "push", "vst", "vpush")):
            return None
        d = {"cond": self._cond(i), "wild": False}
        if fam in ("push", "vpush"):
            regs = reglist(i["ops"])
            n = 4 * len(regs) if fam == "push" else vbytes(regs)
            d.update(base=self._base_atoms(entry, a, "sp"), data=regs if fam == "push" else [],
                     elems=[(4 * k - n, 4, r) for k, r in enumerate(regs)] if fam == "push" else [(-n, n, None)])
            return d
        if fam.startswith(("stm", "vstm")):
            m = re.match(r"(\w+)!?,\{", o)
            if not m:
                raise Finding(f"{self.name(entry)}: a store the model cannot read at {a:#x}: {i['mnem']} {i['ops']}")
            regs = reglist(i["ops"])
            core = fam.startswith("stm")
            n = 4 * len(regs) if core else vbytes(regs)
            up, down = fam in ("stm", "stmia", "stmea", "vstmia"), fam in ("stmdb", "stmfd", "vstmdb")
            lo = 0 if up else -n
            d.update(base=self._base_atoms(entry, a, m.group(1)), data=regs if core else [], wild=not (up or down),
                     elems=[(lo + 4 * k, 4, r) for k, r in enumerate(regs)] if core else [(lo, n, None)])
            return d
        m = re.search(r"\[(\w+)(?:,([^\]]+))?\](!?)(?:,(.+))?$", o)
        if not m:
            raise Finding(f"{self.name(entry)}: a store the model cannot read at {a:#x}: {i['mnem']} {i['ops']}")
        base, inner, post = m.group(1), m.group(2), m.group(4)
        B = set(self._base_atoms(entry, a, base))
        off = 0
        span = None                                            # (A1) a bounded index: [lo, hi] more from the base
        if inner is not None and inner.startswith("#"):
            off = int(inner[1:], 0)
        elif inner is not None:                                # a register index: anywhere from the base …
            ia = self._indexed_address(entry, a, base, inner)
            if ia is not None:                                 # … unless the index is bounded
                B, span, d["a1"] = set(ia[0]), (ia[1], ia[2]), "a register index bounded by " + ia[3]
            else:
                d["wild"] = True
                for r in self._regs(inner):
                    B |= self._derived(self._base_atoms(entry, a, r))
        if span is None and (inner is None or inner.startswith("#")) and any(x == ("der", "frame") or (x[0] == "frame" and x[1] is None) for x in B):
            ls = self._loop_frame_span(entry, a, base)         # a pointer stepped by a ÷10 digit loop / its copy loop
            if ls is not None:
                B, span, d["a1"] = {("frame", ls[0])}, (0, ls[1] - ls[0]), ls[2]
        if span is None and (inner is None or inner.startswith("#")):
            ca = self._computed_address(entry, a, base)        # the address computed before the store
            if ca is not None and not (B and all(x[0] in ("frame", "const", "arg", "argo", "tab", "crange") for x in B)):
                B, span, d["a1"] = set(ca[0]), (ca[1], ca[2]), "an address computed from an index bounded by " + ca[3]
        if post is not None and not post.startswith("#"):
            d["wild"] = True
        data = self._regs(o.split("[")[0])
        if fam == "strd" and len(data) == 1:
            data.append(self._next_reg(data[0]))
        if fam == "str":
            elems = [(off, 4, data[0])]
        elif fam == "strd":
            elems = [(off, 4, data[0]), (off + 4, 4, data[1])]
        elif fam.startswith("vstr"):
            elems = [(off, 8, None)]
            data = []
        elif fam in self.STORE_BYTES:
            elems = [(off, self.STORE_BYTES[fam], None)]
            data = data[-1:]
        else:
            raise Finding(f"{self.name(entry)}: a store the model does not know at {a:#x}: {i['mnem']} {i['ops']}")
        if span is not None:                                   # one element spanning every index: not a word store
            lo, hi = span                                      # of one register (a cell overlapping it is 'may')
            n = max(e[0] + e[1] for e in elems) - min(e[0] for e in elems)
            first = min(e[0] for e in elems)
            if first + lo < 0 or (isinstance(hi, int) and first + hi + n > 0xFFFFFFFF):
                d["wild"] = True
                d.pop("a1", None)
            else:                                              # the count: hi - lo + width — a form when hi is one
                elems = [(first + lo, self._lin_add(hi, n - lo), None)]
        d.update(base=frozenset(B), data=data, elems=elems)
        return d

    def _store_effect(self, entry: int, a: int, slot: int):
        """How the instruction at `a` bears on the word at frame slot `slot`: None (not a store, or provably other
        bytes / not this frame), ('exact', register, conditional) or ('may', the description)."""
        d = self._store_desc(entry, a)
        if d is None:
            return None
        B = d["base"]
        fr = [x for x in B if x[0] == "frame"]
        loose = ("der", "frame") in B
        if not fr and not loose:
            return None
        if d["wild"] or loose or len(B) != 1 or fr[0][1] is None:
            return ("may", d)
        A = fr[0][1]
        hit = [(A + off, n, r) for off, n, r in d["elems"] if A + off < slot + 4 and (not isinstance(n, int) or slot < A + off + n)]
        if not hit:
            return None
        if len(hit) == 1 and hit[0][0] == slot and hit[0][1] == 4 and hit[0][2] is not None:   # (an int: a register's word)
            return ("exact", hit[0][2], d["cond"])
        return ("may", d)

    @staticmethod
    def _is_call(i: dict) -> bool:
        return base_mnem(i["mnem"])[0] in ("bl", "blx")

    def _walk_kinds(self, entry: int) -> dict[int, str]:
        """Per instruction of the routine, what a backward slot walk must look at: 'store', 'call' or ''."""
        c = self._cache("_walk_kind_cache")
        if entry not in c:
            c[entry] = {i["addr"]: ("store" if self._family(i).startswith(("str", "stm", "push", "vst", "vpush"))
                                    else "call" if self._is_call(i) else "") for i in self.region(entry)}
        return c[entry]

    def _slot_compute(self, entry: int, at: int, slot: int) -> set:
        unset = {("arg", ("stk", slot))} if slot >= 0 else {("other",)}     # nothing stored: an incoming stack
        out: set = set()                                                    # word, or an uninitialised local
        if at == entry:
            out |= unset
            if slot < 0:
                self._blocked(entry, slot, at, "a path from the routine's entry with no store to the slot (uninitialised there)", at)
        pred = self._rpred(entry)
        kind = self._walk_kinds(entry)
        loose = self._frame_leaks(entry)                   # an address of the frame is out: any call, and any store
        seen: set = set()                                  # through a pointer that is not this frame's, may write it
        stack = list(pred.get(at, []))
        while stack:
            a = stack.pop()
            if a in seen:
                continue
            seen.add(a)
            eff = self._store_effect(entry, a, slot) if kind[a] == "store" else None
            if loose and (kind[a] == "call" or (kind[a] == "store" and eff is None
                                                and not all(x[0] == "frame" or (x[0] == "const" and not self._in_stacks(x[1]))
                                                            for x in self._store_desc(entry, a)["base"]))):
                out |= {("other",), ("der", "frame")}      # (through a pointer that may be the leaked address)
                self._blocked(entry, slot, a, "an address of this frame has left it (" + str(self._cache("_leaks").get(self.name(entry), "it leaks")) + "): this may write through it", at)
            if eff is not None and eff[0] == "may":         # it may write the word, or part of it, or not: the unknown
                out.add(("other",))                        # AND whatever was there before
                self._blocked(entry, slot, a, "a store that may write the slot or part of it (partial, overlapping, indexed, conditional base or an unpinned frame address)", at)
                for r in eff[1]["data"]:
                    out |= self._derived(self._base_atoms(entry, a, r))
            elif eff is not None:
                out |= self._base_atoms(entry, a, eff[1])
                if not eff[2]:
                    continue                               # an unconditional definition: nothing older survives
            elif kind[a] == "store":                       # a store that is not into this frame: WHERE it lands must
                why = self._store_off_frames(entry, a)     # be shown — no object provenance is assumed
                if why is not None:
                    out.add(("other",))
                    self._blocked(entry, slot, a, "a store " + why, at)
            elif kind[a] == "call":
                left = self._call_may_write(entry, a, slot)
                if left is not None:                       # (the callee MAY write it: the older value stays possible)
                    out |= left
                    self._blocked(entry, slot, a, "a call that may write the slot through a pointer it is handed, or its incoming stack words", at)
                for why in self._call_blockers(entry, a):  # … and every write under the call, wherever it points
                    out.add(("other",))
                    self._blocked(entry, slot, a, "a call " + why, at)
            if a == entry:
                out |= unset
                if slot < 0:
                    self._blocked(entry, slot, a, "a path from the routine's entry with no store to the slot (uninitialised there)", at)
            stack += pred.get(a, [])
        return out

    # ---- a frame cell and the writes of its window (the owner's ruling of 2026-10-06 on the frame unit)
    #
    # The word at a frame slot is what was last stored there only if NOTHING ELSE can have written it between that
    # store and the read. Object provenance (the old B1: "a pointer derived from another object does not reach this
    # frame") is no longer assumed. On every path from the store to the read (the SYNCHRONOUS paths: what an
    # exception taken in between may write is not covered, see VALUE_MODEL):
    #   a store of the routine that is not into this frame must be PLACED (`_write_reach`) off every frame: a
    #       constant range outside the stacks' region; through its own argument, when every caller's pointer for it
    #       is so placed or is an address inside that caller's own frame (`_arg_landing`);
    #   a call must be unable to write the slot through what it is handed (`_call_may_write`, as before), every
    #       other pointer it is handed that the callee writes through must be so placed, and EVERY write of every
    #       routine the call can reach — the context-free union of every indirect call's target set — must be
    #       placed: inside its own routine's frame (never the incoming stack-argument area, which is the caller's),
    #       a constant range outside the stacks, or through an argument (then it lands where a hand-over above it,
    #       itself checked, points). One that is not placed, a frame range that leaves its frame, a target set that
    #       does not resolve: the cell is unknown, and what blocked it is recorded (`_blocked`).

    def _blocked(self, entry: int, slot: int, at: int, why: str, read: int | None = None) -> None:
        stage = self.__dict__.get("_blk_stage")
        if stage:                                          # inside a solver round: kept only if the round converges
            stage[-1].append((entry, slot, at, why, read))
        else:
            self._blocked_commit([(entry, slot, at, why, read)])

    def _blocked_commit(self, recs) -> None:
        for entry, slot, at, why, read in recs:
            self._cache("_cellblk").setdefault((entry, slot), set()).add((at, why))
            if read is not None:                           # (… and against the one read the walk started from)
                self._cache("_cellblk_at").setdefault((entry, slot, read), set()).add((at, why))

    def _blockers_text(self, entry: int, slot: int, at: int | None = None, most: int = 3) -> str:
        """What the slot walk recorded against the cell at the read `at` (against any read, when no read is named),
        for a Finding's text: the first few, by address."""
        bl = sorted(self._cache("_cellblk_at").get((entry, slot, at), ()) if at is not None else self._cache("_cellblk").get((entry, slot), ()))
        if not bl:
            return ""
        return (f" — slot {slot:#x} blocked by: " + "; ".join(f"at {a:#x} {why}" for a, why in bl[:most])
                + (f" (and {len(bl) - most} more)" if len(bl) > most else ""))

    def _reach_blocks_frames(self, reach):
        """Why a write with `reach` is not shown to miss every frame; None when it is (an own-frame range and one
        placed at the callers are the business of whoever asks)."""
        span = self._stack_span()
        for r in reach:
            if r[0] == "unknown":
                return "that is not placed (" + r[1] + ")"
            if r[0] == "abs" and len(r) == 3:
                if span is None:
                    return f"at the constant range {r[1]:#x}..{r[2]:#x}, in an image that names no stacks' region"
                if r[1] < span[1] and span[0] < r[2]:
                    return f"at the constant range {r[1]:#x}..{r[2]:#x}, inside the stacks' region"
        return None

    def _callers(self, R: int) -> list:
        """[(caller, site)]: every call or tail the analysis reads that can enter R (an application-pointer call
        enters every application callback)."""
        idx = self.__dict__.get("_callers_cache")
        if idx is None:
            idx = {}
            try:
                app = list(self.rule_targets("app_function_pointers"))
            except Finding:
                app = []
            for Q in self._code_routines():
                self.analyse(Q)
                sets = {int(e["site"], 16): e.get("set") for e in self.edges.get(Q, []) if e["kind"] in ("indirect_call", "indirect_tail")}
                for site, tgt in self._transfers(Q).items():
                    for t in ([tgt] if tgt is not None else (app if sets.get(site) == "app_function_pointers" else [])):
                        idx.setdefault(t, []).append((Q, site))
            self.__dict__["_callers_cache"] = idx
        return idx.get(R, [])

    def _arg_landing(self, R: int, n):
        """Why a write of R through its argument `n` (0–3, ('stk', k), or 'incoming': into its incoming stack words)
        is not shown to land off every frame cell but its callers' own; None when at every call that enters R the
        pointer handed there is placed — a constant range outside the stacks, an address inside that caller's own
        frame, or the caller's own argument (then its callers', and so on)."""
        return self._guarded("argland", (R, n), self._arg_landing_compute, None)

    def _arg_landing_compute(self, R: int, n):
        if not self._args_followed(R):
            return f"{self.name(R)} is entered other than by a call whose arguments are read"
        for Q, site in self._callers(R):
            items = [(what, reach, m) for a, what, reach, m in self._write_sites(Q) if a == site and m.get("pos") == n]
            if not items:
                return f"{self.name(Q)}'s call at {site:#x} shows no hand-over for it"
            for what, reach, m in items:
                why = self._reach_blocks_frames(reach)
                if why is not None:
                    return f"{self.name(Q)} {what} at {site:#x}, {why}"
                if any(r[0] == "args" for r in reach):     # the caller's own argument (or its incoming area) passed on
                    ups = {x[1] for x in m.get("atoms", ()) if x[0] in ("arg", "argo")} or {"incoming"}
                    for up in sorted(ups, key=str):
                        why = self._arg_landing(Q, up)
                        if why is not None:
                            return why
        return None

    def _store_off_frames(self, R: int, a: int):
        """Why the store at `a` of routine R, which is not into R's frame at a pinned place, is not shown to miss
        every frame cell; None when it is."""
        d = self._store_desc(R, a)
        ext = "ALL" if d["wild"] else frozenset((off, nb) for off, nb, _r in d["elems"])
        reach = self._write_reach(R, d["base"], ext, False)
        why = self._reach_blocks_frames(reach)
        if why is not None:
            return why
        if any(r[0] == "args" for r in reach):
            for up in sorted({x[1] for x in d["base"] if x[0] in ("arg", "argo")} or {"incoming"}, key=str):
                why = self._arg_landing(R, up)
                if why is not None:
                    return "through its argument, and " + why
        return None

    def _under(self, t: int) -> tuple:
        """(the routines a call of `t` can reach, `t` included — over every edge, an indirect one by its rule's whole
        target set, context-free; the reasons a target set under it does not resolve)."""
        c = self._cache("_under_cache")
        if t not in c:
            seen, notes, todo = set(), [], [t]
            while todo:
                q = todo.pop()
                if q in seen or q not in self.ins_at or q not in self.func_entries:
                    continue
                seen.add(q)
                try:
                    self.analyse(q)
                except Finding as f:
                    notes.append(f"{self.name(q)} cannot be read: {f}")
                    continue
                for e in self.edges.get(q, []):
                    try:
                        todo += [x for x in self.targets(e) if x is not None]
                    except Finding as f:
                        notes.append(f"{self.name(q)}'s indirect call at {e.get('site')} has no resolved target set: {f}")
            c[t] = (frozenset(seen), tuple(notes))
        return c[t]

    def _frame_blockers(self, Q: int) -> tuple:
        """The writes of routine Q that are not shown to miss every frame but Q's own: ((address, what, why), …)."""
        return self._fixed("wblock", Q, self._frame_blockers_compute, ())

    def _frame_blockers_compute(self, Q: int) -> tuple:
        out = []
        for a, what, reach, _m in self._write_sites(Q):
            why = self._reach_blocks_frames(reach)
            if why is not None:
                out.append((a, what, why))
        return tuple(out)

    def _under_blockers(self, t: int) -> tuple:
        """What stands under a call of `t`: ((routine name, its blocking writes' count, the first as text), …) for
        every routine it can reach that has one, and a line per unresolved target set."""
        return self._fixed("ublock", t, self._under_blockers_compute, ())

    def _under_blockers_compute(self, t: int) -> tuple:
        routines, notes = self._under(t)
        out = [("", 0, n) for n in notes]
        for Q in sorted(routines):
            bl = self._frame_blockers(Q)
            if bl:
                a, what, why = bl[0]
                out.append((self.name(Q), len(bl), f"{what} at {a:#x}, {why}"))
        return tuple(out)

    def _call_blockers(self, entry: int, a: int) -> list:
        """Why the call at `a` of `entry` is not shown unable to write a frame cell of `entry` OTHER than through a
        frame address it is handed (that is `_call_may_write`'s): every other pointer it is handed that the callee
        writes through, and every write of every routine it can reach."""
        out = []
        tgt = self._call_target(self.ins_at[a])
        whom = self.name(tgt) if tgt is not None else "through a pointer"
        for pos, atoms, (w, _ind, _keep) in self._handed(entry, a):
            rest = frozenset(x for x in atoms if not (x[0] == "frame" or x == ("der", "frame")))
            if not w or (atoms and not rest):
                continue                                   # (a frame address: held against the slot itself)
            reach, _m = self._handed_reach(entry, a, pos, rest, w, False)
            why = self._reach_blocks_frames(reach)
            if why is None and any(r[0] == "args" for r in reach):
                for up in sorted({x[1] for x in rest if x[0] in ("arg", "argo")}, key=str):
                    why = why or self._arg_landing(entry, up)
            if why is not None:
                out.append(f"({whom}) handed {'r%d' % pos if isinstance(pos, int) else pos}, which the callee writes through, {why}")
        if tgt is not None:
            targets = [tgt]
        else:
            targets = []
            for e in self.edges.get(entry, []):
                if e.get("site") == f"{a:#x}" and e["kind"] in ("indirect_call", "indirect_tail"):
                    try:
                        targets = [x for x in self.targets(e) if x is not None]
                    except Finding as f:
                        out.append(f"through a pointer whose target set does not resolve: {f}")
        under: dict = {}
        first = None
        for t in targets:
            for name, n, text in self._isolated(self._under_blockers, t):
                if not name:
                    out.append(f"({whom}) under which {text}")
                elif name not in under:
                    under[name] = n
                    first = first or f"{name} {text}"
        if under:
            names = sorted(under)
            out.append(f"({whom}) under which {len(names)} routine(s) have a write that is not shown to miss a frame: "
                       + ", ".join(f"{x} ({under[x]})" for x in names[:8]) + (f" and {len(names) - 8} more" if len(names) > 8 else "")
                       + f"; the first, {first}")
            self._cache("_callunder")[(entry, a)] = under
        return out

    def frame_cells(self) -> list:
        """Every frame slot of every routine in the image that a load may find holding a callback, the address of a
        read-only callback table, or an incoming argument the routine uses to reach a callback (calls it, calls a
        field of it, or hands it on): [{routine, slot, holds, resolved, blocked_by}]. `resolved`: at every read
        that may see such a value the slot holds nothing else. `blocked_by`: what the slot walk recorded against
        those reads — each with its address, and for a call the routines under it with unplaced writes."""
        for R in self._code_routines():                    # every routine's loads are evaluated, walked or not:
            try:                                           # its hand-overs (the write sites) and its indirect calls
                self._write_sites(R)
                for e in self.edges.get(R, []):
                    if e["kind"] in ("indirect_call", "indirect_tail") and e.get("site"):
                        a = int(e["site"], 16)
                        regs = self._regs(self.ins_at[a]["ops"])
                        if regs:
                            self._raw_reg(R, a, regs[0])
            except Finding:
                pass
        cells: dict = {}
        for key, v in list(self._pt_eval_memo.items()):
            if key[0] != "slot":
                continue
            _k, entry, at, slot = key
            try:
                needs = self._pointsto(entry).get("needs", frozenset())
            except Finding:
                needs = None
            holds = set()
            for x in v:
                if x[0] == "cb":
                    holds.add("a callback")
                elif x[0] == "tab":
                    holds.add("a read-only table's address")
                elif x[0] == "arg" and (needs is None or x[1] in needs):
                    holds.add("an argument the routine reaches a callback through")
            if not holds:
                continue
            c = cells.setdefault((entry, slot), {"holds": set(), "mixed": {}, "reads": 0})
            c["holds"] |= holds
            c["reads"] += 1
            if not all(x[0] in ("cb", "arg") or (x[0] == "tab" and x[2] is not None) for x in v):
                c["mixed"][at] = v
        out = []
        for (entry, slot), c in sorted(cells.items(), key=lambda kv: (self.name(kv[0][0]), kv[0][0], kv[0][1])):
            blocked = []
            for at in sorted(c["mixed"]):
                for a, why in sorted(self._cache("_cellblk_at").get((entry, slot, at), ())):
                    b = {"at": f"{a:#x}", "why": why}
                    if (entry, a) in self._cache("_callunder") and "under which" in why:
                        b["under"] = dict(sorted(self._cache("_callunder")[(entry, a)].items()))
                    if b not in blocked:
                        blocked.append(b)
                if not self._cache("_cellblk_at").get((entry, slot, at)):
                    b = {"at": f"{at:#x}", "why": "at this read the slot may hold " + ", ".join(sorted({x[0] for x in c["mixed"][at]}))
                                                 + " — nothing in its own window blocks it: a value stored there was itself not resolved"}
                    if b not in blocked:
                        blocked.append(b)
            out.append({"routine": self.name(entry), "slot": slot, "holds": sorted(c["holds"]), "reads": c["reads"],
                        "resolved": not c["mixed"], "blocked_by": blocked})
        return out

    # ---- what a callee may do with a pointer it is handed (the owner's HOLD on 1e55967: nothing outside the model
    # is assumed away — it is summarised, or it is the unknown)
    #
    # For argument n (0–3, or ('stk', A)) of a routine, `_arg_summary` gives (writes, ind, keep):
    #   writes  the byte ranges, as SIGNED offsets from the pointer, it — or anything it hands the pointer on to — may
    #           store through it: None, a set of (offset, bytes), or 'ALL';
    #   ind     the offsets of the WORDS it loads through the pointer and then stores through, keeps or hands to a
    #           routine that does (a pointer reached through the object): None, a set of offsets, or 'ALL';
    #   keep    where it may leave the pointer (or one derived from it) as a stored WORD: None, or a set of (m, off) —
    #           the word at its argument m + off, i.e. in an object the caller handed it — and 'EXT', anywhere else.
    # A routine compiled into the image is read; a prebuilt one is EVERYTHING unless it is one of LIBC_CONTRACTS; an
    # indirect call is the union over the application callbacks when that is its target set, else EVERYTHING.
    #
    # The caller's side (`_call_may_write`): every pointer the call is handed — the four argument registers; for a
    # readable callee the stack words it reads; for an unknown one EVERY word of the caller's frame that may hold an
    # address — is held against the callee's summary: 'ALL' writes reach any slot (no direction is assumed), ranges
    # reach what they overlap, an `ind` offset reaches everything when the word there may be a frame address. A
    # pointer the callee keeps IN an object of the caller's frame is then what that slot holds; a frame address stored
    # outside the frame, or kept by a callee anywhere but in the caller's own frame, LEAKS: nothing about the
    # routine's frame is known any more (`_frame_leaks`), and a callback read from it is a Finding.

    NOTHING = (None, None, None)
    EVERYTHING = ("ALL", "ALL", frozenset({"EXT"}))
    POINTERISH = ("frame", "der", "arg", "argo", "ind")

    @staticmethod
    def _merge(x, y):
        if x == "ALL" or y == "ALL":
            return "ALL"
        if x is None or y is None:
            return y if x is None else x
        return frozenset(x) | frozenset(y)

    def _merge3(self, s, x) -> tuple:
        """Two summaries joined (the writes, the loaded-pointer extents, the keeps)."""
        if s[1] == "ALL" or x[1] == "ALL":
            ind = "ALL"
        else:
            d: dict = {}
            for off, ext in set(s[1] or ()) | set(x[1] or ()):
                d.setdefault(off, set()).update({ext} if isinstance(ext, str) else ext)
            ind = self._ind_norm(d)
        return (self._merge(s[0], x[0]), ind, self._merge(s[2], x[2]))

    def _call_target(self, i: dict) -> int | None:
        bt = branch_target(i["ops"]) if base_mnem(i["mnem"])[0] in ("bl", "blx", "b") else None
        return bt[0] if bt else None

    def _cstring(self, addr: int) -> str | None:
        """The NUL-terminated string at `addr`, when it lies in a read-only section of the image (.rodata / .text)."""
        for sec in self.secs:
            if sec["name"] in (".rodata", ".text") and sec["addr"] <= addr < sec["addr"] + sec["size"]:
                o = sec["offset"] + addr - sec["addr"]
                end = self.blob.find(b"\0", o, sec["offset"] + sec["size"])
                return self.blob[o:end].decode("latin-1") if end >= 0 else None
        return None

    @staticmethod
    def format_writes(fmt: str) -> bool:
        """Whether a printf format may WRITE through one of its arguments: anything but plain text and the reading
        conversions d i o u x X c s p e E f F g G a A and %% (with flags, width, precision, length) — so a %n in any
        dress, an unfinished specification and an unknown conversion all count as writing."""
        k = 0
        while True:
            k = fmt.find("%", k)
            if k < 0:
                return False
            m = re.match(r"%[-+ #0']*(?:\*|\d+)?(?:\.(?:\*|\d+)?)?(?:hh|h|ll|l|L|j|z|t|q)?[diouxXcspeEfFgGaA%]", fmt[k:])
            if not m:                                      # %n, or anything that is not a known reading conversion
                return True
            k += m.end()

    def _printf_safe(self, entry: int, a: int, fidx: int) -> bool:
        """The printf-family call at `a` cannot write through a format argument: its format (argument `fidx`) is, on
        every path, a constant string of a read-only section with no %n; or it is the routine's own argument
        forwarded unchanged, the routine is not address-taken, and EVERY call of the routine passes such a constant.
        Anything else is not proved, and the call is then taken to write through any pointer it can see."""
        # While the format is being evaluated the evaluation may come back to this very call (the format sits in a
        # frame slot that this call could only disturb through a %n): it is then taken as proved — if every such
        # call's format is constant and free of %n ON THAT ASSUMPTION, no call is the first to write, so none does.
        return self._guarded("printf", (entry, a, fidx), self._printf_compute, (True, None))[0]

    def _reg_pathwise(self, entry: int, at: int, reg: str) -> frozenset:
        """`reg` just before `at`, its conditional writes CORRELATED: over the straight run that ends at `at` (no
        branch enters it, nothing transfers out unconditionally), each path decides every condition once and keeps
        the decision until an instruction may set the flags — so `movwge r2 / movtge r2` never pairs with
        `movwlt r2`. A write the run does not model, or a value from before the run, is its reaching-definition
        value."""
        self.analyse(entry)
        region = self.region(entry)
        addrs = [i["addr"] for i in region]
        if at not in addrs:
            return self._raw_reg(entry, at, reg)
        targets = self.branch_targets_of(entry)
        k = addrs.index(at)
        start = k
        while start > 0:                                   # back to the run's first instruction
            if addrs[start] in targets:
                break
            i = region[start - 1]
            b, cond = base_mnem(i["mnem"])
            if (b in ("b", "bx") and not cond) or b in ("cbz", "cbnz", "tbb", "tbh") or i["mnem"] == ".data" \
                    or (b in ("pop", "ldm", "ldmia", "ldmfd") and "pc" in i["ops"]):
                break
            start -= 1
        paths = [(frozenset(), None)]                      # (decisions, reg's value — None: as on entry to the run)
        for i in region[start:k]:
            nxt = []
            for known, val in paths:
                c = cond_of(i["mnem"]) if self._cond(i) else None
                for executes, kn in ([(True, known)] if c is None else self._decide(c, known)):
                    v = val
                    if executes and reg in self.written(i):
                        if self._family(i) == "movt" and ",#" in i["ops"].replace(" ", ""):
                            lo = val if val is not None else self._raw_reg(entry, i["addr"], reg)
                            v = frozenset(self._const_atom((imm(i["ops"]) << 16) | (x[1] & 0xFFFF)) if x[0] == "const"
                                          else ("other",) for x in lo)
                            v = frozenset(("cb", x[1] & ~1) if x[0] == "const" and (x[1] & ~1) in self.label_at and
                                          self.unit_of(x[1] & ~1) in self.APP_UNITS else x for x in v)
                        elif self._family(i) in ("movw", "mov", "movs") and re.fullmatch(r"\w+,#(?:0x[0-9a-f]+|\d+)", i["ops"].replace(" ", "")):
                            v = frozenset({("const", imm(i["ops"]))})
                        else:
                            v = frozenset(self._writer_atoms(entry, i, reg))
                    nxt.append((frozenset() if executes and sets_flags(i) else kn, v))
            paths = list(set(nxt))
            if len(paths) > 64:
                return self._raw_reg(entry, at, reg)
        out: set = set()
        for _kn, v in paths:
            out |= v if v is not None else self._raw_reg(entry, region[start]["addr"], reg)
        return frozenset(out)

    def _printf_compute(self, entry: int, a: int, fidx: int) -> tuple:

        def constant(R, at, reg):
            atoms = self._isolated(self._reg_pathwise, R, at, reg)
            if not atoms or any(x[0] != "const" for x in atoms):
                return None
            strs = [self._cstring(x[1]) for x in atoms]
            return None if any(s is None for s in strs) else sorted(strs)
        fmts = constant(entry, a, f"r{fidx}")
        how = "constant"
        if fmts is None:
            atoms = self._isolated(self._raw_reg, entry, a, f"r{fidx}")
            if len(atoms) == 1 and next(iter(atoms))[0] == "arg" and isinstance(next(iter(atoms))[1], int) \
                    and entry not in getattr(self, "address_taken", ()):
                m = next(iter(atoms))[1]
                sites = self.direct_sites(entry)
                each = [constant(o, s, f"r{m}") for o, s, _k in sites]
                if sites and all(e is not None for e in each):
                    fmts = sorted({s for e in each for s in e})
                    how = f"argument {m} of {self.name(entry)}, a constant at each of its {len(sites)} call sites"
        ok = fmts is not None and not any(self.format_writes(s) for s in fmts)
        return (ok, {"call": f"{self.name(entry)} {a:#x} {self.name(self._call_target(self.ins_at[a]))}",
                     "format": how if fmts is not None else "NOT a provable constant", "formats": fmts or [], "no_percent_n": ok})

    def _indirect_targets(self, entry: int, a: int):
        """The routines the indirect call at `a` may reach, for the callee summaries: None when it is not an
        application-pointer call (the unknown); else the callbacks the called pointer can be over EVERY caller of
        the routine (`_site_callbacks` — context-insensitive, so a superset of what any one path resolves), or, when
        that cannot be told, every application callback."""
        sets = {e.get("set") for e in self.edges.get(entry, []) if e.get("site") == f"{a:#x}"}
        if sets != {"app_function_pointers"}:
            return None
        # (the owner's ruling of 2026-10-06 on the frame unit) the CONTEXT-FREE union, always: what a call may
        # write decides whether a frame cell stands, and the pointer it calls through may itself come from such a
        # cell — a target set narrowed by the cell's own (optimistic) value would vouch for itself
        return list(self.rule_targets("app_function_pointers"))

    def _site_callbacks(self, entry: int, a: int):
        if (self.unit_of(entry) or "") not in self.APP_UNITS:
            return None
        rT = self._regs(self.ins_at[a]["ops"])[0]
        try:
            r = self._pt_read(entry, a, rT)
        except Finding:
            return None
        if r[0] == "VAL":
            return self._atoms_callbacks(entry, r[1])
        return self._arg_field_callbacks(entry, r[0], r[1])

    def _callers_values(self, entry: int, n):
        """What every direct caller hands the routine as argument n: [(caller, site, atoms)], or None when the routine
        can be entered any other way (address-taken, or no caller is seen)."""
        if entry in self.address_taken or n is None:
            return None
        sites = self.direct_sites(entry)
        out = []
        for o, s, _k in sites:
            self.analyse(o)
            if isinstance(n, int):
                atoms = self._pt_eval(o, s, f"r{n}")
            else:
                sp = self._pt_slot(o, s, 0)
                if sp is None:
                    return None
                atoms = self._slot_atoms(o, s, sp + n[1])
            out.append((o, s, atoms))
        return out or None

    def _atoms_callbacks(self, R: int, atoms):
        out = set()
        for x in atoms:
            if x[0] == "cb":
                out.add(x[1])
            elif x[0] == "arg":
                sub = self._guarded("argcb", (R, x[1]), self._arg_callbacks, frozenset())
                if sub is None:
                    return None
                out |= sub
            else:
                return None
        return frozenset(out)

    def _arg_callbacks(self, entry: int, n):
        vals = self._callers_values(entry, n)
        if vals is None:
            return None
        out = set()
        for o, _s, atoms in vals:
            sub = self._atoms_callbacks(o, atoms)
            if sub is None:
                return None
            out |= sub
        return frozenset(out)

    def _arg_field_callbacks(self, entry: int, n, off: int):
        return self._guarded("fieldcb", (entry, n, off), self._arg_field_compute, frozenset())

    def _arg_field_compute(self, entry: int, n, off: int):
        vals = self._callers_values(entry, n)
        if vals is None:
            return None
        out = set()
        for o, s, atoms in vals:
            for x in atoms:
                if x[0] == "frame" and x[1] is not None:
                    sub = self._atoms_callbacks(o, self._slot_atoms(o, s, x[1] + off))
                elif x[0] == "tab" and x[2] is not None:
                    try:
                        sub = frozenset(self._ro_field(x[1] + x[2] + off, "a field read"))
                    except Finding:
                        sub = None
                elif x[0] == "arg":
                    sub = self._arg_field_callbacks(o, x[1], off)
                else:
                    sub = None
                if sub is None:
                    return None
                out |= sub
        return frozenset(out)

    # ---- read-only callback tables (2026-10-05: b3_app.c's I/O tables are `static const`, in .rodata)
    #
    # A pointer into a table is followed by PROVENANCE (a ('tab', T, offset) atom, born only where the table's address
    # is materialised and kept through arithmetic and copies), on the same footing as a frame address: a pointer
    # derived from another object — a global, another frame — is taken not to reach the table (see VALUE_MODEL).
    # A callback read from a field of a table in .rodata is the table's word in the ELF — provided the image shows
    # nothing can write the table (`_ro_table_proof`): its address (any address inside it) is materialised only by the
    # image's own units, by movw / movt or a literal-pool load, and appears in no other loaded word; in every routine
    # that materialises it, no store's base may point into it, it is never stored outside the routine's own frame
    # nor returned, and every call (or tail) it is handed to — with everything that callee hands it on to — writes
    # nothing through it and keeps nothing (`_arg_summary`). A failed proof is a Finding.

    def _ro_tables(self) -> dict:
        """start -> (name, size): the .rodata data symbols holding at least one application callback."""
        if "_ro_tables_cache" in self.__dict__:
            return self._ro_tables_cache
        rod = [s for s in self.secs if s["name"] == ".rodata"]
        out = {}
        for name, (v, size, typ) in self.syms.items():
            if typ not in ("r", "R") or not size or not any(s["addr"] <= v and v + size <= s["addr"] + s["size"] for s in rod):
                continue
            if any(((self.words.get(v + k) or 0) & ~1) in self.label_at and self.unit_of((self.words.get(v + k) or 0) & ~1) in self.APP_UNITS
                   for k in range(0, size - 3, 4)):
                out[v] = (name, size)
        self._ro_tables_cache = out
        return out

    def _ro_table_of(self, addr: int):
        for v, (name, size) in self._ro_tables().items():
            if v <= addr < v + size:
                return v
        return None

    def _ro_field(self, addr: int, what: str) -> set:
        """The callback at `addr`, a word of a read-only table proved unwritable. A Finding otherwise."""
        T = self._ro_table_of(addr)
        if T is None:
            raise Finding(f"{what}: {addr:#x} is not in a read-only callback table")
        why = self._guarded("roproof", T, self._ro_table_proof, None)
        if why is not None:
            raise Finding(f"{what}: the read-only table {self._ro_tables()[T][0]} may be written: {why}")
        w = self.words.get(addr)
        if addr & 3 or w is None or (w & ~1) not in self.label_at or self.unit_of(w & ~1) not in self.APP_UNITS:
            raise Finding(f"{what}: the word at {addr:#x} ({self._ro_tables()[T][0]}+{addr - T:#x}) is not an application callback ({w!r})")
        self._cache("_ro_reads")[(self._ro_tables()[T][0], addr - T)] = self.name(w & ~1)
        return {w & ~1}

    def _ro_table_proof(self, T: int):
        """None when nothing in the image can write the table at T; else the reason (see the block comment)."""
        name, size = self._ro_tables()[T]
        inside = lambda v: T <= v < T + size
        text = [s for s in self.secs if s["name"] in (".text", ".init", ".fini")]
        intext = lambda a: any(s["addr"] <= a < s["addr"] + s["size"] for s in text)
        for a, w in self.words.items():                    # a stored address: only in a literal pool of the code
            if inside(w) and not intext(a):
                return f"its address is a data word at {a:#x}"
        users = set()
        for fname, ins in self.funcs.items():
            if not ins:
                continue
            lo: dict = {}
            for i in ins:
                o = i["ops"].replace(" ", "")
                fam = self._family(i)
                hit = False
                if fam == "movw" and ",#" in o:
                    lo[o.split(",")[0]] = imm(o)
                elif fam == "movt" and ",#" in o:
                    hit = inside((imm(o) << 16) | lo.get(o.split(",")[0], 0))
                elif fam == "ldr" and re.fullmatch(r"\w+,\[pc,#-?\w+\]", o):
                    lit = ((i["addr"] + 4) & ~3 if i["thumb"] else i["addr"] + 8) + imm(o)
                    hit = inside(self.words.get(lit, 0))
                elif base_mnem(i["mnem"])[0] in ("add", "adr") and re.fullmatch(r"\w+,pc,#-?\w+", o):
                    hit = inside(((i["addr"] + 4) & ~3 if i["thumb"] else i["addr"] + 8) + imm(o))
                if hit:
                    owner = max(x for x in self.func_entries if x <= i["addr"])
                    if (self.unit_of(owner) or "") not in self.APP_UNITS:
                        return f"its address is materialised outside the image's units, in {self.name(owner)}"
                    users.add(owner)
        if not users:
            return "its address is never materialised (a field read of it cannot be placed)"
        mine = lambda atoms: any(x[0] == "tab" and x[1] == T for x in atoms)   # a pointer derived from the table
        for R in sorted(users):
            self.analyse(R)
            for i in self.region(R):
                a = i["addr"]
                if a not in self.sp_at.get(R, {}):
                    continue
                kind = self._walk_kinds(R)[a]
                b = base_mnem(i["mnem"])[0]
                tgt = self._call_target(i)
                if kind == "store":
                    d = self._store_desc(R, a)
                    if mine(d["base"]):
                        return f"{self.name(R)} stores through it at {a:#x}"
                    if any(mine(self._base_atoms(R, a, r)) for r in d["data"]) and not all(x[0] == "frame" for x in d["base"]):
                        return f"{self.name(R)} stores it outside its frame at {a:#x}"
                elif kind == "call" or (b == "b" and tgt is not None and tgt in self.func_entries and tgt != R):
                    for pos, atoms, (w, _ind, keep) in self._handed(R, a):
                        if mine(atoms) and (w is not None or keep is not None):
                            return (f"{self.name(R)} hands it at {a:#x} ({pos}) to "
                                    f"{self.name(tgt) if tgt else 'an indirect call'}, which may write through it or keep it")
                elif b == "bx" or (b in ("pop", "ldmia", "ldmfd", "ldm") and "pc" in i["ops"]):
                    if mine(self._raw_reg(R, a, "r0")):
                        return f"{self.name(R)} returns it at {a:#x}"
        for R in self._code_routines():                    # (the owner's HOLD on 78c2bb0, P1-1) the BYTES every write
            for a, what, reach, _m in self._write_sites(R):   # of the image may reach, whatever its pointer came from
                why = self._reach_hits(reach, T, T + size)
                if why is not None:
                    return f"{self.name(R)} {what} at {a:#x}: {why}"
        self._cache("_ro_users")[name] = sorted(self.name(R) for R in users)
        return None

    # ---- the bytes a write may reach (the owner's HOLD on 78c2bb0, P1-1, and the strict ruling of 2026-10-06)
    #
    # A protected cell — a word of a read-only callback table — is not shown unwritten by following ITS address: a
    # store through T - 4 + 8, or eight bytes stored at T - 4, writes it through a pointer that never was "the
    # table's". So every write of EVERY routine in the image is placed by the bytes it may reach (`_write_sites`):
    # each store, and each call or tail that hands a pointer to a routine whose summary or contract writes through
    # it. A write is placed (`_write_reach`) when its pointer is, on every path,
    #   a constant (or a stepped constant's interval, or a table address at a known offset) with a known extent:
    #       those address ranges;
    #   an address of the routine's own frame at a known slot, with a known extent: inside the stacks' region moved
    #       by that slot and extent (the frame itself is in the stacks: the bound this analysis publishes);
    #   the routine's own argument at a known offset, with a known extent: placed at every call that hands it the
    #       argument (the callee's summary carries the extent there) — provided every way into the routine IS such a
    #       call: not the reset entry, an exception vector's target, an address-taken routine other than an
    #       application callback, nor a routine nothing calls.
    # Anything else is NOT PLACED — an unbounded or register-indexed extent, a pointer loaded from memory, derived
    # by arithmetic the model does not follow, or unknown, and every call into a routine that cannot be read: it is
    # not proved to miss the cell, whichever object it was meant for (no object provenance is assumed: VALUE_MODEL's
    # B1 is not used here). Inside a routine taken at its contract (CONTRACTS / LIBC_CONTRACTS) a write through a
    # pointer derived only from its own arguments is the contract's, placed at its callers; its other writes are
    # placed like anyone's.

    def _code_routines(self) -> list[int]:
        return sorted(R for R in self.func_entries if R in self.ins_at)

    def _stack_span(self):
        """(lowest, highest) address of the stacks' region, from the linker symbols; None when the image names none
        (the assessment records their absence as a finding of its own)."""
        lims = [self.syms[s][0] for pair in STACK_TOPS.values() for s in pair if s in self.syms]
        return (min(lims), max(lims)) if lims else None

    def _transfers(self, R: int) -> dict:
        """{site: target or None} for every instruction of R that leaves it carrying its registers on: calls, tails
        and indirect ones (the path analysis's edges, and — for a routine handed in without them — by mnemonic)."""
        out = {}
        for e in self.edges.get(R, []):
            if e["kind"] in ("call", "call_noreturn", "tail", "indirect_call", "indirect_tail"):
                out[int(e["site"], 16)] = e.get("to")
        reached = self.sp_at.get(R, {})
        for i in self.region(R):
            b, tgt = base_mnem(i["mnem"])[0], self._call_target(i)
            if i["addr"] in reached and (b in ("bl", "blx") or (b == "b" and tgt is not None and tgt != R and tgt in self.func_entries)):
                out.setdefault(i["addr"], tgt)
        return out

    def _args_followed(self, R: int) -> bool:
        """Whether every way into R is a call the analysis reads the arguments of (see the block comment)."""
        c = self.__dict__.get("_followed_cache")
        if c is None:
            called = set()
            for Q in self._code_routines():
                self.analyse(Q)
                called |= {t for t in self._transfers(Q).values() if t is not None}
                called |= {e["to"] for e in self.edges.get(Q, []) if e["kind"] == "fallthrough"}
            try:
                app = set(self.rule_targets("app_function_pointers"))
            except Finding:
                app = set()
            opened = (set(getattr(self, "address_taken", ())) | set(getattr(self, "exc_targets", ()))) - app
            if "_start" in self.syms:
                opened.add(self.syms["_start"][0] & ~1)
            try:
                opened |= {v[0] for k, v in self.vector_entries().items() if v is not None and k != "_reserved_0x14"}
            except Finding:
                pass
            opened |= {e["to"] for Q in self._code_routines() for e in self.edges.get(Q, []) if e["kind"] == "fallthrough"}
            c = self.__dict__["_followed_cache"] = (called | app) - opened
        return R in c

    def _write_reach(self, R: int, atoms, ext, contract: bool) -> list:
        """Where a write of routine R through a pointer with `atoms`, over `ext` — a set of (offset, bytes) from the
        pointer, or 'ALL' — may land: ('abs', lo, hi) an address range (with a fourth element 'frame' when it is the
        routine's OWN frame — the bytes from its deepest SP up to its entry SP, never its incoming stack-argument
        area, which is its caller's — moved over the stacks' region); ('stack',) the same in an image that names no
        stacks; ('args',) placed at R's callers (through its argument, or into its incoming area); ('unknown', why)
        not placed — a frame range that leaves the frame included."""
        if not atoms:
            return [("unknown", "no value is known to reach its pointer")]
        if ext != "ALL" and not ext:
            return []
        span = self._stack_span()
        lo = hi = None
        param = ext != "ALL" and any(not isinstance(n, int) for _o, n in ext)   # a count that is a linear form of an
        if ext != "ALL" and not param:                                           # argument (A1): placed at the callers
            lo, hi = min(o for o, _n in ext), max(o + n for o, n in ext)
        out = []
        for x in sorted(atoms, key=str):
            k = x[0]
            of_arg = k in ("arg", "argo") or (k == "der" and x[1] != "frame" and x[1][0] == "arg")
            if of_arg and contract:
                continue                                   # the contract's: placed where the routine is called
            if k in ("arg", "argo") and ext != "ALL":
                out.append(("args",) if self._args_followed(R) else
                           ("unknown", "through its own argument, and the routine is entered other than by a call whose arguments are read"))
            elif param:
                out.append(("unknown", "over a length held in one of its arguments, from a pointer that is not its argument"))
            elif k == "frame" and x[1] is not None and ext != "ALL":
                own = self.local.get(R)                    # the routine's own frame is [-own, 0) from its entry SP
                if own is not None and -own <= x[1] + lo and x[1] + hi <= 0:
                    out.append(("abs", span[0] + x[1] + lo, span[1] + x[1] + hi, "frame") if span else ("stack",))
                elif x[1] + lo >= 0:                       # its INCOMING stack-argument area is its caller's frame
                    out.append(("args",) if self._args_followed(R) else
                               ("unknown", "into its incoming stack-argument area, and the routine is entered other than by a call whose arguments are read"))
                else:
                    out.append(("unknown", "through an address of its frame, over a range that leaves the frame"))
            elif k == "const" and ext != "ALL":
                if x[1] + hi > 0x100000000:
                    out.append(("unknown", f"from the constant {x[1]:#x}, a range that wraps round the address space"))
                else:
                    out += [("abs", x[1] + o, x[1] + o + n) for o, n in sorted(ext)]
            elif k == "crange" and ext != "ALL" and (x[1], x[2]) != (0, 0xFFFFFFFF):
                if x[2] + hi > 0x100000000:
                    out.append(("unknown", "from a stepped constant address, a range that wraps round the address space"))
                else:
                    out.append(("abs", x[1] + lo, x[2] + hi))
            elif k == "tab" and x[2] is not None and ext != "ALL":
                out += [("abs", x[1] + x[2] + o, x[1] + x[2] + o + n) for o, n in sorted(ext)]
            else:
                what = {"arg": "its own argument", "argo": "its own argument", "frame": "an address of its frame",
                        "const": f"the constant {x[1]:#x}" if k == "const" else "",
                        "crange": "a stepped constant address" + (" the model does not bound" if k == "crange" and ext != "ALL" else ""),
                        "tab": "an address in a read-only table", "ind": "a pointer loaded from memory",
                        "cb": "a routine's address"}.get(k)
                if k == "der":
                    what = "a pointer derived from " + ("its frame" if x[1] == "frame" else "its argument" if x[1][0] == "arg" else "a loaded pointer")
                out.append(("unknown", f"through {what or 'an unknown pointer'}" +
                            (", over an extent that is not bounded" if ext == "ALL" and k in ("arg", "argo", "frame", "const", "crange", "tab")
                             else ", at a slot the model does not pin" if k == "frame" else "")))
        return out

    @staticmethod
    def _reach_hits(reach, lo: int, hi: int):
        """Why a write with `reach` is not proved to miss [lo, hi); None when it is."""
        for r in reach:
            if r[0] == "unknown":
                return "it is not placed (" + r[1] + ")"
            if r[0] == "abs" and r[1] < hi and lo < r[2]:
                return f"it may reach {max(r[1], lo):#x}..{min(r[2], hi):#x}"
        return None

    def _handed_reach(self, R: int, a: int, pos, atoms, w, contract: bool) -> tuple:
        """`_write_reach` for a pointer handed at `a` in position `pos` — and (A1) when that leaves it unplaced, the
        register's address computed from a bounded index, if that is what it is: (reach, {'a1': rule} or {})."""
        reach = self._write_reach(R, atoms, w, contract)
        if w == "ALL" or not isinstance(pos, int) or not any(r[0] == "unknown" for r in reach):
            return reach, {}
        ca = self._computed_address(R, a, f"r{pos}")
        if ca is None:
            return reach, {}
        base, lo, hi, rule = ca                            # (the owner's HOLD on f624c87, P2) hi may be a linear form
        ext = frozenset((lo + o, self._lin_add(self._lin_add(hi, -lo), nb)) for o, nb in w)
        if any(isinstance(n, int) and o + n > 0xFFFFFFFF for o, n in ext):
            return reach, {}
        return self._write_reach(R, base, ext, contract), {"a1": "a handed address computed from an index bounded by " + rule}

    def _write_sites(self, R: int) -> list:
        """Every place routine R may write memory: [(address, what it does there, `_write_reach`)] — each store, and
        each call / tail handing a pointer that the callee's summary or contract writes through."""
        c = self._cache("_wsites")
        if R in c:
            return c[R]
        self.analyse(R)
        contract = self._contract(R) is not None or self._libc_contract(R) is not None
        reached, kinds = self.sp_at.get(R, {}), self._walk_kinds(R)
        out = []
        for i in self.region(R):
            a = i["addr"]
            if a in reached and kinds[a] == "store":
                d = self._store_desc(R, a)
                ext = "ALL" if d["wild"] else frozenset((off, nb) for off, nb, _r in d["elems"])
                out.append((a, "stores", self._write_reach(R, d["base"], ext, contract),
                            dict({"atoms": d["base"]}, **({"a1": d["a1"]} if "a1" in d else {}))))
        for a, tgt in sorted(self._transfers(R).items()):
            whom = self.name(tgt) if tgt is not None else "an indirect call"
            for pos, atoms, (w, _ind, _keep) in self._handed(R, a):
                if w:                                      # (what it writes through a pointer it LOADS is its own store)
                    reach, meta = self._handed_reach(R, a, pos, atoms, w, contract)
                    out.append((a, f"hands {'r%d' % pos if isinstance(pos, int) else pos} to {whom}, which writes through it",
                                reach, dict(meta, pos=pos, atoms=atoms, to=tgt)))
            _r, sw = self._stack_use_at(R, a)              # the callee writing its incoming stack words: OUR frame
            sp = self._pt_slot(R, a, 0)
            if sw is None:
                out.append((a, f"calls {whom}, which may write its incoming stack words at an offset that is not pinned",
                            [("unknown", "into this routine's frame, at or above its SP at the call")], {"to": tgt}))
            elif sw:
                out.append((a, f"calls {whom}, which writes its incoming stack words",
                            self._write_reach(R, frozenset({("frame", sp)}), frozenset((k, 4) for k in sw), contract)
                            if sp is not None else [("unknown", "the SP at the call is not pinned")], {"to": tgt}))
        for e in self.edges.get(R, []):                    # falling into the next routine hands it the registers
            if e["kind"] == "fallthrough" and any(self._arg_summary(e["to"], m)[0] for m in range(4)):
                out.append((int(e["site"], 16), f"falls into {self.name(e['to'])}, which writes through its arguments",
                            [("unknown", "through whatever the registers hold there")], {"to": e["to"]}))
        if self._solving is None:
            c[R] = out
        return out

    # The cells an indirect call's pointer is read from. The read-only tables are cells no write may reach at all
    # (`_ro_table_proof`). The others are objects the image legitimately writes (the exception table at boot, the
    # FILE operations, the exit handlers): for them the inventory only reports which placed writes overlap the
    # OBJECT that holds the cells, and — for a write through a constant — the stacks' region, where the frame
    # cells are. What each rule makes of those writes is the rule's own proof, not the inventory's.
    PROTECTED_OBJECTS = (EXC_TABLE, "_impure_data", "_impure_ptr", "__sf", "__sglue", "__atexit", "__atexit0",
                         "__stdio_exit_handler", "Xil_AssertCallbackRoutine")
    PROTECTED_SECTIONS = (".preinit_array", ".init_array", ".fini_array")

    def _protected(self) -> list:
        """[(name, lo, hi)]: the read-only callback tables, the named objects and the arrays present in the image."""
        out = [(name, T, T + size) for T, (name, size) in sorted(self._ro_tables().items())]
        out += [(n, self.syms[n][0], self.syms[n][0] + (self.syms[n][1] or 4)) for n in self.PROTECTED_OBJECTS if n in self.syms]
        out += [(sec["name"], sec["addr"], sec["addr"] + sec["size"]) for sec in self.secs if sec["name"] in self.PROTECTED_SECTIONS and sec["size"]]
        return out

    def write_inventory(self) -> dict:
        """Every write of every routine in the image, by where it is placed (`_write_sites`). Per routine: its
        writes (stores + hand_overs — one per store, one per pointer position a call hands to a writer), each counted
        once as placed / at_the_callers / by_contract / not_placed; `not_placed_at` every site that is not placed,
        grouped by why (none is left out); `overlapping_at` every placed site that overlaps a protected object.
        `unproved` counts the sites not proved to miss the callback cells."""
        prot = self._protected()
        span = self._stack_span()
        names = [self.name(R) for R in self._code_routines()]
        routines, total = {}, {"stores": 0, "hand_overs": 0, "placed": 0, "at_the_callers": 0, "by_contract": 0, "not_placed": 0,
                                "not_placed_sites": 0, "overlapping_sites": 0, "placed_by_a1": 0}
        for R in self._code_routines():
            rec = {"stores": 0, "hand_overs": 0, "placed": 0, "at_the_callers": 0, "by_contract": 0, "not_placed": 0}
            unplaced: dict = {}
            over: dict = {}
            a1: dict = {}
            for a, what, reach, m in self._write_sites(R):
                kind = "stores" if what == "stores" else "hand_overs"
                rec[kind] += 1
                why = [r[1] for r in reach if r[0] == "unknown"]
                if "a1" in m and not why:                  # (A1) placed only because its index is bounded
                    a1.setdefault(m["a1"], []).append(f"{a:#x}")
                    total["placed_by_a1"] += 1
                if why:
                    rec["not_placed"] += 1
                    for w in sorted(set(why)):
                        unplaced.setdefault(f"{what}: {w}", []).append(f"{a:#x}")
                    continue
                hit = sorted({n for n, lo, hi in prot for r in reach if r[0] == "abs" and r[1] < hi and lo < r[2]} |
                             {"the stacks" for r in reach if r[0] == "abs" and len(r) == 3 and span and r[1] < span[1] and span[0] < r[2]})
                for n in hit:
                    over.setdefault(n, []).append(f"{a:#x}")
                rec["placed" if any(r[0] in ("abs", "stack") for r in reach) else "at_the_callers" if reach else "by_contract"] += 1
            for k, v in rec.items():
                total[k] += v
            n_un, n_ov = len({x for v in unplaced.values() for x in v}), len({x for v in over.values() for x in v})
            total["not_placed_sites"] += n_un
            total["overlapping_sites"] += n_ov
            if unplaced:
                rec["not_placed_at"] = {k: sorted(set(v)) for k, v in sorted(unplaced.items())}
            if over:
                rec["overlapping_at"] = {k: sorted(set(v)) for k, v in sorted(over.items())}
            if a1:
                rec["placed_by_a1_at"] = {k: sorted(set(v)) for k, v in sorted(a1.items())}
            if rec["stores"] or rec["hand_overs"]:           # (two routines of one name — the libc's two __sbprintf —
                n = self.name(R)                           # are told apart by address: neither record is dropped)
                routines[n if names.count(n) == 1 else f"{n}@{R:#x}"] = rec
        return {"protected": [{"name": n, "from": f"{lo:#x}", "to": f"{hi:#x}"} for n, lo, hi in prot],
                "stacks": [f"{span[0]:#x}", f"{span[1]:#x}"] if span else None,
                "routines": routines, "total": total, "unproved": total["not_placed_sites"] + total["overlapping_sites"]}

    def calls_through_memory(self, entry: int) -> bool:
        """Whether a path from `entry` makes an indirect call or tail (context-free, over every rule's target set):
        its target is then a word read from memory, or carried from one."""
        seen, todo = set(), [entry]
        while todo:
            R = todo.pop()
            if R in seen or R not in self.ins_at:
                continue
            seen.add(R)
            self.analyse(R)
            for e in self.edges.get(R, []):
                if e["kind"] in ("indirect_call", "indirect_tail"):
                    return True
                todo += [t for t in self.targets(e) if t is not None]
        return False

    # ---- named callback contracts (the owner's ruling of 2026-10-05: named write-range summaries for the finite set
    # of routines that block, from their source semantics, bound to the source digest and to the image's code)
    #
    # A contract replaces the routine's summary: what it may write through each argument (its extent from the
    # pointer: a byte count, the value of another argument or a linear function of it (mul x argument + add) — which
    # must then be a constant at the call, else the write is unbounded — or 'STR', within the NUL-terminated string
    # the argument points at, forward), that it
    # writes through nothing else it is handed and keeps no pointer, and what it returns ('in0': NULL or a pointer
    # into argument 0's object; 'int': a number). `keeps` names the argument positions it may keep (a kept frame
    # address leaks that frame). An argument position at or above its arity is not read. It holds
    # only while (1) the routine is the named unit's code, (2) that unit's source digest is the recorded one, (3) the
    # digest of the routine's code WITH everything it calls or branches to (its closure) is the recorded one, and (4)
    # the routine's own instructions do not write, at a pinned offset, more than the contract says (`_arg_summary`
    # read off the code, where it is exact), nor store an argument pointer itself outside its frame unless `keeps`
    # says so. Any of these failing is a Finding.
    STR_EXTENT = 1 << 30
    CONTRACT_SOURCES = {
        "b3/firmware/b3_app.c": "2f7f1660d4f598c483139de4bd45d22afe273eecb7876e7419f142db1de8ff66",
        "b3/firmware/p3_derive.c": "21b4d7a9b4379a6d2d5ff9a76e111d1ae1641305a4647e18f70767c7af50d730",
        "b3/firmware/b3_record.c": "5c9e433e5732dc9f6eea504c5b21a70ceb70f41b33d6916c24d56d89ba6ab8ba",
    }
    CONTRACTS = {
        "rectx_parse_cb": {"unit": "b3/firmware/b3_app.c", "arity": 5, "writes": {0: "STR", 1: ("arg", 2), 3: 4},
                           "returns": "in0",
                           "source": "parse_frame_any(line, type_out, type_max, seq_out): strrchr / *last = 0 and "
                                     "line[i] = 0 only inside the string at line; *seq_out = strtoul(…, NULL, 10) (4 "
                                     "bytes); snprintf(type_out, type_max, \"%s\", …) (at most type_max bytes); returns "
                                     "NULL or f[4], a pointer into line; f[] and expect[] are its own locals"},
        "pull_parse_cb": None,                             # (the same body: parse_frame_any; filled below)
        "rectx_payload_seq_cb": {"unit": "b3/firmware/b3_app.c", "arity": 3, "writes": {1: 4}, "returns": "int",
                                 "source": "p3_base64url_decode(payload, g_json, sizeof g_json - 1) into the global; "
                                           "json_uint(g_json, key, seq_out) writes *seq_out (4 bytes) only"},
        "pull_payload_fields_cb": {"unit": "b3/firmware/b3_app.c", "arity": 5, "writes": {1: 4, 2: 4, 3: 4},
                                   "returns": "int",
                                   "source": "as rectx_payload_seq_cb, then *seq_out, *chunk_out (json_uint) and "
                                             "*has_chunk (an int), 4 bytes each"},
        "tx_recv_cb": {"unit": "b3/firmware/b3_app.c", "arity": 3, "writes": {0: ("arg", 1)}, "returns": "int",
                       "source": "recv_line_bounded(out, max, …) -> p3_rectx_recv_line_timed(&APP_RX, out, max, …): "
                                 "returns -1 at max == 0 before any write; out[n] with n + 1 < max, and out[n] = 0 with "
                                 "n < max — within out[0, max)"},
        "rectx_recv_cb": None,
        "pull_recv_cb": None,
        "sha_emit": {"unit": "b3/firmware/b3_record.c", "arity": 3, "writes": {0: 108}, "returns": "int",
                     "source": "p3_sha256_update((p3_sha256 *)ctx, bytes, n): c->len (8 at 32), c->buf[c->n, c->n + "
                               "take) with take <= 64 - c->n (inside buf, 40..104), c->n (4 at 104), sha256_block("
                               "c->h, c->buf) writes h (0..32) and its own w[64]; sizeof(p3_sha256) = 108. Precondition: "
                               "ctx is a p3_sha256 set up by p3_sha256_init (c->n < 64, kept by update)"},
    }
    SHA = ("p3_sha256 is {uint32_t h[8]; uint64_t len; uint8_t buf[64]; size_t n} = 108 bytes. sha256_block(h, p) writes h[0..8) and its own w[64] only. Precondition for update / final / words: c was set up by p3_sha256_init (c->n < 64, which update keeps: take <= 64 - c->n)")
    CONTRACTS.update({
        "p3_sha256_init": {"unit": "b3/firmware/p3_derive.c", "arity": 1, "writes": {0: 108}, "returns": "int",
                           "source": "memcpy(c->h, iv, 32); c->len = 0; c->n = 0. " + SHA},
        "p3_sha256_update": {"unit": "b3/firmware/p3_derive.c", "arity": 3, "writes": {0: 108}, "returns": "int",
                             "source": "c->len += n; memcpy(c->buf + c->n, data, take) with take <= 64 - c->n; c->n += "
                                       "take; at 64: sha256_block(c->h, c->buf), c->n = 0. " + SHA},
        "p3_sha256_final": {"unit": "b3/firmware/p3_derive.c", "arity": 2, "writes": {0: 108, 1: 32}, "returns": "int",
                            "source": "p3_sha256_update(c, &pad / lenbe, …) on its own locals; out[4i .. 4i+3] for i < 8 "
                                      "(32 bytes). " + SHA},
        "p3_sha256_words": {"unit": "b3/firmware/p3_derive.c", "arity": 3, "writes": {0: 108}, "returns": "int",
                            "source": "p3_sha256_update(c, be, 4) per word, be[4] its own local. " + SHA},
        "p3_hex": {"unit": "b3/firmware/p3_derive.c", "arity": 3, "writes": {2: ("lin", 1, 2, 1)}, "returns": "int",
                   "source": "out[2i], out[2i + 1] for i < n, then out[2n] = 0: out[0, 2n + 1); in is only read"},
    })
    CONTRACTS["pull_parse_cb"] = dict(CONTRACTS["rectx_parse_cb"])
    CONTRACTS["rectx_recv_cb"] = dict(CONTRACTS["tx_recv_cb"])
    CONTRACTS["pull_recv_cb"] = dict(CONTRACTS["tx_recv_cb"])
    CONTRACT_CODE = {                                  # name -> the closure digest it is bound to (this image)
        "p3_hex": "96dc4ca59b157f590820a34fe1cbda6f63c96bbbd2b4c41fea2d9ad51d0b2b92",
        "p3_sha256_final": "ab9f4a86a6c8814ba361c0052c477622a682c81f9def945aa2da7b3c000dfd4b",
        "p3_sha256_init": "53dcdf6551d5c4b8797b30c98ed768eb9b6d9e7a0283d91b8ce0c621be5dab61",
        "p3_sha256_update": "9dc14505f1488f71ed29cd48815da26d2bc8afcec75874df35229b73fd1ec37c",
        "p3_sha256_words": "532af8d21f83ff7b66b8385d456591bb260c518370201899771b2391d39fcdc0",
        "pull_parse_cb": "0b191ebf788a6ffa878d582d06802ec090c9785620ed7b0eb570353f5ccf7781",
        "pull_payload_fields_cb": "4ea251775f22295b7e4a76614cbd8c1677d742cc4a34da5d621d64a29afbb842",
        "pull_recv_cb": "85e02c189c564f15b033c086bcda57b93e4bf9f387011f0e99af49517360f119",
        "rectx_parse_cb": "72e9dda05e40808496b3a81f396505cd0d45d50ef53f8578f7a9cf5971cd2be9",
        "rectx_payload_seq_cb": "21277725af553d07e572862953e444e26eed02f4ad71f90fd4b38cfb06b33e7d",
        "rectx_recv_cb": "14a874c7da636c79c27c38ceaed885ba4d0dd8ed00e513f28b20254cca58ae78",
        "sha_emit": "d1967bf1ba6f1b07e4f11c8e05c647b9549caaf37145bc8cf3d43703acabc573",
        "tx_recv_cb": "d4fbc942382cf09dd440cf4081ccce01e09527ce0a9e71c34e6d7fbd9183d481",
    }

    def _closure(self, t: int) -> list[int] | None:
        """The routine and every routine it can reach: each edge the path analysis records — a call, a tail, a fall-
        through, and every target of an indirect call by its site's named target set (an application-pointer site:
        every application callback — deliberately the whole set, so the closure does not depend on what else has
        been resolved, and the digest is the same in every run). None when a transfer has no named set."""
        seen, todo = set(), [t]
        while todo:
            r = todo.pop()
            if r in seen:
                continue
            seen.add(r)
            if r not in self.ins_at:
                return None
            try:
                self.analyse(r)
                for e in self.edges[r]:
                    if e["kind"] in ("indirect_call", "indirect_tail"):
                        todo += list(self.rule_targets(e["set"]))
                    elif e.get("to") is not None:
                        todo.append(e["to"])
            except Finding:
                return None
        return sorted(seen)

    def _code_digest(self, t: int):
        cl = self._closure(t)
        if cl is None:
            return None
        h = hashlib.sha256(f"closure of {self.name(t)}:".encode())
        for r in cl:
            body = self.region(r)
            h.update(f"{self.name(r)}@{r:#x}:".encode())
            try:
                h.update(self.read_bytes(r, body[-1]["addr"] + body[-1]["size"] - r))
            except Finding:                                # (a synthetic image has no bytes: its instruction text)
                h.update("".join(f"{i['mnem']} {i['ops']};" for i in body).encode())
        return h.hexdigest()

    def _unit_sha(self, unit: str) -> str | None:
        p = REPO_ROOT / unit
        return sha256_file(p) if p.is_file() else None

    def _contract(self, t: int | None):
        """The verified contract of the routine at `t`, None when it has none; a Finding when its binding fails."""
        if t is None or self.name(t) not in self.CONTRACTS:
            return None
        memo = self._cache("_contract_memo")
        if t in memo:
            if isinstance(memo[t], Finding):
                raise memo[t]
            return memo[t]
        name, c = self.name(t), self.CONTRACTS[self.name(t)]
        try:
            if self.unit_of(t) != c["unit"]:
                raise Finding(f"the contract of {name} is for {c['unit']}'s code; this is {self.unit_of(t)}'s")
            want = self.CONTRACT_SOURCES.get(c["unit"])
            if want is None or self._unit_sha(c["unit"]) != want:
                raise Finding(f"the contract of {name} is bound to {c['unit']} at {want}, which is now {self._unit_sha(c['unit'])}")
            got = self._code_digest(t)
            if got is None or got != self.CONTRACT_CODE.get(name):
                raise Finding(f"the contract of {name} is bound to its code closure {self.CONTRACT_CODE.get(name)}, "
                              f"the image's is {got}")
            memo[t] = c                                    # (set before the self-check: it reads the code, which may
            for p in range(4):                             # call back into this routine's contract)
                auto = self._isolated(self._auto_summary, t, p)
                allowed = self._contract_cf(c, p)[0]
                if auto[0] not in (None, "ALL") and allowed != "ALL" and not all(
                        any(lo <= o and o + n <= lo + m for lo, m in (allowed or ())) for o, n in auto[0]):
                    raise Finding(f"the contract of {name} lets argument {p} be written at {sorted(allowed or [])}, "
                                  f"but its code writes {sorted(auto[0])}")
                kept = self._cache("_exact_keeps").get((t, p))
                if kept is not None and p not in c.get("keeps", {}):
                    raise Finding(f"the contract of {name} says argument {p} is not kept, but its code stores that "
                                  f"pointer outside its frame at {kept:#x}")
        except Finding as e:
            memo[t] = e
            raise
        self._cache("_contracts_used")[name] = {"unit": c["unit"], "source_sha256": self.CONTRACT_SOURCES[c["unit"]],
                                                "code_sha256": self.CONTRACT_CODE[name], "arity": c["arity"],
                                                "writes": {str(k): (v if not isinstance(v, tuple) else f"argument {v[1]}" if v[0] == "arg"
                                    else f"{v[2]} x argument {v[1]} + {v[3]}")
                                                           for k, v in sorted(c["writes"].items())},
                                                "returns": c["returns"], "source": c["source"]}
        return c

    def _auto_summary(self, t: int, p):
        s = self._fixed("summary", t, self._arg_summary_compute, {})
        return self.EVERYTHING if s == self.TOP else s.get(p, self.NOTHING)

    def _contract_pos(self, m):
        if isinstance(m, int):
            return m
        if isinstance(m, tuple) and m[0] == "stk":
            return 4 + m[1] // 4
        return None

    def _contract_cf(self, c: dict, m) -> tuple:
        """The contract's summary for position `m`, context-free (an extent given by another argument: unbounded)."""
        pos = self._contract_pos(m)
        if pos is None or pos >= c["arity"]:
            return self.NOTHING
        keep = frozenset({"EXT"}) if pos in c.get("keeps", {}) else None
        if pos not in c["writes"]:
            return (None, None, keep)
        ext = c["writes"][pos]
        if isinstance(ext, int):
            return (frozenset({(0, ext)}) if ext else None, None, keep)
        if ext == "STR":
            return (frozenset({(0, self.STR_EXTENT)}), None, keep)
        return ("ALL", None, keep)

    def _summary_at(self, entry: int, a: int, t: int, m) -> tuple:
        """The summary of the routine `t` called at `a`, for position `m`: its contract evaluated at the call, or
        its summary read off the code."""
        c = self._contract(t)
        if c is None:
            return self._arg_summary(t, m)
        pos = self._contract_pos(m)
        ext = c["writes"].get(pos) if pos is not None and pos < c["arity"] else None
        if isinstance(ext, tuple) and ext[0] in ("arg", "lin"):   # the extent is another argument's value here
            k = ext[1]
            mul, add = (ext[2], ext[3]) if ext[0] == "lin" else (1, 0)
            if k < 4:
                v = self._raw_reg(entry, a, f"r{k}")
            else:
                sp = self._pt_slot(entry, a, 0)
                v = self._raw_slot(entry, a, sp + 4 * (k - 4)) if sp is not None else frozenset()
            keep = self._contract_cf(c, m)[2]
            if v and all(x[0] == "const" for x in v):
                n = mul * max(x[1] for x in v) + add
                return (frozenset({(0, n)}) if n > 0 else None, None, keep)
            return ("ALL", None, keep)                     # the length is not a constant here: unbounded
        return self._contract_cf(c, m)

    def _callee_summary(self, entry: int, a: int, m) -> tuple:
        """(writes, ind, keep) of the call at `a` for its argument `m`, memoised outside a solver round."""
        key = (entry, a, m)
        cache = self._cache("_csum")
        if key in cache:
            return cache[key]
        out = self._callee_summary_compute(entry, a, m)
        if self._solving is None:                          # (inside a solver round an argument value may still move)
            cache[key] = out
        return out

    def _subst_ext(self, entry: int, a: int, w):
        """(A1) A callee's write extents with every count that is a linear form of one of ITS arguments replaced by
        what that argument is at this call: a constant — the count (none when it is not positive: nothing is
        written); exactly the caller's own incoming argument — the form in the caller's numbering (kept parametric,
        for the caller's callers); anything else — the whole extent is unknown ('ALL')."""
        if w is None or w == "ALL" or all(isinstance(nb, int) for _o, nb in w):
            return w
        out = set()
        for off, nb in w:
            if isinstance(nb, int):
                out.add((off, nb))
                continue
            _l, k, mul, add = nb
            v = self._raw_reg(entry, a, f"r{k}") if isinstance(k, int) and k < 4 else frozenset()
            if v and all(x[0] == "const" for x in v):
                cnt = mul * max(x[1] for x in v) + add
                if cnt > 0:
                    if off + cnt > 0xFFFFFFFF:
                        return "ALL"
                    out.add((off, cnt))
            elif len(v) == 1 and next(iter(v))[0] == "arg" and isinstance(next(iter(v))[1], int):
                out.add((off, ("lin", next(iter(v))[1], mul, add)))
            else:
                return "ALL"
        return frozenset(out) or None

    def _callee_summary_compute(self, entry: int, a: int, m) -> tuple:
        w, ind, keep = self._callee_summary_raw(entry, a, m)
        return (self._subst_ext(entry, a, w), ind, keep)

    def _callee_summary_raw(self, entry: int, a: int, m) -> tuple:
        i = self.ins_at[a]
        tgt = self._call_target(i)
        c = self._libc_contract(tgt)
        if c is not None:
            if c[4] is not None:
                if not self._printf_safe(entry, a, c[4]):
                    return ("ALL", None, None)             # a %n is not excluded: it writes through any argument
            if c[1] is None or m != c[1]:
                return self.NOTHING
            size = self._raw_reg(entry, a, f"r{c[2]}")
            if not size or any(x[0] != "const" for x in size):
                return ("ALL", None, None)                 # the byte count is not a constant at the call
            n = max(x[1] for x in size)
            return (frozenset({(0, n)}) if n else None, None, None)
        if tgt is not None:
            return self._summary_at(entry, a, tgt, m)
        targets = self._indirect_targets(entry, a)
        if targets is None:
            return self.EVERYTHING
        out = self.NOTHING
        for t in targets:
            out = self._merge3(out, self._summary_at(entry, a, t, m))
        return out

    def _pointer_slots(self, entry: int):
        """The frame slots of the routine that some store may fill with an address (flow-insensitive), or None when
        that cannot be listed (a store of one at a place the model cannot pin; or the list is being computed)."""
        # asked while it is being computed (a word loaded from the frame is stored back into it): no slot yet — if no
        # store parks an address ON THAT ASSUMPTION, none is the first to
        return self._guarded("pslots", entry, self._pointer_slots_compute, frozenset())

    def _pointer_slots_compute(self, entry: int):
        self.analyse(entry)
        out = set()
        for i in self.region(entry):
            a = i["addr"]
            if a not in self.sp_at.get(entry, {}) or self._walk_kinds(entry)[a] != "store":
                continue
            d = self._store_desc(entry, a)
            B = d["base"]
            if not any(x[0] == "frame" or x == ("der", "frame") for x in B):
                continue
            pinned = len(B) == 1 and next(iter(B))[0] == "frame" and next(iter(B))[1] is not None and not d["wild"]
            for off, nb, r in d["elems"]:
                regs = [r] if r is not None else d["data"]
                if any(x[0] in self.POINTERISH for q in regs for x in self._base_atoms(entry, a, q)):
                    if not pinned or r is None:
                        return None
                    out.add(next(iter(B))[1] + off)
        for i in self.region(entry):                       # … and the words a callee may park a pointer in
            a = i["addr"]
            if a not in self.sp_at.get(entry, {}) or self._walk_kinds(entry)[a] != "call":
                continue
            H = self._handed(entry, a)
            where = {pos: atoms for pos, atoms, _s in H}
            for _pos, atoms, (_w, _d, kp) in H:
                if not kp or not any(x[0] in self.POINTERISH for x in atoms):
                    continue
                for dest in kp:
                    for y in self._frameish(where.get(dest[0], ())) if dest != "EXT" else ():
                        if y[0] != "frame" or y[1] is None:
                            return None
                        out.add(y[1] + dest[1])
        return frozenset(out)

    def _stack_use(self, callee: int) -> tuple:
        """(reads, writes) of the routine's INCOMING stack-argument area (the caller's outgoing words, offsets k >= 0
        from its entry SP), read off its code: each a frozenset of word offsets, or None when the routine can reach
        that area at an offset the model does not pin — a load or store through a derived or unpinned frame address
        or at a register index, a frame address at or above the entry SP that is handed on, stored or kept (a
        va_list), or a callee handed a frame address that may write at or above it. A routine the image does not
        hold: (None, None)."""
        if not self._readable(callee):
            return (None, None)
        return self._guarded("stkuse", callee, self._stack_use_compute, (frozenset(), frozenset()))

    def _stack_use_compute(self, R: int) -> tuple:
        self.analyse(R)
        reads, writes = set(), set()
        unbounded_r = unbounded_w = False

        def words(lo, hi):
            return {k for k in range(lo & ~3, hi, 4) if k >= 0 and k + 4 > lo}
        kinds = self._walk_kinds(R)
        for i in self.region(R):
            a = i["addr"]
            if a not in self.sp_at.get(R, {}):
                continue
            o = i["ops"].replace(" ", "")
            fam = self._family(i)
            if kinds.get(a) == "store":
                d = self._store_desc(R, a)
                for x in d["base"]:
                    if x[0] == "frame" and x[1] is not None and not d["wild"]:
                        for off, n, _r in d["elems"]:
                            if isinstance(n, int):
                                writes |= words(x[1] + off, x[1] + off + n)
                            else:
                                unbounded_w = True         # (a length held in an argument: not a fixed set of words)
                    elif x[0] == "frame" or x == ("der", "frame"):
                        unbounded_w = True
                for r in d["data"]:                        # a frame address at or above the entry SP, stored
                    if any(y[0] == "frame" and (y[1] is None or y[1] >= 0) for y in self._base_atoms(R, a, r)):
                        unbounded_r = unbounded_w = True
                continue
            if fam.startswith(("ldr", "ldm", "pop", "vld", "vpop")) and fam not in ("pop", "vpop"):
                m = re.search(r"\[(\w+)(?:,([^\]]+))?\]", o) or re.match(r"(\w+)!?,\{", o)
                if not m or m.group(1) == "pc":
                    continue
                base, inner = m.group(1), (m.group(2) if m.re.groups > 1 else None)
                n = 4 * len(reglist(i["ops"])) if "{" in o else (8 if fam in ("ldrd", "vldr") else 4)
                k = int(inner[1:], 0) if inner and inner.startswith("#") else 0
                ls = self._loop_frame_span(R, a, base) if not (inner and not inner.startswith("#")) else None
                for x in (self._base_atoms(R, a, base) if ls is None else [("frame", ls[0])]):
                    if x[0] == "frame" and x[1] is not None and not (inner and not inner.startswith("#")):
                        reads |= words(x[1] + k, (x[1] + k + n) if ls is None else (ls[1] + k + n))
                    elif x[0] == "frame" or x == ("der", "frame"):
                        unbounded_r = True
                continue
            if self._is_call(i) or (self._call_target(i) is not None and self._call_target(i) in self.func_entries
                                    and self._call_target(i) != R and base_mnem(i["mnem"])[0] == "b"):
                for _pos, atoms, (w, ind, keep) in self._handed(R, a):
                    for x in self._frameish(atoms):
                        A0 = x[1] if x[0] == "frame" else None
                        if A0 is None or A0 >= 0:          # (a pointer into the incoming area itself: a va_list)
                            unbounded_r = True
                            if w is not None or keep is not None:
                                unbounded_w = True
                        elif w == "ALL" or (w and any(not isinstance(nb, int) or A0 + off + nb > 0 for off, nb in w)):
                            unbounded_w = True
        return (None if unbounded_r else frozenset(reads), None if unbounded_w else frozenset(writes))

    def _stack_use_at(self, entry: int, a: int) -> tuple:
        """`_stack_use` of what the call at `a` may reach (the union over an indirect call's targets)."""
        tgt = self._call_target(self.ins_at[a])
        c = self._libc_contract(tgt)
        if c is not None:                                  # register arguments only — but a printf's variadic words,
            if self.name(tgt) in self.LIBC_VARIADIC:       # only read: where its proved formats put them (unknown
                lay = self._printf_layout(entry, a, tgt)   # when they are not proved or not sized)
                return (None if lay is None else lay[1], frozenset())
            return (frozenset(), frozenset())              # (vsnprintf: its va_list is a register; none of its own)
        targets = [tgt] if tgt is not None else self._indirect_targets(entry, a)
        if targets is None:
            return (None, None)
        reads, writes = frozenset(), frozenset()
        for t2 in targets:
            r2, w2 = self._stack_use(t2)
            reads = None if reads is None or r2 is None else reads | r2
            writes = None if writes is None or w2 is None else writes | w2
        return (reads, writes)

    def _handed(self, entry: int, a: int) -> list:
        """Every pointer position the call at `a` is handed: (position, the atoms there, the callee's summary for
        it). The four argument registers always; the stack words a readable callee reads; for an unknown callee (or a
        printf whose format is not proved free of %n, or a callee that reaches its stack arguments at an offset
        the model does not pin) every frame word at or above SP that may hold an address."""
        out = [(m, self._raw_reg(entry, a, f"r{m}"), self._callee_summary(entry, a, m)) for m in self._handed_regs(entry, a)]
        tgt = self._call_target(self.ins_at[a])
        sp = self._pt_slot(entry, a, 0)
        unknown = frozenset({("other",), ("der", "frame")} | {("der", ("arg", n)) for n in (0, 1, 2, 3)})
        c = self._libc_contract(tgt)
        if c is not None:
            if c[4] is None or self._printf_safe(entry, a, c[4]):
                return out                                 # a fixed register arity, or stack words that are only read
            every = ("ALL", None, None)
        else:
            targets = [tgt] if self._readable(tgt) else (self._indirect_targets(entry, a) if tgt is None else None)
            reads = self._stack_use_at(entry, a)[0] if targets is not None else None
            if targets is not None and reads is not None:  # the stack words the callee actually reads
                for k in sorted(reads):
                    s = self.NOTHING
                    for t in targets:
                        s = self._merge3(s, self._summary_at(entry, a, t, ("stk", k)))
                    if s != self.NOTHING:
                        out.append((("stk", k), unknown if sp is None else self._raw_slot(entry, a, sp + k), s))
                return out
            every = self.EVERYTHING                        # (it may read any of them: each may be a pointer it uses)
        slots = self._pointer_slots(entry)
        if sp is None or slots is None:
            out.append(("frame", unknown, every))
        else:
            out += [(("frame", A), self._raw_slot(entry, a, A), every) for A in sorted(slots) if A >= sp]
        return out

    def _arg_summary(self, callee: int, n) -> tuple:
        if not self._readable(callee):
            return self.EVERYTHING
        c = self._contract(callee)
        if c is not None:
            return self._contract_cf(c, n)
        return self._auto_summary(callee, n)

    def _arg_writes(self, callee: int, n):
        return self._arg_summary(callee, n)[0]

    def _arg_summary_compute(self, callee: int) -> dict:
        """The routine's summary for EVERY argument position at once: {n: (writes, ind, keep)}, absent = NOTHING.
        `ind` = {(the offset, from argument n, of a word the routine loads, the extent it writes through THAT loaded
        pointer: a set of (offset, bytes), 'ALL', or 'KEEP' when it may keep it)}; offset None: a word it reaches
        at a place the model does not pin."""
        self.analyse(callee)
        acc: dict = {}                                     # n -> [writes set, {off: ext set}, keep set]

        def of(n):
            return acc.setdefault(n, [set(), {}, set()])

        def ind_add(n, off, ext):
            cur = of(n)[1].setdefault(off, set())
            cur |= ({ext} if isinstance(ext, str) else set(ext))

        def split(atoms):
            """Per argument n among `atoms`: [exact offsets from it, derived from it?, exact loaded words (offsets),
            loaded words with arithmetic on them (offsets)]."""
            out: dict = {}
            for x in atoms:
                if x[0] in ("arg", "argo"):
                    out.setdefault(x[1], [[], False, [], []])[0].append(0 if x[0] == "arg" else x[2])
                elif x[0] == "der" and x[1] != "frame" and x[1][0] == "arg":
                    out.setdefault(x[1][1], [[], False, [], []])[1] = True
                elif x[0] == "der" and x[1] != "frame" and x[1][0] == "ind":
                    out.setdefault(x[1][1], [[], False, [], []])[3].append(x[1][2])
                elif x[0] == "ind":
                    out.setdefault(x[1], [[], False, [], []])[2].append(x[2])
            return out
        reached = self.sp_at.get(callee, {})
        kinds = self._walk_kinds(callee)
        for i in self.region(callee):
            a = i["addr"]
            if a not in reached:
                continue
            if kinds[a] == "store":
                d = self._store_desc(callee, a)
                B = d["base"]
                for n, (ks, dd, ii, iid) in split(B).items():
                    if dd or (ks and d["wild"]):
                        of(n)[0].add("ALL")
                    of(n)[0].update((k + off, nb) for k in ks for off, nb, _r in d["elems"])
                    for off in ii:
                        ind_add(n, off, "ALL" if d["wild"] or off is None else {(eo, nb) for eo, nb, _r in d["elems"]})
                    for off in iid:
                        ind_add(n, off, "ALL")
                if not (B and all(x[0] == "frame" or x == ("der", "frame") for x in B)):   # not into its own frame
                    one = next(iter(B)) if len(B) == 1 and not d["wild"] else None
                    for off, nb, r in d["elems"]:
                        for q in ([r] if r is not None else d["data"]):
                            for n, (ks, dd, ii, iid) in split(self._base_atoms(callee, a, q)).items():
                                if (ks or dd) and r is not None and nb == 4:      # a whole word: the pointer is kept
                                    self._cache("_keep_why").setdefault((callee, n), []).append(f"stored at {a:#x}")
                                    if ks and not dd:
                                        self._cache("_exact_keeps")[(callee, n)] = a      # the argument itself
                                    of(n)[2].add((one[1], (0 if one[0] == "arg" else one[2]) + off)
                                                 if one is not None and one[0] in ("arg", "argo") else "EXT")
                                for off2 in ii + iid:      # a pointer loaded through argument n, kept
                                    ind_add(n, off2, "KEEP")
                continue
            b = base_mnem(i["mnem"])[0]
            tgt = self._call_target(i)
            tail = b == "b" and tgt is not None and tgt != callee and tgt in self.func_entries
            if not (b in ("bl", "blx") or tail):
                continue
            H = self._handed(callee, a)
            where = {pos: atoms for pos, atoms, _s in H}
            for _m, atoms, (w, d2, kp) in H:
                for n, (ks, dd, ii, iid) in split(atoms).items():
                    if ks or dd:
                        for dest in kp or ():              # the callee keeps it: where, in THIS routine's terms
                            A2 = where.get(dest[0], frozenset()) if dest != "EXT" else frozenset()
                            if len(A2) == 1 and next(iter(A2))[0] in ("arg", "argo"):
                                y = next(iter(A2))
                                of(n)[2].add((y[1], (0 if y[0] == "arg" else y[2]) + dest[1]))
                            elif not (A2 and all(x[0] == "frame" or x == ("der", "frame") for x in A2)):
                                self._cache("_keep_why").setdefault((callee, n), []).append(f"handed on at {a:#x} {dest} {sorted(A2, key=str)[:3]}")
                                of(n)[2].add("EXT")        # (in this routine's own frame: its slots carry it)
                        if w == "ALL" or (w and dd):
                            of(n)[0].add("ALL")
                        elif w:
                            of(n)[0].update((k + off, nb) for k in ks for off, nb in w)
                        if d2 == "ALL" or (d2 and dd):
                            ind_add(n, None, "ALL")
                        elif d2:                           # the callee's loaded words, at our offsets
                            for off2, ext in d2:
                                for k in ks:
                                    ind_add(n, None if off2 is None else k + off2, ext)
                    for off in ii:                         # a word loaded through argument n, handed on
                        if kp:
                            ind_add(n, off, "KEEP")
                        if w == "ALL" or off is None:
                            ind_add(n, off, "ALL" if w else set())
                        elif w:
                            ind_add(n, off, w)
                        if d2:
                            ind_add(n, None, "ALL")        # (a word reached through it: a second remove)
                    for off in iid:                        # … with arithmetic on it: anywhere from it
                        if kp:
                            ind_add(n, off, "KEEP")
                        if w or d2:
                            ind_add(n, off, "ALL")
        out = {}
        for n, (writes, ind, keep) in acc.items():
            w = "ALL" if ("ALL" in writes or len(writes) > 64) else (frozenset(writes) or None)
            d2 = self._ind_norm(ind)
            kp = frozenset({"EXT"}) if ("EXT" in keep or len(keep) > 64) else (frozenset(keep) or None)
            if (w, d2, kp) != self.NOTHING:
                out[n] = (w, d2, kp)
        return out

    @staticmethod
    def _ind_norm(ind: dict):
        """{off: ext set} -> the summary's ind: None, or a frozenset of (off, ext) with ext a frozenset of ranges,
        'ALL' or 'KEEP' (KEEP above ALL above ranges); more than 64 entries: ALL."""
        out = set()
        for off, ext in ind.items():
            if "KEEP" in ext:
                out.add((off, "KEEP"))
            elif "ALL" in ext or len(ext) > 64:
                out.add((off, "ALL"))
            elif ext:
                out.add((off, frozenset(ext)))
        if len(out) > 64:
            return "ALL"
        return frozenset(out) or None

    def _in_stacks(self, v: int) -> bool:
        """`v` lies in the stacks' region (every mode's, from the linker symbols): a constant address that may be a
        frame's. A store through any other constant cannot be through a leaked frame address — that would first have
        to be loaded, and a loaded value is not a constant."""
        lims = [self.syms[s][0] for pair in STACK_TOPS.values() for s in pair if s in self.syms]
        return not lims or min(lims) <= v < max(lims)

    @staticmethod
    def _frameish(atoms) -> list:
        return sorted((x for x in atoms if x[0] == "frame" or x == ("der", "frame")), key=str)   # (a fixed order: an
        #                            early return in a loop over these decides which slots get read, and thereby
        #                            what is recorded against them — never the process's hash seed)

    def _frame_leaks(self, entry: int) -> bool:
        """Whether an address of the routine's frame may come to rest in memory outside the frame: stored there by
        the routine, or handed to a callee that may keep it. Then the frame can be written from anywhere."""
        # while it is being computed the frame is taken not to leak: if no store and no hand-over leaks an address ON
        # THAT ASSUMPTION, none is the first to, so none does (what is solved meanwhile is provisional, see _guarded)
        why = self._guarded("leak", entry, self._frame_leaks_compute, False)
        if why and entry in self._cache("_memo_leak"):
            self._cache("_leaks")[self.name(entry)] = why
        return bool(why)

    def _frame_leaks_compute(self, entry: int):
        if entry not in self.edges and entry not in self.ins_at:
            return False
        self.analyse(entry)
        kinds = self._walk_kinds(entry)
        for i in self.region(entry):
            a = i["addr"]
            if a not in self.sp_at.get(entry, {}):
                continue
            if kinds[a] == "store":
                d = self._store_desc(entry, a)
                if not (d["base"] and all(x[0] == "frame" or x == ("der", "frame") for x in d["base"])):
                    if any(self._frameish(self._base_atoms(entry, a, r)) for r in d["data"]):
                        return f"stored outside the frame at {a:#x}"
            elif kinds[a] == "call" or (self._call_target(i) is not None and self._call_target(i) not in self.sp_at.get(entry, {})
                                        and self._call_target(i) in self.func_entries and self._call_target(i) != entry):
                H = self._handed(entry, a)
                where = {pos: atoms for pos, atoms, _s in H}
                for m, atoms, (_w, _d, kp) in H:
                    for x in self._frameish(atoms) if isinstance(_d, frozenset) else ():
                        for off, ext in sorted(_d, key=str):   # a frame address the callee loads from our object, kept
                            if ext == "KEEP" and (off is None or x[0] != "frame" or x[1] is None
                                                  or self._frameish(self._raw_slot(entry, a, x[1] + off))):
                                return f"handed at {a:#x} ({m}): the callee may keep a frame address it loads from it"
                    if _d == "ALL" and self._frameish(atoms) and self._pointer_slots(entry) != frozenset():
                        return f"handed at {a:#x} ({m}): the callee may keep what it loads from it"
                    if not kp or not self._frameish(atoms):
                        continue
                    for dest in kp:                        # kept in an object of this very frame: not a leak
                        A2 = where.get(dest[0], frozenset()) if dest != "EXT" else frozenset()
                        if not (A2 and all(x[0] == "frame" or x == ("der", "frame") for x in A2)):
                            return f"handed at {a:#x} ({m}) to a routine that may keep it outside this frame"
        return False

    def _call_may_write(self, entry: int, a: int, slot: int):
        """What the call at `a` may leave in the word at the caller's frame slot `slot`: None when it cannot write
        it; else the atoms it may put there — an unknown, and any pointer the callee keeps in that very word."""
        H = self._handed(entry, a)
        where = {pos: atoms for pos, atoms, _s in H}
        out = None
        sp = self._pt_slot(entry, a, 0)
        _reads, sw = self._stack_use_at(entry, a)          # the callee writing its incoming stack words
        if sw is None:
            if sp is None or slot + 4 > sp:
                out = set()
        elif sp is None or any(sp + k < slot + 4 and slot < sp + k + 4 for k in sw):
            out = set() if sw else out
        for _m, atoms, (w, ind, keep) in H:
            for x in self._frameish(atoms):
                A0 = x[1] if x[0] == "frame" else None
                if w == "ALL" or (keep and "EXT" in keep):
                    out = out or set()
                elif w and (A0 is None or any(A0 + off < slot + 4 and (not isinstance(nb, int) or slot < A0 + off + nb) for off, nb in w)):
                    out = out or set()
                if ind and (A0 is None or ind == "ALL"):
                    if self._pointer_slots(entry) != frozenset():
                        out = out or set()
                elif ind:
                    for off, ext in ind:                   # through a pointer the callee loads from our object
                        if off is None:
                            if self._pointer_slots(entry) != frozenset():
                                out = out or set()
                            continue
                        for y in self._frameish(self._raw_slot(entry, a, A0 + off)):
                            if y[0] != "frame" or y[1] is None or isinstance(ext, str) or any(
                                    y[1] + lo < slot + 4 and slot < y[1] + lo + n for lo, n in ext):
                                out = out or set()
            for dest in keep or ():                        # a pointer handed here and kept in the word at `slot`
                for y in self._frameish(where.get(dest[0], ())) if dest != "EXT" else ():
                    if y[0] != "frame" or y[1] is None or (y[1] + dest[1] < slot + 4 and slot < y[1] + dest[1] + 4):
                        out = (out or set()) | set(atoms)
        return None if out is None else out | {("other",)}

    def _pt_read(self, entry: int, site: int, rT: str):
        """What the indirect call at `site` targets: ('VAL', atoms) when the pointer's value AT THE SITE is only
        callbacks and incoming arguments (a constant, a callback passed in, or one reloaded from this routine's own
        frame slot — provably the last word stored there on every path); or (argument, field offset) when it is a
        field load of ONE incoming object. A Finding when it is neither on every path — in particular when a slot of
        this frame it is loaded from may be uninitialised, partially written or overwritten."""
        atoms = self._pt_eval(entry, site, rT)
        if all(x[0] in ("cb", "arg") for x in atoms):
            return ("VAL", frozenset(atoms))
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
                raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} is {w['mnem']} {w['ops']}, not a field load ({sorted(atoms)})")
            batoms = self._pt_eval(entry, w["addr"], base) if base != "sp" else {("frame", None)}
            if len(batoms) == 1 and next(iter(batoms))[0] == "arg":
                keys.add((next(iter(batoms))[1], off))
            elif any(x[0] == "frame" for x in batoms):
                slots = ({self._pt_slot(entry, w["addr"], off)} if base == "sp" else
                         {x[1] + off for x in batoms if x[0] == "frame" and x[1] is not None})
                raise Finding(f"{self.name(entry)}: the callback loaded at {w['addr']:#x} from this routine's own frame is not "
                              f"provably the last callback stored there (uninitialised on a path, partially written, "
                              f"overwritten, or possibly written by a callee): {sorted(atoms)}"
                              + "".join(self._blockers_text(entry, A, w["addr"]) for A in sorted(x for x in slots if x is not None)))
            else:
                raise Finding(f"{self.name(entry)}: the field base {base} at {w['addr']:#x} is neither an incoming argument nor this frame ({sorted(batoms)})")
        if len(keys) != 1:
            raise Finding(f"{self.name(entry)}: the indirect target at {site:#x} is not one object field ({sorted(keys, key=str)})")
        return next(iter(keys))

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
        """The callbacks an application-pointer call at `site` can reach: the pointer's own value at the site, or the
        field it reads of the object bound to its argument — the field's contents AT THE HAND-OVER in the routine
        that built the object. An unbound argument, a field that is not provably initialised with callbacks there
        (uninitialised on a path, partially written, overwritten, or possibly written by a callee), is a Finding —
        never silently empty, never the stale callback, never narrowed to break a cycle."""
        r = self._pointsto(entry)["reads"][site]
        if isinstance(r, Finding):
            raise r
        if r[0] == "VAL":
            return sorted(self._callbacks_of(entry, r[1], binding, f"the pointer called at {site:#x}"))
        argidx, off = r
        v = binding.get(argidx)
        if v is None:
            raise Finding(f"{self.name(entry)}: argument {argidx} of the indirect call at {site:#x} is not bound on the path")
        if v[0] == "ro":
            return sorted(self._ro_field(v[1] + off, f"{self.name(entry)}'s call at {site:#x}"))
        if v[0] != "obj":
            raise Finding(f"{self.name(entry)}: argument {argidx} of the field call at {site:#x} is {v[0]}, not an object")
        return sorted(self._field_callbacks(v[1], v[2] + off, dict(v[3]), v[4]))

    def _callbacks_of(self, R: int, atoms, binding: dict, what: str) -> set:
        """The callbacks a set of atoms of routine `R` denotes: constants directly; an incoming argument resolved in
        the binding active for R. Anything else is a Finding."""
        out = set()
        for atom in sorted(atoms, key=str):                # (a fixed order: the finding names the first non-callback)
            if atom[0] == "cb":
                out.add(atom[1])
            elif atom[0] == "arg":
                b = binding.get(atom[1])
                if b is None or b[0] != "cbs":
                    raise Finding(f"{self.name(R)}: {what} forwards argument {atom[1]}, not bound to a callback")
                out |= set(b[1])
            else:
                raise Finding(f"{self.name(R)}: {what} holds {atom[0]}, not a callback")
        if not out:
            raise Finding(f"{self.name(R)}: {what} has no callback")
        return out

    def _field_callbacks(self, R: int, slot: int, builder_binding: dict, at: int) -> set:
        """The callbacks the field at `R`'s frame slot holds when R hands the object over at the call `at`: the
        slot's value there (`_slot_atoms` — the last store on every path, fully initialised, nothing unknown in
        between), and nothing the call itself may write through the pointer before the field is read."""
        if at not in self.ins_at or not (self._is_call(self.ins_at[at]) or self._call_target(self.ins_at[at]) is not None):
            raise Finding(f"{self.name(R)}: the object's hand-over at {at:#x} is not a call")
        if self._isolated(self._call_may_write, R, at, slot) is not None:
            raise Finding(f"{self.name(R)}: the call at {at:#x} that is handed the object may itself write its field at slot {slot:#x}")
        atoms = self._slot_atoms(R, at, slot)
        if not all(x[0] in ("cb", "arg") for x in atoms):
            raise Finding(f"{self.name(R)}: the field at slot {slot:#x} is not provably initialised with a callback at the "
                          f"hand-over {at:#x} (uninitialised on a path, partially written, overwritten, or possibly "
                          f"written by a callee): {sorted(atoms)}" + self._blockers_text(R, slot, at))
        return self._callbacks_of(R, atoms, builder_binding, f"the field at slot {slot:#x}")

    def _bind_one(self, caller: int, atoms: set, binding: dict, site: int):
        """A binding value for one argument from its atoms at the call `site`: ('obj', caller, A, the caller's
        binding, site) for a frame struct, ('cbs', frozenset) for one or more callbacks passed directly, or a
        forwarded argument resolved through `binding`. Ambiguous mixtures (object and callback, or an unknown) are
        left unbound (None) so the callee Findings rather than guess. Several callbacks are all kept."""
        kinds = {a[0] for a in atoms}
        if kinds == {"cb"}:
            return ("cbs", frozenset(a[1] for a in atoms))
        if len(atoms) == 1 and kinds == {"tab"}:          # a read-only table of the image (`_ro_table_proof`)
            x = next(iter(atoms))
            return ("ro", x[1] + x[2]) if x[2] is not None else None
        if atoms and all(a[0] == "frame" for a in atoms):
            A = {a[1] for a in atoms}
            return ("obj", caller, next(iter(A)), frozenset(binding.items()), site) if len(A) == 1 and None not in A else None
        if atoms and all(a[0] == "arg" for a in atoms):
            vals = {binding.get(a[1]) for a in atoms}
            return next(iter(vals)) if len(vals) == 1 else None
        return None

    def _child_binding(self, caller: int, site: int, callee: int, binding: dict) -> frozenset:
        """The object binding a direct call at `site` gives its callee, PULLED by what the callee uses: for each
        argument identifier the callee dereferences or forwards (`needs`), the caller's register or outgoing stack
        slot AT THE CALL — a struct in the caller's own frame, callbacks, or the caller's own argument forwarded
        through `binding`. An ambiguous or non-object value is left unbound (the callee then Findings)."""
        needs = self._pointsto(callee).get("needs", frozenset())
        if not needs:
            return frozenset()
        self.analyse(caller)
        offs = self.sp_at[caller].get(site, frozenset()) if caller in self.sp_at else frozenset()
        spoff = next(iter(offs)) if len(offs) == 1 else None
        cb = {}
        for arg in sorted(needs, key=str):
            if isinstance(arg, int):                                   # a register argument
                v = self._bind_one(caller, self._pt_eval(caller, site, f"r{arg}"), binding, site)
            elif spoff is not None:                                    # an outgoing stack argument
                v = self._bind_one(caller, self._slot_atoms(caller, site, arg[1] - spoff), binding, site)
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

    TAINTED = "__tainted__"                             # (in a depth memo: the nodes with a finding at or under them)

    def depth(self, entry: int, ctx: tuple | None = None, path: tuple = (), memo: dict | None = None,
              collect: dict | None = None) -> int:
        """The deepest stack use from `entry`. With `collect` (a dict) a Finding does not end the walk: it is
        recorded once — {its text: [what is left unwalked because of it]}, what lies under the edge that raised it
        being left unwalked — the other edges are walked on, and the node, with every node above it, is marked in
        memo[TAINTED]: the number returned for a tainted node is NOT a bound."""
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
        tainted = memo.setdefault(self.TAINTED, set())
        bad = False

        def note(f, what):
            if collect is None:
                raise f
            left = collect.setdefault(str(f), [])
            if what not in left:
                left.append(what)
        for e in self.edges[entry]:
            if skip is not None and e.get("site") == skip:
                continue
            try:
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
            except Finding as f:
                note(f, f"what {self.name(entry)}'s call at {e.get('site')} reaches")
                bad = True
                continue
            for t in tgts:
                cctx = (child, self._reentry(entry, e, t, here))
                try:
                    d = max(d, e["at"] + self.depth(t, cctx, here, memo, collect))
                except Finding as f:
                    note(f, f"{self.name(t)}, called by {self.name(entry)} at {e.get('site')}")
                    bad = True
                else:
                    bad = bad or (t, cctx) in tainted
        memo[key] = d
        if bad:
            tainted.add(key)
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
MAX_PASSES = 12
# what the callback resolution rests on beyond the image's own instructions, recorded with the result; `targets`
# names the C-library routines whose contract (Image.LIBC_CONTRACTS) the analysis actually used on this image
VALUE_MODEL = ("a callback read from a frame slot or an object's field is the LAST word stored there on every path to "
               "the read / the hand-over (flow-sensitive, by the bytes each store writes; a conditional, partial, "
               "overlapping, register-indexed or frame-derived store, a path with no store, and a call that may store "
               "through a pointer reaching the slot each make it unknown, which is a finding). A call is held against "
               "its callee's summary — read off the code of every routine in the image, prebuilt ones included, or a "
               "named contract (rules.callback_contracts): what it may write through each pointer it is handed (signed "
               "offsets; an unbounded write reaches every slot of the frame, in either direction), what it writes "
               "through the words it loads from the object, and whether it may keep the pointer — for every position "
               "it can be handed one: the four argument registers, the stack words a readable callee reads, and for a "
               "callee that cannot be read every frame word that may hold an address. A frame address stored outside "
               "the frame or handed to a routine that may keep it LEAKS that frame (rules.frame_leaks): from then on "
               "any call, and any store through a pointer that is not provably elsewhere, may write any of its slots. "
               "A call clobbers the caller-saved registers its target's code writes (GCC's inter-procedural register "
               "allocation relies on the same). NO OBJECT PROVENANCE IS ASSUMED (the former B1 is removed): a frame "
               "cell stands only if every write on the paths from its store to the read is PLACED off it "
               "(rules.write_placement) — the routine's own stores that are not into its frame, every pointer a call is "
               "handed that its callee writes through, and every write of every routine the call can reach, each "
               "indirect call by its rule's whole context-free target set. A frame write is placed only inside its "
               "routine's own frame; a callee's incoming stack-argument area is its caller's frame. A write that is "
               "not placed, a frame range that leaves its frame, a constant range in the stacks' region and a target "
               "set that does not resolve each leave the cell unknown, with what blocked it recorded "
               "(result.frame_cells; each unresolved cell is a finding). SCOPE — SYNCHRONOUS PATHS ONLY: what an "
               "exception taken between a cell's store and its read may write is NOT covered, and no handler's "
               "writes are analysed; that the image never clears the I / F masks is recorded (masks), not used as "
               "proof that no handler runs; while this stands no bound is published for an entry that calls through "
               "memory. STATED, NOT PROVED FROM THE IMAGE: (B2) the "
               "callee-saved registers are preserved across a call (the AAPCS); (B3) a routine's contract is its "
               "source semantics as stated in it — bound to the source and code digests and self-checked, not derived")
PRINTF_RULE = ("each printf-family call the callback resolution relied on: its format is a constant string in a "
               "read-only section on every path — directly, or as the calling routine's own argument, constant at every "
               "call of that routine, which is not address-taken — and has no %n conversion; a call whose format is "
               "not so proved is taken to write through every pointer it can see")
CONTRACT_RULE = ("the named routines are taken at their contract (Image.CONTRACTS: the bytes each may write through "
                 "each argument, that it keeps no pointer, what it returns), each read from its source and bound to "
                 "that source's digest and to the digest of its code closure in this image, and self-checked against "
                 "the writes and keeps its own instructions show; listed: the contracts the analysis used")
RO_RULE = ("a callback read from a field of a .rodata table is the ELF's word there: the table's address is materialised "
           "only by the image's own units and stored in no data word; it is never stored outside a frame nor returned, "
           "no call it is handed to keeps it; and NO write of the image, through any pointer, may reach one of its "
           "bytes — every store and every pointer handed to a writer is placed by the address range it reaches "
           "(rules.write_placement), and one that overlaps the table or is not placed refuses it; listed: each table "
           "so proved, who materialises it and which fields were read")
WRITE_RULE = ("every write of every routine in the image — each store, and each call or tail handing a pointer the callee "
              "writes through — is placed by the bytes it may reach: a constant or a frame slot with a known extent, or "
              "the routine's own argument at a known offset (then placed at each call that hands it, when every way "
              "into the routine is such a call); a frame slot only INSIDE the routine's own frame — its incoming "
              "stack-argument area is its caller's, placed there — and each indirect call's callee is its rule's "
              "whole context-free target set. A write that is not so placed is not proved to miss any callback "
              "cell, whatever object it was meant for: each is a finding, and while any remains no bound is published "
              "for an entry that calls through a pointer read from memory. A routine taken at its contract has its "
              "writes through its own arguments placed at its callers by that contract. Placed writes overlapping an "
              "object that holds callback cells are listed. listed: the totals; result.writes has every site")
ARITY_RULE = ("the argument registers a call of a C-library routine at its contract hands it (the owner's ruling of "
              "2026-10-08): its C prototype's (Image.LIBC_ARITY), and only where the member's own code, read in this "
              "image, uses no register at or above that number on entry — not read by an instruction, not handed to a "
              "callee whose own arity is not shown to exclude it, not to an indirect call, not returned (by a pop / ldm "
              "into r0: what it loads), a save neither read back unpinned nor its frame handed on, in an argument "
              "register or in an incoming word the callee reads; a routine that does not show it, or that depends on itself to, hands all four. snprintf's "
              "variadic arguments occupy the registers and incoming stack words each proved format puts them in by the "
              "AAPCS base standard (promoted sizes; an 8-byte one at an even register or an 8-byte aligned stack word, "
              "and after one goes to the stack every later one does), the union over the call's formats; a format not "
              "proved or not sized: all four registers and every incoming word. vsnprintf reads none of its own incoming "
              "words; its va_list (r3) is handed like any pointer. An arity is what a call HANDS only: what the callee "
              "clobbers, returns and writes is as before. The named callback contracts (Image.CONTRACTS) still hand all "
              "four registers (not in this unit). listed: each routine's arity, or why it hands all four, and each "
              "printf-family call's layout")
LEAK_RULE = ("the routines one of whose frame addresses may come to rest outside the frame (stored there, or handed to a "
             "routine that may keep it): no callback is resolved from such a frame")


def assess(elf: Path = ELF_DEFAULT) -> dict:
    """The whole assessment: per entry its bound and its mode's stack, the frames, the edges, the indirect target
    sets, the CPSR writes, and every unresolved finding. `ok` only when there is no finding."""
    elf = Path(elf)
    try:                                               # (the owner's HOLD on 78c2bb0, P2) keyed by EVERYTHING the result
        ck = _digest(proof_inputs(elf))                # rests on, not by the ELF alone; no key, no cache
    except Exception:                                  # noqa: BLE001 — an input that cannot be read: assess afresh
        ck = None
    if ck is not None and ck in _ASSESS_CACHE:
        return _ASSESS_CACHE[ck]
    result = assess_image(Image(elf))
    if ck is not None:
        _ASSESS_CACHE[ck] = result
    return result


def _digest(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()


def proof_inputs(elf: Path) -> dict:
    """Every input an assessment's result rests on, by content: the ELF; this analyzer's source and the tables it
    holds AS THEY ARE NOW (the contracts, their bound source and code digests, the library contracts, the newlib
    rule's pins, the limits); each contract unit's CURRENT source digest (through Image._unit_sha, the reader the
    contract check itself uses); the root those sources are read from; the prebuilt archives the link used; the
    newlib version header; the binutils the image is read with and the compiler the FILE-layout probe runs, with the
    build's flags. Two assessments with equal inputs are the same assessment; nothing else may share a cached one."""
    import b3_build_evidence as be
    hdr = Path(b2be.TC) / Image.NEWLIB["version_header"]
    cc = Path(be.trusted_compiler())
    return {"elf": sha256_file(elf),
            "analyzer": sha256_file(Path(__file__)),
            "tool": TOOL_VERSION,
            "tables": _digest([Image.CONTRACTS, Image.CONTRACT_SOURCES, Image.CONTRACT_CODE, Image.LIBC_CONTRACTS, Image.NEWLIB,
                               list(Image.APP_UNITS), list(Image.PROTECTED_OBJECTS), list(Image.PROTECTED_SECTIONS),
                               MAIN_LIMIT, STACK_TOPS, list(NAMED_CHAINS), Image.LIBC_ARITY, sorted(Image.LIBC_VARIADIC)]),
            "source_root": str(REPO_ROOT),
            "contract_sources": {u: Image._unit_sha(None, u) for u in sorted(Image.CONTRACT_SOURCES)},
            "archives": {k: [str(v), sha256_file(v)] for k, v in sorted(runtime_archives().items())},
            "newlib_header": sha256_file(hdr) if hdr.is_file() else None,
            "binutils": {n: sha256_file(Path(tool(n))) for n in ("objdump", "nm", "readelf", "ar")},
            "compiler": [str(cc), sha256_file(cc)],
            "flags": [list(x) for x in be.build_flags()]}


def settle(img: "Image", fn, unsettled=None):
    """fn(image) on passes until every speculative read agrees with the value then computed (see Image._guarded):
    each pass runs on a fresh copy of `img` (left unanalysed), the previous pass's final values as its guesses. A
    Finding raised in the settled pass is raised; one raised in a pass whose speculation failed is not trusted."""
    if "_spec" in img.__dict__ or getattr(img, "_pt_eval_memo", None) or any(k.startswith("_memo_") for k in img.__dict__):
        raise ValueError("settle needs an image no value analysis has run on (its guesses would be unverified)")
    guesses: dict = {}
    for attempt in range(MAX_PASSES):
        im = copy.deepcopy(img)                            # (the image handed in is never analysed itself)
        im._guesses = dict(guesses)
        try:
            out, err = fn(im), None
        except Finding as e:
            out, err = None, e
        failed = im._speculation_failed()
        if not failed:
            im.__dict__["_passes"] = attempt + 1
            if err is not None:
                raise err
            return out
        guesses.update(failed)
    msg = f"the analysis did not settle in {MAX_PASSES} passes: {sorted(map(str, failed))[:4]}"
    if unsettled is not None and err is None:
        return unsettled(out, msg)                         # (the last pass's result, refused)
    raise Finding(msg)


def assess_image(img: "Image") -> dict:
    """The assessment of one loaded Image (what `assess` runs; a test hands it an Image it has altered in memory, to
    show that the sub-proof the alteration breaks is refused and no bound is published), settled (`settle`)."""
    return settle(img, _assess_once, unsettled=lambda r, msg: dict(r, findings=r["findings"] + [msg], ok=False))


def _assess_once(img: "Image") -> dict:
    findings: list[str] = []
    elf = img.elf
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
    collected: dict = {}                                   # (the owner's ruling 4: every finding the walk can decide
    listed: set = set()                                    # independently, not only the first)

    def walked(prefix: str) -> list[str]:
        """The findings collected since the last call, each with what was left unwalked because of it."""
        out = []
        for msg, left in collected.items():
            if msg not in listed:
                listed.add(msg)
                out.append(f"{prefix}: {msg}" + (f" [not walked, depending on this: {left[0]}"
                                                 + (f" and {len(left) - 1} more" if len(left) > 1 else "") + "]" if left else ""))
        return out
    for entry, (addr, mode) in entries.items():
        try:
            d = img.depth(addr, None, (), memo, collected)
            bad = (addr, img.ROOT_CTX) in memo.get(img.TAINTED, ())
        except Finding as e:                               # (the entry itself cannot be walked)
            collected.setdefault(str(e), [])
            d, bad = None, True
        if bad:
            findings.extend(walked(f"{entry} ({img.name(addr)})") or
                            [f"{entry} ({img.name(addr)}): its path reaches a routine with a finding listed under an earlier entry"])
            bounds[entry] = {"function": img.name(addr), "mode": mode, "bound": None, "capacity": capacity.get(mode)}
            continue
        bounds[entry] = {"function": img.name(addr), "mode": mode, "bound": d, "capacity": capacity.get(mode)}
        limit = MAIN_LIMIT if entry == "main" else capacity.get(mode)
        if limit is None or d > limit:
            findings.append(f"{entry} ({img.name(addr)}): bound {d} exceeds {limit}")
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
                d = img.depth(a, None, (), memo, collected)
                if (a, img.ROOT_CTX) in memo.get(img.TAINTED, ()):
                    findings.extend(walked(n) or [f"{n}: its chain reaches a routine with a finding listed above"])
                    d = None
                named[n] = {"chain": d, "local": img.local[a]}
            except Finding as e:
                findings.append(f"{n}: {e}")
    try:                                                   # (the owner's strict ruling of 2026-10-06)
        writes = img.write_inventory()
    except Finding as e:
        writes = {"routines": {}, "total": {}, "unproved": None, "protected": [], "stacks": None}
        findings.append(f"the image's writes could not be inventoried: {e}")
    for n, rec in writes["routines"].items():
        sites = sorted({x for v in rec.get("not_placed_at", {}).values() for x in v})
        if sites:
            findings.append(f"{n}: {len(sites)} write(s) not placed — not proved to miss the callback cells: {', '.join(sites)}")
        for obj, at in rec.get("overlapping_at", {}).items():
            findings.append(f"{n}: {len(at)} placed write(s) overlapping {obj}: {', '.join(at)}")
    try:                                                   # (the frame unit: every frame cell has a result)
        cells = img.frame_cells()
    except Finding as e:
        cells = []
        findings.append(f"the image's frame cells could not be listed: {e}")
    for c in cells:
        if not c["resolved"]:                              # (one line per cell; the same reason at several places once)
            by: dict = {}
            for b in c["blocked_by"]:
                by.setdefault(b["why"], []).append(b["at"])
            findings.append(f"{c['routine']}: the frame cell at slot {c['slot']:#x} (it may hold {', '.join(c['holds'])}) is not "
                            f"resolved: " + "; ".join(f"{why} [at {', '.join(ats)}]" for why, ats in by.items()))
    for _k, v in sorted(img._cache("_memo_printf").items()):   # a printf whose format is not proved is not hidden in
        if not v[0]:                                            # the rule's list: it is a finding of its own
            findings.append(f"{v[1]['call']}: its format is not a provable constant string free of %n (a value held in a frame "
                            f"slot is unknown after a call under which a write is not placed): it is taken to write "
                            f"through every pointer it can see")
    open_cells = sum(1 for c in cells if not c["resolved"])
    # No bound for an entry whose targets are words in memory: while a write is unproved or a frame cell unresolved —
    # and, in this version, at all: the cells are held against the SYNCHRONOUS paths only (VALUE_MODEL's scope)
    reasons = ([f"{writes['unproved']} write(s) of the image are not proved to miss those cells"] if writes["unproved"] != 0 else []) \
        + ([f"{open_cells} frame cell(s) are not resolved"] if open_cells else []) \
        + ["what an exception taken between a cell's store and its read may write is not covered (synchronous paths only)"]
    for entry, (addr, _mode) in entries.items():
        try:
            through = img.calls_through_memory(addr)
        except Finding:
            through = True
        if through and bounds.get(entry, {}).get("bound") is not None:
            findings.append(f"{entry} ({img.name(addr)}): no bound is published — it calls through pointers read from memory, and "
                            + "; ".join(reasons))
            bounds[entry] = dict(bounds[entry], bound=None, unpublished=bounds[entry]["bound"])
    for n in list(named):
        try:
            through = img.calls_through_memory(img.syms[n][0] & ~1)
        except Finding:
            through = True
        if through and named[n]["chain"] is not None:
            findings.append(f"{n}: no chain bound is published — it calls through pointers read from memory")
            named[n] = dict(named[n], chain=None, unpublished=named[n]["chain"])
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
                   "writes": writes,
                   "frame_cells": cells,
                   "rules": dict({n: {"rule": r["rule"], "targets": [img.name(t) for t in r["targets"]]} for n, r in sorted(img.site_rules.items())},
                                 value_model={"rule": VALUE_MODEL, "targets": sorted(img._cache("_libc_used"))},
                                 printf_formats={"rule": PRINTF_RULE,
                                                 "targets": [v[1] for _k, v in sorted(img._cache("_memo_printf").items())]},
                                 write_placement={"rule": WRITE_RULE, "targets": [
                                     f"{k.replace('_', ' ')}: {v}" for k, v in sorted(writes["total"].items())]},
                                 libc_arity={"rule": ARITY_RULE, "targets": img.arity_targets()},
                                 frame_leaks={"rule": LEAK_RULE, "targets": [f"{n}: {w}" for n, w in sorted(img._cache("_leaks").items())]},
                                 callback_contracts={"rule": CONTRACT_RULE, "targets": [
                                     f"{n}: {c['unit']} {c['source_sha256'][:16]}… code {c['code_sha256'][:16]}… arity "
                                     f"{c['arity']} writes {json.dumps(c['writes'], sort_keys=True)} returns {c['returns']} — {c['source']}"
                                     for n, c in sorted(img._cache("_contracts_used").items())]},
                                 read_only_tables={"rule": RO_RULE, "targets": [
                                     f"{img._ro_tables()[T][0]}: materialised by {', '.join(img._cache('_ro_users').get(img._ro_tables()[T][0], []))}; "
                                     f"read {', '.join(f'+{off:#x} {cb}' for (tn, off), cb in sorted(img._cache('_ro_reads').items()) if tn == img._ro_tables()[T][0])}"
                                     for T in sorted(img._ro_tables()) if img._cache("_memo_roproof").get(T, "x") is None]}),
                   "application_pointers": img.produced,
                   "newlib": img._newlib,
                   "main_limit": MAIN_LIMIT,
                   "findings": findings, "ok": not findings})
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
