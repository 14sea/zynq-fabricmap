# The JTAG write-verification gate — a host-side design review, and the stop-loss

**Host-side review only. No RTL was changed, no Vivado run was performed, the board stayed
powered down, and nothing here authorises a board action.** Everything below is reading of
already-committed artifacts in this repository plus one read-only audit of a sibling tree.

**Outcome: the review did not pass, and the pre-committed stop-loss is formally triggered.**

---

## 1. The question this review was asked

Ruled 2026-08-20, superseding the diagnostic-carrier design of the same evening (that design
remains the fallback and is not withdrawn by this document):

> Can a Claim B **write-verification gate** be built on the **already-validated JTAG path**,
> without lowering safety?

The ruling fixed five things the gate must prove **together**, and fixed in advance that a gate
failing any one of them is not a gate:

1. the **scorer cannot arm** until the candidate *and* the controls are verified;
2. **R4/JTAG does not perturb** the phenotype under test or the measurement's starting state;
3. **restore and baseline can still be run safely** after verification;
4. **any** control, marker, identity or bookkeeping anomaly **fails closed**;
5. it is **not** a dressed-up bypass of the `configuration_valid` interlock.

The same ruling attached a stop-loss, quoted in full in §6.

## 2. Verdict table

| # | proof | verdict |
|---|---|---|
| 1 | scorer cannot arm until verified | **FAILS — no hardware channel exists** |
| 2 | R4/JTAG does not perturb the state under test | **FAILS — structurally, not incidentally** |
| 3 | restore and baseline still runnable afterwards | **NOT ESTABLISHED** |
| 4 | any anomaly fails closed | **achievable** |
| 5 | not a bypass of `configuration_valid` | **legitimate in principle, unavailable in practice** |

One proof of five is clean. The ruling's own standard disposes of the design.

---

## 3. Proof 1 — the arm interlock has no host-side channel

`vivado/carrier/carrier_scorer.v:26`:

> `configuration_valid` is the other half and it is **NOT a software bit**. It is driven by
> the guard's readback compare.

`carrier_scorer.v:103` is the enforcement: `else if (!configuration_valid || recovery_required)`
freezes and disarms.

The arm condition of `docs/claimb_carrier_design.md:217` is

> **arm ⟺ `gate_verdict.writable` ∧ `configuration_valid` ∧ `¬recovery_required` ∧
> `candidate_sha256 == readback_sha256`**

and the same section records that **`carrier_scorer` enforces the conjunct in hardware**. The
host's `arm` is a write to CTRL (AXI offset `0x2000`) with bit 6 set (`CTRL_ARM = 0x40`); it is
only a request, and the PL refuses it unless its own internal readback compare has raised
`configuration_valid`.

**A host-side JTAG verdict has no wire to that bit.** This is not a question of protocol design
or host sequencing: there is no path, in the carrier as built, by which an out-of-fabric
observation can satisfy the arming interlock. Connecting one is an RTL change, which this pass's
hard limits exclude, and which §7 shows is also the failure mode proof 5 names.

### The two variants that were considered, and why both die here

**Verify-last, quarantine-and-promote** — measure first, verify after, admit the score only on a
passing verification. This would dodge proof 1's letter and proofs 2 and 3 entirely, because the
verification becomes terminal. It fails anyway: to have a score at all the scorer must have
armed, which requires `configuration_valid`, which requires the internal readback to have
verified a **non-blank** candidate — the exact thing that has never happened. F1 records that
every frame the engine is authorised to rewrite is blank in the base, so the only non-blank
content in play is the candidate itself: **the interlock is unbroken precisely and only in the
degenerate all-zero case, and fails in the one case a gate would be for.**

**Drop the in-fabric scorer and measure the phenotype another way** — a new instrument. Out of
scope here, and it is the fallback design's territory.

## 4. Proof 2 — the JTAG path's validity comes from the action this project forbids

`docs/claimb_r4_protocol.md` §1 records what R3-control established, **for this fixed probe
sequence on this device**: without `JSHUTDOWN` a fresh load with no transaction returns
**0/16**, where the same controls read **16/16** with it. That document is careful that this is
a fact about this instrument and this part and not a general law, and this review does not
upgrade it.

But it does mean the shutdown is not decoration. **It is the mechanism by which this JTAG path
reads anything at all.**

Against that, `docs/claimb_icape2_readback_sequence.md` §1 rules on the read path:

> The SHUTDOWN / GTS / GRESTORE flow does not apply and must not be copied. … This carrier
> **contains the engine doing the reading**: `carrier_stream`, its CRC, its AXI window and the
> U-Boot transport all live in the fabric being read. A SHUTDOWN would stop the machine
> mid-transaction, and `GTS`/`GRESTORE` reach every flip-flop on the die.

**The sharpest finding of this review is that the two are the same action.** The path offered as
"already validated" earns its validity by performing, from outside, the die-wide startup-sequencer
transition that this project forbids the internal path from performing. That is not a detail that
could be engineered away; it is how the instrument works.

The emitted script agrees. `scripts/probe_jtag_config_read.py` builds

```
JSHUTDOWN → runtest 12 → JSTART → runtest 2000 → RCRC envelope → JSHUTDOWN → runtest 12
  → per FAR: RCFG → FAR → FDRO → CFG_OUT → DESYNC
```

and `docs/claimb_r4_protocol.md` §2 requires **one FAR per child process**, because a readback is
trustworthy only as a process's first read. A seventeen-read acquisition is therefore **seventeen
shutdown/startup cycles** applied to the design under test.

## 5. Proof 3 — post-R4 continuation is not established

This is stated as a gap in the evidence, **not** as a general impossibility. What is established:

* every child's emitted script ends at the readback prefix's `JSHUTDOWN`, then the per-FAR
  transactions, then `echo "@@ desync done"` and OpenOCD's own `shutdown` — **there is no
  trailing `JSTART`**, so the part is left in the shutdown state;
* `scripts/board_signature_search.py` contains no board-side restart or restore (its `resume`
  paths are host-side index continuation, not board recovery);
* in `docs/claimb_location_reproduction_spec.md` the acquisition is step ④ and step ⑤ is
  host-side only, so in both O1 and O2 **nothing was ever run on the board after an R4
  acquisition**. Restore and baseline after verification have never been attempted, let alone
  verified;
* adding a trailing `JSTART` would complete the startup transition, and by §1 of the ICAPE2
  derivation that transition reaches every flip-flop on the die. It would therefore disturb
  whole-die sequential state — including the carrier's own state machine, counters, markers and
  bookkeeping — which makes it **unsuitable for the Claim B phenotype as currently defined**.

So the honest statement is: continuation after R4 is **not established to be possible**, and the
one obvious way to establish it is disqualified by proof 2's reasoning rather than by a
measurement.

## 6. Proof 4 — fail-closed is achievable

This is the one proof the JTAG path meets. The sixteen pinned positive controls are the verdict
and nothing else is (`claimb_r4_protocol.md` §7); `plmark` identity pairing binds an acquisition
to its boot; and `probe_jtag_config_read.py` already refuses to emit a script that leaves an
envelope open (`envelope_violations`) or whose recovery prefix is not R4 in order and by exact
dwell (`recovery_order_violations`). Content comparison within a single run — `A20` against the
candidate, word for word — is what O1 and O2 already did and is admissible; the standing
prohibition is on comparing captured content **between rungs**.

Recording this matters for any future architecture: the fail-closed machinery is not what is
missing.

## 7. Proof 5 — what `configuration_valid` actually is

`docs/claimb_carrier_design.md` §3b is explicit:

> **A readback compare proves exactly one thing: the fabric now holds what the guard actually
> received and wrote.** It does not prove that candidate was *permitted*.

Candidate authorisation — the 292-bit whitelist, flush frames equal to the pinned base verbatim,
each ECC a correct recomputation — is **link 1**, the host's, in `scripts/gate_candidate.py`, and
it runs before anything is written. §3b says the PL does not re-implement a content gate and
"must simply not be described as one".

So the accurate name for `configuration_valid` is: **the scorer's hardware write-integrity,
readback-attribution and validity interlock.** It establishes links 2 and 3 of

> bytes the host candidate gate ACCEPTED == bytes actually HANDED TO the guard
> == bytes READ BACK from the fabric

It is **not** a candidate authorization or whitelist gate.

Two consequences, and they must be kept together:

* **In principle, replacing links 2–3 with a stronger oracle is legitimate.** §3b itself demands
  that the third conjunct be "computed by the HOST from readback bytes it actually received —
  never from a match bit the PL reports", and an out-of-fabric instrument carrying sixteen pinned
  controls per acquisition is a stronger reading of that requirement, not a weaker one.
* **That legitimacy does not license the present design.** Such a substitution would have to be a
  **new, reviewed hardware architecture** in which the interlock is re-established, not removed.
  No host-side verdict can reach this line as the carrier is built, and **bypassing the interlock
  directly remains invalid** — which is exactly what proof 5 was written to forbid.

## 8. The sibling-path audit — `zynq_xpart/scripts/hwicap-uart.py`

Audited read-only under the standing isolation rule; nothing was imported and nothing in this
repository depends on that tree. The lead was carried as **UNVERIFIED**; the code has now been
read.

### What it establishes — a weaker proposition than the lead hoped for

> On the **same device type, on another board instance**, and with a **different carrier and a
> different (AXI HWICAP) implementation**, an FDRO stream has been reported to contain
> recognisable **non-blank LUT-INIT content**.

That is the whole of it, and the qualifications are load-bearing:

* the claim is a **single sentence of prior-art prose** (`zynq_xpart/docs/icap_investigation.md`,
  the HWICAP-readback section) with **no pinned evidence record** behind it;
* there is **no stable same-FAR whole-frame exact capture**. A full frame is pad (~101 words) +
  frame (101 words) = 202 words against a read FIFO of ~128, the controller does **not**
  back-pressure ICAP, and words past the FIFO are lost;
* chunked draining reaches further but the **FDRO chunk boundary drifts run-to-run** — two
  back-to-back reads differed by about 18 words — so the prior art's own conclusion is that a
  clean automated before/after frame compare **is not reliable**. Its recommended reliable check
  is the **register** read (`readreg`), not a frame read.

### What it does and does not do to this repository's findings

* It **does not** answer W2, and must not be written up as having done so. **W2's
  frozen-inventory verdict is unchanged**: 7 transactions, 105 frames, 0 non-blank.
* It **does not** establish that the problem lies outside the silicon or the configuration
  engine, and no such statement may be made on its authority.
* It **does** make a **silicon-wide impossibility** — the reading in which this part's
  configuration engine simply cannot return non-blank frame content — **less credible, on the
  strength of this prior-art self-report.** That is a change in credence, not a fact established.
* It **independently corroborates** `claimb_r4_protocol.md` §1's refusal to generalise "readback
  requires a shutdown". The HWICAP path is reported to have returned frame content with **no
  `JSHUTDOWN` at all** (it requires `PCAP_PR=0` instead). Whatever compels the shutdown is a
  property of the JTAG instrument on this part, not a law of the device.

### As a candidate third oracle: no

It fails proof 1 for the same reason the JTAG path does — it is a PS-side instrument and cannot
raise `configuration_valid` in the carrier's fabric. It additionally fails to offer bit-exact
capture at all, and the prior art's own suggested fixes are a deeper HWICAP read FIFO (**not a
parameter on the stock IP**) or a bench-side drain faster than the ICAP stream (the transport is
U-Boot `md`, one word per UART command at 115200 — short by orders of magnitude).

An additive, dated note has been added to `docs/claimb_icape2_readback_sequence.md` §4c so that
the citation there carries these limits alongside the precedent it legitimately supplies.

## 9. Cost was never the obstacle — record this so it is not misread later

`docs/claimb_location_reproduction_spec.md` §6 budgets step ④'s hit branch at **17 reads, ≈2 s**.
Both executed 17-read hit acquisitions record **1.8 s** directly
(`evidence/location_sweep_2026_08_20/reading_steps_2_to_5.md` and
`evidence/location_reproduction_2026_08_20/reading.md`).

The two measured per-read rates in this repository are **0.1007 s/frame** (ibid. §6) and
**0.125 s/frame** (`docs/claimb_location_sweep_request.md`, from the two 2026-08-16 R4
acquisitions), putting seventeen reads between about **1.7 s and 2.1 s**.

> **JTAG was not rejected for being slow.** It was rejected because there is **no hardware
> interlock channel** for its verdict, and because **the read sequence that makes it work
> perturbs the state under test**.

A future architecture that solves the interlock and the perturbation does not then have a
throughput problem to solve, and should not be designed as though it does.

## 10. Conclusion and the stop-loss

> This JTAG-gate review did not pass the five necessary conditions, and Claim B is **paused**
> under the pre-committed stop-loss. The negative result established is: the candidate write was
> observed **twice, independently, by JTAG** to have landed at the intended FAR; the canonical
> carrier's internal readback interlock **faults on the candidate**, and its record of success
> covers only **degenerate all-zero content**. Neither the existing JTAG path nor the sibling
> HWICAP path can serve as a substitute gate without changing the measurement architecture.

The stop-loss was chosen in advance, on 2026-08-20, and it was chosen precisely so that a later
session could not drift past it by finding one more thing to fix. It is triggered here on its own
terms.

**What is paused, and what is not.** Claim B's board programme is paused. The fallback design of
the diagnostic, per-frame-unique carrier is **not withdrawn** — it stands, unexecuted, with its
six constraints intact, and §7 of this document is the finding it would most need if it is ever
revived: the interlock is re-establishable in principle, and only in a new reviewed hardware
architecture.

**Publication is the next action, not further instrumentation.**

## 11. What this review did not do

* It did not touch the board, run Vivado, change RTL, or run `zynq_autoehw`.
* It did not use Linux `fpgautil` (a failed load wedges DEVCFG and costs a power cycle).
* It did not import, execute or depend on anything in the sibling tree; `hwicap-uart.py` was
  read, and nothing else.
* It did not re-open Claim A, Claim C, PCAP/devcfg, a second die, or mechanism research.
