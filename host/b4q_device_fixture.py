#!/usr/bin/env python3
"""B4Q — SYNTHETIC device-format fixtures (the owner's R4 on dad9e4de): a runner archive produced behind the device surrogate on a PTY
rewritten into the FORMAT a board run would produce (`transport.kind = "uart-board"`, `emulated = false`, no backend record, no
private directory, the surrogate's banner marks scrubbed from the raw streams and the control-plane replies), so that the verifier's
offline validation of the physical-source format — its structural / source consistency, the runner linkage of R1, the absence of
emulator-only witnesses, the downgrade attempts — can be exercised without a board. Every such fixture carries `manifest.synthetic`
saying what it is; the verifier reports it as a synthetic fixture, never as board evidence; no result on it grants device execution
or a qualification claim.

    python3 host/b4q_device_fixture.py <pty archive> <out dir> [--downgrade keep-banner|keep-backend|keep-emulated|keep-private|no-marker]

The downgrades produce fixtures that a device-format archive must NOT pass as: the verifier's provenance checks are what the tests
hold against them."""
from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
SURROGATE_MARK = "(surrogate)"


def scrub(data: bytes) -> bytes:
    """The surrogate's banner marks removed from a raw stream, byte-length preserving (the control-plane steps' offsets stay valid)."""
    return data.replace(SURROGATE_MARK.encode(), b" " * len(SURROGATE_MARK))


def make(src: Path, out: Path, downgrade: str | None = None) -> dict:
    src, out = Path(src), Path(out)
    if out.exists():
        shutil.rmtree(out)
    shutil.copytree(src, out)
    m = json.loads((out / "manifest.json").read_text())
    u = json.loads((out / "uboot.json").read_text())
    tr = m["transport"]
    assert tr["kind"] == "console-pty-surrogate", "a synthetic device-format fixture is made from a PTY (surrogate) archive"
    rx, tx = (out / "raw/console.bin").read_bytes(), (out / "raw/console_tx.bin").read_bytes()
    if downgrade != "keep-banner":
        rx, tx = scrub(rx), scrub(tx)
        for s in u["uboot_steps"]:
            if isinstance(s.get("reply"), str):
                s["reply"] = s["reply"].replace(SURROGATE_MARK, " " * len(SURROGATE_MARK))
        if isinstance((u.get("admission") or {}).get("board"), dict) and isinstance(u["admission"]["board"].get("model"), str):
            u["admission"]["board"]["model"] = u["admission"]["board"]["model"].replace(SURROGATE_MARK, "").strip()   # the model as the scrubbed stream reads (stripped)
    (out / "raw/console.bin").write_bytes(rx); (out / "raw/console_tx.bin").write_bytes(tx)
    u["raw"] = {"console_bin_sha256": hashlib.sha256(rx).hexdigest(), "console_bin_bytes": len(rx), "console_tx_bin_sha256": hashlib.sha256(tx).hexdigest(), "console_tx_bin_bytes": len(tx)}
    u["kind"] = "uart-board"; u["port"] = "/dev/ebaz-uart"; u["port_real"] = "/dev/ttyUSB0"
    if downgrade != "keep-fixture":
        u["context"]["fixture"] = None
        if isinstance(u.get("admission"), dict) and isinstance(u["admission"].get("board"), dict):
            u["admission"]["board"]["fixture"] = None
    (out / "uboot.json").write_text(json.dumps(u, indent=1) + "\n")
    tr["kind"] = "uart-board"
    tr["runner"] = u
    tr["standing"] = "a SYNTHETIC device-format fixture (host/b4q_device_fixture.py): the format a board run would produce, made from a surrogate archive; never board evidence"
    if downgrade != "keep-emulated":
        m["emulated"] = False
    if downgrade != "keep-backend":
        m["backend"] = None
    else:
        m["backend"] = {"power_on": "init", "note": "an emulated backend record kept in a device-format archive (the downgrade this fixture demonstrates)"}
    if downgrade != "no-marker":
        m["synthetic"] = {"kind": "device-format fixture", "from": str(src), "from_manifest_sha256": hashlib.sha256((src / "manifest.json").read_bytes()).hexdigest(),
                          "note": "made by host/b4q_device_fixture.py from a PTY (surrogate) archive: structural consistency only; not observed on a device; grants nothing"}
    if downgrade == "keep-private":
        (out / "private").mkdir(exist_ok=True); (out / "private/surrogate_log.jsonl").write_text("{}\n")
    elif (out / "private").exists():
        shutil.rmtree(out / "private")
    (out / "manifest.json").write_text(json.dumps(m, indent=1) + "\n")
    return {"out": str(out), "downgrade": downgrade, "synthetic": m.get("synthetic") is not None}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("src", type=Path); ap.add_argument("out", type=Path)
    ap.add_argument("--downgrade", choices=("keep-banner", "keep-backend", "keep-emulated", "keep-private", "keep-fixture", "no-marker"))
    a = ap.parse_args(argv)
    print(json.dumps(make(a.src, a.out, a.downgrade)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
