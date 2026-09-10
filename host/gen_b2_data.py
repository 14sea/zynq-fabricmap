#!/usr/bin/env python3
"""Generate `firmware/b2/p3_data.h` for the B2 image (host-only; nothing here touches a board).

The B2 image is a successor of the B1 image: it keeps the instrument's whitelist, envelopes
and pinned base frames (so `p3_derive.c` compiles unchanged), drops the two-operator map
tables exactly as `gen_b1_data.py` does, and ADDS what stage B2 legitimately compiles in:

  * `B2_MAP_LUT[]` / `B2_MAP_INIT[]` — the B1 self-map's relation per genome bit. This is the
    BOARD'S OWN ANSWER from stage B1 (`evidence/b1/b1_17A6_2026-09-08-02/self_map_v2.json`,
    canonical digest `B2_MAP_SHA256`), not the certificate: B1's question was to recover it,
    B2's question is whether it is useful. The certificate, the LUT site keys and any
    polarity or group table remain forbidden and are scanned for (FORBIDDEN below and
    `tests/test_b2_leakage.py`).
  * `B2_TRAIN_VECTORS[]` / `B2_HOLDOUT_VECTORS[]` — the carrier's frozen vector order, first
    40 / last 24 (`vivado/carrier/generated/carrier_constants.json`), the same split the
    scorer was built with.
  * `B2_EXCLUDED_SEEDS[]` — every seed value the session draw must skip: the fixed list plus
    every archived run's seed set, so the board derives the frozen pair sequence itself
    (`host/b2_plan.frozen_seed_exclusion`; disjointness is enforced, not assumed).
  * the engine and landscape constants, so a reader of the header can see what the image is.

The universe mask the landscape rule needs is DERIVED on the board from `B2_MAP_*` at init;
it is not a separate table. A wrong map would therefore change the landscape for both arms
equally, and the host's prediction pins every pair's target — a disagreement shows up as a
fitness mismatch on the first record (preregistration §5, falsifier 1).
"""
from __future__ import annotations

import argparse
import hashlib
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "host"))
import b2_landscape as bl  # noqa: E402
import b2_maps as bmaps  # noqa: E402
import b2_plan as bp  # noqa: E402
import b2_search as bs  # noqa: E402
import gen_b1_data as gb1  # noqa: E402

OUT = REPO_ROOT / "firmware/b2/p3_data.h"
FORBIDDEN = ("P3_LUT_KEYS", "P3_LUT_LEN", "P3_LUT_BITS", "P3_MUTATION_BITS", "P3_OPERATOR_DATA_SHA256",
             "CLBLL_L.", "CLBLM_L.", "SLICE_X", "local_map", "certificate")


def strip_comments(text: str) -> str:
    """The header's or a source's DATA, without its prose: the forbidden-token scan must catch
    a table or a string literal, not the sentence that says the table is absent.

    String and character literals are PRESERVED, escapes included, and a comment marker inside
    one does not open a comment (the owner's core review of 2026-09-10, P3: a regex stripper
    turned `"/* certificate */"` into `""` and the token escaped the scan). A quote inside a
    comment does not open a literal either. This is a lexical scan of C, not a parser; it is a
    source-level guard and is NOT a substitute for the scan of the built image's bytes.
    """
    out: list[str] = []
    i, n = 0, len(text)
    while i < n:
        c = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if c == "/" and nxt == "*":                       # block comment: consumed whole
            i += 2
            while i + 1 < n and not (text[i] == "*" and text[i + 1] == "/"):
                i += 1
            i = min(n, i + 2)
        elif c == "/" and nxt == "/":                     # line comment: up to but not the newline
            while i < n and text[i] != "\n":
                i += 1
        elif c in ("\"", "'"):                             # a literal: kept verbatim, escapes and all
            quote = c
            out.append(c)
            i += 1
            while i < n:
                if text[i] == "\\" and i + 1 < n:
                    out.append(text[i])
                    out.append(text[i + 1])
                    i += 2
                    continue
                out.append(text[i])
                closed = text[i] == quote
                i += 1
                if closed:
                    break
        else:
            out.append(c)
            i += 1
    return "".join(out)


def _rows(values, per_line: int, fmt=str) -> list[str]:
    out, line = [], []
    for v in values:
        line.append(fmt(v))
        if len(line) == per_line:
            out.append("    " + ", ".join(line) + ",")
            line = []
    if line:
        out.append("    " + ", ".join(line) + ",")
    return out


def self_map_universe() -> str:
    """The universe digest the image is compiled with — the same object B1's header carried."""
    return bmaps.load_self_map()["binding"]["universe_sha256"]


def render_b2(require_git: bool = True) -> str:
    head = gb1.render_b1(require_git=require_git)
    marker = "\n/* B1 (stage B1 cartography)"
    head = head[:head.index(marker)].rstrip("\n")
    head = head.replace("/* GENERATED by host/gen_b1_data.py (zynq-fabricmap) — do not edit.\n"
                        " * B1 image: the instrument's data header WITHOUT the two-operator map tables.",
                        "/* GENERATED by host/gen_b2_data.py (zynq-fabricmap) — do not edit.\n"
                        " * B2 image: the instrument's data header WITHOUT the two-operator map tables,\n"
                        " * plus the B1 self-map, the carrier's train/holdout split and the seed exclusion.")

    universe = self_map_universe()
    self_map = bmaps.load_self_map()
    entries = {e["genome_bit"]: e for e in self_map["entries"]}
    if sorted(entries) != list(range(bs.bc.N)):
        raise RuntimeError("the self-map does not carry every genome bit exactly once")
    for e in entries.values():
        if e["state"] not in ("decoded", "confirmed") or not e["relation"]:
            raise RuntimeError(f"genome bit {e['genome_bit']} carries no relation: the map is not complete")
    lut = [entries[i]["relation"]["lut_index"] for i in range(bs.bc.N)]
    init = [entries[i]["relation"]["init_index"] for i in range(bs.bc.N)]
    train, holdout = bl.train_vectors(), bl.holdout_vectors()
    exclusion, sources = bp.frozen_seed_exclusion()
    excluded = sorted(exclusion | set(bs.EXCLUDED_SEEDS))

    lines = [head, "",
             "/* ------------------------------------------------------------------ stage B2",
             " * The B1 self-map: the board's own product of stage B1, compiled in as stage B2's",
             " * input. Entry i is the (LUT, INIT) position genome bit i was confirmed to drive.",
             " * The map-guided operator reads only the INIT index (the column); the LUT index is",
             " * used to derive the universe mask the landscape rule masks its target to. No LUT",
             " * site key, no polarity, no group table, no certificate is compiled into this image",
             " * (host/gen_b2_data.py FORBIDDEN, tests/test_b2_leakage.py). */",
             f'#define B2_MAP_SHA256 "{bmaps.sha256_of(self_map)}"',
             f'#define B2_MAP_FILE_SHA256 "{hashlib.sha256(bmaps.SELF_MAP.read_bytes()).hexdigest()}"',
             f'#define B2_MAP_CARTOGRAPHER "{self_map["cartographer"]}"',
             f"#define B2_MAP_N {bs.bc.N}",
             "static const unsigned char B2_MAP_LUT[B2_MAP_N] = {"] + _rows(lut, 24) + ["};",
             "static const unsigned char B2_MAP_INIT[B2_MAP_N] = {"] + _rows(init, 24) + ["};", "",
             "/* the carrier's frozen vector order: train = the first 40, holdout = the last 24",
             " * (vivado/carrier/generated/carrier_constants.json — the order the scorer was built with) */",
             f"#define B2_TRAIN_COUNT {len(train)}",
             f"#define B2_HOLDOUT_COUNT {len(holdout)}",
             "static const unsigned char B2_TRAIN_VECTORS[B2_TRAIN_COUNT] = {"] + _rows(train, 20) + ["};",
             "static const unsigned char B2_HOLDOUT_VECTORS[B2_HOLDOUT_COUNT] = {"] + _rows(holdout, 20) + ["};", "",
             "/* every seed value the session draw skips: the fixed excluded list plus every archived",
             " * run's seed set (gate run 1, gate run 3, the B3 simulation). The board derives the",
             " * pair sequence from the master seed on the identity page with this table, so the",
             " * frozen rule is reproduced on the board and not merely asserted by the host. */",
             f"#define B2_EXCLUDED_SEEDS_N {len(excluded)}",
             "static const unsigned long B2_EXCLUDED_SEEDS[B2_EXCLUDED_SEEDS_N] = {"] + \
            _rows(excluded, 8, lambda v: f"0x{v:08x}ul") + ["};", "",
             "/* the engine and the landscape, as the architecture fixes them (docs/b2_architecture.md) */",
             "#define B2_DATA_NO_OPERATOR_TABLES 1",
             f'#define B2_UNIVERSE_SHA256 "{universe}"',
             f'#define B2_SEED_LABEL "{bp.SESSION_LABEL}"',
             f'#define B2_AUDIT_POLICY "{bp.AUDIT_POLICY}"',
             f'#define B2_FITNESS_ID "F1"',
             "", "#endif /* P3_DATA_H */", ""]
    text = "\n".join(lines)
    data = strip_comments(text)
    for f in FORBIDDEN:
        if f in data:
            raise RuntimeError(f"forbidden token {f!r} in the B2 header's data")
    if len(sources) != len(bp.FROZEN_SEED_SETS):
        raise RuntimeError("the seed exclusion does not cover every archived run")
    return text


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT)
    ap.add_argument("--check", action="store_true", help="compare with the committed header instead of writing")
    ap.add_argument("--no-git", action="store_true")
    a = ap.parse_args(argv)
    text = render_b2(require_git=not a.no_git)
    if a.check:
        cur = a.out.read_text() if a.out.is_file() else ""
        if cur != text:
            print(f"STALE: {a.out} differs from the generator's output", file=sys.stderr)
            return 1
        print(f"fresh: {a.out} sha256 {hashlib.sha256(text.encode()).hexdigest()}")
        return 0
    a.out.write_text(text)
    print(f"wrote {a.out} sha256 {hashlib.sha256(text.encode()).hexdigest()} ({len(text)} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
