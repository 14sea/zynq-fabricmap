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
APP_SOURCES = ("b1_app.c", "b1_carto.c", "b1_carto.h", "b1_wire.c", "b1_wire.h", "p3_data.h",
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


def bsp_inputs() -> dict:
    """Every embeddedsw file the application translation units read, from gcc -M."""
    cc = TC / "bin/arm-none-eabi-gcc"
    inc = [f"-I{FW / 'bsp/include'}", f"-I{SA}/common", f"-I{SA}/arm/common", f"-I{SA}/arm/common/gcc",
           f"-I{SA}/arm/cortexa9", f"-I{SA}/arm/cortexa9/gcc", f"-I{WD}"]
    files: dict[str, str] = {}
    for src in ("b1_app.c", "b1_wire.c", "b1_carto.c", "p3_derive.c", "p3_rectx.c", "p3_pull.c"):
        p = subprocess.run([str(cc), "-mcpu=cortex-a9", "-mfpu=vfpv3", "-mfloat-abi=hard", "-std=c99", "-M", *inc, str(FW / src)],
                           capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(p.stderr[-1000:])
        for tok in p.stdout.replace("\\\n", " ").split()[1:]:
            path = Path(tok)
            if path.is_file() and (str(path).startswith(str(SA)) or str(path).startswith(str(WD))):
                files[str(path)] = sha(path)
    return dict(sorted(files.items()))


def build_evidence(do_build: bool) -> dict:
    hashes = []
    if do_build:
        hashes = [build_once(), build_once()]
    image = OUT / "b1_app.bin"
    elf = OUT / "b1_app.elf"
    ev = {"schema": "b1_build_evidence", "schema_version": "1.0.0",
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
