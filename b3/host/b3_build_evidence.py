#!/usr/bin/env python3
"""B3 lifecycle 2 — build provenance for the B3 image (image stage 5, first unit; host-only; touches no board).

    b3_build_evidence.py [--build] [--out evidence/b3/build_evidence.json]

B2's discipline (host/b2_build_evidence.py, frozen and used read-only for the pinned toolchain's path, its
architecture flags and the resolution of the compiler and the runtime objects), re-aimed at B3:

  * with --build: TWO clean builds from scratch through b3/firmware/bsp/build.sh — the intermediate products
    (build/b3_bsp/) and the two outputs (b3/firmware/bsp/out/b3_app.bin and .elf) removed before each — whose binary
    AND ELF must be byte-identical, or the evidence says so and the exit is non-zero;
  * always: the sha256 of the image and the ELF; of every source the image links (this module's MANDATORY inventory,
    so the evidence's own lists cannot decide what is required — the build and linker scripts included); of every
    translation unit build.sh compiles (BSP assembly and C, syscalls, the watchdog driver, the console glue, the
    application); of every header any unit includes, from the compiler's own -M over each unit with the build's
    flags (embeddedsw's, this repository's AND the toolchain's own — the compiler's hash does not cover the headers
    beside it); of the compiler binary and of the seven runtime objects the link resolves; and the git state —
    the head and every path that differs from it.

The image bytes are COMMITTED (the owner's ruling of 2026-09-28): b3_app.bin and b3_app.elf at b3/firmware/bsp/out/.

`verify_findings` is a pure function of an evidence document and the files it names: it RE-RESOLVES the trusted
build description from the build configuration (the pinned toolchain, -print-file-name under the build's flags,
this module's inventory, build.sh's own unit lists and its own compile flags — printed by build.sh, B3_PRINT_FLAGS=1)
and RE-DISCOVERS every unit's dependencies with the compiler's -M under exactly those flags, comparing the evidence
unit by unit and header by header — never trusting the paths, the lists or the header table the evidence supplies
(the owner's HOLD on 171b638). `build_once` runs the production build.sh clean; B3_OUT_DIR / B3_IMG_DIR let the
hermetic test rebuild without touching the committed image.

THE STACK (the owner's rulings of 2026-10-04): the image stack assessment — the analysis of the final ELF by
b3/host/b3_image_stack.py — now lands. The evidence carries a COMPLETE `stack` block (every entry's bound against
its mode's stack, the indirect-target rules, the verified newlib bounded rule with its pinned digests). The verifier
RE-RUNS the analysis on the named ELF and requires the block to equal it and to be within budget (the main path at
or below 0x2000, each exception entry within its mode's stack); `readiness.image_ready` is true only then. A block
whose recorded bounds / findings / rules differ from a fresh analysis, that claims completion with a finding, or
that is over budget, is refused — and the analyser's conclusion is itself still subject to the owner's review.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b2_build_evidence as b2be  # noqa: E402  (frozen; read only: the toolchain, its flags, the resolution)

SCHEMA = "b3_build_evidence"
SCHEMA_VERSION = "1.1.0"
FW_REL = "b3/firmware"
FW = REPO_ROOT / FW_REL
BUILD = FW / "bsp/build.sh"
INTERMEDIATE = REPO_ROOT / "build/b3_bsp"
OUT = FW / "bsp/out"
IMAGE_REL = "b3/firmware/bsp/out/b3_app.bin"
ELF_REL = "b3/firmware/bsp/out/b3_app.elf"
EVIDENCE_REL = "evidence/b3/build_evidence.json"
TC = b2be.TC
SA = b2be.SA
WD = b2be.WD
ARCH_FLAGS = b2be.ARCH_FLAGS
RUNTIME_OBJECTS = b2be.RUNTIME_OBJECTS
CONSOLE_SRC = "bsp/src/console.c"
# the MANDATORY inventory, relative to b3/firmware: every file the image is built from
APP_SOURCES = ("b3_app.c", "b2_search.c", "b2_search.h", "b3_orch.c", "b3_orch.h", "b3_record.c", "b3_record.h",
               "b3_online_view.c", "b3_online_view.h", "b3_carto.c", "b3_carto.h", "b3_wire.c", "b3_wire.h",
               "p3_derive.c", "p3_derive.h", "p3_rectx.c", "p3_rectx.h", "p3_pull.c", "p3_pull.h", "p3_data.h",
               "b3_seed_data.h", "bsp/build.sh", "bsp/lscript.ld", "bsp/src/console.c", "bsp/include/bspconfig.h",
               "bsp/include/xmem_config.h", "bsp/include/xparameters.h")
STACK_INCOMPLETE = ("the image stack assessment has not been completed: it is the next unit of image stage 5 (the owner's "
                    "ruling of 2026-10-04) — no stack bound is claimed for this image, and it is not ready")


def sha(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def git(*args: str) -> str | None:
    p = subprocess.run(["git", "-C", str(REPO_ROOT), *args], capture_output=True, text=True)
    return p.stdout if p.returncode == 0 else None


def git_state() -> dict:
    """The head and every path that differs from it (tracked changes and untracked files), repo-relative."""
    head = (git("rev-parse", "HEAD") or "").strip() or None
    out = git("status", "--porcelain", "--untracked-files=all") or ""
    dirty = sorted({line[3:].split(" -> ")[-1] for line in out.splitlines() if len(line) > 3})
    return {"head": head, "dirty": dirty}


def trusted_compiler() -> Path:
    return b2be.trusted_compiler()


def resolved_runtime_objects() -> dict[str, dict]:
    return b2be.resolved_runtime_objects()


def build_script_sources(build: Path = BUILD) -> dict[str, list[str]]:
    """The translation units build.sh compiles, read from build.sh itself (one source of truth)."""
    text = Path(build).read_text()
    out = {}
    for name in ("ASM_SRCS", "C_SRCS", "SYS_SRCS", "WDT_SRCS"):
        m = re.search(name + r'="([^"]*)"', text, re.S)
        if not m:
            raise RuntimeError(f"build.sh: {name} not found")
        out[name] = m.group(1).replace("\\\n", " ").split()
    line = [x for x in text.splitlines() if x.strip().startswith("for s in b3_app.c")]
    if len(line) != 1:
        raise RuntimeError("build.sh: the application unit list not found exactly once")
    out["APP_SRCS"] = [t for t in line[0].split(" in ", 1)[1].split(";")[0].split() if t.endswith(".c")]
    out["CONSOLE_SRCS"] = [CONSOLE_SRC]
    return out


OUTPUT_ONLY = ("-fstack-usage", "-fcallgraph-info")      # options that only add output files: not part of what a unit reads


def build_flags(build: Path = BUILD) -> tuple[list[str], list[str]]:
    """The BSP and the application compile flags, from build.sh ITSELF (B3_PRINT_FLAGS=1 makes it print its expanded
    BSP_CFLAGS / APP_CFLAGS and exit before creating anything) — the one source of the flags, so the -M dependency
    discovery reads with exactly the flags the build compiles with (-O2 included: a header behind `#ifdef
    __OPTIMIZE__` is read). Only the output-only options are removed (the owner's HOLD on 171b638, P2-2)."""
    env = dict(os.environ, B3_PRINT_FLAGS="1")
    p = subprocess.run(["bash", str(build)], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(f"build.sh would not print its flags: {p.stderr[-500:]}")
    got = {}
    for line in p.stdout.splitlines():
        k, _, v = line.partition("=")
        if k in ("BSP_CFLAGS", "APP_CFLAGS"):
            got[k] = [t for t in shlex.split(v) if not t.startswith(OUTPUT_ONLY)]
    if sorted(got) != ["APP_CFLAGS", "BSP_CFLAGS"]:
        raise RuntimeError("build.sh printed no BSP_CFLAGS / APP_CFLAGS")
    return got["BSP_CFLAGS"], got["APP_CFLAGS"]


def units(lists: dict, fw: Path = FW) -> list[tuple[Path, str]]:
    out = []
    for s in lists["ASM_SRCS"] + lists["C_SRCS"] + lists["SYS_SRCS"]:
        out.append((SA / s, "bsp"))
    for s in lists["WDT_SRCS"]:
        out.append((WD / s, "bsp"))
    for s in lists["CONSOLE_SRCS"]:
        out.append((fw / s, "bsp"))
    for s in lists["APP_SRCS"]:
        out.append((fw / s, "app"))
    return out


def fresh_dependencies(root: Path = REPO_ROOT) -> dict[str, list[str]]:
    """Every unit's dependencies as the compiler reports them NOW, with the build's own flags, for the tree at `root`:
    what the verifier compares the evidence with (it never takes the evidence's word for them)."""
    fw = Path(root) / FW_REL
    lists = build_script_sources(fw / "bsp/build.sh")
    bsp_flags, app_flags = build_flags(fw / "bsp/build.sh")
    return {str(src): sorted(dependency_set(src, bsp_flags if kind == "bsp" else app_flags)) for src, kind in units(lists, fw)}


def dependency_set(unit: Path, flags: list[str]) -> set[str]:
    p = subprocess.run([str(trusted_compiler()), *flags, "-M", str(unit)], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(f"{unit}: {p.stderr[-1000:]}")
    return {str(Path(t)) for t in p.stdout.replace("\\\n", " ").split()[1:]
            if Path(t).is_file() and Path(t).resolve() != Path(unit).resolve()}


def bsp_inputs() -> dict:
    lists = build_script_sources()
    bsp_flags, app_flags = build_flags()
    tus, headers, deps = {}, {}, {}
    for src, kind in units(lists):
        if not src.is_file():
            raise RuntimeError(f"build input missing: {src}")
        tus[str(src)] = sha(src)
        here = dependency_set(src, bsp_flags if kind == "bsp" else app_flags)
        for h in here:
            headers[h] = sha(Path(h))
        deps[str(src)] = sorted(here)
    objs = {name: {"path": str(v["path"]), "sha256": v["sha256"]} for name, v in resolved_runtime_objects().items()}
    return {"translation_units": dict(sorted(tus.items())), "headers": dict(sorted(headers.items())),
            "dependencies": dict(sorted(deps.items())), "toolchain_objects": objs, "build_script_lists": lists,
            "dependency_flags": {"bsp": bsp_flags, "app": app_flags,
                                 "source": "bash b3/firmware/bsp/build.sh with B3_PRINT_FLAGS=1, the output-only options removed"},
            "header_roots": {"embeddedsw_standalone": str(SA), "embeddedsw_watchdog": str(WD), "firmware": str(FW),
                             "toolchain": str(TC)}}


def expected_units(lists: dict, fw: Path = FW) -> set[str]:
    """The COMPLETE set of translation units build.sh compiles, from ITS lists and the TRUSTED roots."""
    return {str(p) for p, _ in units(lists, fw)}


def build_once(out_dir: Path | None = None, img_dir: Path | None = None) -> dict[str, str]:
    """One CLEAN build through the production build.sh: the intermediate directory and both outputs removed first.
    `out_dir` / `img_dir` (B3_OUT_DIR / B3_IMG_DIR) redirect the products — the hermetic test's use, which leaves the
    committed image untouched; the defaults are the production locations. Returns both output digests.

    The directories chosen here are made absolute and ALWAYS handed to build.sh, overriding any B3_OUT_DIR /
    B3_IMG_DIR the caller's environment carries, so the clean, the build and the digests use one pair of directories
    (the owner's HOLD on 3405273: without an argument the inherited variables sent the build elsewhere while the
    defaults were cleaned and read). Absolute because build.sh builds from the repository root."""
    inter = (Path(out_dir) if out_dir else INTERMEDIATE).resolve()
    img = (Path(img_dir) if img_dir else OUT).resolve()
    if inter.exists():
        shutil.rmtree(inter)
    for name in ("b3_app.bin", "b3_app.elf"):
        (img / name).unlink(missing_ok=True)
    env = dict(os.environ)
    env.pop("B3_PRINT_FLAGS", None)
    env["B3_OUT_DIR"] = str(inter)
    env["B3_IMG_DIR"] = str(img)
    p = subprocess.run(["bash", str(BUILD)], capture_output=True, text=True, env=env)
    if p.returncode != 0:
        raise RuntimeError(p.stdout[-2000:] + p.stderr[-2000:])
    return {"bin_sha256": sha(img / "b3_app.bin"), "elf_sha256": sha(img / "b3_app.elf")}


def stack_block(root: Path = REPO_ROOT) -> dict:
    """The image stack assessment of the FINAL ELF, from b3/host/b3_image_stack.py: every entry's bound against its
    mode's stack, the indirect-target rules, the verified newlib bounded rule, and every unresolved finding. The
    block is COMPLETE only when the analyser reports `ok` (no finding) AND the main path is within its budget
    (MAIN_LIMIT = 0x2000) and every exception entry within its mode's stack; otherwise it names the findings and is
    not complete."""
    import b3_image_stack as isa
    r = isa.assess(root / ELF_REL)
    findings = list(r["findings"])
    for name, b in r["entries"].items():
        limit = isa.MAIN_LIMIT if name == "main" else b["capacity"]
        if b["bound"] is None:
            continue
        if limit is None or b["bound"] > limit:
            msg = f"{name}: bound {b['bound']} exceeds {limit}"
            if msg not in findings:
                findings.append(msg)
    complete = not findings
    return {"status": "COMPLETE" if complete else "FINDINGS", "complete": complete,
            "elf_sha256": r["elf"]["sha256"], "tool": r["tool"], "objdump": r["objdump"],
            "main_limit": isa.MAIN_LIMIT, "entries": r["entries"], "modes": r["modes"], "capacity": r["capacity"],
            "indirect_targets": r["indirect_targets"], "rules": r["rules"], "newlib": r["newlib"],
            "masks": r["masks"], "findings": findings,
            "note": "the stack pointer is tracked along every path of the final ELF; the main path is bounded at or "
                    "below 0x2000 and each exception entry within its mode's stack, with the newlib printf recursion "
                    "bounded by a verified source rule (b3/host/b3_image_stack.py)"}


def build_evidence(do_build: bool) -> dict:
    builds = [build_once(), build_once()] if do_build else []
    image, elf = REPO_ROOT / IMAGE_REL, REPO_ROOT / ELF_REL
    cc = trusted_compiler()
    elf_sha = sha(elf) if elf.is_file() else None
    stk = stack_block()
    ready = bool(stk["complete"]) and not stk["findings"]
    blocking = [] if ready else ([f"stack: {m}" for m in stk["findings"]] or ["stack: not complete"])
    bin_ok = len(builds) == 2 and builds[0]["bin_sha256"] == builds[1]["bin_sha256"]
    elf_ok = len(builds) == 2 and builds[0]["elf_sha256"] == builds[1]["elf_sha256"]
    return {"schema": SCHEMA, "schema_version": SCHEMA_VERSION,
            "at": time.strftime("%Y-%m-%dT%H%M%SZ", time.gmtime()),
            "git": git_state(),
            "toolchain": {"path": str(TC), "gcc_sha256": sha(cc) if cc.is_file() else None,
                          "version": subprocess.run([str(cc), "--version"], capture_output=True, text=True).stdout.splitlines()[0]
                          if cc.is_file() else None,
                          "instrument_role": "read-only use of the archived instrument's toolchain directory"},
            "sources": {s: sha(FW / s) for s in APP_SOURCES},
            "bsp_inputs": bsp_inputs(),
            "image": {"path": IMAGE_REL, "elf_path": ELF_REL, "sha256": sha(image) if image.is_file() else None,
                      "bytes": image.stat().st_size if image.is_file() else None, "elf_sha256": elf_sha,
                      "load_address": "0x02000000", "entry": "go 0x2000000"},
            "reproducibility": {"builds": builds, "bin_identical": bin_ok if do_build else None,
                                "elf_identical": elf_ok if do_build else None,
                                "reproduced_byte_identical": (bin_ok and elf_ok) if do_build else None,
                                "clean": "before each build: build/b3_bsp/ and both outputs removed",
                                "note": "each entry is one clean build's BOTH outputs; the claim is that the two builds agree "
                                        "in the binary AND in the ELF"},
            "stack": stk,
            "readiness": {"image_ready": ready, "blocking": blocking,
                          "note": "the image is ready only when the stack assessment is complete with no finding and "
                                  "within budget, and the provenance verifies; the analyser's conclusion is still "
                                  "subject to the owner's review"}}


def _same_file(a: Path, b: Path) -> bool:
    try:
        return Path(a).resolve() == Path(b).resolve()
    except OSError:
        return str(a) == str(b)


SECTIONS = ("git", "toolchain", "sources", "bsp_inputs", "image", "reproducibility", "stack", "readiness")
BSP_SECTIONS = ("translation_units", "headers", "dependencies", "toolchain_objects", "build_script_lists", "header_roots",
                "dependency_flags")
STACK_KEYS = ("status", "complete", "elf_sha256", "tool", "objdump", "main_limit", "entries", "modes",
              "capacity", "indirect_targets", "rules", "newlib", "masks", "findings", "note")


def verify_findings(ev: dict, root: Path = REPO_ROOT, require_outputs: bool = True) -> list[str]:
    """Every way the evidence can fail to describe the image, as named findings (empty = the PROVENANCE stands).
    A pure function of the evidence and the files it names; readiness is `readiness_findings`."""
    f: list[str] = []
    root = Path(root)
    fw = root / FW_REL

    def check(path: Path, want, what: str):
        if not path.is_file():
            f.append(f"{what}: {path} does not exist")
        elif want is None:
            f.append(f"{what}: {path} has no recorded hash")
        elif sha(path) != want:
            f.append(f"{what}: {path} does not hash to the record")

    if not isinstance(ev, dict) or ev.get("schema") != SCHEMA or ev.get("schema_version") != SCHEMA_VERSION:
        return [f"the evidence is not {SCHEMA} {SCHEMA_VERSION}"]
    for k in SECTIONS:
        if k not in ev:
            return [f"the evidence has no {k!r} section"]
    bi = ev["bsp_inputs"]
    for k in BSP_SECTIONS:
        if k not in bi:
            return [f"bsp_inputs has no {k!r}"]

    # the git state: every change under b3/firmware must be a recorded input, an output, or the import table
    allowed = {f"{FW_REL}/{s}" for s in ev["sources"]} | {IMAGE_REL, ELF_REL, f"{FW_REL}/IMPORT.json"}
    for path in ev["git"].get("dirty", []):
        if path.startswith(FW_REL + "/") and path not in allowed:
            f.append(f"git: {path} differs from the head under b3/firmware but is neither a recorded source nor an output")
    if not ev["git"].get("head"):
        f.append("git: no head recorded")

    # the sources: the MANDATORY set is this module's
    for rel, want in ev["sources"].items():
        check(fw / rel, want, f"source {rel}")
    for rel in APP_SOURCES:
        if rel not in ev["sources"]:
            f.append(f"source inventory: {rel} is a required build input but is not recorded")

    # the translation units: exactly what build.sh compiles (its lists read from the TRUSTED build.sh)
    try:
        lists = build_script_sources(fw / "bsp/build.sh")
    except (OSError, RuntimeError) as e:
        return f + [f"the build script cannot be read: {e}"]
    if bi["build_script_lists"] != lists:
        f.append("build_script_lists: the recorded lists are not build.sh's")
    want_units = expected_units(lists, fw)
    recorded = set(bi["translation_units"])
    for missing in sorted(want_units - recorded):
        f.append(f"translation units: {missing} is compiled by the build script but not recorded")
    for extra in sorted(recorded - want_units):
        f.append(f"translation units: {extra} is recorded but not compiled by the build script")
    for path, want in bi["translation_units"].items():
        check(Path(path), want, "translation unit")
    for rel in lists["APP_SRCS"] + lists["CONSOLE_SRCS"]:
        if rel not in ev["sources"]:
            f.append(f"source inventory: {rel} is linked by the build script but not recorded")

    # the flags the dependencies were discovered with: build.sh's own (the owner's HOLD on 171b638, P2-2)
    try:
        bsp_flags, app_flags = build_flags(fw / "bsp/build.sh")
        fresh = fresh_dependencies(root)
    except (OSError, RuntimeError) as e:
        return f + [f"the dependencies cannot be re-discovered from the build configuration: {e}"]
    df = bi["dependency_flags"]
    if not isinstance(df, dict) or df.get("bsp") != bsp_flags or df.get("app") != app_flags:
        f.append("dependency_flags: the recorded -M flags are not build.sh's compile flags")

    # the dependencies, unit by unit, RE-DISCOVERED by the compiler with those flags — never the evidence's own lists
    # (the owner's HOLD on 171b638, P2-1: a header deleted from both the table and every list must still be missed)
    for unit, deps in bi["dependencies"].items():
        if unit not in bi["translation_units"]:
            f.append(f"dependencies: {unit} is not a recorded translation unit")
    for unit, want in fresh.items():
        got = bi["dependencies"].get(unit)
        if got is None:
            f.append(f"dependencies: no dependency list for {unit}")
        elif sorted(got) != want:
            missing = sorted(set(want) - set(got))
            extra = sorted(set(got) - set(want))
            f.append(f"dependencies: {unit} is not the compiler's dependency set "
                     f"(missing {missing[:3]}{'…' if len(missing) > 3 else ''}, extra {extra[:3]}{'…' if len(extra) > 3 else ''})")
    union = set().union(*fresh.values()) if fresh else set()
    for missing in sorted(union - set(bi["headers"])):
        f.append(f"headers: {missing} is read by the build but has no hash")
    for extra in sorted(set(bi["headers"]) - union):
        f.append(f"headers: {extra} is recorded but the build reads no such header")
    for path, want in bi["headers"].items():
        check(Path(path), want, "header")

    # the compiler and the runtime objects: resolved from the build configuration, then compared
    cc = trusted_compiler()
    tc = ev["toolchain"]
    if not cc.is_file():
        f.append(f"the compiler: {cc} does not exist")
    else:
        if not _same_file(Path(tc.get("path", "")) / "bin/arm-none-eabi-gcc", cc):
            f.append(f"the compiler: the evidence names {tc.get('path')!r}, the build uses {cc.parent.parent}")
        if tc.get("gcc_sha256") != sha(cc):
            f.append("the compiler: the recorded hash is not the build compiler's")
    objs = bi["toolchain_objects"]
    resolved = resolved_runtime_objects()
    for name in RUNTIME_OBJECTS:
        if name not in objs:
            f.append(f"toolchain objects: {name} is not recorded")
            continue
        want = resolved[name]
        if want["sha256"] is None:
            f.append(f"runtime object {name}: the link does not resolve it")
            continue
        if not _same_file(Path(objs[name].get("path", "")), want["path"]):
            f.append(f"runtime object {name}: the evidence names {objs[name].get('path')}, the link resolves {want['path']}")
        if objs[name].get("sha256") != want["sha256"]:
            f.append(f"runtime object {name}: the recorded hash is not the resolved file's")

    # the two clean builds: both outputs, equal to each other and to the named image
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
            if b["bin_sha256"] != ev["image"].get("sha256"):
                f.append(f"reproducibility: build {i}'s binary is not the named image")
            if b["elf_sha256"] != ev["image"].get("elf_sha256"):
                f.append(f"reproducibility: build {i}'s ELF is not the named ELF")

    # the outputs: the canonical paths, present and matching
    im = ev["image"]
    if im.get("path") != IMAGE_REL or im.get("elf_path") != ELF_REL:
        f.append(f"the image: the evidence names {im.get('path')!r} / {im.get('elf_path')!r}, the B3 image is {IMAGE_REL} / {ELF_REL}")
    image, elf = root / IMAGE_REL, root / ELF_REL
    if require_outputs or image.is_file():
        check(image, im.get("sha256"), "the image")
        if image.is_file() and image.stat().st_size != im.get("bytes"):
            f.append("the image on disk is not the recorded size")
    if require_outputs or elf.is_file():
        check(elf, im.get("elf_sha256"), "the ELF")

    # the stack block: the verifier RE-RUNS the analysis on the named ELF and requires the block to match it, then
    # holds the result to the budget (main <= 0x2000, each exception entry within its mode's stack)
    st = ev["stack"]
    if not isinstance(st, dict) or sorted(st) != sorted(STACK_KEYS):
        f.append(f"stack: the block's keys are not exactly {list(STACK_KEYS)}")
    else:
        import b3_image_stack as isa
        fresh = stack_block(root)
        if st["elf_sha256"] != im.get("elf_sha256"):
            f.append("stack: the block is not about the named ELF")
        if st["elf_sha256"] != fresh["elf_sha256"]:
            f.append("stack: the block's ELF digest is not the built image's")
        norm = lambda x: json.loads(json.dumps(x, sort_keys=True))     # the recorded block is JSON; normalise fresh the same
        for key in ("entries", "findings", "newlib", "indirect_targets", "rules", "modes", "masks", "tool", "main_limit"):
            if norm(st.get(key)) != norm(fresh.get(key)):
                f.append(f"stack: the recorded {key} is not the analyser's fresh result")
        if st["complete"] != (not fresh["findings"]) or st["status"] != ("COMPLETE" if not fresh["findings"] else "FINDINGS"):
            f.append("stack: complete / status disagree with the findings")
        for name, b in (st.get("entries") or {}).items():
            limit = isa.MAIN_LIMIT if name == "main" else b.get("capacity")
            if b.get("bound") is not None and (limit is None or b["bound"] > limit):
                f.append(f"stack: {name} bound {b['bound']} exceeds its budget {limit}")
        if st["complete"] and st["findings"]:
            f.append("stack: a complete block must have no finding")
    rd = ev["readiness"]
    ready = isinstance(st, dict) and st.get("complete") is True and not st.get("findings") and not f
    if not isinstance(rd, dict) or rd.get("image_ready") is not ready:
        f.append(f"readiness: image_ready must be {ready} for this stack result and provenance")
    return f


def readiness_findings(ev: dict, root: Path = REPO_ROOT) -> list[str]:
    """Whether the image is READY: the provenance findings, plus every unresolved stack finding. Empty only when the
    provenance verifies AND the stack assessment is complete and within budget."""
    f = verify_findings(ev, root)
    st = ev.get("stack") if isinstance(ev, dict) else None
    if not isinstance(st, dict) or st.get("complete") is not True:
        f.append("stack: the image stack assessment is not complete")
    for m in (st or {}).get("findings", []) if isinstance(st, dict) else []:
        f.append(f"stack: {m}")
    return f


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--build", action="store_true")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / EVIDENCE_REL)
    a = ap.parse_args(argv)
    ev = build_evidence(a.build)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(ev, indent=1, sort_keys=True) + "\n")
    print(f"image {ev['image']['sha256']} reproduced {ev['reproducibility']['reproduced_byte_identical']} "
          f"stack {ev['stack']['status']} image_ready {ev['readiness']['image_ready']} -> {a.out}")
    return 0 if (not a.build or ev["reproducibility"]["reproduced_byte_identical"]) else 1


if __name__ == "__main__":
    sys.exit(main())
