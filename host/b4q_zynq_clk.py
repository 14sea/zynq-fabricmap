#!/usr/bin/env python3
"""B4Q — the Zynq-7000 FCLK0 ELIGIBILITY from PS-accessible SLCR words (the owner's R2 on 6eeacfc2): the one function the runner's
admission and the verifier both use, written against AMD UG585 (the Zynq-7000 SoC TRM, v1.15) register definitions —

  PLL CTRL  (ARM_PLL_CTRL 0xF8000100, DDR_PLL_CTRL 0xF8000104, IO_PLL_CTRL 0xF8000108):
      bit 0  PLL_RESET          1 = the PLL is held in reset
      bit 1  PLL_PWRDWN         1 = the PLL is powered down (a configured FDIV does not undo it)
      bit 3  PLL_BYPASS_QUAL    1 = the bypass is qualified by the BOOT_MODE's sampled PLL_BYPASS pin; 0 = PLL_BYPASS_FORCE alone decides
      bit 4  PLL_BYPASS_FORCE   1 = the PLL output is bypassed (the PS_CLK goes through)
      bits 18:12  PLL_FDIV      the feedback divisor (a configuration value, not a state)
  PLL_STATUS (0xF800010C): bit 0 ARM_PLL_LOCK, bit 1 DDR_PLL_LOCK, bit 2 IO_PLL_LOCK, bit 3 ARM_PLL_STABLE, bit 4 DDR_PLL_STABLE, bit 5 IO_PLL_STABLE
  BOOT_MODE  (0xF800025C): bits 3:0 the sampled boot mode pins, bit 4 PLL_BYPASS (the sampled bypass pin)
  FPGA0_CLK_CTRL (0xF8000170): bits 5:4 SRCSEL (0x / 10 / 11 = IO / ARM / DDR PLL), bits 13:8 DIVISOR0, bits 25:20 DIVISOR1

The NOMINAL rate (PS_CLK × FDIV / (DIVISOR0 × DIVISOR1)) is arithmetic on configuration; the ELIGIBILITY is the selected PLL's
state: not in reset, not powered down, not bypassed (forced, or qualified with the boot pin's bypass sampled), and locked. Only an
eligible source with the pinned nominal rate admits a PL access. None of this measures a clock: a physical rate is the bring-up's
M3, and software register consistency is never called a measurement."""
from __future__ import annotations

SLCR_ARM_PLL_CTRL, SLCR_DDR_PLL_CTRL, SLCR_IO_PLL_CTRL = 0xF8000100, 0xF8000104, 0xF8000108
SLCR_PLL_STATUS, SLCR_FPGA0_CLK_CTRL, SLCR_BOOT_MODE = 0xF800010C, 0xF8000170, 0xF800025C
PS_CLK_MHZ = 33.333333                                                   # the EBAZ boards' PS_CLK crystal
PLL_RESET, PLL_PWRDWN, PLL_BYPASS_QUAL, PLL_BYPASS_FORCE = 1 << 0, 1 << 1, 1 << 3, 1 << 4
FDIV_SHIFT, FDIV_MASK = 12, 0x7F
LOCK_BIT = {"arm": 0, "ddr": 1, "io": 2}
STABLE_BIT = {"arm": 3, "ddr": 4, "io": 5}
BOOT_PLL_BYPASS = 1 << 4
SRCSEL_PLL = {0: "io", 1: "io", 2: "arm", 3: "ddr"}
WORDS = ("fpga0", "arm", "ddr", "io", "status", "boot_mode")             # the six PS words an admission needs, all read before any PL access
ADDR = {"fpga0": SLCR_FPGA0_CLK_CTRL, "arm": SLCR_ARM_PLL_CTRL, "ddr": SLCR_DDR_PLL_CTRL, "io": SLCR_IO_PLL_CTRL, "status": SLCR_PLL_STATUS, "boot_mode": SLCR_BOOT_MODE}


def nominal_fclk0(fpga0_ctrl: int, pll_ctrl: int, ps_clk_mhz: float = PS_CLK_MHZ) -> dict:
    """The configured nominal rate: PS_CLK × FDIV / (DIVISOR0 × DIVISOR1); None when a divisor is zero. Configuration arithmetic only."""
    fdiv = (pll_ctrl >> FDIV_SHIFT) & FDIV_MASK
    div0, div1 = (fpga0_ctrl >> 8) & 0x3F, (fpga0_ctrl >> 20) & 0x3F
    mhz = (ps_clk_mhz * fdiv / (div0 * div1)) if (div0 and div1) else None
    return {"fdiv": fdiv, "div0": div0, "div1": div1, "mhz": (round(mhz, 3) if mhz is not None else None)}


def pll_state(ctrl: int, status: int, boot_mode: int, which: str) -> dict:
    """The selected PLL's state from its CTRL word, PLL_STATUS and BOOT_MODE: reset, powered down, bypassed (forced, or qualified by
    the sampled boot pin), locked, stable — and whether it is ELIGIBLE as a running source (none of the first three, and locked)."""
    reset, pwrdwn = bool(ctrl & PLL_RESET), bool(ctrl & PLL_PWRDWN)
    force, qual = bool(ctrl & PLL_BYPASS_FORCE), bool(ctrl & PLL_BYPASS_QUAL)
    boot_bypass = bool(boot_mode & BOOT_PLL_BYPASS)
    bypassed = force or (qual and boot_bypass)
    locked, stable = bool((status >> LOCK_BIT[which]) & 1), bool((status >> STABLE_BIT[which]) & 1)
    why = []
    if reset:
        why.append("PLL_RESET")
    if pwrdwn:
        why.append("PLL_PWRDWN")
    if force:
        why.append("PLL_BYPASS_FORCE")
    if qual and boot_bypass:
        why.append("PLL_BYPASS_QUAL with the boot pin's PLL_BYPASS sampled")
    if not locked:
        why.append(f"{which.upper()}_PLL_LOCK clear")
    return {"pll": which, "ctrl": f"{ctrl:08x}", "reset": reset, "pwrdwn": pwrdwn, "bypass_force": force, "bypass_qual": qual, "boot_pll_bypass": boot_bypass,
            "bypassed": bypassed, "locked": locked, "stable": stable, "eligible": not why, "why": why}


def fclk0_eligibility(words: dict, ps_clk_mhz: float = PS_CLK_MHZ) -> dict:
    """From the six words (`WORDS`): the selected PLL, its state, the nominal rate; `eligible` iff the PLL is an eligible running source.
    A missing word (None) makes the result ineligible by name: nothing is assumed about an input not read."""
    missing = [k for k in WORDS if words.get(k) is None]
    if missing:
        return {"eligible": False, "why": [f"word(s) not read: {', '.join(missing)}"], "missing": missing, "nominal": None, "state": None, "pll": None, "srcsel": None}
    fpga0 = words["fpga0"]
    srcsel = (fpga0 >> 4) & 3
    which = SRCSEL_PLL[srcsel]
    st = pll_state(words[which], words["status"], words["boot_mode"], which)
    nom = nominal_fclk0(fpga0, words[which], ps_clk_mhz)
    why = list(st["why"])
    if nom["mhz"] is None:
        why.append("a zero divisor in FPGA0_CLK_CTRL")
    return {"eligible": not why, "why": why, "missing": [], "srcsel": srcsel, "pll": which, "state": st, "nominal": nom,
            "inputs": {k: f"{words[k]:08x}" for k in WORDS}, "ps_clk_mhz": ps_clk_mhz}


def fclk0_from_words(fpga0_ctrl: int, pll_ctrl: dict, ps_clk_mhz: float = PS_CLK_MHZ) -> dict:
    """The former arithmetic-only helper, kept for the derivation tests: the nominal rate with the CTRL-word flags, WITHOUT the status /
    boot-mode state — not an eligibility (use fclk0_eligibility); `mhz` is None under reset, power-down or forced bypass."""
    srcsel = (fpga0_ctrl >> 4) & 3
    name = SRCSEL_PLL[srcsel]
    ctrl = pll_ctrl[name]
    nom = nominal_fclk0(fpga0_ctrl, ctrl, ps_clk_mhz)
    reset, pwrdwn, bypass = bool(ctrl & PLL_RESET), bool(ctrl & PLL_PWRDWN), bool(ctrl & PLL_BYPASS_FORCE)
    mhz = nom["mhz"] if not (reset or pwrdwn or bypass) else None
    return {"srcsel": srcsel, "pll": name, "pll_ctrl": f"{ctrl:08x}", "fdiv": nom["fdiv"], "div0": nom["div0"], "div1": nom["div1"], "pll_reset": reset, "pll_pwrdwn": pwrdwn, "pll_bypass": bypass, "mhz": mhz}
