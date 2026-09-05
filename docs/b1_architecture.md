# B1 — autonomous cartography on the known 292 bits: architecture (v0.3, host-only, 2026-09-05)

> **Standing: host-only. Nothing here is frozen or ruled; no board contact is authorised.**
> Stage B1 of `docs/autonomous_cartography_roadmap.md`, built under the owner's ruling of
> 2026-09-05 (B1 to the pre-board package, DRAFT / NO BOARD RULING throughout). v0.2 is the
> rebuild after the owner's review of the first package (2026-09-05, FAIL: five blockers —
> `docs/b1_package.md` §0); the first image `7bc86a3f…` is WITHDRAWN / DEFECTIVE / NO-RUN.
> This document says what the B1 instrument IS; `docs/b1_carrier_contract.md` fixes the
> boundary that makes its measurement non-circular; `docs/b1_preregistration.md` says what
> it will be judged by; `docs/b1_package.md` is what the owner reviews before any board time.

## 1. The question, and the boundary that makes it "autonomous"

*Can the board recover, from its own probes and nothing else, a replayable map of the 292
certified `clb_lut_init` addresses — which LUT, which INIT position — and say how sure it
is, and what each entry rests on?*

**The autonomy boundary (roadmap §1).** The board is the sole executing authority for probe
choice and for the map: it decides which addresses to set in each probe, in what order,
when an entry is resolved, what confidence it carries, and what the map hash is. The host
is notary (it signs *writable* candidates — link 1 — and **nothing about what they should
read**: `docs/b1_carrier_contract.md`), auditor (it pulls every probe's raw words and
recomputes the three hashes), rel-v4 transaction endpoint and collector. After the session
the host **recomputes** the map from the readouts the records carry, as an audit; the
recomputation never reaches the board and never updates a map.

**Closed-book, not human-blind (roadmap §2 B1).** The ground truth — the certificate-derived
`local_map.json` (`56f2b9e8…`) — exists and its developer has read it. B1 claims runtime-blind
reconstruction *by the executable*: the cartographer is compiled with the 292 addresses in
genome-bit order (`P3_WHITELIST`) and the safety class, and with **no** LUT key, INIT index
or group table. That is a fact about bytes, guarded (§5), not a promise.

**The measurement is not pre-certified.** The first B1 package failed review because the
instrument's carrier compares every readout with the host-signed expected tables *before*
the cartographer sees it (`F_ARM_TABLE`), so every observation it could learn from had
already been checked against the ground truth. v0.2 runs on the **B1 carrier**
(`builds/b1/b1.bit` `d85daef4…`; `rtl/b1/`): the same authorisation gate (key, nonce,
SipHash tag), the same sweep, and the readout exposed **raw** — `SEMANTIC_GATE = 0`,
`tables_match` an observation that gates nothing. The **B1 signer** (`host/b1_sign_arm.py`)
signs `commit ‖ twelve ZERO table words ‖ nonce` and disarms the semantic oracle's entry
points in-process before signing; the **B1 host validator** (`host/b1_records.py`, rule
iii-B1) refuses any reply whose table words are not zero. Nobody attests semantics before
the measurement; the ground truth is used by the adjudicator alone, after the session.

## 2. What the board measures, and why the map is decidable from it

The instrument is the archived P3 stack (`zynq-psoracle` `689dde1`, read-only, bound by
hash before any import) minus its carrier and signer, which the B1 successors replace
(§1). For every candidate the PL's arm gate sweeps all 64 input vectors of the six
evolvable LUTs and latches the **functional readout** — six 64-bit truth tables, table *k*
bit *v* = LUT *k*'s output for vector *v* — which the application reads from the READOUT
registers and the record carries (`evidence.score.functional_readout`). The base is
all-zero, so the readout of a candidate that sets address *i* alone has exactly one lit
position, (LUT *k*, INIT *v*): **the address's functional relation is directly
observable**. That is what makes B1 a measurement of the fabric rather than a guess from
address structure — an address-only guesser cannot know *v* (§5). What the map records is
the observed transition (base 0 → set 1 at the lit position); it makes **no polarity
claim** (a derived word the first schema carried and the review struck).

## 3. The cartographer (`firmware/b1/b1_carto.c`, `carto-v1`) and the orchestrator

A pure unit, deterministic from (seed, budget, the observations), compiled into the image
and into a host twin; its Python reference is `host/b1_carto.py`; the RNG is the
instrument's (`l6_operators.Rng`: xorshift64, warm-up 4, rejection sampling).

| phase | probes | what it does |
|---|---|---|
| **A code** | 9 | address *i* carries the code *i*+1 (1..292, never 0); probe *p* sets every address whose code has bit *p*. After the ninth observation every lit position decodes to the address whose code it lit under — group testing, one sweep per code bit. Provisional (confidence 1, state `decoded`). Lit-count ≠ set-count, an out-of-range code, a double claim → anomalies, kept |
| **B confirm** | 292 | single-address probes in an RNG-drawn order (undecoded addresses first): exactly the decoded position lit → confidence 2, state `confirmed`, the record's seq kept as `confirm_seq`; nothing lit on an undecoded address → `no_effect`; anything else → `contradiction` (confidence 0) |
| **C pairs** | 32 | RNG-drawn pairs of confirmed addresses, half same-LUT, half cross-LUT: the readout must be the union of the singles; a deviation is an interaction edge |

Budget 333 = 9 + 292 + 32; a smaller budget cuts B and C where it runs out and every entry
says what it rests on. Every entry carries its evidence separately: the code-probe mask
(which of the 9 sweeps lit it), the confirmation seq, and whether a transition was
observed at all — a claim without an observed transition is an `unobserved_claim` and
scores as wrong.

**The orchestrator** (`firmware/b1/b1_orch.c`, reference `host/b1_carto.session_run`) owns
the session order the first image got wrong: the cartographer is **initialised and bound
before the opening baseline**, so the opening record's block commits to the bound empty map
(not to a zero struct); then the probes; an unscored candidate (any non-SCORED outcome)
**ends the epoch** — it is never re-issued and no closing baseline follows; the closing
baseline is issued only when the budget completes.

**Every record carries a `carto` block** (loop_record 1.2.0): the phase, the probes issued,
the anomaly count, a sample (≤ 8) of the entries this observation changed, and the
board's running commitment — **`content_sha256`** over the map's content (entries with
confidence / state / observed / code mask / confirm seq, pairs, anomalies, seed, budget,
code-probe seqs, version) and **`map_sha256`** over the whole rendering
`{"binding": {image_lo32, token, universe}, "content": {…}}`, which binds the map to the
session token, the universe digest compiled into the image and the low 32 bits of the
image the host loaded (identity page word 7). The content hash is predictable from the
plan (the prediction pins it); the whole-map hash is not, and is not predicted. The IDENT
(app_identity 1.4.0) names `carto-v1`, the universe digest `895baf85…`, the probe budget,
the carrier bitstream hash and the carrier **`VARIANT`** word the application read from the
PL (`0x42310001`; any other value is an IDENT finding and the session is refused).

## 4. The image — a versioned successor, not an edit of the instrument

`firmware/b1/` holds the instrument's `p3_derive`, `p3_rectx`, `p3_pull`, the BSP glue and
the linker script **byte for byte** (`IMPORT.json`, hashes = the archive's pin table, with
`p3_app.c` / `p3_wire.c` / `p3_wire.h` listed as *derived* into `b1_app.c` / `b1_wire.c/h`),
plus B1's own files: `b1_app.c` (the application with the search replaced by the
orchestrator + cartographer; records carry no `arm`; the VARIANT read), `b1_wire.c/h` (the
record and identity writers with the additive fields), `b1_orch.c/h`, `b1_carto.c/h`, and
`p3_data.h` generated by `host/gen_b1_data.py` from the phenotype manifest **without** the
operator block. Same wire protocol (rel-v4), same transactions and bounds, same watchdog,
same closing steps. Built by `firmware/b1/bsp/build.sh` with the instrument's toolchain
(read-only) and the 2025.2 embeddedsw BSP; two clean builds are byte-identical —
`evidence/b1/build_evidence.json` (image **`54b00663…`**, 114 708 bytes; the embeddedsw
inputs by hash; the compiler by hash). The binary is not committed (as the instrument's is
not) and is hash-checked by the runner.

**What does not transfer from the instrument:** its carrier's board-level guarantees (the
B1 carrier needs its own **qualification session** `B1Q` under its own ruling pair —
`docs/b1_carrier_qualification.md`; `host/b1q_runner.py`, `host/b1q_adjudicate.py` — before
any mapping session; its PASS is an evidence chain (`host/b1_qualification.py`: files by
hash, binding, re-adjudication) from which `carrier.qualified` is derived, and the mapping
runner and adjudicator re-verify that chain, never the flag); its L6 calibrations (a new image has its own
period); its `board_ready` mark. B1 needs the owner's compatibility review of this image
before any board session (package §7), and the runner refuses an image not marked
`board_ready` in `manifests/b1_manifest.json`.

## 5. The guards

| guard | where | what it proves |
|---|---|---|
| noninterference contract | `rtl/b1/b1_arm_gate.v` (`SEMANTIC_GATE = 0`), `host/b1_sign_arm.py`, `host/b1_records.py`; `tests/test_b1_carrier.py`, `test_b1_signer.py`, `test_b1_records.py` | the PL never gates on the readout; the signer signs zero tables and cannot compute expected tables (a call is a refusal); the validator refuses a reply with non-zero tables; the RTL diff to the instrument is the parameter and the read-only VARIANT register only; the benches ARM on zero-table payloads and refuse unsigned / replay / wrong commit / wrong key / no key |
| header without tables | `host/gen_b1_data.py`; `tests/test_b1_leakage.py` | `p3_data.h` is fresh from its generator and contains none of `P3_LUT_*`, `P3_MUTATION_BITS`, `P3_OPERATOR_DATA_SHA256`, LUT keys |
| source include scan | same test | `b1_carto.c/h` include only their own header and `p3_derive.h`; the app never references the search or arm names; the build compiles no search unit |
| binary scan | same test (when the image is present) | the image contains no LUT key, no `P3_LUT`, no arm name; it does contain `carto-v1` and the universe digest |
| verbatim imports | same test | every unmodified instrument file hashes to the archive's pin |
| permuted fixture | `host/b1_model.py`; twin + leakage tests | over a fabric with a seeded permutation of the truth, the cartographer outputs the permutation (292/292), not the truth (< 10/292): it measures |
| address-only baseline | `b1_model.address_only_baseline`; leakage test | what address structure alone predicts scores precision < 0.2 against the reference's 1.0 |
| C = Python | `tests/test_b1_twin.py`, `test_b1_session.py` | probes, record blocks, content and map bytes identical over truth / permuted / dropout / interaction fixtures, every budget phase, unscored probes; the session order (init → bind → opening → probes → closing; unscored ends the epoch) identical in C and Python |
| wire contract | `tests/test_b1_wire.py` | the image's own identity (1.4.0) and record (1.2.0 + carto) bytes pass the instrument's validator |
| autonomy replay | `host/b1_adjudicate.py` | after a session the reference, bound as the board was, fed the records' readouts, reproduces every probe the board chose and every record's content and map hash — the board followed the algorithm on its own observations and nothing else |
| fail-closed adjudication | `tests/test_b1_adjudicate.py` | one named check per preregistration condition, EXACT (`EXPECTED`), each with a negative test driven through `adjudicate()`; the plan, prediction and pin table re-verified inside `adjudicate()`; the binding refuses a wrong session / seed / image / prereg / manifest hash / instrument commit / carrier variant / carrier hash / a carrier without a standing qualification chain; a lying block field, a foreign probe, the init-order defect, a short run, a late span, a dropout fabric, an instrument finding, a forced schema finding, a missing validator are each named |
| qualification chain | `host/b1_qualification.py`; `tests/test_b1_qualification.py` | the carrier is qualified only by a B1Q record whose evidence files hash, whose binding is this manifest's carrier / image / prereg / seed, whose outcome is PASS and which re-adjudicates to PASS now; every break refuses |
| end-to-end modelled session | `host/b1_modelled_session.py`; `tests/test_b1_e2e.py` | the whole 335-record session through the instrument's real host stack (reader, console, notary relay with the B1 signer, collector, audit pulls of the candidates' real staging words) written as the runner writes it and adjudicated by the real validators: truth → PASS (335/335 audited, chain 336); permuted → HOLD; tampered served words → KILL falsified; a readout the block contradicts → named; a faulty channel still COMPLETED |
| pins | `host/b1_pins.py`; `manifests/b1_instrument_pins.json`; `tests/test_b1_pins.py` | every adjudication-critical fabricmap file by hash, verified by the runner before the port and by the adjudicator before any verdict; the table is not self-referential |
| map schema + semantics | `schemas/self_map_v2.schema.json`; `b1_adjudicate.schema_findings`; `b1_verify.semantic_findings` | the expanded board-authored map validates under a real JSON-schema validator (draft 2020-12); a missing validator is a finding, never a pass; the semantic rules require exactly the 292 pinned addresses once each, legal state / confidence / observation / evidence combinations, 9 distinct increasing code-probe seqs, 32 legal non-pending edges |

## 6. Adjudication (`host/b1_adjudicate.py`) and the map v2

Pins re-verified inside the adjudicator (plan, prediction, the pin table) → binding
(session B1, the plan's seed, the B1 image, the frozen prereg, **the manifest's own hash,
the instrument commit**, the IDENT's fields including the carrier hash and the VARIANT
word, the carrier's qualification chain re-adjudicated) → the instrument's validators through the B1
successor (`b1_records`: run-log validation with the audit gate, rule iii-B1, the
ALL-SELF-REPORTING policy, structural / baseline / REC / rel-v4 closure and controls, the
rate report, heartbeat and CRC / bad-frame budgets, the deadline; a `Falsified` of either
family is a KILL, any other rejection a HOLD) → COMPLETED at budget + 2 → the autonomy
replay (§5; **the probe sequence is a finding**, per record) → the verifier
(`host/b1_verify.py`) against the truth held back from the executable, every gate an EXACT
equality with the preregistered constants: precision, recall, claimed, unobserved claims,
**confidence snapshots** (the probe-9 map: confidence-1 accuracy 292/292; the final map:
confidence-2 accuracy 292/292 and no confidence-1 cohort; probes to full recall at
confidence ≥ 1 = 9 and to full confirmation = 301), the two **reporting strata** — stratum B = `CLBLM_L.SLICEM_X0.ALUT/DLUT`
(94 addresses, the LUTs not consulted while the cartographer was developed) and stratum A =
the other four (198) — interaction edges, anomalies → the per-record comparison with the
preregistered prediction (content and blocks). Two documents come out: the **board-authored
map** expanded to `self_map` 2.0.0 (`schemas/self_map_v2.schema.json`: relation, confidence,
state, observed transition, evidence provenance, interaction edges, binding — no LUT key, no
polarity, no ground truth; JSON-schema validated) and the **verifier report**
(`self_map_verifier_report` 1.0.0: the truth-side judgement), never merged.

## 7. What B1 does not claim

Nothing about unattested bits (the 1 756 named by the frozen DB): a later ruling. Nothing
about routing, FF or any other class. Nothing about map *utility* (B2) or the closed loop
(B3). Nothing about another die, Linux or the ICAPE2 path. Not a human-blind result (§1).
Not polarity (§2). The board's sample efficiency here (9 probes to a full provisional map)
is a property of an additive, single-position fabric — the very property that made round
1′ undecidable — and B1 measures it rather than assumes it (phase C, the anomaly counters).
