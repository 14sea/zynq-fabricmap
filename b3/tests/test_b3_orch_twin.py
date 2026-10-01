"""b3/firmware/b3_orch.c against b3/host/b3_session.run_context and the formal B3 seed rule (B3 lifecycle 2, image
stage 4; the discipline of tests/test_b2_twin.py's session mode).

The twin (`build/b3_firmware/b3_orch_twin`, `make -C b3/firmware orch-twin`, strictest host warnings, -Werror) links
b3_orch.c with the units the image will link for the session, and is LINKED WITH --wrap on b2_search_init and
b3_online_init, so every initializer call the orchestrator makes is logged (the actual path). The harness plays the
fabric (b2_search.ModelFabric over the truth mapping). Held here:

  * b3_seed_data.h is byte for byte a fresh render of b3/host/gen_b3_seed_data.py, its excluded set is production's
    (b3_plan.session_exclusion() plus b2_search.EXCLUDED_SEEDS) and the committed plan's count, and it carries
    nothing of the prediction;
  * the seed rule on the board: the B3 profile's pairs are the committed plan's; the B3Q profile's are the
    production builder's (b3_plan.build_qualification_plan, in memory — no canonical B3Q document); a master for
    which B2's old table and the B3 rule DIFFER gives the B3 rule's pairs; the helper's extra-exclusion matches
    b2_search.pair_seeds; only the two profiles are accepted by the production path;
  * the committed eight pairs: all 24 026 candidates — seq, baseline, absolute pair, arm, holdout, genome and the
    observed block bytes — equal run_context's, the session completes, R and F are initialised through
    b2_search_init and O through b3_online_init (never b2_search_init) once per pair with that pair's seeds, and the
    O arm's view is empty at evaluation 0 of every pair;
  * a later slice (pairs 1 and 2, decoded from the page's flags): absolute pairs, their seeds and arm orders;
  * B3Q (the production builders): 125 records, 123 fitness values, 40 ledger entries;
  * an unscored candidate — the opening baseline, each arm's search, each arm's holdout, the closing baseline —
    ends the epoch: nothing after it, complete 0, and an unscored O candidate leaves the map where it was;
  * reserved flags, an illegal slice, a wrong profile / master / budget / total are refused before any candidate;
    at the C API, every slice whose check would overflow (pair_first or pair_count INT_MAX, INT_MIN, ...) is refused
    and proposes nothing, also under UBSan with every report fatal (which also runs a whole B3Q session clean);
  * the generator refuses — by name, before a header — a plan whose schema, version, lifecycle, session, types,
    fitness, master, excluded count, or budget / N / gate binding against production's validated gate disagree;
  * the stack: every frame on the session path <= 1 KiB with the host compiler and the pinned ARM toolchain, but for
    the three named (compiler, unit, function) exceptions in B2's frozen b2_search.c (the owner's ruling, capped at
    2 KiB, counted in the chain); and a CALL-CHAIN ESTIMATE through b3_orch's entry points (from -fcallgraph-info, the
    emitter's indirect call resolved) well inside the BSP stack. The estimate INCLUDES LIBRARY ALLOWANCES that are
    assumptions, not proven bounds (snprintf's 2 KiB above all): it is not a stack conclusion for the image. Image
    stage 5 completes the stack assessment with the ARM libc actually linked, the application, the wire, the BSP and
    the image's build flags.

No skip. Builds go to the top-level build/; nothing here writes under b3/, builds an image or touches a board.
"""
from __future__ import annotations

import copy
import json
import os
import re
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b1_carto as bc  # noqa: E402
import b2_search as bs  # noqa: E402
import b3_carto as carto_mod  # noqa: E402
import b3_plan as pl  # noqa: E402
import b3_records as brec  # noqa: E402
import b3_session as bsess  # noqa: E402
import gen_b3_seed_data as gen  # noqa: E402

import b2_build_evidence as be  # noqa: E402  (the pinned ARM toolchain; a frozen B2 module)

FW = R / "b3/firmware"
BUILD = R / "build/b3_firmware"
TWIN = BUILD / "b3_orch_twin"
HEADER = FW / "b3_seed_data.h"
PLAN = json.loads((R / "evidence/b3/plan.json").read_text())
PRED = json.loads((R / "evidence/b3/prediction.json").read_text())
CTX = brec.context_from(PLAN, PRED, 0, PLAN["pairs"])
FABRIC = bs.ModelFabric()
FRAME_LIMIT = 1024
B3_UNITS = ("b3_orch.c", "b3_record.c", "b3_online_view.c", "b3_carto.c")          # B3's own and derived: every frame <= 1 KiB
VERBATIM_UNITS = ("b2_search.c", "p3_derive.c")                                    # B2's bytes, frozen: bounded, and in the chain
BOARD_UNITS = B3_UNITS + VERBATIM_UNITS
# The owner's ruling of 2026-10-01 on the 1 KiB frame limit: B2's frozen b2_search.c (a byte-for-byte copy that cannot
# change, and that ran on the board with this BSP stack) has frames above 1 KiB, and ONLY these exact (compiler, unit,
# function) combinations are excepted, each capped at B2_FRAME_CAP and each still counted in the call chain:
#     select_generation     host 1 216 B   pinned ARM 1 304 B
#     b2_search_state_hex   host 1 184 B   (pinned ARM 544 B: the 1 KiB limit applies there)
# Every other function — B3's own units, and every other function of a verbatim unit — keeps the 1 KiB limit. An
# exception that no longer exceeds 1 KiB is itself a failure (a stale exception must be removed, not left lying).
B2_FRAME_EXCEPTIONS = {("host", "b2_search.c", "select_generation"), ("arm", "b2_search.c", "select_generation"),
                       ("host", "b2_search.c", "b2_search_state_hex")}
B2_FRAME_CAP = 2048
ENTRY_POINTS = ("b3_orch_init", "b3_orch_next", "b3_orch_observe", "b3_orch_unobserved", "b3_orch_record_block",
                "b3_page_slice", "b3_pair_seeds", "b3_profile_seeds")
EMITTERS = ("sha_emit",)                     # the only emitter a board unit hands b3_carto_state_render / b3_commitment_render
# ASSUMED library frames (not proven bounds; image stage 5 measures the libc actually linked)
LIBRARY_ALLOWANCE = {"snprintf": 2048, "vsnprintf": 2048, "memcpy": 128, "memset": 128, "strlen": 64, "memmove": 128,
                     "__stack_chk_fail": 64,
                     # libgcc's ARM EABI division helpers (leaf routines, a few registers)
                     "__aeabi_uldivmod": 128, "__aeabi_ldivmod": 128, "__aeabi_uidivmod": 64, "__aeabi_idivmod": 64,
                     "__aeabi_uidiv": 64, "__aeabi_idiv": 64}
_CACHE: dict = {}


def cached_session_exclusion():
    """Production's session_exclusion() validates the gate report (minutes); its value is pure, so it is computed ONCE
    per process and the builders below are handed copies of the same production result."""
    if "excl" not in _CACHE:
        _CACHE["excl"] = _REAL_SESSION_EXCLUSION()
    return copy.deepcopy(_CACHE["excl"])


_REAL_SESSION_EXCLUSION = pl.session_exclusion
_REAL_GATE_INPUTS = pl.gate_inputs


def cached_gate_inputs():
    """Production's gate_inputs() (the validated gate report), computed once per process for the same reason."""
    if "gi" not in _CACHE:
        _CACHE["gi"] = _REAL_GATE_INPUTS()
    return copy.deepcopy(_CACHE["gi"])


def with_cached_exclusion(fn, *a, **k):
    pl.session_exclusion = lambda gate_report=pl.GATE_REPORT: cached_session_exclusion()
    pl.gate_inputs = lambda gate_report=pl.GATE_REPORT: cached_gate_inputs()
    try:
        return fn(*a, **k)
    finally:
        pl.session_exclusion = _REAL_SESSION_EXCLUSION
        pl.gate_inputs = _REAL_GATE_INPUTS


def gen_inputs() -> dict:
    if "gen" not in _CACHE:
        _CACHE["gen"] = with_cached_exclusion(gen.inputs)
    return _CACHE["gen"]


def b3q():
    """B3Q's plan, prediction and context from the PRODUCTION builders, in memory."""
    if "b3q" not in _CACHE:
        fid, msha = PLAN["fitness"], PLAN["map"]["sha256"]
        qplan = with_cached_exclusion(pl.build_qualification_plan, fid, msha, CTX.seeds)
        qpred = with_cached_exclusion(pl.build_qualification_prediction, fid, msha, CTX.seeds)
        _CACHE["b3q"] = (qplan, qpred, brec.context_from(qplan, qpred, 0, qplan["pairs"]))
    return _CACHE["b3q"]


def hexw(tables) -> str:
    return " ".join(f"{t:016x}" for t in tables)


def build() -> str:
    if "log" not in _CACHE:
        if shutil.which(os.environ.get("CC", "cc")) is None:
            raise AssertionError("no host C compiler: a failure, never a skip")
        p = subprocess.run(["make", "-s", "-C", str(FW), "orch-twin"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the orchestrator twin did not build:\n{p.stdout}{p.stderr}")
        _CACHE["log"] = p.stdout + p.stderr
    return _CACHE["log"]


class Twin:
    def __init__(self):
        build()
        self.p = subprocess.Popen([str(TWIN)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, text=True, bufsize=1)

    def send(self, line: str):
        self.p.stdin.write(line + "\n")
        self.p.stdin.flush()

    def line(self) -> str:
        out = self.p.stdout.readline()
        if not out:
            raise AssertionError("the twin closed its output")
        return out.rstrip("\n")

    def one(self, line: str) -> str:
        self.send(line)
        return self.line()

    def close(self):
        try:
            self.send("Q")
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


def drive(twin: Twin, command: str, unscored_at: int | None = None) -> dict:
    """Run one SESSION / SESSIONF command to its END, answering every candidate from the fabric (or UNSCORED at
    seq `unscored_at`). Returns the candidates as tuples, the blocks, the views, END, CARTO and INITS."""
    twin.send(command)
    cands, blocks, views = [], {}, {}
    while True:
        line = twin.line()
        if line == "REFUSED":
            return {"refused": True}
        if line.startswith("END "):
            break
        assert line.startswith("CAND "), line
        head, ghex = line.split(" | ")
        f = head.split()
        c = (int(f[5]), f[1] == "1", int(f[2]), None if f[3] == "-" else f[3], f[4] == "1", bc.genome_from_hex(ghex))
        cands.append(c)
        views[c[0]] = (int(f[6]), f[7])
        if unscored_at is not None and c[0] == unscored_at:
            twin.send("UNSCORED")
            continue
        twin.send(hexw(FABRIC(c[5])))
        if not c[1]:
            b = twin.line()
            assert b.startswith("BLOCK "), b
            blocks[c[0]] = b[6:]
    _, n, complete = line.split()
    carto = twin.line()
    inits = twin.line()
    assert carto.startswith("CARTO ") and inits.startswith("INITS"), (carto, inits)
    return {"refused": False, "cands": cands, "blocks": blocks, "views": views, "records": int(n),
            "complete": int(complete), "carto": carto[6:], "inits": inits.split()[1:]}


def reference(ctx, unscored_at=None):
    s = bsess.run_context(ctx, unscored_at=unscored_at)
    return [(c.seq, c.is_baseline, c.pair, c.arm, c.holdout, c.genome) for c in s.candidates], \
           {c.seq: c.block for c in s.candidates if not c.is_baseline and c.block}, s


def slice_flags(total: int, first: int, count: int, reserved: int = 0) -> int:
    return (reserved << 28) | ((count - 1) << 24) | (first << 20) | ((total - 1) << 16)


# ------------------------------------------------------------------ the build and the header


class TheBuildAndTheSeedHeader(unittest.TestCase):
    def test_the_twin_builds_silently_with_both_initializers_wrapped(self):
        self.assertEqual(build(), "")
        mk = (FW / "Makefile").read_text()
        self.assertIn("ORCH_WRAP = -Wl,--wrap=b2_search_init -Wl,--wrap=b3_online_init", mk)
        self.assertIn("$(CC) $(CFLAGS) $(ORCH_WRAP) -o $@ $(ORCH_SRC)", mk)

    def test_the_seed_header_is_a_fresh_render_byte_for_byte(self):
        self.assertEqual(HEADER.read_text(), gen.render(gen_inputs()), "b3/firmware/b3_seed_data.h is stale: run b3/host/gen_b3_seed_data.py")

    def test_the_header_s_set_is_production_s_and_the_committed_plan_s_count(self):
        text = HEADER.read_text()
        body = text.split("B3_SEED_EXCLUDED[B3_SEED_EXCLUDED_N] = {")[1].split("};")[0]
        got = [int(x) for x in re.findall(r"(\d+)u", body)]
        excl, _ = cached_session_exclusion()
        want = sorted(set(excl) | set(bs.EXCLUDED_SEEDS))
        self.assertEqual(got, want)
        self.assertEqual(got, sorted(set(got)), "ascending, distinct: the board's binary search")
        self.assertEqual(len(got), PLAN["seed_derivation"]["excluded_values_total"])
        self.assertIn(f"#define B3_SEED_EXCLUDED_N {len(want)}", text)
        self.assertIn(f'#define B3_SEED_EXCLUDED_SHA256 "{gen.excluded_sha256(want)}"', text)
        self.assertIn(f"#define B3_PROFILE_B3_MASTER {PLAN['seed_derivation']['master_seed']}u", text)
        self.assertIn(f"#define B3_PROFILE_B3Q_MASTER {pl.qualification_master()}u", text)
        self.assertIn(f'#define B3_SEED_GATE_REPORT_SHA256 "{gen.sha256_file(pl.GATE_REPORT)}"', text)

    def test_the_header_carries_nothing_of_the_prediction(self):
        text = HEADER.read_text()
        data = re.sub(r"/\*.*?\*/", " ", text, flags=re.S)
        names = set(re.findall(r"#define\s+(\w+)", data)) | set(re.findall(r"static const \w+ (\w+)\[", data))
        self.assertTrue(all(n.startswith(("B3_SEED_", "B3_PROFILE_")) for n in names - {"B3_SEED_DATA_H"}), names)
        for pair in PRED["pairs"]:
            o = pair["runs"]["O"]
            for digest in (o["final_state_sha256"], o["ledger_sha256"], o["champion_genome_sha256"], o["online_map_sha256"]):
                self.assertNotIn(digest, text)
            for t in pair["target"]:
                self.assertNotIn(t, text)
        for word in ("fitness", "genome", "ledger", "state_sha256"):
            self.assertNotIn(word, data, word)


class TheGeneratorChecksThePlanAgainstTheGate(unittest.TestCase):
    """The owner's P2 on 0fe24b0: the B3 profile is a contract the board accepts, so a plan that merely parses must not
    be compiled in. Each probe is a COPY of the committed plan in a temp directory with one change (the committed file
    is never touched); the generator must refuse it by name before rendering. No gate number is written here: the
    budget and N the plan must agree with are production's gate_inputs()."""

    @classmethod
    def setUpClass(cls):
        import tempfile
        cls.dir = Path(tempfile.mkdtemp(prefix="b3_seedgen_"))

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.dir, True)

    def probe(self, name: str, edit) -> Path:
        doc = copy.deepcopy(PLAN)
        edit(doc)
        p = self.dir / f"{name}.json"
        p.write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
        return p

    def test_the_unchanged_plan_renders_the_committed_header(self):
        gi = cached_gate_inputs()
        inp = gen_inputs()
        self.assertEqual((inp["b3"]["budget"], inp["b3"]["pairs"]), (gi["budget_per_arm"], gi["pairs"]))
        self.assertEqual(HEADER.read_text(), gen.render(inp))
        copy_inp = with_cached_exclusion(gen.inputs, self.probe("unchanged", lambda d: None))
        self.assertEqual((copy_inp["values"], copy_inp["b3"], copy_inp["b3q"]), (inp["values"], inp["b3"], inp["b3q"]))

    def test_every_breach_is_refused_by_name_before_a_header(self):
        gi = cached_gate_inputs()
        cases = {
            "budget_per_arm 999 is not the gate's B*": lambda d: d.__setitem__("budget_per_arm", gi["budget_per_arm"] - 1),
            "pairs 7 is not the gate's required N": lambda d: d.__setitem__("pairs", gi["pairs"] - 1),
            "schema 'b3_plan_x' is not 'b3_plan'": lambda d: d.__setitem__("schema", "b3_plan_x"),
            "fitness 'F2' is not the preregistered 'F1'": lambda d: d.__setitem__("fitness", "F2"),
            "schema_version '1.0.0' is not": lambda d: d.__setitem__("schema_version", "1.0.0"),
            "lifecycle 1 is not the integer 2": lambda d: d.__setitem__("lifecycle", 1),
            "lifecycle True is not the integer 2": lambda d: d.__setitem__("lifecycle", True),
            "session 'B3Q' is not 'B3'": lambda d: d.__setitem__("session", "B3Q"),
            "budget_per_arm True is not a positive integer": lambda d: d.__setitem__("budget_per_arm", True),
            "budget_per_arm '1000' is not a positive integer": lambda d: d.__setitem__("budget_per_arm", str(gi["budget_per_arm"])),
            "pairs 8.0 is not a positive integer": lambda d: d.__setitem__("pairs", float(gi["pairs"])),
            "master_seed": lambda d: d["seed_derivation"].__setitem__("master_seed", d["seed_derivation"]["master_seed"] + 1),
            "label / commit": lambda d: d["seed_derivation"].__setitem__("label", "b3-session-1"),
            "gate binding (path, sha256)": lambda d: d["gate"].__setitem__("sha256", "0" * 64),
            "gate head_at_run": lambda d: d["gate"].__setitem__("head_at_run", "0" * 40),
            "gate rules_version": lambda d: d["gate"].__setitem__("rules_version", "architecture v0.2 §9"),
            "excludes 2065 values": lambda d: d["seed_derivation"].__setitem__("excluded_values_total", d["seed_derivation"]["excluded_values_total"] - 1),
            "no gate object": lambda d: d.pop("gate"),
        }
        for i, (needle, edit) in enumerate(cases.items()):
            with self.subTest(breach=needle):
                with self.assertRaises(ValueError) as cm:
                    with_cached_exclusion(gen.inputs, self.probe(f"p{i}", edit))
                self.assertIn(needle.replace("2065", str(PLAN["seed_derivation"]["excluded_values_total"] - 1)), str(cm.exception))


# ------------------------------------------------------------------ the seed rule


class TheSeedRule(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.twin = Twin()

    @classmethod
    def tearDownClass(cls):
        cls.twin.close()

    def seeds(self, line: str) -> list[tuple[int, int]]:
        out = self.twin.one(line).split()
        vals = [int(x) for x in out[1:]]
        return [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]

    def profile(self, master, budget, total):
        out = self.twin.one(f"PROFILE {master} {budget} {total}").split()
        vals = [int(x) for x in out[2:]]
        return int(out[1]), [(vals[i], vals[i + 1]) for i in range(0, len(vals), 2)]

    def test_the_b3_profile_s_pairs_are_the_committed_plan_s(self):
        prof, got = self.profile(CTX.master_seed, CTX.budget, CTX.pairs_total)
        self.assertEqual(prof, 1)
        self.assertEqual(got, CTX.seeds)
        self.assertEqual(got, [(p["landscape_seed"], p["operator_seed"]) for p in PRED["pairs"]])

    def test_the_b3q_profile_s_pairs_are_the_production_builder_s(self):
        qplan, _qpred, qctx = b3q()
        prof, got = self.profile(qplan["seed_derivation"]["master_seed"], qplan["budget_per_arm"], qplan["pairs"])
        self.assertEqual(prof, 2)
        self.assertEqual(got, [tuple(x) for x in qplan["seed_derivation"]["pairs"]])
        self.assertEqual(got, qctx.seeds)
        self.assertEqual(qplan["seed_derivation"]["master_seed"], pl.qualification_master())
        b3_flat = {s for p in CTX.seeds for s in p}
        self.assertFalse(b3_flat & {s for p in got for s in p}, "B3Q excludes every seed of B3's pairs")

    def test_a_master_where_b2_s_table_and_the_b3_rule_differ(self):
        """The lifecycle-2 gate's own master: its 200 pairs are in the B3 set, not in B2's compiled table."""
        gate = json.loads(pl.GATE_REPORT.read_text())
        m = gate["seeds"]["master_seed"]
        text = (R / "firmware/b2/p3_data.h").read_text()
        b2_table = frozenset(int(x, 16) for x in re.findall(r"0x([0-9a-f]{8})ul", text))
        excl, _ = cached_session_exclusion()
        b3_rule = bs.pair_seeds(m, 8, exclude=frozenset(excl))
        b2_old = bs.pair_seeds(m, 8, exclude=b2_table)
        self.assertNotEqual(b3_rule, b2_old, "the control: the two rules differ for this master")
        self.assertEqual(self.seeds(f"SEEDS {m} 8"), b3_rule)
        self.assertEqual(self.profile(m, 1000, 8), (0, []), "the production path refuses a master that is no profile")

    def test_the_helper_s_extra_exclusion_and_dedup_match_pair_seeds(self):
        excl, _ = cached_session_exclusion()
        base = frozenset(excl)
        for m in (CTX.master_seed, 1, 0xFFFFFFFF, 123456789):
            for count in (1, 3, 16):
                with self.subTest(master=m, count=count):
                    self.assertEqual(self.seeds(f"SEEDS {m} {count}"), bs.pair_seeds(m, count, exclude=base))
        first = bs.pair_seeds(CTX.master_seed, 3, exclude=base)
        extra = [s for p in first for s in p]
        got = self.seeds(f"SEEDS {CTX.master_seed} 3 " + " ".join(map(str, extra)))
        self.assertEqual(got, bs.pair_seeds(CTX.master_seed, 3, exclude=base | set(extra)))
        self.assertFalse({s for p in got for s in p} & set(extra))

    def test_only_the_two_profiles_pass_the_production_path(self):
        qm = pl.qualification_master()
        for args in ((CTX.master_seed, 999, 8), (CTX.master_seed, 1000, 7), (CTX.master_seed, 1000, 9), (CTX.master_seed, 40, 1),
                     (qm, 1000, 8), (qm, 40, 2), (qm, 41, 1), (CTX.master_seed + 1, 1000, 8), (0, 0, 1)):
            with self.subTest(args=args):
                self.assertEqual(self.profile(*args), (0, []))
        self.assertEqual(self.twin.one("SEEDS 5 0"), "ERR cannot parse SEEDS")
        self.assertEqual(self.twin.one("SEEDS 5 17"), "ERR cannot parse SEEDS")


# ------------------------------------------------------------------ the sessions


class TheCommittedSession(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref, cls.ref_blocks, _ = reference(CTX)
        twin = Twin()
        try:
            cls.got = drive(twin, f"SESSION {CTX.master_seed} {CTX.budget} {CTX.pairs_total} 0 {CTX.pairs_total}")
        finally:
            twin.close()

    def test_every_candidate_and_every_block_is_run_context_s(self):
        g = self.got
        self.assertFalse(g["refused"])
        self.assertEqual(len(self.ref), 24026)
        self.assertEqual(len(g["cands"]), 24026)
        for a, b in zip(g["cands"], self.ref):
            self.assertEqual(a, b, a[0])
        self.assertEqual(g["blocks"], self.ref_blocks)
        self.assertEqual(len(g["blocks"]), 24024)
        self.assertEqual((g["records"], g["complete"]), (24026, 1))

    def test_the_initializers_actually_called(self):
        """R and F through b2_search_init (arm codes 0, 1), O through b3_online_init, once per pair, in the pair's arm
        order and with the pair's landscape seed — and never b2_search_init with the O arm."""
        want = []
        for r in range(CTX.pairs_total):
            for a in pl.arm_order(r):
                lseed = CTX.seeds[r][0]
                want.append(f"online:2:{lseed}" if a == "O" else f"b2:{0 if a == 'R' else 1}:{lseed}")
        self.assertEqual(self.got["inits"], want)
        self.assertFalse(any(x.startswith("b2:2:") for x in self.got["inits"]))

    def test_the_o_view_is_empty_at_evaluation_0_of_every_pair(self):
        firsts = [c[0] for c in self.got["cands"] if c[3] == "online" and not c[4] and self.got["views"][c[0]][0] == 1]
        self.assertEqual(len(firsts), CTX.pairs_total)
        for seq in firsts:
            self.assertEqual(self.got["views"][seq][1], "0,0", seq)
        later = [self.got["views"][c[0]][1] for c in self.got["cands"] if c[3] == "online" and not c[4]]
        self.assertTrue(any(v != "0,0" for v in later), "the control: the view does fill as the map decodes")

    def test_the_final_map_is_the_last_pair_s_prediction(self):
        o = PRED["pairs"][-1]["runs"]["O"]
        ver, anomalies = self.got["carto"].split("|")[1:3]
        self.assertEqual((int(ver), int(anomalies)), (o["map_version_final"], o["anomalies"]))


class ALaterSlice(unittest.TestCase):
    def test_pairs_1_and_2_from_the_page_s_flags(self):
        ctx = brec.context_from(PLAN, PRED, 1, 2)
        ref, ref_blocks, _ = reference(ctx)
        twin = Twin()
        self.addCleanup(twin.close)
        self.assertEqual(twin.one(f"SLICE {slice_flags(8, 1, 2)}"), "SLICE 8 1 2")
        got = drive(twin, f"SESSIONF {slice_flags(8, 1, 2) | 0x1F} {CTX.master_seed} {CTX.budget}")   # the instrument's low bits untouched
        self.assertEqual(got["cands"], ref)
        self.assertEqual(got["blocks"], ref_blocks)
        self.assertEqual({c[2] for c in got["cands"] if not c[1]}, {1, 2})
        orders = []
        for r in (1, 2):
            seen = []
            for c in got["cands"]:
                if c[2] == r and not c[4] and c[3] not in seen:
                    seen.append(c[3])
            orders.append("".join({"random_safe": "R", "map_guided": "F", "online": "O"}[a] for a in seen))
        self.assertEqual(orders, [pl.ARM_SEQUENCE[1], pl.ARM_SEQUENCE[2]])
        self.assertEqual(got["inits"][0].split(":")[2], str(CTX.seeds[1][0]))
        for b in got["blocks"].values():
            d = json.loads(b)
            self.assertEqual((d["landscape_seed"], d["operator_seed"]), CTX.seeds[d["pair"]])
        self.assertEqual(got["complete"], 1)


class TheB3QSession(unittest.TestCase):
    def test_125_records_123_fitness_values_40_ledger_entries(self):
        qplan, qpred, qctx = b3q()
        ref, ref_blocks, _ = reference(qctx)
        twin = Twin()
        self.addCleanup(twin.close)
        got = drive(twin, f"SESSION {qplan['seed_derivation']['master_seed']} {qplan['budget_per_arm']} {qplan['pairs']} 0 1")
        self.assertEqual(got["cands"], ref)
        self.assertEqual(got["blocks"], ref_blocks)
        self.assertEqual(len(got["cands"]), 125)
        self.assertEqual(qplan["records"]["total"], 125)
        fitness = [json.loads(b) for b in got["blocks"].values()]
        self.assertEqual(sum(1 for d in fitness if d["fitness"] is not None or d["holdout"] is not None), 123)
        ledgers = [d["ledger"] for d in fitness if "ledger" in d]
        self.assertEqual(len(ledgers), 40)
        self.assertEqual(ledgers, qpred["pairs"][0]["runs"]["O"]["ledger"])
        self.assertEqual(got["complete"], 1)


class Unscored(unittest.TestCase):
    """B3Q (one pair, budget 40, order RFO): an unscored candidate at every kind of position."""

    @classmethod
    def setUpClass(cls):
        cls.qplan, cls.qpred, cls.qctx = b3q()
        cls.cmd = f"SESSION {cls.qplan['seed_derivation']['master_seed']} {cls.qplan['budget_per_arm']} {cls.qplan['pairs']} 0 1"
        full, _, _ = reference(cls.qctx)
        cls.full = full
        cls.ledger = cls.qpred["pairs"][0]["runs"]["O"]["ledger"]

    def where(self, arm: str | None, holdout: bool, k: int = 1) -> int:
        if arm is None:
            return 1 if k == 1 else len(self.full)
        hits = [c[0] for c in self.full if c[3] == arm and c[4] == holdout]
        return hits[k - 1]

    def carto_after(self, n: int) -> str:
        c = carto_mod.SpecimenCarto()
        for e in self.ledger[:n]:
            c.observe(e["intervention"], [tuple(p) for p in e["behaviour_delta"]])
        return c.state_text()

    def test_every_position(self):
        o_first = self.where("online", False, 1)
        o_mid = self.where("online", False, 17)
        cases = {"the opening baseline": (1, 0), "the closing baseline": (len(self.full), 40),
                 "R search": (self.where("random_safe", False, 5), 0), "F search": (self.where("map_guided", False, 9), 0),
                 "O search, first": (o_first, 0), "O search, mid": (o_mid, 16), "O search, last": (self.where("online", False, 40), 39),
                 "R holdout": (self.where("random_safe", True), 40), "F holdout": (self.where("map_guided", True), 40),
                 "O holdout": (self.where("online", True), 40)}
        for name, (seq, o_observed) in cases.items():
            with self.subTest(position=name):
                ref, ref_blocks, s = reference(self.qctx, unscored_at=seq)
                twin = Twin()
                try:
                    got = drive(twin, self.cmd, unscored_at=seq)
                finally:
                    twin.close()
                self.assertTrue(s.ended_early)
                self.assertEqual(got["cands"], ref, name)
                self.assertEqual(got["cands"][-1][0], seq, "nothing after the unscored candidate")
                self.assertEqual(got["complete"], 0, name)
                self.assertEqual(got["records"], seq)
                self.assertEqual(got["blocks"], ref_blocks, name)
                if seq > 1 and seq >= o_first:
                    self.assertEqual(got["carto"], self.carto_after(o_observed), f"{name}: the map holds exactly the observed specimens")


STRICT = "-std=c99 -O1 -Wall -Wextra -Werror -pedantic -Wshadow -Wstrict-prototypes -Wmissing-prototypes -Wconversion"
UBSAN_BUILD = R / "build/b3_firmware_ubsan"
INT_MAX, INT_MIN = 2**31 - 1, -2**31


def build_ubsan() -> Path:
    """The same twin under UndefinedBehaviorSanitizer, every report fatal: an overflow is a crash, never a value."""
    if "ubsan" not in _CACHE:
        p = subprocess.run(["make", "-s", "-C", str(FW), "orch-twin", f"BUILD={UBSAN_BUILD}",
                            f"CFLAGS={STRICT} -g -fsanitize=undefined -fno-sanitize-recover=all"], capture_output=True, text=True)
        if p.returncode != 0:
            raise AssertionError(f"the UBSan twin did not build (a failure, not a skip):\n{p.stdout}{p.stderr}")
        _CACHE["ubsan"] = p.stdout + p.stderr
    return UBSAN_BUILD / "b3_orch_twin"


class TheSliceAtTheCApi(unittest.TestCase):
    """The owner's P2 on 0fe24b0: b3_orch_init checked pair_first + pair_count > pairs_total, which overflows for
    pair_first = INT_MAX or pair_count = INT_MAX — accepted, and a candidate proposed. INITRAW calls the C API with ANY
    signed 32-bit values (SESSION's parser bounds them and hid this); a refusal must be -1 AND propose nothing, and
    under UBSan (every report fatal) the check itself must not overflow."""

    CASES = [(INT_MAX, 1), (1, INT_MAX), (INT_MAX, INT_MAX), (INT_MIN, 1), (0, INT_MIN), (-1, 2), (8, 1), (7, 2), (0, 9),
             (0, 0), (0, -1), (7, INT_MAX)]

    def run_cases(self, exe: Path):
        t = Twin.__new__(Twin)
        t.p = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        m, b, n = CTX.master_seed, CTX.budget, CTX.pairs_total
        try:
            for first, count in self.CASES:
                with self.subTest(exe=exe.parent.name, first=first, count=count):
                    self.assertEqual(t.one(f"INITRAW {m} {b} {n} {first} {count}"), "INIT -1 0")
            for first, count in ((0, 8), (7, 1), (3, 5)):
                self.assertEqual(t.one(f"INITRAW {m} {b} {n} {first} {count}"), "INIT 0 1", "the controls: a legal slice proposes")
            for total in (INT_MAX, INT_MIN, 0, 17):
                self.assertEqual(t.one(f"INITRAW {m} {b} {total} 0 1"), "INIT -1 0", total)
        finally:
            t.close()
        self.assertEqual(t.p.stderr.read(), "", "no sanitizer report")
        t.p.stderr.close()

    def test_the_c_api_refuses_every_overflowing_slice_and_proposes_nothing(self):
        build()
        self.run_cases(TWIN)

    def test_the_same_under_ubsan_and_a_whole_session_is_clean(self):
        exe = build_ubsan()
        self.assertEqual(_CACHE["ubsan"], "")
        self.run_cases(exe)
        qplan, _qpred, qctx = b3q()
        ref, ref_blocks, _ = reference(qctx)
        t = Twin.__new__(Twin)
        t.p = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1)
        try:
            got = drive(t, f"SESSION {qplan['seed_derivation']['master_seed']} {qplan['budget_per_arm']} {qplan['pairs']} 0 1")
        finally:
            t.close()
        self.assertEqual(t.p.stderr.read(), "", "no sanitizer report over a whole B3Q session")
        t.p.stderr.close()
        self.assertEqual(got["cands"], ref)
        self.assertEqual(got["blocks"], ref_blocks)


class Refusals(unittest.TestCase):
    def test_refused_before_any_candidate(self):
        twin = Twin()
        self.addCleanup(twin.close)
        m, b, n = CTX.master_seed, CTX.budget, CTX.pairs_total
        qm = pl.qualification_master()
        cases = [f"SESSIONF {slice_flags(8, 0, 8, reserved=1)} {m} {b}", f"SESSIONF {slice_flags(8, 0, 8, reserved=8)} {m} {b}",
                 f"SESSIONF {slice_flags(8, 7, 2)} {m} {b}", f"SESSIONF {slice_flags(8, 0, 9)} {m} {b}",
                 f"SESSION {m} {b} {n} 8 1", f"SESSION {m} {b} {n} 0 0", f"SESSION {m} {b} {n} 6 3",
                 f"SESSION {m + 1} {b} {n} 0 1", f"SESSION {m} 999 {n} 0 1", f"SESSION {m} {b} 7 0 1", f"SESSION {m} 0 {n} 0 1",
                 f"SESSION {qm} 1000 8 0 1", f"SESSION {qm} 40 2 0 1", f"SESSION {m} 40 1 0 1",
                 f"SESSIONF {slice_flags(9, 0, 1)} {m} {b}"]
        for cmd in cases:
            with self.subTest(cmd=cmd):
                self.assertEqual(twin.one(cmd), "REFUSED", cmd)
        self.assertEqual(twin.one(f"SLICE {slice_flags(8, 0, 8, reserved=2)}"), "SLICE REFUSED")
        self.assertEqual(twin.one(f"SLICE {slice_flags(8, 7, 2)}"), "SLICE REFUSED")
        self.assertEqual(twin.one(f"SLICE {slice_flags(16, 15, 1)}"), "SLICE 16 15 1")


# ------------------------------------------------------------------ the stack


def compile_su_ci(cmd: list[str], unit: str, out: Path) -> tuple[dict, dict]:
    """-fstack-usage and -fcallgraph-info=su for one unit: (frames by node title, edges by node title)."""
    obj = out / (Path(unit).stem + ".o")
    p = subprocess.run(cmd + ["-I", str(FW), "-fstack-usage", "-fcallgraph-info=su", "-c", "-o", str(obj), str(FW / unit)],
                       capture_output=True, text=True)
    assert p.returncode == 0 and p.stderr == "", p.stderr
    ci = obj.with_suffix(".ci").read_text()
    nodes, edges = {}, {}
    for m in re.finditer(r'node: \{ title: "([^"]+)" label: "([^"]*)"', ci):
        title, label = m.group(1), m.group(2)
        sz = re.search(r"(\d+) bytes \((static|dynamic,bounded|dynamic)\)", label)
        nodes[title] = (int(sz.group(1)), sz.group(2)) if sz else None
    for m in re.finditer(r'edge: \{ sourcename: "([^"]+)" targetname: "([^"]+)"', ci):
        edges.setdefault(m.group(1), []).append(m.group(2))
    return nodes, edges


class TheStack(unittest.TestCase):
    def test_every_frame_and_the_deepest_chain_on_the_host_and_on_the_pinned_arm_toolchain(self):
        ld = (R / "firmware/b2/bsp/lscript.ld").read_text()
        stack = int(re.search(r"_STACK_SIZE = DEFINED\(_STACK_SIZE\) \? _STACK_SIZE : (0x[0-9A-Fa-f]+);", ld).group(1), 16)
        self.assertEqual(stack, 0x4000)
        arm = Path(be.TC) / "bin/arm-none-eabi-gcc"
        self.assertTrue(arm.is_file(), f"the pinned ARM toolchain is absent at {arm}: a failure, not a skip")
        cases = {"host": [os.environ.get("CC", "cc"), "-std=c99", "-O2", "-Wall", "-Wextra", "-Werror", "-pedantic"],
                 "arm": [str(arm), *be.ARCH_FLAGS, "-std=c99", "-O2", "-ffreestanding", "-Wall", "-Wextra", "-Werror", "-pedantic"]}
        seen_exceptions: set = set()
        for cname, cmd in cases.items():
            out = BUILD / f"stack_usage_stage4_{cname}"
            out.mkdir(parents=True, exist_ok=True)
            frames, edges = {}, {}
            for unit in BOARD_UNITS:
                n, e = compile_su_ci(cmd, unit, out)
                for title, v in n.items():
                    if v is not None:
                        self.assertIn(v[1], ("static", "dynamic,bounded"), (cname, unit, title))
                        fn = title.split(":")[-1].split(".")[0]
                        if (cname, unit, fn) in B2_FRAME_EXCEPTIONS:
                            self.assertGreater(v[0], FRAME_LIMIT, f"a stale exception: {(cname, unit, fn)} is {v[0]} B")
                            self.assertLessEqual(v[0], B2_FRAME_CAP, (cname, unit, title, v[0]))
                            seen_exceptions.add((cname, unit, fn))
                        else:
                            self.assertLessEqual(v[0], FRAME_LIMIT, (cname, unit, title, v[0]))
                        frames[title] = v[0]
                for k, v in e.items():
                    edges.setdefault(k, []).extend(v)
            self.assertIn("b3_orch_observe", frames)
            for em in EMITTERS:
                self.assertTrue(any(t.endswith(":" + em) or t == em for t in frames), (cname, em))

            def resolve(t: str) -> list[str]:
                if t == "__indirect_call":                 # the only indirect calls on the path are the emitter's
                    return [x for x in frames if x.split(":")[-1] in EMITTERS]
                return [t]
            memo: dict = {}

            def depth(t: str, path: tuple = ()) -> int:
                if t in path:
                    raise AssertionError(f"{cname}: recursion through {t}")
                if t in memo:
                    return memo[t]
                if t not in frames:
                    name = t.split(":")[-1]
                    if name.startswith("__") and name.endswith("_chk"):
                        name = name[2:-4]                   # glibc's fortified variants (host): the function's allowance
                    if name not in LIBRARY_ALLOWANCE:
                        raise AssertionError(f"{cname}: a call to {t} with no frame and no allowance")
                    return LIBRARY_ALLOWANCE[name]
                d = frames[t] + max([depth(x, path + (t,)) for c in edges.get(t, []) for x in resolve(c)] or [0])
                memo[t] = d
                return d
            # an ESTIMATE with the library allowances assumed (not proven bounds): held to a quarter of the stack here;
            # the image's stack conclusion is image stage 5's, with the linked ARM libc, the app, the wire and the BSP
            deepest = max(depth(e) for e in ENTRY_POINTS)
            self.assertLess(deepest * 4, stack, (cname, deepest))
            self.assertGreater(deepest, frames["b3_orch_observe"], "the chain is longer than one frame")
        self.assertEqual(seen_exceptions, B2_FRAME_EXCEPTIONS, "every exception is a frame that exists")


if __name__ == "__main__":
    unittest.main()
