#!/usr/bin/env python3
"""The production transport: one buffer of bytes, from the host gate to the wire.

§3b link 1 says the transport must send **the same in-memory bytes the host gate
accepted**. Re-reading the file after gating produces a different artifact with the same
name, and every property the gate established was about the bytes it held. That is not a
style preference — it is the link that makes `configuration_valid` mean anything.

So there is one object, `SealedPayload`, constructed once from bytes, and the three
consumers take *it*.

**And one authority.** The bytes being what was judged is worth nothing if the *judge* can
be swapped: the manifest carries the 292-address whitelist and the pinned base frames, so a
caller passing a bare dict could widen the whitelist by one address, flip that bit, recompute
the ECC correctly, and the fixed FAR/FDRI guard would still agree — reproduced, and
`run_candidate` reported `writable=True` and sent all 6,432 bytes. `PublishedCarrierAuthority`
closes that: it is loaded from the canonical carrier run, re-uses
`carrier_run.head_authority_problems()` so the bundle, the HEAD blobs and the manifest digest
all have to agree, and `run_candidate` accepts nothing else.

    authority = PublishedCarrierAuthority.load(RUN_DIR)        # reads files, before the run
    payload   = SealedPayload(build_sequence_bytes(authority.manifest, frames))
    run_candidate(payload, authority, transmit)                # gate -> guard -> wire

The authority is loaded BEFORE the gate-to-wire section, which stays a zero-file-read
region.

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
import json
import struct
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import board_carrier_guard as guard  # noqa: E402
import carrier_run as cr  # noqa: E402
import gate_candidate as hostgate  # noqa: E402
import icap_sequence as iseq  # noqa: E402

TOOL_VERSION = "board_carrier_exec.py/1.0.0"


class TransportRefusal(Exception):
    """A refusal on the path to the wire."""


class PublishedCarrierAuthority:
    """The manifest, and the proof that it is the one HEAD published.

    Loaded once, from a canonical carrier run, before anything is judged. `run_candidate`
    takes this and never a bare dict, because the manifest IS the whitelist and the pinned
    base: a caller who can supply it can widen what counts as a permitted bit, and the
    fixed FAR/FDRI guard would have no complaint — that was reproduced, ECC and all.
    """

    __slots__ = ("_manifest", "_run_dir", "_manifest_sha256")

    def __init__(self, manifest: dict, run_dir: Path, manifest_sha256: str) -> None:
        self._manifest = manifest
        self._run_dir = run_dir
        self._manifest_sha256 = manifest_sha256

    @classmethod
    def load(cls, run_dir: Path) -> "PublishedCarrierAuthority":
        """Refuse unless the run is the published one, bundle and HEAD blobs included."""
        problems = cr.head_authority_problems(run_dir)
        if problems:
            raise TransportRefusal(
                "the carrier run is not a published authority: "
                + "; ".join(p["message"] for p in problems)
            )
        bundle, load_problems = cr.load(run_dir)
        if load_problems or bundle is None:
            raise TransportRefusal(
                "the carrier run bundle does not verify: "
                + "; ".join(p["message"] for p in load_problems)
            )
        path = run_dir / "phenotype_manifest.json"
        raw = path.read_bytes()
        pinned = (bundle.get("artifacts") or {}).get("phenotype_manifest.json", {}).get("sha256")
        actual = hashlib.sha256(raw).hexdigest()
        if actual != pinned:
            raise TransportRefusal(
                f"the manifest does not match the digest the bundle pins ({actual} vs {pinned})"
            )
        return cls(json.loads(raw.decode("utf-8")), run_dir, actual)

    @property
    def manifest(self) -> dict:
        return self._manifest

    @property
    def manifest_sha256(self) -> str:
        return self._manifest_sha256

    @property
    def run_dir(self) -> Path:
        return self._run_dir


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


def run_candidate(payload: SealedPayload, authority: PublishedCarrierAuthority,
                  transmit) -> dict:
    """gate -> guard -> wire, over ONE buffer and ONE published authority.

    `authority` is not a dict, by type check as well as by signature: the manifest carries
    the whitelist and the pinned base, so accepting a caller-supplied one lets the caller
    decide what a permitted bit is.

    `transmit` is a callable taking bytes; the caller owns the session. Injected rather
    than opened here so the wiring can be tested without a board, and so this module never
    holds a transport it could quietly reopen. A production executor must bind it to a
    `BoardSession` whose `authorise_write()` has succeeded — see `board_uboot_transmit()`.
    """
    if not isinstance(authority, PublishedCarrierAuthority):
        raise TransportRefusal(
            "run_candidate takes a PublishedCarrierAuthority, not a manifest: a caller who "
            "supplies the manifest supplies the whitelist and the pinned base, and the "
            "fixed FAR/FDRI guard would not notice"
        )
    manifest = authority.manifest
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
        "authority_run_dir": str(authority.run_dir),
        "authority_manifest_sha256": authority.manifest_sha256,
    }


def board_uboot_transmit(session, control_plane: str = "uboot"):
    """A transmit callable structurally bound to a verified session and epoch.

    An arbitrary callable carries no session, no epoch and no control plane, so a run could
    verify one board and write to whatever the callable happened to hold. This asks
    `authorise_write()` on the SAME `BoardSession` before the first device write, and again
    for each candidate — the epoch invalidates an authorisation on any transport reopen,
    reset or disruption, which is precisely the window this closes.
    """
    def transmit(payload_bytes: bytes) -> None:
        session.authorise_write(control_plane)     # raises unless this session, this epoch
        session.write_sequence(payload_bytes)

    return transmit
