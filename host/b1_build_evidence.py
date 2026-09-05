#!/usr/bin/env python3
"""B1 — build provenance for the image (host-only; touches no board).

    b1_build_evidence.py [--build] [--out evidence/b1/build_evidence.json]

With `--build`: two clean builds from scratch (`rm -rf firmware/b1/bsp/out` between them)
through `firmware/b1/bsp/build.sh`; the two binaries must be byte-identical or the evidence
says `reproduced_byte_identical: false` and the exit is non-zero. Always: the sha256 of the
image and the ELF, of every source the image links (this repository's b1_* files and the
verbatim instrument imports), of the generated data header, of the toolchain's compiler
binary, and — from the compiler's own `-M` dependency output over b1_app.c — every
embeddedsw header the build reads, each by sha256 (the instrument's
`gen_bsp_input_manifest.py` discipline). The image bytes are not committed (bsp/out is
gitignored, as the instrument's is); the evidence and the manifest pin them by hash, and
the runner checks the file it is handed against the pin.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FW = REPO_ROOT / "firmware/b1"
OUT = FW / "bsp/out"
BUILD = FW / "bsp/build.sh"
INSTRUMENT = Path(os.environ.get("PSORACLE_ROOT", "/home/test/zynq_psoracle"))
TC = INSTRUMENT / "toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1"
SA = Path("/home/test/Xilinx/2025.2/data/embeddedsw/lib/bsp/standalone_v9_4/src")
WD = Path("/home/test/Xilinx/2025.2/data/embeddedsw/XilinxProcessorIPLib/drivers/scuwdt_v2_6/src")
APP_SOURCES = ("b1_app.c", "b1_carto.c", "b1_carto.h", "b1_orch.c", "b1_orch.h", "b1_wire.c", "b1_wire.h", "p3_data.h",
               "p3_derive.c", "p3_derive.h", "p3_rectx.c", "p3_rectx.h", "p3_pull.c", "p3_pull.h",
               "bsp/build.sh", "bsp/lscript.ld", "bsp/src/console.c",
               "bsp/include/bspconfig.h", "bsp/include/xmem_config.h", "bsp/include/xparameters.h")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args: str) -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def build_once() -> str:
    if OUT.exists():
        shutil.rmtree(OUT)
    p = subprocess.run(["bash", str(BUILD)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
    return sha(OUT / "b1_app.bin")


def build_script_sources() -> dict[str, list[str]]:
    """The BSP translation units build.sh compiles, read from build.sh itself (one source of
    truth): ASM_SRCS / C_SRCS / SYS_SRCS relative to the standalone BSP, WDT_SRCS relative to
    the watchdog driver."""
    import re
    text = BUILD.read_text()
    out = {}
    for name in ("ASM_SRCS", "C_SRCS", "SYS_SRCS", "WDT_SRCS"):
        m = re.search(name + r'="([^"]*)"', text, re.S)
        if not m:
            raise RuntimeError(f"build.sh: {name} not found")
        out[name] = m.group(1).replace("\\\n", " ").split()
    return out


def bsp_inputs() -> dict:
    """EVERY file the build reads, by hash (owner's review 2026-09-05: the earlier list was
    the headers the application units include; it omitted the BSP and watchdog C and
    assembly units build.sh compiles and the toolchain's runtime objects and libraries):
      * translation_units — every .c / .S build.sh compiles (BSP, syscalls, watchdog, the
        console glue, the application), the source file itself by hash;
      * headers — every embeddedsw header any of those units includes (gcc -M over each unit
        with the flags build.sh uses; the toolchain's own headers are covered by the pinned
        compiler);
      * toolchain_objects — crti/crtbegin/crtend/crtn and libgcc/libc/libm as the link
        resolves them (-print-file-name), by hash."""
    cc = TC / "bin/arm-none-eabi-gcc"
    arch = ["-mcpu=cortex-a9", "-mfpu=vfpv3", "-mfloat-abi=hard"]
    inc = [f"-I{FW / 'bsp/include'}", f"-I{SA}/common", f"-I{SA}/arm/common", f"-I{SA}/arm/common/gcc",
           f"-I{SA}/arm/cortexa9", f"-I{SA}/arm/cortexa9/gcc", f"-I{WD}"]
    srcs = build_script_sources()
    units: list[tuple[Path, list[str]]] = []
    bsp_flags = [*arch, "-std=gnu11", "-DUSE_AMP=0", *inc]
    app_flags = [*arch, "-std=c99", "-ffreestanding", *inc]
    for s in srcs["ASM_SRCS"] + srcs["C_SRCS"] + srcs["SYS_SRCS"]:
        units.append((SA / s, bsp_flags))
    for s in srcs["WDT_SRCS"]:
        units.append((WD / s, bsp_flags))
    units.append((FW / "bsp/src/console.c", bsp_flags))
    for s in ("b1_app.c", "p3_derive.c", "b1_carto.c", "b1_orch.c", "b1_wire.c", "p3_rectx.c", "p3_pull.c"):
        units.append((FW / s, app_flags))
    tus: dict[str, str] = {}
    headers: dict[str, str] = {}
    for src, flags in units:
        if not src.is_file():
            raise RuntimeError(f"build input missing: {src}")
        tus[str(src)] = sha(src)
        p = subprocess.run([str(cc), *flags, "-M", str(src)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{src}: {p.stderr[-1000:]}")
        for tok in p.stdout.replace("\\\n", " ").split()[1:]:
            path = Path(tok)
            if path.is_file() and path != src and (str(path).startswith(str(SA)) or str(path).startswith(str(WD)) or str(path).startswith(str(FW))):
                headers[str(path)] = sha(path)
    objs: dict[str, str] = {}
    for name in ("crti.o", "crtbegin.o", "crtend.o", "crtn.o", "libgcc.a", "libc.a", "libm.a"):
        p = subprocess.run([str(cc), *arch, f"-print-file-name={name}"], capture_output=True, text=True)
        path = Path(p.stdout.strip())
        objs[name] = {"path": str(path), "sha256": sha(path) if path.is_file() else None}
    return {"translation_units": dict(sorted(tus.items())), "headers": dict(sorted(headers.items())),
            "toolchain_objects": objs, "build_script_lists": srcs}


def build_evidence(do_build: bool) -> dict:
    hashes = []
    if do_build:
        hashes = [build_once(), build_once()]
    image = OUT / "b1_app.bin"
    elf = OUT / "b1_app.elf"
    ev = {"schema": "b1_build_evidence", "schema_version": "1.1.0",
          "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
          "git": {"head": git("rev-parse", "HEAD"), "worktree_dirty": bool(git("status", "--porcelain"))},
          "toolchain": {"path": str(TC), "gcc_sha256": sha(TC / "bin/arm-none-eabi-gcc") if (TC / "bin/arm-none-eabi-gcc").is_file() else None,
                        "version": subprocess.run([str(TC / "bin/arm-none-eabi-gcc"), "--version"], capture_output=True, text=True).stdout.splitlines()[0]
                        if (TC / "bin/arm-none-eabi-gcc").is_file() else None,
                        "instrument_role": "read-only use of the archived instrument's toolchain directory"},
          "sources": {s: sha(FW / s) for s in APP_SOURCES},
          "bsp_inputs": bsp_inputs() if (TC / "bin/arm-none-eabi-gcc").is_file() else {},
          "image": {"path": "firmware/b1/bsp/out/b1_app.bin", "sha256": sha(image) if image.is_file() else None,
                    "bytes": image.stat().st_size if image.is_file() else None,
                    "elf_sha256": sha(elf) if elf.is_file() else None, "load_address": "0x02000000", "entry": "go 0x2000000"},
          "reproducibility": {"builds": hashes, "reproduced_byte_identical": (len(hashes) == 2 and hashes[0] == hashes[1]) if do_build else None}}
    return ev


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/b1/build_evidence.json")
    a = ap.parse_args(argv)
    ev = build_evidence(a.build)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ev, indent=1) + "\n")
    print(f"image {ev['image']['sha256']} reproduced {ev['reproducibility']['reproduced_byte_identical']} -> {a.out}")
    return 0 if (not a.build or ev["reproducibility"]["reproduced_byte_identical"]) else 1


if __name__ == "__main__":
    sys.exit(main())
