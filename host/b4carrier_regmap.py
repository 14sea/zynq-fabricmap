#!/usr/bin/env python3
"""The B4 carrier v2 register map — ONE table that the host sequence model and the MMIO-allowlist check read (an
executing-side PS program would be held to it too; none is delivered in this unit, so the allowlist check is of this
declared table against the RTL decode, not of a firmware's accesses) (rtl/b4/b4_axil.v is the decode; tests/test_b4carrier_regmap.py holds this table to it:
app reads ⊆ RTL reads, app writes ⊆ RTL writes, RTL − app = the key window, exactly as the instrument's rule).

Offsets are the AXI window offsets (16-bit); the instrument's eight stable words keep their B1 offsets."""
from __future__ import annotations

CTRL, STATUS, FAULT = 0x2000, 0x2004, 0x2008
Q_LIVE, IN_LIVE, SLOT_READ, SLOT_ADDR, WITNESS, TIMING = 0x2010, 0x2014, 0x2018, 0x201C, 0x2020, 0x2024
HEARTBEAT, NONCE_LO, NONCE_HI, VARIANT, STEP_IN = 0x2028, 0x202C, 0x2030, 0x2034, 0x2038
BASE_STATE, SLOT_IN_READ = 0x203C, 0x2040
PAYLOAD = tuple(0x2100 + 4 * i for i in range(20))
TAG = tuple(0x2150 + 4 * i for i in range(4))
KEY = tuple(0x2160 + 4 * i for i in range(4))
HW_COMMIT = tuple(0x2200 + 4 * i for i in range(8))
VARIANT_WORD = 0x42340001
MECHANISM = 2            # (b) GSR through STARTUPE2

CTRL_BITS = {"arm": 6, "arm_a5": 7, "key_commit": 8, "pre_sample": 9, "init_req": 10, "step": 11, "cleanup": 12, "close": 13,
             "restore_init": 14, "close_injection": 15}
# the CTRL acceptance rule of rtl/b4/b4_axil.v: exactly one operation (bit 7 only together with bit 6), no other bit,
# engine and gate idle — otherwise SLVERR and nothing changes
CTRL_OPS = ("arm", "key_commit", "pre_sample", "init_req", "step", "cleanup", "close", "restore_init", "close_injection")


def ctrl_word(op: str, a5: bool = False) -> int:
    if op not in CTRL_OPS:
        raise ValueError(f"not a CTRL operation: {op!r}")
    if a5 and op != "arm":
        raise ValueError("the A5 context flag accompanies arm only")
    return (1 << CTRL_BITS[op]) | ((1 << CTRL_BITS["arm_a5"]) if a5 else 0)


def ctrl_accepted(word: int) -> bool:
    """The register file's structural rule (the busy half is the engine's state, not the word's)."""
    ops = [b for name, b in CTRL_BITS.items() if name != "arm_a5" and (word >> b) & 1]
    known = (word & ~0xFFC0) == 0
    a5_ok = not ((word >> 7) & 1) or ((word >> 6) & 1)
    return len(ops) == 1 and known and a5_ok
STATUS_BITS = {"gate_busy": 0, "fault": 1, "configuration_valid_hw": 2, "engine_busy": 3, "step_done": 4, "pre_sampled": 5,
               "tag_ok": 6, "recovery_required": 7, "alive": 8, "init_done": 9, "init_pending": 10, "key_loaded": 11,
               "idle": 12, "cleanup_done": 13, "injection_open": 14, "cleanup_edge": 15, "restore_done": 26}
WITNESS_BITS = {"restore_pending": 24, "pre_context_a5": 25, "stall": 26}
WITNESS_FIELDS = {"gsr_count": (0, 8), "mechanism": (8, 8), "pulse": (16, 8)}
STATUS_FIELDS = {"slot_count": (16, 5), "step_index": (21, 5)}
FAULT_CODES = {0: "none", 5: "not_armed", 6: "not_realisable", 7: "sequence", 8: "slot_overflow", 12: "arm_nokey", 13: "arm_auth"}
# the closed set of the carrier's named refusals (docs/b4_observation_contract.md 3.4): never the model's DOMAIN
FAULT_NAMES = frozenset(v for k, v in FAULT_CODES.items() if k)

# what the executing-side program reads and writes (the allowlist the firmware will be held to)
APP_READABLE = frozenset({STATUS, FAULT, Q_LIVE, IN_LIVE, SLOT_READ, SLOT_ADDR, WITNESS, TIMING, HEARTBEAT, NONCE_LO, NONCE_HI, VARIANT, STEP_IN, BASE_STATE, SLOT_IN_READ} | set(HW_COMMIT))
APP_WRITABLE = frozenset({CTRL, SLOT_ADDR, STEP_IN} | set(PAYLOAD) | set(TAG))
KEY_WINDOW = frozenset(KEY)            # written by the signer principal only, never by the application


def step_word(d: int, ce: int, sr: int, clock: int) -> int:
    """The STEP_IN word: d bits 7:0, ce bits 15:8, sr bits 23:16, clock bit 24 — the step's ce / sr are the eight-bit
    vectors of the stimulus; the carrier applies a step only when each is uniform (one CE and one SR pin per slice)."""
    for name, v, hi in (("d", d, 0xFF), ("ce", ce, 0xFF), ("sr", sr, 0xFF), ("clock", clock, 1)):
        if not isinstance(v, int) or isinstance(v, bool) or not 0 <= v <= hi:
            raise ValueError(f"{name} out of range: {v!r}")
    return d | (ce << 8) | (sr << 16) | (clock << 24)


def realisable(ce: int, sr: int) -> bool:
    return ce in (0x00, 0xFF) and sr in (0x00, 0xFF)


def timing_word(assert_delay: int, release: int, sample_offset: int, settle: int, hold: int) -> int:
    return assert_delay | (release << 8) | (sample_offset << 16) | (settle << 24) | (hold << 28)


def decode_timing(word: int) -> dict:
    return {"assert_delay": word & 0xFF, "release": (word >> 8) & 0xFF, "sample_offset": (word >> 16) & 0xFF,
            "settle": (word >> 24) & 0xF, "hold": (word >> 28) & 0xF}


def decode_status(word: int) -> dict:
    out = {k: (word >> b) & 1 for k, b in STATUS_BITS.items()}
    for k, (b, w) in STATUS_FIELDS.items():
        out[k] = (word >> b) & ((1 << w) - 1)
    out["reserved_zero"] = (word >> 27) == 0
    return out


def decode_witness(word: int) -> dict:
    out = {k: (word >> b) & 1 for k, b in WITNESS_BITS.items()}
    for k, (b, w) in WITNESS_FIELDS.items():
        out[k] = (word >> b) & ((1 << w) - 1)
    return out


def decode_applied(word: int) -> dict:
    """SLOT_IN_READ: the inputs applied at a sample, in the stimulus's own vector form."""
    return {"d": word & 0xFF, "ce": (word >> 8) & 0xFF, "sr": (word >> 16) & 0xFF, "clock": (word >> 24) & 1}
