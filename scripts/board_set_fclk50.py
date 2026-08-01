#!/usr/bin/env python3
"""Set and verify Zynq FCLK0 = 50 MHz from a U-Boot prompt (4205 or 4203).

Every DFX build in this repo is signed off at 50 MHz, so FCLK0 must be pinned
before `fpga loadb` on any board.

Why this is not a constant compare: FPGA0_CLK_CTRL encodes *divisors*, not a
frequency, and the two boards run different IO PLLs.

  EBAZ4205 (miner FSBL):   IO PLL 1000 MHz, /10 /2 -> 0x00200a00 = 50 MHz
                           (and it reverts to 125 MHz on EVERY reset)
  EBAZ4203 (vendor ps7_init in U-Boot SPL): IO PLL 1600 MHz, /8 /4
                           -> 0x00400800 = 50 MHz already

Writing the 4205's magic 0x00200a00 onto a 4203 would give 1600/10/2 = 80 MHz
— silently wrong, and exactly the class of bug that produced the EHW-5.2 FAILs.
So this script decodes the PLLs and computes the real frequency instead.
"""

import argparse
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from board_serial import BAUD, PORT, md1, mw1, sync_prompt  # noqa: E402

try:
    import serial
except ImportError:  # pragma: no cover - board-host dependency
    print("pyserial is required: install it in the board-control environment", file=sys.stderr)
    raise

SLCR_UNLOCK = 0xF8000008
UNLOCK_KEY = 0x0000DF0D
ARM_PLL_CTRL = 0xF8000100
DDR_PLL_CTRL = 0xF8000104
IO_PLL_CTRL = 0xF8000108
FPGA0_CLK_CTRL = 0xF8000170

TARGET_MHZ = 50.0
TOL_MHZ = 0.5

# Divisor pairs known to be in use, keyed by the PLL frequency they divide.
# Keeping these exact preserves the 4205's historical 0x00200a00 golden value.
KNOWN_DIVISORS = {
    1000: (10, 2),  # EBAZ4205 miner chain
    1600: (8, 4),   # EBAZ4203 vendor ps7_init
}


def pll_mhz(ctrl, ps_clk_mhz):
    """PLL output from a *_PLL_CTRL register (PLL_FDIV = bits [18:12])."""
    return ps_clk_mhz * ((ctrl >> 12) & 0x7F)


def decode_fclk(clk_ctrl, pll_by_src):
    src = (clk_ctrl >> 4) & 0x3
    pll = pll_by_src[0 if src < 2 else src]  # 0b0x = IO, 0b10 = ARM, 0b11 = DDR
    div0 = (clk_ctrl >> 8) & 0x3F or 1
    div1 = (clk_ctrl >> 20) & 0x3F or 1
    return pll / (div0 * div1), pll, div0, div1


def divisors_for(pll):
    ratio = round(pll / TARGET_MHZ)
    if abs(pll / ratio - TARGET_MHZ) > TOL_MHZ:
        raise RuntimeError(f"PLL {pll:.1f} MHz cannot be divided to {TARGET_MHZ} MHz")
    known = KNOWN_DIVISORS.get(round(pll))
    if known:
        return known
    for div1 in range(1, 64):  # fall back to any legal pair
        if ratio % div1 == 0 and 1 <= ratio // div1 <= 63:
            return ratio // div1, div1
    raise RuntimeError(f"no legal divisor pair for ratio {ratio}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--port", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--ps-clk", type=float, default=33.333333, help="PS_CLK in MHz")
    ap.add_argument("--verify-only", action="store_true")
    args = ap.parse_args()

    with serial.Serial(args.port, args.baud, timeout=0.1) as ser:
        sync_prompt(ser)
        pll_by_src = {
            0: pll_mhz(md1(ser, IO_PLL_CTRL), args.ps_clk),
            2: pll_mhz(md1(ser, ARM_PLL_CTRL), args.ps_clk),
            3: pll_mhz(md1(ser, DDR_PLL_CTRL), args.ps_clk),
        }
        before = md1(ser, FPGA0_CLK_CTRL)
        mhz, pll, div0, div1 = decode_fclk(before, pll_by_src)
        print(f"before FPGA0_CLK_CTRL=0x{before:08x} -> {pll:.1f}/{div0}/{div1} = {mhz:.2f} MHz")

        if abs(mhz - TARGET_MHZ) > TOL_MHZ:
            if args.verify_only:
                print(f"FAIL: FCLK0 is {mhz:.2f} MHz, expected {TARGET_MHZ}", file=sys.stderr)
                return 1
            div0, div1 = divisors_for(pll)
            want = (before & ~0x03F03F00) | (div0 << 8) | (div1 << 20)
            print(f"writing FPGA0_CLK_CTRL=0x{want:08x} ({pll:.1f}/{div0}/{div1})")
            mw1(ser, SLCR_UNLOCK, UNLOCK_KEY)
            mw1(ser, FPGA0_CLK_CTRL, want)

        after = md1(ser, FPGA0_CLK_CTRL)
        mhz, pll, div0, div1 = decode_fclk(after, pll_by_src)
        print(f"after  FPGA0_CLK_CTRL=0x{after:08x} -> {pll:.1f}/{div0}/{div1} = {mhz:.2f} MHz")
        if abs(mhz - TARGET_MHZ) > TOL_MHZ:
            print(f"FAIL: FCLK0 is not {TARGET_MHZ} MHz", file=sys.stderr)
            return 1

    print(f"PASS: FCLK0 pinned to {TARGET_MHZ} MHz")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
