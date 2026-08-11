#!/usr/bin/env python3
"""The production transport: one buffer of bytes, from the host gate to the wire.

§3b link 1 says the transport must send **the same in-memory bytes the host gate
accepted**. Re-reading the file after gating produces a different artifact with the same
name, and every property the gate established was about the bytes it held. That is not a
style preference — it is the link that makes `configuration_valid` mean anything.

So there is one object, `SealedPayload`, constructed once from bytes, and the three
consumers take *it*:

    payload = SealedPayload(build_sequence_bytes(manifest, frames))
    run_candidate(payload, manifest, session)      # gate -> guard -> wire

`SealedPayload` seals its digest at construction and re-checks it before every handoff, so
a mutation anywhere in the chain is caught at the next step rather than on the board. It
exposes no path and cannot be constructed from one: a CLI that re-read a file to fill it
would reintroduce exactly what this exists to prevent. Reading a sequence from disk is
**offline diagnosis only** and lives in `board_carrier_guard.py`'s CLI, which never
transmits.

The board-side guard runs on the bytes at the moment of transmission, after the host gate
and independently of it, and the fabric checks them again word by word.
"""

from __future__ import annotations

import hashlib
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_carrier_guard as guard  # noqa: E402
import gate_candidate as hostgate  # noqa: E402
import icap_sequence as iseq  # noqa: E402

TOOL_VERSION = "board_carrier_exec.py/1.0.0"


class TransportRefusal(Exception):
    """A refusal on the path to the wire."""


class SealedPayload:
    """Bytes plus the digest they had when they were sealed.

    Deliberately NOT constructible from a path. The failure this guards against is quiet:
    gate a buffer, then hand the transmitter a file with the same name, and every check
    passed while something else went to the device.
    """

    __slots__ = ("_data", "_sha256")

    def __init__(self, data: bytes) -> None:
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError(
                "SealedPayload takes bytes, not a path: re-reading a file after the gate "
                "sends a different artifact with the same name"
            )
        self._data = bytes(data)
        self._sha256 = hashlib.sha256(self._data).hexdigest()

    @property
    def sha256(self) -> str:
        return self._sha256

    def __len__(self) -> int:
        return len(self._data)

    def unseal(self) -> bytes:
        """The bytes, re-checked against the seal at every handoff."""
        if hashlib.sha256(self._data).hexdigest() != self._sha256:
            raise TransportRefusal(
                "the payload changed after it was sealed: what the gate accepted is not "
                "what is about to be sent"
            )
        return self._data


def build_sequence_bytes(manifest: dict, candidate_frames: dict[int, list[int]]) -> bytes:
    """Serialize in memory. Nothing in this module writes the sequence to disk first."""
    envelopes = iseq.build_sequence(manifest, candidate_frames)
    return b"".join(struct.pack(f">{len(e)}I", *e) for e in envelopes)


def envelopes_of(payload: SealedPayload) -> list[list[int]]:
    """The word lists the host gate judges — derived from the sealed bytes themselves."""
    words = list(struct.unpack(f">{len(payload) // 4}I", payload.unseal()))
    size = guard.ENVELOPE_WORDS
    return [words[i * size:(i + 1) * size] for i in range(guard.ENVELOPES)]


def run_candidate(payload: SealedPayload, manifest: dict, transmit) -> dict:
    """gate -> guard -> wire, over ONE buffer. Returns what was actually sent.

    `transmit` is a callable taking bytes; the caller owns the session. Injected rather
    than opened here so the wiring can be tested without a board, and so this module never
    holds a transport it could quietly reopen.
    """
    sealed_at_entry = payload.sha256

    verdict = hostgate.gate_candidate(manifest, envelopes_of(payload))
    if not verdict.get("writable"):
        raise TransportRefusal(
            f"the host gate refused the candidate: {len(verdict.get('findings', []))} finding(s)"
        )

    disagreements = guard.check_against_manifest(manifest)
    if disagreements:
        raise TransportRefusal("; ".join(disagreements))

    # the board-side guard sees the SAME object, not a re-read
    guard.guard_sequence(payload.unseal())

    transmit(payload.unseal())

    if payload.sha256 != sealed_at_entry:
        raise TransportRefusal("the payload's seal changed during the run")
    return {
        "tool": TOOL_VERSION,
        "sent_sha256": payload.sha256,
        "sent_bytes": len(payload),
        "gate_verdict_writable": True,
    }
