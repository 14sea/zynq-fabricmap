"""b3/firmware/b3_carto.c against b3/host/b3_carto.py — the C cartographer equals the Python reference
specimen by specimen (B3 lifecycle 2, image stage 1; the discipline of tests/test_b2_twin.py).

The twin (`build/b3_firmware/b3_carto_twin`, built by `make -C b3/firmware twin` under the strictest host
warnings with -Werror) is compiled from the SAME b3_carto.c the image will link. It is driven over a pipe:
for every specimen the harness sends the moved addresses and the toggled positions to the twin AND to the
Python cartographer, and after EVERY step the twin's newly-decoded list (in order) and its commitment text
must equal the Python's byte for byte — the version, the anomaly count, every decoded address and every
candidate set are in that text. Held here: the ported boundary corpus (direct decode, narrowing by
intersection, the global closure, validate-then-commit, every malformed specimen, a closure conflict, a
repeated specimen, a duplicate decode, a position claimed twice, the version bumping only on a decode); the
pipe protocol refusing what it cannot parse without touching the state; two seeded specimen streams; and
the committed lifecycle-2 prediction's 8 000 O-arm ledger entries replayed through the twin, entry for
entry (`decoded` in the recorded order, `map_version`, `map_version_after`, `anomalies`, the final decoded
count and map version), with the Python cartographer walked beside it.

No skip: a missing host compiler or a failed build is a FAILURE. Nothing here builds an image, writes
build evidence, touches the tree under b3/ (build products go to the top-level build/) or a board.
"""
from __future__ import annotations

import json
import os
import random
import re
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b1_model as bm  # noqa: E402
import b2_landscape as bl  # noqa: E402
import b3_carto as b3  # noqa: E402
import b3_manifest as bman  # noqa: E402

import b2_build_evidence as be  # noqa: E402  (the pinned ARM toolchain's path and arch flags; a frozen B2 module, imported by content)

FW = R / "b3/firmware"
BUILD = R / "build/b3_firmware"
TWIN = BUILD / "b3_carto_twin"
REQUIRED_SOURCES = ("Makefile", "b3_carto.c", "b3_carto.h", "b3_carto_twin.c")
PRODUCT_SUFFIXES = (".o", ".su", ".d", ".map", ".a", ".bin", ".elf")
COMMITTED_IMAGE = ("bsp/out/b3_app.bin", "bsp/out/b3_app.elf")     # the owner's ruling (b): these two exact paths, and no other binary
FRAME_LIMIT = 1024                                    # bytes per function frame, host and ARM


def firmware_findings(fw: Path) -> list:
    """The rule for b3/firmware: the stage-1 sources are required; a build product anywhere under it (an object,
    a stack-usage file, a dependency file, a linker map, an archive, ANY .bin or .elf, the twin executable, a
    build/ directory) is refused on its own — with exactly two exceptions, the committed image at
    bsp/out/b3_app.bin and bsp/out/b3_app.elf (the owner's ruling of 2026-09-28), by exact path; anything else
    — a later stage's sources, the BSP inputs — is allowed."""
    f = []
    for name in REQUIRED_SOURCES:
        if not (fw / name).is_file():
            f.append(f"{name}: required, absent")
    for p in sorted(fw.rglob("*")):
        rel = p.relative_to(fw).as_posix()
        if p.is_dir() and p.name == "build":
            f.append(f"{rel}/: a build directory under b3/firmware")
        elif p.is_file() and rel in COMMITTED_IMAGE:
            continue
        elif p.is_file() and (p.suffix in PRODUCT_SUFFIXES or p.name == "b3_carto_twin"):
            f.append(f"{rel}: a build product under b3/firmware")
    return f
TRUTH = bm.truth_mapping()
P, Q, RR, T, U = (0, 0), (0, 1), (0, 2), (0, 3), (0, 4)
_BUILT = {"log": None}


def build_twin() -> str:
    """`make -s twin` once per process; the compiler must exist and the build must be silent (no warning
    survives -Werror, and none may be printed either)."""
    if _BUILT["log"] is None:
        cc = os.environ.get("CC", "cc")
        if shutil.which(cc) is None:
            raise AssertionError(f"no host C compiler ({cc}): the twin cannot be built — this is a failure, never a skip")
        p = subprocess.run(["make", "-s", "-C", str(FW), "twin"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the twin did not build:\n{p.stdout}{p.stderr}")
        _BUILT["log"] = p.stdout + p.stderr
    return _BUILT["log"]


class Twin:
    """One cartographer process, driven line by line."""

    def __init__(self):
        build_twin()
        self.p = subprocess.Popen([str(TWIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def close(self):
        """Quit the twin, close both ends of the pipe, and hold it to exit status 0 (the owner's P2 on
        4817662: an unclosed pipe is a ResourceWarning and an unchecked exit hides a crash)."""
        try:
            self.p.stdin.write("Q\n")
            self.p.stdin.flush()
        except (BrokenPipeError, ValueError):
            pass
        try:
            self.p.stdin.close()
            rest = self.p.stdout.read()
            self.p.stdout.close()
        finally:
            rc = self.p.wait(timeout=10)
        if rc != 0:
            raise AssertionError(f"the twin exited {rc}: {rest[-300:]!r}")

    def _line(self) -> str:
        line = self.p.stdout.readline()
        if not line:
            raise AssertionError("the twin closed its output")
        return line.rstrip("\n")

    def send(self, text: str) -> str:
        self.p.stdin.write(text + "\n")
        self.p.stdin.flush()
        return self._line()

    def state(self) -> str:
        line = self.send("S")
        assert line.startswith("STATE "), line
        return line[6:]

    def reset(self) -> str:
        line = self.send("R")
        assert line.startswith("STATE "), line
        return line[6:]

    @staticmethod
    def observe_line(moved, delta) -> str:
        return f"O {len(moved)} " + " ".join(str(i) for i in moved) + f" | {len(delta)} " + " ".join(f"{k}.{v}" for k, v in delta)

    def observe(self, moved, delta):
        """(newly as [(i, k, v)…] in the twin's order, or None on ANOMALY; the state text after)."""
        first = self.send(self.observe_line(moved, delta))
        if first == "ANOMALY":
            newly = None
        elif first.startswith("NEWLY "):
            parts = first.split()
            n = int(parts[1])
            newly = [tuple(int(x) for x in t.split(":")) for t in parts[2:]]
            assert len(newly) == n, first
        else:
            raise AssertionError(f"unexpected reply {first!r}")
        state = self._line()
        assert state.startswith("STATE "), state
        return newly, state[6:]

    def raw(self, text: str) -> str:
        return self.send(text)


class Lockstep(unittest.TestCase):
    """A twin and a Python cartographer driven together; every step compared."""

    def setUp(self):
        self.twin = Twin()
        self.addCleanup(self.twin.close)
        self.ref = b3.SpecimenCarto()
        self.assertEqual(self.twin.state(), self.ref.state_text())

    def step(self, moved, delta, where=""):
        """Both observe; the twin's newly list must be the Python's, in order, with the Python's positions;
        the commitment text must be byte-identical."""
        newly_ref = self.ref.observe(list(moved), [tuple(p) for p in delta])
        newly_twin, text = self.twin.observe(moved, delta)
        want = None if (newly_ref == [] and self.ref_refused) else [(i, *self.ref.decoded[i]) for i in newly_ref]
        self.assertEqual(newly_twin, want, where)
        self.assertEqual(text, self.ref.state_text(), where)
        return newly_twin

    @property
    def ref_refused(self) -> bool:
        return self._last_anomalies != self.ref.anomalies

    def observe(self, moved, delta, where=""):
        self._last_anomalies = self.ref.anomalies
        return self.step(moved, delta, where)


# ------------------------------------------------------------------ the build


class TheBuild(unittest.TestCase):
    def test_the_twin_builds_silently_under_the_strictest_warnings_as_errors(self):
        log = build_twin()
        self.assertEqual(log, "", f"the build printed something:\n{log}")
        self.assertTrue(TWIN.is_file())
        text = (FW / "Makefile").read_text()
        for flag in ("-std=c99", "-Wall", "-Wextra", "-Werror", "-pedantic", "-Wshadow", "-Wstrict-prototypes", "-Wmissing-prototypes", "-Wconversion"):
            self.assertIn(flag, text, flag)
        self.assertIn("../../build/b3_firmware", text)                        # products go to the top-level build/, never under b3/
        self.assertEqual(firmware_findings(FW), [])

    def test_the_firmware_directory_rule_is_a_subset_never_the_exact_set(self):
        """The owner's P1 on 4817662: an exact listing would go red at stage 2's first legitimate source
        (the stage-constant defect §9 exists to prevent). The rule: the stage-1 files are REQUIRED, a build
        product anywhere under b3/firmware is REFUSED on its own, and any other source is allowed."""
        d = Path(tempfile.mkdtemp(prefix="b3_fw_rule_"))
        self.addCleanup(shutil.rmtree, d, True)
        shutil.copytree(FW, d / "firmware")
        fw = d / "firmware"
        self.assertEqual(firmware_findings(fw), [])
        for later in ("b3_orch.c", "b3_orch.h", "b3_wire.c", "b3_app.c", "IMPORT.json", "p3_derive.c", "bsp/build.sh", "bsp/lscript.ld", "bsp/out/b3_app.bin", "bsp/out/b3_app.elf"):
            (fw / later).parent.mkdir(parents=True, exist_ok=True)
            (fw / later).write_text("later stage\n")
        self.assertEqual(firmware_findings(fw), [], "a later stage's legitimate sources and the committed image are allowed")
        for product in ("b3_carto.o", "b3_carto.su", "b3_carto.d", "b3_app.map", "libx.a", "b3_carto_twin", "bsp/out/x.o", "build/anything",
                        "b3_app.bin", "b3_app.elf", "bsp/out/other.bin", "bsp/out/b3_app_old.elf", "bsp/b3_app.bin", "bsp/other/b3_app.elf",
                        "nested/deeper/x.elf", "b3_carto_twin.bin"):                       # the owner's P2 on baae5f6: only the two exact paths are the image
            (fw / product).parent.mkdir(parents=True, exist_ok=True)
            (fw / product).write_text("product\n")
            got = firmware_findings(fw)
            needle = "build/" if product.startswith("build/") else product
            self.assertTrue(any(needle in x for x in got), (product, got))
            (fw / product).unlink()
            if product.startswith("build/"):
                (fw / "build").rmdir()
        self.assertEqual(firmware_findings(fw), [])
        (fw / "b3_carto.h").unlink()
        self.assertTrue(any("b3_carto.h" in x and "required" in x for x in firmware_findings(fw)))
        self.assertEqual(COMMITTED_IMAGE, ("bsp/out/b3_app.bin", "bsp/out/b3_app.elf"))
        self.assertEqual(bman.IMAGE_REL, "b3/firmware/" + COMMITTED_IMAGE[0])

    def test_every_frame_stays_far_below_the_bsp_stack_on_the_host_and_on_the_pinned_arm_toolchain(self):
        """The owner's P1 on 4817662: b3_carto_observe once held the whole 15 KB state copy on the stack —
        15 992 bytes on ARM against the BSP's 0x4000-byte stack (firmware/b2/bsp/lscript.ld, byte-for-byte
        reused). The copy is now the caller's scratch; every function's frame is measured with -fstack-usage
        by the host compiler AND by the pinned ARM toolchain (arm-none-eabi-gcc, cortex-a9, freestanding —
        the compiler the image will be built with), and held under FRAME_LIMIT, with the deepest chain
        (observe → check_on_copy, inlined or not) a small fraction of the stack. No skip: an absent toolchain
        is a failure."""
        ld = (R / "firmware/b2/bsp/lscript.ld").read_text()
        m = re.search(r"_STACK_SIZE = DEFINED\(_STACK_SIZE\) \? _STACK_SIZE : (0x[0-9A-Fa-f]+);", ld)
        self.assertIsNotNone(m, "the BSP stack size line")
        stack = int(m.group(1), 16)
        self.assertEqual(stack, 0x4000)
        arm = Path(be.TC) / "bin/arm-none-eabi-gcc"
        self.assertTrue(arm.is_file(), f"the pinned ARM toolchain is absent at {arm}: a failure, not a skip")
        cases = {"host": [os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic"],
                 "arm": [str(arm), *be.ARCH_FLAGS, "-std=c99", "-O2", "-ffreestanding", "-Wall", "-Wextra", "-Werror", "-pedantic"]}
        out = BUILD / "stack_usage"
        out.mkdir(parents=True, exist_ok=True)
        for name, cmd in cases.items():
            with self.subTest(compiler=name):
                obj = out / f"b3_carto_{name}.o"
                p = subprocess.run(cmd + ["-fstack-usage", "-c", "-o", str(obj), str(FW / "b3_carto.c")], capture_output=True, text=True)
                self.assertEqual(p.returncode, 0, p.stderr)
                self.assertEqual(p.stderr, "", "a warning-free compile")
                su = obj.with_suffix(".su").read_text()
                frames = {}
                for line in su.splitlines():
                    parts = line.split("\t")
                    frames[parts[0].split(":")[-1]] = (int(parts[1]), parts[2])
                self.assertIn("b3_carto_observe", frames)
                self.assertIn("b3_carto_state_render", frames)
                for fn, (nbytes, kind) in frames.items():
                    self.assertIn(kind, ("static", "dynamic,bounded"), (fn, kind))   # never an unbounded frame (no VLA, no alloca)
                    self.assertLessEqual(nbytes, FRAME_LIMIT, (name, fn, nbytes))
                deepest = frames["b3_carto_observe"][0] + max((n for fn, (n, _) in frames.items() if fn != "b3_carto_observe"), default=0)
                self.assertLess(deepest * 8, stack, (name, deepest))
        # and the scratch is where the copy lives: the state type is the size the frame no longer carries
        src = (FW / "b3_carto.c").read_text()
        self.assertNotIn("b3_carto work;", src)
        self.assertIn("memcpy(scratch, c, sizeof(*scratch));", src)
        self.assertIn("static b3_carto carto, scratch;", (FW / "b3_carto_twin.c").read_text())

    def test_the_cartographer_unit_is_freestanding(self):
        """b3_carto.c is the image's unit: no stdio, no allocation, no libc but memcpy / memset / strlen."""
        src = (FW / "b3_carto.c").read_text()
        for forbidden in ("#include <stdio.h>", "#include <stdlib.h>", "malloc(", "printf(", "snprintf("):
            self.assertNotIn(forbidden, src)
        self.assertIn("#include <string.h>", src)
        self.assertNotIn("B3_CARTO_N", (FW / "b3_carto.h").read_text().split("#define B3_CARTO_N 292")[0].split("#define B3_CARTO_VERSION")[1])
        self.assertEqual(b3.CARTO_VERSION, "specimen-carto-v1.1")
        self.assertIn('#define B3_CARTO_VERSION "specimen-carto-v1.1"', (FW / "b3_carto.h").read_text())
        self.assertIn("#define B3_CARTO_N 292", (FW / "b3_carto.h").read_text())
        self.assertEqual((bc.N, bl.LUTS, bl.VECTORS), (292, 6, 64))


# ------------------------------------------------------------------ the boundary corpus


class TheCorpus(Lockstep):
    def test_a_single_bit_specimen_decodes_directly_and_bumps_the_version_once(self):
        k, v = TRUTH["mapping"][5]
        self.assertEqual(self.observe([5], [(k, v)]), [(5, k, v)])
        self.assertEqual(self.twin.state(), f"{b3.CARTO_VERSION}|1|0|5:{k}:{v}|5:{k}.{v}")
        self.assertEqual(self.observe([5], [(k, v)]), [])                     # repeated: nothing new, no bump
        self.assertTrue(self.twin.state().startswith(f"{b3.CARTO_VERSION}|1|0|"))

    def test_multi_bit_specimens_narrow_by_intersection_then_decode_by_closure(self):
        pa, pb, pd = TRUTH["mapping"][1], TRUTH["mapping"][2], TRUTH["mapping"][3]
        self.assertEqual(self.observe([1, 2], [pa, pb]), [])
        self.assertEqual(self.twin.state(), f"{b3.CARTO_VERSION}|0|0||" + ";".join(f"{i}:" + ",".join(f"{k}.{v}" for k, v in sorted([pa, pb])) for i in (1, 2)))
        newly = self.observe([1, 3], [pa, pd])
        self.assertEqual(sorted(i for i, _, _ in newly), [1, 2, 3])           # 1 by intersection, 3 by exclusion, 2 by closure
        self.assertEqual([i for i, _, _ in newly], [1, 2, 3], "the Python's order (first-pending): 1, then 2 (closure), then 3")
        self.assertTrue(self.twin.state().startswith(f"{b3.CARTO_VERSION}|1|0|"))

    def test_the_documented_projection(self):
        self.observe([4, 7], [P, Q])
        self.assertEqual(self.twin.state(), f"{b3.CARTO_VERSION}|0|0||4:0.0,0.1;7:0.0,0.1")
        self.observe([4], [P])
        self.assertEqual(self.twin.state(), f"{b3.CARTO_VERSION}|1|0|4:0:0;7:0:1|4:0.0;7:0.0,0.1")

    def test_every_refusal_is_counted_and_commits_nothing(self):
        """The ported corpus of refusals, each an ANOMALY with the state text unchanged but for the count."""
        self.observe([0, 2], [P, Q])
        self.observe([1, 3], [RR, T])
        before = self.twin.state()
        cases = [
            ("a contradiction: 1 toggled U, but 1's candidates are {RR, T}", [0, 1], [P, U]),
            ("a duplicate address", [0, 0], [P, Q]),
            ("a LUT out of range", [0], [(6, 0)]),
            ("a vector out of range", [0], [(0, 64)]),
            ("a duplicate position", [0, 1], [P, P]),
            ("an empty specimen", [], []),
            ("an address out of range", [999], [P]),
            ("|delta| != |intervention|", [0, 1], [P]),
            ("|delta| != |intervention| the other way", [0], [P, Q]),
            ("an address at the edge", [292], [P]),
            ("a huge address", [65535], [P]),
            ("a LUT at the edge with a valid vector", [0], [(6, 63)]),
            ("an empty intersection: 0's candidates are {P, Q}, U is neither", [0, 5], [U, (1, 9)]),
            ("a duplicate position with the counts equal: three fresh addresses over two toggles", [10, 11, 12], [U, U, (1, 9)]),
            ("a duplicate position, all fresh, that no later check would catch", [20, 21, 22, 23], [(2, 1), (2, 1), (2, 2), (2, 3)]),
        ]
        for n, (why, moved, delta) in enumerate(cases, 1):
            with self.subTest(why=why):
                self.assertIsNone(self.observe(moved, delta, why))
                expect = before.replace(f"|0|0|", f"|0|{n}|", 1)
                self.assertEqual(self.twin.state(), expect, why)
        self.assertEqual(self.ref.anomalies, len(cases))

    def test_a_decoded_moved_address_must_toggle_its_own_position(self):
        k, v = TRUTH["mapping"][9]
        self.observe([9], [(k, v)])
        before = self.twin.state()
        self.assertIsNone(self.observe([9], [U]))                             # 9 is decoded at (k, v); U is not it
        self.assertEqual(self.twin.state(), before.replace("|1|0|", "|1|1|", 1))
        self.assertEqual(self.observe([9, 10], [(k, v), U]), [(10, *U)])       # 9 consumes its position; 10 decodes at U
        self.assertIsNone(self.observe([11], [(k, v)]))                       # (k, v) belongs to 9, which was not moved
        self.assertEqual(self.ref.anomalies, 2)

    def test_a_position_claimed_twice_is_a_closure_conflict_refused_atomically(self):
        self.observe([0, 1], [P, Q])
        self.observe([2, 3], [P, Q])
        before = self.twin.state()
        self.assertIsNone(self.observe([0], [P]))                             # 0 at P → 1 at Q → 2, 3 have nothing left
        self.assertEqual(self.twin.state(), before.replace("|0|0|", "|0|1|", 1))
        self.assertEqual(self.ref.version, 0)

    def test_validate_then_commit_a_late_conflict_leaves_the_narrowing_uncommitted(self):
        """A specimen that passes the intervention, the delta and the intersection checks and fails only
        in the closure: the candidate sets it narrowed on the copy are NOT committed."""
        self.observe([0, 1, 2], [P, Q, RR])                                   # candidates {P,Q,RR} for 0, 1, 2
        self.observe([3, 4], [P, Q])                                          # 3, 4: {P, Q}
        before = self.twin.state()
        # 0 and 1 toggled {P, Q}: 0, 1 narrow to {P, Q}; 2 keeps {P,Q,RR}; closure: none decodes yet — consistent
        self.assertEqual(self.observe([0, 1], [P, Q]), [])
        self.assertNotEqual(self.twin.state(), before)
        before = self.twin.state()
        # 2 toggled RR → 2 decodes at RR; then 0, 1, 3, 4 share {P, Q}: no conflict yet (two free positions)
        self.assertEqual(self.observe([2], [RR]), [(2, *RR)])
        before = self.twin.state()
        # 0 toggled P → 0 at P; 1 → Q; then 3 and 4 have nothing: a closure conflict AFTER narrowing 0 — refused whole
        self.assertIsNone(self.observe([0], [P]))
        self.assertEqual(self.twin.state(), before.replace("|1|0|", "|1|1|", 1))
        self.assertEqual(self.ref.decoded.get(0), None)

    def test_the_first_pending_order_is_the_pythons(self):
        """The closure decodes in the order addresses FIRST became pending (the Python dict's order), not in
        address order: two pairs sharing candidate sets are resolved by one specimen in the same closure pass,
        and the newly-decoded list comes out in pending order — which the image's ledger `decoded` reproduces."""
        self.observe([200, 201], [P, RR])                                     # 200, 201: {P, RR}
        self.observe([100, 101], [Q, T])                                      # 100, 101: {Q, T}
        newly = self.observe([200, 100], [P, Q])                              # 200 → P, so 201 → RR; 100 → Q, so 101 → T
        self.assertEqual([i for i, _, _ in newly], [200, 201, 100, 101])      # pending order, not 100, 101, 200, 201
        self.twin.reset()
        self.ref = b3.SpecimenCarto()
        self.observe([100, 101], [Q, T])                                      # the other way round
        self.observe([200, 201], [P, RR])
        newly = self.observe([200, 100], [P, Q])
        self.assertEqual([i for i, _, _ in newly], [100, 101, 200, 201])


# ------------------------------------------------------------------ the pipe protocol


class TheProtocol(Lockstep):
    def test_what_the_twin_cannot_parse_is_refused_without_touching_the_state(self):
        self.observe([4, 7], [P, Q])
        before = self.twin.state()
        for line, why in (("O x", "the address count"), ("O 1", "an address token"), ("O 1 -1 | 1 0.0", "an address token"),
                          ("O 1 4 | 1 0", "the '.' of a position"), ("O 1 4 | 1 0.", "a vector token"), ("O 1 4 | 1 .0", "a LUT token"),
                          ("O 1 4 1 0.0", "the '|' separator"), ("O 1 4 | 2 0.0", "a LUT token"), ("O 1 4 | 1 0.0 extra", "trailing tokens"),
                          ("O 1 4 | 1 0.0 | 1 0.0", "trailing tokens"), ("O 293 " + " ".join(str(i) for i in range(293)) + " | 0", "too many addresses"),
                          ("O 1 4 | 385 " + " ".join("0.0" for _ in range(385)), "too many positions"), ("O 1 70000 | 1 0.0", "an address token"),
                          ("O 1 4 | 1 0.70000", "a vector token"), ("X", "unknown command"), ("", "unknown command"), ("observe 1 4 | 1 0.0", "unknown command"),
                          ("S junk", "unknown command"), ("R junk", "unknown command"), ("Q junk", "unknown command"), ("Sx", "unknown command"),
                          ("Rx", "unknown command"), ("S ", "unknown command"), (" S", "unknown command"), ("O1 4 | 1 0.0", "unknown command"),
                          ("O", "unknown command"), ("Observe 1 4 | 1 0.0", "unknown command")):
            with self.subTest(line=line[:30]):
                reply = self.twin.raw(line)
                self.assertTrue(reply.startswith("ERR "), (line, reply))
                self.assertIn(why, reply)
                self.assertEqual(self.twin.state(), before)
        self.assertEqual(self.ref.anomalies, 0)
        self.assertEqual(self.twin.state(), before, "in particular 'R junk' did not reset the cartographer (the owner's probe)")
        # values that parse but are out of the cartographer's range are the cartographer's refusal (an anomaly), as in Python
        self.assertIsNone(self.observe([292], [P]))
        self.assertIsNone(self.observe([4], [(6, 0)]))
        self.assertIsNone(self.observe([4], [(0, 64)]))
        self.assertEqual(self.twin.state(), before.replace("|0|0|", "|0|3|", 1))

    def test_an_aliasing_or_null_scratch_is_a_bad_call_that_does_nothing_and_counts_nothing(self):
        """The API contract (the owner's P1 on 4817662 made the scratch caller-owned): a scratch that IS the
        state, or no scratch at all, is a programming error — B3_CARTO_BAD_CALL, nothing done, nothing counted
        — probed through the twin's B (aliasing) and N (NULL) commands, each its own guard (the owner's P3 on
        baae5f6). A consistent specimen that would decode, a refused one that would count, and a duplicate
        decode all leave the state — the anomaly count included — byte-identical."""
        k, v = TRUTH["mapping"][5]
        self.observe([4, 7], [P, Q])
        before = self.twin.state()
        for probe in ("B ", "N "):
            for moved, delta in (([5], [(k, v)]), ([0, 0], [P, Q]), ([4], [P]), ([999], [P])):
                with self.subTest(probe=probe.strip(), moved=moved):
                    reply = self.twin.raw(self.twin.observe_line(moved, delta).replace("O ", probe, 1))
                    self.assertEqual(reply, "ERR bad call", (probe, moved, delta))
                    self.assertEqual(self.twin._line(), "STATE " + before)
                    self.assertEqual(self.twin.state(), before)
        self.assertEqual(self.ref.anomalies, 0)
        self.assertEqual(self.observe([5], [(k, v)]), [(5, k, v)])              # the same specimen through O: it decodes
        self.assertIsNone(self.observe([0, 0], [P, Q]))                        # and the refused one through O: counted
        self.assertTrue(self.twin.state().split("|")[2] == "1")

    def test_reset_and_the_empty_state(self):
        self.assertEqual(self.twin.state(), f"{b3.CARTO_VERSION}|0|0||")
        self.observe([4], [P])
        self.assertEqual(self.twin.reset(), f"{b3.CARTO_VERSION}|0|0||")
        self.ref = b3.SpecimenCarto()
        self.assertEqual(self.observe([4], [Q]), [(4, *Q)])                  # a fresh cartographer: no memory of P


# ------------------------------------------------------------------ seeded streams


class SeededStreams(Lockstep):
    def stream(self, seed: int, steps: int, wrong: float, malformed: float):
        rng = random.Random(seed)
        for step in range(steps):
            k = rng.choice([1, 1, 2, 3, 4, 6])
            moved = rng.sample(range(bc.N), k)
            delta = [TRUTH["mapping"][i] for i in moved]
            r = rng.random()
            if r < wrong:
                delta[0] = (rng.randrange(6), rng.randrange(64))
            elif r < wrong + malformed:
                choice = rng.randrange(6)
                if choice == 0:
                    delta = delta[:-1]
                elif choice == 1:
                    moved = moved + [moved[0]]
                elif choice == 2:
                    delta = delta + [delta[0]]
                elif choice == 3:
                    moved = moved[:-1] + [rng.choice([292, 300, 65535])]
                elif choice == 4:
                    delta = delta[:-1] + [(6, rng.randrange(64))]
                else:
                    moved, delta = [], []
            self.observe(moved, delta, f"seed {seed} step {step}")
        return self.ref

    def test_the_python_equivalence_stream(self):
        ref = self.stream(20260917, 1500, 0.05, 0.03)
        self.assertGreater(ref.anomalies, 0)
        self.assertGreater(len(ref.decoded), 200)
        self.assertEqual(self.twin.state(), ref.state_text())

    def test_a_heavier_malformed_mix(self):
        ref = self.stream(20260928, 2500, 0.10, 0.12)
        self.assertGreater(ref.anomalies, 100)
        self.assertGreater(ref.version, 20)


# ------------------------------------------------------------------ the committed prediction


class TheCommittedPrediction(unittest.TestCase):
    """The lifecycle-2 prediction (evidence/b3/prediction.json, pinned at S0): every O-arm ledger entry
    replayed through the twin, the Python cartographer beside it, entry for entry."""

    @classmethod
    def setUpClass(cls):
        cls.pred = json.loads((R / "evidence/b3/prediction.json").read_text())

    def test_every_ledger_entry_of_every_pair(self):
        total = 0
        for r, pair in enumerate(self.pred["pairs"]):
            run = pair["runs"]["O"]
            twin = Twin()
            ref = b3.SpecimenCarto()
            try:
                for e in run["ledger"]:
                    self.assertEqual(int(twin.state().split("|")[1]), e["map_version"], (r, e["seq"]))
                    newly_ref = ref.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
                    newly_twin, text = twin.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
                    self.assertIsNotNone(newly_twin, (r, e["seq"], "the prediction has no anomaly"))
                    self.assertEqual([list(t) for t in newly_twin], e["decoded"], (r, e["seq"]))       # the RECORDED order
                    self.assertEqual([i for i, _, _ in newly_twin], newly_ref, (r, e["seq"]))
                    self.assertEqual(text, ref.state_text(), (r, e["seq"]))
                    v, a = text.split("|")[1:3]
                    self.assertEqual((int(v), int(a)), (e["map_version_after"], e["anomalies"]), (r, e["seq"]))
                    total += 1
                self.assertEqual(len(run["ledger"]), run["ledger_entries"])
                final = twin.state()
                self.assertEqual(int(final.split("|")[1]), run["map_version_final"], r)
                self.assertEqual(final.split("|")[3].count(":") // 2, run["decoded_final"], r)
                self.assertEqual(final.split("|")[2], "0", r)
            finally:
                twin.close()
        self.assertEqual(total, 8000)
        self.assertEqual(total, sum(p["runs"]["O"]["ledger_entries"] for p in self.pred["pairs"]))


if __name__ == "__main__":
    unittest.main()
