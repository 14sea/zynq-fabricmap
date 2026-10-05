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


def synth(seq, base=0x1000, sp_off=SP, more=None, library=()):
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

    def test_every_path_is_bounded_and_within_budget(self):
        self.assertTrue(self.r["ok"], f"unresolved findings: {self.r['findings']}")
        self.assertEqual(self.r["findings"], [])
        e = self.r["entries"]
        self.assertLessEqual(e["main"]["bound"], isa.MAIN_LIMIT, "the main path is within 0x2000")
        self.assertEqual(self.r["main_limit"], 0x2000)
        for name, b in e.items():
            limit = isa.MAIN_LIMIT if name == "main" else b["capacity"]
            self.assertIsNotNone(b["bound"], f"{name} has no bound")
            self.assertLessEqual(b["bound"], limit, f"{name} exceeds its budget")
        for exc in ("undefined", "svc", "prefetch_abort", "data_abort", "irq", "fiq"):
            self.assertIn(exc, e)

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
        for stated in ("(B1)", "(B2)", "(B3)"):
            self.assertIn(stated, vm["rule"])
        for gone in ("(M1)", "(M2)", "(M3)"):               # the owner's HOLD on 1e55967: no longer assumed
            self.assertNotIn(gone, vm["rule"])
        self.assertTrue(vm["targets"], "the library contracts the analysis relied on are named")
        self.assertLessEqual(set(vm["targets"]), set(isa.Image.LIBC_CONTRACTS))
        formats = rules["printf_formats"]["targets"]
        self.assertTrue(formats)
        self.assertTrue(all(f["no_percent_n"] and f["formats"] for f in formats), "every printf format is proved")
        used = {s.split(":")[0] for s in rules["callback_contracts"]["targets"]}
        self.assertLessEqual(used, set(isa.Image.CONTRACTS))
        self.assertIn("sha_emit", used)
        tables = {s.split(":")[0] for s in rules["read_only_tables"]["targets"]}
        self.assertEqual(tables, {"APP_RX", "TX_IO", "REC_IO", "PULL_IO"}, "every I/O table is proved read-only")

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

    def test_a_store_through_a_pointer_that_is_not_this_frame_does_not_touch_it(self):
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r3, #0"), ("str", "r3, [r6, #8]"), ("strb", "r3, [r6, r2]"),
                             ("ldr", "r1, [sp, #8]"), ("blx", "r1")])
        self.assertEqual(targets(img, b), [CB_A])

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
        # no pointer to the frame is handed over: the slot is untouched
        img, b = synth(pre + [("mov", "r0, #0"), ("mov", "r1, #0"), ("mov", "r2, #0"), ("mov", "r3, #0"),
                              ("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))
        self.assertEqual(targets(img, b), [CB_A])
        # a prebuilt routine handed ANY address of the frame may write the slot — below it, at it or above it (no
        # direction is assumed of a routine that cannot be read)
        for reg in ("r0", "r3"):
            for off in (4, 8, 12, 200):
                with self.subTest(reg=reg, off=off):
                    regs = [("mov", f"r{n}, #0") for n in range(4) if f"r{n}" != reg]
                    self.refused(pre + regs + [("add", f"{reg}, sp, #{off}"), ("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))

    def test_a_frame_address_in_a_stack_word_of_a_call_to_an_unknown_routine(self):
        # the fifth argument: the address goes into an outgoing stack word, the registers hold nothing
        lib = {"lib": (0x3000, [("bx", "lr")])}
        zero = [("mov", f"r{n}, #0") for n in range(4)]
        post = [("ldr", "r1, [sp, #8]"), ("blx", "r1")]
        for off in (0, 4, 40):
            with self.subTest(off):
                self.refused(CB + [("str", "r0, [sp, #8]"), ("add", "r4, sp, #8"), ("str", "r4, [sp, #%d]" % off)] + zero +
                             [("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))
        # the control: a stack word that holds no address
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r4, #5"), ("str", "r4, [sp, #0]")] + zero +
                       [("bl", call(0x3000, "lib"))] + post, more=lib, library=("lib",))
        self.assertEqual(targets(img, b), [CB_A])

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
        # the control: a value that is no frame address stored there
        img, b = synth(CB + [("str", "r0, [sp, #8]"), ("mov", "r4, #9"), ("str", "r4, [r6]"), ("ldr", "r0, [r6]"),
                             ("bl", call(W, "w"))] + post, more=writer)
        self.assertEqual(targets(img, b), [CB_A])
        self.assertIsInstance(why, str)


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
        img, b = self.build(seq, more={"h": (H, [("ldr", "r4, [r0, #4]"), ("mov", "r3, #0"), ("str", "r3, [r4]"), ("bx", "lr")])})
        self.assertEqual(handed(img, b, C), [CB_A], "a helper that writes through ANOTHER word of the object")
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
    img.syms = {name: (T_ADDR, 4 * len(words), "r")}
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
