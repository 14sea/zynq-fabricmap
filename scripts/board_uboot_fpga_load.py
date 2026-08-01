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

    # 4. program the PL
    line = f"fpga {args.op} 0 0x{addr:08x} 0x{size:08x}\r"
    print(f"[*] {line.strip()}", flush=True)
    s.reset_input_buffer()
    s.write(line.encode())
    print("[fpga]", read_until(s, PROMPT_RE, 30).decode(errors="replace").strip())

    # 5. read a PL register twice -> a live mailbox shows different values
    if args.read:
        for i in range(2):
            s.reset_input_buffer()
            s.write(f"md {args.read} 1\r".encode())
            print(f"[md#{i}]", read_until(s, PROMPT_RE, 5).decode(errors="replace").strip())
            time.sleep(0.8)
    s.close()


if __name__ == "__main__":
    main()
