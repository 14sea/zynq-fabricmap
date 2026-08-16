#!/usr/bin/env python3
"""READ-ONLY: the fifth fresh-power precondition — `plmark` must NOT be defined.

`plmark_only.py` asserts the opposite (that a known marker is still set), so it cannot be
reused here: for a fresh power-on the *absence* of the variable is the pass. Sends
`printenv plmark` and nothing else — no md, no mw, no bare CR.
"""
import re
import sys

sys.path.insert(0, "/home/test/zynq_fabricmap/scripts")

import serial  # noqa: E402
import board_serial as bs  # noqa: E402

with serial.Serial("/dev/ebaz-uart", bs.BAUD, timeout=0.1) as ser:
    sync = bs.ub_cmd(ser, bs.SYNC_COMMAND, 3.0)
    reply = bs.ub_cmd(ser, "printenv plmark", 3.0)

print(f"printenv plmark -> {reply.decode('ascii', 'replace').strip()!r}")

if bs.BOOT_BANNER_RE.search(sync + reply):
    print("STOP: a boot banner came back — the board is still booting")
    raise SystemExit(1)
found = re.search(rb"plmark=([0-9a-f]+)", reply)
if found:
    print(f"STOP: plmark IS defined ({found.group(1).decode()}) — this is not a fresh power-on")
    raise SystemExit(1)
if b"not defined" not in reply:
    print("STOP: the reply is neither a marker nor a 'not defined' error — unreadable")
    raise SystemExit(1)
print("PRECHECK PASS: plmark is not defined (fresh power-on)")
