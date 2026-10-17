#!/usr/bin/env python3
"""B4-FF — the simulated fabric: a configuration of the 21 addresses plus a stimulus sequence gives an
OBSERVATION TRACE, under a certificate mapping and a behaviour hypothesis that are passed in separately
and never merged (docs/b4_architecture.md sections 4.4, 5.1-5.3). Host-only; no board; no RTL.

    fab = Fabric(site_mapping(), load())
    trace = fab.observe(config, [init(), set_(clock=1, ce=0xff, sr=0, d=0x0f), set_(clock=0, ...)])

The state machine is PARAMETERISED by the hypothesis: every reading of a configuration bit goes through
`Hypothesis.decode`, every behavioural choice through `Hypothesis.flag(...)`; nothing about INIT, SRVAL,
CE, SR, latches or clock inversion is a literal here. A different hypothesis therefore gives a different
trace (the swap fixtures), and a model that stopped consulting its hypothesis is caught by those fixtures.

One observation (section 5.1): `observe` starts from NOTHING — every element's Q is None (never initialised),
the clock low, the inputs low — so no state can cross from one candidate to the next; the stimulus's own
`init` step is what gives Q a value (the initialisation event, modelled as the UNISIM GSR: Q := INIT on every
applicable element — an assumption, A8). A `set` step applies the inputs, settles the level-sensitive
effects at the old clock level, applies the clock change (an edge per element in ITS physical clock, which
is the slice clock XOR the decoded inversion), settles again at the new level, and reads out. Every step's
record carries the whole context (section 5.1 of the hypothesis file: prev_event, clock before / after, the
edge, the physical edge per element, ce / sr / d, Q before / after, applicability), so a readout can be
replayed from the trace alone. Q is None for an element that is not applicable in the configuration
(the x5FF elements under a latch) or that was never initialised.

Fixtures (`fixture`): `truth` (the certificate mapping), `permuted` (the same 21 targets dealt to the
addresses by a seeded permutation: a cartographer that still names the truth is hard-coded), `dropout`
(addresses with no effect), and the hypothesis swaps `ce_ungated`, `init_no_effect`, `zini_polarity`,
`latch_hold`, `sync_level`, `x5ff_storage`.
"""
from __future__ import annotations

import hashlib
import json
import random
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
import sys  # noqa: E402
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hyp  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402

ELEMENTS = bm.ELEMENTS
N = 8


class ModelRefusal(ValueError):
    pass


# ------------------------------------------------------------------ the stimulus
def init() -> dict:
    return {"kind": "init"}


def set_(clock: int, ce: int = 0, sr: int = 0, d: int = 0) -> dict:
    for name, v, hi in (("clock", clock, 1), ("ce", ce, 0xFF), ("sr", sr, 0xFF), ("d", d, 0xFF)):
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= hi:
            raise ModelRefusal(f"step {name} = {v!r} is not an integer in [0, {hi}]")
    return {"kind": "set", "clock": clock, "ce": ce, "sr": sr, "d": d}


def pulse(ce: int = 0, sr: int = 0, d: int = 0) -> list[dict]:
    """A rising then a falling slice-clock edge with the inputs held."""
    return [set_(1, ce, sr, d), set_(0, ce, sr, d)]


def bit(vec: int, i: int) -> int:
    return (vec >> i) & 1


# ------------------------------------------------------------------ the fabric
class Fabric:
    def __init__(self, mapping: bm.Mapping, hypothesis: hyp.Hypothesis, effect: dict[str, tuple[str | None, str]] | None = None,
                 dropout: frozenset[str] = frozenset()):
        self.mapping = mapping
        self.hypothesis = hypothesis
        # effect: address -> the (element, semantic) its bit drives. The truth is the mapping's own entries.
        self.effect = dict(effect) if effect is not None else {a: (e.element, e.semantic) for a, e in mapping.entries.items()}
        if set(self.effect) != set(mapping.addresses):
            raise ModelRefusal("the effect table does not cover exactly the mapping's addresses")
        self.dropout = frozenset(dropout)
        self.calls = 0

    # -- configuration
    def config_from_genome(self, genome: int) -> dict[str, int]:
        if not isinstance(genome, int) or genome < 0 or genome >> len(self.mapping.addresses):
            raise ModelRefusal("the genome is not a non-negative integer over the mapping's addresses")
        return {a: (genome >> i) & 1 for i, a in enumerate(self.mapping.addresses)}

    def _virtual(self, config: dict[str, int]) -> dict[str, int]:
        """The configuration as the decoder sees it: each address's bit routed to the target its effect names
        (identity for the truth); a dropped address moves nothing (its target stays 0 unless another drives it)."""
        v = {a: 0 for a in self.mapping.addresses}
        for a in self.mapping.addresses:
            b = config.get(a)
            if b not in (0, 1):
                raise ModelRefusal(f"the configuration has no 0/1 value for {a}")
            if a in self.dropout or not b:
                continue
            element, semantic = self.effect[a]
            v[self.mapping.address_of(element, semantic)] = 1
        return v

    def decode(self, config: dict[str, int]) -> dict[str, hyp.ElementConfig]:
        return self.hypothesis.decode(self._virtual(config), self.mapping)

    # -- the state machine, parameterised by the hypothesis
    def _phys(self, cfg: hyp.ElementConfig, clock: int) -> int:
        return clock ^ (1 if (cfg.clk_inverted and self.hypothesis.flag("clock_inversion_swaps_edge")) else 0)

    def _ce_ok(self, cfg: hyp.ElementConfig, ce: int, i: int) -> bool:
        if not cfg.ce_driven:
            return True                                            # CE tied high
        return bool(bit(ce, i)) if self.hypothesis.flag("ce_gates_capture") else True

    def _sr_active(self, cfg: hyp.ElementConfig, sr: int, i: int) -> bool:
        if not cfg.sr_driven and self.hypothesis.flag("sr_tied_low_when_not_driven"):
            return False
        return bool(bit(sr, i))

    def _settle(self, q: list, decoded: dict, clock: int, ce: int, sr: int, d: int) -> None:
        """Level-sensitive effects at the current clock level: asynchronous SR, latch transparency."""
        h = self.hypothesis
        for i, e in enumerate(ELEMENTS):
            cfg = decoded[e]
            if not cfg.applicable:
                continue
            if self._sr_active(cfg, sr, i):
                level_acts = cfg.latch or not cfg.sync or not h.flag("sync_sr_acts_on_edge_only")
                if level_acts and h.flag("async_sr_acts_on_level"):
                    q[i] = cfg.srval
                    continue
            if cfg.latch and h.flag("latch_transparent_when_gate_high_and_ge"):
                gate = self._phys(cfg, clock) if h.flag("latch_gate_is_physical_clock") else clock
                if gate and self._ce_ok(cfg, ce, i):
                    q[i] = bit(d, i)

    def _edges(self, q: list, decoded: dict, clock_before: int, clock_after: int, ce: int, sr: int, d: int) -> list:
        """The clock change: per element the edge in its physical clock; a flip-flop captures on the physical
        rising edge (the hypothesis's rule), SR first when synchronous and active."""
        h = self.hypothesis
        phys_edges = []
        for i, e in enumerate(ELEMENTS):
            cfg = decoded[e]
            if not cfg.applicable:
                phys_edges.append(None)
                continue
            pb, pa = self._phys(cfg, clock_before), self._phys(cfg, clock_after)
            edge = "rising" if (pb, pa) == (0, 1) else "falling" if (pb, pa) == (1, 0) else None
            phys_edges.append(edge)
            if cfg.latch or edge is None:
                continue
            capture_edge = "rising" if h.flag("ff_capture_on_physical_rising_edge") else "falling"
            if edge != capture_edge:
                continue
            if cfg.sync and self._sr_active(cfg, sr, i) and h.flag("sr_has_priority_over_capture"):
                q[i] = cfg.srval
            elif self._ce_ok(cfg, ce, i):
                q[i] = bit(d, i)
        return phys_edges

    # -- one observation
    def observe(self, config: dict[str, int], stimulus: list[dict]) -> dict:
        self.calls += 1
        decoded = self.decode(config)
        q: list = [None] * N                                        # never initialised: NOTHING crosses from an earlier observation
        clock, ce, sr, d = 0, 0, 0, 0
        prev_event = "none"
        steps = []
        for n, st in enumerate(stimulus):
            kind = st.get("kind")
            q_before = list(q)
            if kind == "init":
                if self.hypothesis.flag("init_event_sets_q_to_init"):
                    for i, e in enumerate(ELEMENTS):
                        q[i] = decoded[e].init if decoded[e].applicable else None
                rec = {"step": n, "kind": "init", "prev_event": prev_event, "clock_before": clock, "clock_after": clock, "edge": None,
                       "physical_edge": [None] * N, "ce": ce, "sr": sr, "d": d}
                prev_event = "init"
            elif kind == "set":
                ce, sr, d = st["ce"], st["sr"], st["d"]
                self._settle(q, decoded, clock, ce, sr, d)
                clock_before, clock = clock, st["clock"]
                edge = "rising" if (clock_before, clock) == (0, 1) else "falling" if (clock_before, clock) == (1, 0) else None
                phys = self._edges(q, decoded, clock_before, clock, ce, sr, d) if edge else [None] * N
                self._settle(q, decoded, clock, ce, sr, d)
                rec = {"step": n, "kind": "set", "prev_event": prev_event, "clock_before": clock_before, "clock_after": clock, "edge": edge,
                       "physical_edge": phys, "ce": ce, "sr": sr, "d": d}
                prev_event = "edge" if edge else "level"
            else:
                raise ModelRefusal(f"step {n}: kind {kind!r} is not init / set")
            rec["q_before"], rec["q_after"] = q_before, list(q)
            rec["applicable"] = [decoded[e].applicable for e in ELEMENTS]
            steps.append(rec)
        cfg_text = json.dumps({a: config[a] for a in self.mapping.addresses}, sort_keys=True)
        return {"schema": "b4_ff_observation_trace", "schema_version": "0.1.0",
                "hypothesis": {"path": self.hypothesis.path, "sha256": self.hypothesis.sha256, "version": self.hypothesis.version},
                "mapping": {"site": self.mapping.site, "certificate": self.mapping.certificate_rel, "certificate_sha256": self.mapping.certificate_sha256},
                "config": {a: config[a] for a in self.mapping.addresses}, "config_sha256": hashlib.sha256(cfg_text.encode()).hexdigest(),
                "decoded": {e: {"applicable": c.applicable, "primitive": c.primitive, "init": c.init, "srval": c.srval, "ce_driven": c.ce_driven,
                                "sr_driven": c.sr_driven, "sync": c.sync, "latch": c.latch, "clk_inverted": c.clk_inverted} for e, c in decoded.items()},
                "initial": {"clock": 0, "ce": 0, "sr": 0, "d": 0, "q": [None] * N},
                "elements": list(ELEMENTS), "steps": steps}


# ------------------------------------------------------------------ fixtures
SWAPS = {
    "ce_ungated": ("flag", "ce_gates_capture", False),
    "init_no_effect": ("flag", "init_event_sets_q_to_init", False),
    "latch_hold": ("flag", "latch_transparent_when_gate_high_and_ge", False),
    "sync_level": ("flag", "sync_sr_acts_on_edge_only", False),
    "x5ff_storage": ("flag", "x5ff_not_storage_when_latch", False),
    "zini_polarity": ("reading", "ff_init", "INIT = 1", "INIT = 0"),
}


def fixture(kind: str, mapping: bm.Mapping, hypothesis: hyp.Hypothesis, seed: int = 0, drop: int = 5) -> Fabric:
    truth = {a: (e.element, e.semantic) for a, e in mapping.entries.items()}
    rng = random.Random(seed)
    if kind == "truth":
        return Fabric(mapping, hypothesis, truth)
    if kind == "permuted":
        targets = [truth[a] for a in mapping.addresses]
        rng.shuffle(targets)
        return Fabric(mapping, hypothesis, {a: targets[i] for i, a in enumerate(mapping.addresses)})
    if kind == "dropout":
        return Fabric(mapping, hypothesis, truth, dropout=frozenset(rng.sample(list(mapping.addresses), drop)))
    if kind in SWAPS:
        spec = SWAPS[kind]
        h2 = hypothesis.with_flag(spec[1], spec[2], kind) if spec[0] == "flag" else hypothesis.with_reading(spec[1], spec[2], spec[3], kind)
        return Fabric(mapping, h2, truth)
    raise ModelRefusal(f"no fixture {kind!r}")


if __name__ == "__main__":
    fab = Fabric(bm.site_mapping(), hyp.load())
    base = {a: 0 for a in fab.mapping.addresses}
    for a, e in fab.mapping.entries.items():
        if e.semantic in ("ff_srval", "ce_mode", "sr_mode", "sr_kind"):
            base[a] = 1
    t = fab.observe(base, [init(), *pulse(ce=0xFF, d=0x00)])
    print(json.dumps([s["q_after"] for s in t["steps"]]))
