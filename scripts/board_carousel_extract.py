#!/usr/bin/env python3
"""Reconstruct a mailbox carousel POSITIONALLY from a long-run monitor trace.

Hard-won rule (M1, v2 A/B round): the mailbox latches only the last word, and
distinct-value polling silently drops any word that repeats consecutively or is
byte-identical across pages.  A carousel must therefore always be rebuilt from
the ordered, timestamped transition trace — NEVER from a first-seen set.

Usage:
    board_carousel_extract.py <monitor.log> [--head a7000000] [--cycle -1]

Prints the words of one full cycle (head word .. word before the next head),
one per line, plus a summary.  With two or more complete cycles present it also
reports whether they are byte-identical, which is the self-consistency check
used for every board verdict in this repo.
"""

import argparse
import re
import sys

TRACE_RE = re.compile(r"^T\+\s*([0-9.]+)s\s+0x([0-9a-fA-F]{8})\s*$")


def load_trace(path):
    out = []
    with open(path) as handle:
        for line in handle:
            match = TRACE_RE.match(line.strip())
            if match:
                out.append((float(match.group(1)), match.group(2).lower()))
    return out


def cycles_from(trace, head):
    starts = [i for i, (_, word) in enumerate(trace) if word == head]
    return [trace[a:b] for a, b in zip(starts, starts[1:])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("log")
    ap.add_argument("--head", default="a7000000", help="carousel head word (hex, no 0x)")
    ap.add_argument("--cycle", type=int, default=-1, help="which complete cycle to print")
    ap.add_argument("--words-only", action="store_true")
    args = ap.parse_args()

    trace = load_trace(args.log)
    cycles = cycles_from(trace, args.head.lower())
    if not cycles:
        print(f"no complete cycle for head {args.head} in {len(trace)} transitions", file=sys.stderr)
        return 1

    chosen = cycles[args.cycle]
    words = [word for _, word in chosen]
    for word in words:
        print(word if args.words_only else f"0x{word}")

    if not args.words_only:
        print(f"# {len(words)} words, cycle {args.cycle} of {len(cycles)} complete cycles",
              file=sys.stderr)
        print(f"# span T+{chosen[0][0]:.1f}s .. T+{chosen[-1][0]:.1f}s", file=sys.stderr)
        if len(cycles) >= 2:
            seqs = [[word for _, word in cycle] for cycle in cycles]
            same = all(seq == seqs[-1] for seq in seqs)
            print(f"# {len(cycles)} cycles byte-identical: {same}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
