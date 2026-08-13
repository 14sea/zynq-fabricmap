#!/usr/bin/env python3
"""A read-only dump of the engine's staging window, with the reply kept WHOLE.

It does NOT reload, does NOT begin a transaction, does NOT hand over PCAP_PR, does NOT
acknowledge a frame and does NOT arm anything. Every command it issues is an `md` or a
`printenv`.

The window is `board_uboot_axi.RDBACK`, `FRAME_WORDS` words long. Its address is NOT
written down here: `tests/test_single_write_entrypoint.py` requires the carrier's AXI window
to be named in the transport and nowhere else, so that a second writer would have to say
where it is writing. Every address below is derived from that module, which also means this
tool cannot drift from it. The count is `FRAME_WORDS` = 101 words — one more than the 100
that an off-by-one in the window's own documentation implied.

WHY THIS KEEPS ITS OWN TRANSCRIPT
---------------------------------
The first run of this probe recorded its commands through `board_calibrate_noop`'s
`InstrumentedTransport`, which truncates a normal reply to its last 400 characters
(`board_calibrate_noop.py`, the `entry["raw"][-400:]` line). That is a deliberate choice
there — it keeps a 171-command transcript readable and it keeps the WHOLE reply whenever
anything is odd — but for a 26-line `md.l` dump it left 7 lines, and the evidence claimed
the raw reply was preserved when it was not. The words and the digest were parsed from the
complete reply in memory, before the truncation, so they were never in doubt; the archive
was.

So this tool records the reply itself: exact bytes, base64, and the decoded text, with no
truncation anywhere.
"""
import argparse
import base64
import hashlib
import json
import struct
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "scripts"))

import board_uboot_axi as axi               # noqa: E402
import gate_board_identity as ident         # noqa: E402


class WholeReplyTransport:
    """Records every command and the COMPLETE reply. No tail, no elision."""

    def __init__(self, inner, log: list):
        self.inner = inner
        self.log = log

    def command(self, line: str, timeout: float) -> bytes:
        started = time.monotonic()
        reply = self.inner.command(line, timeout)
        self.log.append({
            "command": line,
            "elapsed_s": round(time.monotonic() - started, 4),
            "reply_bytes": len(reply),
            "reply_b64": base64.b64encode(reply).decode("ascii"),
            "reply_text": reply.decode("ascii", "replace"),
            "reply_sha256": hashlib.sha256(reply).hexdigest(),
        })
        return reply

    def __getattr__(self, name):
        return getattr(self.inner, name)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", default="/dev/ebaz-uart")
    ap.add_argument("--plmark", required=True,
                    help="the marker the load set; a different one means a restart")
    ap.add_argument("--expect-sha256", default=None,
                    help="require the dump to hash to this (a repeat of an earlier read)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    commands: list = []
    record: dict = {
        "tool": "probe_stage_dump.py/2.0.0",
        "what": "the 101 words carrier_stream captured for envelope 0 frame 0",
        "authorised": "read-only; no reload, no transaction, no PCAP_PR, no ack, no arm",
        "reply_capture": "COMPLETE — bytes, base64 and text, untruncated",
        # derived from the transport, never re-typed
        "window": {
            "first_word_addr": f"{axi.RDBACK:#010x}",
            "last_word_addr": f"{axi.RDBACK + (axi.FRAME_WORDS - 1) * 4:#010x}",
            "byte_range": f"{axi.RDBACK:#010x}.."
                          f"{axi.RDBACK + axi.FRAME_WORDS * 4 - 1:#010x}",
            "words": axi.FRAME_WORDS,
            "md_count": f"{axi.FRAME_WORDS:#x}",
        },
        "started_at": time.time(),
        "commands": commands,
    }

    transport = WholeReplyTransport(ident.SerialTransport(args.port), commands)
    try:
        # 1. still the same boot? Asked FIRST: if the board restarted the PL is empty, and
        #    reading the window would stall the CPU.
        axi.same_boot(transport, args.plmark)
        record["plmark"] = {"expected": args.plmark, "verdict": "same boot"}

        # 2. the state must still be the one the calibration left behind
        status = axi.read_status(transport)
        code, name = axi.read_fault(transport)
        record["status"] = status
        record["fault"] = {"code": code, "name": name}
        expected = {"fault": True, "rb_latency_valid": True, "rb_latency_words": 1,
                    "recovery_required": True}
        mismatched = {key: status[key] for key, want in expected.items()
                      if status[key] != want}
        if code != 8 or mismatched:
            record["verdict"] = "STOP — the board is not in the state that was dumped before"
            record["mismatched"] = mismatched
            return 1

        # 3. the dump itself, through the existing constants and parser
        words = axi.read_words(transport, axi.RDBACK, axi.FRAME_WORDS)
        blob = struct.pack(f">{len(words)}I", *words)
        digest = hashlib.sha256(blob).hexdigest()
        record["dump"] = {
            "words": [f"0x{word:08x}" for word in words],
            "count": len(words),
            "base64_be": base64.b64encode(blob).decode("ascii"),
            "sha256_be": digest,
        }
        if len(words) != axi.FRAME_WORDS:
            record["verdict"] = (f"STOP — {len(words)} words came back, not "
                                 f"{axi.FRAME_WORDS}")
            return 1
        if args.expect_sha256 and digest != args.expect_sha256:
            record["verdict"] = "STOP — the window no longer reads the same"
            record["expected_sha256"] = args.expect_sha256
            return 1
        record["verdict"] = "DUMPED"
        record["reproduces_earlier_dump"] = bool(args.expect_sha256)
        return 0
    finally:
        transport.close()
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
        print(f"verdict: {record.get('verdict')}")
        if "dump" in record:
            print(f"  sha256(be) {record['dump']['sha256_be']}")
            print(f"  distinct values: "
                  f"{sorted(set(record['dump']['words']))[:4]}")
        total = sum(entry["reply_bytes"] for entry in commands)
        print(f"  {len(commands)} commands, {total} reply bytes kept whole")
        print(f"  evidence: {args.out}")


if __name__ == "__main__":
    sys.exit(main())
