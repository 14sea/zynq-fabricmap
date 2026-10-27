#!/usr/bin/env python3
"""B4Q — A7 on the EXECUTING SIDE'S ACTUAL ACCESSES: the MMIO reads and writes the program made (logged by the host
transport, host/b4q_backend.Backend.accesses) against (i) the RTL's AXI-Lite decode (rtl/b4/b4_axil.v, parsed as
tests/test_b4carrier_regmap.py parses it), (ii) the register table of record (host/b4carrier_regmap.py: app reads / writes,
the key window), (iii) the four other regions the program may touch — the DevC's six registers, the three DDR buffers, the
SLCR IDCODE (read only). The instrument's rule: mismatches only — anything the program touched that the allowlist does not
name is a finding, and so is a write into the key window, a SLVERR answered inside the carrier window, or a DevC transaction
whose four registers are not one of the legal tuples. (The table-vs-RTL check of tests/test_b4carrier_regmap.py remains;
this one is of a program's accesses, which that unit did not have.)"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4carrier_regmap as rm  # noqa: E402
import b4q_backend as bk  # noqa: E402
import b4q_frames as fr  # noqa: E402

AXIL = (R / "rtl/b4/b4_axil.v").read_text()
DEVC_REGS = {bk.DEVCFG_CTRL: "CTRL", bk.DEVCFG_INT_STS: "INT_STS", bk.DEVCFG_DMA_SRC_ADDR: "DMA_SRC_ADDR", bk.DEVCFG_DMA_DEST_ADDR: "DMA_DEST_ADDR",
             bk.DEVCFG_DMA_SRC_LEN: "DMA_SRC_LEN", bk.DEVCFG_DMA_DEST_LEN: "DMA_DEST_LEN"}
BUFFERS = {"CMD_BUF": (bk.CMD_BUF, 4 * fr.READBACK_CMD_WORDS), "DST_BUF": (bk.DST_BUF, 4 * fr.READBACK_WORDS), "WR_BUF": (bk.WR_BUF, len(fr.ENVELOPES) * 4 * fr.STREAM_WORDS)}
LEGAL_DMA = {("env", bk.PCAP_ENDPOINT, fr.STREAM_WORDS, 0), ("cmd", bk.PCAP_ENDPOINT, fr.READBACK_CMD_WORDS, 0), ("frame", bk.PCAP_ENDPOINT, 0, fr.READBACK_WORDS), ("clean", bk.PCAP_ENDPOINT, fr.CLEANUP_WORDS, 0)}


def rtl_reads() -> set:
    out = set()
    for m in re.finditer(r"ra == 16'h([0-9A-Fa-f]{4})", AXIL):
        out.add(int(m.group(1), 16))
    for m in re.finditer(r"ra >= 16'h([0-9A-Fa-f]{4}) && ra < 16'h([0-9A-Fa-f]{4})", AXIL):
        out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
    return out


def rtl_writes() -> set:
    out = set()
    for m in re.finditer(r"wire wr_\w+\s*=\s*\(wa == 16'h([0-9A-Fa-f]{4})\)", AXIL):
        out.add(int(m.group(1), 16))
    for m in re.finditer(r"wire wr_\w+\s*=\s*\(wa >= 16'h([0-9A-Fa-f]{4})\) && \(wa < 16'h([0-9A-Fa-f]{4})\)", AXIL):
        out.update(range(int(m.group(1), 16), int(m.group(2), 16), 4))
    return out


def check(accesses: list, pcap_log: list | None = None) -> dict:
    """`accesses`: [(op, absolute address, resp)] or dicts. Returns the report: the sets touched and the mismatches."""
    rd_rtl, wr_rtl = rtl_reads(), rtl_writes()
    touched = {"carrier_reads": set(), "carrier_writes": set(), "devc_reads": set(), "devc_writes": set(), "buffer_reads": {}, "buffer_writes": {}, "slcr_reads": set(), "other": []}
    findings = []
    slverr = 0
    for a in accesses:
        op, addr, resp = (a["op"], a["addr"], a.get("resp", 0)) if isinstance(a, dict) else a
        if bk.AXI_BASE <= addr < bk.AXI_BASE + bk.AXI_SIZE:
            off = addr - bk.AXI_BASE
            key = "carrier_reads" if op == "rd" else "carrier_writes"
            touched[key].add(off)
            if resp != 0:
                slverr += 1
        elif addr in DEVC_REGS:
            touched["devc_reads" if op == "rd" else "devc_writes"].add(addr)
        elif addr == bk.SLCR_PSS_IDCODE:
            if op == "rd":
                touched["slcr_reads"].add(addr)
            else:
                findings.append("a write to the SLCR IDCODE word")
        else:
            for name, (base, size) in BUFFERS.items():
                if base <= addr < base + size:
                    d = touched["buffer_reads" if op == "rd" else "buffer_writes"]
                    d[name] = d.get(name, 0) + 1
                    break
            else:
                touched["other"].append((op, addr))
    # (i) / (ii): the carrier window
    for off in sorted(touched["carrier_reads"]):
        if off not in rd_rtl:
            findings.append(f"read of {off:#06x}: not decoded by the RTL")
        if off not in rm.APP_READABLE:
            findings.append(f"read of {off:#06x}: not in the application's read allowlist")
    for off in sorted(touched["carrier_writes"]):
        if off not in wr_rtl:
            findings.append(f"write of {off:#06x}: not decoded by the RTL")
        if off in rm.KEY_WINDOW:
            findings.append(f"write of {off:#06x}: the KEY window (the signer principal's, never the application's)")
        elif off not in rm.APP_WRITABLE:
            findings.append(f"write of {off:#06x}: not in the application's write allowlist")
    if slverr:
        findings.append(f"{slverr} access(es) of the carrier window answered SLVERR")
    for op, addr in touched["other"][:10]:
        findings.append(f"{op} of {addr:#010x}: outside every region the program may touch")
    # (iii): the DevC transactions
    if pcap_log is not None:
        for e in pcap_log:
            if e.get("pcap") == "submit":
                kind, src, dst, slen, dlen = e["kind"], e["src"], e["dst"], e["src_len"], e["dst_len"]
                tup = (kind, dst if src != bk.PCAP_ENDPOINT else src, slen, dlen)
                if kind == "other" or tup not in LEGAL_DMA:
                    findings.append(f"DMA submission {e['n']}: not one of the four legal transactions ({kind}, src {src:#010x}, dst {dst:#010x}, {slen}/{dlen})")
    return {"findings": findings, "slverr": slverr,
            "carrier_reads": sorted(f"{o:#06x}" for o in touched["carrier_reads"]), "carrier_writes": sorted(f"{o:#06x}" for o in touched["carrier_writes"]),
            "rtl_reads_untouched": sorted(f"{o:#06x}" for o in rd_rtl - touched["carrier_reads"]), "rtl_writes_untouched": sorted(f"{o:#06x}" for o in wr_rtl - touched["carrier_writes"]),
            "devc_reads": sorted(DEVC_REGS[a] for a in touched["devc_reads"]), "devc_writes": sorted(DEVC_REGS[a] for a in touched["devc_writes"]),
            "buffer_reads": touched["buffer_reads"], "buffer_writes": touched["buffer_writes"], "slcr_reads": sorted(f"{a:#010x}" for a in touched["slcr_reads"]),
            "accesses": len(accesses)}


def main(argv=None) -> int:
    d = Path((argv or sys.argv[1:])[0])
    acc = [json.loads(l) for l in (d / "accesses.jsonl").read_text().splitlines() if l.strip()]
    pcap = [json.loads(l) for l in (d / "pcap_log.jsonl").read_text().splitlines() if l.strip()] if (d / "pcap_log.jsonl").is_file() else None
    rep = check(acc, pcap)
    print(json.dumps(rep, indent=1))
    return 0 if not rep["findings"] else 1


if __name__ == "__main__":
    sys.exit(main())
