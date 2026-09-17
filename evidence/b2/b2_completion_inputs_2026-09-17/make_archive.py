#!/usr/bin/env python3
"""B2 completion inputs — the producer. Packs the 15 files the B2 S3 verify at 73b68d7 needs that git
does not carry (the two image binaries, gitignored by design; the 13 gitignored Vivado files the B1
pin table's glob `vivado/carrier/generated/*` captured) into a deterministic tar (sorted members,
fixed metadata) compressed with zstd, and writes archive.json with every member's size and sha256.
Refuses if the working tree is not at BASE or any input is absent. Reads only; writes only into this
directory. Run from anywhere: paths are resolved against the repository root."""
from __future__ import annotations

import hashlib
import io
import json
import subprocess
import sys
import tarfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
BASE = "73b68d79fd43fc032c178da73dda2b2c95764db8"
EXPECT_MANIFEST = "aec84514ff29dda7957d46d650a370e155f6dc60a281b992e148f8a0fae6c4c0"
EXPECT_PINS = "82a5f2fb1d246c9cab506df65d53a0f329ca219ec3c5cdf50a272ff79ee319d1"
IMAGES = {"firmware/b1/bsp/out/b1_app.bin": "manifests/b1_manifest.json image.path (gitignored: firmware/b1/bsp/out/)",
          "firmware/b2/bsp/out/b2_app.bin": "manifests/b2_manifest.json image.path (gitignored: firmware/b2/bsp/out/)"}


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def main() -> int:
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()
    # The files are the WORKING TREE's copies; they are the completion inputs because each hashes to the
    # digest the frozen tables / manifests pin (checked below), not because of what HEAD is. HEAD must
    # still descend from BASE so the tables read here are the completion-state ones.
    if subprocess.run(["git", "merge-base", "--is-ancestor", BASE, head], cwd=REPO).returncode != 0:
        print(f"REFUSED: HEAD {head} does not descend from {BASE}", file=sys.stderr)
        return 2
    for t, want in (("manifests/b2_manifest.json", EXPECT_MANIFEST), ("manifests/b2_instrument_pins.json", EXPECT_PINS)):
        if sha256((REPO / t).read_bytes()) != want:
            print(f"REFUSED: {t} is not the completion-state document", file=sys.stderr)
            return 2
    image_pins = {json.loads((REPO / m).read_text())["image"]["path"]: json.loads((REPO / m).read_text())["image"]["sha256"]
                  for m in ("manifests/b1_manifest.json", "manifests/b2_manifest.json")}
    tracked = set(subprocess.run(["git", "ls-files"], cwd=REPO, capture_output=True, text=True, check=True).stdout.split("\n"))
    b1 = json.loads((REPO / "manifests/b1_instrument_pins.json").read_text())
    b2 = json.loads((REPO / "manifests/b2_instrument_pins.json").read_text())
    why = {}
    for rel in sorted(b1["files"]):
        if rel not in tracked:
            why[rel] = "manifests/b1_instrument_pins.json pins it (glob vivado/carrier/generated/*); gitignored"
    for rel in sorted(b2["files"]):
        if rel not in tracked:
            why[rel] = "manifests/b2_instrument_pins.json pins it; gitignored"
    why.update(IMAGES)
    files = {}
    buf = io.BytesIO()
    with tarfile.open(fileobj=buf, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for rel in sorted(why):
            p = REPO / rel
            if not p.is_file():
                print(f"REFUSED: {rel} is absent from the working tree", file=sys.stderr)
                return 2
            data = p.read_bytes()
            ti = tarfile.TarInfo(rel)
            ti.size, ti.mtime, ti.mode, ti.uid, ti.gid, ti.uname, ti.gname = len(data), 0, 0o644, 0, 0, "", ""
            tar.addfile(ti, io.BytesIO(data))
            files[rel] = {"bytes": len(data), "sha256": sha256(data), "why": why[rel],
                          "pinned_sha256": b1["files"].get(rel) or b2["files"].get(rel) or image_pins.get(rel)}
    for rel, e in files.items():
        if e["pinned_sha256"] != e["sha256"]:
            print(f"REFUSED: {rel} does not hash to the digest the frozen table / manifest pins", file=sys.stderr)
            return 2
    tar_bytes = buf.getvalue()
    zst = subprocess.run(["zstd", "-19", "-q", "--no-progress", "-c"], input=tar_bytes, capture_output=True, check=True).stdout
    out = HERE / "inputs.tar.zst"
    out.write_bytes(zst)
    doc = {"schema": "b2_completion_inputs", "schema_version": "1.0.0", "base": BASE,
           "expect_manifest_sha256": EXPECT_MANIFEST, "expect_pins_sha256": EXPECT_PINS,
           "created_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "source": "the working tree of /home/test/zynq_fabricmap, the only copy of these files at creation; every file hashes to the digest the frozen B1/B2 pin tables or the B1/B2 manifests' image pins carry",
           "head_at_creation": head,
           "archive": "inputs.tar.zst", "archive_sha256": sha256(zst), "archive_bytes": len(zst),
           "tar_sha256": sha256(tar_bytes), "tar_format": "ustar, members sorted by path, mtime 0, mode 0644, uid/gid 0",
           "file_count": len(files), "total_bytes": sum(e["bytes"] for e in files.values()), "files": files}
    (HERE / "archive.json").write_text(json.dumps(doc, indent=1, sort_keys=True) + "\n")
    print(f"{len(files)} files, {doc['total_bytes']} bytes -> {out.name} {len(zst)} bytes sha256 {doc['archive_sha256']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
