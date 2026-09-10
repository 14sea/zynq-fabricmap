#!/usr/bin/env python3
"""B2 — build provenance for the image (host-only; touches no board).

    b2_build_evidence.py [--build] [--out evidence/b2/build_evidence.json]

With `--build`: two clean builds from scratch (`rm -rf firmware/b2/bsp/out` between them)
through `firmware/b2/bsp/build.sh`; the two binaries must be byte-identical or the evidence
says `reproduced_byte_identical: false` and the exit is non-zero. Always: the sha256 of the
image and the ELF, of every source the image links (this repository's b2_* files and the
verbatim instrument imports), of the generated data header, of the toolchain's compiler
binary, and — from the compiler's own `-M` dependency output over b2_app.c — every
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
FW = REPO_ROOT / "firmware/b2"
OUT = FW / "bsp/out"
BUILD = FW / "bsp/build.sh"
INSTRUMENT = Path(os.environ.get("PSORACLE_ROOT", "/home/test/zynq_psoracle"))
TC = INSTRUMENT / "toolchain/xpack-arm-none-eabi-gcc-14.2.1-1.1"
SA = Path("/home/test/Xilinx/2025.2/data/embeddedsw/lib/bsp/standalone_v9_4/src")
WD = Path("/home/test/Xilinx/2025.2/data/embeddedsw/XilinxProcessorIPLib/drivers/scuwdt_v2_6/src")
APP_SOURCES = ("b2_app.c", "b2_search.c", "b2_search.h", "b2_orch.c", "b2_orch.h", "b2_wire.c", "b2_wire.h", "p3_data.h",
               "p3_derive.c", "p3_derive.h", "p3_rectx.c", "p3_rectx.h", "p3_pull.c", "p3_pull.h",
               "bsp/build.sh", "bsp/lscript.ld", "bsp/src/console.c",
               "bsp/include/bspconfig.h", "bsp/include/xmem_config.h", "bsp/include/xparameters.h")


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def git(*args: str) -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    return p.stdout.strip() if p.returncode == 0 else None


def build_once() -> dict[str, str]:
    """One clean build; returns BOTH output digests. The owner's integration review of
    2026-09-10 noted that recording only the binary made the two-ELF equality claim
    unsupported, so both are recorded and both are compared."""
    if OUT.exists():
        shutil.rmtree(OUT)
    p = subprocess.run(["bash", str(BUILD)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
    return {"bin_sha256": sha(OUT / "b2_app.bin"), "elf_sha256": sha(OUT / "b2_app.elf")}


APP_SRCS = ("b2_app.c", "p3_derive.c", "b2_search.c", "b2_orch.c", "b2_wire.c", "p3_rectx.c", "p3_pull.c")
CONSOLE_SRC = "bsp/src/console.c"
RUNTIME_OBJECTS = ("crti.o", "crtbegin.o", "crtend.o", "crtn.o", "libgcc.a", "libc.a", "libm.a")


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
    # the two the script compiles outside those lists, so the recorded inventory is COMPLETE
    # (the owner's correction review of 2026-09-10: console was omitted from the expected set)
    line = [l for l in text.splitlines() if l.strip().startswith("for s in b2_app.c")]
    if not line:
        raise RuntimeError("build.sh: the application unit list not found")
    out["APP_SRCS"] = [t for t in line[0].split(" in ", 1)[1].split(";")[0].split() if t.endswith(".c")]
    out["CONSOLE_SRCS"] = [CONSOLE_SRC]
    return out


def bsp_inputs() -> dict:
    """EVERY file the build reads, by hash (owner's review 2026-09-05: the earlier list was
    the headers the application units include; it omitted the BSP and watchdog C and
    assembly units build.sh compiles and the toolchain's runtime objects and libraries):
      * translation_units — every .c / .S build.sh compiles (BSP, syscalls, watchdog, the
        console glue, the application), the source file itself by hash;
      * headers — EVERY header any of those units includes (gcc -M over each unit with the
        flags build.sh uses): the embeddedsw ones, this repository's, AND the toolchain's own
        (newlib's stdint.h / stdio.h / string.h …, gcc's stddef.h …) — the compiler
        executable's hash does not cover the headers beside it (owner's review 2026-09-05);
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
    for s in srcs["APP_SRCS"]:
        units.append((FW / s, app_flags))
    tus: dict[str, str] = {}
    headers: dict[str, str] = {}
    deps: dict[str, list[str]] = {}
    for src, flags in units:
        if not src.is_file():
            raise RuntimeError(f"build input missing: {src}")
        tus[str(src)] = sha(src)
        p = subprocess.run([str(cc), *flags, "-M", str(src)], capture_output=True, text=True)
        if p.returncode != 0:
            raise RuntimeError(f"{src}: {p.stderr[-1000:]}")
        here = []
        for tok in p.stdout.replace("\\\n", " ").split()[1:]:
            path = Path(tok)
            if path.is_file() and path.resolve() != src.resolve():
                headers[str(path)] = sha(path)          # every dependency gcc names, wherever it lives
                here.append(str(path))
        deps[str(src)] = sorted(set(here))
    objs: dict[str, str] = {}
    for name in RUNTIME_OBJECTS:
        p = subprocess.run([str(cc), *arch, f"-print-file-name={name}"], capture_output=True, text=True)
        path = Path(p.stdout.strip())
        objs[name] = {"path": str(path), "sha256": sha(path) if path.is_file() else None}
    return {"translation_units": dict(sorted(tus.items())), "headers": dict(sorted(headers.items())),
            "dependencies": dict(sorted(deps.items())),
            "toolchain_objects": objs, "build_script_lists": srcs,
            "header_roots": {"embeddedsw_standalone": str(SA), "embeddedsw_watchdog": str(WD), "firmware": str(FW), "toolchain": str(TC)}}


def expected_units(lists: dict, roots: dict) -> set[str]:
    """The COMPLETE set of translation units the build script compiles, derived from the
    recorded lists and roots: the standalone BSP's assembly, C and syscall units, the
    watchdog driver's, the console glue and the application's. The owner's correction review
    of 2026-09-10 found the earlier expected set omitted the console."""
    sa, wd, fw = Path(roots["embeddedsw_standalone"]), Path(roots["embeddedsw_watchdog"]), Path(roots["firmware"])
    out = {str(sa / x) for x in lists["ASM_SRCS"] + lists["C_SRCS"] + lists["SYS_SRCS"]}
    out |= {str(wd / x) for x in lists["WDT_SRCS"]}
    out |= {str(fw / x) for x in lists.get("CONSOLE_SRCS", [CONSOLE_SRC])}
    out |= {str(fw / x) for x in lists.get("APP_SRCS", APP_SRCS)}
    return out


def verify_findings(ev: dict, root: Path = REPO_ROOT, require_outputs: bool = True) -> list[str]:
    """Every way the recorded provenance can fail to describe the image, as a list of named
    findings (empty = the evidence stands). A PURE function of the evidence and the files it
    names, so `tests/test_b2_build_evidence.py` can drive it with deliberately corrupted
    copies — the owner's correction review of 2026-09-10 showed a guard that reads the real
    file cannot demonstrate that it would refuse anything."""
    f: list[str] = []
    fw = root / "firmware/b2"

    def check(path: Path, want, what: str):
        if not path.is_file():
            f.append(f"{what}: {path} does not exist")
        elif want is None:
            f.append(f"{what}: {path} has no recorded hash")
        elif sha(path) != want:
            f.append(f"{what}: {path} does not hash to the record")

    for k in ("sources", "bsp_inputs", "image", "reproducibility", "git", "toolchain"):
        if k not in ev:
            return [f"the evidence has no {k!r} section"]
    bi = ev["bsp_inputs"]
    for k in ("translation_units", "headers", "dependencies", "toolchain_objects", "build_script_lists", "header_roots"):
        if k not in bi:
            return [f"bsp_inputs has no {k!r}"]

    if ev["git"].get("worktree_dirty"):
        f.append("the evidence was taken from a dirty tree")

    # the sources, and the completeness of that list against what the script links
    for rel, want in ev["sources"].items():
        check(fw / rel, want, f"source {rel}")
    lists = bi["build_script_lists"]
    for rel in list(lists.get("APP_SRCS", APP_SRCS)) + list(lists.get("CONSOLE_SRCS", [CONSOLE_SRC])):
        if rel not in ev["sources"]:
            f.append(f"source inventory: {rel} is linked by the build script but not recorded")

    # the translation units: exactly the expected set, each existing and hashing
    recorded = set(bi["translation_units"])
    want_units = expected_units(lists, bi["header_roots"])
    for missing in sorted(want_units - recorded):
        f.append(f"translation units: {missing} is compiled by the build script but not recorded")
    for extra in sorted(recorded - want_units):
        f.append(f"translation units: {extra} is recorded but not compiled by the build script")
    for path, want in bi["translation_units"].items():
        check(Path(path), want, "translation unit")

    # the headers: exactly the union of the recorded dependencies, each existing and hashing
    dep_union: set[str] = set()
    for unit, deps in bi["dependencies"].items():
        if unit not in bi["translation_units"]:
            f.append(f"dependencies: {unit} is not a recorded translation unit")
        dep_union |= set(deps)
    for missing in sorted(dep_union - set(bi["headers"])):
        f.append(f"headers: {missing} is a recorded dependency but has no hash")
    for extra in sorted(set(bi["headers"]) - dep_union):
        f.append(f"headers: {extra} is recorded but is no unit's dependency")
    for unit in bi["translation_units"]:
        if unit not in bi["dependencies"]:
            f.append(f"dependencies: no dependency list for {unit}")
    for path, want in bi["headers"].items():
        check(Path(path), want, "header")

    # the compiler and every runtime object the link resolves
    tc = ev["toolchain"]
    check(Path(tc["path"]) / "bin/arm-none-eabi-gcc", tc.get("gcc_sha256"), "the compiler")
    objs = bi["toolchain_objects"]
    for name in RUNTIME_OBJECTS:
        if name not in objs:
            f.append(f"toolchain objects: {name} is not recorded")
            continue
        check(Path(objs[name]["path"]), objs[name].get("sha256"), f"runtime object {name}")

    # the two clean builds: both outputs each, equal to each other AND to the named image
    rep = ev["reproducibility"]
    builds = rep.get("builds") or []
    if len(builds) != 2 or not all(isinstance(b, dict) and "bin_sha256" in b and "elf_sha256" in b for b in builds):
        f.append("reproducibility: two builds, each with both output digests, are required")
    else:
        bin_ok = builds[0]["bin_sha256"] == builds[1]["bin_sha256"]
        elf_ok = builds[0]["elf_sha256"] == builds[1]["elf_sha256"]
        if not bin_ok:
            f.append("reproducibility: the two builds' binaries differ")
        if not elf_ok:
            f.append("reproducibility: the two builds' ELFs differ")
        if rep.get("bin_identical") is not bin_ok or rep.get("elf_identical") is not elf_ok \
                or rep.get("reproduced_byte_identical") is not (bin_ok and elf_ok):
            f.append("reproducibility: the recorded verdicts disagree with the recorded digests")
        for i, b in enumerate(builds):
            if b["bin_sha256"] != ev["image"]["sha256"]:
                f.append(f"reproducibility: build {i}'s binary is not the named image")
            if b["elf_sha256"] != ev["image"]["elf_sha256"]:
                f.append(f"reproducibility: build {i}'s ELF is not the named ELF")

    # the outputs themselves: a completed package requires them, and requires them to match
    image, elf = root / ev["image"]["path"], root / ev["image"]["path"].replace(".bin", ".elf")
    if require_outputs or image.is_file():
        check(image, ev["image"]["sha256"], "the image")
        if image.is_file() and image.stat().st_size != ev["image"]["bytes"]:
            f.append("the image on disk is not the recorded size")
    if require_outputs or elf.is_file():
        check(elf, ev["image"].get("elf_sha256"), "the ELF")
    return f


def dependency_set(unit: Path, flags: list[str]) -> set[str]:
    """Every file gcc -M names for one unit (the completeness test compares this with the
    evidence's header set)."""
    cc = TC / "bin/arm-none-eabi-gcc"
    p = subprocess.run([str(cc), *flags, "-M", str(unit)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr[-1000:])
    return {str(Path(t)) for t in p.stdout.replace("\\\n", " ").split()[1:] if Path(t).is_file() and Path(t).resolve() != unit.resolve()}


def build_evidence(do_build: bool) -> dict:
    hashes = []
    if do_build:
        hashes = [build_once(), build_once()]
    image = OUT / "b2_app.bin"
    elf = OUT / "b2_app.elf"
    ev = {"schema": "b2_build_evidence", "schema_version": "1.2.0",
          "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
          "git": {"head": git("rev-parse", "HEAD"), "worktree_dirty": bool(git("status", "--porcelain"))},
          "toolchain": {"path": str(TC), "gcc_sha256": sha(TC / "bin/arm-none-eabi-gcc") if (TC / "bin/arm-none-eabi-gcc").is_file() else None,
                        "version": subprocess.run([str(TC / "bin/arm-none-eabi-gcc"), "--version"], capture_output=True, text=True).stdout.splitlines()[0]
                        if (TC / "bin/arm-none-eabi-gcc").is_file() else None,
                        "instrument_role": "read-only use of the archived instrument's toolchain directory"},
          "sources": {s: sha(FW / s) for s in APP_SOURCES},
          "bsp_inputs": bsp_inputs() if (TC / "bin/arm-none-eabi-gcc").is_file() else {},
          "image": {"path": "firmware/b2/bsp/out/b2_app.bin", "sha256": sha(image) if image.is_file() else None,
                    "bytes": image.stat().st_size if image.is_file() else None,
                    "elf_sha256": sha(elf) if elf.is_file() else None, "load_address": "0x02000000", "entry": "go 0x2000000"},
          "reproducibility": {"builds": hashes,
                              "reproduced_byte_identical": (len(hashes) == 2 and hashes[0] == hashes[1]) if do_build else None,
                              "bin_identical": (len(hashes) == 2 and hashes[0]["bin_sha256"] == hashes[1]["bin_sha256"]) if do_build else None,
                              "elf_identical": (len(hashes) == 2 and hashes[0]["elf_sha256"] == hashes[1]["elf_sha256"]) if do_build else None,
                              "note": "each entry is one clean build's BOTH outputs; the claim is that the two builds "
                                      "agree in the binary AND in the ELF"}}
    return ev


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "evidence/b2/build_evidence.json")
    a = ap.parse_args(argv)
    ev = build_evidence(a.build)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ev, indent=1) + "\n")
    print(f"image {ev['image']['sha256']} reproduced {ev['reproducibility']['reproduced_byte_identical']} -> {a.out}")
    return 0 if (not a.build or ev["reproducibility"]["reproduced_byte_identical"]) else 1


if __name__ == "__main__":
    sys.exit(main())
