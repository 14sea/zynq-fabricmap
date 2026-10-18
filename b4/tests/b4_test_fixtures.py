"""Shared fixtures of the B4 tests: the MARKED mechanics hypothesis (the latch's clock bit 0 read as not inverted, so
the domain has no hole — for exercising complete runs; it says nothing about the fabric) and the injecting port
that refuses at one attempt ordinal (DOMAIN or another refusal)."""
from __future__ import annotations

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
