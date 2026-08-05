# `clb_ff_config` pre-registration plan — committed before any specimen bitstream

**Status: COMMITTED 2026-08-05, no specimen bitstream built.** Commit `c45e76e` lifted
the explicit hold; commit `2b40693` then recorded
`gate_runs/run_2026_08_05_ff/predictions.json` at sha256
`5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51`.
The git ordering is the evidence: this exact plan existed before the first build.

The commitment permanently fixes the four items this document put to the author:

1. the **key space** — which `(specimen, feature)` pairs exist at all;
2. the **completeness rule** — which of them must be reported for the certificate to be
   emittable;
3. the **coverage denominator** — and the numerator, `attested_count`;
4. the **split** — which keys can never score.

None of these may now be reshaped for this run.

## 1. The class, recomputed from the freeze

`clb_ff_config` is **176 entries, every one single-bit**, evenly spread: 44 per tile
type, 22 per site instance, 8 site instances.

| shape | features per site instance | entries | how the bit is moved |
|---|---|---|---|
| per-FF | 16 | 128 | `[A-D]5?FF.{ZINI,ZRST}` — 8 FFs × 2 |
| per-slice singleton | 4 | 32 | `CEUSEDMUX`, `FFSYNC`, `LATCH`, `SRUSEDMUX` |
| per-slice complementary | 2 | 16 | `CLKINV` / `NOCLKINV` — the class's only negated tokens (8 of them) |

Grouped by polarity-free coordinate set (the freeze-derived rule, bits not names):
168 groups = 160 singleton + 8 two-member, the 8 being exactly `CLKINV|NOCLKINV`.
**Zero multi-bit scopes**, which is why round 9 ruled the feature model for this class.

Site instances, one per (tile type, slice index), all in clock row Y25 so the clock
region never varies across the run:

| site instance | tile | site | prefix | split |
|---|---|---|---|---|
| 1 | `CLBLL_L_X2Y25` | `SLICE_X2Y25` | `SLICEL_X0` | **mine** |
| 2 | `CLBLL_L_X2Y25` | `SLICE_X3Y25` | `SLICEL_X1` | holdout |
| 3 | `CLBLL_R_X11Y25` | `SLICE_X14Y25` | `SLICEL_X0` | holdout |
| 4 | `CLBLL_R_X11Y25` | `SLICE_X15Y25` | `SLICEL_X1` | holdout |
| 5 | `CLBLM_L_X6Y25` | `SLICE_X8Y25` | `SLICEM_X0` | holdout |
| 6 | `CLBLM_L_X6Y25` | `SLICE_X9Y25` | `SLICEL_X1` | holdout |
| 7 | `CLBLM_R_X17Y25` | `SLICE_X24Y25` | `SLICEM_X0` | holdout |
| 8 | `CLBLM_R_X17Y25` | `SLICE_X25Y25` | `SLICEL_X1` | holdout |

`SLICE_X2Y25` is `mine` for the same reason it was in runs A and B: the harness rules
(addressing, ECC exclusion, anchoring) were established there, so its evidence is spent.
That gives **22 mine keys and 154 holdout keys, denominator 176, `attested_count` 176 —
the whole class**.

> **Ruled 2026-08-04: 22 / 154 stands, instance 6 stays holdout.** `SLICE_X9Y25` was the
> anchor *keeper* site for the `clb_lutram` isolation work, but a keeper discloses
> nothing about its own FF bit mapping — it was held clocked and untouched, and no
> configuration bit of it was ever measured or asserted. Tolerating a mode is not
> knowledge of where its bits live, so its evidence is not spent.

## 2. Specimen family, per site instance

Every design instantiates **all eight storage elements of the slice under test**, so
every per-FF bit exists and can be moved individually — **except the `LATCH` pair, which
cannot**: `A5FF` and its siblings are BEL type `FF_INIT` and will not hold an `LDCE`
(measured, `docs/ff_latch_probe.md`). That pair is four elements on `AFF..DFF` at both
endpoints. This is a change from
`vivado/specimen/specimen_ff.v`, which pins exactly one FF per slice: that was right for
establishing isolation, and is wrong for covering `[A-D]5?FF.*`.

The `ANCHOR=1` structure from `docs/lutram_anchored.md` is mandatory here, not optional:
four `DONT_TOUCH` LOC+BEL-forced cells consuming every port and the buffered clock, plus
a clocked keeper beside the site under test. Without it the modes below trim different
IBUFs, `RIOB33`/`RIOI3`/`CLK_BUFG_*` bits land in `ownership_unknown`, and 1.4 counts
those as FP with FP=0 required.

Baseline design **B**: eight `FDRE`, `INIT=1'b1` on all of them, `CE` and `R` both
driven from ports, synchronous reset, non-inverted clock.

| # | variant | differs from B by | asserts | feature endpoint |
|---|---|---|---|---|
| 1–8 | `zini_<BEL>` | that FF's `INIT` = `1'b0` | `<BEL>.ZINI` | the variant |
| 9–16 | `zrst_<BEL>` | that FF becomes `FDSE` (`SRVAL=1`) | `<BEL>.ZRST` | **B** |
| 17 | `ce_tied` | `CE` tied to `1'b1` | `CEUSEDMUX` | **B** |
| 18 | `sr_tied` | `R` tied to `1'b0` | `SRUSEDMUX` | **B** |
| 19 | `async` | `FDCE` (asynchronous clear) | `FFSYNC` | **B** |
| 20 | `latch` | four `LDCE` on `AFF..DFF` | `LATCH` | the variant |
| 21 | `latch_base` | four `FDCE` with `IS_C_INVERTED` on `AFF..DFF` | — | it is the `LATCH` pair's comparison endpoint |
| 22–23 | `clkinv` | `IS_C_INVERTED` on the clock pin | `CLKINV` (variant) and `NOCLKINV` (**B**) | both |

`latch` and `latch_base` are the one pair that is **not** against B, and the one pair
with four storage elements rather than eight. Both facts are measured, not chosen:
`A5FF` and its siblings will not hold an `LDCE`, and a latch differenced against B moves
`FFSYNC` and `CLKINV` as well as `LATCH` (`docs/ff_latch_probe.md`).

**The "feature endpoint" column is a falsifiable prediction, not bookkeeping.** Four of
these features are predicted to be asserted in the *baseline*, because of the `Z`
polarity convention: `ZINI = 1` when `INIT = 0` was measured directly (`31_03` =
`AFF.ZINI`, INIT 0↔1 moves exactly that one bit and nothing else), and this plan extends
the same reading to `ZRST = 1 ⟺ SRVAL = 0`, `CEUSEDMUX = 1 ⟺ CE actually driven`,
`SRUSEDMUX = 1 ⟺ R actually driven` (measured once: tying `R` off flips it 1→0),
`FFSYNC = 1 ⟺ synchronous`. If any of those polarity readings is backwards, the gate
records FN on that key and the certificate fails. That is the intended behaviour and the
reason not to soften them into "either direction counts".

Per site instance: **15 place-and-route runs** (B, eight `zrst_*`, and six slice-wide
designs) and **23 bitstreams** — the eight `zini_*` bitstreams come from B's single
routed checkpoint, because `INIT` is a cell property and `write_bitstream` can be re-run
without re-placing anything. B is one endpoint of 20 of the 21 pairs; the `clkinv` pair
carries two features (the complementary `CLKINV`/`NOCLKINV`), which is how 21 pairs
assert 22 features. Across all eight instances: **120 P&R runs, 184 bitstreams, 168
endpoint pairs, 176 predictions**.

**Both endpoints of every pair are preregistered.** From schema 1.5 each prediction
carries `comparison_specimen_id` alongside `specimen_id`, and the verifier requires the
certificate's `baseline_specimen_id` to equal it and `pair_accounting[]` to be exactly
the pair set the commitment implies. Without that the plan would fix what is claimed
while leaving what it is compared against open until after the build
(`docs/round10_request.md`, `docs/round10_handoff.md`).

Per-FF features get **one pair each** rather than one pair moving eight bits. A single
design with all eight `INIT`s flipped would be one P&R cheaper and strictly weaker: if
two FFs' bits were swapped in the database, a grouped pair would still show every
predicted bit moving and every mover predicted. Isolation per FF is what makes a
mis-attribution show up as FN + FP.

## 3. Semantic assertions

Every 1.4 prediction preregisters one `member_identity` assertion resolved by RFC 6901
pointer into the feature endpoint's pinned attestation. `readback_ff.tcl` currently
resolves the FF's data-source edge, which is what `clb_mux` needed; this class needs the
FF's own configuration read back instead:

| feature | attestation field | expected value |
|---|---|---|
| `<BEL>.ZINI` | `/resolved/ff_init/<BEL>` | `"0"` |
| `<BEL>.ZRST` | `/resolved/ff_srval/<BEL>` | `"0"` |
| `CEUSEDMUX` | `/resolved/ce_mode` | `"DRIVEN"` |
| `SRUSEDMUX` | `/resolved/sr_mode` | `"DRIVEN"` |
| `FFSYNC` | `/resolved/sr_kind` | `"SYNC"` |
| `LATCH` | `/resolved/storage_kind` | `"LATCH"` |
| `CLKINV` / `NOCLKINV` | `/resolved/clock_mode` | `"CLKINV"` / `"NOCLKINV"` |

These say what the producer claims the frozen name means; the pinned readback makes the
basis auditable. **It is not a silicon-behaviour claim** — nothing in this line has been
on a board, and a semantic failure never touches the address decision.

## 4. Completeness, decision and what would make the gate refuse

- every one of the 176 committed keys reported exactly once, or nothing is emitted;
- `tp_count == 154` (the committed holdout count), `fn_count == 0`, `fp_count == 0`;
- FP is the fixed 1.4 profile rule — `ownership_unknown ∪ unattributed ∪ {db_attributed
  in an asserted tile claimed by this class and outside every preregistered scope}`,
  counted once per `(pair, address)`;
- every pair's five-bucket partition exact; observation consistency global;
- `coverage.attested_count = 176`, `class_entry_count = 176`.

`gate_emit_ff.py` refuses to emit if any of the 176 frozen entries has no key, if any
rule is not single-bit, or if a computed address disagrees with the normative arithmetic
of `docs/freeze_format.md` §5. `gate_measure_ff.py` refuses to score unless the
predictions file still hashes to the committed value. `gate_certify_ff.py` refuses to
emit if any committed holdout key would go unreported.

## 5. Risks, stated before they can be excused afterwards

1. **FP=0 across 168 pairs is the hard part**, not the addressing. `LATCH` and `clkinv`
   change what the slice needs from the clock and control routing; the lutram round
   already proved that a keeper site valid in one mode can be **illegal** in another
   (`RAM256X1S` occupying `A5LUT` broke a keeper that worked for six other modes). Every
   mode must be built before any of them is trusted, and the keeper may have to differ
   per mode. If it does, that is a specimen-plan fact and belongs in the commitment.
2. **`ZRST` may not be reachable by `FDRE`→`FDSE` alone.** It is a different primitive,
   not a property, so Vivado re-synthesises; the LOC/BEL constraints should hold the
   placement, but if routing moves, the diff grows and the FP rule bites.
3. **`LATCH` changes the primitive to `LDCE`**, which has no `CE`/`R` in the same shape.
   The control-set bits of that variant will differ from B by more than the `LATCH` bit;
   those movers are `db_attributed` **and** claimed by this class **and** outside the
   pair's single preregistered scope, which makes them FP by the 1.4 rule.

   > **MEASURED 2026-08-04 — `docs/ff_latch_probe.md`, two results.** The concern was
   > real and the fix is a baseline, not a scope; and the topology of §2 turns out to be
   > impossible for this one variant.
   >
   > *The isolation.* `fdre → ldce` leaves two same-class movers (`FFSYNC` 1→0,
   > `CLKINV` 0→1) and FP=2; matching the reset kind leaves one, `CLKINV`, FP=1;
   > matching the reset kind **and** the clock polarity (`FDCE` with `IS_C_INVERTED` →
   > `LDCE`) leaves **only the `LATCH` bit, FP=0**. Two control pairs attribute each
   > removed mover separately. `LATCH` = `30_32` moves **0→1** into the latch, as
   > preregistered.
   >
   > *The topology.* **A slice cannot hold eight latches.** `A5FF` and its siblings are
   > BEL type `FF_INIT` and Vivado refuses `LDCE` on them outright; the eight-element
   > FDCE baseline builds fine, so the restriction is specific to latch mode. The
   > `LATCH` pair is therefore a **four-element** pair on `AFF..DFF`, and the formal
   > four-element pair reproduces the single-FF result exactly: raw 6, one mover, FP=0.
   >
   > The resulting change — `latch` redefined to four `LDCE`, one new `latch_base`
   > specimen per site instance, pairs and predictions unchanged at 168 and 176 — is
   > written up there and is **not applied**: the variant list is fixed only once the
   > author confirms the exploration.

   > **Ruled 2026-08-04: `LATCH` stays in the key space, and its scope is not guessed.**
   > Before the commitment, the `LATCH` pair is explored **on the mine site only**
   > (`SLICE_X2Y25`, whose evidence is already spent and cannot score). The first
   > design attempt is a **control-matched baseline** — a baseline built so that the
   > only difference from the `latch` variant is the storage kind, rather than the
   > default B reused unchanged. If that reduces the pair to the single `LATCH` bit, the
   > plan is unchanged. If same-class movers remain, they are **reported back and
   > preregistered feature by feature**, never absorbed into a widened scope on
   > suspicion. Dropping `LATCH` and certifying 175 is explicitly refused: a class
   > certificate that quietly omits an entry is not a class certificate.
4. **8 site instances × 15 P&R is 120 Vivado runs.** Nothing about that is risky, but a
   failed run in the middle must not tempt anyone to certify the subset that worked —
   hence the all-or-nothing completeness rule above.

## 6. The committed artifact, and how to re-read it

```sh
sha256sum gate_runs/run_2026_08_05_ff/predictions.json
git show 2b40693:gate_runs/run_2026_08_05_ff/predictions.json | sha256sum
```

The committed `gate_predictions` **1.5.0** record contains **184 specimens, 176
predictions, 154 holdout, 168 committed endpoint pairs**, sha256
`5440ef27acbd5b4f624cae54f4ffad89b3f656c1e6e5fa35b29226ff0d1b2e51`. Both commands
above must print that value. A different plan is a different run, not an amendment to
this commitment.

**The post-hold test transition is done.** One pre-freeze case expected an emitter
write into `gate_runs/` to be refused while the hold was true; after `c45e76e` that
premise is intentionally false, and running it unchanged would have created
`gate_runs/ff_hold_probe/` before failing. The refusal is still tested — the child
process sets `PREREGISTRATION_HOLD` back to `True` and runs the shipped `main()`, so
the guard itself is exercised rather than a copy of it — and a stronger case replaces
what the flag used to give: **the emitter must reproduce the committed bytes exactly**,
sha256 `5440ef27…`. Both were confirmed to fail for the right reason by mutating the
emitter (a one-character seed change; the guard deleted). Suite: **136 tests**.

`tests/test_ff_plan.py` checks on the freeze, not on prose: all 176 entries asserted
exactly once, every rule single-bit, every address equal to the normative arithmetic,
every transition the complement of its asserted value, the eight negated tokens exactly
the `NOCLKINV` features, the complementary pair sharing one address across two
specimens, one endpoint pair per feature, the exact 1.5 prediction and
comparison-endpoint contract, 168 canonical accounting pairs, and 176 directed feature
observations.

`gate_measure_ff.py` and `gate_certify_ff.py` are written and will not run until
specimens exist. Both refuse rather than improvise: measure refuses to score if the
predictions hash moved, certify refuses if any committed key is unmeasured, if a
measured key was never committed, if a measured projection differs from the
preregistered one, or if any holdout key would go unreported.

**Semantic isolation is enforced structurally, not by convention.** The measurement
keeps two lists — `address_problems`, which sinks the address decision, and
`semantic_findings`, which never can — and `address_decision()` takes only the first,
so a naming claim cannot be passed into it by accident. The certifier reads
`address_problems` alone for the same reason. Semantic pass is the verifier's own rule,
`transition_exact and attestation_basis_consistent`: a semantic claim about a specimen
whose addressing did not match names a member the evidence did not select, and
`host/verify_certificate.py` rebuilds that boolean and rejects a record that disagrees.
A semantic-only failure therefore certifies as `status: passed`,
`semantic_status: failed`, exit 0, with the failure count printed prominently. The fourth tool —
`gate_build_ff.py`, the Vivado-facing one — is deliberately **not** written yet: its
variant list is exactly what §2 and the rulings below decide, and writing it first would
put the plan in two places.

## 7. Rulings (author, 2026-08-04)

1. **Split: 22 / 154.** `mine = {SLICE_X2Y25}`; instance 6 stays holdout — a keeper does
   not disclose its own FF bit mapping.
2. **Coverage must be the full 176.** A subset may not be presented as the class being
   certified, so `attested_count = class_entry_count = 176` is a condition of emitting
   at all, not a target.
3. **`LATCH` stays**, explored on the mine site only before the commitment, with a
   control-matched baseline tried first; remaining same-class movers get preregistered
   feature by feature. No guessed scope, no dropped entry. (§5 risk 3.)
4. **The twelve directional predictions stand as written** — they are explicit,
   refutable hypotheses, and softening them would remove the only thing a bitstream
   could contradict.

The second, independent blocker raised on 2026-08-04 — **the comparison endpoint was not
part of the commitment** — is **closed**. `docs/round10_handoff.md` shipped schema
1.5.0: `comparison_specimen_id` is required and locked in advance, the verifier rebuilds
the whole pair set and the in-scope union from the commitment, and substituting a
baseline *together with* its accounting record still fails. The producer half now emits
and reads it, and the variant list above is the one frozen in `2b40693`.

Pre-registration is **complete**. The author approved the freeze, `c45e76e` records the
one-line hold release, and `2b40693` records the artifact. The next task is a complete
184-specimen builder implementing this fixed plan; the existing `gate_build_ff.py`
remains the mine-site LATCH probe and must not be mistaken for that builder.
