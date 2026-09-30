"""The O arm's C side against the Python reference (B3 lifecycle 2, image stage 2): the combined commitment, the
specimen-ledger entry, the record block and the online view, on B2's engine.

The twin (`build/b3_firmware/b3_record_twin`, built by `make -C b3/firmware record-twin` under the strictest host
warnings with -Werror) links b3_record.c and b3_online_view.c (the new board units), the stage-1 b3_carto.c, and
the byte-for-byte copies of B2's b2_search.{c,h}, p3_derive.{c,h} and p3_data.h. The harness plays the fabric
(b2_search.ModelFabric over the truth mapping): the twin proposes, the harness answers with the readout of the
PROPOSED genome, and the twin observes, updates the cartographer and the view, and renders what the image will
write. Held here:

  * the five copies equal firmware/b2/ by digest (IMPORT.json is stage 3);
  * the real O arm — every committed pair, pair 0 included, all 1 000 evaluations and the champion's holdout —
    evaluation by evaluation: the proposal (genome, move kind, parent, bits), the search text, the cartographer
    text, the exact bytes the commitment hashes (search text, "|", cartographer text), the commitment, the
    ledger entry, the record block (exactly one `ledger` sub-block on a search record, none on the holdout
    record) and the operator's view after every evaluation (Python's map_view());
  * the committed prediction's 8 000 O-arm ledger entries rendered by the C ledger writer, byte for byte the
    Python json.dumps(sort_keys, compact);
  * synthetic search states (boundary integers) under the combined commitment;
  * b3_record_json's refusals (a search block without its entry, a holdout block with one, a buffer one byte
    short);
  * the encoders fail closed (the owner's HOLD on 08030dd): b3_ledger_json refuses every entry outside the
    specimen_ledger 1.1.0 schema or the cartographer's version rule — each rule with a control just inside it —
    and bounds every count before any element is read (held under an AddressSanitizer build of the twin, over
    arrays of exactly their capacity); b3_record_json binds the search record's entry field by field to the
    observation just made and to this cartographer (each tampered field accepted by the ledger encoder alone,
    refused by the record) and the holdout record to the champion's evaluation;
  * E1 leakage: the view is empty at evaluation 0; the O initializer and the bridge never name B2_MAP_INIT
    and the O path never calls b2_search_init (source with comments stripped, and the objects' symbols); and
    with ONLY p3_data.h's B2_MAP_INIT changed (a within-LUT permutation that keeps the universe mask) the whole
    O trace is unchanged — a guard with a killable mutant, run here: a bridge that places a decoded address in
    the column B2_MAP_INIT names (invisible on the unchanged table, which equals the truth) diverges;
  * the stack guard: every frame of b3_record.c and b3_online_view.c <= 1 KiB with the host compiler and the
    pinned ARM toolchain, the output buffers the caller's.

No skip: a missing compiler or toolchain, or a failed build, is a FAILURE. The five copies and every temp copy
are built outside b3/ (the top-level build/ or a temp dir); nothing here writes under b3/, builds an image,
writes build evidence, IMPORT.json, a pin table or S0, or touches a board.
"""
from __future__ import annotations

import hashlib
import json
import os
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
import b2_search as bs  # noqa: E402
import b3_carto as b3  # noqa: E402
import b3_online_arm as oa  # noqa: E402

import b2_build_evidence as be  # noqa: E402  (the pinned ARM toolchain's path and arch flags; a frozen B2 module)

FW = R / "b3/firmware"
B2FW = R / "firmware/b2"
BUILD = R / "build/b3_firmware"
TWIN = BUILD / "b3_record_twin"
COPIES = ("b2_search.c", "b2_search.h", "p3_derive.c", "p3_derive.h", "p3_data.h")
NEW_UNITS = ("b3_record.c", "b3_online_view.c")
STAGE2_SOURCES = ("b3_record.c", "b3_record.h", "b3_online_view.c", "b3_online_view.h", "b3_record_twin.c") + COPIES
FRAME_LIMIT = 1024
PRED = json.loads((R / "evidence/b3/prediction.json").read_text())
TRUTH = bm.truth_mapping()
FABRIC = bs.ModelFabric(TRUTH)
MASKS = bl.universe_mask(TRUTH)
TRAIN = bl.train_vectors()
_BUILT: dict = {}


def canon(doc) -> str:
    return json.dumps(doc, sort_keys=True, separators=(",", ":"))


def hexw(tables) -> str:
    return " ".join(f"{t:016x}" for t in tables)


def build(fw: Path = FW, out: Path = BUILD) -> Path:
    """`make -s record-twin` for a firmware tree into `out`, once per (tree, out); the build must be silent."""
    key = (str(fw), str(out))
    if key not in _BUILT:
        cc = os.environ.get("CC", "cc")
        if shutil.which(cc) is None:
            raise AssertionError(f"no host C compiler ({cc}): a failure, never a skip")
        p = subprocess.run(["make", "-s", "-C", str(fw), "record-twin", f"BUILD={out}"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the record twin did not build:\n{p.stdout}{p.stderr}")
        _BUILT[key] = p.stdout + p.stderr
    return out / "b3_record_twin"


class Twin:
    def __init__(self, exe: Path | None = None):
        self.p = subprocess.Popen([str(exe or build())], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def close(self):
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

    def lines(self, n: int) -> list[str]:
        out = []
        for _ in range(n):
            line = self.p.stdout.readline()
            if not line:
                raise AssertionError("the twin closed its output")
            out.append(line.rstrip("\n"))
        return out

    def send(self, text: str, n: int = 1) -> list[str]:
        self.p.stdin.write(text + "\n")
        self.p.stdin.flush()
        return self.lines(n)

    def one(self, text: str) -> str:
        return self.send(text)[0]


def python_view(carto: b3.SpecimenCarto) -> str:
    """Python's map_view(train) in the twin's VIEW syntax."""
    v = carto.map_view(TRAIN)
    total = sum(len(b) for b in v.columns.values())
    body = ";".join(f"{k}:" + ",".join(str(i) for i in v.columns[k]) for k in v.column_keys)
    return f"VIEW {len(v.column_keys)} {total} {body}"


def landscape(pair: dict) -> bl.Landscape:
    return bl.Landscape(PRED["fitness"], pair["landscape_seed"], masks=MASKS, truth=TRUTH)


def run_pair(twin: Twin, r: int, check) -> dict:
    """Drive the twin through committed pair r's O arm beside run_online. `check(what, got, want, n)` compares.
    Returns counts of what was compared, and the first divergence (or None)."""
    pair = PRED["pairs"][r]
    land = landscape(pair)
    budget = PRED["budget_per_arm"]
    oo = oa.run_online(land, pair["operator_seed"], budget, FABRIC, keep_ledger=True, pair=r)
    ref = b3.SpecimenCarto()
    check("init", twin.one(f"I {r} {pair['landscape_seed']} {pair['operator_seed']} {budget} {hexw(FABRIC(0))}"), "OK", 0)
    check("view at evaluation 0", twin.one("V"), "VIEW 0 0 ", 0)
    base = FABRIC(0)
    base_fit = land.train_fitness(base)
    check("the base fitness", base_fit, pair["base_train_fitness"], 0)
    initial = [bs.Individual(0, base, base_fit, born=i) for i in range(bs.MU)]
    check("the O initializer's state", twin.one("S"),
          "SEARCH " + oa.search_state_text(oa.ARM_CODE, pair["landscape_seed"], pair["operator_seed"], budget, 0, 0, base_fit, initial), 0)
    for n in range(budget):
        e = oo.ledger[n]
        prop = twin.one("P").split()
        check("proposal line", prop[0], "PROP", n)
        genome = bc.genome_from_hex(prop[3])
        check("genome", genome, oo.genomes[n], n)
        check("move kind", prop[1], e["move_kind"], n)
        check("parent", int(prop[2]), e["parent_born"], n)
        check("bits", [int(x) for x in prop[5:]], e["intervention"], n)
        check("bit count", int(prop[4]), len(e["intervention"]), n)
        text, search, commit, ledger, block = twin.send("M " + hexw(FABRIC(genome)), 5)
        stext, ctext = oo.search_state_trace[n], oo.carto_state_trace[n]
        check("search trace", search, "SEARCH " + stext, n)
        check("commitment bytes", text, f"TEXT {stext}|{ctext}", n)
        check("commitment = sha256 of those bytes", commit, "COMMIT " + hashlib.sha256(text[5:].encode()).hexdigest(), n)
        check("commitment", commit, "COMMIT " + oo.state_trace[n], n)
        check("ledger", ledger, "LEDGER " + canon(e), n)
        check("block", block, "BLOCK " + oo.blocks[n], n)
        check("exactly one ledger sub-block", block.count('"ledger":'), 1, n)
        ref.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
        check("carto trace", ctext, ref.state_text(), n)
        check("view", twin.one("V"), python_view(ref), n)
    check("budget spent", twin.one("P"), "DONE", budget)
    champ = twin.one("C").split()
    check("champion", bc.genome_from_hex(champ[1]), oo.champion.genome, budget)
    block, commit = twin.send("H " + hexw(FABRIC(oo.champion.genome)), 2)
    check("holdout block", block, "BLOCK " + oo.champion_block, budget)
    check("no ledger on the holdout block", block.count('"ledger":'), 0, budget)
    check("final commitment", commit, "COMMIT " + oo.state_trace[-1], budget)
    check("the prediction's final commitment", oo.state_trace[-1], pair["runs"]["O"]["final_state_sha256"], budget)
    return {"evaluations": budget, "ledger": oo.ledger}


def strip_comments(src: str) -> str:
    src = re.sub(r"/\*.*?\*/", " ", src, flags=re.S)
    return re.sub(r"//[^\n]*", " ", src)


def map_arrays(text: str) -> tuple[list[int], list[int]]:
    def arr(name):
        m = re.search(r"static const unsigned char " + name + r"\[B2_MAP_N\] = \{(.*?)\};", text, re.S)
        assert m, name
        return [int(x) for x in re.findall(r"\d+", m.group(1))]
    return arr("B2_MAP_LUT"), arr("B2_MAP_INIT")


def permute_init(text: str) -> str:
    """p3_data.h with ONLY B2_MAP_INIT changed: within each LUT the INIT values are rotated by one address, so the
    set of positions (the universe mask) is the same and the map (which address sits where) is not."""
    lut, init = map_arrays(text)
    new = list(init)
    for k in sorted(set(lut)):
        idx = [i for i in range(len(lut)) if lut[i] == k]
        for a, b in zip(idx, idx[1:] + idx[:1]):
            new[a] = init[b]
    m = re.search(r"(static const unsigned char B2_MAP_INIT\[B2_MAP_N\] = \{)(.*?)(\};)", text, re.S)
    it = iter(new)
    body = re.sub(r"\d+", lambda _m: str(next(it)), m.group(2))
    return text[:m.start(2)] + body + text[m.end(2):]


# ------------------------------------------------------------------ the copies and the build


class TheCopiesAndTheBuild(unittest.TestCase):
    def test_the_five_copies_equal_firmware_b2_by_digest(self):
        for name in COPIES:
            with self.subTest(name=name):
                a, b = (FW / name).read_bytes(), (B2FW / name).read_bytes()
                self.assertEqual(hashlib.sha256(a).hexdigest(), hashlib.sha256(b).hexdigest(), name)
                self.assertGreater(len(a), 1000)
        self.assertFalse((FW / "IMPORT.json").exists(), "IMPORT.json is stage 3")

    def test_the_record_twin_builds_silently_and_the_carto_twin_target_is_unchanged(self):
        self.assertEqual(build(), TWIN)
        self.assertEqual(_BUILT[(str(FW), str(BUILD))], "", "the build printed something")
        self.assertTrue(TWIN.is_file())
        mk = (FW / "Makefile").read_text()
        self.assertIn("$(BUILD)/b3_carto_twin: b3_carto_twin.c b3_carto.c b3_carto.h\n\t@mkdir -p $(BUILD)\n"
                      "\t$(CC) $(CFLAGS) -o $@ b3_carto_twin.c b3_carto.c\n", mk)
        self.assertIn("twin: $(BUILD)/b3_carto_twin\n", mk)
        self.assertIn("record-twin: $(BUILD)/b3_record_twin\n", mk)
        for name in STAGE2_SOURCES:
            self.assertTrue((FW / name).is_file(), name)
            self.assertIn(name, mk)
        for p in FW.rglob("*"):                           # no build product under b3/
            self.assertFalse(p.is_file() and (p.suffix in (".o", ".su", ".d", ".map", ".a") or p.name in ("b3_record_twin", "b3_carto_twin")), p)

    def test_the_new_units_are_freestanding(self):
        for name in NEW_UNITS:
            src = strip_comments((FW / name).read_text())
            for forbidden in ("#include <stdio.h>", "#include <stdlib.h>", "malloc(", "printf(", "snprintf("):
                self.assertNotIn(forbidden, src, (name, forbidden))

    def test_every_frame_of_the_new_units_stays_under_1_kib_on_the_host_and_on_the_pinned_arm_toolchain(self):
        ld = (R / "firmware/b2/bsp/lscript.ld").read_text()
        m = re.search(r"_STACK_SIZE = DEFINED\(_STACK_SIZE\) \? _STACK_SIZE : (0x[0-9A-Fa-f]+);", ld)
        self.assertIsNotNone(m)
        stack = int(m.group(1), 16)
        self.assertEqual(stack, 0x4000)
        arm = Path(be.TC) / "bin/arm-none-eabi-gcc"
        self.assertTrue(arm.is_file(), f"the pinned ARM toolchain is absent at {arm}: a failure, not a skip")
        cases = {"host": [os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic"],
                 "arm": [str(arm), *be.ARCH_FLAGS, "-std=c99", "-O2", "-ffreestanding", "-Wall", "-Wextra", "-Werror", "-pedantic"]}
        out = BUILD / "stack_usage_stage2"
        out.mkdir(parents=True, exist_ok=True)
        # the units a record render reaches: the new ones, the cartographer's renderer and the hash
        reached = NEW_UNITS + ("b3_carto.c", "p3_derive.c")
        for cname, cmd in cases.items():
            frames_all = {}
            for unit in reached:
                with self.subTest(compiler=cname, unit=unit):
                    obj = out / f"{Path(unit).stem}_{cname}.o"
                    p = subprocess.run(cmd + ["-I", str(FW), "-fstack-usage", "-c", "-o", str(obj), str(FW / unit)], capture_output=True, text=True)
                    self.assertEqual(p.returncode, 0, p.stderr)
                    self.assertEqual(p.stderr, "")
                    frames = {}
                    for line in obj.with_suffix(".su").read_text().splitlines():
                        parts = line.split("\t")
                        frames[parts[0].split(":")[-1]] = (int(parts[1]), parts[2])
                    frames_all[unit] = frames
                    if unit in NEW_UNITS:
                        self.assertTrue(frames, unit)
                        for fn, (nbytes, kind) in frames.items():
                            self.assertIn(kind, ("static", "dynamic,bounded"), (cname, unit, fn, kind))
                            self.assertLessEqual(nbytes, FRAME_LIMIT, (cname, unit, fn, nbytes))
            for fn in ("b3_record_json", "b3_ledger_json", "b3_state_hex", "b3_commitment_render", "b3_search_state_render", "b3_delta_positions"):
                self.assertIn(fn, frames_all["b3_record.c"], (cname, fn))
            for fn in ("b3_online_init", "b3_online_view_rebuild"):
                self.assertIn(fn, frames_all["b3_online_view.c"], (cname, fn))
            # an upper bound on any chain through the record path: every frame of the new units plus the deepest
            # of the cartographer's and the hash's
            bound = sum(n for u in NEW_UNITS for n, _ in frames_all[u].values()) + \
                max(n for n, _ in frames_all["b3_carto.c"].values()) + max(n for n, _ in frames_all["p3_derive.c"].values())
            self.assertLess(bound * 4, stack, (cname, bound))
        for name in NEW_UNITS:                            # the output buffers are the caller's: no buffer parameter is filled on a frame
            src = strip_comments((FW / name).read_text())
            self.assertIsNone(re.search(r"\bchar\s+\w+\s*\[\s*(\d{4,}|JSON_MAX|LINE_MAX_BYTES)", src), name)


# ------------------------------------------------------------------ E1: no frozen-map leakage


class NoFrozenMapLeakage(unittest.TestCase):
    def test_the_o_initializer_and_the_bridge_never_name_b2_map_init_nor_call_b2_search_init(self):
        for name in ("b3_online_view.c", "b3_online_view.h", "b3_record.c", "b3_record.h", "b3_record_twin.c"):
            src = strip_comments((FW / name).read_text())
            for word in ("B2_MAP_INIT", "b2_search_init", "build_view"):
                self.assertIsNone(re.search(r"\b" + word + r"\b", src), (name, word))
        self.assertIn("B2_MAP_INIT", (FW / "b2_search.c").read_text(), "the control: the B2 unit does name it")

    def test_the_objects_carry_no_b2_map_init_and_no_reference_to_b2_search_init(self):
        build()
        out = BUILD / "symbols_stage2"
        out.mkdir(parents=True, exist_ok=True)
        cc = os.environ.get("CC", "cc")
        nm = shutil.which("nm")
        self.assertIsNotNone(nm, "nm is required: a failure, not a skip")
        seen_control = False
        for unit in ("b3_online_view.c", "b3_record.c", "b3_record_twin.c", "b2_search.c"):
            obj = out / (Path(unit).stem + ".o")
            p = subprocess.run([cc, "-std=c99", "-O2", "-I", str(FW), "-c", "-o", str(obj), str(FW / unit)], capture_output=True, text=True)
            self.assertEqual(p.returncode, 0, p.stderr)
            syms = subprocess.run([nm, str(obj)], capture_output=True, text=True, check=True).stdout
            names = {line.split()[-1]: line.split()[-2] for line in syms.splitlines() if line.split()}
            if unit == "b2_search.c":                       # the control: B2's own object defines b2_search_init and holds the table
                self.assertEqual(names.get("b2_search_init"), "T")
                self.assertIn("B2_MAP_INIT", names)
                seen_control = True
                continue
            self.assertNotIn("B2_MAP_INIT", names, unit)
            self.assertNotIn("b2_search_init", names, unit)
            self.assertNotIn("build_view", names, unit)
        self.assertTrue(seen_control)

    def test_only_b2_map_init_changed_the_whole_o_trace_is_unchanged_and_a_leaky_bridge_is_killed(self):
        """p3_data.h with ONLY B2_MAP_INIT changed — a within-LUT rotation that keeps the universe mask (so the
        landscape is the same), while every relation the frozen map states moves. The O arm, whose view is the
        cartographer's, must produce the same trace to the byte. The killable mutant: a bridge that places a decoded
        address in the column B2_MAP_INIT names instead of the one the cartographer decoded — identical on the
        unchanged table (which equals the truth), divergent on the rotated one."""
        orig = (FW / "p3_data.h").read_text()
        rotated = permute_init(orig)
        lut0, init0 = map_arrays(orig)
        lut1, init1 = map_arrays(rotated)
        self.assertEqual(lut1, lut0, "B2_MAP_LUT unchanged")
        self.assertEqual(sorted(zip(lut1, init1)), sorted(zip(lut0, init0)), "the same positions: the universe mask is unchanged")
        self.assertGreater(sum(a != b for a, b in zip(init0, init1)), 250, "most relations moved")
        body = re.compile(r"static const unsigned char B2_MAP_INIT\[B2_MAP_N\] = \{.*?\};", re.S)
        mo, mr = body.search(orig), body.search(rotated)
        self.assertEqual((orig[:mo.start()], orig[mo.end():]), (rotated[:mr.start()], rotated[mr.end():]),
                         "every byte outside the B2_MAP_INIT initializer is unchanged")
        self.assertNotEqual(mo.group(0), mr.group(0))
        # the rotated table is load-bearing for B2's own view: the train columns it states differ
        train = set(TRAIN)
        cols = lambda init: sorted((i, v) for i, v in enumerate(init) if v in train)  # noqa: E731
        self.assertNotEqual(cols(init0), cols(init1))

        anchor = "        v = pos % B3_CARTO_VECTORS;\n"
        view_src = (FW / "b3_online_view.c").read_text()
        self.assertEqual(view_src.count(anchor), 1)
        leaky = view_src.replace(anchor, "        v = (int)B2_MAP_INIT[i];\n")

        def tree(tag: str, data: str, view: str) -> Path:
            d = Path(tempfile.mkdtemp(prefix=f"b3_e1_{tag}_"))
            self.addCleanup(shutil.rmtree, d, True)
            shutil.copytree(FW, d / "fw")
            (d / "fw/p3_data.h").write_text(data)
            (d / "fw/b3_online_view.c").write_text(view)
            return build(d / "fw", d / "build")

        def first_divergence(exe: Path) -> tuple | None:
            twin = Twin(exe)
            found = []

            def check(what, got, want, n):
                if got != want and not found:
                    found.append((what, n))
                    raise _Stop()
            try:
                run_pair(twin, 0, check)
            except _Stop:
                pass
            finally:
                try:
                    twin.close()
                except AssertionError:
                    pass
            return found[0] if found else None

        self.assertIsNone(first_divergence(tree("rotated", rotated, view_src)), "only B2_MAP_INIT changed: the O trace is unchanged")
        self.assertIsNone(first_divergence(tree("leaky_orig", orig, leaky)), "the leak is invisible on the unchanged table")
        got = first_divergence(tree("leaky_rotated", rotated, leaky))
        self.assertIsNotNone(got, "the mutant bridge is killed by the rotation")


class _Stop(Exception):
    pass


# ------------------------------------------------------------------ the real O arm


class TheRealOArm(unittest.TestCase):
    def check(self, what, got, want, n):
        self.assertEqual(got, want, f"{self._pair} evaluation {n}: {what}")

    def test_every_committed_pair_evaluation_by_evaluation_and_its_holdout(self):
        """Pair 0 is the owner's minimum; the other seven cost seconds and are run too. The 24 026-record session
        comparison is the orchestrator stage's."""
        total = 0
        for r in range(len(PRED["pairs"])):
            self._pair = f"pair {r}"
            twin = Twin()
            try:
                got = run_pair(twin, r, self.check)
                self.assertEqual(got["ledger"], PRED["pairs"][r]["runs"]["O"]["ledger"], r)
                total += got["evaluations"]
            finally:
                twin.close()
        self.assertEqual(total, 8000)

    def test_the_record_writer_refuses_what_it_must(self):
        """On a live state: a search block without its entry, a holdout block with one, a buffer exactly the length
        (no room for the NUL) and an eval index that is not the entry's seq are each refused (0); one byte more
        renders the block."""
        pair = PRED["pairs"][0]
        twin = Twin()
        self.addCleanup(twin.close)
        self.assertEqual(twin.one("K"), "ERR no observation")
        twin.one(f"I 0 {pair['landscape_seed']} {pair['operator_seed']} {PRED['budget_per_arm']} {hexw(FABRIC(0))}")
        genome = bc.genome_from_hex(twin.one("P").split()[3])
        lines = twin.send("M " + hexw(FABRIC(genome)), 5)
        k = twin.one("K").split()
        self.assertEqual(k[0], "K")
        no_ledger, holdout_with_ledger, exact, plus, n, wrong_seq = (int(x) for x in k[1:])
        self.assertEqual((no_ledger, holdout_with_ledger, exact, wrong_seq), (0, 0, 0, 0))
        self.assertEqual(n, len(lines[4]) - len("BLOCK "))
        self.assertEqual(plus, n)
        self.assertEqual(twin.one("C"), "ERR no champion", "no champion before the budget is spent")


# ------------------------------------------------------------------ the encoders fail closed (the owner's HOLD on 08030dd)

ASAN_BUILD = R / "build/b3_firmware_asan"
STRICT = "-std=c99 -O1 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wconversion"


def build_asan(fw: Path = FW, out: Path = ASAN_BUILD) -> Path:
    """The same twin under AddressSanitizer: a count past an array's capacity that is read before it is refused
    is a global-buffer-overflow report and a non-zero exit — never a quiet 0."""
    key = ("asan", str(fw), str(out))
    if key not in _BUILT:
        p = subprocess.run(["make", "-s", "-C", str(fw), "record-twin", f"BUILD={out}",
                            f"CFLAGS={STRICT} -g -fno-omit-frame-pointer -fsanitize=address"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the ASan twin did not build (a failure, not a skip):\n{p.stdout}{p.stderr}")
        _BUILT[key] = p.stdout + p.stderr
    return out / "b3_record_twin"


class _Probe:
    """A twin on committed pair 0 with a small budget, observed `k` times (the harness is the fabric)."""

    def __init__(self, tc: unittest.TestCase, exe: Path | None = None, budget: int = 16, k: int = 1):
        self.pair = PRED["pairs"][0]
        self.twin = Twin(exe)
        tc.addCleanup(self.twin.close)
        self.budget = budget
        tc.assertEqual(self.twin.one(f"I 0 {self.pair['landscape_seed']} {self.pair['operator_seed']} {budget} {hexw(FABRIC(0))}"), "OK")
        self.last = None
        for _ in range(k):
            self.observe()

    def observe(self):
        prop = self.twin.one("P").split()
        self.genome = bc.genome_from_hex(prop[3])
        out = self.twin.send("M " + hexw(FABRIC(self.genome)), 5)
        self.entry = json.loads(out[3][len("LEDGER "):])
        self.block = out[4][len("BLOCK "):]
        return self.entry

    def t(self, spec: str) -> int:
        line = self.twin.one(("T " + spec).rstrip())
        assert line.startswith("T "), line
        return int(line[2:])

    def full_ledger_carto(self):
        """The LEDGER cartographer with all 292 addresses decoded (292 single-bit specimens of the truth)."""
        assert self.twin.one("X") == "OK"
        for i in range(bc.N):
            k, v = TRUTH["mapping"][i]
            assert self.twin.one(f"E {i + 1} 0 random 0 1 {i} | 1 {k}.{v}").startswith("LEDGER {")


class TheLedgerEncoderFailsClosed(unittest.TestCase):
    """P1: b3_ledger_json refuses (0) every entry outside the specimen_ledger 1.1.0 schema or the cartographer's
    version rule, and bounds every count before any element is read. Each refusal has a control one step inside
    the rule that renders."""

    def test_the_owners_reproductions_through_the_ledger_cartographer(self):
        pr = _Probe(self)
        pos = lambda ids: " ".join(f"{k}.{v}" for k, v in sorted(TRUTH["mapping"][i] for i in ids))  # noqa: E731  (positions_of order)
        self.assertEqual(pr.twin.one("X"), "OK")
        for line, ok in ((f"E 1 0 random 1 5 1 2 3 4 5 | 5 {pos([1, 2, 3, 4, 5])}", False),       # five interventions (maxItems 4)
                         ("E 1 0 random 1 0 | 0", False),                                        # an empty intervention (minItems 1)
                         (f"E 0 0 random 1 1 7 | 1 {pos([7])}", False),                          # seq 0 (minimum 1)
                         (f"E 1 0 random -1 1 8 | 1 {pos([8])}", False),                         # fitness -1 (minimum 0)
                         (f"E 1 0 random 41 1 9 | 1 {pos([9])}", False),                         # fitness above F1's 40 train columns
                         (f"E 1 0 random 1 3 12 11 13 | 3 {pos([11, 12, 13])}", False),           # an intervention out of order
                         ("E 1 0 random 1 2 14 15 | 2 " + " ".join(f"{k}.{v}" for k, v in sorted((TRUTH["mapping"][i] for i in (14, 15)), reverse=True)),
                          False),                                                                # a delta out of positions_of order
                         (f"E 1 0 random 40 4 20 21 22 23 | 4 {pos([20, 21, 22, 23])}", True),    # the controls: inside every bound
                         (f"E 1 0 column 0 1 30 | 1 {pos([30])}", True)):
            with self.subTest(line=line[:40]):
                got = pr.twin.one(line)
                self.assertTrue(got.startswith("LEDGER {") if ok else got == "LEDGER ", (line, got))

    def test_every_schema_rule_on_the_live_entry(self):
        pr = _Probe(self)
        e = pr.entry
        self.assertEqual(pr.t("L"), len(canon(e)))                               # the untouched entry renders
        refused = ["seq 0", "fitness -1", "fitness 41", "kind 2", "kind -1", "bits 0", "bits 2 5 3", "bits 2 3 3",
                   "bits 1 292", "bits 1 65535", "delta 2 7 5", "delta 2 5 5", "delta 1 384", "delta 1 65535",
                   f"map_version_after {e['map_version'] + 1}",                    # a bump without a decode
                   f"newly 1 0 map_version_after {e['map_version'] + 1}",         # a decode of an undecoded address
                   f"map_version {e['map_version_after'] + 1}"]
        accepted = ["fitness 0", "fitness 40", "kind 1", "kind 0", "bits 1 291", "bits 4 0 1 2 291", "delta 1 383",
                    "delta 0", "delta 3 0 64 383", "seq 4294967295", "anomalies 7", "parent_born 99"]
        for spec in refused:
            with self.subTest(refused=spec):
                self.assertEqual(pr.t("L " + spec), 0, spec)
        for spec in accepted:
            with self.subTest(accepted=spec):
                self.assertGreater(pr.t("L " + spec), 0, spec)

    def test_newly_is_unique_decoded_and_bounded(self):
        pr = _Probe(self)
        pr.full_ledger_carto()
        bump = "carto other map_version 0 map_version_after 1"
        self.assertGreater(pr.t(f"L {bump} newly 2 5 6"), 0)
        self.assertGreater(pr.t(f"L {bump} newly 3 200 5 100"), 0, "the cartographer's order, not sorted")
        self.assertEqual(pr.t(f"L {bump} newly 2 5 5"), 0, "a duplicate")
        self.assertEqual(pr.t(f"L {bump} newly 1 292"), 0, "out of range")
        self.assertEqual(pr.t("L map_version 0 map_version_after 1 newly 1 5"), 0, "not decoded by the O arm's cartographer")
        self.assertEqual(pr.t("L carto other newly 1 5"), 0, "a decode without the version bump")

    def _counts(self, exe: Path | None):
        pr = _Probe(self, exe)
        pr.full_ledger_carto()
        bump = "carto other map_version 0 map_version_after 1"
        for spec, want in (("nbits 4", True), ("nbits 5", False), ("nbits 100000", False), ("nbits -1", False), ("nbits 0", False),
                           ("ndelta 384", True), ("ndelta 385", False), ("ndelta 1000000", False), ("ndelta -1", False),
                           (f"{bump} nnewly 292", True), (f"{bump} nnewly 293", False), (f"{bump} nnewly 1000000", False),
                           (f"{bump} nnewly -1", False)):
            with self.subTest(spec=spec):
                got = pr.t("L " + spec)
                self.assertTrue(got > 0 if want else got == 0, (spec, got))

    def test_every_count_is_bounded_before_any_element_is_read_under_asan(self):
        """The count probes run over arrays of EXACTLY their capacity filled 0, 1, 2 … — every element valid — so a
        count one past the capacity is only refused in time if the bound is checked before the loop: under
        AddressSanitizer a late check is a global-buffer-overflow and a crashed twin (which close() reports)."""
        self._counts(None)
        self._counts(build_asan())
        self.assertEqual(_BUILT[("asan", str(FW), str(ASAN_BUILD))], "")


class TheRecordBindsItsLedger(unittest.TestCase):
    """P2: b3_record_json binds the search record's entry, field by field, to the observation just made and to this
    cartographer, and the holdout record to the champion's evaluation. Every tampered field is ACCEPTED by the
    ledger encoder alone (T L) — so the refusal is the binding, not the schema."""

    def test_each_field_is_bound_to_the_search_and_the_cartographer(self):
        pr = _Probe(self, k=3)
        e = pr.entry
        pr.full_ledger_carto()                       # so that "carto other" holds every newly address: only the binding refuses it
        self.assertEqual(pr.t("B"), len(pr.block), "the untouched entry: the block the twin wrote")
        bits = e["intervention"]
        other = sorted(set(range(bc.N)) - set(bits))
        same_len = sorted(other[:len(bits)])
        cases = {
            "seq": f"seq {e['seq'] + 1}",
            "parent_born": f"parent_born {e['parent_born'] + 1}",
            "move kind": f"kind {1 if e['move_kind'] == 'random' else 0}",
            "fitness": f"fitness {e['fitness'] + 1 if e['fitness'] < 40 else e['fitness'] - 1}",
            "bits (same count)": f"bits {len(same_len)} " + " ".join(map(str, same_len)),
            "the cartographer": "carto other",
            "the map version": f"map_version {e['map_version'] + 1} map_version_after {e['map_version_after'] + 1}",
            "the anomaly count": f"anomalies {e['anomalies'] + 1}",
        }
        for what, spec in cases.items():
            with self.subTest(field=what):
                self.assertGreater(pr.t("L " + spec), 0, f"{what}: the ledger encoder alone accepts it")
                self.assertEqual(pr.t("B " + spec), 0, f"{what}: the record refuses it")
        # another bit count with the SAME prefix — on the first observation, four bits — so that only the count
        # binding can tell (b2_search's last_bits beyond the count hold a previous move's stale values, which a
        # longer tampered list would be compared against)
        first = _Probe(self, k=1)
        self.assertEqual(len(first.entry["intervention"]), 4)
        prefix = first.entry["intervention"][:3]
        spec = "bits 3 " + " ".join(map(str, prefix))
        self.assertGreater(first.t("L " + spec), 0)
        self.assertEqual(first.t("B " + spec), 0, "a prefix of the move's bits: the count binding refuses it")

    def test_a_search_record_needs_a_fresh_observation_and_a_holdout_record_the_champions(self):
        pr = _Probe(self, budget=16, k=16)
        self.assertGreater(pr.t("B"), 0)
        self.assertEqual(pr.twin.one("U 16 0"), "U 0", "no holdout before the champion's evaluation")
        self.assertEqual(pr.twin.one("C").split()[0], "CHAMP")
        self.assertEqual(pr.t("B"), 0, "the holdout is in flight: no search record")
        self.assertEqual(pr.twin.one("U 16 0"), "U 0", "the holdout is in flight")
        block, _commit = pr.twin.send("H " + hexw(FABRIC(pr.genome)), 2)   # any readout; the holdout value is the C side's
        h = json.loads(block[len("BLOCK "):])["holdout"]
        self.assertEqual(pr.twin.one(f"U 16 {h}"), f"U {len(block) - len('BLOCK ')}")
        self.assertEqual(pr.twin.one(f"W 16 {h}"), "W 0", "the valid holdout block handed a ledger entry: refused")
        for spec in (f"U 17 {h}", f"U 15 {h}", f"U 16 {h + 1}", f"U 0 {h}"):
            with self.subTest(spec=spec):
                self.assertEqual(pr.twin.one(spec), "U 0", spec)
        self.assertEqual(pr.t("B"), 0, "the holdout is done: no search record")
        fresh = _Probe(self, k=1)
        self.assertEqual(fresh.twin.one("P").split()[0], "PROP")
        self.assertEqual(fresh.t("B"), 0, "a proposal is in flight: the last observation is no longer fresh")
        self.assertGreater(fresh.t("L"), 0)


# ------------------------------------------------------------------ the committed ledger, the synthetic states


class TheCommittedLedger(unittest.TestCase):
    def test_every_o_arm_ledger_entry_of_the_prediction_byte_for_byte(self):
        twin = Twin()
        self.addCleanup(twin.close)
        total = 0
        for r, pair in enumerate(PRED["pairs"]):
            self.assertEqual(twin.one("X"), "OK")
            for e in pair["runs"]["O"]["ledger"]:
                line = (f"E {e['seq']} {e['parent_born']} {e['move_kind']} {e['fitness']} {len(e['intervention'])} "
                        + " ".join(str(i) for i in e["intervention"]) + f" | {len(e['behaviour_delta'])} "
                        + " ".join(f"{k}.{v}" for k, v in e["behaviour_delta"]))
                self.assertEqual(twin.one(line), "LEDGER " + canon(e), (r, e["seq"]))
                total += 1
        self.assertEqual(total, 8000)


class SyntheticStates(unittest.TestCase):
    def test_boundary_search_states_under_the_combined_commitment(self):
        twin = Twin()
        self.addCleanup(twin.close)
        ref = b3.SpecimenCarto()
        k, v = TRUTH["mapping"][5]
        states = [
            (2, 0, 0, 0, 0, 0, 0, [(0, 0, 0), (0, 1, 0), (0, 2, 0), (0, 3, 0)]),
            (2, 4294967295, 4294967295, 4294967295, 4294967295, 4294967295, 2147483647,
             [(40, 4294967295, (1 << 292) - 1), (-1, 7, 1 << 291), (-2147483648, 8, 1), (39, 9, 0xDEADBEEF << 100)]),
            (0, 1, 2, 3, 4, 5, -7, [(-7, 10, 1 << 31), (3, 11, 1 << 32), (2, 12, 1 << 63), (1, 13, 1 << 64)]),
        ]
        self.assertEqual(twin.one("X"), "OK")
        for step, specimen in enumerate((None, ([5], [(k, v)]), ([4, 7], [(0, 0), (0, 1)]))):
            if specimen is not None:
                moved, delta = specimen
                ref.observe(moved, delta)
                twin.one(f"E 1 0 random 0 {len(moved)} " + " ".join(map(str, moved)) + f" | {len(delta)} " + " ".join(f"{a}.{b}" for a, b in delta))
            for arm, ls, os_, budget, evals, gen, best, pop in states:
                with self.subTest(step=step, arm=arm, best=best):
                    members = " ".join(f"{f}:{b}:{bc.genome_to_hex(g)}" for f, b, g in pop)
                    text, commit = twin.send(f"Z {arm} {ls} {os_} {budget} {evals} {gen} {best} {members}", 2)
                    inds = [bs.Individual(g, None, f, born=b) for f, b, g in pop]
                    stext = oa.search_state_text(arm, ls, os_, budget, evals, gen, best, inds)
                    self.assertEqual(text, f"TEXT {stext}|{ref.state_text()}")
                    self.assertEqual(commit, "COMMIT " + oa.state_sha256(stext, ref.state_text()))
                    if arm != 2:                         # B2's own commitment over the same search text (the text is B2's)
                        self.assertEqual(hashlib.sha256(stext.encode()).hexdigest(), bs.state_sha256(arm, ls, os_, budget, evals, gen, best, inds))


class TheProtocol(unittest.TestCase):
    def test_unparseable_or_out_of_order_commands_are_refused(self):
        twin = Twin()
        self.addCleanup(twin.close)
        for line in ("", "x", "S", "V", "P", "C", "S junk", "M 0", "H 0", "I", "I 0 1 2", "E", "Z 1", "VV", "V ", "Q junk", "X junk",
                     "E 1 0 other 0 1 5 | 1 0.0", "E 1 0 random 0 1 5 | 1 6.0", "E 1 0 random 0 1 5 1 0.0"):
            with self.subTest(line=line):
                self.assertTrue(twin.one(line).startswith("ERR "), line)
        pair = PRED["pairs"][0]
        self.assertEqual(twin.one(f"I 0 {pair['landscape_seed']} {pair['operator_seed']} 1000 {hexw(FABRIC(0))}"), "OK")
        self.assertEqual(twin.one("M " + hexw(FABRIC(0))), "ERR no proposal in flight")
        self.assertEqual(twin.one("M 0000000000000000"), "ERR cannot parse M")
        self.assertEqual(twin.one("V"), "VIEW 0 0 ")


if __name__ == "__main__":
    unittest.main()
