#!/usr/bin/env python3
"""ONE read-only dump of the engine's staging window, after the erratum-004 no-op stopped.

Authorised as a single act. It does NOT reload, does NOT begin a transaction, does NOT hand
over PCAP_PR, does NOT acknowledge a frame and does NOT arm anything. Every command it
issues is an `md`/`printenv`.

The window is 101 words: first word 0x43C01000, LAST word 0x43C01190, byte range
0x43C01000..0x43C01193. `read_words(..., 101)` issues `md.l 0x43c01000 0x65` — 0x65, not
0x64, which would stop one word short.
"""
import base64
import hashlib
import json
import re
import struct
import sys
import time
from pathlib import Path

REPO = Path("/home/test/zynq_fabricmap")
sys.path.insert(0, str(REPO / "scripts"))

import board_calibrate_noop as cal          # noqa: E402
import board_uboot_axi as axi               # noqa: E402
import gate_board_identity as ident         # noqa: E402

PLMARK = "18cb503072f557a3"                 # what the load set, from the calibration record
OUT = REPO / "evidence/calibration_noop_2026_08_13_erratum004/stage_dump.json"

record: dict = {
    "tool": "one-shot read-only staging dump",
    "what": "the 101 words carrier_stream captured for envelope 0 frame 0 before F_READBACK",
    "authorised": "one read-only act; no reload, no transaction, no PCAP_PR, no ack, no arm",
    "window": {
        "first_word_addr": "0x43c01000",
        "last_word_addr": "0x43c01190",
        "byte_range": "0x43c01000..0x43c01193",
        "words": 101,
        "md_count": "0x65",
    },
    "started_at": time.time(),
}

transport = cal.InstrumentedTransport(ident.SerialTransport("/dev/ebaz-uart"), record)
try:
    # 1. still the same boot? Asked FIRST: if the board restarted, the PL is empty and
    #    reading the window would stall the CPU.
    axi.same_boot(transport, PLMARK)
    record["plmark"] = {"expected": PLMARK, "verdict": "same boot"}

    # 2. the state must still be the one the calibration left behind
    status = axi.read_status(transport)
    code, name = axi.read_fault(transport)
    record["status"] = status
    record["fault"] = {"code": code, "name": name}
    expected = {"fault": True, "rb_latency_valid": True, "rb_latency_words": 1,
                "recovery_required": True}
    mismatched = {k: status[k] for k, v in expected.items() if status[k] != v}
    if code != 8 or mismatched:
        record["verdict"] = "STOP — the board is not in the state the calibration left"
        record["mismatched"] = mismatched
        record["fault_expected"] = 8
        raise SystemExit(1)

    # 3. the dump itself, through the existing constants and parser
    words = axi.read_words(transport, axi.RDBACK, 101)
    blob = struct.pack(">101I", *words)
    record["dump"] = {
        "words": [f"0x{w:08x}" for w in words],
        "count": len(words),
        "base64_be": base64.b64encode(blob).decode("ascii"),
        "sha256_be": hashlib.sha256(blob).hexdigest(),
    }
    record["verdict"] = "DUMPED"
finally:
    transport.close()
    # the full md.l replies are in record["instrumentation"]["commands"][*]["raw"]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"verdict: {record.get('verdict')}")
    if "dump" in record:
        print(f"  sha256(be) {record['dump']['sha256_be']}")
        print("  first 8:", " ".join(record["dump"]["words"][:8]))
        print("  last 4: ", " ".join(record["dump"]["words"][-4:]))
    print(f"  evidence: {OUT}")
