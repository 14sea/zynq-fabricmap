# B1 carrier qualification — what is host-verified, what needs the board, and in what order (v0.1, 2026-09-05)

> **Standing: host-only. No ruling; no board contact.** The B1 carrier (`builds/b1/b1.bit`
> `d85daef4…`) is a new bitstream and inherits none of the instrument's board-level
> guarantees (L2 non-perturbation, L3–L5 on the P3 carrier, the L6 soak). This document
> lists what is already verified on the host and what the **qualification session** — its
> own ruling pair, before the mapping session — must establish.

## 1. What changed and what did not

| | instrument (P3, `956379fa…`) | B1 carrier (`d85daef4…`) |
|---|---|---|
| gate | `p3_arm_gate` — readout must equal the signed tables | `b1_arm_gate`, `SEMANTIC_GATE = 0` — the same authorisation (key, nonce, tag), the same sweep, the readout raw, `tables_match` an observation |
| register file | `p3_axil` | `b1_axil` + read-only `VARIANT` (`0x2034` = `0x42310001`); the eight stable words keep their offsets; the write-once key window unchanged |
| everything else | AXI3 shim, scorer, XDC, pblock, isolation checks, constants | **identical files** (hash-equal to the instrument's imports; `tests/test_b1_carrier.py`) |
| part / top / seed | `xc7z010clg400-1` / `p3_top` / `0x9E3779B97F4A7C15` | the same part / `b1_top` / the same seed |

## 2. Host-verified (done)

| item | result | where |
|---|---|---|
| RTL diff is the parameter and the register only | siphash verbatim; gate = the instrument's + `SEMANTIC_GATE`; axil + `VARIANT` | `tests/test_b1_carrier.py::CarrierSources` |
| simulation, the instrument's scenarios that still apply + the contract's own | `tb_p3_siphash` (verbatim) PASS; `tb_b1_core` PASS — zero-table payload ARMs and the readout is the bench's fabric; a changed fabric changes the readout, no fault; attested tables still ARM (the host refuses them); unsigned / replay / wrong commit / wrong key / no key refuse; reset clears the key | `sim/b1/run.sh`; `tests/test_b1_carrier.py::Benches` |
| Vivado build (2025.2) | routed; **WNS +7.993 ns**; **ICAPE2 0**; isolation: target cells 6, flush cells 0 | `builds/b1/b1_build.json`, `isolation.txt`, `timing.rpt` |
| carrier manifest (the instrument's own generator) | validates under the instrument's schema; 12 target frames blank; positive control `0x00401420` globally unique; frame count 5144 | `builds/b1/carrier_manifest.json` |
| MMIO allowlist vs the RTL decode | app reads ⊆ RTL reads (VARIANT included), app writes ⊆ RTL writes, RTL − app = the key window only | `tests/test_b1_carrier.py::MmioAllowlist` |
| the host validator refuses an attested reply | `host/b1_records.py` rule (iii-B1) | `tests/test_b1_records.py` |
| the signer never computes semantics | the oracle's entry points are disarmed in-process in `host/b1_sign_arm.py` (a call is a refusal); the answer carries zero tables only; no host-attested `sign` op exists | `tests/test_b1_signer.py` |

Not host-verifiable, by nature: that the silicon behaves as the routed netlist says (the
qualification session), and that the PS→PL path is undisturbed by the new register (the
same session's read-only checks).

## 3. The qualification session (board; its own ruling pair; before any mapping)

Ruling text: `whole-of-run B1 carrier qualification` + `provisioning P3-K`. One session on
`17A6`, U-Boot → the **B1 image** with budget 0? — no: with a tiny budget (the identity
page's budget = 9, the code probes only) so that every step of the loop is exercised once
on the new carrier without spending the mapping seed:

1. load `b1.bit` (sha-gated), identity, `VARIANT` reads `0x42310001` over the PS path;
2. key provisioning (P3-K), `key_loaded`;
3. the opening baseline: zero-table payload ARMs, readout all-zero, counters equal the
   pinned base `[18, 22, 20, 20, 20, 18]` (the scorer is unchanged);
4. nine code probes: each SCORED, each readout host-audited against the link-3 readback
   (the audit gate, unchanged) — the readouts are what the contract says they are, the
   PL's raw observation;
5. the closing baseline equal to the opening; the closing unsigned control refused
   (`F_ARM_AUTH`, fault 13) — the authorisation half of the gate is the instrument's;
6. a **host-attested reply control**: the runner, once, signs with the INSTRUMENT's signer
   (non-zero tables) for one extra candidate at the end — the PL ARMs (the fabric is
   indifferent), the host validator refuses the record (`(iii-B1)`), the session ends
   HOLD-by-design on that record — proving the contract is enforced at the host, on
   silicon. *(Whether this control belongs in the qualification or in a separate
   negative-control session is the owner's call; it is listed so it is not forgotten.)*

PASS = the instrument's session conditions (validation with the audit gate, closure,
controls, heartbeat, budgets) + items 1–5; then the owner marks the carrier qualified in
`manifests/b1_manifest.json` and the mapping session's ruling pair may be issued.
Until then `carrier.qualified` is false and both `host/b1_runner.py` and
`host/b1_adjudicate.py` refuse a mapping session on this carrier.

## 4. What this does not qualify

Long runs (the mapping session is ≈ 6 min; the L6 soak's 2 h guarantee is the P3
carrier's, not this one's — a B1 soak would be a separate decision if a long session were
ever planned); any other die; any change to the pblock or the constraints (none was made).
