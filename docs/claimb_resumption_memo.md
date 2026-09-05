# Claim B — resumption memo (ruled 2026-09-01: RESUMPTION-ELIGIBLE, still PAUSED)

> **DRAFT — 2026-09-01. This memo is not a resumption authorisation, not a preregistration,
> and not a change to any governing document. It authorises no board contact.** It exists so
> that the decision whether to resume Claim B's board programme is taken against the
> stop-loss's own words and the evidence produced since, with scopes and gaps in view. The
> stop-loss (`docs/claimb_findings.md` §5–§7, `docs/claimb_jtag_gate_review.md` §10) and the
> round-1 preregistration (`docs/claimb_preregistration.md`, still DRAFT) are quoted, never
> edited. The decision is the owner's (`zynq-psoracle/docs/p3_architecture.md` §9: "the
> decision to resume it — under its own preregistration, with the P3 instrument as its
> `carrier` — is fabricmap's owner ruling, recorded there").

## 0. Owner ruling — 2026-09-01 (additive; the draft below is unchanged)

> Claim B's "there must be a new mechanism" resumption condition has been satisfied by the
> PS/PCAP + P3 evidence within its explicit scope; the readback leg is therefore
> **RESUMPTION-ELIGIBLE**. Its execution status nevertheless **remains PAUSED** until a
> calibration/soak preregistration has passed and the two-operator image has completed P3
> compatibility review.

What the ruling means, in the owner's terms:

- the original ICAPE2 readback path is **not** resumed, and its failure is **not** claimed to
  be explained;
- the new path is an **architecture replacement**, not a retry of the old probe;
- Claim B still has **zero valid data points**;
- the first Claim B ruling must **not** be spent on calibration or integration debugging;
- blank FARs, the long run, cross-chip and the two-operator integration remain **explicit
  gaps** (§4);
- until the above is complete, PAUSED may **not** be changed to active/running.

Next host-only work, per the ruling: an independent calibration/soak preregistration that
pins the P3 stack, the two-operator image, the audit policy, the time/candidate budget and
the stop-loss; after that whole package is reviewed, a separate decision on whether Claim B
formally leaves PAUSED. That preregistration belongs to the instrument's repository
(`zynq-psoracle`, whose `l5_design.md` already assigns long-run sampling to "the long-run
prereg"); this repository records the decision and its pointer.

## 0a. 2026-09-05 — both conditions of §0 met; the ruling is requested (additive)

The calibration/soak preregistration (`zynq-psoracle/docs/l6_soak_prereg.md` v0.7,
`95d177a1…`) passed — Q1 by C1 #6 / C2 #2, Q2 by S #3 — and the two-operator image
`5deee74c…` completed P3 compatibility review, both owner-adjudicated in `zynq-psoracle`,
now archived (adjudication `32d1460`, archive head `689dde1`). The package and the request for the separate resumption ruling
are `docs/claimb_l6_package.md`. Nothing in §0 changes until that ruling is given.


## 0b. 2026-09-05 — ruled: RESUMED — PREREGISTRATION PENDING (HOST-ONLY) (additive)

The owner ruled on `docs/claimb_l6_package.md` (its §0 carries the text): Claim B leaves
PAUSED into a preregistration-pending, host-only state. Round 1′'s preregistration, runner,
validators, guards, model/replay tests, evidence index and candidate execution package are
authorised in one run of work; nothing is FROZEN or board-ruled before the whole-package
review, and the next board contact needs its own explicit ruling. §0 above and the draft
below remain as written.

## 0c. 2026-09-05, later — round 1′ WITHDRAWN BEFORE FREEZE / NO-RUN; the line re-shaped (additive)

The round 1′ package (`docs/claimb_round1prime_package.md`) found the pinned carrier's fitness additive over the 292 bits, so the map-guided A/B there is decided by arithmetic. On two audits the owner withdrew round 1′ before any freeze — it is not a Claim B negative — and re-shaped the programme into four stages — B1 autonomous mapping (with its correctness metrics), B2 map utility, B3 closed loop, B4 expansion; Claim B is now the map-utility stage B2 of `docs/autonomous_cartography_roadmap.md`. The readback leg's status stays as §0b ruled: host-only, no board contact, no ruling issued.

---

Author: Claude. Evidence repositories pinned: `zynq-psmap` `191ab05`, `zynq-psoracle`
`dbf471c`; this repository at `71666b0` (the commit P3 imported and pinned as `71666b02…`).

---

## 1. The stop-loss and the resumption condition, verbatim

**The ruling's stop-loss** (2026-08-20 session ruling; first repository artifact commit
`dd7721d`, quoted in `docs/claimb_findings.md` §5):

> If the review cannot find a credible Claim B verification chain, Claim B is PAUSED and the work
> to date is published as a complete negative result.

**The negative result** (`docs/claimb_findings.md` §5, commit `7cd37a3`):

> The candidate write was observed **twice, in separately established fault states, by the same
> JTAG method** to have landed at the intended FAR. The canonical carrier's **internal readback
> interlock faults on the candidate**, and its record of success covers only **degenerate
> all-zero content**. Neither the existing JTAG path nor the sibling HWICAP path can serve as a
> substitute gate without changing the measurement architecture.

**What is paused** (`docs/claimb_findings.md` §6): "Claim B's board programme. No board contact
is authorised." Not withdrawn: the diagnostic, per-frame-unique carrier fallback, with its six
constraints, unexecuted.

**What would reopen it** (`docs/claimb_findings.md` §7, commit `7cd37a3`):

> Not a fix to the present instrument. Either:
>
> * a **new, reviewed measurement architecture** in which the write-integrity interlock is
>   re-established around an oracle that can actually observe non-blank content (§3.5); or
> * the **diagnostic carrier** returning 15/15 same-FAR bit-exact non-blank frames on a fresh-load
>   no-op, which would for the first time establish that this engine can deliver non-blank
>   configuration data correctly, and would make H-PAD/H-ADDR/H-IDLE separable (§3.3).
>
> Absent one of those, further runs of the present carrier under the same all-blank authority do
> not provide distinctive content with which to separate the hypotheses. That is the condition
> this pause exists to stop paying for.

**The legitimacy condition for the first route** (`docs/claimb_findings.md` §3.5):

> replacing links 2–3 with a stronger oracle is **legitimate in principle** … But that legitimacy
> requires a **new, reviewed hardware architecture** in which the interlock is re-established
> rather than removed. **Direct bypass remains invalid.**

where the three links are (§3.5): *bytes the host candidate gate ACCEPTED == bytes actually
HANDED TO the guard == bytes READ BACK from the fabric*.

**The review's five necessary proofs** (`docs/claimb_jtag_gate_review.md` §2, commit
`dd7721d`), which any substitute gate was held to: (1) the scorer cannot arm until verified;
(2) the verifying path does not perturb the state under test; (3) restore and baseline are
still runnable afterwards; (4) any anomaly fails closed; (5) not a bypass of
`configuration_valid`.

**The PS line's own discipline** (`zynq-psmap/docs/stop_loss.md`): "There is exactly one thing
that may reopen it: **a new mechanism** … **A new instrument is not a new mechanism.**"

## 2. Evidence produced since, mapped onto those words

### 2.1 `zynq-psmap` `191ab05` — the oracle's three properties (instrument-feasibility, not Claim B)

| rung | observed (silicon, `17A6`, U-Boot) | scope as ruled | not tested, in its own words |
|---|---|---|---|
| S1–S3 (`s1s3_findings.md`, run #3, ruling 2026-08-29-02) | PS/PCAP reads a setup-loaded **non-blank** frame (`0x00000B99`) bit-exactly and repeatably, ten reads, no SHUTDOWN/START/RCRC, no startup transition; neighbours B98/B9A distinct; sentinel alive; `CTRL` untouched | Claim P "observed within scope"; "not extrapolated to P1, P2, Claim B, other dies, Linux" | non-perturbation; post-write readback; **Claim B's FARs `0x00400A20‥`, blank in the base, were not read; a BLANK there would say nothing (4,716 FARs share the blank hash)**; the carrier's ICAPE2 engine; any other die; Linux; U2/U3; "Claim B itself. Zero data points" |
| P1 (`p1_findings.md`, run #1, ruling 2026-08-29-01) | PCAP writes a certified content-bit change (`0x00400A20` word 51, blank→A→B, 14 whitelisted INIT bits) and reads it back bit-exact twice each; **terminal JTAG (R4) confirms B on the die, CRC_ERROR = 0**; `CTRL`/`PCFG_DONE` unchanged across the writes | "`17A6`, U-Boot control plane, the specified blank→A→B content-bit path. Nothing here extends to P2, Claim B, another die, or Linux" | non-perturbation; anything beyond LUT-INIT word 51 of one frame; a wrong/absent CRC; Claim B ("no map-guided arm, no random arm, no score"); other dies; what JSHUTDOWN/JSTART did afterwards |
| P2 (`p2_findings.md`, run #3, ruling 2026-08-29-03) | ten PCAP reads of a live-logic frame and one content-bit write leave the carrier's **eight** readable registers unchanged against a matched no-read control; 14/14 comparisons equal | "on this `17A6` carrier, in the eight pinned registers, under these PCAP operations, no state perturbation was observed. It is **not** a proof that a design kept computing (that is P2b)" | P2b (a counter-class observable on a computing design); everything above |

`s1s3_findings.md` §5 already placed this correctly: "it does not reopen `zynq-fabricmap`'s
paused readback leg, whose stop-loss asked for a new *mechanism*: this result is a new
mechanism candidate (a PS-side read with no shutdown), and it is now the far goal's job (P3, a
new repository) to build the interlock around it."

### 2.2 `zynq-psoracle` `dbf471c` — the interlock re-established around the PS oracle (P3, L0–L5)

P3 is the "new, reviewed measurement architecture" route. Its ladder, all adjudicated by the
owner (`zynq-psoracle/docs/status.md`):

| rung | what it established | how it was reviewed |
|---|---|---|
| L0 architecture (`p3_architecture.md`, v0.3) | three links kept; **link 1 unchanged** (this repository's `gate_candidate.py`, 292-bit whitelist, flush verbatim, ECC recomputed — imported at `71666b02`, never edited); links 2–3 witnessed by the **host** from bytes it actually received (staged streams re-read; frames read back by PCAP), never from a match bit the PL reports; a scorer that arms only on a **signed ARM** (SipHash tag over commit + tables + nonce) from a notary that signs only after its own whitelist verdict; a hardware-enforced nonce chain; fail-closed everywhere | L0 REJECT → A′ accepted → whole-line gate review PASS (2026-08-29) |
| D4 key custody | signer and runner are different OS principals; runner cannot read the key or open the pod (R1–R5 verified before every session) | owner re-review PASS |
| L1 carrier `956379fa…` | the same **twelve target FARs** as Claim B (`0x00400A20‥23`, `0x00400C1A‥1D`, `0x00400C20‥23`), **all blank in the base** as in Claim B's; isolation 6/0; ICAPE2 count 0; positive-control frame `0x0040129D` globally unique | owner PASS (preparation) |
| L2 non-perturbation | P2's discipline re-run on the P3 carrier; heartbeat pinned [49.5, 50.5] MHz | owner PASS on `17A6` |
| L3 one gated candidate | a candidate accepted by link 1, staged, witnessed at link 2, DMA'd, read back at link 3, ARMed with a real signature and **scored**; negative controls refused with the expected faults; five sessions | owner PASS (scoped) |
| L4 fault / restore / baseline | a fault latches and disarms; restore to the pinned base; baseline re-scored `[18, 22, 20, 20, 20, 18]` | owner PASS |
| **L5 the loop** (session 4, `evidence/l5_17A6_2026-09-01-04/`, image `a7c73d1f…`) | the standalone application ran the whole loop PC-free of scoring: opening baseline, **eight distinct non-blank candidates**, closing baseline, closing unsigned control; 10/10 `SCORED`; every readback recomputed on the host from served raw words (80 audit chunks, three hash domains, an independent second implementation agreeing); nonce chain 11/11; both baselines exactly the pinned scores; the unsigned control refused `F_ARM_AUTH`; zero disruptions | owner **PASS (scoped)**, 2026-09-01, after four design-review rounds of the correction batch |

**The L5 scope, verbatim** (`zynq-psoracle/docs/status.md`): *EBAZ4203 17A6, carrier
`956379fa…`, application image `a7c73d1f…`, the U-Boot→standalone control-plane crossing, a
host-supplied seed, N = 8, all-self-reporting audit, under the established notary/interlock.
Not extrapolated to autonomous discovery, long-run stability, other carriers/dies, Linux, or a
precise ARM-gate time.*

### 2.3 The mapping, item by item

| the stop-loss asked for | what now exists | status |
|---|---|---|
| "a new, reviewed measurement architecture" | P3: L0 architecture with an owner-adjudicated whole-line gate review; every rung reviewed before its ruling | **met, within P3's scope** |
| "in which the write-integrity interlock is re-established rather than removed" | links 2–3 computed by the host from bytes it received, and enforced in hardware by the signed-ARM gate: no signature → no arm → no score (L3/L4/L5 closing controls) | **met**; the interlock is not the carrier's `configuration_valid` — it is a different interlock with the same three links, which §3.5 says is legitimate if reviewed |
| "around an oracle that can actually observe non-blank content" | S1–S3 (non-blank frame, bit-exact), P1 (written content confirmed by a second instrument), **L5: eight non-blank candidates on Claim B's own twelve FARs read back bit-exact by the PS and recomputed on the host** | **met on the PS path**; the carrier's internal ICAP readback engine is untouched and still only ever succeeded on all-zero content |
| review proof 1 — cannot arm until verified | the scorer arms only on a signed ARM; the signature is issued by the notary only after the host has witnessed links 1–3; `F_ARM_AUTH` on a zero tag (every session's closing control) | met |
| proof 2 — the verifying path does not perturb the state under test | P2 (psmap) and L2 (psoracle): PCAP reads/writes leave the observable state unchanged | met for the observables pinned; **not** for "a design kept computing" (P2b never run) |
| proof 3 — restore and baseline still runnable afterwards | L4; and L5's closing baseline equal to the opening one after eight candidates | met |
| proof 4 — fail-closed | validators with a `Falsified`/`HOLD` boundary; the audit gate inside `validate_standalone_run_log`; rulings consumed by any outcome | met |
| proof 5 — not a bypass of `configuration_valid` | not a bypass: the carrier's interlock is replaced by a reviewed one, exactly the case §3.5 admits; P3 does not touch this repository's carrier or its readback | met in the sense §3.5 defines |
| psmap's rule: a new mechanism, not a new instrument | the mechanism is specific and was falsifiable: the PS reads the fabric through PCAP without any startup transition, so the carrier keeps computing while it is read; predicted and observed (S1–S3, P2, L2) | met |

## 3. Non-claims that travel with the evidence (and must travel into any resumed prereg)

- Nothing above is a Claim B data point. No map-guided arm, no random-safe arm, no primary
  metric, no holdout has ever been run. Claim B still has **zero data points**.
- Every measurement is on **one die, `17A6`**, one carrier per line, one control plane per
  line (U-Boot for psmap; U-Boot→standalone for P3), the stated registers/frames only.
- P3's `SCORED` records are the P3 scorer's six LUT counters under P3's sweep; they are not
  the round-1 primary metric ("best holdout fitness at a fixed evaluation budget") until a
  preregistration says how the two relate.
- L5's PASS explicitly excludes autonomous discovery (its search was a reference sampler with
  a host-supplied seed), long-run stability, and any time figure ("16 reads" is a count).
- P1 wrote **14 bits of one word of one frame**; L3/L5 wrote candidates over the 292-bit
  universe, but their content was chosen by P3's sampler, not by a map-guided operator.

## 4. Gaps Claim B has not closed — stated as gaps, not as hidden asks

1. **Blank FARs.** Claim B's twelve target FARs are blank in the base (this repository's
   prereg §2; P3's carrier manifest: zero non-zero words in every target frame). s1s3 §4's
   warning stands for reading the *base*: a BLANK read there is undiagnostic (4,716 FARs here,
   4,326 in P3's carrier, share the blank hash). What P3 changed is that the frames *read* are
   candidate content, non-blank whenever the genome is non-zero, and the read is attributed
   by FAR through the PS oracle with a globally unique positive-control frame in the same
   session. What remains untested: a **blank-genome candidate** (the two baselines) is by
   construction the same all-zero content the old interlock succeeded on; its readback
   attribution rests on the positive control and the per-session identity, not on
   distinctive content. The diagnostic-carrier fallback (§7 bullet 2) would give distinctive
   content at every FAR; it is unexecuted and this route does not need it, but it also does
   not deliver it.
2. **Long runs.** The longest P3 epoch is N = 8 (minutes). Claim B's budget is "derived from a
   measured evaluation rate on this board" and the runs are hours; no P3 session has measured
   that rate, and the watchdog is **off** (D-c option 2). Long-run stability is outside L5's
   scope by the owner's words. A calibration/soak preregistration would have to precede any
   budget freeze.
3. **Cross-chip.** Everything is `17A6`. Round 1 as preregistered is single-board, so this is
   not a gap *for round 1*, but the 4205 — the die the ICAPE2 line ran on — has never run the
   P3 stack, and the negative result of §1 was on it. Nothing here explains the old engine's
   behaviour on that die.
4. **The original Claim B path.** The carrier-internal ICAPE2 readback, the three
   hypotheses H-PAD/H-ADDR/H-IDLE (§3.3), and the diagnostic carrier remain exactly where the
   findings left them. The PS route **goes around** the paused mechanism; it does not explain
   it, and a resumed Claim B on the PS route would say nothing about it. That should be
   written into the resumed programme's non-claims so that a Claim B result is never read as
   a resolution of the readback question.
5. **Universe and map identity.** P3 imports this repository's `gate_candidate.py`,
   `local_map.json` and certificates at `71666b02` (292 bits, twelve FARs). A resumed prereg
   must re-verify that pin (the prereg's own falsifier 3, compatibility drift) rather than
   inherit it by name.
6. **The evaluation loop is different.** Prereg §6 was ruled on **partial-frame ICAP** with the
   carrier's internal readback; P3 stages three PCAP write envelopes (twelve targets + flush
   frames), re-reads the staging, DMAs, and reads back twelve frames by PCAP. §6's transfer
   arithmetic, budget and control-plane boundary (§6 "the control-plane boundary": U-Boot-only
   identity) are all superseded by P3's crossing to a standalone application with its own
   identity page and epoch. None of that is a defect; all of it is a **new** prereg, not an
   amendment.
7. **Two arms on the board.** Round 1's only difference between arms is the mutation
   operator. P3's application carries a reference sampler (`p3_search_next`), not a map-guided
   operator and not a random-safe operator. Implementing both on the standalone plane is a
   firmware change → a new image → P3's own build/prereg/review discipline before any Claim B
   ruling. Running the operators on the host instead would move candidate selection off the
   board and change P3's "PC-free" scope; either way it is a decision to record.
8. **Audit under a long run.** L5 audited every self-reporting candidate (`all-self-reporting`);
   `l5_design.md` §1's 1/16 sampling belongs to a long-run prereg that does not exist.

## 5. The two options for the owner

**Option A — resume Claim B on the PS/PCAP oracle, with the P3 stack as the `carrier`.**
This is the route §7's first bullet admits and §3.5 calls legitimate if reviewed; P3 was
built to be that review. What it buys: a read/write/verify chain that has scored non-blank
candidates on Claim B's twelve FARs with a host-computed interlock. What it costs: a new
preregistration (§6 below) and the gaps of §4 items 2, 6, 7 and 8 closed *before* a budget is
frozen. What it does not do: resolve the ICAPE2 readback question (§4 item 4).

**Option B — keep Claim B PAUSED.** Right if the owner judges that (i) the diagnostic-carrier
route (§7 bullet 2) is the one worth the next board time, because it would explain the old
engine rather than route around it; or (ii) the §4 gaps — especially the untested long run and
the arms not yet on the board — mean a resumed programme would spend its first rulings on
instrument work again, which is the pattern the psmap stop-loss was written against; or (iii)
the pause should hold until the P3 result has been reproduced on a second die.

The author's view, marked as such: the evidence meets §7's first condition within P3's scope,
so Option A is *admissible*; whether it is *worth it now* turns on §4 items 2 and 7, which are
engineering before science. A middle path the owner may prefer: rule Option A **admissible in
principle** (recording that §7 is satisfied on the PS route), and defer the actual resumption
ruling until a calibration/soak prereg and the two-operator image exist and have passed P3's
review — so that the first Claim B ruling is spent on Claim B.

## 6. If Option A: what a resumed programme needs before its first ruling

1. **A new Claim B preregistration** ("round 1′") in this repository, superseding the DRAFT
   one by reference, not by edit: the claim (§1), the universe (§2, re-pinned against P3's
   import), the map (§3), the metrics and paired-seed/interleaving/firewall rules (§4), the
   falsifiers (§5) carried over verbatim where they still apply; §6 rewritten for the P3
   evaluation loop; §7 gates extended by P3's validators and audit gate; §8–§9 rewritten
   for the standalone plane; §10 frozen with hashes.
2. **Instrument pins:** `zynq-psmap` `191ab05`, `zynq-psoracle` `dbf471c` (or a later
   reviewed commit), carrier `956379fa…`, the two-operator application image (new, reviewed,
   byte-identical rebuilds), this repository's `71666b02` artifacts.
3. **Identity and epoch:** P3's identity page (session token, `uboot_epoch`, `app_epoch`,
   carrier sha, image sha, `fclk0_hz_decoded`) plus `board_session` identity (`17A6`, role
   `verify`, IDCODE); one epoch per power cycle; the `CPU_CLK_CTRL` preflight; the D4
   boundary verified as the runner < 6 h before every session.
4. **Rulings:** this repository's rule is one whole-of-run board ruling per round (prereg
   header); P3's rule is a fresh pair per session (`whole-of-probe P3-L5` + `provisioning
   P3-K`, consumed by any outcome). A resumed programme needs a ruling text of its own for the
   Claim B run (e.g. `whole-of-run Claim B round 1′`) checked by the Claim B runner exactly as
   P3 checks its own, with the P3 session rulings still issued per session underneath it.
5. **Budget and the long run:** a calibration/soak preregistration first (measured
   evaluation rate on the P3 path; watchdog decision — D-c option 1 needs a prescaler build;
   heartbeat/CRASH thresholds for hours), so the budget can be frozen from a measurement.
6. **Stop-loss, in advance:** prereg §5's four falsifiers; P3's kill criteria and prereg §6
   stop-loss (two sessions lost to the same instrument cause → fix and prove; three without
   `COMPLETED` → design review); psmap's "a new instrument is not a new mechanism"; and the
   rule this memo inherits from the whole line: a `STOPPED`/`CRASHED` end is a HOLD, never
   argued into a PASS, and a falsifier is a KILL for the claim.

## 7. What this memo is not

It is not evidence; every observation above lives in the three repositories at the pinned
commits. It does not change `docs/claimb_findings.md`, `docs/claimb_jtag_gate_review.md`,
`docs/claimb_preregistration.md` or the README; the pause stands until the owner rules. It
does not request a ruling, a build, or board time. It does not decide.
