#!/usr/bin/env python3
"""B4Q — the host twin of the executing side's frame derivation and PCAP streams (firmware/b4q/b4q_derive.c), over the
B4 carrier v2's target column.

The B1 instrument wrote a 292-bit genome into twelve target frames of its own site through three envelopes of the pinned
grammar (p3_derive.c: 4 target frames + 1 flush frame per FDRI write of 505 words, RCRC / IDCODE / WCFG / FAR / FDRI / DESYNC,
type-1 writes only). B4's universe is the 21 certified addresses of SLICE_X2Y25 (b4/host/b4_ff_mapping.py), which lie in
four frames of ONE CLB column — 0x00400a00, 0x00400a01, 0x00400a1e, 0x00400a1f (words 51 / 52). The SAME grammar is kept and
only the data table changes (the instrument's gen_firmware_data.py precedent): two envelopes of four consecutive frames,

    envelope 0: FAR 0x00400a00 — targets 0x00400a00 .. 0x00400a03, flush 0x00400a04
    envelope 1: FAR 0x00400a1c — targets 0x00400a1c .. 0x00400a1f, flush 0x00400a20

The four frames that carry no certified bit (0x00400a02 / 03 / 1c / 1d) and the two flush frames are written with the
LOADED IMAGE's own content (builds/b4/b4.bit, the natural build): the write changes exactly the whitelisted bits and the
ECC word of the frames that hold them. The base frames come from the bitstream the carrier manifest records
(builds/b4/b4_carrier_manifest.json, `bitstream_sha256`), parsed with the repository's read-only frame parser; a
different bitstream is refused by digest.

WHAT THIS IS NOT. A host derivation over a parsed bitstream: the write set, the flush frames and the whitelist are
host facts; whether a write of these eight frames on a live device is safe for the carrier's own logic in the same
column, and what the device does with it, are the B4Q plan's legal-write / composition question (docs/b4q_plan.md)
and a board matter — nothing here is evidence of a physical write or readback. The genome's bit order is the mapping's
address order (bit i = `mapping.addresses[i]`); the hash domains are the instrument's (FAR big-endian then the frame's
words, candidate_sha256) and the stream grammar is byte-exact with the C twin (tests/test_b4q_derive.py)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "scripts", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import bitstream_frames as bf  # noqa: E402
import frame_ecc as fe  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402

BITSTREAM_REL = "builds/b4/b4.bit"
MANIFEST_REL = "builds/b4/b4_carrier_manifest.json"
BUILD_REL = "builds/b4/b4_build.json"
FRAME_WORDS = 101
GENOME_BITS = 21
IDCODE = 0x03722093
# the write set (minor frames of the column 0x00400a00; the device's auto-increment reaches the flush frame after the four targets)
ENVELOPES = ({"far_set": 0x00400a00, "targets": (0x00400a00, 0x00400a01, 0x00400a02, 0x00400a03), "flush": 0x00400a04},
             {"far_set": 0x00400a1c, "targets": (0x00400a1c, 0x00400a1d, 0x00400a1e, 0x00400a1f), "flush": 0x00400a20})
TARGET_FARS = tuple(f for e in ENVELOPES for f in e["targets"])          # ascending: the FAR-ordered hash domain
FLUSH_FARS = tuple(e["flush"] for e in ENVELOPES)
ENVELOPE_FRAMES = 5
FDRI_WORDS = ENVELOPE_FRAMES * FRAME_WORDS                                # 505
STREAM_WORDS = 534
READBACK_CMD_WORDS, READBACK_WORDS, CLEANUP_WORDS = 43, 202, 5
# the pinned grammar (p3_derive.c, verbatim constants)
DUMMY, SYNC, NOOP = 0xFFFFFFFF, 0xAA995566, 0x20000000
REG_CMD, REG_FAR, REG_FDRI, REG_IDCODE = 4, 1, 2, 12
CMD_RCRC, CMD_WCFG, CMD_DESYNC, CMD_RCFG = 7, 1, 13, 4
OP_READ, OP_WRITE, R_FDRO = 1, 2, 3
FLUSH_NOOPS = 32


class DeriveRefusal(ValueError):
    pass


def t1w(reg: int, count: int) -> int:
    return (1 << 29) | (2 << 27) | (reg << 13) | count


def t2w(count: int) -> int:
    return (2 << 29) | (2 << 27) | count


def t1op(op: int, reg: int, count: int) -> int:
    return (1 << 29) | (op << 27) | (reg << 13) | count


def t2op(op: int, count: int) -> int:
    return (2 << 29) | (op << 27) | count


def nonce_step(x: int) -> int:
    m = (1 << 64) - 1
    x ^= (x << 13) & m
    x ^= x >> 7
    x ^= (x << 17) & m
    return x & m


# ------------------------------------------------------------------ the base: the loaded image's frames
def whitelist(mapping=None) -> list[tuple[int, int, int]]:
    """Bit i of the genome = the i-th address of the mapping (far, word, bit)."""
    m = mapping or bm.site_mapping()
    out = []
    for a in m.addresses:
        far, word, bit = a.split("/")
        out.append((int(far, 16), int(word), int(bit)))
    if len(out) != GENOME_BITS:
        raise DeriveRefusal(f"{len(out)} addresses, not {GENOME_BITS}")
    for far, _, _ in out:
        if far not in TARGET_FARS:
            raise DeriveRefusal(f"address frame {far:#010x} outside the write set")
    return out


def load_base(repo_root: Path = R, expected_sha256: str | None = None) -> dict:
    """The loaded image's frames of the write set, from the bitstream the carrier manifest names (refused by digest)."""
    build = json.loads((repo_root / BUILD_REL).read_text())
    manifest = json.loads((repo_root / MANIFEST_REL).read_text())
    want = expected_sha256 or build["bitstream_sha256"]                 # the build record of the committed bitstream (b4_build.json)
    data = (repo_root / BITSTREAM_REL).read_bytes()
    got = hashlib.sha256(data).hexdigest()
    if got != want:
        raise DeriveRefusal(f"{BITSTREAM_REL} sha256 {got[:16]}… is not the build record's {want[:16]}…")
    parsed = bf.parse_frames(repo_root / BITSTREAM_REL, data=data)
    if parsed["idcode"] != IDCODE:
        raise DeriveRefusal(f"idcode {parsed['idcode']:#010x}")
    frames = parsed["frames"]
    base = {far: list(frames[far]) for far in TARGET_FARS + FLUSH_FARS}
    for far, words in base.items():
        if len(words) != FRAME_WORDS or not fe.frame_is_consistent(words):
            raise DeriveRefusal(f"frame {far:#010x} of the loaded image is not ECC-consistent")
    # the carrier manifest of record names an EARLIER file digest (the pre-v0.4 build; the unit README names this
    # discrepancy): the frame CONTENT it records per column frame is compared here, never silently trusted or rewritten
    column = {f"{far:#010x}": frame_sha256(frames[far]) for far in range(0x00400a00, 0x00400a24)}
    stale = sorted(k for k, v in manifest.get("target_column_frames_sha256", {}).items() if column.get(k) != v)
    return {"bitstream_sha256": got, "build_bitstream_sha256": build["bitstream_sha256"], "frames": base,
            "manifest_bitstream_sha256": manifest["bitstream_sha256"], "manifest_file_digest_matches": manifest["bitstream_sha256"] == got,
            "manifest_column_frames_differing": stale, "column_frames_sha256": column}


def frame_sha256(words: list[int]) -> str:
    return hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()


# ------------------------------------------------------------------ the derive: genome -> frames
def derive_frames(genome: int, base: dict, wl: list[tuple[int, int, int]]) -> dict[int, list[int]]:
    """The single derive function the signer and the application must agree on, bit for bit: the base target frames, the
    whitelisted bits set to the genome's values, the ECC word recomputed (frame_ecc; only word 50 changes)."""
    if not isinstance(genome, int) or isinstance(genome, bool) or not 0 <= genome < (1 << GENOME_BITS):
        raise DeriveRefusal("the genome is not a 21-bit value")
    frames = {far: list(base[far]) for far in TARGET_FARS}
    for i, (far, w, b) in enumerate(wl):
        if (genome >> i) & 1:
            frames[far][w] |= 1 << b
        else:
            frames[far][w] &= ~(1 << b) & 0xFFFFFFFF
    return {far: fe.update_ecc(words) for far, words in frames.items()}


def genome_from_frames(frames: dict[int, list[int]], wl) -> int:
    g = 0
    for i, (far, w, b) in enumerate(wl):
        if (frames[far][w] >> b) & 1:
            g |= 1 << i
    return g


def frames_hash(frames: dict[int, list[int]], fars=TARGET_FARS) -> str:
    """candidate_sha256: FAR-ordered (far big-endian, then the frame's words big-endian) — p3_frames_hash."""
    h = hashlib.sha256()
    for far in fars:
        h.update(far.to_bytes(4, "big"))
        h.update(b"".join(w.to_bytes(4, "big") for w in frames[far]))
    return h.hexdigest()


def build_stream(envelope: int, frames: dict[int, list[int]], base: dict) -> list[int]:
    e = ENVELOPES[envelope]
    out = [DUMMY] * 8 + [SYNC, NOOP, t1w(REG_CMD, 1), CMD_RCRC, NOOP, NOOP, t1w(REG_IDCODE, 1), IDCODE, t1w(REG_CMD, 1), CMD_WCFG, NOOP,
                         t1w(REG_FAR, 1), e["far_set"], t1w(REG_FDRI, 0), t2w(FDRI_WORDS)]
    for far in e["targets"]:
        out += frames[far]
    out += base[e["flush"]]                                   # the flush frame, verbatim
    out += [t1w(REG_CMD, 1), CMD_DESYNC, NOOP, NOOP, NOOP, NOOP]
    assert len(out) == STREAM_WORDS
    return out


def parse_stream(words: list[int]):
    """The literal grammar walk of p3_parse_stream: (far_set, the five frames) or None on any deviation."""
    if len(words) != STREAM_WORDS or any(w != DUMMY for w in words[:8]) or words[8] != SYNC:
        return None
    i, cmds, far_set, frames5, have_far, have_fdri = 9, [], None, None, False, False
    while i < STREAM_WORDS:
        w = words[i]
        if w == NOOP:
            i += 1; continue
        if (w >> 29) != 1 or ((w >> 27) & 3) != 2:
            return None
        reg, count = (w >> 13) & 0x3FFF, w & 0x7FF
        if reg == REG_CMD:
            cmd = words[i + 1]
            if cmd not in (CMD_RCRC, CMD_WCFG, CMD_DESYNC) or len(cmds) >= 3:
                return None
            cmds.append(cmd); i += 2
        elif reg == REG_IDCODE:
            if words[i + 1] != IDCODE:
                return None
            i += 2
        elif reg == REG_FAR:
            if words[i + 1] not in {e["far_set"] for e in ENVELOPES}:
                return None
            far_set, have_far = words[i + 1], True; i += 2
        elif reg == REG_FDRI:
            if count != 0 or (words[i + 1] >> 29) != 2 or (words[i + 1] & 0x07FFFFFF) != FDRI_WORDS or not have_far or have_fdri:
                return None
            frames5 = [words[i + 2 + k * FRAME_WORDS:i + 2 + (k + 1) * FRAME_WORDS] for k in range(ENVELOPE_FRAMES)]
            have_fdri = True; i += 2 + FDRI_WORDS
        else:
            return None
    if not have_fdri or cmds != [CMD_RCRC, CMD_WCFG, CMD_DESYNC]:
        return None
    return far_set, frames5


def build_readback_command(far: int) -> list[int]:
    return [DUMMY, SYNC, NOOP, NOOP, t1op(OP_WRITE, REG_CMD, 1), CMD_RCFG, NOOP, t1op(OP_WRITE, REG_FAR, 1), far,
            t1op(OP_READ, R_FDRO, 0), t2op(OP_READ, READBACK_WORDS)] + [NOOP] * FLUSH_NOOPS


def build_cleanup_command() -> list[int]:
    return [NOOP, t1op(OP_WRITE, REG_CMD, 1), CMD_DESYNC, NOOP, NOOP]


def words_sha256(words: list[int]) -> str:
    return hashlib.sha256(b"".join(w.to_bytes(4, "big") for w in words)).hexdigest()


def write_set_record(base: dict, wl) -> dict:
    """What the data header is generated from — a reviewable record of the write set and the base content digests."""
    return {"bitstream": BITSTREAM_REL, "bitstream_sha256": base["bitstream_sha256"], "build_record": BUILD_REL, "idcode": f"{IDCODE:#010x}",
            "carrier_manifest": MANIFEST_REL, "carrier_manifest_bitstream_sha256": base["manifest_bitstream_sha256"],
            "carrier_manifest_file_digest_matches": base["manifest_file_digest_matches"], "carrier_manifest_column_frames_differing": base["manifest_column_frames_differing"],
            "envelopes": [{"far_set": f"{e['far_set']:#010x}", "targets": [f"{t:#010x}" for t in e["targets"]], "flush": f"{e['flush']:#010x}"} for e in ENVELOPES],
            "target_fars": [f"{f:#010x}" for f in TARGET_FARS], "flush_fars": [f"{f:#010x}" for f in FLUSH_FARS],
            "whitelist": [{"bit": i, "far": f"{far:#010x}", "word": w, "bit_in_word": b} for i, (far, w, b) in enumerate(wl)],
            "base_frame_sha256": {f"{far:#010x}": frame_sha256(base["frames"][far]) for far in TARGET_FARS + FLUSH_FARS},
            "base_genome_of_loaded_image": genome_from_frames({f: base["frames"][f] for f in TARGET_FARS}, wl),
            "loaded_image_target_frames_sha256": frames_hash(base["frames"]),
            "note": "the loaded image is the natural build (CEUSEDMUX = SRUSEDMUX = 1); the signed base genome 0 differs from it in exactly those two bits and their frames' ECC"}
