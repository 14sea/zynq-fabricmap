"""Shared fixtures of the B4 tests: the MARKED mechanics hypothesis (the latch's clock bit 0 read as not inverted —
kept after v0.3 as the fixture the mechanism tests run under; it says nothing about the fabric), the MARKED v021_hole
hypothesis (the superseded b4/hypothesis/ff_behaviour_v0.2.json, verified byte for byte against its old digest before
it is read, with the latch's clock bit 0 unknown — the domain hole of 0.2.1, under which the DOMAIN mechanism and the
F termination fact are exercised) and the injecting port that refuses at one attempt ordinal (DOMAIN or another refusal)."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

R = Path(__file__).resolve().parents[2]
for p in (R / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_execution as ex  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402


def mechanics_hypothesis() -> hy.Hypothesis:
    return hy.load().with_reading("clock_mode", "not_inverted", "not_inverted", "mechanics", context="latch")


def mechanics_fabric() -> fm.Fabric:
    return fm.Fabric(bm.site_mapping(), mechanics_hypothesis())


V021_REL = "b4/hypothesis/ff_behaviour_v0.2.json"            # the superseded file, kept byte for byte (the owner's ruling of 2026-10-18)
V021_SHA256 = "1118bedf4831bac3806be4aa3d9b56630912a946156869807f2c26f6374e6ed2"


def v021_hole_hypothesis() -> hy.Hypothesis:
    """The 0.2.1 hypothesis as a MARKED fixture: read from the kept v0.2 file only after its bytes hash to the old pinned
    digest (a changed file is an error here, never a different fixture); its sources are not re-verified (a fixture)."""
    raw = (R / V021_REL).read_bytes()
    got = hashlib.sha256(raw).hexdigest()
    if got != V021_SHA256:
        raise AssertionError(f"{V021_REL} hashes to {got[:16]}…, not the 0.2.1 digest {V021_SHA256[:16]}…: the kept file changed")
    return hy.fixture(json.loads(raw), "v021_hole")


def v021_hole_fabric() -> fm.Fabric:
    return fm.Fabric(bm.site_mapping(), v021_hole_hypothesis())


class InjectingPort(ex.ObservationPort):
    """Refuses with DOMAIN (or another refusal) at one attempt ordinal — the injection of the revised scope section 6.2."""
    __slots__ = ("refuse_at", "exc")

    def __init__(self, fabric, refuse_at: int, exc=None):
        super().__init__(fabric)
        self.refuse_at = refuse_at
        self.exc = exc

    def observe(self, config, stimulus):
        self.calls += 1
        if self.calls == self.refuse_at:
            raise (self.exc or fm.DomainRefusal())
        return self._observe(config, stimulus)
