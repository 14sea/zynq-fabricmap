#!/usr/bin/env python3
"""Judge the serialized ICAP sequence a candidate will actually send.

Preregistration §6 item 5: *"the candidate gate parses the final serialized ICAP sequence,
not the operator's intent"*. Everything here is recomputed from the word stream and the
pinned manifest. The operator's description of what it meant to do is not an input, and
neither is the builder's internal state — a gate that read either would agree with the
thing it is judging.

**Two semantics, ruled 2026-08-10, and they are different rules:**

* **target frames** — only the whitelisted addresses may differ from the pinned base, plus
  word 50's ECC, which must equal a *correct recomputation* over the resulting content. An
  ECC that merely differs is not accepted, and neither is a stale one.
* **flush frames** — nothing may differ. All 101 words must equal the pinned base
  verbatim, word 50 included. Falling inside the FDRI range does not make a frame
  writable, and two of the three flush frames belong to a different column entirely.

A single "matches the base outside the whitelist" rule over all 15 frames would be wrong,
which is why `frame_findings` dispatches on the pinned role rather than on where a frame
happens to sit in the burst.

Findings are returned **already bucketed** by kind. This repo has been bitten by a gate
that classified findings by the English prefix of their message — `startswith("pair")`
made a missing declaration report a pass. Message strings here are for humans only;
nothing branches on them.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import frame_ecc as fe  # noqa: E402
import icap_sequence as iseq  # noqa: E402

TOOL_VERSION = "gate_candidate.py/1.0.0"

KINDS = (
    "structure",       # the envelope shape itself
    "skeleton",        # the non-payload packet trace differing from the pinned envelope
    "addressing",      # FAR sets, IDCODE, FDRI lengths
    "forbidden",       # commands that must never appear
    "target_frame",    # a target frame differing outside the whitelist
    "flush_frame",     # a flush frame differing at all
    "ecc",             # an ECC field that is not a correct recomputation
)


def expected_trace(far: int, idcode: int, payload_words: int) -> list[dict]:
    """The one control skeleton a candidate write may have.

    Written out here independently rather than obtained by calling the builder: a gate
    that asked the builder what it should expect would agree with it by construction,
    including when the builder is wrong. This list is the preregistered envelope of §6
    transcribed, and the only free values are the FAR, the IDCODE and the payload length.
    """
    return (
        [{"kind": "dummy", "count": 8}, {"kind": "sync"}, {"kind": "noop"}]
        + [{"kind": "cmd", "value": iseq.CMD_RCRC}]
        + [{"kind": "noop"}, {"kind": "noop"}]
        + [{"kind": "idcode", "value": idcode}]
        + [{"kind": "cmd", "value": iseq.CMD_WCFG}, {"kind": "noop"}]
        + [{"kind": "far", "value": far}]
        + [{"kind": "fdri_header", "words": 0},
           {"kind": "fdri_data", "words": payload_words}]
        + [{"kind": "crc", "value": 0}]
        + [{"kind": "cmd", "value": iseq.CMD_DESYNC}]
        + [{"kind": "noop"}] * 4
    )


def describe(entry: dict) -> str:
    kind = entry.get("kind")
    if kind in ("cmd", "far", "idcode", "crc"):
        return f"{kind}={entry['value']:#010x}"
    if kind in ("fdri_header", "fdri_data"):
        return f"{kind}[{entry['words']}]"
    if kind == "dummy":
        return f"dummy x{entry['count']}"
    if kind == "write":
        return f"write reg={entry['reg']} count={entry['count']}"
    if kind == "unknown":
        return f"unknown word {entry['word']:#010x}"
    return str(kind)


def skeleton_findings(index: int, trace: list, expected: list) -> list[dict]:
    """Compare the non-payload packet trace element by element.

    A membership check cannot see an ABSENT command or a wrong CRC value — it only sees
    what is present. The consumer demonstrated the consequence: removing WCFG, removing
    RCRC, and writing a non-zero CRC each passed the previous gate with zero findings,
    because none of them adds a forbidden command and DESYNC was still there.
    """
    if trace == expected:
        return []
    out = []
    for position, (got, want) in enumerate(zip(trace, expected)):
        if got != want:
            out.append(
                finding(
                    "skeleton",
                    f"envelope {index}: packet {position} is {describe(got)}, "
                    f"the pinned envelope has {describe(want)}",
                    position=position,
                    got=got,
                    expected=want,
                )
            )
            break
    if len(trace) != len(expected):
        out.append(
            finding(
                "skeleton",
                f"envelope {index}: {len(trace)} control packets, the pinned envelope "
                f"has {len(expected)}",
                got_length=len(trace),
                expected_length=len(expected),
            )
        )
    return out


def finding(kind: str, message: str, **detail) -> dict:
    if kind not in KINDS:
        raise ValueError(f"unknown finding kind: {kind}")
    return {"kind": kind, "message": message, **detail}


def pinned_frames(manifest: dict) -> tuple[dict[int, list[int]], dict[int, str]]:
    frames, roles = {}, {}
    for record in manifest["frames"]:
        far = int(record["far"], 16)
        frames[far] = [int(w, 16) for w in record["words"]]
        roles[far] = record["role"]
    return frames, roles


def whitelist_by_far(manifest: dict) -> dict[int, set[tuple[int, int]]]:
    out: dict[int, set[tuple[int, int]]] = {}
    for far_hex, entries in manifest["ownership"]["whitelist_by_far"].items():
        out[int(far_hex, 16)] = {(e["word"], e["bit"]) for e in entries}
    return out


def differing_bits(base: list[int], candidate: list[int]) -> list[tuple[int, int]]:
    bits = []
    for word_index in range(bf.FRAME_WORDS):
        delta = base[word_index] ^ candidate[word_index]
        while delta:
            low = delta & -delta
            bits.append((word_index, low.bit_length() - 1))
            delta ^= low
    return bits


def target_frame_findings(
    far: int, base: list[int], candidate: list[int], allowed: set[tuple[int, int]]
) -> list[dict]:
    """Only whitelisted bits, plus a correctly recomputed ECC."""
    out = []
    offending = [
        (word, bit)
        for word, bit in differing_bits(base, candidate)
        if word != fe.ECC_WORD and (word, bit) not in allowed
    ]
    if offending:
        out.append(
            finding(
                "target_frame",
                f"{far:#010x}: {len(offending)} bit(s) differ outside the whitelist",
                far=f"{far:#010x}",
                bits=[f"{w}/{b}" for w, b in offending[:16]],
                count=len(offending),
            )
        )

    expected = fe.calculate_ecc(candidate) & fe.ECC_MASK
    actual = fe.stored_ecc(candidate)
    if actual != expected:
        out.append(
            finding(
                "ecc",
                f"{far:#010x}: ECC {actual:#06x} is not the recomputation {expected:#06x}",
                far=f"{far:#010x}",
                stored=f"{actual:#06x}",
                recomputed=f"{expected:#06x}",
            )
        )

    upper_delta = (base[fe.ECC_WORD] ^ candidate[fe.ECC_WORD]) & fe.ECC_KEEP
    if upper_delta:
        out.append(
            finding(
                "target_frame",
                f"{far:#010x}: word 50 differs outside the ECC field",
                far=f"{far:#010x}",
                delta=f"{upper_delta:#010x}",
            )
        )
    return out


def flush_frame_findings(far: int, base: list[int], candidate: list[int]) -> list[dict]:
    """Verbatim, ECC included. No exception of any kind."""
    if candidate == base:
        return []
    words = [i for i in range(bf.FRAME_WORDS) if base[i] != candidate[i]]
    return [
        finding(
            "flush_frame",
            f"{far:#010x}: flush frame differs from the pinned base in "
            f"{len(words)} word(s) — flush frames admit no difference at all",
            far=f"{far:#010x}",
            words=words[:16],
            count=len(words),
        )
    ]


def envelope_findings(
    index: int, words: list[int], spec: dict, manifest: dict,
    base_frames: dict[int, list[int]], roles: dict[int, str],
    allowed: dict[int, set[tuple[int, int]]],
) -> list[dict]:
    out: list[dict] = []
    record = iseq.parse_sequence(words)
    idcode = int(manifest["base_bitstream"]["idcode"], 16)

    if not record["synced"]:
        out.append(finding("structure", f"envelope {index}: no sync word"))
    if record["truncated"]:
        first = record["truncated"][0]
        out.append(
            finding(
                "structure",
                f"envelope {index}: a packet at word {first['index']} declares "
                f"{first['declared']} payload word(s) but only {first['available']} "
                "remain — the stream is truncated",
                truncated=first,
            )
        )
    if record["unknown"]:
        out.append(
            finding(
                "structure",
                f"envelope {index}: {len(record['unknown'])} unrecognised packet(s)",
                first=record["unknown"][0],
            )
        )
    if iseq.CMD_DESYNC not in record["commands"]:
        out.append(finding("structure", f"envelope {index}: never desyncs"))

    for cmd in record["commands"]:
        if cmd in iseq.FORBIDDEN_CMDS:
            out.append(
                finding(
                    "forbidden",
                    f"envelope {index}: forbidden command "
                    f"{iseq.FORBIDDEN_CMDS[cmd]} ({cmd:#010x})",
                    command=f"{cmd:#010x}",
                )
            )

    # The skeleton comparison subsumes the membership checks above and catches what they
    # structurally cannot: an omission. Both are kept — the named forbidden commands give
    # a better message for the case that matters most, and the trace gives completeness.
    out.extend(
        skeleton_findings(
            index,
            record["trace"],
            expected_trace(int(spec["far_set"], 16), idcode, spec["payload_words"]),
        )
    )

    if record["idcodes"] != [idcode]:
        out.append(
            finding(
                "addressing",
                f"envelope {index}: IDCODE writes {[hex(i) for i in record['idcodes']]}, "
                f"expected exactly [{idcode:#010x}]",
            )
        )

    expected_far = int(spec["far_set"], 16)
    if record["far_sets"] != [expected_far]:
        out.append(
            finding(
                "addressing",
                f"envelope {index}: FAR sets {[hex(f) for f in record['far_sets']]}, "
                f"expected exactly [{expected_far:#010x}] — multiple FAR sets in one "
                "envelope mis-commit the buffered frame and corrupt the array",
            )
        )

    if len(record["fdri"]) != 1:
        out.append(
            finding(
                "addressing",
                f"envelope {index}: {len(record['fdri'])} FDRI block(s), expected 1",
            )
        )
        return out

    block = record["fdri"][0]
    expected_words = spec["payload_words"]
    # Mutation note: removing this check is BUCKET-EQUIVALENT. Any wrong length is caught
    # a few lines below — a non-multiple of 101 by `split_frames`, a wrong multiple by the
    # frame-count comparison — and both land in the same bucket, so no test can separate
    # them while findings are classified by kind rather than by message. It is kept for
    # the clearer message and the early return, not because it is load-bearing.
    if block["words"] != expected_words:
        out.append(
            finding(
                "addressing",
                f"envelope {index}: FDRI carries {block['words']} words, "
                f"expected {expected_words}",
            )
        )
        return out

    try:
        frames = iseq.split_frames(block["payload"])
    except iseq.SequenceError as exc:
        out.append(finding("structure", f"envelope {index}: {exc}"))
        return out

    order = [int(f, 16) for f in spec["target_fars"]] + [int(spec["flush_far"], 16)]
    if len(frames) != len(order):
        out.append(
            finding(
                "addressing",
                f"envelope {index}: {len(frames)} frames for {len(order)} addresses",
            )
        )
        return out

    for far, frame in zip(order, frames):
        base = base_frames[far]
        if roles[far] == "flush":
            out.extend(flush_frame_findings(far, base, frame))
        else:
            out.extend(target_frame_findings(far, base, frame, allowed.get(far, set())))
    return out


def gate_candidate(manifest: dict, envelopes: list[list[int]]) -> dict:
    """Judge every envelope. Returns bucketed findings and a verdict."""
    base_frames, roles = pinned_frames(manifest)
    allowed = whitelist_by_far(manifest)
    specs = manifest["write_envelope"]["envelopes"]

    findings: list[dict] = []
    if len(envelopes) != len(specs):
        findings.append(
            finding(
                "structure",
                f"{len(envelopes)} envelope(s) for {len(specs)} pinned by the manifest",
            )
        )
    for index, (words, spec) in enumerate(zip(envelopes, specs)):
        findings.extend(
            envelope_findings(index, words, spec, manifest, base_frames, roles, allowed)
        )

    buckets = {kind: [f for f in findings if f["kind"] == kind] for kind in KINDS}
    return {
        "tool": TOOL_VERSION,
        "envelopes": len(envelopes),
        "findings": findings,
        "buckets": {k: len(v) for k, v in buckets.items()},
        "writable": not findings,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--sequence", type=Path, nargs="+", required=True,
                    help="one binary file per envelope, big-endian 32-bit words")
    args = ap.parse_args()

    manifest = json.loads(args.manifest.read_text())
    envelopes = []
    for path in args.sequence:
        blob = path.read_bytes()
        if len(blob) % 4:
            print(f"REFUSED: {path} is not a whole number of words", file=sys.stderr)
            return 2
        envelopes.append([int.from_bytes(blob[k:k + 4], "big") for k in range(0, len(blob), 4)])

    verdict = gate_candidate(manifest, envelopes)
    for item in verdict["findings"]:
        print(f"  [{item['kind']}] {item['message']}")
    print(json.dumps(verdict["buckets"]))
    if verdict["writable"]:
        print("CANDIDATE WRITABLE")
        return 0
    print("CANDIDATE REFUSED")
    return 1


if __name__ == "__main__":
    sys.exit(main())
