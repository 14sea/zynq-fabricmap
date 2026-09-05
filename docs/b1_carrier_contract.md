# B1 carrier / signing contract — noninterference (v0.1, host-only, 2026-09-05)

> **Standing: host-only design, unbuilt on any board, no ruling.** Written after the owner's
> review of the first B1 package (2026-09-05): *"the observations that reach the cartographer
> are pre-certified by the host's hidden ground truth — a circular proof."* This document
> fixes the boundary so that it is not.

## 1. The defect, precisely

In the instrument (P3, `zynq-psoracle` `689dde1`) the host signer computes, from the
certificate-derived oracle, the six **expected truth tables** of every candidate and signs
`commit ‖ tables ‖ nonce` (`host/sign_arm.py`). The PL's arm gate sweeps the LUTs and
**requires the readout to equal those signed tables** (`rtl/p3_arm_gate.v` state 3:
`F_ARM_TABLE` otherwise); the application then refuses the candidate before any cartographer
sees the readout (`REFUSED_BY_PL`). So every readout the first B1 cartographer could learn
from had already been checked against the ground truth by the host. That proves that a
board program can *reconstruct tables the host attested*; it does not prove autonomous
mapping from unattested readouts. The permuted / dropout fixtures tested only the pure
cartographer; on the real carrier those fabrics would have been refused before it ran.

## 2. The contract

| link | who | before the measurement | after |
|---|---|---|---|
| 1 — the candidate is writable | host signer (D4 principal) | verifies the whitelist, the flush frames, the ECC; signs **`commit ‖ 0×12 ‖ nonce`** — the twelve table words are ZERO; the signer **never computes semantics** (`host/b1_sign_arm.py` replaces the semantic oracle's entry points with a refusal in-process before any signing — the module is imported transitively by the genome codec, so an assertion on import would be false; the disarming is what is tested) | — |
| 2 — what was staged is what was signed | application + host audit | the staging re-read hashes to the commit (unchanged) | the host recomputes from the served raw words (unchanged) |
| 3 — what is in the fabric is what was signed | application + host audit | the twelve-frame readback hashes to the commit (unchanged) | the host recomputes (unchanged) |
| authorisation | PL gate | SipHash over the payload with the provisioned key and the stepping nonce; no key / wrong key / replay / wrong commit are the same faults as before | — |
| **semantics** | **nobody before the measurement** | the gate sweeps all 64 vectors and exposes the readout **raw**; `tables_match` is computed and readable but **does not gate** (`rtl/b1/b1_arm_gate.v`, `SEMANTIC_GATE = 0`); `configuration_valid_hw = tag_ok ∧ sweep_done ∧ ¬recovery ∧ fault = 0` | the cartographer learns from the raw readout; **the ground truth is used only by the adjudicator, after the session** |
| the host validator | `host/b1_records.py` (successor of the instrument's `validators/records.py`, one rule changed) | rule (iii) no longer compares the readout with the reply's tables; instead it **refuses any reply whose table words are not zero** — a host that attested semantics violates the contract | — |
| identity | PL + application | the B1 carrier exposes `VARIANT` (`0x2034`) = `0x42310001`; the application reads it at identity and refuses to run on any other carrier; the IDENT carries it | the runner requires it |

What is unchanged: the whitelist gate (the universe is still the only thing that may be
written), links 2–3, the nonce chain, the key custody (D4), the watchdog, the audit
transport, rel-v4, the closing steps, the stop-loss.

What the contract gives up, knowingly: the instrument's on-chip check that the fabric
exhibits the signed content. For B1 that check is the *question*, so it cannot be a
*gate*; the host's post-hoc audit of links 2–3 (the bytes written and read back) still
binds every readout to the candidate that produced it, and the adjudicator's comparison of
the reconstructed map with the certificate is where a wrong fabric (or a wrong cartographer)
shows — as a finding, after the fact, never as a refusal before it.

## 3. The B1 carrier (`rtl/b1/`, `vivado/b1/build_b1.tcl`)

The instrument's RTL with: `b1_arm_gate` = `p3_arm_gate` + the `SEMANTIC_GATE` parameter
(1 reproduces the instrument bit for bit; 0 is the contract); `b1_axil` = `p3_axil` + the
read-only `VARIANT` word at `0x2034`; `b1_core` / `b1_top` passing the parameters;
`p3_siphash.v` verbatim. The carrier's own files (AXI3 shim, scorer, XDC, isolation
checks, generated constants) are this repository's `vivado/carrier`, hash-equal to the
copies the instrument imported. Same part, same pblock, same isolation checks, no ICAPE2,
no board IO. The build is `builds/b1/` (bitstream, timing, utilisation, isolation report,
`b1_build.json`); its carrier manifest is produced by the instrument's own
`gen_carrier_manifest.py` (read-only tool) over the new bitstream.

Simulation (`sim/b1/run.sh`, iverilog): the instrument's SipHash bench verbatim, and
`tb/b1/tb_b1_core.v` — the instrument's scenarios that still apply (alive, SLVERR, write-once
key, no-key, replay, unsigned, wrong commit, wrong key, reset) and the contract's own: a
zero-table payload ARMs and the readout is the bench's fabric that nothing named; a changed
fabric changes the readout and raises no fault; a payload with attested (non-zero) tables
still ARMs — the fabric is indifferent, the host validator is where such a reply is refused;
`VARIANT` reads the B1 word and is not writable.

## 4. Qualification before any B1 ruling (`docs/b1_carrier_qualification.md`)

A new carrier does not inherit the instrument's board-level guarantees. Host-verified now:
isolation (the routed design's report), ICAPE2 = 0, timing, the MMIO allowlist against
the RTL, the benches above, the frame table (target frames blank in the base, the positive
control frame, the flush frames), the carrier manifest validating under the instrument's
schema. Board-verified only under its own ruling, before the mapping session: load and
identity, key provisioning, the closing negative controls (unsigned / replay / wrong key
refuse; an attested reply is refused by the host), the two baselines equal, the readout of
one signed non-blank candidate equal to the host's audited link-3 readback — one short
**qualification session** with its own ruling pair; the mapping session follows under a
second pair.

## 5. What B1 now claims, and what it does not

Claims: the board, given the addresses and the safety class, chooses probes and builds a
map from readouts **that nothing checked against the ground truth before the cartographer
saw them**; the host's audit binds each readout to the bytes written and read back; the
ground truth enters only in the adjudicator's scoring. Does not claim: a human-blind test;
anything the first package did not claim either (unattested bits, routing, another die,
utility, the loop).
