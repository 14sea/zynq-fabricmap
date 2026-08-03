# Round 9 request — how a class with two assertion shapes gets certified

> **RULED 2026-08-03 — see `docs/round9_ruling.md`.** Candidate **B** was adopted
> (one feature namespace + verifier-derived group consistency, certificate 1.4);
> candidate A is the rejected alternative and its A-only fixtures are out of scope.
> The vacuity/counting rules and the FP definition were accepted as requested, with
> the per-run declared-FP fallback refused. This document is kept as the record of
> what was asked and why, not as a spec.

Producer → author. `clb_ff_config` is inventoried, isolated and really diffed, but
pre-registration is **on hold** until this is settled, because 1.3's single
`evidence_model` selector determines the commitment key, the completeness rule and the
coverage denominator. Those cannot be reshaped after the pre-registration hash is
committed — the ordering is the evidence.

Nothing below needs Vivado or producer source. Every number is recomputed from the
frozen data in `data/` plus the class record in `data/MANIFEST.json`.

**This is the fifth draft.** Twelve review findings so far, none of them cosmetic;
findings 5–7 were factual errors in the producer's own numbers, and 9–10 were the same
unproven assumption surviving in prose the erratum sits directly above:

1. (draft 1) The vacuity argument was scoped to singleton and complementary groups. The
   correct criterion is **unique codewords**, which makes `group_exclusivity`
   unfalsifiable for **all 170 `clb_mux` groups as well** — so this request also carries
   an erratum against an already-certified class and against `docs/mux_groups.md`.
2. (draft 1) Replacing the 1.2 diff fields with the shared five-bucket partition left
   the feature model's TP/FP/FN undefined. That now has its own section.
3. (draft 2) The three falsifiability levels were presented as separately scorable.
   **Level 3 entails level 2**, so counting both counts one observation twice. Only
   level 3 may enter `address_pass`; level 2 is a diagnostic.
4. (draft 2) The mixed model was presented as forced by the shape of the data. It is
   not. The argument that the feature model cannot hold `CLKINV`/`NOCLKINV` was simply
   wrong, and with it removed a **simpler candidate** stands up. This draft asks the
   author to **rule between two candidates** rather than to ratify one.
5. (draft 3) The `in_scope` owner rule demanded exactly one owning result, which would
   have rejected run B: both endpoints of a pair legitimately cover a moved bit, and all
   24 of run B's movers have two owners.
6. (draft 3) `clb_mux` has **74** multi-bit scopes, not 72; 72 is the count that is also
   multi-member, which is the actual differentiator between the models.
7. (draft 3) "682 forbidden patterns" quietly assumed all-zero is a legitimate unset
   state. The raw figure is **844**, and the exemption is a policy assumption the frozen
   DB does not establish. Now an open question below.
8. (draft 3) The pointer in `docs/round6_request.md` still announced a mixed model.
   Rewritten neutrally.
9. (draft 4) `docs/mux_groups.md` still called 89,331 unmatched evaluations "the normal
   unset state", and the erratum repeated it. The scan shows only that no listed codeword
   matched; the frozen DB gives no way to read that as unset, inactive or safe.
10. (draft 4) `decode_groups.py` said "zero means the group is unset". The legacy `unset`
   field means **unmatched** and carries no safety semantics; the name is kept only for
   compatibility with the committed scan artifact.
11. (draft 4) "the same codeword twice, i.e. two identical features" → **two distinct
   feature names carrying identical codewords**, which is what such a collision would
   actually be. None exists in either class.
12. (draft 4) The fixture list had exactly one positive and it was the mixed one, so
   candidate B would have gone unexercised even if B were ruled for. A positive is now
   required for whichever candidate is chosen, and the A-only negatives are marked.

## The class as the freeze describes it

`clb_ff_config` is 176 entries, **every one a single-bit feature**. Grouping them by
polarity-free coordinate set — the 1.3 rule, bits not names — gives:

```
176 entries -> 168 bit-set groups
                160 singleton groups   (160 entries)
                  8 two-member groups   (16 entries)  all CLKINV / NOCLKINV
```

Structural breakdown, for the pre-registration plan:

| shape | entries | features |
|---|---|---|
| per-FF | 128 | `[A-D]5?FF.{ZINI,ZRST}`, 8 FFs × 2 slices × 2 features × 4 tile types |
| per-slice, singleton | 32 | `CEUSEDMUX`, `FFSYNC`, `LATCH`, `SRUSEDMUX` (8 each) |
| per-slice, complementary pair | 16 | `CLKINV` / `NOCLKINV` (8 groups), the only negated tokens in the class |

## What is ruled out, and what is not

**Ruled out: certify all 176 as 168 groups.** `group_exclusivity` is a tautology for
every group in this class — and in `clb_mux` too (next section). That route puts two
address assertions on every group, 336 in a fully reported run, of which **168 could not
have failed**, while dropping the feature model's TP/FP/FN falsifier and its
`unattributed_diff` discipline. Larger-looking certificate, strictly less evidence.

**Ruled out: two separate certificates.** Whichever one fails can be withheld and no
verifier could tell, because neither would know the other was owed.

**Not ruled out — and an earlier draft of this request wrongly said it was.** That draft
claimed the feature model cannot hold `CLKINV`/`NOCLKINV` because "a certificate could
report both as passing on the same specimen". That is wrong, and the mistake matters
because it was the whole argument for a new evidence model. `CLKINV` and `NOCLKINV`
passing **in different specimens** is two states of one bit correctly certified, not a
composition error. Within **one** specimen they cannot both pass unless the certificate
reports two different observed values for the same absolute address — which is a
**contradiction in the record**, catchable by an invariant, not by a model.

So the requirement that argument was reaching for is:

> **Observation consistency.** For any `(specimen_id, absolute address)`, every result
> that reports an observed value must report the **same** value. The verifier recomputes
> this across all results and rejects the certificate otherwise.

That invariant is needed under either candidate below, and neither candidate is
established by the shape of the data alone.

## Two candidates — the author's ruling is requested

| | **A — `evidence_model: mixed`** | **B — one feature namespace + verifier-derived group consistency** |
|---|---|---|
| key space | two: `(specimen, feature)` and `(specimen, group)` | one: `(specimen, feature)`, 176 entries |
| new schema surface | a third evidence model, cross-namespace disjointness, per-namespace completeness, conjunctive status | additive verifier duties on 1.3; no new model |
| complementary pair | a first-class asserted group | **derived by the verifier from the frozen DB**, never producer-asserted |
| "half a certificate" hole | closed by cross-namespace completeness | does not exist — one namespace to complete |
| observation consistency | required | required |
| five buckets + new FP rule | required | required |
| semantic `member_identity` | inside the group namespace | reported independently, same isolation |

**Candidate B in full**: all 176 entries go through the feature namespace; the verifier
additionally (i) enforces observation consistency as above, (ii) derives from the frozen
DB which features share a coordinate with opposite polarity and recomputes the resulting
decode — so the complementary relation is a *derived* check the producer cannot assert
its way past, (iii) reports semantic member identity independently of the address
decision, and (iv) uses the shared five-bucket accounting and whichever FP definition is
settled below.

**Producer's leaning, with the reason, not as a conclusion:** B, for this class. The
group model's extra content over the feature model is `scope_assignment` across a
**multi-bit** scope. Every group in `clb_ff_config` is **one bit wide**, so for all 168
of them the group assertion and the feature assertion are the same statement about the
same bit. Recomputed across the frozen subset:

| class | entries | groups | multi-bit scopes | of those, multi-member | where the two models actually differ |
|---|---|---|---|---|---|
| `clb_ff_config` | 176 | 168 | **0** | 0 | nowhere |
| `clb_lutram` | 42 | 36 (30 singleton + 6 complementary pairs) | **0** | 0 | nowhere |
| `clb_mux` | 500 | 170 | **74** (8×3b, 14+50×4b, 2×5b) | **72** | the 72 |

The two counts are deliberately separate: `clb_mux` has 74 multi-bit scopes, but 2 of
them are **singletons on 5 bits**, where a group assertion again says exactly what a
feature assertion says. The 72 multi-bit **and** multi-member groups are the only place
in the frozen subset where the two models genuinely differ. (An earlier draft wrote 72
as the multi-bit count while listing the 5-bit pair in the same parenthesis — the 72 was
the right differentiator with the wrong label.)

`clb_lutram` — the next class in the queue — has the identical shape to
`clb_ff_config`, so a decision made here applies to it. Adopting A would therefore add a
model for a distinction that does not arise in either remaining content class.

The counter-argument the producer can see for A: `clb_mux` proves multi-bit groups do
exist in this fabric, `int_pip` is not yet inventoried at group level, and a model added
now is cheaper than a schema migration later. The producer does not think that outweighs
the above, but it is the author's call, and the request below specifies A completely so
that ruling for it costs nothing.

## Candidate A in full — `evidence_model: mixed` in certificate 1.4

One certificate, **one commitment, two result namespaces, one partition, one
conjunctive address decision.** Concretely:

1. **Single `prediction_commitment`.** One `gate_predictions` artifact, one seed, one
   `split_policy`, carrying both `predictions[]` (feature shape, as 1.2) and
   `group_predictions[]` (group shape, as 1.3), with `totals` counting each namespace
   separately *and* the union. Its sha256 is committed before any bitstream exists, as
   now. Two commitments would reintroduce the withholding hole.

2. **Both key spaces stay authoritative and stay disjoint.**
   `(prediction_specimen_id, feature)` keys `feature_results[]`;
   `(prediction_specimen_id, group)` keys `group_results[]`. Duplicates within a
   namespace are already rejected; 1.4 must additionally reject **cross-namespace
   double claiming**: the set of class entries claimed by the feature namespace and the
   set claimed by the group namespace (a group contributes every member of its complete
   scope) must be disjoint. A feature belongs to exactly one namespace, and which one is
   fixed at pre-registration.

3. **One split, over specimens.** `mine` / `holdout` is a partition of the specimens in
   the single commitment; every result in either namespace inherits its specimen's
   split. A certificate where the same `specimen_id` carries different splits in the two
   namespaces is malformed. Holdout completeness is then checked per namespace against
   the same commitment: every committed holdout `(specimen, feature)` **and** every
   committed holdout `(specimen, group)` pair reported exactly once. Reporting one
   namespace in full and the other partially is the failure this rule exists to catch.

4. **Coverage is a union over class entries, never a sum of records.** Numerator is the
   size of the set of distinct manifest class entries claimed across both namespaces —
   a feature result contributes 1, a group result contributes every member of its
   complete frozen scope. Denominator stays the manifest class entry count (176). The
   verifier must recompute both from the frozen DB and the results; `attested_count` in
   the record is a summary, like every other producer count since round 8. Summing
   records would report 168 for a run covering 176 entries, or 176 for one covering 160.

5. **The address decision is the conjunction.** `status: passed` requires the feature
   namespace's `tp/fp/fn` verdict to pass **and** both group address `fail_count`s to be
   zero **and** both completeness checks to be exact. There is no per-namespace status
   that can pass on its own. Report the per-namespace counts, decide on the conjunction.

6. **Semantic stays independent**, exactly as 1.3: recomputed from `netlist_basis`,
   reported in `semantic_status` / `semantic_accounting`, never folded into the address
   decision, verifier exit 0 on a semantic-only failure with the counts printed loudly.

7. **One diff partition per variant pair, consumed once.** This is the sharpest
   collision between the two models, and the one most likely to be got wrong: 1.2 books
   the raw diff as `observed_diff` / `excluded_diff` / `unattributed_diff` with a
   `frame_ecc` exclusion rule, while 1.3 books it as the five identity-bearing buckets
   in `pair_accounting[]`. A mixed run has pairs that move bits belonging to both
   namespaces. Requested: **in mixed, the five-bucket `pair_accounting[]` is the single
   bookkeeping for every pair**, each pair recorded exactly once, and `in_scope` is
   computed against the **union of both namespaces' asserted scopes** for that pair.
   Otherwise a feature-namespace bit that moved lands in `db_attributed` — true, and
   silent — while its own assertion is never checked against it. Whether the 1.2 diff
   fields are then forbidden or kept as derived duplicates is your call; if kept, the
   verifier must recompute one from the other rather than accept both.

## Open: how feature TP/FP/FN is recomputed from the shared partition

Point 7 replaces the 1.2 diff fields, and 1.2's falsifier is defined **on those fields**
(`fp_count = unattributed changed-bit observations`, where `unattributed_diff[]` is
every changed address absent from the prediction). Dropping them without redefining the
falsifier would leave the feature namespace with no FP at all. The producer will not
pre-register until this is nailed down, so: here are the three questions, the producer's
recommendation for each, and the reason none of them is settled by existing evidence.

**(a) Which buckets are false positives?** The two models disagree today, and the
disagreement is real, not cosmetic:

| bucket | 1.2 feature model | 1.3 group model |
|---|---|---|
| `in_scope` | predicted → not FP | asserted → not FP |
| `frame_ecc` | excluded by rule | excluded by rule |
| `db_attributed` | **FP** (absent from the prediction) | tolerated — run B passed with 328 |
| `ownership_unknown` | **FP** | alarm bucket; blocks a tile-wide claim |
| `unattributed` | **FP** | alarm bucket |

Run B's 328 `db_attributed` bits are INT routing changes, correctly attributed to
`segbits_int_*.db`, and a strict-1.2 reading would have failed that run. Run A never
exercised the question: `LOCK_PINS` LUT-INIT pairs change nothing outside the prediction
except ECC. So the strict rule has never been tested against a *legitimate* out-of-class
change, and adopting either model's answer wholesale is a decision, not a deduction.

**Producer recommendation:** `FP = ownership_unknown ∪ unattributed ∪ {db_attributed
bits whose claiming feature belongs to this bit class, in a tile this run asserts over}`.
Rationale: the certificate claims *this class's* rules predict where this class's bits
move. A changed bit that our own class claims, in a tile under assertion, and that no
result predicted, is a prediction miss and must count. A bit claimed by another class's
DB (INT routing) is outside the claim and must not. This keeps 1.2's strictness where
1.2's strictness was actually about something, and keeps run B legal.

**(b) A legitimate group-scope change must not pollute the feature account.** Under
candidate A, with `in_scope` computed over the union of both namespaces (point 7) and
the namespaces disjoint (point 2), an in-scope bit is covered by an assertion in exactly
one namespace, so a group-scope mover can never be an FP for the feature namespace.

**Requested rule:** every bit listed as `in_scope` for a pair must be **covered by at
least one preregistered scope belonging to that pair**, recomputed by the verifier from
the frozen DB; a bit covered by none is mislabelled and the certificate is rejected.

**Not** "exactly one owning result" — an earlier draft asked for that and it is wrong.
A pair is two endpoint specimens asserting the same group or feature, so both endpoints
legitimately cover the moved bit. Measured on the certified artifact: all **24** of run
B's `in_scope` movers have **two** result owners, one per endpoint, in every one of the
12 pairs. A uniqueness-at-result-level rule would reject the very run it was written
against. Uniqueness belongs at the level of the namespace / class entry — one class
entry is claimed by exactly one namespace (point 2) — and never at the level of results.

Under candidate B the question mostly dissolves: one namespace, so `in_scope` is just
the union of predicted addresses. What remains wanted in both is the coverage direction
of the check (no `in_scope` bit without a paired preregistered scope) plus the
observation-consistency invariant, which is what actually catches two results
contradicting each other on one address.

**(c) When one pair moves bits belonging to several results — under A, in both
namespaces — what is the TP/FN observation set?**
Producer recommendation: **decouple TP/FN from the diff entirely.** A feature result's
TP/FN is decided only by comparing `observed_assignments[]` — read at that result's own
predicted addresses in its own variant specimen — with the preregistered expectation. A
group result's outcome likewise depends only on its own complete scope. A shared pair
then changes nothing about either, because the address sets are disjoint by (b). FP
stays a **pair-level** quantity, computed once over the union, with a nonzero FP set
failing the run.

This does change 1.2's wording — TP is currently "complete prediction matched **with no
unattributed diff**", i.e. a per-result condition carrying a pair-level fact — and one
stray bit would then sink every result sharing that pair. That is true under either
candidate: B has many feature results per pair just as A has results from two namespaces.
It does not weaken the pass condition: `fp_count == 0` is required anyway, so a run with
any FP fails either way. What it buys is that the failure is reported at the level where
it happened.

Supporting fact for whichever rule is chosen: FF `INIT` variants are generated from one
P&R, so feature-namespace pairs in this run have **zero routing change by construction**
— an `INIT` 0↔1 flip moves exactly one bit plus frame ECC. The strict reading is
affordable here; that is not an argument that it is right in general, and the producer is
not asking for a rule tailored to a run it has already measured.

All three questions apply to candidate B unchanged: B keeps the shared five-bucket
accounting, so it needs the same FP definition. Only (b) simplifies, because there is
one namespace to own a bit.

If you would rather not settle (a) in the schema, the fallback the producer can pre-register
against is an explicit per-run declared FP set, named in the commitment before any
bitstream exists and recomputed by the verifier from the buckets. That is weaker — it
lets the producer choose its own strictness — but it is at least chosen in advance and
on the record, which a silent default is not.

## `group_exclusivity` is a tautology for every group we have — including `clb_mux`

**This supersedes an earlier, too-narrow version of this request** that claimed vacuity
only for singleton and complementary groups. The general criterion is
**unique codewords**, and it applies to the already-certified class.

By the 1.3 definition, a group is the maximal set of features sharing one polarity-free
coordinate set, so **every member's rule is a full 0/1 codeword over the same complete
scope** (verified: no member of any group in either class has a token outside its
group's scope). Assert-iff means "observed assignment equals this member's codeword".
Therefore, if the members' codewords are pairwise distinct, **at most one can match any
observed assignment whatsoever** — the assertion is satisfied by every possible
bitstream. Two members could both decode only if the DB listed the same codeword under
**two distinct feature names**; no such collision exists in either class.

Recomputed from the freeze:

| class | groups | all-codewords-unique | `group_exclusivity` falsifiable |
|---|---|---|---|
| `clb_ff_config` | 168 | 168 | **0** |
| `clb_mux` | 170 | 170 | **0** |

`clb_mux`'s group sizes are 96×1-member, 8×4-member, 14×5-member, 50×6-member and
2×1-member-on-5-bits. Size does not help: a 6-member `AFFMUX` on a 4-bit field lists six
distinct patterns, so two of them can never match one observation. **The rule is not
weak for big muxes, it is unfalsifiable for all of them.**

### What is actually falsifiable, in three levels

Decomposing the group check by what a bitstream could refute:

| level | statement | falsifiable in isolation when | `clb_mux` | `clb_ff_config` |
|---|---|---|---|---|
| 1 exclusivity | at most one member matches | codewords collide | never (0/170) | never (0/168) |
| 2 decode-validity | the observed pattern is *some* listed member | the group is not a complete cover | 170/170 | 160/168 |
| 3 codeword equality | the observed pattern equals the **preregistered** member's codeword | always | 170/170 | 168/168 |

**The three levels are not additive, and only level 3 may be counted.** Level 3 entails
level 2: an observation equal to the preregistered member's codeword is a listed member
by construction. Scoring both would count one observation twice — the same defect as the
vacuous exclusivity pass, one step subtler, and an earlier draft of this request asked
for exactly that. Level 1 is unfalsifiable and level 2 is entailed, so the entire
address evidence of a group result is **one** falsifiable statement: level 3.

Level 2 keeps real **diagnostic** value and should be reported, never counted: when
level 3 fails, level 2 says *how* — the observation landed on another listed member's
codeword (an addressing or grouping error) versus on an unlisted pattern (a decode or
arithmetic error). That distinction is worth having in a failure record and is worth
nothing in a pass count.

The complete-cover figures still matter for a different reason: the 8 `CLKINV|NOCLKINV`
groups list 2 of 2 patterns, so nothing about them is diagnosable at level 2 either,
while all 170 mux groups are proper subsets — **844 patterns across them are listed by
no member**, which is the part of the frozen model a bitstream could contradict.

**Open, and please rule on it: what the all-zero pattern means.** Of those 844, **162
are the all-zero pattern** of a group whose members do not include it; 8 mux groups list
all-zero as a genuine member. Treating all-zero as "this mux is unset, and that is safe"
drops the count to 682 — and an earlier draft of this request quoted 682 as if the
frozen DB established it. **It does not.** prjxray's segbits files say which patterns
name a member; they say nothing about what an unnamed pattern does to the silicon, and
nothing about all-zero being benign. The same assumption is what makes `clb_ff_config`
and `clb_lutram` look like they forbid nothing: their raw unlisted counts are **160** and
**30**, every one of them the all-zero/unset pattern of a one-bit group.

Two ways out, either acceptable, and the producer prefers the second:

- state "all-zero = unset = safe" as an **explicit, labelled policy assumption** in the
  schema doc, not derived from the freeze, so that anything relying on it is visible; or
- **do not make the assumption at all**: require a listed codeword only for groups the
  pre-registration declares *selected*, or that a write actually touches. Then the
  question of what an untouched, unlisted pattern means never has to be answered, and no
  count depends on it.

1.3 already contains level 3 inside `scope_assignment` ("every complete-scope observed
value equals its preregistered value, and that value pattern encodes a frozen member"),
which is why the certification decision does not change. What must change is the
counting, and the claim the count is presented as.

### Requested rule

The verifier recomputes falsifiability **from the frozen DB alone**, before looking at
any observation: an assertion satisfied by every possible assignment of its group's bits
is `vacuous`. It must be labelled so in the record and **must not be counted in
`address_pass`**. Emitting it as a plain pass is a defect regardless of intent — the
producer did exactly that in run B without noticing.

Level 2 should be split out of `scope_assignment` as a separately **reported diagnostic
outcome**, explicitly outside `address_pass`, so that a complete-cover group cannot
inherit a falsifiable-looking label and so that no implementation can read the split as
licence to add it to the count.

### How the existing 1.3 certificate corrects its counts

Run B (`clb_mux`, `gate_runs/run_2026_08_02_b/certificate.json`) has 24 group results,
16 of them holdout, × 2 address assertions = **32/32 address pass**. Sixteen of those
are `group_exclusivity` and are tautologies. The corrected reading is:

```
address, falsifiable   16/16   (strict codeword equality — level 3)
address, vacuous       16      (group_exclusivity — reported, not counted)
decode-validity        16      (level 2 — diagnostic, entailed by level 3, not counted)
semantic               16/16   (member_identity, independent as before)
```

**The decision does not change: `clb_mux` remains certified, status passed, zero
failures.** What changes is that the headline "32/32" overstated the evidence by exactly
2×. `data/MANIFEST.json`'s `clb_mux` record inherits it as
`address_accounting.group_exclusivity.pass_count: 16`, which is the field that would
have to become a vacuous count. Requested: 1.4 defines the corrected accounting, the
producer re-emits run B's certificate under it (same predictions, same measurement, same
specimens — recounted only), and the erratum is written down rather than silently
recounted.

The producer-side claim in `docs/mux_groups.md` — "zero violations in 281,700 group
evaluations" — is affected the same way and worse: `scripts/decode_groups.py` counts a
violation as `len(matched_members) > 1`, which the codeword argument shows is
structurally impossible once groups are derived by bit set. That scan's zero is a
tautology, not evidence. Its non-vacuous content is the decode census it also recorded
across the same 281,700 evaluations — 23,910 groups decoded to exactly one listed
member, 257,790 matched no listed codeword at all. Note what that census does *not* say:
it does not say those 257,790 groups are *unset*, inactive or safe — only that no listed
codeword matched, which the frozen DB gives no way to interpret further. So they refute
nothing, and they establish nothing either. Level 2 only bites where the pre-registration
claims a group *is* selected, which is the gate, not the scan. An erratum is being added to that
document in the same commit as this request. The name-derived comparison in the same
document is unaffected: name-grouped "members" do **not** share a scope, which is
precisely why that variant could and did produce 160 real violations.

## Fixtures requested

**Positive — one is required for whichever candidate is ruled for, not only for A.**

- *If A:* one conforming mixed pass — both namespaces complete, partition exact,
  coverage union equal to the claimed entry set.
- *If B:* one conforming single-namespace pass — 176 entries in one key space,
  observation consistency satisfied, the 8 complementary relations **derived by the
  verifier** and reported, partition exact, coverage equal to the claimed entry set.

A previous draft asked only for the A positive, which would have left B unexercised even
if B were chosen.

Negative, in the order they matter. Items **1–3, 6 and 8 are candidate-A-conditional**:
they exist because A has two namespaces, and under B they are unreachable by
construction rather than caught by a rule — which is itself part of B's case. Items
**4, 5, 7, 9 and 10** apply under either.

1. *(A only)* **Half a certificate.** `feature_results[]` complete and passing,
   `group_results[]` omitted entirely (or truncated to the passing groups), everything
   else self-consistent. Must FAIL on holdout completeness against the single
   commitment. This is the fixture the two-namespace design has to earn.
2. *(A only)* **Cross-namespace double claim.** `CLBLL_L.SLICEL_X0.CLKINV` reported as a
   feature result *and* as a member of the reported group's scope. Both records
   individually valid. Must FAIL.
3. *(A only)* **Coverage double count.** The 8 group results counted as 8 toward a
   numerator that also counts their 16 members — or the reverse, a numerator summing
   records to 168 over a denominator of 176 while claiming full coverage. Must FAIL,
   recomputed.
4. **Vacuous pass inflation, complementary group.** `group_exclusivity` reported as a
   holdout pass for a `CLKINV|NOCLKINV` group and counted in `address_pass`. Must FAIL
   (or be recomputed to `vacuous` and excluded — either is acceptable, silently counting
   it is not).
5. **Vacuous pass inflation, real multi-member mux — `AFFMUX`.** The same thing on a
   six-member group over a 4-bit field, taken from the certified run B data, where the
   assertion *looks* substantive. This is the fixture that decides whether the
   implementation used the general unique-codeword criterion or special-cased small
   groups; a checker that only recognises singletons and complementary pairs passes 4
   and fails here. Second variant of the same fixture: its level-2 decode-validity
   outcome reported **and added to `address_pass`** alongside level 3 (6 of 16 patterns
   are listed, so level 2 looks substantive here). Must FAIL — level 3 entails level 2,
   and counting both counts one observation twice.
6. *(A only)* **Cross-namespace FP pollution.** A pair where a group-scope bit moved,
   reported with `in_scope` computed from the feature namespace only, so the group's
   mover lands in `db_attributed` and is counted as a feature FP — and the mirror
   version, where it is silently absorbed and counted as nothing. Both must FAIL on the
   coverage recomputation in (b).
7. **Partition consumed twice.** One variant pair recorded in `pair_accounting[]` twice
   with its buckets split between the two records, `raw_diff_bits` still summing
   correctly. Must FAIL. Under B the split is between results rather than namespaces;
   the fixture is the same shape either way.
8. *(A only)* **Conjunction bypass.** Group namespace clean, feature namespace with one
   `fn`, and `status: passed` justified by a per-namespace status field. Must FAIL.
9. **Observation consistency, both directions.** Required under either candidate, and
   the pair that replaces the bad argument this request previously made.
   *Must PASS:* `CLKINV` passing in specimen X and `NOCLKINV` passing in specimen Y —
   two states of one bit, correctly certified. A verifier that rejects this is wrong.
   *Must FAIL:* two results in the **same** specimen reporting different observed values
   for the same absolute address. That is a contradiction in the record, and it is what
   "both members passed" would actually have to mean.
10. **Semantic-only failure.** `member_identity` wrong, every address assertion correct
   (under A, in both namespaces). Must **PASS** the address decision, report the semantic
   failure loudly, exit 0. Carried over from round 6 because neither candidate's dispatch
   may lose it.

## Measured shape, for reference

From the isolation work already done, not yet pre-registered: FF `INIT` is a cell
property, so one P&R yields many bitstreams. `INIT` 0↔1 moves exactly one bit
(`31_03` = `AFF.ZINI`) with zero routing change, and **the polarity is inverted** —
`INIT=0` gives bit 1. That is the Z in ZINI, and it is a *semantic* claim, not an
addressing one; it belongs in `member_identity`-class evidence, not in the address
decision. Tying `R` off flips the slice-wide `SRUSEDMUX` 1→0.

Expected run shape, under A: 160 feature-namespace entries and 8 group-namespace groups.
Under B: 176 feature entries with the 8 complementary relations derived. Either way, over
`CLBLL_L` / `CLBLM_L`, SLICEL and SLICEM, all four slice positions, with the split
drawn over specimens by the single commitment.

## What is blocked on this

`gate_emit_ff.py` is not written and **no pre-registration hash is committed**. The
producer will not emit a commitment until three things are settled, because each of them
is fixed permanently by the commitment:

1. **A or B** — the key space and the completeness rule differ between them, and the
   commitment fixes both;
2. the vacuity rule and the level-2/level-3 counting, since together they decide which
   assertions are worth pre-registering at all for the 8 complementary groups;
3. the FP definition in the open section above, since the falsifier cannot be chosen
   after the measurement.

Under B the pre-registration is materially simpler — one key space, 176 entries, no
cross-namespace bookkeeping — which is a reason to rule promptly, not a reason to rule
for B.

Independent of the answer, `clb_mux`'s corrected accounting can proceed as an erratum:
it is a recount of committed artifacts, not a new run.
