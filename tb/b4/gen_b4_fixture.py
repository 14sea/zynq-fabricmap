#!/usr/bin/env python3
"""The B4 carrier v2 bench fixture — tb/b4/b4_fixture.vh — from two sources the bench must agree with:

  1. the ARM payloads, signed by the SAME signer library the host uses (the instrument's validators.signer,
     bound read-only, exactly as tb/b1/gen_b1_fixture.py does): zero table words under the contract; VALID1..VALID4
     on the nonce chain n0..n3, UNSIGNED, WRONG_COMMIT, and a replay is VALID1 again;
  2. the behaviour hypothesis, through the FORMAL model b4/host/b4_ff_model.py (hypothesis v0.3, the certificate
     mapping): for an explicit fixture schedule of genomes and stimuli — NOT task-v0.2's generator, NOT a production
     seed — the expected q_after of every step, with the model's null cells marked so the bench compares only the
     modelled cells (docs/b4_observation_contract.md 3.4). The stimuli use UNIFORM ce / sr vectors (one CE and one
     SR pin per slice: rtl/b4/b4_target_slice.v); the carrier applies nothing else.

The fixture is a mechanics fixture: explicit genomes, explicit vectors, the model called directly. Its digest and
the hypothesis digest are written into the header so the bench record can name what it reproduced."""
import hashlib
import os
import sys
import tempfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(R / "host"))
sys.path.insert(0, str(R / "b4/host"))
import claimb_r1p_instrument as inst  # noqa: E402
import b4_ff_hypothesis as hy  # noqa: E402
import b4_ff_mapping as bm  # noqa: E402
import b4_ff_model as fm  # noqa: E402

inst.bind(inst.DEFAULT_ROOT, require_git=False)
from validators import nonce as nn, signer as sg  # noqa: E402

KEY = bytes(range(16))
KEY_B = bytes(range(16, 32))
SEED = 0x9E3779B97F4A7C15
ZERO = [0] * 6
n = nn.sequence(SEED, 9)
tmp = Path(tempfile.mkdtemp()); kp = tmp / "K"; kp.write_bytes(KEY); os.chmod(kp, 0o400)
holder = sg.KeyHolder(kp)


def commit(label): return hashlib.sha256(label.encode()).digest()
def verdict(c): return {"writable": True, "candidate_sha256": c.hex()}


commits = [commit(f"b4-cand{i}") for i in range(1, 10)]
cases = {}
for i in range(8):
    cases[f"VALID{i + 1}"] = sg.sign_arm(holder, verdict(commits[i]), commits[i], ZERO, n[i].to_bytes(8, "little")).words()
p = sg.sign_arm(holder, verdict(commits[0]), commits[0], ZERO, n[0].to_bytes(8, "little"))
cases["UNSIGNED"] = sg.ArmPayload(p.candidate_commit, p.expected_tables, p.nonce, bytes(16)).words()
q = sg.sign_arm(holder, verdict(commits[2]), commits[2], ZERO, n[0].to_bytes(8, "little"))
cases["WRONG_COMMIT"] = sg.ArmPayload(commits[8], q.expected_tables, q.nonce, q.tag).words()

# ------------------------------------------------------------------ the model's expected traces
mapping = bm.site_mapping()
hypothesis = hy.load()
fabric = fm.Fabric(mapping, hypothesis)                       # the formal source (kind truth)
ADDR = list(mapping.addresses)


def config_of(genome: int) -> dict:
    return {a: (genome >> i) & 1 for i, a in enumerate(ADDR)}


def u8(v: int) -> int:            # a uniform ce / sr vector: all eight elements the same
    return 0xFF if v else 0x00


# the explicit schedule: (name, genome, steps) — steps as (clock, ce, sr, d) after the init step
SCHEDULE = [
    # base: FF, async, INIT 1, SRVAL 1, CE tied, SR tied; d captured on rising edges
    ("BASE", 0x000000, [(1, 0, 0, 0x5A), (0, 0, 0, 0xA5), (1, 0, 0, 0xA5), (0, 0, 0, 0x00), (1, 0, 0, 0x0F), (1, 0, 0, 0xF0), (0, 0, 0, 0xF0)]),
    # CE driven (bit 4) and SR driven (bit 3), async: SR level sets to SRVAL 1; CE gates capture
    ("CE_SR_ASYNC", (1 << 4) | (1 << 3), [(1, 1, 0, 0x33), (0, 1, 0, 0x33), (1, 0, 0, 0xCC), (0, 0, 1, 0x00), (1, 1, 0, 0x0F), (0, 1, 1, 0x0F), (1, 1, 0, 0x55)]),
    # synchronous SR (bit 0) with SR driven, SRVAL 0 on AFF and B5FF (bits 8, 2), INIT 0 on CFF (bit 17)
    ("SYNC_SRVAL0", (1 << 0) | (1 << 3) | (1 << 4) | (1 << 8) | (1 << 2) | (1 << 17), [(1, 1, 0, 0xFF), (0, 1, 1, 0xFF), (1, 1, 1, 0x00), (0, 1, 0, 0x00), (1, 1, 0, 0x81), (0, 0, 0, 0x81), (1, 0, 0, 0x7E)]),
    # clock inverted (bit 6): capture on the falling edge of the slice clock
    ("CLKINV", (1 << 6) | (1 << 4), [(1, 1, 0, 0x3C), (0, 1, 0, 0x3C), (1, 1, 0, 0xC3), (0, 1, 0, 0xC3), (1, 1, 0, 0x00), (0, 1, 0, 0x00), (0, 1, 0, 0xFF)]),
    # latch (bit 10), CLKINV = 1 => gate not inverted (v0.3): transparent while the slice clock is high; x5FF not storage
    ("LATCH", (1 << 10) | (1 << 6) | (1 << 4), [(1, 1, 0, 0x55), (1, 1, 0, 0xAA), (0, 1, 0, 0x00), (0, 1, 0, 0xFF), (1, 1, 0, 0x0F), (0, 0, 0, 0xF0), (0, 1, 0, 0xF0)]),
    # the all-ones genome: every bit set (latch, inverted gate reading = inverted, sync, SR / CE driven, INIT 0, SRVAL 0)
    ("ALL_ONES", (1 << 21) - 1, [(1, 1, 0, 0xA5), (0, 1, 0, 0x5A), (1, 1, 1, 0x5A), (0, 1, 1, 0x00), (1, 0, 0, 0xFF), (0, 1, 0, 0xFF), (0, 1, 0, 0x00)]),
]

traces = []
for name, genome, steps in SCHEDULE:
    stim = [fm.init()] + [fm.set_(c, u8(ce), u8(sr), d) for (c, ce, sr, d) in steps]
    t = fabric.observe(config_of(genome), stim)
    rows = []
    for s in t["steps"]:
        val = 0; mask = 0
        for i, qv in enumerate(s["q_after"]):
            if qv is not None:
                mask |= 1 << i; val |= (int(qv) << i)
        rows.append((val, mask))
    traces.append((name, genome, steps, rows, t["config_sha256"]))

sched_text = repr([(nm, g, st) for nm, g, st in SCHEDULE]).encode()
out = ["// generated by tb/b4/gen_b4_fixture.py — do not edit",
       f"// hypothesis {hy.HYPOTHESIS_REL} sha256 {hy.HYPOTHESIS_SHA256}",
       f"// certificate {mapping.certificate_rel} sha256 {mapping.certificate_sha256}",
       f"// schedule sha256 {hashlib.sha256(sched_text).hexdigest()} (an explicit mechanics fixture; no production seed)",
       f"localparam [127:0] KEY_A = 128'h{int.from_bytes(KEY, 'little'):032x};",
       f"localparam [127:0] KEY_B = 128'h{int.from_bytes(KEY_B, 'little'):032x};",
       f"localparam [63:0] SEED = 64'h{SEED:016x};"]
out += [f"localparam [63:0] N{i} = 64'h{v:016x};" for i, v in enumerate(n)]
for name, w in cases.items():
    assert len(w) == 24
    out.append(f"localparam [767:0] {name} = 768'h" + "".join(f"{x:08x}" for x in w) + ";")
out += [f"localparam [255:0] C{i + 1} = 256'h{c.hex()};" for i, c in enumerate(commits)]
out.append(f"localparam integer FIX_N = {len(traces)};")
out.append(f"localparam integer FIX_STEPS = {len(SCHEDULE[0][2])};")
for k, (name, genome, steps, rows, csha) in enumerate(traces):
    assert len(steps) == len(SCHEDULE[0][2]) and len(rows) == len(steps) + 1
    out.append(f"// fixture {k}: {name}  genome {genome:#08x}  model config_sha256 {csha}")
    out.append(f"localparam [20:0] FIX{k}_GENOME = 21'h{genome:06x};")
    for j, (c, ce, sr, d) in enumerate(steps):
        word = d | (u8(ce) << 8) | (u8(sr) << 16) | (c << 24)
        out.append(f"localparam [24:0] FIX{k}_IN{j} = 25'h{word:07x};")
    for j, (val, mask) in enumerate(rows):
        out.append(f"localparam [7:0] FIX{k}_Q{j} = 8'h{val:02x}; localparam [7:0] FIX{k}_M{j} = 8'h{mask:02x};")
(R / "tb/b4/b4_fixture.vh").write_text("\n".join(out) + "\n")
print("fixture:", list(cases), "traces", [t[0] for t in traces], "nonces", [hex(x) for x in n])
