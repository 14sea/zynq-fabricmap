#!/usr/bin/env python3
"""B4Q — a HOST EMULATION of the B4 carrier v2 (rtl/b4: the register file b4_axil, the gate b4_gate, the engine b4_engine)
over the behaviour hypothesis as the fabric (b4/host/b4_ff_model.Fabric, read-only use), with a cycle model of the
engine's durations and the event stall. It is the MMIO backend the executing-side program (firmware/b4q) is driven
against on the host — "injectable MMIO / transport in a host bench" — and nothing more:

  * it is NOT the RTL and NOT silicon: a register-level model written from the RTL, held to the RTL by replaying the
    archived bench traces of the carrier unit (evidence/b4/unit_carrier_v2_2026_10_21/bench/*.jsonl) through it
    (host/b4q_emu_fidelity.py: every write applied at its recorded time, every read's data / resp compared, the
    heartbeat compared by its reset semantic); a difference is a finding against THIS file;
  * its fabric is the hypothesis: an element the model gives no value for (an x5FF under a latch; any element before
    the first event when the power-on state is unknown) reads as the bench's `x`, so a record built from it carries
    None where silicon would carry a physical 0 / 1 — the D1 rule seen from the host (contract 3.4);
  * the ARM tag is verified with the instrument's own signer library (SipHash-2-4-128 over the 20 payload words and the
    carrier's nonce, the key as provisioned through the write-once window) — the same arithmetic the RTL's verbatim
    p3_siphash.v computes; the nonce is the PL's xorshift.

The configuration (the 21-bit genome the slice is "configured" with) is SUPPLIED by the caller — on the bench by the
scenario, in the full host backend (host/b4q_backend.py) by the emulated PCAP frame store after each write — the
emulator never reads a frame itself. Every access is logged as the bench logs it ({t, op, addr, data, resp} and
marks), so host/b4carrier_records.py reads the emulation's trace exactly as it reads the RTL bench's."""
from __future__ import annotations

import sys
from pathlib import Path

R = Path(__file__).resolve().parent.parent
for p in (R / "host", R / "b4/host"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import b4carrier_regmap as rm  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402

TIMING = {"assert_delay": 8, "pulse": 2, "release": 16, "sample_offset": 4, "settle": 4, "hold": 4}
NONCE_SEED = 0x9E3779B97F4A7C15
MASK64 = (1 << 64) - 1
OKAY, SLVERR = 0, 2
# the cycle model (FCLK0 cycles). ENGINE_LATENCY: from the register file's acceptance of a CTRL write (the bench logs the
# write after its response) to the engine's first cycle of the operation; the durations are the RTL's state sequences
# (b4_engine.v): a step S_STEP_CTRL + S_STEP_DATA + SETTLE + HOLD + S_POST, a cleanup SETTLE + HOLD + S_WRITE + S_POST, an event
# ASSERT_DELAY quiet cycles + the PULSE + RELEASE + SAMPLE_OFFSET + S_POST, the pre-init cleanup SETTLE + HOLD before the launch.
# The cycle model, calibrated on the archived bench traces (host/b4q_emu_fidelity.py) and read from the RTL: a CTRL write the
# register file accepts is seen by the engine / the gate in the cycle after the bench logs it (ENGINE_LATENCY); a state
# machine leaves IDLE at the END of that cycle; a flip-flop result is visible one cycle after the cycle that computes it and a
# LUTRAM (b4_gsr_reg / b4_slot_ram) result two cycles after (its write enable is registered first, the RAM writes on the next
# edge). The reads of the bench sample the register file at their logged time.
ENGINE_LATENCY = 1
FF, RAM = 1, 2               # visibility delays after the computing cycle
GATE_TAG_AT = 49             # cycles after the gate sees the ARM strobe: tag_ok / busy-drop visible (p3_siphash over 20 words + nonce)


def xorshift(x: int) -> int:
    x &= MASK64
    x ^= (x << 13) & MASK64
    x ^= x >> 7
    x ^= (x << 17) & MASK64
    return x & MASK64


def _siphash128():
    import claimb_r1p_instrument as inst
    inst.bind(inst.DEFAULT_ROOT, require_git=False)
    from validators.siphash import siphash128
    return siphash128


class EmuRefusal(ValueError):
    pass


class Fabric8:
    """The eight elements under the hypothesis for one configuration: the model's own step semantics applied incrementally
    (b4_ff_model.Fabric._settle / _edges / decode — the same code observe() runs, so a whole stimulus through this object
    equals observe()'s q_after row by row; tests/test_b4q_emu.py holds it)."""

    def __init__(self, fabric: fm.Fabric, genome: int, q: list | None, gsr_init_effect: bool = True):
        self.fabric = fabric
        self.genome = genome
        self.config = fabric.config_from_genome(genome)
        try:
            self.decoded = fabric.decode(self.config)
            self.in_domain = self.decoded.in_domain
        except fm.ModelRefusal:
            self.decoded, self.in_domain = None, False
        self.q = list(q) if q is not None else [None] * 8
        self.gsr_init_effect = gsr_init_effect
        self.clock, self.ce, self.sr, self.d = 0, 0, 0, 0

    def reconfigure(self, genome: int):
        """The PCAP wrote a different configuration: the state of the storage elements is kept (a frame write is not an
        event); an element the new configuration makes no storage element of (an x5FF under a latch) has no model value
        from then on — the bench's slice model drives x there at once, the hypothesis has nothing to say about it."""
        f = Fabric8(self.fabric, genome, self.q, self.gsr_init_effect)
        f.clock, f.ce, f.sr, f.d = self.clock, self.ce, self.sr, self.d
        if f.in_domain:
            f.q = [c if f.decoded[e].applicable else None for c, e in zip(f.q, fm.ELEMENTS)]
        else:
            f.q = [None] * 8
        return f

    def init_event(self):
        if not self.in_domain:
            self.q = [None] * 8
        elif self.gsr_init_effect and self.fabric.hypothesis.flag("init_event_sets_q_to_init"):
            self.q = [self.decoded[e].init if self.decoded[e].applicable else None for e in fm.ELEMENTS]
        self.clock, self.ce, self.sr, self.d = 0, 0, 0, 0

    def apply_controls(self, ce: int, sr: int, d: int):
        """A set step's first half (S_STEP_CTRL / S_STEP_DATA): the level effects under the current clock."""
        self.ce, self.sr, self.d = ce, sr, d
        if self.in_domain:
            self.fabric._settle(self.q, self.decoded, self.clock, ce, sr, d)

    def apply_clock(self, clock: int):
        """The second half (after SETTLE): the clock moves; an edge captures; the level effects settle again."""
        cb, self.clock = self.clock, clock
        if not self.in_domain:
            return
        if (cb, clock) in ((0, 1), (1, 0)):
            self.fabric._edges(self.q, self.decoded, cb, clock, self.ce, self.sr, self.d)
        self.fabric._settle(self.q, self.decoded, clock, self.ce, self.sr, self.d)

    def q_word(self):
        """(data, x): the eight cells as a word, or None with the bench's x string when a cell has no value."""
        if any(c is None for c in self.q):
            return None, "0" * 24 + "".join("x" if c is None else str(c) for c in reversed(self.q))
        return sum(c << i for i, c in enumerate(self.q)), None

    def in_live(self) -> int:
        """IN_LIVE: d 7:0, ce bit 8, sr bit 9, the slice clock bit 10 (the controls are one pin each on the slice)."""
        return self.d | ((1 if self.ce else 0) << 8) | ((1 if self.sr else 0) << 9) | (self.clock << 10)


class CarrierEmu:
    def __init__(self, genome: int = 0, power_on: str = "x", timing: dict = TIMING, nonce_seed: int = NONCE_SEED, hypothesis=None, mapping=None,
                 gsr_init_effect: bool = True, log=None):
        self.mapping = mapping or bm.site_mapping()
        self.hypothesis = hypothesis or hy.load()
        self.model = fm.Fabric(self.mapping, self.hypothesis)
        self.timing = dict(timing)
        self.timing_word = rm.timing_word(timing["assert_delay"], timing["release"], timing["sample_offset"], timing["settle"], timing["hold"])
        self.nonce_seed = nonce_seed & MASK64
        self.log = log                                   # a list the trace events are appended to, or None
        self.siphash128 = None
        self.t = 0                                       # cycles
        self.fab = Fabric8(self.model, genome, None, gsr_init_effect)
        if power_on == "init":                           # the power-up state of a configured device (the configuration GSR), set on the fabric only —
            saved = self.fab.gsr_init_effect             # whatever the hypothesis swap says about the CARRIER's event (a5_persist), the loaded device starts at INIT
            self.fab.gsr_init_effect = True; self.fab.init_event(); self.fab.gsr_init_effect = saved
        elif power_on != "x":
            raise EmuRefusal("power_on is 'x' or 'init'")
        # persistent (LUTRAM) state
        self.key, self.key_loaded = None, False
        self.nonce = self.nonce_seed
        self.armed, self.fault, self.recovery = False, 0, False
        self.flags = {k: False for k in ("pre_sampled", "init_pending", "init_done", "cleanup_done", "cleanup_edge", "restore_pending", "restore_done",
                                         "injection_open", "pre_context_a5", "pre_init_cleanup")}
        self.gsr_count, self.base_state, self.base_state_x = 0, 0, None
        self.step_index, self.slot_count = 0, 0
        self.slots = {}                                  # slot -> (q_data|None, x_str|None, applied_word)
        self.reset_ffs()
        self.events = []                                 # the launch cycle of every GSR event
        self.pending = None                              # an event in flight: dict(kind, t_launch, t_done)
        self.busy_from, self.busy_until = 0, 0           # the engine's state != IDLE window (end exclusive)
        self.gate_busy_from, self.gate_busy_until = 0, 0
        self.gate_pending = None                         # the ARM verification in flight
        self._defer = []                                 # [(t_visible, fn)]: results written at the end of a state, visible later

    # ---------------------------------------------------------------- flip-flop state (reset by every event)
    def reset_ffs(self):
        self.payload = [0] * 20
        self.tag = [0] * 4
        self.hw_commit = [0] * 8
        self.tag_ok = False
        self.step_in = 0
        self.slot_addr = 0
        self.step_done = False
        self.heartbeat_base = self.t

    # ---------------------------------------------------------------- the clock
    def _at(self, t_vis: int, fn):
        self._defer.append((t_vis, fn))

    def _settle_time(self):
        """Apply every result that became visible by now, in time order (the gate's verification, deferred stores, the event)."""
        while True:
            due = [d for d in self._defer if d[0] <= self.t]
            if self.gate_pending is not None and self.t >= self.gate_busy_until:
                self._gate_finish()
                continue
            if self.pending is not None and self.t >= self.pending["t_done"]:
                self._event_finish()
                continue
            if not due:
                break
            d = min(due, key=lambda x: x[0]); self._defer.remove(d); d[1]()

    def _stall_until_event(self):
        if self.pending is not None and self.t < self.pending["t_done"]:
            self.t = self.pending["t_done"]              # the gate holds the access until the event's sample; the access is served after
            self._settle_time()

    def _engine_busy(self) -> bool:
        return self.busy_from <= self.t < self.busy_until

    def _gate_busy(self) -> bool:
        return self.gate_busy_from <= self.t < self.gate_busy_until

    def _log(self, ev: dict):
        if self.log is not None:
            self.log.append(ev)

    def mark(self, what: str):
        self._log({"t": self.t * 20, "mark": what})

    # ---------------------------------------------------------------- the register file: writes
    def write(self, addr: int, data: int, cost: int = 4) -> int:
        self.t += cost
        self._stall_until_event()
        self._settle_time()
        resp = self._write(addr & 0xFFFF, data & 0xFFFFFFFF)
        self._log({"t": self.t * 20, "op": "wr", "addr": addr & 0xFFFF, "data": data & 0xFFFFFFFF, "resp": resp})
        return resp

    def _write(self, a: int, d: int) -> int:
        if a == rm.CTRL:
            if not rm.ctrl_accepted(d) or self._engine_busy() or self._gate_busy() or self.pending is not None:
                return SLVERR
            self._ctrl(d)
            return OKAY
        if a in rm.KEY:
            if self.key_loaded:
                return SLVERR
            k = (a - rm.KEY[0]) >> 2
            words = list(self.key or [0] * 4); words[k] = d; self.key = words
            return OKAY
        if a in rm.PAYLOAD:
            self.payload[(a - rm.PAYLOAD[0]) >> 2] = d; return OKAY
        if a in rm.TAG:
            self.tag[(a - rm.TAG[0]) >> 2] = d; return OKAY
        if a == rm.STEP_IN:
            self.step_in = d & 0x1FFFFFF; return OKAY
        if a == rm.SLOT_ADDR:
            self.slot_addr = d & 0x1F; return OKAY
        return SLVERR

    def _fault(self, code: int, t_vis: int):
        def fn():
            self.fault, self.recovery = code, True
        self._at(t_vis, fn)

    def _set_flags(self, t_vis: int, **kv):
        def fn():
            for k, v in kv.items():
                self.flags[k] = v
        self._at(t_vis, fn)

    def _ctrl(self, d: int):
        b = rm.CTRL_BITS
        t0 = self.t + ENGINE_LATENCY                     # the cycle the engine / the gate sees the operation
        if (d >> b["arm"]) & 1:
            self._arm(bool((d >> b["arm_a5"]) & 1), t0); return
        if (d >> b["key_commit"]) & 1:
            if not self.key_loaded and self.key is not None:
                self._at(t0 + RAM, lambda: setattr(self, "key_loaded", True))
            return
        op = [name for name in rm.CTRL_OPS if name not in ("arm", "key_commit") and (d >> b[name]) & 1][0]
        F = self.flags
        tm = self.timing
        if not self.armed or self.recovery:
            if not self.recovery:
                self._fault(5, t0 + 1 + RAM)             # F_NOT_ARMED: the engine's strobe (FF), then the gate's latch (RAM)
            return                                       # under recovery: refused silently
        if op == "pre_sample":
            if F["pre_sampled"] or F["init_done"]:
                self._fault(7, t0 + 1 + RAM); return
            q, x = self.fab.q_word()
            il = self.fab.in_live()
            applied = (il & 0xFF) | ((0xFF if (il >> 8) & 1 else 0) << 8) | ((0xFF if (il >> 9) & 1 else 0) << 16) | (((il >> 10) & 1) << 24)
            a5 = F["injection_open"]
            def commit():
                self.slots[0] = (q, x, applied)
                F["pre_sampled"] = True
                if a5:
                    F["pre_context_a5"] = True
                self.slot_count, self.step_index = 1, 0
            self._at(t0 + RAM, commit)
            self.busy_from, self.busy_until = t0 + 1, t0 + 2          # S_POST
        elif op == "init_req":
            if not F["pre_sampled"] or F["init_pending"] or F["init_done"]:
                self._fault(7, t0 + 1 + RAM); return
            pre = 0
            if self.fab.in_live() != 0:                  # the held inputs of an A5 injection: the recorded pre-init cleanup inside step 0
                self._set_flags(t0 + RAM, pre_init_cleanup=True, init_pending=True)
                self.fab.apply_controls(0, 0, 0)
                self.fab.apply_clock(0)
                pre = tm["settle"] + tm["hold"]
            else:
                self._set_flags(t0 + RAM, init_pending=True)
            self._launch("init", t0 + pre)
        elif op == "step":
            if not F["init_done"] or F["cleanup_done"]:
                self._fault(7, t0 + 1 + RAM); return
            ce, sr = (self.step_in >> 8) & 0xFF, (self.step_in >> 16) & 0xFF
            if not rm.realisable(ce, sr):
                self._fault(6, t0 + 1 + RAM); return
            if self.slot_count >= 30:
                self._fault(8, t0 + 1 + RAM); return
            cmd = self.step_in                           # latched: the live STEP_IN may change while the step runs
            self.step_done = False
            self.fab.apply_controls(0xFF if ce else 0, 0xFF if sr else 0, cmd & 0xFF)
            self.fab.apply_clock((cmd >> 24) & 1)
            q, x = self.fab.q_word()
            applied = (cmd & 0xFF) | ((0xFF if ce else 0) << 8) | ((0xFF if sr else 0) << 16) | (((cmd >> 24) & 1) << 24)
            t_hold_end = t0 + 2 + tm["settle"] + tm["hold"]            # the last HOLD cycle (CTRL, DATA, SETTLE, HOLD after the IDLE cycle)
            slot, sc, si = 2 + self.step_index, self.slot_count + 1, self.step_index + 1
            def commit(slot=slot, entry=(q, x, applied), sc=sc, si=si):
                self.slots[slot] = entry; self.slot_count, self.step_index = sc, si
            self._at(t_hold_end + FF, lambda: setattr(self, "step_done", True))
            self._at(t_hold_end + RAM, commit)
            self.busy_from, self.busy_until = t0 + 1, t_hold_end + 2  # S_POST after HOLD, IDLE at t_hold_end + 2
        elif op == "cleanup":
            if not F["init_done"] or F["cleanup_done"]:
                self._fault(7, t0 + 1 + RAM); return
            self.fab.apply_controls(0, 0, 0)
            edge = bool(self.fab.clock)
            self.fab.apply_clock(0)
            q, x = self.fab.q_word()
            t_settle_end = t0 + tm["settle"]
            t_hold_end = t_settle_end + tm["hold"]
            if edge:
                self._set_flags(t_settle_end + RAM, cleanup_edge=True)
            slot, sc = 2 + self.step_index, self.slot_count + 1
            def commit(slot=slot, entry=(q, x, 0), sc=sc):
                self.slots[slot] = entry; self.slot_count = sc
            self._at(t_hold_end + RAM, commit)
            self._set_flags(t_hold_end + 1 + RAM, cleanup_done=True)     # S_WRITE, one cycle after the slot
            self.busy_from, self.busy_until = t0 + 1, t_hold_end + 3     # S_WRITE, S_POST, then IDLE
        elif op == "restore_init":
            if not F["cleanup_done"] or F["restore_pending"] or F["restore_done"]:
                self._fault(7, t0 + 1 + RAM); return
            self._set_flags(t0 + RAM, restore_pending=True)
            self._launch("restore", t0)
        elif op == "close":
            if not F["restore_done"]:
                self._fault(7, t0 + 1 + RAM); return
            def commit():
                for k in F:
                    F[k] = False
                self.step_index = self.slot_count = 0
            self._at(t0 + RAM, commit)
            self._at(t0 + 1 + FF, lambda: setattr(self, "tag_ok", False))
            self._at(t0 + 1 + RAM, lambda: setattr(self, "armed", False))  # close_strobe (FF) then the gate's armed latch (RAM)
            self.step_done = False
            self.busy_from, self.busy_until = t0 + 1, t0 + 2
        elif op == "close_injection":
            if not F["init_done"] or F["cleanup_done"]:
                self._fault(7, t0 + 1 + RAM); return
            def commit():
                for k in F:
                    F[k] = False
                F["injection_open"] = True
                self.step_index = self.slot_count = 0
            self._at(t0 + RAM, commit)
            self._at(t0 + 1 + FF, lambda: setattr(self, "tag_ok", False))
            self._at(t0 + 1 + RAM, lambda: setattr(self, "armed", False))
            self.step_done = False
            self.busy_from, self.busy_until = t0 + 1, t0 + 2

    def _launch(self, kind: str, t_start: int):
        """From the cycle the engine enters S_LAUNCH: ASSERT_DELAY quiet cycles, the fire (FF), the pulse-store load, the GSR for
        PULSE cycles, the wake, RELEASE + SAMPLE_OFFSET cycles, the sample (RAM: visible two cycles later), S_POST, IDLE."""
        tm = self.timing
        t_launch = t_start + 1 + tm["assert_delay"] + 2              # the first GSR cycle
        t_done = t_launch + tm["pulse"] + tm["release"] + tm["sample_offset"] + RAM
        self.pending = {"kind": kind, "t_launch": t_launch, "t_done": t_done}
        self.busy_from, self.busy_until = t_start + 1, t_done

    def _event_finish(self):
        ev = self.pending; self.pending = None
        self.events.append(ev["t_launch"])
        # the GSR: every flip-flop of the PL returns to its reset value; the fabric's elements to INIT (the model's event)
        self.fab.init_event()
        self.reset_ffs()
        self.heartbeat_base = ev["t_launch"] + self.timing["pulse"]
        self.gate_pending = None
        self._defer = [d for d in self._defer if d[0] <= ev["t_launch"]]   # a LUTRAM write already taken stays; nothing else survives the reset
        for d in list(self._defer):
            self._defer.remove(d); d[1]()
        q, x = self.fab.q_word()
        F = self.flags
        if ev["kind"] == "init":
            self.slots[1] = (q, x, 0)
            F["init_pending"], F["init_done"] = False, True
            self.slot_count, self.step_index = 2, 0
        else:
            self.base_state, self.base_state_x = (q if q is not None else 0), x
            F["restore_pending"], F["restore_done"] = False, True
        self.gsr_count = (self.gsr_count + 1) & 0xFF

    # ---------------------------------------------------------------- the gate
    def _arm(self, a5: bool, t0: int):
        if self.recovery:
            return                                       # refused silently: the fault is already latched
        if self.armed or (a5 != self.flags["injection_open"]):
            self._fault(7, t0 + RAM); return             # a sequence fault, the nonce untouched
        if not self.key_loaded:
            self._at(t0 + RAM, lambda: setattr(self, "nonce", xorshift(self.nonce)))
            self._fault(12, t0 + RAM); return
        self.gate_pending = {"payload": list(self.payload), "tag": list(self.tag)}
        self.gate_busy_from, self.gate_busy_until = t0 + 1, t0 + GATE_TAG_AT
        self.tag_ok = False

    def _gate_finish(self):
        g = self.gate_pending; self.gate_pending = None
        t_tag = self.gate_busy_until                     # tag_ok / busy drop visible now; the RAM writes one cycle later
        if self.siphash128 is None:
            self.siphash128 = _siphash128()
        key_int = (self.key[0] << 96) | (self.key[1] << 64) | (self.key[2] << 32) | self.key[3]
        key = key_int.to_bytes(16, "little")
        msg = b"".join(w.to_bytes(4, "big") for w in g["payload"]) + self.nonce.to_bytes(8, "little")
        tag = self.siphash128(key, msg)
        t0_, t1_ = int.from_bytes(tag[:8], "little"), int.from_bytes(tag[8:], "little")
        want = [t0_ >> 32, t0_ & 0xFFFFFFFF, t1_ >> 32, t1_ & 0xFFFFFFFF]
        self._at(t_tag + 1, lambda: setattr(self, "nonce", xorshift(self.nonce)))   # consumed by this attempt whatever the outcome
        if want == g["tag"]:
            self.tag_ok = True
            self.hw_commit = list(g["payload"][:8])
            self._at(t_tag + 1, lambda: setattr(self, "armed", True))
        else:
            self._fault(13, t_tag + 1)

    # ---------------------------------------------------------------- the register file: reads
    def read(self, addr: int, cost: int = 4):
        self.t += cost
        self._stall_until_event()
        self._settle_time()
        data, x, resp = self._read(addr & 0xFFFF)
        ev = {"t": self.t * 20, "op": "rd", "addr": addr & 0xFFFF, "data": data, "resp": resp}
        if x is not None:
            ev["x"] = x
        self._log(ev)
        return data, x, resp

    def status_word(self) -> int:
        F = self.flags
        busy = self._engine_busy() or self.pending is not None
        idle = (not busy) and not self.armed and not F["injection_open"] and self.fab.in_live() == 0
        bits = {"gate_busy": self._gate_busy(), "fault": self.fault != 0, "configuration_valid_hw": self.armed and not self.recovery, "engine_busy": busy,
                "step_done": self.step_done, "pre_sampled": F["pre_sampled"], "tag_ok": self.tag_ok, "recovery_required": self.recovery, "alive": True,
                "init_done": F["init_done"], "init_pending": F["init_pending"], "key_loaded": self.key_loaded, "idle": idle, "cleanup_done": F["cleanup_done"],
                "injection_open": F["injection_open"], "cleanup_edge": F["cleanup_edge"], "restore_done": F["restore_done"]}
        w = 0
        for name, b in rm.STATUS_BITS.items():
            w |= int(bool(bits[name])) << b
        w |= (self.slot_count & 0x1F) << 16
        w |= (self.step_index & 0x1F) << 21
        return w

    def witness_word(self) -> int:
        F = self.flags
        return (self.gsr_count & 0xFF) | (rm.MECHANISM << 8) | (self.timing["pulse"] << 16) | (int(F["restore_pending"]) << 24) | (int(F["pre_context_a5"]) << 25) \
            | (int(self.pending is not None) << 26) | (int(F["pre_init_cleanup"]) << 27)

    def _read(self, a: int):
        if a == rm.STATUS:
            return self.status_word(), None, OKAY
        if a == rm.FAULT:
            return self.fault & 0xF, None, OKAY
        if a == rm.Q_LIVE:
            q, x = self.fab.q_word()
            return q, x, OKAY
        if a == rm.IN_LIVE:
            return self.fab.in_live(), None, OKAY
        if a == rm.SLOT_READ:
            q, x, _ = self.slots.get(self.slot_addr, (0, None, 0))
            return q, x, OKAY
        if a == rm.SLOT_ADDR:
            return self.slot_addr, None, OKAY
        if a == rm.WITNESS:
            return self.witness_word(), None, OKAY
        if a == rm.TIMING:
            return self.timing_word, None, OKAY
        if a == rm.HEARTBEAT:
            return (self.t - self.heartbeat_base) & 0xFFFFFFFF, None, OKAY
        if a == rm.NONCE_LO:
            return self.nonce & 0xFFFFFFFF, None, OKAY
        if a == rm.NONCE_HI:
            return self.nonce >> 32, None, OKAY
        if a == rm.VARIANT:
            return rm.VARIANT_WORD, None, OKAY
        if a == rm.STEP_IN:
            return self.step_in, None, OKAY
        if a == rm.BASE_STATE:
            return (None if self.base_state_x else self.base_state), self.base_state_x, OKAY
        if a == rm.SLOT_IN_READ:
            _, _, applied = self.slots.get(self.slot_addr, (0, None, 0))
            return applied, None, OKAY
        if a in rm.HW_COMMIT:
            return self.hw_commit[(a - rm.HW_COMMIT[0]) >> 2], None, OKAY
        return 0, None, SLVERR

    # ---------------------------------------------------------------- the bench's hooks
    def set_genome(self, genome: int):
        """The configuration the slice holds now (the PCAP wrote it; on the bench the scenario set it)."""
        self.fab = self.fab.reconfigure(genome)

    def reset(self):
        """The bench's `reset`: the configuration reset of every flip-flop; the persistent (LUTRAM) state survives."""
        self.reset_ffs()
        self.pending = None
        self.gate_pending = None
        self._defer = []
        self.busy_until = self.t
