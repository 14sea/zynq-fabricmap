"""The image's stack assessment (b3/host/b3_image_stack.py), image stage 5, the stack unit.

Three kinds of test.

The POSITIVE ones drive the whole analysis on the FINAL linked ELF: every entry is bounded, the main path is within
its 0x2000 budget and each exception entry within its mode's stack, every indirect call resolves to a named target
set, and the newlib printf recursion is bounded by the verified source rule (with its pinned digests).

The callback-resolution NEGATIVES are discriminating and go through the path the assessment itself uses
(`_app_targets`, and `_child_binding` for an object handed to a consumer), on SYNTHETIC routines built in memory: a
callback is resolved only when the slot / field provably holds it AT THE READ or AT THE HAND-OVER. Stored and then
zeroed, skipped on a path, written by a halfword only, written under a condition, overlapped by a byte or an
unaligned word, overwritten through a frame pointer or a register index, restored from a stale copy, written by a
helper or by the consumer itself through the pointer — each is REFUSED (a Finding), never the older callback; two
callbacks reaching one slot keep BOTH.

The newlib-rule NEGATIVES alter the final image IN MEMORY, one instruction at a time (each alteration anchored on
the instruction's own text), and require that the sub-proof it breaks fails by name, that no main bound is published
and that the build evidence's stack block is then not complete: a tested constant made zero, the wrong FILE, the
wrong offset, an unknown overwrite, a bypassed guard, a second / third activation and another cycle.

No skip: the assessment runs against the built ELF.
"""
from __future__ import annotations

import copy
import sys
import unittest
from pathlib import Path
from unittest import mock

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_image_stack as isa  # noqa: E402
import b3_build_evidence as be  # noqa: E402

ELF = R / "b3/firmware/bsp/out/b3_app.elf"
CB_A = 0x2000
CB_B = 0x2100
APP = "b3/firmware/b3_app.c"
CB = [("movw", "r0, #8193"), ("movt", "r0, #0")]          # r0 = CB_A | 1 (thumb)
CBB5 = [("movw", "r5, #8449"), ("movt", "r5, #0")]        # r5 = CB_B | 1
SP = 256                                                  # every synthetic instruction's SP offset
SLOT8 = 8 - SP                                            # the frame slot [sp, #8] denotes


STACKS = (0x80000, 0x90000)                              # the synthetic images' stacks' region (all six modes)


def synth(seq, base=0x1000, sp_off=SP, more=None, library=(), stacks=STACKS):
    """A bare Image carrying hand-written routines: `seq` at `base` (named "f") and `more` {name: (base, seq)}, each
    a list of (mnem, ops) at 4-byte spacing, every instruction at SP offset `sp_off`. Two callbacks (CB_A, CB_B)
    exist as one-instruction routines. Every routine is in an application unit except the names in `library`: those
    have a label and NO instructions in the image — a routine the analysis cannot read. Direct calls and register
    calls are wired as the edges the path analysis would record. No ELF is read."""
    img = isa.Image.__new__(isa.Image)
    routines = {"f": (base, seq), "cb_a": (CB_A, [("bx", "lr")]), "cb_b": (CB_B, [("bx", "lr")])}
    routines.update(more or {})
    img.ins_at, img.funcs, img.label_at, img.func_entries = {}, {}, {}, {}
    img.sp_at, img.edges, img.local, img.own_return, img.units = {}, {}, {}, {}, []
    for name, (b, s) in routines.items():
        body, a = [], b
        if name in library:
            img.label_at[b] = name
            continue
        for mnem, ops in s:
            i = {"addr": a, "size": 4, "mnem": mnem, "ops": ops, "thumb": True}
            img.ins_at[a] = i
            body.append(i)
            a += 4
        img.funcs[b] = body
        img.label_at[b] = img.func_entries[b] = name
        img.sp_at[b] = {i["addr"]: frozenset({sp_off}) for i in body}
        img.units.append((b, 4 * len(s), APP))
        edges = []
        for i in body:
            fam = i["mnem"]
            if fam in ("blx", "bx") and i["ops"].strip() != "lr" and not isa.branch_target(i["ops"]):
                edges.append({"kind": "indirect_call", "to": None, "at": sp_off, "site": f"{i['addr']:#x}", "set": "app_function_pointers"})
            elif fam in ("bl", "blx"):
                edges.append({"kind": "call", "to": isa.branch_target(i["ops"])[0], "at": sp_off, "site": f"{i['addr']:#x}"})
        img.edges[b], img.local[b], img.own_return[b] = edges, sp_off, True
    img.site_rules = {"app_function_pointers": {"targets": [CB_A, CB_B], "rule": "synthetic"}}
    img._rsucc_cache, img._rw_cache, img._pt_eval_memo, img._pt_cache, img._pt_state = {}, {}, {}, {}, {}
    img._member_of, img.words, img.syms, img.address_taken, img.secs, img.blob = {}, {}, {}, [], [], b""
    if stacks:                                            # the linker symbols that bound the stacks (STACK_TOPS): a
        names = sorted({n for pair in isa.STACK_TOPS.values() for n in pair})   # constant address outside them is
        step = (stacks[1] - stacks[0]) // (len(names) - 1)                      # then provably not a frame's
        img.syms.update({n: (stacks[0] + k * step if k < len(names) - 1 else stacks[1], 0, "B") for k, n in enumerate(names)})
    return img, base


def br(addr, base=0x1000):
    return f"{addr:x} <f+{addr - base:#x}>"


def call(addr, name):
    return f"{addr:x} <{name}>"


def site_of(img, base, nth=-1):
    """The address of the routine's nth register call."""
    return [i for i in img.funcs[base] if i["mnem"] in ("blx", "bx") and i["ops"].strip() != "lr"][nth]["addr"]


def targets(img, base, binding=None, nth=-1):
    """What the assessment resolves the routine's register call to — its own path, `_app_targets`, settled."""
    site = site_of(img, base, nth)
    return isa.settle(img, lambda im: im._app_targets(base, site, binding or {}))


def handed(img, builder, consumer, nth=0):
    """What the consumer's register call resolves to when `builder` hands it its arguments at its nth call of it."""
    site = [i for i in img.funcs[builder] if i["mnem"] == "bl" and isa.branch_target(i["ops"])[0] == consumer][nth]["addr"]
    csite = site_of(img, consumer)
    return isa.settle(img, lambda im: im._app_targets(consumer, csite, dict(im._child_binding(builder, site, consumer, {}))))


def value(img, base, reg=None, at=None):
    """The atoms of the register the routine's last register call goes through (or of `reg` just before `at`)."""
    i = img.ins_at[at if at is not None else site_of(img, base)]
    return isa.settle(img, lambda im: im._pt_eval(base, i["addr"], reg or i["ops"].strip()))


class TheFinalImage(unittest.TestCase):
    """The whole analysis on the built ELF."""

    @classmethod
    def setUpClass(cls):
        isa._ASSESS_CACHE.clear()
        cls.r = isa.assess(ELF)

    def test_the_committed_image_is_blocked_and_no_bound_is_published(self):
        """The owner's strict ruling of 2026-10-06: the image has writes that are not placed, so nothing shows they
        miss the callback cells — the result is FINDINGS, and no entry that calls through memory gets a bound."""
        self.assertFalse(self.r["ok"])
        self.assertTrue(self.r["findings"])
        self.assertEqual(self.r["main_limit"], 0x2000)
        e = self.r["entries"]
        self.assertIsNone(e["main"]["bound"], "no main bound is published")
        self.assertNotIn("unpublished", e["main"], "nor computed: the path is refused where it reads a table's callback")
        main = [f for f in self.r["findings"] if f.startswith("main (_start): ")]
        # (the owner's ruling 4 on the frame unit) EVERY finding the walk can decide independently, each once —
        self.assertGreater(len(main), 1, "not only the first")
        self.assertEqual(len(main), len(set(main)))
        self.assertEqual(len({f.split(" [not walked")[0] for f in main}), len(main), "one line per finding, whatever it leaves unwalked")
        tables = [f for f in main if "the read-only table" in f and "may be written" in f]
        self.assertTrue(tables, "the table callbacks' reads are refused")
        # — the one the table refusal used to hide included: b3_state_hex hands its frame object to search_render,
        # whose stack-argument reads are not pinned (disclosed here, not fixed in this unit)
        hidden = [f for f in main if "b3_state_hex: the call at " in f and "that is handed the object may itself write its field" in f]
        self.assertEqual(len(hidden), 1, hidden)
        self.assertIn("[not walked, depending on this: what search_render.constprop.0's call at ", hidden[0])
        for exc in ("undefined", "svc", "prefetch_abort", "data_abort", "irq", "fiq"):
            self.assertIn(exc, e)
            self.assertIsNone(e[exc]["bound"], f"{exc}: it calls through the exception table, a word in memory")
            self.assertEqual(e[exc]["unpublished"], 24, "what the call graph alone gives, kept apart and not a bound")
            self.assertLessEqual(e[exc]["unpublished"], e[exc]["capacity"])
            why = [f for f in self.r["findings"] if f.startswith(f"{exc} (") and "no bound is published" in f]
            self.assertEqual(len(why), 1)
            for reason in ("write(s) of the image are not proved to miss those cells", "frame cell(s) are not resolved",
                           "what an exception taken between a cell's store and its read may write is not covered (synchronous paths only)"):
                self.assertIn(reason, why[0])
        w = self.r["writes"]
        self.assertGreater(w["total"]["not_placed_sites"], 0)
        self.assertEqual(w["unproved"], w["total"]["not_placed_sites"] + w["total"]["overlapping_sites"])
        for name, rec in w["routines"].items():           # every routine with a write that is not placed is a finding
            sites = sorted({x for v in rec.get("not_placed_at", {}).values() for x in v})   # naming every such site
            mine = [f for f in self.r["findings"] if f.startswith(f"{name}: ") and "write(s) not placed — " in f]
            self.assertEqual(len(mine), 1 if sites else 0, name)
            if sites:
                self.assertTrue(mine[0].endswith(": " + ", ".join(sites)), name)
                self.assertIn(f"{len(sites)} write(s) not placed", mine[0])

    def test_every_frame_cell_has_a_result_and_a_refusal_is_traceable(self):
        """The frame unit's acceptance: each candidate cell is resolved or not, and one that is not names concrete
        writes or calls — every one with its address; a call's routines are ones the inventory lists. (How many
        cells there are is the image's business: no count is fixed here.)"""
        cells = self.r["frame_cells"]
        self.assertTrue(cells)
        self.assertEqual(len({(c["routine"], c["slot"]) for c in cells}), len(cells))
        kinds = ("a store ", "a call ", "an address of this frame has left it", "a path from the routine's entry with no store",
                 "at this read the slot may hold ")
        w = self.r["writes"]["routines"]

        def listed(name):                                  # a routine with a write the inventory could not place
            return any("not_placed_at" in rec or "the stacks" in rec.get("overlapping_at", {})
                       for k, rec in w.items() if k == name or k.startswith(name + "@"))
        for c in cells:
            where = f"{c['routine']} slot {c['slot']:#x}"
            self.assertTrue(c["holds"], where)
            self.assertIsInstance(c["resolved"], bool)
            mine = [f for f in self.r["findings"] if f.startswith(f"{c['routine']}: the frame cell at slot {c['slot']:#x} ")]
            if c["resolved"]:
                self.assertEqual((c["blocked_by"], mine), ([], []), where)
                continue
            self.assertEqual(len(mine), 1, where)
            self.assertTrue(c["blocked_by"], f"{where}: unresolved with nothing named")
            for b in c["blocked_by"]:
                self.assertRegex(b["at"], r"^0x[0-9a-f]+$", where)
                self.assertTrue(b["why"].startswith(kinds), f"{where}: {b['why'][:80]}")
                self.assertIn(b["why"], mine[0], where)
                self.assertIn(b["at"], mine[0], where)
                if "routine(s) have a write that is not shown to miss a frame" in b["why"]:
                    self.assertTrue(b["under"], where)
                    for name in b["under"]:
                        self.assertTrue(listed(name), f"{where}: {name} is named under a call but the inventory lists no such write of it")
        self.assertTrue(any(c["resolved"] for c in cells) and any(not c["resolved"] for c in cells),
                        "this image has cells of both kinds")
        self.assertEqual(sum("the frame cell at slot" in f for f in self.r["findings"]), sum(not c["resolved"] for c in cells))

    def test_what_a1_placed_is_listed_by_rule_and_is_placed(self):
        """A1 (2026-10-07): every write placed only because its index is bounded is listed under its rule, counted
        once, and is in no routine's not-placed list; the image's own numbers are not fixed here."""
        w = self.r["writes"]
        n = 0
        for name, rec in w["routines"].items():
            for rule, sites in rec.get("placed_by_a1_at", {}).items():
                self.assertTrue(rule.startswith(("a register index bounded by ", "an address computed from an index bounded by ",
                                                 "a handed address computed from an index bounded by ")) or rule in (
                    "a pointer stepped by a ÷10 digit loop", "a pointer stepped by the copy loop after a ÷10 digit loop",
                    "a pointer stepped back by the copy loop after a ÷10 digit loop"), rule)
                unplaced = {x for v in rec.get("not_placed_at", {}).values() for x in v}
                for site in sites:
                    self.assertNotIn(site, unplaced, f"{name} {site}: listed as placed by A1 and as not placed")
                n += len(sites)
        self.assertEqual(w["total"]["placed_by_a1"], n)
        self.assertGreater(n, 0, "this image has writes A1 places")
        self.assertIn(f"placed by a1: {n}", self.r["rules"]["write_placement"]["targets"])

    def test_the_inventory_leaves_out_no_store(self):
        """Counted independently, off the disassembly: every store instruction the path analysis reaches, in every
        routine of the image, is in its routine's record — placed, placed at its callers, its contract's, or listed."""
        img = isa.Image(ELF)
        w = self.r["writes"]
        names = [img.name(R) for R in img._code_routines()]
        total = 0
        for R in img._code_routines():
            img.analyse(R)
            reached = img.sp_at.get(R, {})
            stores = [i["addr"] for i in img.region(R) if i["addr"] in reached
                      and i["mnem"].split(".")[0].startswith(("str", "stm", "push", "vst", "vpush"))]
            total += len(stores)
            n = img.name(R)
            rec = w["routines"].get(n if names.count(n) == 1 else f"{n}@{R:#x}", {"stores": 0})
            self.assertEqual(rec["stores"], len(stores), n)
            listed = {int(x, 16) for k, v in rec.get("not_placed_at", {}).items() if k.startswith("stores: ") for x in v}
            self.assertLessEqual(listed, set(stores), n)
            if "hand_overs" in rec:                        # each write is counted exactly once
                self.assertEqual(rec["stores"] + rec["hand_overs"],
                                 rec["placed"] + rec["at_the_callers"] + rec["by_contract"] + rec["not_placed"], n)
                self.assertEqual(bool(rec["not_placed"]), bool(rec.get("not_placed_at")), n)
        self.assertEqual(w["total"]["stores"], total)
        self.assertGreater(total, 2500)
        self.assertEqual({p["name"] for p in w["protected"]} >= {"APP_RX", "TX_IO", "REC_IO", "PULL_IO", "XExc_VectorTable", "__sf",
                                                                    "__atexit", ".init_array", ".fini_array"}, True)

    def test_the_newlib_recursion_is_bounded_by_a_verified_rule(self):
        nl = self.r["newlib"]
        self.assertEqual(nl["rule"], "newlib_bounded_sbprintf")
        self.assertEqual(nl["max_activations"], {"_vfiprintf_r": 2, "__sbprintf": 1})
        self.assertEqual(nl["binding"]["version"], "4.4.0")
        self.assertEqual(nl["binding"]["libc_sha256"], "920deffb255f7cd01f501a4eabae436f660b009331c6b61066ded2c628b42e44")
        self.assertEqual(nl["binding"]["version_header_sha256"], "bfc4b55e8665b5c4ae407e090a6aac2fb829905f04a5a7519686631eb1633fff")
        self.assertEqual(nl["source"]["tarball_sha256"], "0c166a39e1bf0951dfafcd68949fe0e4b6d3658081d6282f39aeefc6310f2f13")

    def test_every_indirect_target_set_is_named(self):
        rules = self.r["rules"]
        self.assertIn("exception_table", rules)
        self.assertEqual(sorted(rules["exception_table"]["targets"]),
                         sorted(["Xil_ExceptionNullHandler", "Xil_DataAbortHandler",
                                 "Xil_PrefetchAbortHandler", "Xil_UndefinedExceptionHandler"]))
        self.assertIn("app_function_pointers", rules)
        self.assertTrue(rules["app_function_pointers"]["targets"], "the application callbacks resolve")

    def test_what_the_bound_rests_on_is_recorded(self):
        rules = self.r["rules"]
        vm = rules["value_model"]
        for stated in ("(B2)", "(B3)"):
            self.assertIn(stated, vm["rule"])
        for gone in ("(M1)", "(M2)", "(M3)", "(B1)"):       # the owner's HOLD on 1e55967; the frame unit of 2026-10-06
            self.assertNotIn(gone, vm["rule"])
        for said in ("NO OBJECT PROVENANCE IS ASSUMED", "a callee's incoming stack-argument area is its caller's frame",
                     "SCOPE — SYNCHRONOUS PATHS ONLY", "NOT covered", "not used as proof that no handler runs",
                     "no bound is published for an entry that calls through memory"):
            self.assertIn(said, vm["rule"])
        self.assertEqual(self.r["tool"], "b3-image-stack 1.6.0")
        self.assertTrue(vm["targets"], "the library contracts the analysis relied on are named")
        self.assertLessEqual(set(vm["targets"]), set(isa.Image.LIBC_CONTRACTS))
        formats = rules["printf_formats"]["targets"]
        self.assertTrue(formats)
        proved = [f for f in formats if f["no_percent_n"] and f["formats"]]
        self.assertTrue(proved, "some printf format is proved")
        for f in formats:                                  # one that is not is SAID not to be, and is a finding: with
            if f in proved:                                # no object provenance a format pointer kept in a frame slot
                continue                                   # across a call over unplaced writes is no longer a constant
            self.assertEqual((f["format"], f["formats"], f["no_percent_n"]), ("NOT a provable constant", [], False))
            self.assertEqual(sum(x.startswith(f["call"] + ": its format is not a provable constant string free of %n")
                                 for x in self.r["findings"]), 1, f["call"])
        self.assertEqual(sum("its format is not a provable constant" in x for x in self.r["findings"]), len(formats) - len(proved))
        used = {s.split(":")[0] for s in rules["callback_contracts"]["targets"]}
        self.assertLessEqual(used, set(isa.Image.CONTRACTS))
        self.assertIn("sha_emit", used)
        tables = {s.split(":")[0] for s in rules["read_only_tables"]["targets"]}
        self.assertEqual(tables, set(), "no I/O table is proved read-only while a write of the image is not placed")
        wp = rules["write_placement"]
        self.assertIn("is not proved to miss any callback cell", wp["rule"])
        self.assertIn(f"not placed sites: {self.r['writes']['total']['not_placed_sites']}", wp["targets"])

    def test_the_image_clears_only_the_async_abort_mask(self):
        self.assertEqual(self.r["masks"]["cleared_by_the_image"], ["A"])


class ACallbackInTheRoutinesOwnFrame(unittest.TestCase):
    """`_app_targets` on a callback spilled to a local slot: resolved only when the slot provably holds it at the
    read, on every path."""

    def refused(self, seq, **kw):
        img, b = synth(seq, **kw)
        with self.assertRaises(isa.Finding) as c:
            targets(img, b)
        self.assertNotEqual(value(img, b), {("cb", CB_A)}, "the value at the call is not the callback alone")
        return str(c.exception)

    def test_a_fully_initialised_slot_resolves_to_its_callback(self):
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A])
        self.assertEqual(value(img, b), {("cb", CB_A)})

    def test_stored_and_then_zeroed_is_refused(self):
        self.assertIn("not provably the last callback", self.refused(
            CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")]))

    def test_bypassing_the_initialisation_is_refused(self):
        self.refused([("cbz", f"r2, {br(0x1010)}")] + CB + [("str", "r0, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_a_halfword_initialisation_is_refused(self):
        self.refused(CB + [("strh", "r0, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_a_conditional_store_is_not_an_initialisation(self):
        for mnem in ("strne", "streq.w"):
            with self.subTest(mnem):
                self.refused(CB + [("cmp", "r2, #0"), (mnem, "r0, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_a_conditional_overwrite_keeps_what_was_there_and_what_it_writes(self):
        img, b = synth(CB + CBB5 + [("str", "r0, [sp, #8]"), ("cmp", "r2, #0"), ("strne", "r5, [sp, #8]"),
                                    ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A, CB_B])

    def test_an_overlapping_byte_store_is_refused(self):
        for off in (8, 9, 10, 11):
            with self.subTest(off):
                self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("strb", f"r3, [sp, #{off}]"),
                                   ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_a_byte_store_next_to_the_slot_does_not_touch_it(self):
        for off in (7, 12):
            with self.subTest(off):
                img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("strb", f"r3, [sp, #{off}]"),
                                     ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
                self.assertEqual(targets(img, b), [CB_A])

    def test_an_overlapping_unaligned_word_or_wider_store_is_refused(self):
        for mnem, ops in (("str", "r3, [sp, #6]"), ("str", "r3, [sp, #10]"), ("strh", "r3, [sp, #7]"),
                          ("strd", "r3, r4, [sp, #2]"), ("vstr", "d0, [sp, #4]")):
            with self.subTest(ops):
                self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), (mnem, ops), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_an_overwrite_through_a_frame_pointer_register_is_seen(self):
        self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r7, sp"), ("mov", "r3, #0"), ("str", "r3, [r7, #8]"),
                           ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.refused(CB + [("str", "r0, [sp, #8]"), ("add", "r7, sp, #4"), ("mov", "r3, #0"), ("str", "r3, [r7, #4]"),
                           ("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    def test_a_register_indexed_or_derived_frame_store_is_refused(self):
        for seq in ([("str", "r3, [sp, r2]")],
                    [("mov", "r2, #8"), ("str", "r3, [sp, r2]")],                  # an index is never taken as an offset
                    [("mov", "r7, sp"), ("str", "r3, [r7, r2, lsl #2]")],
                    [("add", "r7, sp, r2"), ("str", "r3, [r7]")],                  # an address the model cannot place
                    [("mov", "r7, sp"), ("orr", "r7, r7, #4"), ("strb", "r3, [r7, #100]")]):
            with self.subTest(seq):
                self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0")] + seq + [("ldr", "r1, [sp, #8]"), ("blx", "r1")])

    # ---- the frame unit (the owner's ruling of 2026-10-06): no object provenance. Between the store and the read,
    # a write that is not into this frame must be SHOWN to land off every frame — the old B1 ("a pointer derived
    # from another object does not reach this frame") is gone, and each of its three uses is refused below.

    FAR = [("movw", "r6, #40960"), ("movt", "r6, #0")]            # r6 = 0xA000: a constant outside the stacks
    INSIDE = [("movw", "r6, #16"), ("movt", "r6, #8")]            # r6 = 0x80010: a constant inside the stacks' region
    PRE = CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0")]
    POST = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]

    def test_a_store_of_the_routine_that_is_not_into_its_frame_must_be_placed(self):
        """B1's first use: the routine's own store through another pointer, between the store and the read."""
        P, Q = self.PRE, self.POST
        for what, mid, why, kw in (
                ("through an unknown pointer", [("str", "r3, [r6, #8]")], "at 0x1010 a store that is not placed (through an unknown pointer)", {}),
                ("a byte at a register index from one", [("strb", "r3, [r6, r2]")], "at 0x1010 a store that is not placed", {}),
                ("through a pointer loaded from memory", self.FAR + [("ldr", "r5, [r6]"), ("str", "r3, [r5]")], "at 0x101c a store that is not placed", {}),
                ("through its own argument, in a routine nothing calls", [("str", "r3, [r1, #4]")],
                 "at 0x1010 a store that is not placed (through its own argument, and the routine is entered other than by a call", {}),
                ("at a constant inside the stacks' region", self.INSIDE + [("str", "r3, [r6]")],
                 "at 0x1018 a store at the constant range 0x80010..0x80014, inside the stacks' region", {}),
                ("at a constant index", self.FAR + [("str", "r3, [r6, r2]")], "over an extent that is not bounded", {}),
                ("at a constant, in an image that names no stacks", self.FAR + [("str", "r3, [r6]")],
                 "at 0x1018 a store at the constant range 0xa000..0xa004, in an image that names no stacks' region", {"stacks": None})):
            with self.subTest(what):
                r = self.refused(P + mid + Q, **kw)
                self.assertIn("slot -0xf8 blocked by: ", r)
                self.assertIn(why, r)
        img, b = synth(P + self.FAR + [("str", "r3, [r6]"), ("strb", "r3, [r6, #9]"), ("strd", "r2, r3, [r6, #16]")] + Q)
        self.assertEqual(targets(img, b), [CB_A], "stores at constants outside the stacks' region")
        img, b = synth(P + [("str", "r3, [sp, #12]"), ("strb", "r3, [sp, #7]"), ("str", "r3, [sp, #4]")] + Q)
        self.assertEqual(targets(img, b), [CB_A], "stores into its own frame, beside the slot")

    def test_a_store_through_an_argument_lands_where_every_caller_points(self):
        """h holds a callback in its frame and stores through its argument in between: the cell stands only when
        every call of h hands it a pointer that is placed off the frames, or an address inside that caller's frame."""
        H2 = 0x5000
        h = self.PRE + [("str", "r3, [r1, #4]")] + self.POST + [("bx", "lr")]
        ret = [("mov", "r0, #0"), ("bx", "lr")]

        def go(*leads):
            body = []
            for lead in leads:
                body += list(lead) + [("bl", call(H2, "h"))]
            img, _b = synth(body + ret, more={"h": (H2, h)})
            try:
                return isa.settle(img, lambda im: im._app_targets(H2, site_of(im, H2), {}))
            except isa.Finding as e:
                return str(e)
        far, inside = [("movw", "r1, #40960"), ("movt", "r1, #0")], [("movw", "r1, #16"), ("movt", "r1, #8")]
        self.assertEqual(go(far), [CB_A], "a constant outside the stacks")
        self.assertEqual(go([("add", "r1, sp, #16")]), [CB_A], "an address inside the caller's own frame")
        self.assertEqual(go(far, [("add", "r1, sp, #16")]), [CB_A], "both callers placed")
        for what, leads, why in (("a constant inside the stacks", (inside,), "f hands r1 to h, which writes through it at 0x1008, at the constant range 0x80014..0x80018, inside the stacks' region"),
                                 ("an unknown pointer", ([("mov", "r1, r6")],), "f hands r1 to h, which writes through it at 0x1004, that is not placed (through an unknown pointer)"),
                                 ("one caller of two unplaced", (far, [("mov", "r1, r6")]), "f hands r1 to h, which writes through it at 0x1010, that is not placed (through an unknown pointer)"),
                                 ("a frame address whose range straddles the top of the caller's frame", ([("add", "r1, sp, #250")],),
                                  "f hands r1 to h, which writes through it at 0x1004, that is not placed (through an address of its frame, over a range that leaves the frame)"),
                                 ("an address in the caller's INCOMING area — its own caller's frame, and nothing calls f", ([("add", "r1, sp, #252")],),
                                  "f hands r1 to h, which writes through it at 0x1004, that is not placed (into its incoming "
                                  "stack-argument area, and the routine is entered other than by a call")):
            with self.subTest(what):
                r = go(*leads)
                self.assertIsInstance(r, str, "resolved")
                self.assertIn("a store through its argument, and " + why, r)

    def test_every_write_under_a_call_must_be_placed(self):
        """B1's second use: a call between the store and the read. Whatever the routines it can reach write — through
        any pointer, not only one the call is handed — must be placed off the frames."""
        H2, G2, L2 = 0x5000, 0x6000, 0x7000
        ret = [("mov", "r0, #0"), ("bx", "lr")]
        zero = [("mov", f"r{n}, #0") for n in range(4)]
        far = [("movw", "r4, #40960"), ("movt", "r4, #0")]

        def go(h, more=None, lead=None, library=(), tweak=None):
            routines = {"h": (H2, h)}
            routines.update(more or {})
            img, b = synth(self.PRE + (zero if lead is None else lead) + [("bl", call(H2, "h"))] + self.POST, more=routines, library=library)
            if tweak:
                tweak(img)

            def run(im):                                   # the result, and EVERYTHING recorded against the cell
                try:
                    r = im._app_targets(b, site_of(im, b), {})
                except isa.Finding as e:
                    r = str(e)
                return r, [f"at {a:#x} {why}" for a, why in sorted(im._cache("_cellblk").get((b, SLOT8), ()))]
            return isa.settle(img, run)
        unk = [("mov", "r3, #0"), ("str", "r3, [r6]")] + ret
        ptr = [("movw", "r3, #8193"), ("movt", "r3, #0"), ("blx", "r3")] + ret     # h calls CB_A through a pointer

        def no_rule(img):
            for e in img.edges[H2]:
                if e["kind"] == "indirect_call":
                    e["set"] = "no_such_rule"
        for what, kw, why in (
                ("the callee stores through an unknown pointer", {"h": unk},
                 "a call (h) under which 1 routine(s) have a write that is not shown to miss a frame: h (1); the first, h stores at 0x5004, that is not placed (through an unknown pointer)"),
                ("a routine two calls down does", {"h": [("bl", call(G2, "g"))] + ret, "more": {"g": (G2, unk)}},
                 "a call (h) under which 1 routine(s) have a write that is not shown to miss a frame: g (1); the first, g stores at 0x6004, that is not placed"),
                ("the callee stores at a constant inside the stacks", {"h": [("movw", "r4, #16"), ("movt", "r4, #8"), ("mov", "r3, #0"), ("str", "r3, [r4]")] + ret},
                 "h (1); the first, h stores at 0x500c, at the constant range 0x80010..0x80014, inside the stacks' region"),
                ("the callee calls a routine that cannot be read", {"h": zero + [("bl", call(L2, "lib"))] + ret, "more": {"lib": (L2, [])}, "library": ("lib",)},
                 "; the first, h hands r0 to lib, which writes through it at 0x5010, that is not placed"),
                ("a callback in the pointer's CONTEXT-FREE target set does, though this pointer is the other one",
                 {"h": ptr, "more": {"cb_b": (CB_B, [("str", "r3, [r6]"), ("bx", "lr")])}},
                 "a call (h) under which 1 routine(s) have a write that is not shown to miss a frame: cb_b (1); the first, cb_b stores at 0x2100, that is not placed"),
                ("an indirect call under it has no resolved target set", {"h": ptr, "tweak": no_rule},
                 "a call (h) under which h's indirect call at 0x5008 has no resolved target set: no rule 'no_such_rule'"),
                ("the callee writes through its argument, handed an unknown pointer", {"h": [("mov", "r3, #0"), ("str", "r3, [r1, #4]")] + ret,
                                                                                      "lead": [("mov", "r1, r6"), ("mov", "r0, #0"), ("mov", "r2, #0")]},
                 "a call (h) handed r1, which the callee writes through, that is not placed (through an unknown pointer)")):
            with self.subTest(what):
                r, blocked = go(**kw)
                self.assertIsInstance(r, str, "resolved")
                self.assertIn("slot -0xf8 blocked by: at 0x10", r)
                self.assertTrue(any(why in x for x in blocked), f"{why!r} not recorded against the cell: {blocked}")
                self.assertTrue(all(x.startswith(("at 0x101c a call ", "at 0x1020 a call ")) for x in blocked), blocked)
        for what, kw in (
                ("the callee stores at a constant outside the stacks", {"h": far + [("mov", "r3, #0"), ("str", "r3, [r4]"), ("strb", "r3, [r4, #7]")] + ret}),
                ("the callee stores into its own frame", {"h": [("mov", "r3, #0"), ("str", "r3, [sp, #8]"), ("str", "r3, [sp, #4]")] + ret}),
                ("a routine two calls down writes its caller's frame through its argument",
                 {"h": [("add", "r0, sp, #16"), ("bl", call(G2, "g"))] + ret, "more": {"g": (G2, [("mov", "r3, #0"), ("str", "r3, [r0, #4]")] + ret)}}),
                ("the callee calls through a pointer whose whole target set writes nothing", {"h": ptr}),
                ("the callee writes through its argument, handed a constant outside the stacks",
                 {"h": [("mov", "r3, #0"), ("str", "r3, [r1, #4]")] + ret, "lead": [("movw", "r1, #40960"), ("movt", "r1, #0"), ("mov", "r0, #0"), ("mov", "r2, #0")]})):
            with self.subTest(what):
                self.assertEqual(go(**kw), ([CB_A], []), "resolved, and nothing recorded against the cell")

    def test_the_incoming_stack_words_are_the_caller_s_frame(self):
        """B1's third use, and the owner's condition: a callee's incoming stack-argument area is not its own frame. A
        write there is held against the CALLER's slots; a range that leaves the frame it starts in is not placed."""
        H2 = 0x5000
        ret = [("mov", "r0, #0"), ("bx", "lr")]
        zero = [("mov", f"r{n}, #0") for n in range(4)]

        def go(h):
            img, b = synth(self.PRE + zero + [("bl", call(H2, "h"))] + self.POST, more={"h": (H2, h)})
            try:
                return targets(img, b)
            except isa.Finding as e:
                return str(e)
        r = go([("mov", "r3, #0"), ("str", "r3, [sp, #264]")] + ret)          # its incoming word 8 = the caller's [sp, #8]
        self.assertIsInstance(r, str, "resolved")
        self.assertIn("a call that may write the slot through a pointer it is handed, or its incoming stack words", r)
        self.assertEqual(go([("mov", "r3, #0"), ("str", "r3, [sp, #268]")] + ret), [CB_A], "its incoming word 12: beside the slot")
        r = go([("mov", "r3, #0"), ("mov", "r2, #0"), ("strd", "r2, r3, [sp, #252]")] + ret)   # [-4, 4): out of its own frame
        self.assertIsInstance(r, str, "resolved")
        self.assertIn("that is not placed (through an address of its frame, over a range that leaves the frame)", r)

        def inventory(h):
            img, _b = synth(zero + [("bl", call(H2, "h"))] + ret, more={"h": (H2, h)})
            return isa.settle(img, lambda im: im.write_inventory())["routines"]
        w = inventory([("mov", "r3, #0"), ("str", "r3, [sp, #264]")] + ret)
        self.assertEqual((w["h"]["stores"], w["h"]["at_the_callers"], w["h"]["placed"]), (1, 1, 0), "not h's own frame: placed at its caller")
        self.assertEqual((w["f"]["hand_overs"], w["f"]["placed"], w["f"]["not_placed"]), (1, 1, 0), "in f's own frame, where f's SP is at the call")
        w = inventory([("mov", "r3, #0"), ("str", "r3, [sp, #512]")] + ret)    # h's incoming word 256 = f's entry SP + 0
        self.assertEqual(w["h"]["at_the_callers"], 1)
        self.assertEqual(w["f"]["not_placed"], 1, "f's own incoming area, and nothing calls f")
        self.assertIn("into its incoming stack-argument area, and the routine is entered other than by a call", str(w["f"]["not_placed_at"]))
        w = inventory([("mov", "r3, #0"), ("mov", "r2, #0"), ("strd", "r2, r3, [sp, #252]")] + ret)
        self.assertEqual(w["h"]["not_placed_at"], {"stores: through an address of its frame, over a range that leaves the frame": ["0x5008"]})

    def test_two_branches_with_different_callbacks_keep_both(self):
        img, b = synth([("cbz", f"r2, {br(0x1014)}"),
                        ("movw", "r0, #8193"), ("movt", "r0, #0"), ("str", "r0, [sp, #8]"), ("b", br(0x1020)),
                        ("movw", "r0, #8449"), ("movt", "r0, #0"), ("str", "r0, [sp, #8]"),
                        ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A, CB_B])

    def test_a_reload_and_store_back_resolves(self):
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("ldr", "r4, [sp, #8]"), ("str", "r4, [sp, #8]"),
                             ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A])

    def test_a_stale_copy_stored_back_is_the_old_value_not_the_newer_store(self):
        # r4 = the slot (CB_A); the slot is overwritten with CB_B; r4 is stored back: the slot holds CB_A again
        img, b = synth(CB + CBB5 + [("str", "r0, [sp, #8]"), ("ldr", "r4, [sp, #8]"), ("str", "r5, [sp, #8]"),
                                    ("str", "r4, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A])

    def test_a_spill_round_a_loop_resolves(self):
        # the callback is reloaded and spilled again on every iteration (the emit-render shape)
        img, b = synth(CB + [("str", "r0, [sp, #8]"),
                             ("ldr", "r4, [sp, #8]"), ("str", "r4, [sp, #8]"), ("cbnz", f"r2, {br(0x100c)}"),
                             ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A])

    def test_a_cycle_is_solved_not_cut(self):
        # r4 = CB_A; loop { r5 = r4; maybe r5 = CB_B; r4 = r5 }: r4 is {A, B} everywhere in the loop, whatever
        # point is asked first (a cycle cut to "nothing" and memoised left the inner point with A alone)
        seq = [("movw", "r4, #8193"), ("movt", "r4, #0"), ("movw", "r6, #8449"), ("movt", "r6, #0"),
               ("mov", "r5, r4"), ("cbz", f"r2, {br(0x101c)}"), ("mov", "r5, r6"), ("mov", "r4, r5"),
               ("cbnz", f"r3, {br(0x1010)}"), ("blx", "r4")]
        both = {("cb", CB_A), ("cb", CB_B)}
        img, b = synth(seq)
        self.assertEqual(value(img, b), both)
        self.assertEqual(value(img, b, "r4", at=0x1010), both, "the point inside the cycle, asked second")
        img, b = synth(seq)
        self.assertEqual(value(img, b, "r4", at=0x1010), both, "the point inside the cycle, asked first")
        self.assertEqual(targets(img, b), [CB_A, CB_B])

    def test_a_pointer_stepped_round_a_loop_reaches_the_slot(self):
        # r4 starts at [sp, #4] and steps by 4 while it writes: only iterating the cycle carries it on to [sp, #40]
        # (a cycle cut after a round or two sees [sp, #4] and [sp, #8] alone)
        loop = [("mov", "r3, #0"), ("str", "r3, [r4]"), ("add", "r4, r4, #4"), ("cbnz", f"r2, {br(0x1010)}")]
        self.refused(CB + [("str", "r0, [sp, #40]"), ("add", "r4, sp, #4")] + loop + [("ldr", "r1, [sp, #40]"), ("blx", "r1")])
        # and its value there is every place it can reach — widened, not its first positions
        img, b = synth(CB + [("str", "r0, [sp, #40]"), ("add", "r4, sp, #4")] + loop + [("ldr", "r1, [sp, #40]"), ("blx", "r1")])
        raw = isa.settle(img, lambda im: im._raw_reg(b, 0x1014, "r4"))
        self.assertIn(("der", "frame"), raw, f"the stepped pointer at the store: {sorted(raw)}")
        # (no stepping-down control: once widened, a stepped frame pointer has no direction and is refused either way)

    def test_a_double_word_load_reads_each_registers_own_slot(self):
        seq = CB + [("str", "r0, [sp, #12]"), ("mov", "r3, #7"), ("str", "r3, [sp, #8]"), ("ldrd", "r2, r3, [sp, #8]")]
        img, b = synth(seq + [("blx", "r3")])
        self.assertEqual(targets(img, b), [CB_A])
        self.refused(seq + [("blx", "r2")])

    def test_a_call_between_the_store_and_the_read(self):
        lib = {"lib": (0x3000, [("bx", "lr")])}
        pre = CB + [("str", "r0, [sp, #8]")]
        post = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        zero = [("mov", "r0, #0"), ("mov", "r1, #0"), ("mov", "r2, #0"), ("mov", "r3, #0")]
        # a routine the image holds, handed no pointer and writing nothing: the slot is untouched
        img, b = synth(pre + zero + [("bl", call(0x3000, "lib"))] + post, more=lib)
        self.assertEqual(targets(img, b), [CB_A])
        # one the image does not hold may write its own stack arguments — of an arity nobody knows, so any word
        # above the caller's SP, the slot included — even when it is handed no pointer
        self.refused(pre + zero + [("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))
        # and handed ANY address of the frame it may write the slot — below it, at it or above it
        for reg in ("r0", "r3"):
            for off in (4, 8, 12, 200):
                with self.subTest(reg=reg, off=off):
                    regs = [("mov", f"r{n}, #0") for n in range(4) if f"r{n}" != reg]
                    self.refused(pre + regs + [("add", f"{reg}, sp, #{off}"), ("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))

    def test_a_frame_address_in_a_stack_argument_the_callee_reads(self):
        # the address goes into the outgoing stack word k; the callee reads its incoming word k (entry SP + k) and
        # writes through it — whatever k is: the words handed are the ones the callee's code reads, not a fixed 64
        zero = [("mov", f"r{n}, #0") for n in range(4)]
        post = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]

        def run(k, body, stored=("add", "r4, sp, #8")):
            img, b = synth(CB + [("str", "r0, [sp, #8]"), stored, ("str", f"r4, [sp, #{k}]")] + zero +
                           [("bl", call(0x3000, "h"))] + post, more={"h": (0x3000, body)})
            try:
                return targets(img, b)
            except isa.Finding as e:
                return str(e)
        for k in (0, 4, 60, 64, 68, 200):
            writer = [("ldr", f"r4, [sp, #{SP + k}]"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")]
            reader = [("ldr", f"r4, [sp, #{SP + k}]"), ("ldr", "r3, [r4]"), ("bx", "lr")]
            with self.subTest(k=k):
                self.assertIsInstance(run(k, writer), str, "a callee writing through its stack argument")
                self.assertEqual(run(k, reader), [CB_A], "one that only reads through it")
                self.assertEqual(run(k, writer, stored=("mov", "r4, #5")), [CB_A], "a stack word that is no address")
        # a callee that walks its incoming area at an index (a va_list): every word above SP is handed to it
        walker = [("add", "r4, sp, #256"), ("ldr", "r5, [r4, r2, lsl #2]"), ("mov", "r3, #0"), ("str", "r3, [r5]"), ("bx", "lr")]
        self.assertIsInstance(run(40, walker), str)

    def test_a_frame_address_parked_outside_the_frame(self):
        W = 0x5000
        writer = {"w": (W, [("mov", "r3, #0"), ("str", "r3, [r0]"), ("bx", "lr")])}
        post = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        pre = CB + [("str", "r0, [sp, #8]"), ("add", "r4, sp, #8")]
        # stored in outside memory, read back, handed to a writer
        why = self.refused(pre + [("str", "r4, [r6]"), ("ldr", "r0, [r6]"), ("bl", call(W, "w"))] + post, more=writer)
        # … and stored there with nothing else: the frame is loose all the same
        self.refused(pre + [("str", "r4, [r6, #12]")] + post)
        self.refused(pre + [("stm", "r6, {r4, r5}")] + post)
        self.assertIsInstance(why, str)
        # a value that is NO frame address stored there, read back and handed to the writer: once taken for harmless
        # (B1: "not this frame's pointer") — now the store and the writer's target are simply not placed
        r = self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r4, #9"), ("str", "r4, [r6]"), ("ldr", "r0, [r6]"),
                               ("bl", call(W, "w"))] + post, more=writer)
        self.assertIn("at 0x1010 a store that is not placed (through an unknown pointer)", r)
        self.assertIn("at 0x1018 a call (w) handed r0, which the callee writes through, that is not placed", r)
        # the control: the value stored at a constant outside the stacks, the writer handed such a constant
        far = [("movw", "r6, #40960"), ("movt", "r6, #0")]
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r4, #9")] + far + [("str", "r4, [r6]"), ("add", "r0, r6, #16"),
                             ("bl", call(W, "w"))] + post, more=writer)
        self.assertEqual(targets(img, b), [CB_A])


    def test_a_derived_frame_address_handed_to_a_callee_that_keeps_what_it_loads(self):
        """The frame-leak check met a frame address the model does not pin (sp + a register: derived from the frame,
        no slot) handed to a callee that keeps a word it loads at a KNOWN offset from it — and added that offset to
        the atom's tag. Through the assessment's own path it is a refusal: any slot may hold a frame address."""
        K = 0x5000
        keeper = {"k": (K, [("ldr", "r2, [r0, #4]"), ("movw", "r6, #40960"), ("movt", "r6, #0"), ("str", "r2, [r6]"),
                            ("mov", "r0, #0"), ("bx", "lr")])}       # (keeps it at a constant outside the stacks)
        post = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        park = [("add", "r3, sp, #20"), ("str", "r3, [sp, #16]")]            # a frame address parked in the frame
        derived = CB + [("str", "r0, [sp, #8]")] + park + [("add", "r0, sp, r4"), ("bl", call(K, "k"))] + post
        why = self.refused(derived, more=keeper)
        self.assertIsInstance(why, str)

        def leak(seq):                                     # the leak fact itself, by name: other layers refuse it too
            img, b = synth(seq, more=keeper)
            return isa.settle(img, lambda im: (im._frame_leaks(b), im._cache("_leaks").get("f")))
        self.assertEqual(leak(derived), (True, "handed at 0x1018 (0): the callee may keep a frame address it loads from it"))
        self.assertEqual(leak(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #9"), ("str", "r3, [sp, #16]"), ("add", "r0, sp, #12"),
                                    ("bl", call(K, "k"))] + post), (False, None))
        # the controls: the same callee handed a PINNED frame address — keeping the frame address parked at +4 …
        self.refused(CB + [("str", "r0, [sp, #8]")] + park + [("add", "r0, sp, #12"), ("bl", call(K, "k"))] + post, more=keeper)
        # … and keeping a word that is no address: nothing leaks, the callback stands
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #9"), ("str", "r3, [sp, #16]"), ("add", "r0, sp, #12"),
                             ("bl", call(K, "k"))] + post, more=keeper)
        self.assertEqual(targets(img, b), [CB_A])


CONSUMER = [("ldr", "r3, [r0]"), ("blx", "r3"), ("bx", "lr")]          # calls the first field of the object in r0
C = 0x4000


class ACallbackInAnObjectHandedToAConsumer(unittest.TestCase):
    """The object's field is evaluated in the routine that BUILT it, at the call that hands it over."""

    def build(self, seq, consumer=CONSUMER, more=None, library=()):
        routines = {"c": (C, consumer)}
        routines.update(more or {})
        return synth(seq, more=routines, library=library)

    def refused(self, seq, nth=0, **kw):
        img, b = self.build(seq, **kw)
        with self.assertRaises(isa.Finding) as c:
            handed(img, b, C, nth)
        return str(c.exception)

    HAND = [("add", "r0, sp, #8"), ("bl", call(C, "c"))]

    def test_an_initialised_field_resolves(self):
        img, b = self.build(CB + [("str", "r0, [sp, #8]")] + self.HAND + [("bx", "lr")])
        self.assertEqual(handed(img, b, C), [CB_A])

    def test_a_field_zeroed_before_the_hand_over_is_refused(self):
        self.assertIn("not provably initialised", self.refused(
            CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [sp, #8]")] + self.HAND + [("bx", "lr")]))

    def test_a_field_whose_initialisation_a_path_skips_is_refused(self):
        self.refused([("cbz", f"r2, {br(0x1010)}")] + CB + [("str", "r0, [sp, #8]")] + self.HAND + [("bx", "lr")])

    def test_a_field_written_by_a_halfword_or_under_a_condition_is_refused(self):
        self.refused(CB + [("strh", "r0, [sp, #8]")] + self.HAND + [("bx", "lr")])
        self.refused(CB + [("cmp", "r2, #0"), ("strne", "r0, [sp, #8]")] + self.HAND + [("bx", "lr")])

    def test_a_field_partly_overwritten_before_the_hand_over_is_refused(self):
        self.refused(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("strb", "r3, [sp, #9]")] + self.HAND + [("bx", "lr")])

    def test_each_hand_over_sees_the_field_as_it_is_then(self):
        # the field holds CB_A at the first call and CB_B at the second: neither sees the other's
        img, b = self.build(CB + CBB5 + [("str", "r0, [sp, #8]")] + self.HAND +
                            [("str", "r5, [sp, #8]")] + self.HAND + [("bx", "lr")])
        self.assertEqual(handed(img, b, C, 0), [CB_A])
        self.assertEqual(handed(img, b, C, 1), [CB_B])

    def test_a_field_zeroed_after_the_first_hand_over_is_refused_at_the_second(self):
        seq = CB + [("str", "r0, [sp, #8]")] + self.HAND + [("mov", "r3, #0"), ("str", "r3, [sp, #8]")] + self.HAND + [("bx", "lr")]
        img, b = self.build(seq)
        self.assertEqual(handed(img, b, C, 0), [CB_A])
        self.refused(seq, nth=1)

    def test_a_helper_that_writes_the_field_through_the_pointer_is_seen(self):
        H = 0x5000
        hand_helper = [("add", "r0, sp, #8"), ("bl", call(H, "h"))]
        seq = CB + [("str", "r0, [sp, #8]")] + hand_helper + self.HAND + [("bx", "lr")]
        for name, body in (("a word at the field", [("mov", "r3, #0"), ("str", "r3, [r0]"), ("bx", "lr")]),
                           ("a byte inside it", [("mov", "r3, #0"), ("strb", "r3, [r0, #3]"), ("bx", "lr")]),
                           ("through a copy", [("mov", "r4, r0"), ("mov", "r3, #0"), ("str", "r3, [r4, #0]"), ("bx", "lr")]),
                           ("at an index", [("mov", "r3, #0"), ("str", "r3, [r0, r1]"), ("bx", "lr")]),
                           ("through a stepped pointer", [("add", "r4, r0, #8"), ("sub", "r4, r4, #8"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")]),
                           ("through arithmetic", [("orr", "r4, r0, #0"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])):
            with self.subTest(name):
                self.refused(seq, more={"h": (H, body)})
        # a helper that writes OTHER bytes of the object, or nothing, leaves the field as it was
        for name, body in (("the next word", [("mov", "r3, #0"), ("str", "r3, [r0, #4]"), ("bx", "lr")]),
                           ("nothing", [("ldr", "r3, [r0]"), ("bx", "lr")])):
            with self.subTest(name):
                img, b = self.build(seq, more={"h": (H, body)})
                self.assertEqual(handed(img, b, C), [CB_A])

    def test_a_helper_that_hands_the_pointer_on_to_a_writer_is_seen(self):
        H, W = 0x5000, 0x6000
        seq = CB + [("str", "r0, [sp, #8]"), ("add", "r0, sp, #8"), ("bl", call(H, "h"))] + self.HAND + [("bx", "lr")]
        writer = {"w": (W, [("mov", "r3, #0"), ("str", "r3, [r1]"), ("bx", "lr")])}
        self.refused(seq, more=dict(writer, h=(H, [("mov", "r1, r0"), ("bl", call(W, "w")), ("bx", "lr")])))
        # … and one that hands it to a prebuilt routine the analysis cannot read
        self.refused(seq, more={"h": (H, [("bl", call(0x3000, "lib")), ("bx", "lr")]), "lib": (0x3000, [("bx", "lr")])}, library=("lib",))

    def test_a_helper_handed_a_pointer_behind_the_field_that_writes_backwards(self):
        H = 0x5000
        seq = CB + [("str", "r0, [sp, #8]"), ("add", "r0, sp, #16"), ("bl", call(H, "h"))] + self.HAND + [("bx", "lr")]
        for name, body in (("a negative immediate", [("mov", "r3, #0"), ("str", "r3, [r0, #-8]"), ("bx", "lr")]),
                           ("a stepped-back pointer", [("sub", "r4, r0, #8"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")]),
                           ("a pre-decrement", [("mov", "r3, #0"), ("str", "r3, [r0, #-8]!"), ("bx", "lr")]),
                           ("a negative index", [("mov", "r3, #0"), ("str", "r3, [r0, -r1]"), ("bx", "lr")]),
                           ("an index", [("mov", "r3, #0"), ("strb", "r3, [r0, r1]"), ("bx", "lr")])):
            with self.subTest(name):
                self.refused(seq, more={"h": (H, body)})
        img, b = self.build(seq, more={"h": (H, [("mov", "r3, #0"), ("str", "r3, [r0, #-4]"), ("bx", "lr")])})
        self.assertEqual(handed(img, b, C), [CB_A], "the word between the field and the pointer is not the field")

    def test_a_field_pointer_in_a_fifth_stack_argument(self):
        H = 0x5000
        pre = CB + [("str", "r0, [sp, #8]"), ("add", "r4, sp, #8"), ("str", "r4, [sp, #0]")] + [("mov", f"r{n}, #0") for n in range(4)]
        seq = pre + [("bl", call(H, "h"))] + self.HAND + [("bx", "lr")]
        # a readable callee that stores through its first stack argument (SP offset 256 at its entry: [sp, #256])
        self.refused(seq, more={"h": (H, [("ldr", "r4, [sp, #256]"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])})
        img, b = self.build(seq, more={"h": (H, [("ldr", "r4, [sp, #256]"), ("ldr", "r3, [r4]"), ("bx", "lr")])})
        self.assertEqual(handed(img, b, C), [CB_A], "a callee that only reads through it")
        # an unknown callee
        self.refused(seq, more={"h": (H, [("bx", "lr")])}, library=("h",))

    def test_a_pointer_reached_through_the_object_or_kept_by_a_callee(self):
        H, W = 0x5000, 0x6000
        # the builder puts &field in a second object and hands THAT to a helper which loads it and writes through it
        seq = CB + [("str", "r0, [sp, #8]"), ("add", "r4, sp, #8"), ("str", "r4, [sp, #32]"), ("add", "r0, sp, #32"),
                    ("bl", call(H, "h"))] + self.HAND + [("bx", "lr")]
        self.refused(seq, more={"h": (H, [("ldr", "r4, [r0]"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])})
        self.refused(seq, more={"h": (H, [("ldr", "r0, [r0]"), ("bl", call(W, "w")), ("bx", "lr")]),
                                "w": (W, [("mov", "r3, #0"), ("str", "r3, [r0]"), ("bx", "lr")])})
        img, b = self.build(seq, more={"h": (H, [("ldr", "r4, [r0]"), ("ldr", "r3, [r4]"), ("bx", "lr")])})
        self.assertEqual(handed(img, b, C), [CB_A], "a helper that only reads through the inner pointer")
        # a helper that writes through ANOTHER word of the object: once taken for harmless (B1) — the pointer it
        # loads is not placed, so nothing shows where it writes
        r = self.refused(seq, more={"h": (H, [("ldr", "r4, [r0, #4]"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])})
        self.assertIn("a call (h) under which 1 routine(s) have a write that is not shown to miss a frame: h (1); the first, "
                      "h stores at 0x5008, that is not placed (through a pointer loaded from memory)", r)
        img, b = self.build(seq, more={"h": (H, [("movw", "r4, #40960"), ("movt", "r4, #0"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])})
        self.assertEqual(handed(img, b, C), [CB_A], "a helper that writes at a constant outside the stacks")
        # a helper that keeps the pointer it is handed (stores it through another pointer): the frame is loose
        keep = CB + [("str", "r0, [sp, #8]"), ("add", "r0, sp, #8"), ("bl", call(H, "h"))] + self.HAND + [("bx", "lr")]
        self.refused(keep, more={"h": (H, [("str", "r0, [r1]"), ("bx", "lr")])})
        self.refused(keep, more={"h": (H, [("add", "r4, r0, #4"), ("str", "r4, [r1, #8]"), ("bx", "lr")])})

    def test_a_printf_format_that_may_write_through_an_argument(self):
        SN, FMT = 0x7000, 0x9000

        def run(fmt, how=None, stack=False):
            lead = [("movw", "r2, #36864"), ("movt", "r2, #0")] if how is None else how
            hand = [("add", "r4, sp, #8"), ("str", "r4, [sp, #0]"), ("mov", "r3, #0")] if stack else [("add", "r3, sp, #8")]
            seq = CB + [("str", "r0, [sp, #8]")] + lead + hand + [("add", "r0, sp, #64"), ("mov", "r1, #16"),
                                                                  ("bl", call(SN, "snprintf"))] + self.HAND + [("bx", "lr")]
            img, b = self.build(seq, more={"snprintf": (SN, [("bx", "lr")])}, library=("snprintf",))
            img._member_of[SN] = "libc.a(libc_a-snprintf.o)"
            img._cstring = lambda a: {FMT: fmt}.get(a)
            return handed(img, b, C)
        for stack in (False, True):
            with self.subTest(stack=stack):
                self.assertEqual(run("%s %d\n", stack=stack), [CB_A], "a format with no %n only reads its arguments")
                for fmt in ("%n", "%d%n", "x %hhn", "%-5ln", "%*n", "%", "%!"):
                    with self.subTest(fmt):
                        with self.assertRaises(isa.Finding):
                            run(fmt, stack=stack)
                with self.assertRaises(isa.Finding):
                    run("%d", how=[("ldr", "r2, [r6]")], stack=stack)       # a format that is not a constant
                with self.assertRaises(isa.Finding):
                    run(None, stack=stack)                                  # a constant that is not a read-only string

    def test_the_format_reader(self):
        for fmt, writes in (("", False), ("plain", False), ("%d %5.2f %-8s %llu %% %zx %c", False), ("100%%n", False),
                            ("%n", True), ("%%%n", True), ("%08.3ln", True), ("%hhn", True), ("%*.*n", True),
                            ("trailing %", True), ("%5", True), ("%.", True), ("%l", True)):
            self.assertEqual(isa.Image.format_writes(fmt), writes, fmt)

    def test_a_consumer_that_writes_the_field_itself_is_refused(self):
        self.assertIn("may itself write its field", self.refused(
            CB + [("str", "r0, [sp, #8]")] + self.HAND + [("bx", "lr")],
            consumer=[("mov", "r2, #0"), ("str", "r2, [r0]"), ("ldr", "r3, [r0]"), ("blx", "r3"), ("bx", "lr")]))

    def test_a_callback_forwarded_into_the_field_resolves_in_the_builders_binding(self):
        # the builder stores its OWN argument r1 in the field; the binding it was called with names the callback
        img, b = self.build([("str", "r1, [sp, #8]")] + self.HAND + [("bx", "lr")])
        site = [i for i in img.funcs[b] if i["mnem"] == "bl"][0]["addr"]
        outer = {1: ("cbs", frozenset({CB_B}))}
        csite = site_of(img, C)
        self.assertEqual(isa.settle(img, lambda im: im._app_targets(C, csite, dict(im._child_binding(b, site, C, outer)))), [CB_B])
        with self.assertRaises(isa.Finding):                                     # the argument is not bound: refused
            isa.settle(img, lambda im: im._app_targets(C, csite, dict(im._child_binding(b, site, C, {}))))


class TheBytesAStoreWrites(unittest.TestCase):
    """`_store_effect`: a store is the definition of a word only when it writes exactly that word, unconditionally."""

    def test_by_offset_width_and_condition(self):
        img, b = synth([("str", "r0, [sp, #8]"), ("strh", "r1, [sp, #16]"), ("strd", "r2, r3, [sp, #24]"),
                        ("strne", "r0, [sp, #32]"), ("strb", "r1, [sp, #41]"), ("str", "r1, [r5, r6]"), ("bx", "lr")], sp_off=0)
        eff = lambda k, slot: img._store_effect(b, b + 4 * k, slot)
        self.assertEqual(eff(0, 8), ("exact", "r0", False))
        self.assertIsNone(eff(0, 12), "a different word")
        self.assertIsNone(eff(0, 4))
        self.assertEqual(eff(0, 6)[0], "may", "an overlap that does not coincide")
        self.assertEqual(eff(1, 16)[0], "may", "a halfword does not define a word")
        self.assertEqual(eff(2, 24), ("exact", "r2", False))
        self.assertEqual(eff(2, 28), ("exact", "r3", False))
        self.assertEqual(eff(2, 26)[0], "may")
        self.assertEqual(eff(3, 32), ("exact", "r0", True), "a conditional store is flagged")
        self.assertEqual(eff(4, 40)[0], "may", "one byte inside the word")
        self.assertIsNone(eff(4, 44))
        self.assertIsNone(eff(5, 8), "a base that is not this frame")

    def test_a_multi_register_store_maps_each_slot(self):
        img, b = synth([("stm", "sp, {r2, r3, r4}"), ("push", "{r4, lr}"), ("bx", "lr")], sp_off=0)
        self.assertEqual([img._store_effect(b, b, s) for s in (0, 4, 8)],
                         [("exact", "r2", False), ("exact", "r3", False), ("exact", "r4", False)])
        self.assertIsNone(img._store_effect(b, b, 12))
        self.assertEqual([img._store_effect(b, b + 4, s) for s in (-8, -4)], [("exact", "r4", False), ("exact", "lr", False)])

    def test_every_conditional_family_is_conditional(self):
        img, _b = synth([("bx", "lr")])
        for mnem, cond in (("str", False), ("strne", True), ("strbne", True), ("strdeq", True), ("strhpl.w", True),
                           ("orrne", True), ("movs", False), ("bls", True), ("bics", False), ("teq", False), ("ldrhmi", True)):
            self.assertEqual(img._cond({"mnem": mnem}), cond, mnem)


class TheFlagSetters(unittest.TestCase):
    """`sets_flags`: a flag-setting mnemonic that happens to END in a condition's letters (lsls, movs, bics, adcs,
    sbcs, muls) sets the flags — read as `lsl` + ls it left the path walk following a stale decision, and the code
    after it (in the final image: part of __swsetup_r with its call to _free_r) was never walked."""

    def test_by_mnemonic(self):
        for m, want in (("lsls", True), ("movs", True), ("bics", True), ("adcs", True), ("sbcs", True), ("muls", True),
                        ("subs", True), ("negs", True), ("ands", True), ("cmpne", True), ("teq", True), ("bl", True),
                        ("blls", True), ("lsls.w", True), ("mls", False), ("movls", False), ("bls", False),
                        ("addcs", False), ("biccs", False), ("orrpl", False), ("ldrmi", False), ("it", False),
                        ("strhpl", False), ("lsl", False), ("mov", False)):
            self.assertEqual(isa.sets_flags({"mnem": m, "ops": "r0, r1"}), want, m)

    def test_the_final_image_walks_the_code_after_a_flag_setting_shift(self):
        img = isa.Image(ELF)
        W = img.syms["__swsetup_r"][0] & ~1
        img.analyse(W)
        missed = [f"{i['addr']:#x}" for i in img.region(W) if i["mnem"] != ".data" and i["addr"] not in img.sp_at[W]]
        self.assertEqual(missed, [], "every instruction of __swsetup_r is on a walked path")
        self.assertIn("_free_r", {img.name(e["to"]) for e in img.edges[W] if e["to"] is not None})


H = 0x5000                                                # the contracted helper's entry


class TheNamedContracts(unittest.TestCase):
    """A named contract stands for a routine's code: what it writes through each argument it is handed (an extent
    from the pointer), that it keeps nothing, what it returns. It is honoured only while bound — its unit, the unit's
    source digest, its code closure's digest, and the routine's own instructions writing no more, at a pinned offset,
    than it says nor storing an argument pointer outside its frame. The builder below stores CB_A at [sp, #8], hands
    the helper a frame address, reads [sp, #8] back and calls it: the callback is resolved only when the contract,
    evaluated at that call, leaves bytes 8..12 alone."""

    BODY = [("mov", "r3, #0"), ("str", "r3, [r0]"), ("bx", "lr")]          # writes [p, p + 4)

    def run_with(self, contract, hand, body=None, code=None, source="S", more_regs=()):
        """`hand`: the instructions that set up the helper's arguments. Returns the resolved targets, or the
        Finding's text."""
        seq = CB + [("str", "r0, [sp, #8]")] + list(more_regs) + list(hand) + [("bl", call(H, "h")), ("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        img, b = synth(seq, more={"h": (H, body or self.BODY)})
        c = dict({"unit": APP, "arity": 1, "returns": "int", "source": "synthetic"}, **contract)
        digest = code if code is not None else img._code_digest(H)
        with mock.patch.dict(isa.Image.CONTRACTS, {"h": c}, clear=True), \
                mock.patch.dict(isa.Image.CONTRACT_SOURCES, {APP: "S"}, clear=True), \
                mock.patch.dict(isa.Image.CONTRACT_CODE, {"h": digest}, clear=True), \
                mock.patch.object(isa.Image, "_unit_sha", return_value=source):
            try:
                return targets(img, b)
            except isa.Finding as e:
                return str(e)

    def refused(self, *a, why=None, **k):
        r = self.run_with(*a, **k)
        self.assertIsInstance(r, str, f"resolved {r}: the contract should have been refused here")
        if why:
            self.assertIn(why, r)
        return r

    # -- the positive controls: a legal write that does not reach the field
    def test_a_bounded_write_elsewhere_in_the_frame_leaves_the_callback(self):
        self.assertEqual(self.run_with({"writes": {0: 4}}, [("add", "r0, sp, #12")]), [CB_A])
        self.assertEqual(self.run_with({"writes": {0: 4}}, [("add", "r0, sp, #4")]), [CB_A], "[4, 8): just below")
        self.assertEqual(self.run_with({"arity": 2, "writes": {0: 4}}, [("add", "r0, sp, #12"), ("add", "r1, sp, #8")]),
                         [CB_A], "a frame address in a position the contract says it does not write")
        self.assertEqual(self.run_with({"writes": {0: 4}}, [("add", "r0, sp, #12"), ("add", "r1, sp, #8")]),
                         [CB_A], "a frame address in a register beyond its arity")

    # -- the write range made wider than the gap
    def test_an_extent_that_reaches_the_field(self):
        self.refused({"writes": {0: 8}}, [("add", "r0, sp, #4")], body=[("bx", "lr")])
        self.refused({"writes": {0: 1}}, [("add", "r0, sp, #11")], body=[("bx", "lr")])
        self.refused({"writes": {0: "STR"}}, [("add", "r0, sp, #4")], body=[("bx", "lr")])

    def test_code_that_writes_more_than_its_contract(self):
        self.refused({"writes": {0: 4}}, [("add", "r0, sp, #12")],
                     body=[("mov", "r3, #0"), ("str", "r3, [r0, #4]"), ("bx", "lr")], why="but its code writes")
        self.refused({"writes": {}}, [("add", "r0, sp, #12")], why="but its code writes")

    def test_a_contract_not_bound_to_this_code_or_source(self):
        self.refused({"writes": {0: 4}}, [("add", "r0, sp, #12")], code="0" * 64, why="bound to its code closure")
        self.refused({"writes": {0: 4}}, [("add", "r0, sp, #12")], source="T", why="which is now")
        with mock.patch.object(isa.Image, "unit_of", return_value="b3/firmware/b3_record.c"):
            self.refused({"writes": {0: 4}}, [("add", "r0, sp, #12")], why="this is")

    # -- a negative offset
    def test_a_pointer_behind_the_field(self):
        self.refused({"writes": {0: 8}}, [("add", "r0, sp, #6")], body=[("bx", "lr")])

    def test_code_that_writes_below_its_pointer(self):
        self.refused({"writes": {0: 4}}, [("add", "r0, sp, #12")],
                     body=[("mov", "r3, #0"), ("str", "r3, [r0, #-4]"), ("bx", "lr")], why="but its code writes")

    # -- the length precondition
    def test_an_extent_given_by_another_argument(self):
        c = {"arity": 2, "writes": {0: ("arg", 1)}}
        self.assertEqual(self.run_with(c, [("add", "r0, sp, #12"), ("mov", "r1, #64")], body=[("bx", "lr")]), [CB_A])
        self.assertEqual(self.run_with(c, [("add", "r0, sp, #0"), ("mov", "r1, #8")], body=[("bx", "lr")]), [CB_A],
                         "[0, 8): up to the field")
        self.refused(c, [("add", "r0, sp, #0"), ("mov", "r1, #9")], body=[("bx", "lr")])
        self.refused(c, [("add", "r0, sp, #0"), ("ldr", "r1, [r6]")], body=[("bx", "lr")])   # not a constant here
        lin = {"arity": 2, "writes": {0: ("lin", 1, 2, 1)}}                                  # 2n + 1 (a hex string)
        self.assertEqual(self.run_with(lin, [("add", "r0, sp, #0"), ("mov", "r1, #3")], body=[("bx", "lr")]), [CB_A])
        self.refused(lin, [("add", "r0, sp, #0"), ("mov", "r1, #4")], body=[("bx", "lr")])

    # -- a kept pointer
    def test_a_contract_that_keeps_the_pointer(self):
        self.refused({"writes": {0: 4}, "keeps": {0: "EXT"}}, [("add", "r0, sp, #12")])

    def test_code_that_keeps_the_pointer_under_a_contract_that_says_not(self):
        self.refused({"writes": {}}, [("add", "r0, sp, #12")], body=[("str", "r0, [r6]"), ("bx", "lr")],
                     why="is not kept")
        # declared: the self-check passes, and the declared keep then leaks the frame
        self.refused({"writes": {}, "keeps": {0: "EXT"}}, [("add", "r0, sp, #12")], body=[("str", "r0, [r6]"), ("bx", "lr")])


class TheRealContracts(unittest.TestCase):
    """The contracts the final image relies on are bound to it, and each one's code passes the self-check."""

    @classmethod
    def setUpClass(cls):
        cls.img = isa.Image(ELF)                           # (kept unanalysed: every use goes through settle)

    def test_every_contract_is_bound_and_consistent(self):
        names = sorted(isa.Image.CONTRACTS)

        def check(im):
            return {n: (im._contract(im.syms[n][0] & ~1), im._code_digest(im.syms[n][0] & ~1)) for n in names}
        got = isa.settle(self.img, check)
        for name in names:
            with self.subTest(name):
                c, digest = got[name]
                self.assertIsNotNone(c)
                self.assertEqual(digest, isa.Image.CONTRACT_CODE[name])
                self.assertEqual(isa.sha256_file(R / c["unit"]), isa.Image.CONTRACT_SOURCES[c["unit"]])

    def test_the_bindings_are_read_off_the_bytes(self):
        img = copy.deepcopy(self.img)
        t = img.syms["p3_hex"][0] & ~1
        sec = next(s for s in img.secs if s["addr"] <= t < s["addr"] + s["size"])
        blob = bytearray(img.blob)
        blob[sec["offset"] + t - sec["addr"]] ^= 1                        # one bit of p3_hex's code
        img.blob = bytes(blob)
        with self.assertRaises(isa.Finding) as c:
            isa.settle(img, lambda im: im._contract(t))
        self.assertIn("bound to its code closure", str(c.exception))

T_ADDR = 0x9100                                           # a synthetic read-only table, in a synthetic .rodata


def with_table(img, words=None, extra_words=None, name="TBL"):
    """Give a synthetic image a .rodata section holding the table `name` at T_ADDR: its words (default CB_A | 1,
    CB_B | 1), and any `extra_words` elsewhere {address: word}."""
    words = words if words is not None else [CB_A | 1, CB_B | 1]
    img.secs = [{"name": ".rodata", "addr": 0x9000, "offset": 0, "size": 0x1000},
                {"name": ".data", "addr": 0xA000, "offset": 0x1000, "size": 0x1000}]
    img.syms = dict(img.syms, **{name: (T_ADDR, 4 * len(words), "r")})
    img.words = {T_ADDR + 4 * k: w for k, w in enumerate(words)}
    img.words.update(extra_words or {})
    img.__dict__.pop("_ro_tables_cache", None)
    return img


TBL = [("movw", "r0, #37120"), ("movt", "r0, #0")]       # r0 = T_ADDR
CONSUME = [("ldr", "r3, [r0, #4]"), ("blx", "r3"), ("mov", "r0, #0"), ("bx", "lr")]   # calls the 2nd word


class TheReadOnlyTables(unittest.TestCase):
    """A callback read from a field of a .rodata table is the ELF's word there — only while nothing can write the
    table: materialised only by the image's units, no store through it, never stored outside a frame, every
    callee it is handed to writing nothing through it and keeping nothing."""

    def run_with(self, builder, consumer=CONSUME, more=None, **kw):
        routines = {"c": (C, consumer)}
        routines.update(more or {})
        img, b = synth(builder + [("bl", call(C, "c")), ("mov", "r0, #0"), ("bx", "lr")], more=routines)
        with_table(img, **kw)
        try:
            return handed(img, b, C)
        except isa.Finding as e:
            return str(e)

    def test_a_table_read_resolves_to_its_word(self):
        self.assertEqual(self.run_with(TBL), [CB_B])
        self.assertEqual(self.run_with(TBL, consumer=[("ldr", "r3, [r0]"), ("blx", "r3"), ("mov", "r0, #0"), ("bx", "lr")]), [CB_A])

    def test_a_store_through_it(self):
        self.assertIn("may be written", self.run_with(TBL, consumer=[("mov", "r2, #0"), ("str", "r2, [r0, #4]")] + CONSUME))
        self.assertIn("may be written", self.run_with(TBL + [("mov", "r2, #0"), ("strb", "r2, [r0, #5]")]))

    def test_a_callee_that_writes_through_it_or_keeps_it(self):
        H2 = 0x5000
        for body in ([("mov", "r2, #0"), ("str", "r2, [r0, #4]"), ("mov", "r0, #0"), ("bx", "lr")],
                     [("str", "r0, [r6]"), ("mov", "r0, #0"), ("bx", "lr")]):
            with self.subTest(body):
                self.assertIn("may be written", self.run_with(TBL + [("bl", call(H2, "h"))] + TBL, more={"h": (H2, body)}))
        self.assertEqual(self.run_with(TBL + [("bl", call(H2, "h"))] + TBL,
                                       more={"h": (H2, [("ldr", "r2, [r0]"), ("mov", "r0, #0"), ("bx", "lr")])}),
                         [CB_B], "a callee that only reads it")

    def test_stored_outside_the_frame(self):
        self.assertIn("may be written", self.run_with(TBL + [("str", "r0, [r6]")]))
        self.assertEqual(self.run_with(TBL + [("str", "r0, [sp, #8]")]), [CB_B], "spilled to its own frame")

    def test_its_address_in_a_data_word(self):
        self.assertIn("may be written", self.run_with(TBL, extra_words={0xA010: T_ADDR + 4}))

    def test_materialised_outside_the_image_s_units(self):
        routines = {"c": (C, CONSUME)}
        img, b = synth(TBL + [("bl", call(C, "c")), ("mov", "r0, #0"), ("bx", "lr")], more=routines)
        with_table(img)
        img.units = [u for u in img.units if u[0] != b]
        with self.assertRaises(isa.Finding) as c:
            handed(img, b, C)
        self.assertIn("outside the image's units", str(c.exception))

    def test_a_word_that_is_not_a_callback(self):
        self.assertIn("not an application callback", self.run_with(TBL, words=[CB_A | 1, 0x1234]))

    # ---- the owner's HOLD on 78c2bb0, P1-1: the table is written through a pointer that never was "the table's"
    # (T - 4 is outside it, so it carries no table provenance). What counts is the BYTES a write may reach.

    BESIDE = [("movw", "r1, #37116"), ("movt", "r1, #0")]    # r1 = T_ADDR - 4
    ZERO = [("mov", "r2, #0"), ("mov", "r3, #0")]

    def test_a_store_that_reaches_it_from_a_pointer_beside_it(self):
        B, Z = self.BESIDE, self.ZERO
        for what, lead, reach in (
                ("T - 4, plus 8, then a word", B + [("add", "r1, r1, #8")] + Z + [("str", "r2, [r1]")], "0x9104..0x9108"),
                ("a word at [T - 4, #8]", B + Z + [("str", "r2, [r1, #8]")], "0x9104..0x9108"),
                ("eight bytes at T - 4, crossing in", B + Z + [("strd", "r2, r3, [r1]")], "0x9100..0x9104"),
                ("a word at T - 2, crossing in", [("movw", "r1, #37118"), ("movt", "r1, #0")] + Z + [("str", "r2, [r1]")], "0x9100..0x9102"),
                ("a byte at the table's last byte", B + Z + [("strb", "r2, [r1, #11]")], "0x9107..0x9108"),
                ("a byte at the table's first byte", B + Z + [("strb", "r2, [r1, #4]")], "0x9100..0x9101")):
            with self.subTest(what):
                r = self.run_with(lead + TBL)
                self.assertIsInstance(r, str, "accepted")
                self.assertIn("may be written: f stores at", r)
                self.assertIn("it may reach " + reach, r)
        for what, lead in (("a word at T - 4, ending where it starts", B + Z + [("str", "r2, [r1]")]),
                           ("a word at T + 8, starting where it ends", B + Z + [("str", "r2, [r1, #12]")]),
                           ("a byte just past it", B + Z + [("strb", "r2, [r1, #12]")]),
                           ("eight bytes ending where it starts", B + Z + [("strd", "r2, r3, [r1, #-4]")])):
            with self.subTest(what):
                self.assertEqual(self.run_with(lead + TBL), [CB_B], "a write that does not overlap it")

    def test_a_callee_handed_a_pointer_beside_it(self):
        H2, G2 = 0x5000, 0x6000
        beside = [("movw", "r0, #37116"), ("movt", "r0, #0")]
        ret = [("mov", "r0, #0"), ("bx", "lr")]

        def via(body, more=None):
            routines = {"h": (H2, body)}
            routines.update(more or {})
            return self.run_with(beside + [("bl", call(H2, "h"))] + TBL, more=routines)
        on = [("add", "r0, r0, #4"), ("bl", call(G2, "g")), ("mov", "r0, #0"), ("bx", "lr")]   # (no push: a synthetic
        #                                         routine's SP is one fixed offset, so a push would leave its frame)
        for what, r, why in (
                ("a word at its argument + 8", via([("mov", "r2, #0"), ("str", "r2, [r0, #8]")] + ret), "it may reach 0x9104..0x9108"),
                ("eight bytes at its argument", via(self.ZERO + [("strd", "r2, r3, [r0]")] + ret), "it may reach 0x9100..0x9104"),
                ("its argument stepped by 8", via([("add", "r0, r0, #8"), ("mov", "r2, #0"), ("str", "r2, [r0]")] + ret), "it may reach 0x9104..0x9108"),
                ("handed on to a writer", via(on, {"g": (G2, [("mov", "r2, #0"), ("str", "r2, [r0, #4]")] + ret)}), "it may reach 0x9104..0x9108"),
                ("at a register index", via([("mov", "r2, #0"), ("str", "r2, [r0, r1]")] + ret), "over an extent that is not bounded")):
            with self.subTest(what):
                self.assertIsInstance(r, str, "accepted")
                self.assertIn("may be written: f hands r0 to h, which writes through it", r)
                self.assertIn(why, r)
        for what, r in (("a word at its argument, ending where the table starts", via([("mov", "r2, #0"), ("str", "r2, [r0]")] + ret)),
                        ("a word at its argument + 12, starting where it ends", via([("mov", "r2, #0"), ("str", "r2, [r0, #12]")] + ret)),
                        ("a callee that only reads through it", via([("ldr", "r2, [r0, #8]")] + ret)),
                        ("handed on to a writer that misses it", via(on, {"g": (G2, [("mov", "r2, #0"), ("str", "r2, [r0, #8]")] + ret)}))):
            with self.subTest(what):
                self.assertEqual(r, [CB_B])

    def test_a_write_that_cannot_be_placed(self):
        """No object provenance is assumed: a write whose bytes are not pinned is not proved to miss the table."""
        H2 = 0x5000
        far = [("movw", "r0, #40960"), ("movt", "r0, #0")]      # r0 = 0xA000, in .data
        ret = [("mov", "r0, #0"), ("bx", "lr")]
        store = [("mov", "r2, #0"), ("str", "r2, [r0, #4]")]
        for what, r, why in (
                ("through a pointer loaded from memory", self.run_with(far + [("ldr", "r1, [r0]"), ("mov", "r2, #0"), ("str", "r2, [r1]")] + TBL),
                 "f stores at 0x1010: it is not placed (through an unknown pointer)"),
                ("at a register index from a constant", self.run_with(far + [("mov", "r2, #0"), ("str", "r2, [r0, r4]")] + TBL),
                 "over an extent that is not bounded"),
                ("through a constant stepped round a loop", self.run_with(
                    far + [("mov", "r2, #0"), ("str", "r2, [r0]"), ("add", "r0, r0, #4"), ("cmp", "r0, r5"), ("bne", br(0x100c))] + TBL),
                 "f stores at 0x100c: it is not placed (through a stepped constant address the model does not bound)"),
                ("through the argument of a routine nothing calls", self.run_with(store + TBL),
                 "the routine is entered other than by a call whose arguments are read"),
                ("by a routine that cannot be read", self.run_with(far + [("bl", call(H2, "lib"))] + TBL, more={"lib": (H2, [])}),
                 "may be written")):
            with self.subTest(what):
                self.assertIsInstance(r, str, "accepted")
                self.assertIn(why, r)
        self.assertEqual(self.run_with(far + store + TBL), [CB_B], "the same store, through a constant elsewhere")
        self.assertEqual(self.run_with(far + [("bl", call(H2, "h"))] + TBL, more={"h": (H2, store + ret)}), [CB_B],
                         "the same store through an argument, in a routine called with that constant")
        self.assertEqual(self.run_with([("mov", "r2, #0"), ("str", "r2, [sp, #8]"), ("strb", "r2, [sp, #13]")] + TBL), [CB_B],
                         "stores into its own frame at known slots")
        self.assertIn("f stores at 0x1004: it is not placed (through an address of its frame, over an extent that is not bounded)",
                      self.run_with([("mov", "r2, #0"), ("str", "r2, [sp, r4]")] + TBL), "its own frame, at a register index")

    def test_a_pointer_handed_on_by_a_tail(self):
        H2, G2 = 0x5000, 0x6000
        writer = [("mov", "r2, #0"), ("str", "r2, [r0, #8]"), ("mov", "r0, #0"), ("bx", "lr")]
        for what, lead, want in (("beside the table", [("movw", "r0, #37116"), ("movt", "r0, #0")], "g hands r0 to h, which writes through it at 0x6008: it may reach 0x9104..0x9108"),
                                 ("elsewhere", [("movw", "r0, #40960"), ("movt", "r0, #0")], None)):
            with self.subTest(what):
                r = self.run_with([("bl", call(G2, "g"))] + TBL, more={"g": (G2, lead + [("b", call(H2, "h"))]), "h": (H2, writer)})
                if want:
                    self.assertIsInstance(r, str, "accepted")
                    self.assertIn(want, r)
                else:
                    self.assertEqual(r, [CB_B])

    def test_an_argument_is_followed_only_where_every_entry_is_a_call(self):
        """h writes through its argument and f calls it with a constant elsewhere: placed. The same h, address-taken
        (so something else may enter it with anything in r0): not placed."""
        H2 = 0x5000
        far = [("movw", "r0, #40960"), ("movt", "r0, #0")]
        h = {"h": (H2, [("mov", "r2, #0"), ("str", "r2, [r0, #4]"), ("mov", "r0, #0"), ("bx", "lr")])}
        routines = dict({"c": (C, CONSUME)}, **h)
        for taken, want in (((), None), ((H2,), "h stores at 0x5004: it is not placed (through its own argument, and the routine is entered other than by a call")):
            with self.subTest(taken=taken):
                img, b = synth(far + [("bl", call(H2, "h"))] + TBL + [("bl", call(C, "c")), ("mov", "r0, #0"), ("bx", "lr")], more=routines)
                with_table(img)
                img.address_taken = list(taken)
                try:
                    r = handed(img, b, C)
                except isa.Finding as e:
                    r = str(e)
                if want:
                    self.assertIsInstance(r, str, "accepted")
                    self.assertIn(want, r)
                else:
                    self.assertEqual(r, [CB_B])

    def test_a_contracted_writer_is_placed_by_its_contract(self):
        """h's code writes at a register index — not placed when read off the code; under a contract (4 or 8 bytes
        through its argument) the write is the contract's, placed where h is called."""
        H2 = 0x5000
        body = [("mov", "r3, #0"), ("strb", "r3, [r0, r1]"), ("mov", "r0, #0"), ("bx", "lr")]

        def go(lead, writes):
            img, b = synth(lead + [("bl", call(H2, "h"))] + TBL + [("bl", call(C, "c")), ("mov", "r0, #0"), ("bx", "lr")],
                           more={"c": (C, CONSUME), "h": (H2, body)})
            with_table(img)
            patches = [mock.patch.dict(isa.Image.CONTRACTS, {} if writes is None else {"h": {
                           "unit": APP, "arity": 2, "returns": "int", "source": "synthetic", "writes": writes}}, clear=True),
                       mock.patch.dict(isa.Image.CONTRACT_SOURCES, {APP: "S"}, clear=True),
                       mock.patch.dict(isa.Image.CONTRACT_CODE, {"h": img._code_digest(H2)}, clear=True),
                       mock.patch.object(isa.Image, "_unit_sha", return_value="S")]
            for p in patches:
                p.start()
            try:
                return handed(img, b, C)
            except isa.Finding as e:
                return str(e)
            finally:
                for p in patches:
                    p.stop()
        beside = [("movw", "r0, #37116"), ("movt", "r0, #0")]
        far = [("movw", "r0, #40960"), ("movt", "r0, #0")]
        self.assertIn("f hands r0 to h, which writes through it at 0x1008: it is not placed (through the constant 0xa000, "
                      "over an extent that is not bounded)", go(far, None), "no contract: read off the code")
        self.assertEqual(go(far, {0: 4}), [CB_B], "4 bytes at a constant elsewhere")
        self.assertEqual(go(beside, {0: 4}), [CB_B], "4 bytes ending where the table starts")
        r = go(beside, {0: 8})
        self.assertIsInstance(r, str, "accepted")
        self.assertIn("f hands r0 to h, which writes through it at 0x1008: it may reach 0x9100..0x9104", r)


class TheWriteInventory(unittest.TestCase):
    """Every write of every routine, by where it is placed (the owner's strict ruling of 2026-10-06): none is left
    out, one that is not placed is listed by its address, and a placed one overlapping a protected object is named."""

    H2, LIB = 0x5000, 0x7000
    A000 = [("movw", "r0, #40960"), ("movt", "r0, #0")]      # r0 = 0xA000, in .data
    A100 = [("movw", "r0, #41216"), ("movt", "r0, #0")]      # r0 = 0xA100: the synthetic __atexit

    def inventory(self, body, lib=True):
        more = {"h": (self.H2, [("mov", "r2, #0"), ("str", "r2, [r0, #16]"), ("mov", "r0, #0"), ("bx", "lr")])}
        if lib:
            more["lib"] = (self.LIB, [])
        img, _b = synth(body + [("mov", "r0, #0"), ("bx", "lr")], more=more, library=("lib",) if lib else ())
        with_table(img)
        img.syms["__atexit"] = (0xA100, 4, "B")
        return isa.settle(img, lambda im: im.write_inventory())

    BODY = ([("mov", "r2, #0"), ("str", "r2, [sp, #8]")]                        # 0x1004 its own frame
            + A000 + [("str", "r2, [r0, #4]"),                                  # 0x1010 a constant, elsewhere
                      ("bl", call(H2, "h"))]                                    # 0x1014 h writes [its argument, #16]
            + A100 + [("mov", "r2, #0"), ("str", "r2, [r0]"),                   # 0x1024 a constant: the __atexit word
                      ("ldr", "r1, [r0]"), ("str", "r2, [r1]"),                 # 0x102c through a loaded pointer
                      ("str", "r2, [r0, r4]")])                                 # 0x1030 at a register index

    def test_each_write_is_counted_once_and_the_unplaced_are_listed(self):
        w = self.inventory(self.BODY + [("bl", call(self.LIB, "lib"))])         # 0x1034 a routine that cannot be read
        f, h = w["routines"]["f"], w["routines"]["h"]
        self.assertEqual(f["stores"], 5)
        self.assertEqual({x for v in f["not_placed_at"].values() for x in v}, {"0x102c", "0x1030", "0x1034"})
        self.assertEqual([k for k in f["not_placed_at"] if k.startswith("stores: ")],
                         ["stores: through an unknown pointer", "stores: through the constant 0xa100, over an extent that is not bounded"])
        self.assertEqual(f["overlapping_at"], {"__atexit": ["0x1024"]})
        self.assertEqual(f["stores"] + f["hand_overs"], f["placed"] + f["at_the_callers"] + f["by_contract"] + f["not_placed"])
        self.assertEqual(f["placed"], 4, "the frame store, two constant stores and the constant handed to h")
        self.assertEqual((h["stores"], h["at_the_callers"], h["not_placed"]), (1, 1, 0), "h's store is placed where h is called")
        self.assertNotIn("not_placed_at", h)
        self.assertEqual(w["total"]["not_placed_sites"], 3)
        self.assertEqual(w["unproved"], 4, "three not placed and one overlapping")
        self.assertEqual([p["name"] for p in w["protected"]], ["TBL", "__atexit"])

    def test_an_image_whose_writes_are_all_placed_and_miss(self):
        w = self.inventory([("mov", "r2, #0"), ("str", "r2, [sp, #8]")] + self.A000
                           + [("str", "r2, [r0, #4]"), ("bl", call(self.H2, "h"))], lib=False)
        self.assertEqual(w["unproved"], 0)
        self.assertEqual(w["total"]["not_placed"], 0)
        self.assertEqual(w["total"]["stores"], 3)
        self.assertEqual(w["total"]["placed"] + w["total"]["at_the_callers"], w["total"]["stores"] + w["total"]["hand_overs"])
        self.assertTrue(all("not_placed_at" not in r and "overlapping_at" not in r for r in w["routines"].values()))

    def test_a_write_into_the_table_is_an_overlap_by_name(self):
        w = self.inventory([("mov", "r2, #0"), ("movw", "r1, #37116"), ("movt", "r1, #0"), ("str", "r2, [r1, #8]")], lib=False)
        self.assertEqual(w["routines"]["f"]["overlapping_at"], {"TBL": ["0x100c"]})
        self.assertNotIn("not_placed_at", w["routines"]["f"])
        (why, at), = w["routines"]["h"]["not_placed_at"].items()   # h is called by nothing here: its argument is unknown
        self.assertIn("the routine is entered other than by a call whose arguments are read", why)
        self.assertEqual(at, ["0x5004"])
        self.assertEqual(w["unproved"], 2)

    def test_two_routines_of_one_name_keep_a_record_each(self):
        more = {"h": (self.H2, [("mov", "r2, #0"), ("str", "r2, [sp, #8]"), ("mov", "r0, #0"), ("bx", "lr")])}
        img, _b = synth([("mov", "r2, #0"), ("str", "r2, [sp, #8]"), ("str", "r2, [sp, #12]"), ("mov", "r0, #0"), ("bx", "lr")], more=more)
        img.label_at[self.H2] = img.func_entries[self.H2] = "f"
        w = isa.settle(with_table(img), lambda im: im.write_inventory())
        self.assertEqual({k: v["stores"] for k, v in w["routines"].items()}, {"f@0x1000": 2, "f@0x5000": 1})
        self.assertEqual(w["total"]["stores"], 3)

    def test_what_calls_through_memory(self):
        img, b = synth([("bl", call(C, "c")), ("bx", "lr")],
                       more={"c": (C, CONSUME), "h": (self.H2, [("mov", "r0, #0"), ("bx", "lr")])})
        self.assertTrue(img.calls_through_memory(b), "f calls c, which calls a pointer")
        self.assertTrue(img.calls_through_memory(C))
        self.assertFalse(img.calls_through_memory(self.H2), "a leaf")


class TheFrameCells(unittest.TestCase):
    """Every frame slot that may hold a callback, a table's address or an argument the routine reaches a callback
    through has a result (`Image.frame_cells`), and a cell that is not resolved names what blocked it — the write,
    or the call and the routines under it."""

    G2, K2, U2, H2 = 0x5000, 0x6000, 0x7000, 0x7800
    POST = [("ldr", "r1, [sp, #8]"), ("blx", "r1"), ("mov", "r0, #0"), ("bx", "lr")]

    def cells(self, **kw):
        ret = [("mov", "r0, #0"), ("bx", "lr")]
        more = {"g": (self.G2, CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [r6]")] + self.POST),   # an unplaced store
                "k": (self.K2, [("str", "r0, [sp, #16]"), ("mov", "r2, #7"), ("str", "r2, [sp, #20]"),              # its argument, spilled
                                ("str", "r1, [sp, #24]"), ("ldr", "r2, [sp, #24]"),      # (an argument it reaches no callback through)
                                ("ldr", "r3, [sp, #16]"), ("blx", "r3")] + ret),
                "u": (self.U2, CB + [("str", "r0, [sp, #8]"), ("bl", call(self.H2, "h"))] + self.POST),            # a call over an unplaced store
                "h": (self.H2, [("mov", "r3, #0"), ("str", "r3, [r6]")] + ret)}
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r2, #5"), ("str", "r2, [sp, #24]")] + TBL +
                       [("str", "r0, [sp, #12]"), ("ldr", "r0, [sp, #12]"), ("bl", call(C, "c"))] + self.POST,
                       more=dict(more, c=(C, CONSUME)), **kw)
        with_table(img)
        return {(c["routine"], c["slot"]): c for c in isa.settle(img, lambda im: im.frame_cells())}

    def test_every_candidate_has_a_result_and_a_refusal_names_what_blocked_it(self):
        c = self.cells()
        self.assertEqual(sorted(c), [("f", 8 - SP), ("f", 12 - SP), ("g", 8 - SP), ("k", 16 - SP), ("u", 8 - SP)],
                         "the callback slots, the table-address slot and the spilled callback argument — not the data words, "
                         "nor k's other argument")
        self.assertEqual(c["f", 8 - SP]["holds"], ["a callback"])
        self.assertEqual(c["f", 12 - SP]["holds"], ["a read-only table's address"])
        self.assertEqual(c["k", 16 - SP]["holds"], ["an argument the routine reaches a callback through"])
        for key in (("f", 8 - SP), ("f", 12 - SP), ("k", 16 - SP)):
            self.assertEqual((c[key]["resolved"], c[key]["blocked_by"]), (True, []), key)
        g = c["g", 8 - SP]
        self.assertFalse(g["resolved"])
        self.assertEqual(g["blocked_by"], [{"at": "0x5010", "why": "a store that is not placed (through an unknown pointer)"}])
        u = c["u", 8 - SP]
        self.assertFalse(u["resolved"])
        self.assertEqual(len(u["blocked_by"]), 1)
        self.assertEqual(u["blocked_by"][0]["at"], "0x700c")
        self.assertEqual(u["blocked_by"][0]["under"], {"h": 1}, "the routines under the call with a write that is not placed")
        self.assertIn("h stores at 0x7804, that is not placed (through an unknown pointer)", u["blocked_by"][0]["why"])

    def test_a_cell_overwritten_by_a_value_that_is_no_callback_is_unresolved_with_a_reason(self):
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("cbz", f"r2, {br(0x1018)}"), ("mov", "r3, #0"), ("str", "r3, [sp, #8]"),
                             ("ldr", "r1, [sp, #8]"), ("blx", "r1"), ("mov", "r0, #0"), ("bx", "lr")])   # zeroed on one path
        (c,) = isa.settle(img, lambda im: im.frame_cells())
        self.assertEqual((c["routine"], c["slot"], c["resolved"]), ("f", 8 - SP, False))
        self.assertTrue(c["blocked_by"], "an unresolved cell always carries a reason")
        self.assertIn("at this read the slot may hold cb, const", c["blocked_by"][0]["why"])


    def test_only_what_blocks_a_read_that_may_see_the_value_is_reported(self):
        """The slot is also loaded BEFORE its store (uninitialised there: no callback to see, so not that read's
        business); what is reported is what stands between the store and the read that may see the callback."""
        img, b = synth([("ldr", "r2, [sp, #8]")] + CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [r6]"),
                                                         ("ldr", "r1, [sp, #8]"), ("blx", "r1"), ("mov", "r0, #0"), ("bx", "lr")])

        def run(im):
            cells = im.frame_cells()
            return cells, sorted(why for _a, why in im._cache("_cellblk").get((b, 8 - SP), ()))
        (c,), everything = isa.settle(img, run)
        self.assertEqual((c["routine"], c["slot"], c["resolved"]), ("f", 8 - SP, False))
        self.assertEqual(c["blocked_by"], [{"at": "0x1014", "why": "a store that is not placed (through an unknown pointer)"}])
        self.assertIn("a path from the routine's entry with no store to the slot (uninitialised there)", everything,
                      "recorded against the early load, and rightly left out of the cell's reasons")


class TheBoundedIndex(unittest.TestCase):
    """A1 (the owner's ruling of 2026-10-07): a write at base + index is placed when the index has an UNSIGNED range
    read off the image — an unsigned guard on every path after the index's last definition, or a definition that
    bounds it — with the write's width and the 32-bit wrap counted. A signed test, an equality, a guard a path goes
    round, an index written after the guard, a wrap: not placed. Each refusal has its placed control beside it."""

    FAR = [("movw", "r6, #40960"), ("movt", "r6, #0")]            # r6 = 0xA000: a buffer outside the stacks
    PRE = CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0")]
    POST = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]

    def run_with(self, mid, **kw):
        """f holds a callback at [sp, #8]; `mid` writes in between; the cell stands only if the write is placed."""
        img, b = synth(self.PRE + self.FAR + list(mid) + self.POST, **kw)
        try:
            return targets(img, b), isa.settle(synth(self.PRE + self.FAR + list(mid) + self.POST, **kw)[0],
                                               lambda im: im.write_inventory()["routines"]["f"])
        except isa.Finding as e:
            return str(e), None

    def placed(self, mid, rule, **kw):
        r, inv = self.run_with(mid, **kw)
        self.assertEqual(r, [CB_A], f"not placed: {r}")
        self.assertEqual(inv["not_placed"], 0)
        self.assertEqual(list(inv["placed_by_a1_at"]), [rule], inv["placed_by_a1_at"])

    def refused(self, mid, why, **kw):
        r, _inv = self.run_with(mid, **kw)
        self.assertIsInstance(r, str, f"placed: {r}")
        self.assertIn(why, r)

    UNB = "over an extent that is not bounded"
    GUARD = "a register index bounded by an unsigned guard"

    def test_an_unsigned_guard_on_the_index(self):
        skip = br(0x1024)                                  # PRE 4 + FAR 2 = 6 instructions: the store is 0x1020
        self.placed([("cmp", "r4, #16"), ("bcs", skip), ("strb", "r3, [r6, r4]")], self.GUARD)
        self.placed([("cmp", "r4, #16"), ("bhi", skip), ("strb", "r3, [r6, r4]")], self.GUARD)
        self.placed([("cmp", "r4, #16"), ("bcc", br(0x1024)), ("mov", "r4, #0"), ("strb", "r3, [r6, r4]")], "a register index bounded by a constant / an unsigned guard")
        # a counted loop: the guard is the loop test, the store the body
        self.placed([("cmp", "r4, #16"), ("bcs", br(0x102c)), ("strb", "r3, [r6, r4]"), ("add", "r4, r4, #1"), ("b", br(0x1018))], self.GUARD)
        for what, test in (("a signed test", "bge"), ("an equality", "beq"), ("the other way round", "bcc")):
            with self.subTest(what):
                self.refused([("cmp", "r4, #16"), (test, skip), ("strb", "r3, [r6, r4]")], self.UNB)
        self.refused([("strb", "r3, [r6, r4]")], self.UNB)

    def test_both_outcomes_of_a_branch_are_paths_to_the_write(self):
        """The owner's HOLD on f624c87, P1: the index is 64, the test is `< 16`, and BOTH outcomes of the branch
        reach the write — through the table's first word. A walk that visited the branch once would see only the
        outcome it came back over first and take its bound. Each outcome is a path of its own; a branch whose target
        is its own fallthrough says nothing."""
        tables = TheReadOnlyTables().run_with
        prefix = [("movw", "r6, #37056"), ("movt", "r6, #0"), ("mov", "r4, #64"), ("mov", "r3, #0"), ("cmp", "r4, #16")]
        first = [("ldr", "r3, [r0]"), ("blx", "r3"), ("mov", "r0, #0"), ("bx", "lr")]
        for what, mid, store in (("no branch (the control)", [], 0x1014),
                                 ("a branch whose target is its fallthrough", [("bcc", br(0x1018))], 0x1018),
                                 ("both outcomes rejoin before the write", [("bcc", br(0x1020)), ("mov", "r5, #0"), ("b", br(0x1024)), ("mov", "r5, #1")], 0x1024),
                                 ("the taken outcome rejoins from further on", [("bcc", br(0x1020)), ("mov", "r5, #0"), ("mov", "r5, #1")], 0x1020)):
            with self.subTest(what):
                r = tables(prefix + mid + [("str", "r3, [r6, r4]")] + TBL, consumer=first)
                self.assertIsInstance(r, str, "accepted")
                self.assertIn(f"f stores at {store:#x}: it may reach 0x9100..0x9104", r)
        # and the control the other way: only the bounded outcome reaches the write
        r = tables(prefix + [("bcs", br(0x101c)), ("str", "r3, [r6, r4]")] + TBL, consumer=first)
        self.assertEqual(r, [CB_A], "r4 < 16 on the one path to the store: sixteen bytes below the table")

    def test_a_guard_a_path_goes_round_or_the_index_written_after_it(self):
        store = br(0x1024)
        self.refused([("cbz", f"r2, {store}"), ("cmp", "r4, #16"), ("bcs", br(0x1028)), ("strb", "r3, [r6, r4]")], self.UNB)
        self.placed([("cmp", "r4, #16"), ("bcs", br(0x1028)), ("add", "r4, r4, #1"), ("strb", "r3, [r6, r4]")], self.GUARD + " + 1")
        self.placed([("cmp", "r4, #16"), ("bcs", br(0x1028)), ("add", "r5, r4, #1"), ("strb", "r3, [r6, r5]")], self.GUARD + " + 1")
        self.refused([("cmp", "r4, #16"), ("bcs", br(0x1028)), ("add", "r4, r4, r7"), ("strb", "r3, [r6, r4]")], self.UNB)
        self.refused([("cmp", "r4, #16"), ("bcs", br(0x1028)), ("ldr", "r5, [sp, #20]"), ("strb", "r3, [r6, r5]")], self.UNB)

    def test_an_index_bounded_by_its_definition(self):
        for what, defs, rule in (("uxtb", [("uxtb", "r4, r4")], "a uxtb"), ("an and-mask", [("and", "r4, r4, #7")], "an and-mask"),
                                 ("an lsr", [("lsr", "r4, r4, #28")], "an lsr"), ("a byte load", [("ldrb", "r4, [sp, #20]")], "a ldrb"),
                                 ("a constant", [("mov", "r4, #3")], "a constant"), ("a ubfx", [("ubfx", "r4, r4, #2, #4")], "a ubfx"),
                                 ("a copy of one", [("uxtb", "r5, r4"), ("mov", "r4, r5")], "a uxtb"),
                                 ("a shift of one", [("uxtb", "r4, r4"), ("lsl", "r4, r4, #2")], "a uxtb << 2")):
            with self.subTest(what):
                self.placed(defs + [("strb", "r3, [r6, r4]")], "a register index bounded by " + rule)
        self.refused([("ldr", "r4, [sp, #20]"), ("strb", "r3, [r6, r4]")], self.UNB)
        self.refused([("uxtb", "r4, r4"), ("lsl", "r4, r4, #25"), ("strb", "r3, [r6, r4]")], self.UNB, )   # 255 << 25 wraps
        self.refused([("cbz", f"r2, {br(0x1020)}"), ("uxtb", "r4, r4"), ("strb", "r3, [r6, r4]")], self.UNB)   # unbounded on a path

    def test_a_compare_against_a_bounded_register_and_a_conditional_store(self):
        self.placed([("mov", "r7, #8"), ("cmp", "r4, r7"), ("bcs", br(0x1028)), ("strb", "r3, [r6, r4]")], self.GUARD)
        self.refused([("cmp", "r4, r7"), ("bcs", br(0x1024)), ("strb", "r3, [r6, r4]")], self.UNB)
        self.placed([("cmp", "r4, #16"), ("strbls", "r3, [r6, r4]")], self.GUARD)
        self.refused([("cmp", "r4, #16"), ("strble", "r3, [r6, r4]")], self.UNB)

    def test_the_extent_counts_the_scale_and_the_width_against_the_table(self):
        """Through the read-only-table proof: a scaled index into the words just below the table."""
        run = TheReadOnlyTables().run_with
        below = [("movw", "r6, #37056"), ("movt", "r6, #0")]       # r6 = T_ADDR - 64: sixteen words below the table
        for what, lead, want in (("fifteen words, then the table's first", [("cmp", "r4, #16"), ("bcs", br(0x101c)), ("str", "r3, [r6, r4, lsl #2]")], None),
                                 ("sixteen: the table's first word", [("cmp", "r4, #16"), ("bhi", br(0x101c)), ("str", "r3, [r6, r4, lsl #2]")], "it may reach 0x9100..0x9104"),
                                 ("a double word at the fifteenth", [("cmp", "r4, #16"), ("bcs", br(0x101c)), ("strd", "r2, r3, [r6, r4, lsl #2]")], "it may reach 0x9100..0x9104"),
                                 ("a byte at the index, unscaled", [("cmp", "r4, #64"), ("bcs", br(0x101c)), ("strb", "r3, [r6, r4]")], None),
                                 ("a byte one further", [("cmp", "r4, #65"), ("bcs", br(0x101c)), ("strb", "r3, [r6, r4]")], "it may reach 0x9100..0x9101")):
            with self.subTest(what):
                r = run(below + [("mov", "r2, #0"), ("mov", "r3, #0")] + lead + TBL)
                if want is None:
                    self.assertEqual(r, [CB_B])
                else:
                    self.assertIsInstance(r, str, "accepted")
                    self.assertIn(want, r)

    def test_an_address_computed_from_the_index(self):
        skip = br(0x1028)
        rule = "an address computed from an index bounded by an unsigned guard"
        self.placed([("cmp", "r4, #16"), ("bcs", skip), ("add", "r5, r6, r4, lsl #2"), ("str", "r3, [r5, #4]")], rule)
        self.placed([("cmp", "r4, #16"), ("bcs", skip), ("add", "r5, r6, r4"), ("strb", "r3, [r5]")], rule)
        self.refused([("add", "r5, r6, r4, lsl #2"), ("str", "r3, [r5, #4]")], "that is not placed")
        # the computed address handed to a callee that writes through it
        H2 = 0x5000
        w = {"h": (H2, [("mov", "r2, #0"), ("str", "r2, [r0, #4]"), ("mov", "r0, #0"), ("bx", "lr")])}
        r, inv = self.run_with([("cmp", "r4, #16"), ("bcs", br(0x1034)), ("add", "r0, r6, r4, lsl #2"), ("mov", "r1, #0"), ("mov", "r2, #0"),
                                ("mov", "r3, #0"), ("bl", call(H2, "h"))], more=w)
        self.assertEqual(r, [CB_A])
        self.assertEqual(list(inv["placed_by_a1_at"]), ["a handed address computed from an index bounded by an unsigned guard"])
        self.refused([("add", "r0, r6, r4, lsl #2"), ("mov", "r1, #0"), ("mov", "r2, #0"), ("mov", "r3, #0"), ("bl", call(H2, "h"))],
                     "that is not placed", more=w)

    def test_the_wrap_and_the_cell_s_own_frame(self):
        top = [("movw", "r6, #65520"), ("movt", "r6, #65535")]     # r6 = 0xFFFFFFF0: sixteen bytes to the end of memory
        img, b = synth(self.PRE + top + [("uxtb", "r4, r4"), ("strb", "r3, [r6, r4]")] + self.POST)
        with self.assertRaises(isa.Finding) as c:
            targets(img, b)
        self.assertIn("a range that wraps round the address space", str(c.exception), "255 from 0xFFFFFFF0 wraps: not placed")
        # a bounded index into the routine's OWN frame: placed, and held against the cell like any frame store
        skip = br(0x1028)
        self.placed([("cmp", "r4, #16"), ("bcs", skip), ("add", "r5, sp, #16"), ("strb", "r3, [r5, r4]")], self.GUARD)
        r, _ = self.run_with([("cmp", "r4, #16"), ("bcs", skip), ("add", "r5, sp, #0"), ("strb", "r3, [r5, r4]")])
        self.assertIn("a store that may write the slot or part of it", r, "[sp, 0..16) covers the slot at [sp, #8]")


class TheArgumentBoundedIndex(unittest.TestCase):
    """A1, the argument-bounded index (the owner's ruling of 2026-10-07): an index guarded against the routine's
    INCOMING argument — the register holding exactly what the routine received — gives a parametric extent,
    substituted where the routine is called: a constant there places the write (none when the length is zero), the
    caller's own argument keeps it parametric for the caller's callers, anything else leaves it unknown."""

    H2, F2 = 0x5000, 0x6000
    HB = 0x5000

    def writer(self, store=("strb", "r3, [r0, r4]"), lead=()):
        """h(buf = r0, len = r1): for (i = 0; i < len; i++) buf[i] = …, with `lead` before the loop."""
        lead = list(lead)
        base = self.HB + 4 * len(lead)
        return lead + [("mov", "r4, #0"), ("cmp", "r4, r1"), ("bcs", br(base + 0x18, base)), store,
                       ("add", "r4, r4, #1"), ("b", br(base + 0x4, base)), ("mov", "r0, #0"), ("bx", "lr")]

    FAR = [("movw", "r0, #40960"), ("movt", "r0, #0")]            # r0 = 0xA000, outside the stacks
    PRE = CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0")]
    POST = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]

    def go(self, lead, h=None, more=None):
        """The caller holds a callback at [sp, #8], sets up r0 / r1 with `lead`, calls h, reads the callback."""
        routines = {"h": (self.H2, h or self.writer())}
        routines.update(more or {})
        img, b = synth(self.PRE + list(lead) + [("mov", "r2, #0"), ("bl", call(self.H2, "h"))] + self.POST, more=routines)
        try:
            r = targets(img, b)
        except isa.Finding as e:
            return str(e), None
        inv = isa.settle(synth(self.PRE + list(lead) + [("mov", "r2, #0"), ("bl", call(self.H2, "h"))] + self.POST, more=routines)[0],
                         lambda im: im.write_inventory()["routines"])
        return r, inv

    def test_a_constant_length_at_the_call_places_the_write(self):
        r, inv = self.go(self.FAR + [("mov", "r1, #16")])
        self.assertEqual(r, [CB_A])
        self.assertEqual(inv["h"]["placed_by_a1_at"], {"a register index bounded by an unsigned guard against argument 1": ["0x500c"]})
        self.assertEqual((inv["h"]["at_the_callers"], inv["h"]["not_placed"]), (1, 0), "h's store is placed where h is called")
        self.assertEqual((inv["f"]["placed"], inv["f"]["not_placed"]), (2, 0), "f's frame store, and the pointer handed with 16 bytes to write")

    def test_a_zero_length_writes_nothing(self):
        r, inv = self.go(self.FAR + [("mov", "r1, #0")])
        self.assertEqual(r, [CB_A])
        self.assertEqual(inv["f"]["not_placed"], 0)

    def test_an_unknown_length_leaves_the_write_unknown(self):
        for what, lead in (("loaded from memory", self.FAR + [("ldr", "r1, [sp, #20]")]), ("the caller's register as it came", self.FAR + [("mov", "r1, r6")])):
            with self.subTest(what):
                r, _ = self.go(lead)
                self.assertIsInstance(r, str, "placed")
                self.assertIn("a call (h) handed r0, which the callee writes through, that is not placed (through the constant 0xa000, over an extent that is not bounded)", r)

    def test_a_forwarded_length_stays_parametric_until_a_caller_fixes_it(self):
        """f holds the callback and calls mid(buf, len); mid forwards both to h. The write is placed only at f."""
        mid = [("bl", call(self.H2, "h")), ("bx", "lr")]          # mid(r0, r1) -> h(r0, r1), nothing else

        def f(lead):
            routines = {"h": (self.H2, self.writer()), "mid": (self.F2, mid)}
            img, fb = synth(self.PRE + list(lead) + [("mov", "r2, #0"), ("bl", call(self.F2, "mid"))] + self.POST, more=routines)
            try:
                return targets(img, fb), isa.settle(synth(self.PRE + list(lead) + [("mov", "r2, #0"), ("bl", call(self.F2, "mid"))] + self.POST,
                                                          more=routines)[0], lambda im: im.write_inventory()["routines"])
            except isa.Finding as e:
                return str(e), None
        r, inv = f(self.FAR + [("mov", "r1, #16")])
        self.assertEqual(r, [CB_A])
        self.assertEqual((inv["mid"]["at_the_callers"], inv["mid"]["not_placed"]), (1, 0), "mid's hand-over stays parametric: placed at mid's caller")
        self.assertEqual((inv["h"]["at_the_callers"], inv["mid"]["placed"]), (1, 0))
        r, _ = f(self.FAR + [("ldr", "r1, [sp, #20]")])
        self.assertIsInstance(r, str, "placed")
        self.assertIn("a call (mid) handed r0, which the callee writes through, that is not placed", r)
        # mid on its own, called by nothing: its argument is unknown
        img, _b = synth(mid, more={"h": (self.H2, self.writer())})
        inv = isa.settle(img, lambda im: im.write_inventory()["routines"])
        self.assertIn("the routine is entered other than by a call whose arguments are read", str(inv["f"]["not_placed_at"]))

    def test_a_length_redefined_before_the_guard_bounds_nothing(self):
        for what, lead in (("replaced by an unknown", [("mov", "r1, r6")]), ("stepped by one", [("add", "r1, r1, #1")])):
            with self.subTest(what):
                r, _ = self.go(self.FAR + [("mov", "r1, #16")], h=self.writer(lead=lead))
                self.assertIsInstance(r, str, "placed")
                self.assertIn("over an extent that is not bounded", r)
        r, _ = self.go(self.FAR + [("mov", "r1, #16")], h=self.writer(lead=[("mov", "r5, r1")]))
        self.assertEqual(r, [CB_A], "a COPY of the argument is still the argument")
        # the argument on one path and something else on another: not the argument as received
        lead = [("cbz", f"r2, {br(self.HB + 0x8, self.HB)}"), ("mov", "r1, r6")]
        r, _ = self.go(self.FAR + [("mov", "r1, #16"), ("mov", "r2, #1")], h=self.writer(lead=lead))
        self.assertIsInstance(r, str, "placed")
        self.assertIn("over an extent that is not bounded", r)

    def test_a_parametric_computed_address_handed_on_is_refused_by_name_not_by_a_crash(self):
        """The owner's HOLD on f624c87, P2: h computes buf + index (index < len, its argument) and hands it to g,
        which writes through it. The hand-over's extent is a form of h's argument: carried, not subtracted from."""
        G2 = 0x6000
        h = [("mov", "r4, #0"), ("cmp", "r4, r1"), ("bcs", br(self.HB + 0x18, self.HB)), ("add", "r0, r0, r4"),
             ("bl", call(G2, "g")), ("mov", "r0, #0"), ("bx", "lr")]
        g = [("strb", "r2, [r0]"), ("mov", "r0, #0"), ("bx", "lr")]
        r, _ = self.go(self.FAR + [("mov", "r1, #16")], h=h, more={"g": (G2, g)})
        self.assertIsInstance(r, str, "placed")                  # (conservative: h's summary for buf is unbounded)
        self.assertIn("a call (h) handed r0, which the callee writes through, that is not placed", r)
        img, _b = synth(self.PRE + self.FAR + [("mov", "r1, #16"), ("mov", "r2, #0"), ("bl", call(self.H2, "h"))] + self.POST,
                        more={"h": (self.H2, h), "g": (G2, g)})
        inv = isa.settle(img, lambda im: im.write_inventory()["routines"])
        self.assertEqual(inv["h"]["placed_by_a1_at"], {"a handed address computed from an index bounded by an unsigned guard against argument 1": ["0x5010"]},
                         "h's own hand-over: a parametric extent, placed at h's callers")
        self.assertEqual((inv["h"]["at_the_callers"], inv["h"]["not_placed"]), (1, 0))

    def test_a_parametric_count_from_a_pointer_that_is_not_an_argument_is_unknown(self):
        """A constant base in the callee, a length from its argument: nothing at the call can place it."""
        far_in_h = [("movw", "r0, #40960"), ("movt", "r0, #0")]
        r, inv = self.go([("mov", "r0, #0"), ("mov", "r1, #16")], h=self.writer(lead=far_in_h))
        self.assertIsInstance(r, str, "placed")
        self.assertIn("over a length held in one of its arguments, from a pointer that is not its argument", str(inv) if inv else r)

    def test_a_parametric_element_may_write_a_cell_of_its_own_frame(self):
        """The slot walk: a store whose count is a form of an argument, into the routine's own frame at or below the
        cell, MAY write it (its end is unknown there) — `_store_effect`'s own verdict, by name."""
        h = [("mov", "r4, #0"), ("cmp", "r4, r1"), ("bcs", br(0x5018, 0x5000)), ("strb", "r3, [sp, r4]"), ("add", "r4, r4, #1"),
             ("b", br(0x5004, 0x5000)), ("mov", "r0, #0"), ("bx", "lr")]
        img, _b = synth([("bx", "lr")], more={"h": (0x5000, h)})
        img.analyse(0x5000)
        d = img._store_desc(0x5000, 0x500c)
        self.assertEqual(d.get("a1"), "a register index bounded by an unsigned guard against argument 1")
        self.assertEqual(d["elems"], [(0, ("lin", 1, 1, 0), None)])
        self.assertEqual(img._store_effect(0x5000, 0x500c, 8 - SP)[0], "may", "[sp + 0 .. sp + len): the slot at [sp, #8] may be in it")
        self.assertIsNone(img._store_effect(0x5000, 0x500c, -SP - 4), "a slot below the frame's base is not")

    def test_the_scale_and_the_width_at_the_call_against_the_table_and_the_wrap(self):
        tables = TheReadOnlyTables().run_with
        below = [("movw", "r0, #37056"), ("movt", "r0, #0")]       # r0 = T_ADDR - 64: sixteen words below the table
        words = self.writer(store=("str", "r3, [r0, r4, lsl #2]"))
        dwords = self.writer(store=("strd", "r2, r3, [r0, r4, lsl #2]"))
        for what, lead, h, want in (("sixteen words below the table", below + [("mov", "r1, #16")], words, None),
                                    ("seventeen: the table's first word", below + [("mov", "r1, #17")], words, "it may reach 0x9100..0x9104"),
                                    ("sixteen double words: four bytes too far", below + [("mov", "r1, #16")], dwords, "it may reach 0x9100..0x9104"),
                                    ("sixteen bytes, unscaled, from the top of memory", [("movw", "r0, #65520"), ("movt", "r0, #65535"), ("mov", "r1, #16")], self.writer(), None),
                                    ("seventeen: wrapping round", [("movw", "r0, #65520"), ("movt", "r0, #65535"), ("mov", "r1, #17")], self.writer(), "a range that wraps round the address space")):
            with self.subTest(what):
                r = tables([("mov", "r2, #0"), ("mov", "r3, #0")] + lead + [("bl", call(self.H2, "h"))] + TBL, more={"h": (self.H2, h)})
                if want is None:
                    self.assertEqual(r, [CB_B])
                else:
                    self.assertIsInstance(r, str, "accepted")
                    self.assertIn(want, r)


class TheDigitLoop(unittest.TestCase):
    """The ÷10 digit loop and the copy loop after it (the owner's ruling of 2026-10-07 on the search_render unit):
    read off the code as GCC emits them, they bound a frame pointer stepped once per digit (1 to 10 times) and the
    digit count, and the copy loop's pointers — so a routine's own frame stays its own and its incoming area is
    shown untouched. Anything off the pattern leaves the pointer unpinned, as before."""

    H2 = 0x5000
    MAGIC = [("movw", "lr, #52429"), ("movt", "lr, #52428")]       # lr = 0xCCCCCCCD

    def digits(self, *, magic=None, shift="#3", word="ip", update=("mov", "r1, ip"), flags=None, count=("add", "r5, r5, #1"), low=False,
               extra=(), copy_end="r5", copy_start="r5", first=("mov", "r0, sp"), store=("strb", "r3, [r0], #1"), bypass=False,
               copy_dest="#12", copy_store=("strb", "r0, [r3], #1"), step_after_cmp=False, copy_bypass=False,
               cmp_imm="#9", reenter=False, copy_extra=(), after_extra=(), body_exit=False,
               umull="umull", lsr="lsr", cmp_mn="cmp", copy_cmp="cmp"):
        """h(ctx, value): the digits of `value` into a frame buffer at sp, reversed into sp + 12, as GCC emits it."""
        H = self.H2
        pre = list(magic or self.MAGIC) + [("mov", "r4, r0"), ("mov", "r2, sp"), first, ("mov", "r5, #0")]
        L = H + 4 * len(pre)
        body = [(umull, f"r3, {word}, lr, r1" if not low else f"{word}, r3, lr, r1"), (cmp_mn, f"r1, {cmp_imm}"), count, (lsr, f"ip, {word}, {shift}"),
                ("add", "r3, ip, ip, lsl #2"), ("sub", "r3, r1, r3, lsl #1"), update, ("add", "r3, r3, #48")] + list(extra) + [store]
        if flags:
            body.insert(2, flags)
        if body_exit:                                      # leaves the body before the count is stepped
            body.insert(1, ("cbz", f"r6, {br(L + 4 * (len(body) + 2), H)}"))
        body = pre + body + [("bhi", br(L, H))]
        if reenter:                                        # back into the loop's head from below it
            body.append(("cbnz", f"r6, {br(L, H)}"))
        if bypass:                                         # a jump from before the loop into its middle
            body = [("cbz", f"r6, {br(L + 8, H)}")] + [x if x != ("bhi", br(L, H)) else ("bhi", br(L + 4, H)) for x in body]
            L += 4
        after = [("add", "r1, sp, " + copy_dest), ("add", "r2, r2, " + copy_start)] + list(after_extra) + [("mov", "r3, r1"), ("add", "ip, r1, " + copy_end)]
        if copy_bypass:                                    # a jump from before the copy loop into its middle
            after.insert(0, ("cbz", f"r6, {br(H + 4 * (len(body) + len(after) + 2), H)}"))
        L2 = H + 4 * (len(body) + len(after))
        loop = [("ldrb", "r0, [r2, #-1]!"), copy_store] + list(copy_extra) + [(copy_cmp, "r3, ip")]
        if step_after_cmp:
            loop = [("ldrb", "r0, [r2, #-1]!"), ("cmp", "r3, ip"), ("strb", "r0, [r3], #1")]
        return body + after + loop + [("bne", br(L2, H)), ("mov", "r0, #0"), ("bx", "lr")]

    def facts(self, h):
        img, _b = synth([("bx", "lr")], more={"h": (self.H2, h)})
        img.analyse(self.H2)
        d, c = img._div10_loops(self.H2), img._copy_loops(self.H2)
        return d, c, img._stack_use_compute(self.H2), img

    def test_the_loops_as_gcc_emits_them_pin_the_frame(self):
        d, c, use, img = self.facts(self.digits())
        (info,), = [list(d.values())]
        self.assertEqual((info["q"], info["ptr"], info["count"]), ("r1", {"r0": 1}, {"r5": 0}))
        (cinfo,), = [list(c.values())]
        self.assertEqual((cinfo["p"], cinfo["e"], cinfo["count"][:3], cinfo["A"]), ("r3", "ip", ("r5", 1, 10), 12 - SP))
        self.assertEqual(use, (frozenset(), frozenset()), "no incoming word is read or written")
        store = [i for i in img.region(self.H2) if i["mnem"] == "strb" and i["ops"] == "r3, [r0], #1"][0]["addr"]
        self.assertEqual(img._loop_frame_span(self.H2, store, "r0"), (-SP, -SP + 9, "a pointer stepped by a ÷10 digit loop"))
        dsc = img._store_desc(self.H2, store)
        self.assertEqual((sorted(dsc["base"]), dsc["elems"], dsc["a1"]), ([("frame", -SP)], [(0, 10, None)], "a pointer stepped by a ÷10 digit loop"))
        copy = [i for i in img.region(self.H2) if i["mnem"] == "strb" and i["ops"] == "r0, [r3], #1"][0]["addr"]
        self.assertEqual(img._loop_frame_span(self.H2, copy, "r3"), (12 - SP, 21 - SP, "a pointer stepped by the copy loop after a ÷10 digit loop"))
        self.assertEqual(img._loop_frame_span(self.H2, copy - 4, "r2"), (1 - SP, 10 - SP, "a pointer stepped back by the copy loop after a ÷10 digit loop"))
        after = [i for i in img.region(self.H2) if i["mnem"] == "add" and i["ops"] == "ip, r1, r5"][0]["addr"]
        self.assertEqual(img._reg_range(self.H2, after, "r5"), (1, 10, "the digit count of a ÷10 loop"))

    def test_a_caller_s_object_survives_such_a_callee(self):
        """f holds a callback and hands its frame object to h; h's incoming area is shown untouched: resolved."""
        for what, h, want in (("the loops as emitted", self.digits(), [CB_A]),
                              ("a wrong multiplier", self.digits(magic=[("movw", "lr, #52428"), ("movt", "lr, #52428")]), None),
                              ("the low word", self.digits(low=True), None)):
            with self.subTest(what):
                img, b = synth(CB + [("str", "r0, [sp, #8]"), ("add", "r0, sp, #8"), ("mov", "r1, #1234"), ("bl", call(self.H2, "h")),
                                     ("ldr", "r1, [sp, #8]"), ("blx", "r1")], more={"h": (self.H2, h)})
                if want is not None:
                    self.assertEqual(targets(img, b), want)
                else:
                    with self.assertRaises(isa.Finding) as c:
                        targets(img, b)
                    self.assertIn("a call that may write the slot through a pointer it is handed, or its incoming stack words", str(c.exception))

    def test_what_is_off_the_pattern_is_not_a_digit_loop(self):
        for what, kw in (("a wrong multiplier", {"magic": [("movw", "lr, #52428"), ("movt", "lr, #52428")]}),
                         ("a wrong shift", {"shift": "#2"}),
                         ("the low word of the product", {"low": True}),
                         ("an update that is not the quotient", {"update": ("mov", "r1, r3")}),
                         ("flags set between the compare and the branch", {"flags": ("cmp", "r5, #3")}),
                         ("a branch into the body", {"bypass": True}),
                         ("a compare against another constant (#0: one run more than the digits)", {"cmp_imm": "#0"}),
                         ("the head entered again from below the loop", {"reenter": True}),
                         ("a branch out of the body before the count is stepped", {"body_exit": True}),
                         ("a second step of the pointer in the body", {"extra": [("add", "r0, r0, #1")]})):
            with self.subTest(what):
                d, _c, use, _img = self.facts(self.digits(**kw))
                if what == "a second step of the pointer in the body":
                    self.assertEqual(list(d.values())[0]["ptr"], {}, "the pointer is not one the loop steps once")
                else:
                    self.assertEqual(d, {}, "recognised")
                self.assertIsNone(use[1], "its writes to the incoming area are not pinned")

    def test_the_count_and_the_copy_loop_s_ends(self):
        for what, kw, copies in (("the count stepped twice", {"count": ("add", "r5, r5, #2")}, 0),
                                 ("the count not stepped", {"count": ("nop", "")}, 0),
                                 ("the copy's end from another count", {"copy_end": "r6"}, 0),
                                 ("the copy's start from another count", {"copy_start": "r6"}, 1)):
            with self.subTest(what):
                d, c, use, img = self.facts(self.digits(**kw))
                self.assertEqual(len(c), copies)
                if what == "the copy's start from another count":
                    load = [i for i in img.region(self.H2) if i["mnem"] == "ldrb"][0]["addr"]
                    self.assertIsNone(img._loop_frame_span(self.H2, load, "r2"), "a pointer from a different count is not placed")
                self.assertIsNone(use[0], "its reads of the incoming area are not pinned")

    def test_the_pointer_from_the_loop_stays_in_its_frame_and_a_wider_store_does_not(self):
        """The range is pinned either way; one that leaves the routine's own frame is the caller's (its incoming
        words, held against the caller's slots) and is not PLACED (write placement: 'a range that leaves the frame')."""
        def placed(h):
            d, _c, use, img = self.facts(h)
            self.assertTrue(d, "recognised")
            img2, _b = synth([("bx", "lr")], more={"h": (self.H2, h)})
            sites = isa.settle(img2, lambda im: [(a, reach) for a, what, reach, _m in im._write_sites(self.H2) if what == "stores"])
            return use, [r for a, reach in sites for r in reach if r[0] == "unknown"]
        use, unknown = placed(self.digits(first=("add", "r0, sp, #250")))        # 250 + 10 digits: past the frame's top
        self.assertEqual(use[1], frozenset({0}), "the tenth digit lands in the incoming area: the caller's word 0")
        self.assertIn(("unknown", "through an address of its frame, over a range that leaves the frame"), unknown)
        use, unknown = placed(self.digits(first=("add", "r0, sp, #246")))        # 246 + 10 = 256: the frame's last byte
        self.assertEqual((use, unknown), ((frozenset(), frozenset()), []))
        use, unknown = placed(self.digits(store=("str", "r3, [r0], #1")))        # a word, stepped by one: 13 bytes
        self.assertEqual((use, unknown), ((frozenset(), frozenset()), []), "still inside: 0 .. 13 of 256")
        use, unknown = placed(self.digits(first=("add", "r0, sp, #244"), store=("str", "r3, [r0], #1")))
        self.assertEqual(use[1], frozenset({0}), "244 + 9 + 4 = 257: the last word's last byte is the caller's")
        self.assertIn(("unknown", "through an address of its frame, over a range that leaves the frame"), unknown)

    def test_pre_and_post_index_and_the_copy_loop_s_own_bounds(self):
        """The span is the BASE register's value before the access; a pre-indexed access adds its own offset."""
        _d, c, use, img = self.facts(self.digits(copy_store=("strb", "r0, [r3, #1]!")))        # A + 1 .. A + c
        self.assertEqual(len(c), 1)
        self.assertEqual(use, (frozenset(), frozenset()))
        st = [i for i in img.region(self.H2) if i["ops"] == "r0, [r3, #1]!"][0]["addr"]
        self.assertEqual(img._loop_frame_span(self.H2, st, "r3")[:2], (12 - SP, 21 - SP))
        dsc = img._store_desc(self.H2, st)
        self.assertEqual(dsc["elems"], [(1, 10, None)], "base 12 - SP .. 21 - SP, plus the pre-index 1: 13 .. 22")
        ld = [i for i in img.region(self.H2) if i["mnem"] == "ldrb"][0]["addr"]
        self.assertEqual(img._loop_frame_span(self.H2, ld, "r2")[:2], (1 - SP, 10 - SP), "from sp + c back to sp + 1, pre-indexed by -1: sp .. sp + 9")
        for what, kw, room in (("bytes ending at the frame's top", {"copy_dest": "#246"}, True),
                               ("bytes one past it", {"copy_dest": "#247"}, False),
                               ("pre-indexed bytes ending at the top", {"copy_dest": "#245", "copy_store": ("strb", "r0, [r3, #1]!")}, True),
                               ("pre-indexed bytes one past it", {"copy_dest": "#246", "copy_store": ("strb", "r0, [r3, #1]!")}, False),
                               ("words ending at the top", {"copy_dest": "#243", "copy_store": ("str", "r0, [r3], #1")}, True),
                               ("words one byte past it", {"copy_dest": "#244", "copy_store": ("str", "r0, [r3], #1")}, False)):
            with self.subTest(what):
                _d, c, use, _img = self.facts(self.digits(**kw))
                self.assertEqual(len(c), 1, "recognised")
                self.assertEqual(use[1] == frozenset(), room, use)

    def test_a_copy_loop_off_the_pattern(self):
        for what, kw in (("the pointer stepped after the compare (count + 1 runs)", {"step_after_cmp": True}),
                         ("a branch into the copy loop", {"copy_bypass": True}),
                         ("the end from another count", {"copy_end": "r6"}),
                         ("the end moved in the body", {"copy_extra": [("add", "ip, ip, #1")]})):
            with self.subTest(what):
                _d, c, use, _img = self.facts(self.digits(**kw))
                self.assertEqual(c, {}, "recognised")
                self.assertIsNone(use[1] if what != "the end from another count" else use[0])
        # the reverse pointer from the SAME register but another definition of it: the count was stepped in between
        _d, c, use, img = self.facts(self.digits(after_extra=[("add", "r5, r5, #1")]))
        self.assertEqual(len(c), 1, "the copy loop itself: its end is r1 + the stepped count, which is still a count")
        ld = [i for i in img.region(self.H2) if i["mnem"] == "ldrb"][0]["addr"]
        self.assertIsNone(img._loop_frame_span(self.H2, ld, "r2"), "r2 = sp + the count BEFORE the step: not the end's count")
        self.assertIsNone(use[0])

    def test_what_runs_only_under_a_condition_or_steps_the_other_way(self):
        """The owner's HOLD on 4c9ee82: an instruction the rule relies on must run on EVERY pass (a conditional one
        may not — `moveq r1, ip` never runs for 1234, the loop never ends); a step is read from its opcode, its
        direction and its writeback (`sub r3, r3, #1` steps back)."""
        for what, kw in (("the quotient's update only on EQ (the owner's probe)", {"update": ("moveq", "r1, ip")}),
                         ("the multiply under a condition", {"umull": "umulleq"}),
                         ("the shift under a condition", {"lsr": "lsrne"}),
                         ("the compare under a condition", {"cmp_mn": "cmpne"}),
                         ("the pointer's step under a condition", {"store": ("strbeq", "r3, [r0], #1")}),
                         ("the pointer stepped back", {"store": ("strb", "r3, [r0], #-1")})):
            with self.subTest(what):
                d, _c, use, _img = self.facts(self.digits(**kw))
                if what in ("the pointer's step under a condition", "the pointer stepped back"):
                    self.assertEqual(list(d.values())[0]["ptr"] if d else {}, {}, "a pointer the loop steps forward on every pass")
                else:
                    self.assertEqual(d, {}, "recognised")
                self.assertIsNone(use[1], "the digit store is not pinned")
        d, _c, _use, _img = self.facts(self.digits(count=("addeq", "r5, r5, #1")))
        self.assertEqual(list(d.values())[0]["count"], {}, "a count stepped under a condition is not the digit count")
        for what, kw in (("the copy's pointer stepped back by a sub (the owner's probe)", {"copy_store": ("sub", "r3, r3, #1")}),
                         ("stepped back by a post-indexed store", {"copy_store": ("strb", "r0, [r3], #-1")}),
                         ("stepped under a condition", {"copy_store": ("strbeq", "r0, [r3], #1")}),
                         ("the copy's compare under a condition", {"copy_cmp": "cmpeq"})):
            with self.subTest(what):
                _d, c, use, img = self.facts(self.digits(**kw))
                self.assertEqual(c, {}, "recognised")
                ld = [i for i in img.region(self.H2) if i["mnem"] == "ldrb"][0]["addr"]
                self.assertIsNone(img._loop_frame_span(self.H2, ld, "r2"), "the reverse load is not placed")
                self.assertIsNone(use[0], "its reads of the incoming area are not pinned")
        # the controls: a forward step by an add, and by a pre-indexed store, are the loop's
        _d, c, use, _img = self.facts(self.digits(copy_store=("add", "r3, r3, #1")))
        self.assertEqual((len(c), use), (1, (frozenset(), frozenset())))
        _d, c, use, _img = self.facts(self.digits(copy_store=("strb", "r0, [r3, #1]!")))
        self.assertEqual((len(c), use), (1, (frozenset(), frozenset())))

    def test_the_owner_s_probes_through_the_formal_path(self):
        """The two probes of the HOLD, through callback resolution, in A32 (predicated without IT)."""
        def run(**kw):
            img, b = synth(CB + [("str", "r0, [sp, #8]"), ("add", "r0, sp, #8"), ("mov", "r1, #1234"), ("bl", call(self.H2, "h")),
                                 ("ldr", "r1, [sp, #8]"), ("blx", "r1")], more={"h": (self.H2, self.digits(**kw))})
            for ins in img.ins_at.values():
                ins["thumb"] = False
            try:
                return targets(img, b)
            except isa.Finding as e:
                return str(e)
        self.assertEqual(run(), [CB_A], "the loops as emitted")
        r = run(update=("moveq", "r1, ip"))
        self.assertIsInstance(r, str, "resolved")
        self.assertIn("a call that may write the slot through a pointer it is handed, or its incoming stack words", r)
        self.assertIsInstance(run(copy_store=("strb", "r0, [r3], #-1")), str, "a copy store stepping down: unbounded writes")

    def test_the_magic_constant_divides_every_32_bit_value_by_ten(self):
        """(x * 0xCCCCCCCD) >> 35 == x // 10 for EVERY unsigned 32-bit x: exhaustive, not sampled."""
        import numpy as np
        magic = np.uint64(isa.Image.MAGIC10)
        step = 1 << 24
        for lo in range(0, 1 << 32, step):
            x = np.arange(lo, lo + step, dtype=np.uint64)
            self.assertTrue(np.array_equal((x * magic) >> np.uint64(35), x // np.uint64(10)), f"at {lo:#x}")
        self.assertEqual(isa.Image.MAGIC10, -(-(1 << 35) // 10))


class TheWalkPastAFinding(unittest.TestCase):
    """`depth` with a collector lists every finding it can decide independently: a refused edge leaves what is under
    it unwalked (and says so), the other edges are walked on, and the node and all above it are tainted — the number
    for a tainted node is not a bound. Without a collector the first finding ends the walk, as before."""

    A2, B2, D2 = 0x5000, 0x6000, 0x7000

    def build(self):
        # f calls a and d; a's own pointer call is refused, and AFTER it a calls b, whose pointer call is refused too
        bad = CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [r6]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        good = CB + [("str", "r0, [sp, #8]"), ("ldr", "r1, [sp, #8]"), ("blx", "r1"), ("bx", "lr")]
        return synth([("bl", call(self.A2, "a")), ("bl", call(self.D2, "d")), ("bx", "lr")],
                     more={"a": (self.A2, bad + [("bl", call(self.B2, "b")), ("bx", "lr")]),
                           "b": (self.B2, [("mov", "r3, #0")] + bad + [("bx", "lr")]), "d": (self.D2, good)})

    def test_every_independent_finding_is_listed_and_the_path_is_tainted(self):
        img, f = self.build()

        def run(im):
            memo, got = {}, {}
            d = im.depth(f, None, (), memo, got)
            return d, got, memo[im.TAINTED], im.depth(self.D2, None, (), memo, got), len(got)
        d, got, tainted, d_clean, n = isa.settle(img, run)
        self.assertEqual(len(got), 2, got)
        (ma, la), (mb, lb) = got.items()                   # {the finding: what is left unwalked because of it}
        self.assertIn("a: the callback loaded at 0x5014", ma)
        self.assertIn("at 0x5010 a store that is not placed (through an unknown pointer)", ma)
        self.assertEqual(la, ["what a's call at 0x5018 reaches"])
        self.assertIn("b: the callback loaded at 0x6018", mb)
        self.assertEqual(lb, ["what b's call at 0x601c reaches"])
        root = isa.Image.ROOT_CTX
        self.assertIn((f, root), tainted)
        self.assertIn((self.A2, (frozenset(), False)), tainted)
        self.assertIn((self.B2, (frozenset(), False)), tainted, "a's later edge was walked on after its refused one")
        self.assertNotIn((self.D2, (frozenset(), False)), tainted, "the clean callee was walked and is not tainted")
        self.assertEqual((d_clean, n), (SP + SP, 2), "a clean routine still has its depth, and adds no finding")
        self.assertGreaterEqual(d, 3 * SP, "f -> a -> b was walked to the bottom")

    def test_without_a_collector_the_first_finding_ends_the_walk(self):
        img, f = self.build()
        with self.assertRaises(isa.Finding) as c:
            isa.settle(img, lambda im: im.depth(f, None, (), {}))
        self.assertIn("a: the callback loaded at 0x5014", str(c.exception))


class TheGateOnTheInventory(unittest.TestCase):
    """What withholds a bound is computed, reason by reason: with the same image, an inventory that has nothing
    unproved and a cell list with nothing unresolved, the exception entries are withheld for the one reason left —
    the synchronous-paths scope, under which no entry calling through memory is published — and main stays refused
    by the table proof and the frame cells, which read the writes themselves."""

    def test_clean_lists_leave_only_the_scope_and_publish_nothing(self):
        clean = {"protected": [], "stacks": None, "routines": {}, "total": {"not_placed_sites": 0}, "unproved": 0}
        with mock.patch.object(isa.Image, "write_inventory", lambda self: copy.deepcopy(clean)), \
                mock.patch.object(isa.Image, "frame_cells", lambda self: []):
            r = isa.assess_image(isa.Image(ELF))
        for exc in ("undefined", "svc", "prefetch_abort", "data_abort", "irq", "fiq"):
            self.assertIsNone(r["entries"][exc]["bound"], exc)
            self.assertEqual(r["entries"][exc]["unpublished"], 24)
            (why,) = [f for f in r["findings"] if f.startswith(f"{exc} (") and "no bound is published" in f]
            self.assertIn("synchronous paths only", why)
            self.assertNotIn("are not proved to miss those cells", why, "the inventory's reason is the inventory's")
            self.assertNotIn("frame cell(s) are not resolved", why, "the cells' reason is the cells'")
        self.assertFalse(any("the frame cell at slot" in f or "write(s) not placed" in f for f in r["findings"]))
        self.assertIsNone(r["entries"]["main"]["bound"])
        self.assertNotIn("unpublished", r["entries"]["main"])
        self.assertFalse(r["ok"])
        self.assertTrue(any(f.startswith("main (_start): ") and "may be written" in f for f in r["findings"]))


class TheAssessmentCache(unittest.TestCase):
    """The owner's HOLD on 78c2bb0, P2: a cached assessment is shared only by a call with the SAME proof inputs — the
    ELF, the analyzer and its tables, each contract unit's current source digest, the archives, the newlib header, the
    tools. (The analysis itself is stubbed here: what is under test is which calls reach it.)"""

    def setUp(self):
        self.calls = []
        isa._ASSESS_CACHE.clear()
        self.addCleanup(isa._ASSESS_CACHE.clear)
        for p in (mock.patch.object(isa.Image, "__init__", lambda im, elf: None),     # (the class and its tables stay real)
                  mock.patch.object(isa, "assess_image", side_effect=lambda img: self.calls.append(img) or {"n": len(self.calls)})):
            p.start()
            self.addCleanup(p.stop)

    def test_equal_inputs_share_one_assessment(self):
        self.assertEqual(isa.assess(ELF), {"n": 1})
        self.assertEqual(isa.assess(ELF), {"n": 1})
        self.assertEqual(len(self.calls), 1)

    def test_any_changed_input_is_assessed_afresh(self):
        import tempfile
        with tempfile.TemporaryDirectory(dir=R / "build") as d:
            other = Path(d) / "other"
            other.write_bytes(b"not the same bytes")
            twin = Path(d) / "twin"                        # another root holding byte-identical contract units: only
            for u in isa.Image.CONTRACT_SOURCES:           # the root differs (and with it what the ELF's units map to)
                (twin / u).parent.mkdir(parents=True, exist_ok=True)
                (twin / u).write_bytes((isa.REPO_ROOT / u).read_bytes())
            real_sha = isa.sha256_file
            changes = {
                "a contract unit's source": mock.patch.object(isa.Image, "_unit_sha", return_value="0" * 64),
                "one contract unit's source": mock.patch.object(isa.Image, "_unit_sha", side_effect=lambda _s, u: "1" * 64 if u == APP else "2" * 64),
                "a contract": mock.patch.dict(isa.Image.CONTRACTS, {"sha_emit": dict(isa.Image.CONTRACTS["sha_emit"], arity=9)}),
                "a contract's bound source digest": mock.patch.dict(isa.Image.CONTRACT_SOURCES, {APP: "3" * 64}),
                "a contract's bound code digest": mock.patch.dict(isa.Image.CONTRACT_CODE, {"sha_emit": "4" * 64}),
                "a library contract": mock.patch.dict(isa.Image.LIBC_CONTRACTS, {"memcpy": ("x.o", 0, 2, "arg0", None)}),
                "the main limit": mock.patch.object(isa, "MAIN_LIMIT", 0x4000),
                "the tool version": mock.patch.object(isa, "TOOL_VERSION", "another"),
                "the source root": mock.patch.object(isa, "REPO_ROOT", twin),
                "an archive": mock.patch.object(isa, "runtime_archives", return_value={"libc.a": other, "libgcc.a": other}),
                **{f"the bytes of {what}": mock.patch.object(
                    isa, "sha256_file", side_effect=lambda p, _f=Path(f): "5" * 64 if Path(p) == _f else real_sha(p))
                   for what, f in [("the analyzer", isa.__file__), ("the compiler", be.trusted_compiler()),
                                   ("the newlib version header", Path(isa.b2be.TC) / isa.Image.NEWLIB["version_header"])]
                   + [(f"binutils' {n}", isa.tool(n)) for n in ("objdump", "nm", "readelf", "ar")]},
                "the build's flags": mock.patch.object(be, "build_flags", return_value=(["-O0"], ["-O0"])),
            }
            self.assertEqual(isa.assess(ELF), {"n": 1})
            n = 1
            for what, patch in changes.items():
                with self.subTest(what), patch:
                    n += 1
                    self.assertEqual(isa.assess(ELF), {"n": n}, "a cached result of other inputs was returned")
                    self.assertEqual(isa.assess(ELF), {"n": n}, "the same changed inputs: one assessment")
            self.assertEqual(isa.assess(other), {"n": n + 1}, "another ELF")
            self.assertEqual(isa.assess(ELF), {"n": 1}, "the first inputs again: the first assessment")
            self.assertEqual(len(self.calls), n + 1)

    def test_inputs_that_cannot_be_read_are_never_cached(self):
        with mock.patch.object(isa, "runtime_archives", side_effect=RuntimeError("no archive")):
            self.assertEqual(isa.assess(ELF), {"n": 1})
            self.assertEqual(isa.assess(ELF), {"n": 2})
        self.assertEqual(isa._ASSESS_CACHE, {})

    def test_the_source_root_is_the_one_the_elf_names(self):
        """A contract is bound to a unit by its repository-relative path, and a unit gets that path only when the
        ELF's own DWARF names it under THIS root: an image built from sources elsewhere has no contract unit here."""
        self.assertEqual(isa.unit_name(str(isa.REPO_ROOT / APP)), APP)
        self.assertIn(APP, isa.Image.CONTRACT_SOURCES)
        elsewhere = isa.unit_name("/elsewhere/" + APP)
        self.assertEqual(elsewhere, "b3_app.c")
        self.assertNotIn(elsewhere, isa.Image.CONTRACT_SOURCES)
        self.assertNotIn(elsewhere, isa.Image.APP_UNITS)


FMT2 = 0x19004                                            # a second format, in another 64 KiB page


class ThePrintfFormatProof(unittest.TestCase):
    """A printf-family call is taken at its contract only where its format is a read-only constant with no %n on
    every path — the conditional halves of a movw / movt pair correlated by their condition, a register a callee
    leaves untouched (GCC's inter-procedural register allocation) kept across that call."""

    SN = 0x7000

    def run_with(self, lead, more=None, strings=None):
        hand = [("add", "r3, sp, #8"), ("add", "r0, sp, #64"), ("mov", "r1, #16")]
        seq = CB + [("str", "r0, [sp, #8]")] + lead + hand + [("bl", call(self.SN, "snprintf")),
                                                              ("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        routines = {"snprintf": (self.SN, [("bx", "lr")])}
        routines.update(more or {})
        img, b = synth(seq, more=routines, library=("snprintf",))
        img._member_of[self.SN] = "libc.a(libc_a-snprintf.o)"
        table = strings or {0x9000: "%s", FMT2: "%d"}
        img._cstring = lambda a, table=table: table.get(a)
        try:
            return targets(img, b)
        except isa.Finding as e:
            return str(e)

    def test_correlated_conditional_halves(self):
        lead = [("cmp", "r5, #0"), ("movwge", "r2, #36864"), ("movwlt", "r2, #36868"), ("movtge", "r2, #0"),
                ("movtlt", "r2, #1")]                       # ge: 0x9000; lt: 0x19004 — never 0x19000 or 0x9004
        self.assertEqual(self.run_with(lead), [CB_A])
        self.assertIsInstance(self.run_with(lead, strings={0x9000: "%s", FMT2: "%n"}), str, "a %n on one path")
        mixed = [("cmp", "r5, #0"), ("movwge", "r2, #36864"), ("cmp", "r6, #0"), ("movtlt", "r2, #1")]
        self.assertIsInstance(self.run_with(mixed), str, "halves under different flags: not one constant")

    def test_a_register_a_callee_leaves_alone(self):
        H2 = 0x5000
        lead = [("movw", "r2, #36864"), ("movt", "r2, #0"), ("bl", call(H2, "h"))]
        self.assertEqual(self.run_with(lead, more={"h": (H2, [("mov", "r0, #1"), ("bx", "lr")])}), [CB_A])
        self.assertIsInstance(self.run_with(lead, more={"h": (H2, [("mov", "r2, #1"), ("bx", "lr")])}), str,
                              "a callee that writes r2")


class TheSpeculation(unittest.TestCase):
    """A fact that depends on itself is guessed (its optimistic placeholder first), every guess is recorded and
    checked against the fact's final value when the pass is over, and a pass with a wrong guess is thrown away:
    the next one starts from the final values. Exercised on the mechanism itself: a fact whose computation reads
    itself, through `_guarded`."""

    @staticmethod
    def fact(rule):
        """A one-fact image: fact ('x', 1) computes rule(the value it reads of itself); returns (the outer result
        — the value READ inside, which an unverified pass would hand out —, the fact's final value)."""
        def fn(im):
            seen = []

            def compute(_key):
                inner = im._guarded("x", 1, compute, False)
                seen.append(inner)
                return rule(inner)
            final = im._guarded("x", 1, compute, False)
            return seen[0], final
        return fn

    def test_a_consistent_guess_is_accepted_at_once(self):
        img = isa.Image.__new__(isa.Image)
        self.assertEqual(isa.settle(img, self.fact(lambda g: g)), (False, False))

    def test_a_wrong_guess_is_thrown_away(self):
        img = isa.Image.__new__(isa.Image)
        first = copy.deepcopy(img)
        self.assertEqual(self.fact(lambda g: True)(first), (False, True), "the first pass read False and computed True")
        self.assertEqual(first._speculation_failed(), {("x", 1): True}, "its guess is seen to be wrong")
        self.assertEqual(isa.settle(img, self.fact(lambda g: True)), (True, True), "the settled pass reads what it computes")

    def test_a_contradiction_never_settles(self):
        img = isa.Image.__new__(isa.Image)
        with self.assertRaises(isa.Finding) as c:
            isa.settle(img, self.fact(lambda g: not g))
        self.assertIn("did not settle", str(c.exception))


def find(img, routine, mnem, ops, nth=0):
    """The one instruction of `routine` with exactly this text (the nth, when several)."""
    hits = [i for i in img.region(img.syms[routine][0] & ~1) if i["mnem"] == mnem and i["ops"] == ops]
    if len(hits) <= nth:
        raise AssertionError(f"{routine}: no {mnem} {ops!r} (#{nth}) — the image is not the one these alterations were written for")
    return hits[nth]


class TheNewlibRuleRefuses(unittest.TestCase):
    """Each alteration of the final image breaks ONE sub-proof of the newlib bounded rule (or the cycle rule), and
    that sub-proof fails BY NAME. _vfiprintf_r is reached only through fiprintf, so the depth from fiprintf — the same
    depth computation, the same rule, the same refusal the main path meets on its way there — is what each
    alteration is judged by: it must raise, i.e. no bound is published for any entry that reaches it. One alteration
    (`test_end_to_end`) is also run through the WHOLE assessment, the main path and the build evidence's stack block
    included."""

    @classmethod
    def setUpClass(cls):
        cls.pristine = isa.Image(ELF)
        cls.F = cls.pristine.syms["fiprintf"][0] & ~1
        cls.ref_depth, cls.ref = isa.settle(cls.pristine, lambda im: (im.depth(cls.F, None, (), {}), im))

    def depth(self, img):
        return isa.settle(img, lambda im: im.depth(self.F, None, (), {}))

    def altered(self, *changes):
        """A fresh copy of the image with the named instructions rewritten (each anchored on its own text). Whose
        code each routine is (the archive member) is the unaltered image's: the alteration is to the sub-proof."""
        img = copy.deepcopy(self.pristine)
        img._member_of = dict(self.ref._member_of)
        for routine, old, new, *nth in changes:
            i = find(img, routine, old[0], old[1], *(nth or [0]))
            i["mnem"], i["ops"] = new
        return img

    def refuses(self, why, *changes):
        img = self.altered(*changes)
        with self.assertRaises(isa.Finding) as c:
            self.depth(img)
        self.assertIn(why, str(c.exception), "the sub-proof that fails is the one the alteration breaks")
        return img

    def test_the_unaltered_copy_is_accepted_with_the_same_bound(self):
        self.assertGreater(self.ref_depth, 0)
        self.assertEqual(self.depth(self.altered()), self.ref_depth)

    def test_end_to_end(self):
        img = self.altered(("__swsetup_r", ("ldrmi", "r2, [r4, #16]"), ("movmi", "r2, #0")))   # a tested constant 0
        r = isa.assess_image(img)
        self.assertFalse(r["ok"])
        self.assertTrue(any(self.GATE in f for f in r["findings"]), r["findings"])
        self.assertIsNone(r["entries"]["main"]["bound"], "no bound is published for the main path")
        with mock.patch.object(isa, "assess", return_value=r):
            stk = be.stack_block()
        self.assertEqual((stk["status"], stk["complete"]), ("FINDINGS", False), "the image would not be ready")

    # -- __swsetup_r: __smakebuf_r runs only when the FILE's buffer is NULL
    GATE = "gating __smakebuf_r"
    LOAD = ("__swsetup_r", ("ldrmi", "r2, [r4, #16]"))

    def test_a_tested_constant_made_zero(self):
        self.refuses(self.GATE, (*self.LOAD, ("movmi", "r2, #0")))

    def test_a_nonzero_tested_constant_is_still_accepted(self):
        img = self.altered((*self.LOAD, ("movmi", "r2, #9")))          # the control: zero is what is refused
        self.assertEqual(self.depth(img), self.ref_depth)

    def test_the_wrong_file(self):
        self.refuses(self.GATE, (*self.LOAD, ("ldrmi", "r2, [r5, #16]")))

    def test_the_wrong_offset(self):
        self.refuses(self.GATE, (*self.LOAD, ("ldrmi", "r2, [r4, #20]")))

    def test_an_unknown_value_in_the_tested_register(self):
        self.refuses(self.GATE, ("__swsetup_r", ("movs", "r1, #0"), ("movs", "r2, r1")))

    def test_a_store_to_the_buffer_field_before_the_test(self):
        self.refuses("writes the FILE's buffer field before the NULL test",
                     ("__swsetup_r", ("str", "r2, [r4, #48]"), ("str", "r2, [r4, #16]")))

    def test_a_flag_store_that_may_set_snbf(self):
        self.refuses("may set __SNBF", ("__swsetup_r", ("orr.w", "r3, r3, #8"), ("orr.w", "r3, r3, #10")))

    # -- __sbprintf: the fake FILE
    def test_the_fake_flags_overwritten(self):
        self.refuses("flags are not written once", ("__sbprintf", ("strh.w", "r3, [sp, #14]"), ("strh.w", "r3, [sp, #12]")))

    def test_the_fake_flags_without_snbf_cleared(self):
        self.refuses("not the caller's with __SNBF cleared", ("__sbprintf", ("bic.w", "r3, r3, #2"), ("bic.w", "r3, r3, #4")))

    def test_the_fake_buffer_made_null(self):
        self.refuses("buffer is not an address in __sbprintf's frame", ("__sbprintf", ("add", "r3, sp, #104"), ("movs", "r3, #0")))

    def test_another_file_handed_over(self):
        self.refuses("does not pass its own frame as the FILE", ("__sbprintf", ("mov", "r1, sp"), ("mov", "r1, r5"), 0))

    # -- _vfiprintf_r: the guard
    def test_the_guard_on_another_mask(self):
        self.refuses("is not of (flags & (__SNBF|__SWR|__SRW))", ("_vfiprintf_r", ("and.w", "r3, r2, #26"), ("and.w", "r3, r2, #24"), 1))

    def test_the_guard_compare_removed(self):
        self.refuses("no guard", ("_vfiprintf_r", ("cmp", "r3, #10"), ("cmp", "r3, #8"), 1))

    def test_a_branch_round_the_guard(self):
        i = find(self.pristine, "_vfiprintf_r", "bl", [x for x in self.pristine.region(self.pristine.syms["_vfiprintf_r"][0] & ~1)
                                                    if x["mnem"] == "bl" and "<__sbprintf>" in x["ops"]][0]["ops"])
        block = i["addr"] - 8                                          # the `ldr r1, [sp, #20]` that begins the call
        self.assertEqual(self.pristine.ins_at[block]["ops"], "r1, [sp, #20]")
        V = self.pristine.syms["_vfiprintf_r"][0] & ~1
        jump = [x for x in self.pristine.region(V) if x["mnem"] == "b.n" and x["addr"] < block][-1]
        self.refuses("no guard", ("_vfiprintf_r", (jump["mnem"], jump["ops"]), ("b.n", f"{block:x} <_vfiprintf_r+{block - V:#x}>"),
                                  [x["addr"] for x in self.pristine.region(V) if (x["mnem"], x["ops"]) == (jump["mnem"], jump["ops"])].index(jump["addr"])))

    # -- the activations and other cycles
    def test_a_second_call_site_of_sbprintf(self):
        V, S = (self.pristine.syms[n][0] & ~1 for n in ("_vfiprintf_r", "__sbprintf"))
        sprint = [x for x in self.pristine.region(V) if x["mnem"] == "bl" and "<__sprint_r>" in x["ops"]][0]
        self.refuses("not one call site", ("_vfiprintf_r", ("bl", sprint["ops"]), ("bl", f"{S:x} <__sbprintf>")))

    def test_another_caller_of_sbprintf(self):
        S = self.pristine.syms["__sbprintf"][0] & ~1
        i = [x for x in self.pristine.region(self.pristine.syms["__sprint_r"][0] & ~1) if x["mnem"] in ("bl", "b.w", "b.n", "b")
             and "<__sfvwrite_r>" in x["ops"]][0]
        self.refuses("a caller other than the one call", ("__sprint_r", (i["mnem"], i["ops"]), (i["mnem"], f"{S:x} <__sbprintf>")))

    def test_a_cycle_back_into_vfiprintf(self):
        V = self.pristine.syms["_vfiprintf_r"][0] & ~1
        i = [x for x in self.pristine.region(self.pristine.syms["__sprint_r"][0] & ~1) if "<__sfvwrite_r>" in x["ops"]][0]
        self.refuses("recursion", ("__sprint_r", (i["mnem"], i["ops"]), (i["mnem"], f"{V:x} <_vfiprintf_r>")))

    def test_another_cycle(self):
        W = self.pristine.syms["__swsetup_r"][0] & ~1
        i = [x for x in self.pristine.region(W) if x["mnem"] == "bl" and "<_free_r>" in x["ops"]][0]
        self.refuses("recursion", ("__swsetup_r", ("bl", i["ops"]), ("bl", f"{W:x} <__swsetup_r>")))

    def test_the_depth_rule_admits_one_nested_activation_and_no_more(self):
        img = copy.deepcopy(self.ref)
        V, S, P = (img.syms[n][0] & ~1 for n in ("_vfiprintf_r", "__sbprintf", "__sprint_r"))
        root, nested = img.ROOT_CTX, (frozenset(), True)
        self.assertGreater(img.depth(V, nested, ((V, root), (S, root)), {}), 0, "the one nested _vfiprintf_r")
        for what, entry, ctx, path in (
                ("a nested entry the rule did not flag", V, root, ((V, root), (S, root))),
                ("a third _vfiprintf_r", V, nested, ((V, root), (S, root), (V, nested), (S, root))),
                ("a third _vfiprintf_r through another routine", V, nested, ((V, root), (S, root), (V, nested), (P, root))),
                ("a third _vfiprintf_r behind the one __sbprintf", V, nested, ((V, root), (V, nested), (S, root))),
                ("a second __sbprintf", S, root, ((V, root), (S, root), (V, nested))),
                ("_vfiprintf_r re-entered without __sbprintf", V, nested, ((V, root), (P, root)))):
            with self.subTest(what):
                with self.assertRaises(isa.Finding) as c:
                    img.depth(entry, ctx, path, {})
                self.assertIn("recursion", str(c.exception))


if __name__ == "__main__":
    unittest.main()
