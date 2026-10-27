#!/usr/bin/env python3
"""B4Q — the bench NOTARY (the signer principal of link 1) for the host session: derives the candidate's frames itself
(host/b4q_frames.py, the twin of the executing side's derive), commits to them in the instrument's candidate_sha256 domain,
and signs commit ‖ six ZERO table words ‖ the PL's nonce with the instrument's signer library (validators.signer — the same
arithmetic the carrier's verbatim p3_siphash.v computes; bound read-only as tb/b4/gen_b4_fixture.py binds it). It computes
NO expected tables and attests nothing about what the fabric should read (B1's non-semantic contract carried over). Its
gate is the write set's: a genome outside 21 bits, or a candidate whose frames differ from the loaded image anywhere but the
whitelisted bits and the ECC words, is refused. The key is a FIXTURE key on a private temporary file — the production key
provisioning (`provisioning P3-K`, a ruling) is not modelled here."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(R / "host"))
import b4q_frames as fr  # noqa: E402

ZERO_TABLES = [0] * 6
FIXTURE_KEY = bytes(range(16))               # tb/b4/gen_b4_fixture.py's KEY_A


def _signer():
    import claimb_r1p_instrument as inst
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    from validators import signer as sg
    return sg


class NotaryRefusal(ValueError):
    pass


class Notary:
    def __init__(self, base: dict, wl, key: bytes = FIXTURE_KEY):
        self.base, self.wl = base, wl
        self.sg = _signer()
        self.tmp = Path(tempfile.mkdtemp(prefix="b4q_notary_"))
        kp = self.tmp / "K"; kp.write_bytes(key); os.chmod(kp, 0o400)
        self.holder = self.sg.KeyHolder(kp)
        self.key = key
        self.log = []

    @property
    def key_id(self) -> str:
        return self.holder.key_id

    def gate(self, genome: int) -> dict:
        """The write-set gate: the derived frames differ from the loaded image only at the whitelisted bits and word 50."""
        if not isinstance(genome, int) or not 0 <= genome < (1 << fr.GENOME_BITS):
            raise NotaryRefusal("the genome is not a 21-bit value")
        frames = fr.derive_frames(genome, self.base["frames"], self.wl)
        allowed = {(far, w) for far, w, _ in self.wl}
        for far in fr.TARGET_FARS:
            for w in range(fr.FRAME_WORDS):
                if frames[far][w] != self.base["frames"][far][w] and w != 50 and (far, w) not in allowed:
                    raise NotaryRefusal(f"frame {far:#010x} word {w} differs outside the whitelist")
        return {"writable": True, "candidate_sha256": fr.frames_hash(frames), "frames": frames}

    def sign(self, genome: int, nonce: int) -> dict:
        v = self.gate(genome)
        commit = bytes.fromhex(v["candidate_sha256"])
        payload = self.sg.sign_arm(self.holder, {"writable": True, "candidate_sha256": v["candidate_sha256"]}, commit, ZERO_TABLES, nonce.to_bytes(8, "little"))
        entry = {"genome": genome, "genome_hex": f"{genome:08x}", "nonce": f"{nonce:016x}", "commit": v["candidate_sha256"], "expected_tables": [f"{t:016x}" for t in ZERO_TABLES],
                 "tag": payload.tag.hex(), "key_id": self.holder.key_id, "contract": "b1-nonsemantic-v1 (carried to B4Q: zero tables, no attestation)"}
        self.log.append(entry)
        return {"words": payload.words(), **entry}
