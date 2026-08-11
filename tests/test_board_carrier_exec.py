"""The wiring: one buffer of bytes, from the host gate to the wire.

§3b link 1 — the transport must send the same in-memory bytes the host gate accepted. The
failure is quiet: gate a buffer, hand the transmitter a file with the same name, and every
check passes while something else reaches the device. So the tests here are mostly about
what the transport must NOT do.

The positive case is built with the real builder from the published manifest and the
published carrier's own frames — a no-op candidate, which is exactly what the calibration
transmits first.
"""

from __future__ import annotations

import builtins
import json
import struct
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import bitstream_frames as bf  # noqa: E402
import board_carrier_exec as ex  # noqa: E402
import board_carrier_guard as guard  # noqa: E402

RUN = REPO_ROOT / "gate_runs/claimb_round1_carrier_2026_08_11"


class WiringTests(unittest.TestCase):
    def setUp(self) -> None:
        path = RUN / "carrier.bit"
        if not path.is_file():
            self.skipTest("the published carrier run is not in this tree")
        with path.open("rb") as fh:
            if fh.read(40).startswith(b"version https://git-lfs.github.com/spec/"):
                self.skipTest("carrier.bit is an unpulled Git LFS pointer: `git lfs pull`")
        self.manifest = json.loads(
            (RUN / "phenotype_manifest.json").read_text(encoding="utf-8"))
        frames = bf.parse_frames(path)["frames"]
        self.targets = {}
        for entry in self.manifest["write_envelope"]["envelopes"]:
            for far_hex in entry["target_fars"]:
                far = int(far_hex, 16)
                self.targets[far] = list(frames[far])

    def payload(self) -> ex.SealedPayload:
        return ex.SealedPayload(ex.build_sequence_bytes(self.manifest, self.targets))

    def test_the_no_op_candidate_reaches_the_wire(self) -> None:
        sent: list[bytes] = []
        payload = self.payload()
        record = ex.run_candidate(payload, self.manifest, sent.append)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0], payload.unseal())
        self.assertEqual(record["sent_sha256"], payload.sha256)
        self.assertEqual(record["sent_bytes"], guard.TOTAL_BYTES)

    def test_the_bytes_gated_are_the_bytes_sent(self) -> None:
        """The whole point: one buffer, and the digest of what went out equals the digest
        of what was judged."""
        import hashlib
        sent: list[bytes] = []
        payload = self.payload()
        judged = hashlib.sha256(payload.unseal()).hexdigest()
        ex.run_candidate(payload, self.manifest, sent.append)
        self.assertEqual(hashlib.sha256(sent[0]).hexdigest(), judged)

    def test_the_transport_opens_no_file_between_the_gate_and_the_wire(self) -> None:
        """A path re-read is offline diagnosis only. If `run_candidate` ever opens
        anything, the artifact it sends is not the artifact it judged."""
        payload = self.payload()
        opened: list = []
        real_open, real_read = builtins.open, Path.read_bytes

        def watched_open(*a, **k):
            opened.append(a[0] if a else k.get("file"))
            return real_open(*a, **k)

        def watched_read(self_path, *a, **k):
            opened.append(self_path)
            return real_read(self_path, *a, **k)

        builtins.open, Path.read_bytes = watched_open, watched_read
        try:
            ex.run_candidate(payload, self.manifest, lambda _b: None)
        finally:
            builtins.open, Path.read_bytes = real_open, real_read
        self.assertEqual(opened, [], f"the transport read {opened}")

    def test_a_sealed_payload_cannot_be_built_from_a_path(self) -> None:
        with self.assertRaises(TypeError):
            ex.SealedPayload(RUN / "carrier.bit")          # type: ignore[arg-type]
        with self.assertRaises(TypeError):
            ex.SealedPayload(str(RUN / "carrier.bit"))     # type: ignore[arg-type]

    def test_a_payload_mutated_after_sealing_is_refused(self) -> None:
        payload = self.payload()
        object.__setattr__(payload, "_data", b"\x00" * guard.TOTAL_BYTES)
        with self.assertRaises(ex.TransportRefusal):
            payload.unseal()

    def test_a_candidate_the_host_gate_refuses_never_reaches_the_wire(self) -> None:
        words = list(struct.unpack(f">{guard.TOTAL_BYTES // 4}I", self.payload().unseal()))
        words[words.index(0x30002001) + 1] = 0x00400A24     # a FAR outside the envelope
        sent: list[bytes] = []
        with self.assertRaises(Exception):
            ex.run_candidate(ex.SealedPayload(struct.pack(f">{len(words)}I", *words)),
                             self.manifest, sent.append)
        self.assertEqual(sent, [], "bytes reached the wire after a refusal")

    def test_a_manifest_disagreeing_with_the_fixed_bounds_never_reaches_the_wire(self) -> None:
        import copy
        doc = copy.deepcopy(self.manifest)
        doc["write_envelope"]["total_bytes"] = guard.TOTAL_BYTES + 4
        sent: list[bytes] = []
        with self.assertRaises(Exception):
            ex.run_candidate(self.payload(), doc, sent.append)
        self.assertEqual(sent, [])

    def test_the_guard_runs_before_the_wire_not_after(self) -> None:
        """Ordering is the property: a guard that ran after transmission would be a report,
        not a guard."""
        order: list[str] = []
        real_guard = guard.guard_sequence

        def watched(payload_bytes):
            order.append("guard")
            return real_guard(payload_bytes)

        guard.guard_sequence = watched
        try:
            ex.run_candidate(self.payload(), self.manifest,
                             lambda _b: order.append("wire"))
        finally:
            guard.guard_sequence = real_guard
        self.assertEqual(order, ["guard", "wire"])


if __name__ == "__main__":
    unittest.main()
