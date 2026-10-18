#!/usr/bin/env python3
"""B4 — the SOFT, MONOTONIC deadline of the exploration harness (the owner's ruling of 2026-10-18 on unit 2b-4a,
section 3.3). `time.monotonic` is the clock; UTC is only a timestamp. The deadline counts from the moment the harness
opens its pre-flight, not from the first search.

    dl = Deadline(seconds)                  # starts now (monotonic)
    dl.check()                              # raises StopWork once expired; called BETWEEN work units, never inside one
    dl.expired(); dl.elapsed(); dl.checks   # for the record

The deadline is SOFT: an engine run, a replay, one cartographer ingest, one model observation, one bootstrap of 1 000
experiments are work units that are not interrupted (no engine or replay change), so the batch may overrun by the
length of one started unit; after expiry no new unit starts, what has returned is written, and the batch is
`incomplete`. A function that takes `check` calls it before each unit and, on `StopWork`, returns what it has with
`complete = False` — the chunking changes the stopping point only, never a value: with a check that never raises the
result is identical to a run with no check.
"""
from __future__ import annotations

import time


class StopWork(Exception):
    """Raised by a deadline check between work units; the caller stops starting new units and keeps what it has."""


def no_check() -> None:
    return None


class Deadline:
    def __init__(self, seconds: int, clock=time.monotonic):
        if not isinstance(seconds, int) or isinstance(seconds, bool) or seconds <= 0:
            raise ValueError("the deadline is a positive integer number of seconds")
        self.seconds = seconds
        self._clock = clock
        self.start = clock()
        self.checks = 0
        self.first_expired_at: float | None = None

    def elapsed(self) -> float:
        return self._clock() - self.start

    def expired(self) -> bool:
        e = self.elapsed() >= self.seconds
        if e and self.first_expired_at is None:
            self.first_expired_at = self.elapsed()
        return e

    def check(self) -> None:
        self.checks += 1
        if self.expired():
            raise StopWork(f"the soft deadline of {self.seconds} s passed after {self.elapsed():.3f} s (check {self.checks})")

    def record(self) -> dict:
        return {"seconds": self.seconds, "elapsed_s": round(self.elapsed(), 3), "checks": self.checks, "expired": self.expired(),
                "first_expired_at_s": None if self.first_expired_at is None else round(self.first_expired_at, 3), "clock": "time.monotonic"}
