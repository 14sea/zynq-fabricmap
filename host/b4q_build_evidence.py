#!/usr/bin/env python3
"""B4Q — build provenance for the PS image (host-only; touches no board), after B1's host/b1_build_evidence.py.

    b4q_build_evidence.py [--build] [--out evidence/b4/unit_b4q_image_2026_10_28/build_evidence.json]

With `--build`: two clean builds from scratch (`rm -rf build/b4q_image` between them) through firmware/b4q/bsp/build.sh; the two
raw .bin images must be byte-identical or the evidence says `reproduced_byte_identical: false` and the exit is non-zero (that
boolean covers the raw .bin only; the ELF / map hashes are provenance, path- and debug-dependent). Always: the
sha256 of the image, the ELF and the map; of every source the image links (this repository's b4q_* files, the target's units,
the BSP glue — B1's console.c / lscript.ld / headers byte for byte); of the toolchain's compiler binary; and — from the
compiler's own `-M` dependency output over every translation unit with the flags build.sh uses — every header the build reads
(embeddedsw's, this repository's, the toolchain's own), each by sha256; the toolchain's runtime objects and libraries as the
link resolves them; the ELF's entry point, its program headers and sections, the addresses of the symbols that matter (the
vector table, main, the application's entry, the stack / heap bounds) and the DDR buffer layout the image assumes (from the
pure allowlist's constants). The image bytes are not committed (build/ is ignored); the evidence pins them by hash and a later
runner checks the file it is handed against the pin. An unavailable input is reported by name, never worked around."""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FW = REPO_ROOT / "firmware/b4q"
OUT = REPO_ROOT / "build/b4q_image"
BUILD = FW / "bsp/build.sh"
INSTRUMENT = Path(os.environ.get("PSORACLE_ROOT", "/home/test/zynq_psoracle"))
TC = INSTRUMENT / "toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1"
SA = Path(os.environ.get("EMBEDDEDSW_STANDALONE", "/home/test/Xilinx/2025.2/data/embeddedsw/lib/bsp/standalone_v9_4/src"))
WD = Path(os.environ.get("EMBEDDEDSW_SCUWDT", "/home/test/Xilinx/2025.2/data/embeddedsw/XilinxProcessorIPLib/drivers/scuwdt_v2_6/src"))
IMAGE = "b4q_app"
APP_SOURCES = ("target/b4q_board_main.c", "target/b4q_board_hal.c", "target/b4q_board_console.c", "target/b4q_app.c", "target/b4q_app.h", "target/b4q_wire.c", "target/b4q_wire.h",
               "target/b4q_psmap.c", "target/b4q_psmap.h", "target/b4q_console.h", "target/b4q_platform.h",
               "b4q_tx.c", "b4q_tx.h", "b4q_cmd.c", "b4q_cmd.h", "b4q_derive.c", "b4q_derive.h", "b4q_hal.h", "b4q_data.h", "b4q_regmap.h",
               "bsp/build.sh", "bsp/lscript.ld", "bsp/src/console.c", "bsp/include/bspconfig.h", "bsp/include/xmem_config.h", "bsp/include/xparameters.h")
B1_VERBATIM = {"bsp/lscript.ld": "firmware/b1/bsp/lscript.ld", "bsp/src/console.c": "firmware/b1/bsp/src/console.c", "bsp/include/bspconfig.h": "firmware/b1/bsp/include/bspconfig.h",
               "bsp/include/xmem_config.h": "firmware/b1/bsp/include/xmem_config.h", "bsp/include/xparameters.h": "firmware/b1/bsp/include/xparameters.h"}
SYMBOLS = ("_vector_table", "_boot", "_start", "main", "b4q_app_run", "b4q_transaction", "b4q_session_open", "b4q_sign", "b4q_rd32", "b4q_wr32", "outbyte", "inbyte",
           "_heap_start", "_heap_end", "__stack", "_end", "_bss_start", "_bss_end")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args: str) -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def tool(name: str) -> Path:
    return TC / "bin" / f"arm-none-eabi-{name}"


def build_once() -> str:
    if OUT.exists():
        shutil.rmtree(OUT)
    p = subprocess.run(["bash", str(BUILD)], capture_output=True, text=True, env={**os.environ, "OUT": str(OUT)})
    if p.returncode != 0:
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
    return sha(OUT / f"{IMAGE}.bin")


def build_script_sources() -> dict[str, list[str]]:
    text = BUILD.read_text()
    out = {}
    for name in ("ASM_SRCS", "C_SRCS", "SYS_SRCS", "WDT_SRCS", "APP_SRCS"):
        m = re.search(name + r'="([^"]*)"', text, re.S)
        if not m:
            raise RuntimeError(f"build.sh: {name} not found")
        out[name] = m.group(1).replace("\\\n", " ").split()
    return out


def inputs() -> dict:
    """EVERY file the build reads, by hash: the translation units (BSP, syscalls, watchdog, the console glue, the application),
    every header any of them includes (gcc -M with the flags build.sh uses), the toolchain's runtime objects and libraries."""
    cc = tool("gcc")
    arch = ["-mcpu=cortex-a9", "-mfpu=vfpv3", "-mfloat-abi=hard"]
    inc = [f"-I{FW / 'bsp/include'}", f"-I{SA}/common", f"-I{SA}/arm/common", f"-I{SA}/arm/common/gcc", f"-I{SA}/arm/cortexa9", f"-I{SA}/arm/cortexa9/gcc", f"-I{WD}"]
    srcs = build_script_sources()
    units: list[tuple[Path, list[str]]] = []
    bsp_flags = [*arch, "-std=gnu11", "-DUSE_AMP=0", *inc]
    app_flags = [*arch, "-std=c99", "-ffreestanding", *inc, f"-I{FW}", f"-I{FW / 'target'}"]
    for s in srcs["ASM_SRCS"] + srcs["C_SRCS"] + srcs["SYS_SRCS"]:
        units.append((SA / s, bsp_flags))
    for s in srcs["WDT_SRCS"]:
        units.append((WD / s, bsp_flags))
    units.append((FW / "bsp/src/console.c", bsp_flags))
    for s in srcs["APP_SRCS"]:
        units.append((FW / s, app_flags))
    tus, headers = {}, {}
    for src, flags in units:
        if not src.is_file():
            raise RuntimeError(f"build input missing: {src}")
        tus[str(src)] = sha(src)
        p = subprocess.run([str(cc), *flags, "-M", str(src)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{src}: {p.stderr[-1000:]}")
        for tok in p.stdout.replace("\\\n", " ").split()[1:]:
            path = Path(tok)
            if path.is_file() and path.resolve() != src.resolve():
                headers[str(path)] = sha(path)
    objs = {}
    for name in ("crti.o", "crtbegin.o", "crtend.o", "crtn.o", "libgcc.a", "libc.a", "libm.a"):
        p = subprocess.run([str(cc), *arch, f"-print-file-name={name}"], capture_output=True, text=True)
        path = Path(p.stdout.strip())
        objs[name] = {"path": str(path), "sha256": sha(path) if path.is_file() else None}
    return {"translation_units": dict(sorted(tus.items())), "headers": dict(sorted(headers.items())), "toolchain_objects": objs, "build_script_lists": srcs,
            "header_roots": {"embeddedsw_standalone": str(SA), "embeddedsw_watchdog": str(WD), "firmware": str(FW), "toolchain": str(TC)}}


def layout(elf: Path) -> dict:
    """The ELF's entry, program headers, sections and the symbols that matter — read from the ELF, never from the source."""
    rh = subprocess.run([str(tool("readelf")), "-h", "-l", "-S", "-W", str(elf)], capture_output=True, text=True).stdout
    entry = re.search(r"Entry point address:\s+(0x[0-9a-f]+)", rh)
    phdrs = [{"type": m.group(1), "offset": m.group(2), "vaddr": m.group(3), "paddr": m.group(4), "filesz": m.group(5), "memsz": m.group(6), "flags": m.group(7).strip()}
             for m in re.finditer(r"^\s+(LOAD|[A-Z_]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+(0x[0-9a-f]+)\s+([RWE ]+)\s+0x[0-9a-f]+", rh, re.M)]
    sections = [{"name": m.group(1), "type": m.group(2), "addr": m.group(3), "size": m.group(4)}
                for m in re.finditer(r"^\s+\[\s*\d+\]\s+(\.\S+)\s+(\S+)\s+([0-9a-f]{8})\s+[0-9a-f]+\s+([0-9a-f]{6})", rh, re.M)]
    nm = subprocess.run([str(tool("nm")), str(elf)], capture_output=True, text=True).stdout
    syms = {}
    for line in nm.splitlines():
        parts = line.split()
        if len(parts) == 3 and parts[2] in SYMBOLS:
            syms[parts[2]] = {"addr": "0x" + parts[0], "kind": parts[1]}
    size = subprocess.run([str(tool("size")), str(elf)], capture_output=True, text=True).stdout.splitlines()
    return {"entry": entry.group(1) if entry else None, "program_headers": phdrs, "sections": sections, "symbols": syms, "size": size[-1].split()[:4] if len(size) > 1 else None}


def buffers() -> dict:
    """The DDR layout the image assumes, from the pure allowlist's constants (the same the host harness and the A7 regions use)."""
    text = (FW / "target/b4q_psmap.h").read_text()
    consts = {m.group(1): int(m.group(2), 16) for m in re.finditer(r"#define (B4Q_PSMAP_\w+) (0x[0-9A-Fa-f]+)u", text)}
    hdr = (FW / "b4q_derive.h").read_text()
    words = {k: int(m.group(1)) for k, pat in (("READBACK_CMD_WORDS", r"#define P3_READBACK_CMD_WORDS (\d+)"), ("READBACK_WORDS", r"#define P3_READBACK_WORDS (\d+)"),
                                               ("STREAM_WORDS", r"#define P3_STREAM_WORDS (\d+)"), ("ENVELOPE_COUNT", r"#define P3_ENVELOPE_COUNT (\d+)")) if (m := re.search(pat, hdr))}
    return {"load_address": "0x02000000", "go": "go 0x2000000 (U-Boot: the raw .bin at the load address, the vector table first — the instrument's L5 recipe)",
            "ddr_region_of_the_image": "0x02000000 .. 0x0FF00000 (lscript.ld ps7_ddr_0)",
            "CMD_BUF": {"addr": f"{consts['B4Q_PSMAP_CMD_BUF']:#010x}", "words": words.get("READBACK_CMD_WORDS")},
            "DST_BUF": {"addr": f"{consts['B4Q_PSMAP_DST_BUF']:#010x}", "words": words.get("READBACK_WORDS")},
            "WR_BUF": {"addr": f"{consts['B4Q_PSMAP_WR_BUF']:#010x}", "words": (words.get("STREAM_WORDS") or 0) * (words.get("ENVELOPE_COUNT") or 0), "envelopes": words.get("ENVELOPE_COUNT")},
            "PAGE": {"addr": f"{consts['B4Q_PSMAP_PAGE_ADDR']:#010x}", "words": 24, "written_by": "the host before go (mw.l), read-only for the program"},
            "mmu": "the four 1 MiB sections holding CMD_BUF / DST_BUF / WR_BUF / PAGE mapped strongly-ordered non-cacheable (Xil_SetTlbAttributes 0x14de2) before any access; the image's own code / data cacheable",
            "carrier_window": f"{consts['B4Q_PSMAP_AXI_BASE']:#010x} (+{consts['B4Q_PSMAP_AXI_SIZE']:#x})", "devcfg": f"{consts['B4Q_PSMAP_DEVCFG_BASE']:#010x}", "slcr_idcode": f"{consts['B4Q_PSMAP_SLCR_PSS_IDCODE']:#010x}"}


def build_evidence(do_build: bool) -> dict:
    available = {"toolchain": tool("gcc").is_file(), "embeddedsw_standalone": (SA / "common/xil_io.h").is_file(), "embeddedsw_scuwdt": (WD / "xscuwdt.h").is_file()}
    hashes = []
    if do_build and all(available.values()):
        hashes = [build_once(), build_once()]
    image, elf, mp = OUT / f"{IMAGE}.bin", OUT / f"{IMAGE}.elf", OUT / f"{IMAGE}.map"
    ev = {"schema": "b4q_build_evidence", "schema_version": "1.0.0", "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
          "standing": "a host-only build record: the image was COMPILED, never loaded on a board; nothing here is on-target evidence",
          "git": {"head": git("rev-parse", "HEAD"), "worktree_dirty": bool(git("status", "--porcelain"))},
          "inputs_available": available,
          "toolchain": {"path": str(TC), "gcc_sha256": sha(tool("gcc")) if available["toolchain"] else None,
                        "version": subprocess.run([str(tool("gcc")), "--version"], capture_output=True, text=True).stdout.splitlines()[0] if available["toolchain"] else None,
                        "instrument_role": "read-only use of the archived instrument's toolchain directory"},
          "sources": {s: sha(FW / s) for s in APP_SOURCES},
          "b1_verbatim": {s: {"base": b, "equal": (FW / s).read_bytes() == (REPO_ROOT / b).read_bytes()} for s, b in B1_VERBATIM.items()},
          "bsp_inputs": inputs() if all(available.values()) else {},
          "image": {"path": str(image.relative_to(REPO_ROOT)), "sha256": sha(image) if image.is_file() else None, "bytes": image.stat().st_size if image.is_file() else None,
                    "elf_sha256": sha(elf) if elf.is_file() else None, "map_sha256": sha(mp) if mp.is_file() else None,
                    "layout": layout(elf) if elf.is_file() and available["toolchain"] else None, "ddr": buffers()},
          "reproducibility": {"builds": hashes, "reproduced_byte_identical": (len(hashes) == 2 and hashes[0] == hashes[1]) if do_build else None,
                              "covers": "the raw .bin only: two clean builds from scratch produce the same raw image bytes (the digests in `builds`); the ELF and the map are provenance artifacts whose hashes carry debug sections and checkout paths and may differ between checkouts — their layout facts (entry, program headers, symbols) are what the ELF test holds, not their file hashes (the owner's P3 of 2026-10-28)"}}
    return ev


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/b4/unit_b4q_image_2026_10_28/build_evidence.json")
    a = ap.parse_args(argv)
    ev = build_evidence(a.build)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ev, indent=1) + "\n")
    print(f"image {ev['image']['sha256']} reproduced {ev['reproducibility']['reproduced_byte_identical']} inputs {ev['inputs_available']} -> {a.out}")
    return 0 if (not a.build or ev["reproducibility"]["reproduced_byte_identical"]) else 1


if __name__ == "__main__":
    sys.exit(main())
