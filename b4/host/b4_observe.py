#!/usr/bin/env python3
"""B4 — the AUDIT OBSERVATIONS of K9 and K10: a per-seed memo over an `ObservationPort` that keeps every unique
observation whole (the owner's ruling of 2026-10-18 on unit 2b-4a, section 4.2). These observations enter no search
ledger and no cartographer; they are the host's diagnostics, counted apart from the arms' calls.

    memo = Memo(port)                               # one per seed and per source identity; never shared across seeds
    obs_id, grid, hit = memo.observe(genome, stimulus)
    memo.calls, memo.hits, memo.records()           # the true port calls, the cache hits, every unique observation

The key is (genome, stimulus digest) under ONE source identity: the first trace's header fixes the identity (validated by
`b4_execution.provenance_findings`) and every later trace must carry the same one, else `SourceRefusal`. A hit changes the
call count only — never a comparison, a denominator or a value. A `DomainRefusal` propagates as it is: the caller decides
what it means (K10: invalid; K9: invalid), it is never absorbed here.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402


class Memo:
    def __init__(self, port: ex.ObservationPort):
        self.port = port
        self.addresses = tuple(port.addresses)
        self.n = len(self.addresses)
        self.calls = 0
        self.hits = 0
        self.provenance: dict | None = None
        self.provenance_sha256: str | None = None
        self._by_key: dict[tuple[int, str], int] = {}
        self._records: list[dict] = []

    def observe(self, genome: int, stimulus) -> tuple[int, list, bool]:
        if not isinstance(genome, int) or isinstance(genome, bool) or genome < 0 or genome >> self.n:
            raise ValueError("the genome is not over the port's addresses")
        steps = list(stimulus)
        ssha = ex.sha256_json(steps)
        key = (genome, ssha)
        if key in self._by_key:
            self.hits += 1
            rec = self._records[self._by_key[key]]
            return rec["id"], [list(r) for r in rec["q_grid"]], True
        config = ex.genome_to_config(genome, self.addresses)
        self.calls += 1
        trace = self.port.observe(config, steps)
        hdr = {k: trace.get(k) for k in ("hypothesis", "mapping", "fabric")} if isinstance(trace, dict) else None
        f = ex.provenance_findings(hdr)
        if f:
            raise ex.SourceRefusal("the observation source's identity is malformed: " + "; ".join(f))
        if self.provenance is None:
            self.provenance, self.provenance_sha256 = hdr, ex.sha256_json(hdr)
        elif hdr != self.provenance:
            raise ex.SourceRefusal("the observation source's identity changed between observations")
        grid = [list(s["q_after"]) for s in trace["steps"]]
        rec = {"id": len(self._records), "genome": genome, "genome_hex": ex.genome_hex(genome, self.n), "config_sha256": ex.sha256_json(config),
               "stimulus_sha256": ssha, "provenance_sha256": self.provenance_sha256, "fixture": hdr["hypothesis"]["fixture"],
               "fabric_kind": hdr["fabric"]["kind"], "trace_sha256": ex.sha256_json(grid), "q_grid": grid}
        self._by_key[key] = rec["id"]
        self._records.append(rec)
        return rec["id"], [list(r) for r in grid], False

    def records(self) -> list[dict]:
        return [dict(r, q_grid=[list(row) for row in r["q_grid"]]) for r in self._records]

    def summary(self) -> dict:
        return {"port_calls": self.calls, "cache_hits": self.hits, "unique_observations": len(self._records),
                "provenance": self.provenance, "provenance_sha256": self.provenance_sha256}
