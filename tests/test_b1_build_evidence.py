"""host/b1_build_evidence.py — the build's INPUT set is complete: every translation unit
build.sh compiles is recorded by hash, every dependency gcc -M names for every unit
(embeddedsw, this repository's, and the toolchain's own headers) is in the evidence with
the hash the file has now, and the toolchain's runtime objects and libraries are named.
The owner's review of 2026-09-05 found 23 newlib / gcc headers of b1_app.c missing; this
test recomputes the dependency set per unit and requires it to be covered."""
from __future__ import annotations

import hashlib
import json
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b1_build_evidence as be  # noqa: E402

EV = R / "evidence/b1/build_evidence.json"
HAVE_TC = (be.TC / "bin/arm-none-eabi-gcc").is_file() and be.SA.is_dir() and be.WD.is_dir()


@unittest.skipUnless(HAVE_TC and EV.is_file(), "toolchain, embeddedsw or the build evidence absent")
class Completeness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ev = json.loads(EV.read_text())
        cls.b = cls.ev["bsp_inputs"]

    def test_schema_and_unit_lists_come_from_build_sh(self):
        self.assertEqual(self.ev["schema_version"], "1.2.0")
        self.assertEqual(self.b["build_script_lists"], be.build_script_sources())
        for s in ("b1_orch.c", "b1_orch.h"):
            self.assertIn(s, self.ev["sources"])
        tus = self.b["translation_units"]
        for s in self.b["build_script_lists"]["ASM_SRCS"] + self.b["build_script_lists"]["C_SRCS"] + self.b["build_script_lists"]["SYS_SRCS"]:
            self.assertIn(str(be.SA / s), tus)
        for s in self.b["build_script_lists"]["WDT_SRCS"]:
            self.assertIn(str(be.WD / s), tus)
        for s in ("b1_app.c", "b1_orch.c", "b1_carto.c", "b1_wire.c", "p3_derive.c", "p3_rectx.c", "p3_pull.c", "bsp/src/console.c"):
            self.assertIn(str(be.FW / s), tus)
        for name in ("crti.o", "crtbegin.o", "crtend.o", "crtn.o", "libgcc.a", "libc.a", "libm.a"):
            self.assertTrue(self.b["toolchain_objects"][name]["sha256"], name)

    def test_every_dependency_of_every_unit_is_recorded_with_its_current_hash(self):
        arch = ["-mcpu=cortex-a9", "-mfpu=vfpv3", "-mfloat-abi=hard"]
        inc = [f"-I{be.FW / 'bsp/include'}", f"-I{be.SA}/common", f"-I{be.SA}/arm/common", f"-I{be.SA}/arm/common/gcc",
               f"-I{be.SA}/arm/cortexa9", f"-I{be.SA}/arm/cortexa9/gcc", f"-I{be.WD}"]
        bsp_flags = [*arch, "-std=gnu11", "-DUSE_AMP=0", *inc]
        app_flags = [*arch, "-std=c99", "-ffreestanding", *inc]
        headers = self.b["headers"]
        toolchain_seen = 0
        for unit_s, sha in self.b["translation_units"].items():
            unit = Path(unit_s)
            self.assertEqual(hashlib.sha256(unit.read_bytes()).hexdigest(), sha, unit_s)
            flags = app_flags if unit.parent == be.FW else bsp_flags
            deps = be.dependency_set(unit, flags)
            missing = sorted(d for d in deps if d not in headers)
            self.assertEqual(missing, [], f"{unit.name}: dependencies not in the evidence")
            for d in deps:
                self.assertEqual(hashlib.sha256(Path(d).read_bytes()).hexdigest(), headers[d], d)
                if d.startswith(str(be.TC)):
                    toolchain_seen += 1
        self.assertGreater(toolchain_seen, 0, "no toolchain header in any unit's dependencies")
        # the owner's example: b1_app.c's newlib / gcc headers
        for name in ("stdint.h", "stdio.h", "string.h"):
            self.assertTrue(any(h.endswith("/" + name) and h.startswith(str(be.TC)) for h in headers), name)

    def test_the_evidence_hashes_to_the_manifests_pin(self):
        m = json.loads((R / "manifests/b1_manifest.json").read_text())
        self.assertEqual(hashlib.sha256(EV.read_bytes()).hexdigest(), m["image"]["build_evidence"]["sha256"])
        self.assertEqual(self.ev["image"]["sha256"], m["image"]["sha256"])


if __name__ == "__main__":
    unittest.main()
