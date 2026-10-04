"""The image's stack assessment (b3/host/b3_image_stack.py), image stage 5, the stack unit.

Two kinds of test. The POSITIVE ones drive the whole analysis on the FINAL linked ELF: every entry is bounded, the
main path is within its 0x2000 budget and each exception entry within its mode's stack, every indirect call resolves
to a named target set, and the newlib printf recursion is bounded by the verified source rule (with its pinned
digests). The NEGATIVE ones are discriminating: they drive the reload / must-initialised proof and the per-field
points-to on SYNTHETIC routines built in memory, so that a value that is not provably initialised, only partially
initialised, overwritten, or read before it is written is REFUSED (resolves to nothing usable), while a field that
two paths fill with different callbacks keeps BOTH, and an identity re-store is transparent.

No skip: the assessment runs against the built ELF.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "host", R / "b3/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b3_image_stack as isa  # noqa: E402

CB_A = 0x2000
CB_B = 0x2100
APP = "b3/firmware/b3_app.c"


def synth(seq, base=0x1000, sp_off=256, extra_labels=None):
    """A bare Image carrying one hand-written routine at `base`: a list of (mnem, ops) at 4-byte spacing, every
    instruction at SP offset `sp_off`. Two callbacks (CB_A, CB_B) are labelled and placed in an application unit so
    movw/movt of them resolve to ('cb', …). No ELF is read."""
    img = isa.Image.__new__(isa.Image)
    ins, body = {}, []
    a = base
    for mnem, ops in seq:
        i = {"addr": a, "size": 4, "mnem": mnem, "ops": ops, "thumb": True}
        ins[a] = i
        body.append(i)
        a += 4
    img.ins_at = ins
    img.funcs = {base: body}
    img.label_at = {base: "f", CB_A: "cb_a", CB_B: "cb_b"}
    for k, v in (extra_labels or {}).items():
        img.label_at[k] = v
    img.func_entries = {base: "f", CB_A: "cb_a", CB_B: "cb_b"}
    img.sp_at = {base: {x: frozenset({sp_off}) for x in ins}}
    img.units = [(CB_A, 1, APP), (CB_B, 1, APP)]
    img._rsucc_cache = {}
    img._rw_cache = {}
    img._pt_eval_memo = {}
    img._pt_cache = {}
    img._pt_state = {}
    img._member_of = {}
    img.words = {}
    return img, base


def br(addr):
    return f"{addr:x} <f+{addr - 0x1000:#x}>"


def reload_value(img, base):
    """The reaching-def value, at the routine's terminating `bx <reg>`, of the register it branches through — the
    proof the stack unit uses to resolve a callback spilled to a local slot. {('other',)} means refused."""
    img._rsucc_cache.clear()
    img._rw_cache.clear()
    img._pt_eval_memo.clear()
    bx = [i for i in img.funcs[base] if i["mnem"] == "bx"][-1]
    return img._pt_eval(base, bx["addr"], bx["ops"].strip(), img.sp_at)


def ldr_addr(img, base, slot_imm):
    """The address of the ldr from [sp, #slot_imm] (the reload)."""
    import re
    for i in img.funcs[base]:
        m = re.search(r"\[sp,\s*#(\d+)\]", i["ops"])
        if i["mnem"].startswith("ldr") and m and int(m.group(1)) == slot_imm:
            return i["addr"]
    raise AssertionError("no reload")


def slot_of(img, base, addr, imm):
    return img._pt_slot(base, addr, imm)


class TheFinalImage(unittest.TestCase):
    """The whole analysis on the built ELF."""

    @classmethod
    def setUpClass(cls):
        isa._ASSESS_CACHE.clear()
        cls.r = isa.assess(R / "b3/firmware/bsp/out/b3_app.elf")

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

    def test_the_image_clears_only_the_async_abort_mask(self):
        self.assertEqual(self.r["masks"]["cleared_by_the_image"], ["A"])


class TheReloadProof(unittest.TestCase):
    """A spilled callback resolves only when its slot is provably initialised on every path to the reload."""

    def test_a_fully_initialised_slot_resolves_to_its_callback(self):
        img, b = synth([("movw", "r0, #8193"), ("movt", "r0, #0"),      # r0 = CB_A | 1 (thumb)
                        ("str", "r0, [sp, #8]"),
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        self.assertEqual(reload_value(img, b), {("cb", CB_A)})

    def test_bypassing_the_initialisation_is_refused(self):
        # a branch jumps past the store to the reload: on that path the slot is uninitialised
        img, b = synth([("cbz", f"r2, {br(0x1010)}"),                     # skip the store
                        ("movw", "r0, #8193"), ("movt", "r0, #0"),
                        ("str", "r0, [sp, #8]"),
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        la = ldr_addr(img, b, 8)
        self.assertFalse(img._must_init(b, la, slot_of(img, b, la, 8), 4, img.sp_at), "not initialised on every path")
        self.assertEqual(reload_value(img, b), {("other",)})

    def test_a_partial_byte_initialisation_does_not_count(self):
        img, b = synth([("movw", "r0, #8193"), ("movt", "r0, #0"),
                        ("strh", "r0, [sp, #8]"),                         # only two bytes of a four-byte read
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        la = ldr_addr(img, b, 8)
        self.assertFalse(img._must_init(b, la, slot_of(img, b, la, 8), 4, img.sp_at))
        self.assertEqual(reload_value(img, b), {("other",)})

    def test_an_overwrite_with_a_non_callback_is_kept(self):
        # the slot is written with a callback, then overwritten with a scalar: a read must see the scalar too
        img, b = synth([("movw", "r0, #8193"), ("movt", "r0, #0"),
                        ("str", "r0, [sp, #8]"),
                        ("mov", "r3, #7"), ("str", "r3, [sp, #8]"),       # overwrite with a non-callback
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        v = reload_value(img, b)
        self.assertIn(("other",), v, "the overwriting scalar is not hidden")
        self.assertNotEqual(v, {("cb", CB_A)})

    def test_two_branches_with_different_callbacks_keep_both(self):
        img, b = synth([("cbz", f"r2, {br(0x1014)}"),
                        ("movw", "r0, #8193"), ("movt", "r0, #0"),      # CB_A path
                        ("str", "r0, [sp, #8]"),
                        ("b", br(0x1020)),
                        ("movw", "r0, #8449"), ("movt", "r0, #0"),      # CB_B path (0x2101)
                        ("str", "r0, [sp, #8]"),
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        la = ldr_addr(img, b, 8)
        self.assertTrue(img._must_init(b, la, slot_of(img, b, la, 8), 4, img.sp_at), "both paths initialise it")
        self.assertEqual(reload_value(img, b), {("cb", CB_A), ("cb", CB_B)})

    def test_an_identity_restore_is_transparent(self):
        img, b = synth([("movw", "r0, #8193"), ("movt", "r0, #0"),
                        ("str", "r0, [sp, #8]"),
                        ("ldr", "r4, [sp, #8]"), ("str", "r4, [sp, #8]"),  # reload and store back: identity
                        ("ldr", "r1, [sp, #8]"), ("bx", "r1")])
        st = [i["addr"] for i in img.funcs[b] if i["mnem"] == "str"][-1]
        self.assertTrue(img._is_identity_store(b, st, slot_of(img, b, st, 8)))
        self.assertEqual(reload_value(img, b), {("cb", CB_A)})


class SlotSourceWidth(unittest.TestCase):
    """_slot_src_reg and _covers bind the object slot, offset and width."""

    def test_covers_requires_a_word_store_at_the_slot(self):
        img, b = synth([("str", "r0, [sp, #8]"), ("strh", "r1, [sp, #16]"), ("bx", "lr")], sp_off=0)
        self.assertTrue(img._covers(b, b, 8, 4, {}))        # a word store covers
        self.assertFalse(img._covers(b, b + 4, 16, 4, {}))  # a halfword store does not
        self.assertEqual(img._slot_src_reg(b, b, 8), "r0")
        self.assertIsNone(img._slot_src_reg(b, b, 12), "a different slot")

    def test_a_multi_register_store_maps_each_slot(self):
        img, b = synth([("stm", "sp, {r2, r3, r4}"), ("bx", "lr")], sp_off=0)
        self.assertEqual(img._slot_src_reg(b, b, 0), "r2")
        self.assertEqual(img._slot_src_reg(b, b, 4), "r3")
        self.assertEqual(img._slot_src_reg(b, b, 8), "r4")


if __name__ == "__main__":
    unittest.main()
