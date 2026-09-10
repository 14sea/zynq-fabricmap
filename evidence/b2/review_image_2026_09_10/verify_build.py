#!/usr/bin/env python3
"""Rehash the submitted B2 image and all build inputs; rerun dependency discovery only."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

R = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(R / "host"))
import b2_build_evidence as be
import b1_pins

def sha(p):
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()

ev = json.loads((R / "evidence/b2/build_evidence.json").read_text())
fresh = be.bsp_inputs()
findings = []
for section in fresh:
    if fresh[section] != ev["bsp_inputs"][section]:
        for name in fresh[section].keys() | ev["bsp_inputs"][section].keys():
            before = ev["bsp_inputs"][section].get(name)
            after = fresh[section].get(name)
            if before != after:
                findings.append({"section": section, "path": name, "recorded": before, "current": after})
for name, digest in ev["sources"].items():
    current = sha(be.FW / name)
    if current != digest:
        findings.append({"section": "sources", "path": name, "recorded": digest, "current": current})
assert sha(be.TC / "bin/arm-none-eabi-gcc") == ev["toolchain"]["gcc_sha256"]
binary = R / ev["image"]["path"]
assert sha(binary) == ev["image"]["sha256"]
assert binary.stat().st_size == ev["image"]["bytes"]
assert sha(binary.with_suffix(".elf")) == ev["image"]["elf_sha256"]

# Derive application units independently from the actual compile loop, not APP_SOURCES.
build = be.BUILD.read_text()
app_units = re.search(r"for s in (b2_app\.c[^;]+); do", build).group(1).split()
expected = {str(be.FW / s) for s in app_units} | {str(be.FW / "bsp/src/console.c")}
for key, names in be.build_script_sources().items():
    root = be.WD if key == "WDT_SRCS" else be.SA
    expected.update(str(root / s) for s in names)
assert set(fresh["translation_units"]) == expected

inc = [f"-I{be.FW / 'bsp/include'}", f"-I{be.SA}/common", f"-I{be.SA}/arm/common",
       f"-I{be.SA}/arm/common/gcc", f"-I{be.SA}/arm/cortexa9", f"-I{be.SA}/arm/cortexa9/gcc", f"-I{be.WD}"]
arch = ["-mcpu=cortex-a9", "-mfpu=vfpv3", "-mfloat-abi=hard", "-O2", "-g",
        "-ffunction-sections", "-fdata-sections", *inc]
for unit in expected:
    flags = (["-std=c99", "-Wall", "-Wextra", "-ffreestanding"]
             if Path(unit).parent == be.FW else ["-std=gnu11", "-DUSE_AMP=0"])
    deps = be.dependency_set(Path(unit), arch + flags)
    assert deps <= set(fresh["headers"]), sorted(deps - set(fresh["headers"]))

imports = json.loads((be.FW / "IMPORT.json").read_text())
for path, entry in imports["files"].items():
    if entry["kind"] != "verbatim":
        continue
    if path.startswith("firmware/b1/"):
        original = (R / path).read_bytes()
    else:
        original = subprocess.check_output(["git", "-C", str(be.INSTRUMENT), "show", f"{imports['source_commit']}:{path}"])
    assert (R / entry["copied_to"]).read_bytes() == original
    assert hashlib.sha256(original).hexdigest() == entry["sha256"]

b1_pins.verify()
header_counts = {key: sum(str(Path(h).resolve()).startswith(str(Path(root).resolve()) + "/")
                           for h in fresh["headers"]) for key, root in fresh["header_roots"].items()}
print(json.dumps({"reviewed_head": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
                  "image": ev["image"], "source_entries": len(ev["sources"]),
                  "translation_units": len(expected), "headers": len(fresh["headers"]),
                  "headers_by_root": header_counts, "runtime_objects": len(fresh["toolchain_objects"]),
                  "source_hash_findings": findings,
                  "compiler_dependency_sets_covered": True,
                  "binary_contains_old_refusal": b"REFUSED_BY_GATE: an unscored candidate ends the B1 epoch" in binary.read_bytes(),
                  "binary_contains_current_refusal": b"REFUSED_BY_GATE: an unscored candidate ends the epoch" in binary.read_bytes(),
                  "verbatim_imports": 10, "b1_pins_verify": True,
                  "b1_manifest_sha256": sha(R / "manifests/b1_manifest.json"),
                  "submitted_reproducibility": ev["reproducibility"],
                  "review_built_arm_image": False}, indent=2))
