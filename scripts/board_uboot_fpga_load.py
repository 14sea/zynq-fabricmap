#!/usr/bin/env python3
"""Load a full/partial bitstream into the Zynq PL via U-Boot `fpga`, over UART.

Sequence:  loady <addr>  ->  sb -k <bit>  ->  fpga <op> 0 <addr> <size>
           [-> md <read> 1  twice, to watch a live PL register change]

Ported into this repo from zynq_xpart's `uboot-fpga-load.py` so the autoehw
board flow is self-contained and board-agnostic (see board_serial.py for the
4205-vs-4203 prompt difference).  ~3 min for a 2 MB bitstream at 115200.
"""
import argparse
import os
import re
import subprocess
import sys
import time

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from board_serial import BAUD, PORT, PROMPT_RE, read_until  # noqa: E402

import serial  # noqa: E402

READY_RE = re.compile(rb"Ready for binary|CC")
MD_RE = re.compile(rb"^[0-9a-fA-F]{8}:\s+([0-9a-fA-F]{8})", re.MULTILINE)

# devcfg INT_STS. Bit 2 is PCFG_DONE. `fpga loadb` prints the bitstream header, the byte
# count and a prompt whether or not configuration happened, and this script used to exit 0
# on that alone — which cost three board sessions.
#
# **PCFG_DONE is STICKY and write-1-to-clear, so reading it as a level proves nothing.** A
# 1 after the load may be left over from the previous one; that is not a hypothetical, it
# is what happened — the level check passed on `0x50021004` and the fabric still did not
# answer. So the bit is CLEARED first, confirmed to read 0, and only then required to be 1.
# An edge is evidence that THIS load configured the PL; a level is evidence that some load
# once did.
DEVCFG_INT_STS = 0xF8007000 + 0x0C
PCFG_DONE = 1 << 2


def read_int_sts(s):
    """devcfg INT_STS, or None if the console did not answer."""
    s.reset_input_buffer()
    s.write(f"md 0x{DEVCFG_INT_STS:08x} 1\r".encode())
    reply = read_until(s, PROMPT_RE, 5)
    match = MD_RE.search(reply)
    return int(match.group(1), 16) if match else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default=PORT)
    ap.add_argument("--baud", type=int, default=BAUD)
    ap.add_argument("--bit", required=True)
    ap.add_argument("--addr", default="0x4000000")
    ap.add_argument("--op", default="loadb", choices=["loadb", "loadbp", "load", "loadp"])
    ap.add_argument("--read", help="hex AXI addr to md after load, e.g. 0x41200000")
    ap.add_argument("--log", default="/tmp/sb-fpga.log")
    args = ap.parse_args()

    size = os.path.getsize(args.bit)
    addr = int(args.addr, 16)
    print(f"[*] {args.bit}: {size} bytes -> 0x{addr:08x}, then `fpga {args.op}`", flush=True)

    # 1. tell U-Boot to receive ymodem (bare CR first: both boards can hold junk)
    s = serial.Serial(args.port, args.baud, timeout=0.3)
    s.write(b"\r")
    time.sleep(0.3)
    s.reset_input_buffer()
    s.write(f"loady 0x{addr:08x}\r".encode())
    read_until(s, READY_RE, 6)
    s.close()

    # 2. ymodem transfer
    print("[*] ymodem transfer via sb ...", flush=True)
    with open(args.port, "r+b", buffering=0) as tty, open(args.log, "wb") as log:
        rc = subprocess.run(["sb", "-k", args.bit], stdin=tty, stdout=tty, stderr=log)
    if rc.returncode != 0:
        sys.exit(f"sb failed rc={rc.returncode} (see {args.log})")

    # 3. consume transfer-complete + prompt
    s = serial.Serial(args.port, args.baud, timeout=0.3)
    tail = read_until(s, PROMPT_RE, 20)
    print("[xfer]", tail[-160:].decode(errors="replace").strip())

    # 4. clear the sticky PCFG_DONE so the check after the load is an EDGE
    cleared_first = False
    before = read_int_sts(s)
    if before is not None:
        s.reset_input_buffer()
        s.write(f"mw 0x{DEVCFG_INT_STS:08x} 0x{PCFG_DONE:08x} 1\r".encode())
        read_until(s, PROMPT_RE, 5)
        after = read_int_sts(s)
        cleared_first = after is not None and not after & PCFG_DONE
        print(f"[devcfg] INT_STS 0x{before:08x} -> 0x{after:08x} before the load "
              f"({'cleared' if cleared_first else 'NOT cleared'})")

    # 5. program the PL
    line = f"fpga {args.op} 0 0x{addr:08x} 0x{size:08x}\r"
    print(f"[*] {line.strip()}", flush=True)
    s.reset_input_buffer()
    s.write(line.encode())
    print("[fpga]", read_until(s, PROMPT_RE, 30).decode(errors="replace").strip())

    # 6. the load is not believed until the PL says THIS load configured it
    int_sts = read_int_sts(s)
    print(f"[devcfg] INT_STS=0x{int_sts:08x} PCFG_DONE="
          f"{'1' if int_sts & PCFG_DONE else '0'} (after the load)")
    if not int_sts & PCFG_DONE:
        s.close()
        sys.exit(
            f"FPGA CONFIGURATION DID NOT HAPPEN: devcfg INT_STS=0x{int_sts:08x}, PCFG_DONE "
            "is clear. `fpga loadb` printed the header and returned a prompt anyway. Every "
            "AXI access to the PL will now stall the CPU.")
    # A marker that survives nothing. `setenv` without `saveenv` lives in RAM, so if the
    # board restarts for ANY reason the variable is gone — which is the only cheap way to
    # ask "is this the same boot that configured the PL?" without touching the PL. Asking
    # the PL is not an option: if it has been cleared, the question stalls the CPU.
    marker = f"{time.time_ns():016x}"
    s.reset_input_buffer()
    s.write(f"setenv plmark {marker}\r".encode())
    read_until(s, PROMPT_RE, 5)
    print(f"[plmark] {marker}")

    if not cleared_first:
        print("[devcfg] NOTE: PCFG_DONE was already set before this load and could not be "
              "cleared, so the 1 above is a level and not an edge — it does not prove that "
              "THIS load configured the PL.")

    # 7. read a PL register twice -> a live mailbox shows different values
    if args.read:
        for i in range(2):
            s.reset_input_buffer()
            s.write(f"md {args.read} 1\r".encode())
            print(f"[md#{i}]", read_until(s, PROMPT_RE, 5).decode(errors="replace").strip())
            time.sleep(0.8)
    s.close()


if __name__ == "__main__":
    main()
