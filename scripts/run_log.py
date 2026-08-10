#!/usr/bin/env python3
"""The Claim B run log: what was written, to what, under which authorisation.

Preregistration §7. A run log exists so a result can be re-derived and disputed later,
which means it must record the things that would let someone re-run the candidate stream
and the things that would explain a divergence. Both halves matter: pinning only the
artifacts hides the recoveries, and recording only the events hides what was actually
sent.

Per run: the map hash, the phenotype manifest hash (which itself pins the base bitstream
and the 15 frames), the arm, the seed schedule, the budget and how it was derived.

Per candidate: the seed, the arm, the candidate hash, the **frame-diff hash actually sent**
and — separately — the **readback hash**, because §6 item 8 scores fitness only when the
readback equals the candidate. Recording one number for both would make that check
unfalsifiable after the fact.

Per event: every disruption, with the epoch it ended, and every re-verification with the
epoch it opened. An authorisation never spans a disruption (see `gate_board_identity`), so
the log must show which epoch each write belonged to; a candidate whose epoch does not
appear in the identity record is a candidate written without a live authorisation, and a
reader should be able to find that without trusting the writer.

Nothing here decides anything. It records. The gates decide, and this file is what makes
their decisions auditable afterwards.
"""

from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import icap_sequence as iseq  # noqa: E402

TOOL_VERSION = "run_log.py/1.0.0"
SCHEMA_VERSION = "1.0.0"

ARMS = frozenset({"map_guided", "random_safe"})


class RunLogError(Exception):
    """A refusal."""


def sha256_hex(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def sequence_hash(envelopes: list[list[int]]) -> str:
    """One hash over the exact words that will be transmitted, in order."""
    return sha256_hex(b"".join(iseq.to_bytes(words) for words in envelopes))


def frames_hash(frames: dict[int, list[int]]) -> str:
    """Order-independent over FARs, so a dict reordering is not a different candidate."""
    parts = []
    for far in sorted(frames):
        parts.append(far.to_bytes(4, "big"))
        parts.append(iseq.to_bytes(frames[far]))
    return sha256_hex(b"".join(parts))


class RunLog:
    """Append-only in spirit: entries are added, never edited."""

    def __init__(
        self,
        run_id: str,
        arm: str,
        local_map: dict,
        phenotype_manifest: dict,
        budget: dict,
        seed_schedule: list,
        preregistration: dict,
    ):
        if arm not in ARMS:
            raise RunLogError(f"unknown arm {arm!r}; expected one of {sorted(ARMS)}")
        self.doc = {
            "schema": "claimb_run_log",
            "schema_version": SCHEMA_VERSION,
            "run_id": run_id,
            "arm": arm,
            "started_at": time.time(),
            "preregistration": preregistration,
            "local_map": {
                "map_id": local_map["map_id"],
                "sha256": None,  # filled by pin_artifact
                "address_count": local_map["universe"]["address_count"],
            },
            "phenotype_manifest": {
                "phenotype_id": phenotype_manifest["phenotype_id"],
                "sha256": None,
                "base_bitstream_sha256": phenotype_manifest["base_bitstream"]["sha256"],
                "target_far_count": phenotype_manifest["write_envelope"]["target_far_count"],
                "flush_far_count": phenotype_manifest["write_envelope"]["flush_far_count"],
            },
            "budget": budget,
            "seed_schedule": seed_schedule,
            "identity_records": [],
            "disruptions": [],
            "candidates": [],
            "tool_versions": {"run_log": TOOL_VERSION},
        }

    # -- pinning ---------------------------------------------------------------

    def pin_artifact(self, which: str, path: Path) -> str:
        if which not in ("local_map", "phenotype_manifest"):
            raise RunLogError(f"nothing to pin called {which!r}")
        digest = sha256_hex(path.read_bytes())
        self.doc[which]["sha256"] = digest
        self.doc[which]["path"] = (
            path.relative_to(REPO_ROOT).as_posix()
            if path.is_relative_to(REPO_ROOT)
            else str(path)
        )
        return digest

    # -- session lifecycle -----------------------------------------------------

    def record_identity(self, identity: dict) -> None:
        """A verification that opened an epoch."""
        self.doc["identity_records"].append(
            {
                "epoch": identity["epoch"],
                "at": time.time(),
                "parsed": identity["parsed"],
                "transport": identity["transport"],
                "raw_replies": identity["raw_replies"],
            }
        )

    def record_disruption(self, entry: dict) -> None:
        self.doc["disruptions"].append(dict(entry))

    def authorised_epochs(self) -> set[int]:
        return {record["epoch"] for record in self.doc["identity_records"]}

    # -- candidates ------------------------------------------------------------

    def record_candidate(
        self,
        *,
        index: int,
        seed: int,
        epoch: int,
        candidate_frames: dict[int, list[int]],
        envelopes: list[list[int]],
        gate_verdict: dict,
        readback_frames: dict[int, list[int]] | None,
        fitness: float | None,
        scored: bool,
        notes: str = "",
    ) -> dict:
        candidate_hash = frames_hash(candidate_frames)
        readback_hash = frames_hash(readback_frames) if readback_frames else None

        if scored:
            if readback_hash is None:
                raise RunLogError(
                    f"candidate {index} is marked scored with no readback — §6 item 8 "
                    "scores fitness only when the readback equals the candidate"
                )
            if readback_hash != candidate_hash:
                raise RunLogError(
                    f"candidate {index} is marked scored but the readback "
                    f"({readback_hash[:12]}…) differs from the candidate "
                    f"({candidate_hash[:12]}…)"
                )
            if not gate_verdict.get("writable"):
                raise RunLogError(
                    f"candidate {index} is marked scored but the gate refused it"
                )
            if fitness is None:
                raise RunLogError(f"candidate {index} is marked scored with no fitness")

        entry = {
            "index": index,
            "seed": seed,
            "arm": self.doc["arm"],
            "epoch": epoch,
            "at": time.time(),
            "candidate_sha256": candidate_hash,
            "sequence_sha256": sequence_hash(envelopes),
            "readback_sha256": readback_hash,
            "readback_matches": readback_hash == candidate_hash if readback_hash else False,
            "gate": {
                "writable": bool(gate_verdict.get("writable")),
                "buckets": gate_verdict.get("buckets", {}),
                "finding_count": len(gate_verdict.get("findings", [])),
            },
            "scored": scored,
            "fitness": fitness,
            "notes": notes,
        }
        self.doc["candidates"].append(entry)
        return entry

    # -- integrity -------------------------------------------------------------

    def problems(self) -> list[str]:
        """Checks a reader can run over the finished log without trusting the writer."""
        out = []
        for which in ("local_map", "phenotype_manifest"):
            if not self.doc[which].get("sha256"):
                out.append(f"{which} was never pinned")

        authorised = self.authorised_epochs()
        for entry in self.doc["candidates"]:
            if entry["epoch"] not in authorised:
                out.append(
                    f"candidate {entry['index']} was written in epoch {entry['epoch']}, "
                    "which no identity record opened"
                )
            if entry["scored"] and not entry["readback_matches"]:
                out.append(
                    f"candidate {entry['index']} is scored but its readback does not match"
                )
            if entry["scored"] and not entry["gate"]["writable"]:
                out.append(f"candidate {entry['index']} is scored but the gate refused it")

        scored = [e for e in self.doc["candidates"] if e["scored"]]
        if self.doc["budget"].get("evaluations") is not None:
            if len(scored) > self.doc["budget"]["evaluations"]:
                out.append(
                    f"{len(scored)} scored evaluations exceed the budget of "
                    f"{self.doc['budget']['evaluations']}"
                )
        return out

    def finish(self) -> dict:
        self.doc["completed_at"] = time.time()
        self.doc["totals"] = {
            "candidates": len(self.doc["candidates"]),
            "scored": sum(1 for e in self.doc["candidates"] if e["scored"]),
            "gate_refusals": sum(
                1 for e in self.doc["candidates"] if not e["gate"]["writable"]
            ),
            "readback_mismatches": sum(
                1
                for e in self.doc["candidates"]
                if e["readback_sha256"] and not e["readback_matches"]
            ),
            "disruptions": len(self.doc["disruptions"]),
            "epochs": len(self.authorised_epochs()),
        }
        self.doc["problems"] = self.problems()
        return self.doc

    def write(self, path: Path) -> dict:
        doc = self.finish()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
        return doc
