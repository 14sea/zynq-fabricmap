#!/usr/bin/env python3
"""B4-FF — the simulated fabric: a configuration of the 21 addresses plus a stimulus sequence gives an
OBSERVATION TRACE, under a certificate mapping and a behaviour hypothesis that are passed in separately and
never merged (docs/b4_architecture.md sections 4.4, 5.0-5.3). Host-only; no board; no RTL.

    fab = Fabric(site_mapping(), load())
    trace = fab.observe(config, [init(), set_(clock=1, ce=0xff, sr=0, d=0x0f), set_(clock=0, ...)])
    diag = fab.diagnose(config)            # HOST-ONLY: the decode, applicability, the physical edges — never in a trace

TWO OUTPUTS, KEPT APART (the owner's P1 on 2bad829, section 5.0 of the hypothesis file):
  * `observe` returns what the EXECUTING SIDE can see: the configuration it wrote, the stimulus it applied, and
    per step the readout — Q before / after per element — with the context it applied (clock before / after,
    the slice-clock edge, ce / sr / d, the previous event). Nothing derived from the decode is in it: no
    primitive, no INIT / SRVAL, no kind, no inversion, no applicability, no physical edge. A Q of None means the
    hypothesis gives no readout for that element in that configuration (the x5FF elements under a latch) or the
    element was never initialised — that is all a None says.
  * `diagnose` returns the host-only diagnostics for audits and simulation reports: the decode per element, the
    applicability, the unknown readings; `step_diagnostics(trace)` adds the physical edge per element per step.
    A session tool may never feed these to a decision (section 2).

VALIDATION AT THE ENTRY (the owner's P2): `observe` checks the configuration (exactly the mapping's addresses,
each 0 or 1, no bool) and every step as a dict (an init step carries nothing else; a set step's clock in {0, 1},
ce / sr / d in 0..255, ints not bools) — whatever built them; a step that bypassed `set_` is refused the same.
The init step's allowed context (the hypothesis's `initialisation_event.allowed_context`): the slice clock low
and SR de-asserted at that moment, else refused. A configuration outside the hypothesis's domain (a reading the
hypothesis leaves unknown — v0.2's clock_mode bit 0 under a latch; none in v0.3) is refused by name, never simulated
with a default.

The state machine is PARAMETERISED by the hypothesis: every reading goes through `Hypothesis.decode`, every
behavioural choice through `Hypothesis.flag(...)`; nothing about INIT, SRVAL, CE, SR, latches or clock inversion
is a literal here. `observe` starts from NOTHING (Q None, clock and inputs low): no state crosses candidates.
A `set` step applies the inputs, settles the level-sensitive effects at the old clock level, applies the clock
change (an edge per element in ITS physical clock — the slice clock through the decoded inversion, which under
a latch means the gate is the slice clock or, under v0.3's bit-0 reading, the slice clock inverted), settles
again, and reads out. The order matters and is the model's: the new inputs are settled at the OLD clock level
first, so a step that changes D while closing a latch's gate passes the new D before the gate closes; the init
step assigns INIT atomically and settles nothing (a model abstraction the hypothesis file names).

Fixtures (`fixture`): `truth`, `permuted`, `dropout`, and the hypothesis swaps `ce_ungated`, `init_no_effect`,
`zini_polarity`, `latch_hold`, `sync_level`, `x5ff_storage`, `latch_gate_inverted` — each a marked fixture
hypothesis (its trace header says `fixture: true`).

A configuration outside the hypothesis's domain is refused with `DomainRefusal`: the executing side receives the
fixed code DOMAIN and no reason (the reason is `diagnose`'s, host-only); such a refusal is never a specimen, a
redraw condition or a map-update signal — a rule 2b-2's cartographer and engine inherit.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
for p in (REPO_ROOT / "b4/host",):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4_ff_hypothesis as hyp  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402

ELEMENTS = bm.ELEMENTS
N = 8
STEP_KEYS = {"init": {"kind"}, "set": {"kind", "clock", "ce", "sr", "d"}}
VISIBLE_STEP_KEYS = ("step", "kind", "prev_event", "clock_before", "clock_after", "edge", "ce", "sr", "d", "q_before", "q_after")


class ModelRefusal(ValueError):
    pass


class DomainRefusal(ModelRefusal):
    """What the executing side receives for a configuration outside the hypothesis's domain: the fixed code and
    nothing else — no reading, no semantic, no reason (the owner's P1 on b91162c). The reason is `diagnose`'s
    (host-only). A domain refusal is never a specimen, a redraw condition or a map-update signal."""
    CODE = "DOMAIN"
    MESSAGE = "REFUSED: configuration outside the model's domain (DOMAIN)"

    def __init__(self):
        super().__init__(self.MESSAGE)


# ------------------------------------------------------------------ the stimulus
def _int_in(name: str, v, hi: int) -> int:
    if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= hi:
        raise ModelRefusal(f"{name} = {v!r} is not an integer in [0, {hi}]")
    return v


def validate_step(st, n: int | None = None) -> dict:
    """The one validator, used by the builders AND by `observe` on whatever it is handed."""
    where = f"step {n}: " if n is not None else ""
    if not isinstance(st, dict):
        raise ModelRefusal(f"{where}a step must be a dict")
    kind = st.get("kind")
    if kind not in STEP_KEYS:
        raise ModelRefusal(f"{where}kind {kind!r} is not init / set")
    if set(st) != STEP_KEYS[kind]:
        raise ModelRefusal(f"{where}{'an' if kind == 'init' else 'a'} {kind} step carries exactly {sorted(STEP_KEYS[kind])}, not {sorted(st)}")
    if kind == "set":
        for name, hi in (("clock", 1), ("ce", 0xFF), ("sr", 0xFF), ("d", 0xFF)):
            _int_in(where + name, st[name], hi)
    return dict(st)


def init() -> dict:
    return {"kind": "init"}


def set_(clock: int, ce: int = 0, sr: int = 0, d: int = 0) -> dict:
    return validate_step({"kind": "set", "clock": clock, "ce": ce, "sr": sr, "d": d})


def pulse(ce: int = 0, sr: int = 0, d: int = 0) -> list[dict]:
    """A rising then a falling slice-clock edge with the inputs held."""
    return [set_(1, ce, sr, d), set_(0, ce, sr, d)]


def bit(vec: int, i: int) -> int:
    return (vec >> i) & 1


# ------------------------------------------------------------------ the fabric
SOURCE_KINDS = ("truth", "permuted", "dropout", "custom")


class Fabric:
    def __init__(self, mapping: bm.Mapping, hypothesis: hyp.Hypothesis, effect: dict[str, tuple[str | None, str]] | None = None,
                 dropout: frozenset[str] = frozenset(), kind: str | None = None, seed: int | None = None):
        self.mapping = mapping
        self.hypothesis = hypothesis
        self.effect = dict(effect) if effect is not None else {a: (e.element, e.semantic) for a, e in mapping.entries.items()}
        if set(self.effect) != set(mapping.addresses):
            raise ModelRefusal("the effect table does not cover exactly the mapping's addresses")
        self.dropout = frozenset(dropout)
        self.calls = 0
        truth = {a: (e.element, e.semantic) for a, e in mapping.entries.items()}
        if kind is None:
            kind = "truth" if (self.effect == truth and not self.dropout) else "custom"
        if kind not in SOURCE_KINDS:
            raise ModelRefusal(f"source kind {kind!r}")
        if not (seed is None or (isinstance(seed, int) and not isinstance(seed, bool))):
            raise ModelRefusal("the source seed must be an int or None")
        # the SOURCE descriptor: the fabric's identity as DIGESTS — the effect table (address -> target) and the dropout set are
        # never in it; a trace header carries it so that a truth, a permuted and a dropout fabric are told apart (the owner's P1 on
        # 8d2757a) without the executing side learning what the effect is
        effect_text = json.dumps([[a, list(self.effect[a])] for a in mapping.addresses], sort_keys=True, separators=(",", ":"))
        drop_text = json.dumps(sorted(self.dropout), separators=(",", ":"))
        self.source = {"kind": kind, "effect_sha256": hashlib.sha256(effect_text.encode()).hexdigest(),
                       "dropout_sha256": hashlib.sha256(drop_text.encode()).hexdigest(), "dropout_count": len(self.dropout), "seed": seed}

    # -- configuration
    def config_from_genome(self, genome: int) -> dict[str, int]:
        if not isinstance(genome, int) or isinstance(genome, bool) or genome < 0 or genome >> len(self.mapping.addresses):
            raise ModelRefusal("the genome is not a non-negative integer over the mapping's addresses")
        return {a: (genome >> i) & 1 for i, a in enumerate(self.mapping.addresses)}

    def validate_config(self, config) -> dict[str, int]:
        if not isinstance(config, dict) or set(config) != set(self.mapping.addresses):
            raise ModelRefusal("the configuration must map exactly the mapping's addresses")
        for a, b in config.items():
            if not isinstance(b, int) or isinstance(b, bool) or b not in (0, 1):
                raise ModelRefusal(f"the configuration's value for {a} is {b!r}, not 0 / 1")
        return {a: int(config[a]) for a in self.mapping.addresses}

    def _virtual(self, config: dict[str, int]) -> dict[str, int]:
        v = {a: 0 for a in self.mapping.addresses}
        for a in self.mapping.addresses:
            if a in self.dropout or not config[a]:
                continue
            element, semantic = self.effect[a]
            v[self.mapping.address_of(element, semantic)] = 1
        return v

    def decode(self, config: dict[str, int]) -> hyp.Decode:
        return self.hypothesis.decode(self._virtual(self.validate_config(config)), self.mapping)

    def diagnose(self, config: dict[str, int]) -> dict:
        """HOST-ONLY. The decode and its derived facts; never part of a trace, never an input to a session decision."""
        d = self.decode(config)
        return {"visibility": "host_only", "in_domain": d.in_domain, "unknown_readings": [list(u) for u in d.unknown_readings],
                "decoded": {e: {"applicable": c.applicable, "primitive": c.primitive, "init": c.init, "srval": c.srval, "ce_driven": c.ce_driven,
                                "sr_driven": c.sr_driven, "sync": c.sync, "latch": c.latch, "clk_inverted": c.clk_inverted} for e, c in d.elements.items()},
                "applicable": [d[e].applicable for e in ELEMENTS]}

    # -- the state machine, parameterised by the hypothesis
    def _phys(self, cfg: hyp.ElementConfig, clock: int) -> int:
        return clock ^ (1 if (cfg.clk_inverted and self.hypothesis.flag("clock_inversion_swaps_edge")) else 0)

    def _ce_ok(self, cfg: hyp.ElementConfig, ce: int, i: int) -> bool:
        if not cfg.ce_driven:
            return True
        return bool(bit(ce, i)) if self.hypothesis.flag("ce_gates_capture") else True

    def _sr_active(self, cfg: hyp.ElementConfig, sr: int, i: int) -> bool:
        if not cfg.sr_driven and self.hypothesis.flag("sr_tied_low_when_not_driven"):
            return False
        return bool(bit(sr, i))

    def _settle(self, q: list, decoded: hyp.Decode, clock: int, ce: int, sr: int, d: int) -> None:
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

    def _physical_edges(self, decoded: hyp.Decode, clock_before: int, clock_after: int) -> list:
        out = []
        for e in ELEMENTS:
            cfg = decoded[e]
            if not cfg.applicable:
                out.append(None); continue
            pb, pa = self._phys(cfg, clock_before), self._phys(cfg, clock_after)
            out.append("rising" if (pb, pa) == (0, 1) else "falling" if (pb, pa) == (1, 0) else None)
        return out

    def _edges(self, q: list, decoded: hyp.Decode, clock_before: int, clock_after: int, ce: int, sr: int, d: int) -> None:
        h = self.hypothesis
        capture_edge = "rising" if h.flag("ff_capture_on_physical_rising_edge") else "falling"
        for i, (e, edge) in enumerate(zip(ELEMENTS, self._physical_edges(decoded, clock_before, clock_after))):
            cfg = decoded[e]
            if not cfg.applicable or cfg.latch or edge != capture_edge:
                continue
            if cfg.sync and self._sr_active(cfg, sr, i) and h.flag("sr_has_priority_over_capture"):
                q[i] = cfg.srval
            elif self._ce_ok(cfg, ce, i):
                q[i] = bit(d, i)

    # -- one observation: the executing side's view
    def observe(self, config, stimulus) -> dict:
        self.calls += 1
        config = self.validate_config(config)
        if not isinstance(stimulus, (list, tuple)):
            raise ModelRefusal("the stimulus must be a list of steps")
        steps_in = [validate_step(st, n) for n, st in enumerate(stimulus)]
        decoded = self.decode(config)
        if not decoded.in_domain:
            raise DomainRefusal()                                   # the fixed code; the reason only through diagnose()
        q: list = [None] * N
        clock, ce, sr, d = 0, 0, 0, 0
        prev_event = "none"
        steps = []
        for n, st in enumerate(steps_in):
            q_before = list(q)
            if st["kind"] == "init":
                if clock != 0 or sr != 0:
                    raise ModelRefusal(f"step {n}: an init step is allowed only with the slice clock low and SR de-asserted (clock {clock}, sr {sr:#04x})")
                if self.hypothesis.flag("init_event_sets_q_to_init"):
                    for i, e in enumerate(ELEMENTS):
                        q[i] = decoded[e].init if decoded[e].applicable else None
                rec = {"step": n, "kind": "init", "prev_event": prev_event, "clock_before": clock, "clock_after": clock, "edge": None, "ce": ce, "sr": sr, "d": d}
                prev_event = "init"
            else:
                ce, sr, d = st["ce"], st["sr"], st["d"]
                self._settle(q, decoded, clock, ce, sr, d)
                clock_before, clock = clock, st["clock"]
                edge = "rising" if (clock_before, clock) == (0, 1) else "falling" if (clock_before, clock) == (1, 0) else None
                if edge:
                    self._edges(q, decoded, clock_before, clock, ce, sr, d)
                self._settle(q, decoded, clock, ce, sr, d)
                rec = {"step": n, "kind": "set", "prev_event": prev_event, "clock_before": clock_before, "clock_after": clock, "edge": edge, "ce": ce, "sr": sr, "d": d}
                prev_event = "edge" if edge else "level"
            rec["q_before"], rec["q_after"] = q_before, list(q)
            steps.append(rec)
        cfg_text = json.dumps(config, sort_keys=True)
        return {"schema": "b4_ff_observation_trace", "schema_version": "0.2.0", "visibility": "executing_side",
                "q_null_means": "no readout is given by the hypothesis for that element in that configuration, or the element was never initialised",
                "hypothesis": {"path": self.hypothesis.path, "sha256": self.hypothesis.sha256, "version": self.hypothesis.version, "fixture": self.hypothesis.fixture},
                "mapping": {"site": self.mapping.site, "certificate": self.mapping.certificate_rel, "certificate_sha256": self.mapping.certificate_sha256},
                "fabric": dict(self.source),
                "config": config, "config_sha256": hashlib.sha256(cfg_text.encode()).hexdigest(),
                "stimulus": steps_in, "initial": {"clock": 0, "ce": 0, "sr": 0, "d": 0, "q": [None] * N},
                "elements": list(ELEMENTS), "steps": steps}

    def step_diagnostics(self, trace: dict) -> list[dict]:
        """HOST-ONLY: per step, the edge in each element's physical clock and the applicability, from the decode."""
        decoded = self.decode(trace["config"])
        out = []
        for s in trace["steps"]:
            out.append({"step": s["step"], "physical_edge": self._physical_edges(decoded, s["clock_before"], s["clock_after"]) if s["edge"] else [None] * N,
                        "applicable": [decoded[e].applicable for e in ELEMENTS]})
        return out


# ------------------------------------------------------------------ fixtures
SWAPS = {
    "ce_ungated": ("flag", "ce_gates_capture", False),
    "init_no_effect": ("flag", "init_event_sets_q_to_init", False),
    "latch_hold": ("flag", "latch_transparent_when_gate_high_and_ge", False),
    "sync_level": ("flag", "sync_sr_acts_on_edge_only", False),
    "x5ff_storage": ("flag", "x5ff_not_storage_when_latch", False),
    "zini_polarity": ("reading", "ff_init", "init_1", "init_0", None),
    "latch_gate_inverted": ("reading", "clock_mode", "inverted", "not_inverted", "latch"),   # the reading the probe says must NOT be applied
}


def fixture(kind: str, mapping: bm.Mapping, hypothesis: hyp.Hypothesis, seed: int = 0, drop: int = 5) -> Fabric:
    truth = {a: (e.element, e.semantic) for a, e in mapping.entries.items()}
    rng = random.Random(seed)
    if kind == "truth":
        return Fabric(mapping, hypothesis, truth, kind="truth")
    if kind == "permuted":
        targets = [truth[a] for a in mapping.addresses]
        rng.shuffle(targets)
        return Fabric(mapping, hypothesis, {a: targets[i] for i, a in enumerate(mapping.addresses)}, kind="permuted", seed=seed)
    if kind == "dropout":
        return Fabric(mapping, hypothesis, truth, dropout=frozenset(rng.sample(list(mapping.addresses), drop)), kind="dropout", seed=seed)
    if kind in SWAPS:
        spec = SWAPS[kind]
        if spec[0] == "flag":
            h2 = hypothesis.with_flag(spec[1], spec[2], kind)
        else:
            h2 = hypothesis.with_reading(spec[1], spec[2], spec[3], kind, context=spec[4])
        return Fabric(mapping, h2, truth, kind="truth")
    raise ModelRefusal(f"no fixture {kind!r}")


if __name__ == "__main__":
    fab = Fabric(bm.site_mapping(), hyp.load())
    base = {a: 0 for a in fab.mapping.addresses}
    for a, e in fab.mapping.entries.items():
        if e.semantic in ("ff_srval", "ce_mode", "sr_mode", "sr_kind"):
            base[a] = 1
    t = fab.observe(base, [init(), *pulse(ce=0xFF, d=0x00)])
    print(json.dumps([s["q_after"] for s in t["steps"]]), sorted(t["steps"][0]))
