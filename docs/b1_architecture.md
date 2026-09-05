# B1 — autonomous cartography on the known 292 bits: architecture (v0.1, host-only, 2026-09-05)

> **Standing: host-only. Nothing here is frozen or ruled; no board contact is authorised.**
> Stage B1 of `docs/autonomous_cartography_roadmap.md`, built under the owner's ruling of
> 2026-09-05 (B1 to the pre-board package, DRAFT / NO BOARD RULING throughout). This
> document says what the B1 instrument IS; `docs/b1_preregistration.md` says what it will
> be judged by; `docs/b1_package.md` is what the owner reviews before any board time.

## 1. The question, and the boundary that makes it "autonomous"

*Can the board recover, from its own probes and nothing else, a replayable map of the 292
certified `clb_lut_init` addresses — which LUT, which INIT position, which polarity — and
say how sure it is?*

**The autonomy boundary (roadmap §1).** The board is the sole executing authority for probe
choice and for the map: it decides which addresses to set in each probe, in what order,
when an entry is resolved, what confidence it carries, and what the map hash is. The host
is notary (it signs whitelisted candidates — link 1, exactly as for every P3 session),
auditor (it pulls every probe's raw words and recomputes the three hashes), rel-v4
transaction endpoint and collector. After the session the host **recomputes** the map from
the readouts the records carry, as an audit; the recomputation never reaches the board and
never updates a map.

**Closed-book, not human-blind (roadmap §2 B1).** The ground truth — the certificate-derived
`local_map.json` (`56f2b9e8…`) — exists and its developer has read it. B1 claims runtime-blind
reconstruction *by the executable*: the cartographer is compiled with the 292 addresses in
genome-bit order (`P3_WHITELIST`) and the safety class, and with **no** LUT key, INIT index,
polarity or group table. That is a fact about bytes, guarded (§5), not a promise.

## 2. What the board measures, and why the map is decidable from it

The instrument is the archived P3 stack (`zynq-psoracle` `689dde1`, carrier `956379fa…`,
read-only, bound by hash before any import). For every candidate the PL's arm gate sweeps
all 64 input vectors of the six evolvable LUTs and latches the **functional readout** — six
64-bit truth tables, table *k* bit *v* = LUT *k*'s output for vector *v* — which the
application reads from the READOUT registers and the record carries
(`evidence.score.functional_readout`; the instrument's rule (iii) requires it to equal the
signed expected tables). The base is all-zero, so the readout of a candidate that sets
address *i* alone has exactly one lit position, (LUT *k*, INIT *v*): **the address's
functional relation is directly observable**, polarity included (frame bit 1 → INIT bit 1
→ lit). That is what makes B1 a measurement of the fabric rather than a guess from
address structure — an address-only guesser cannot know *v* (§5).

## 3. The cartographer (`firmware/b1/b1_carto.c`, `carto-v1`)

A pure unit, deterministic from (seed, budget, the observations), compiled into the image
and into a host twin; its Python reference is `host/b1_carto.py`; the RNG is the
instrument's (`l6_operators.Rng`: xorshift64, warm-up 4, rejection sampling).

| phase | probes | what it does |
|---|---|---|
| **A code** | 9 | address *i* carries the code *i*+1 (1..292, never 0); probe *p* sets every address whose code has bit *p*. A lit position decodes to the address whose code it lit under — group testing, one sweep per code bit. Provisional (confidence 1). Lit-count ≠ set-count, an out-of-range code, a double claim → anomalies, kept |
| **B confirm** | 292 | single-address probes in an RNG-drawn order (undecoded addresses first): exactly the decoded position lit → confidence 2; nothing lit on an undecoded address → `no_effect`; anything else → `contradiction` (confidence 0) |
| **C pairs** | 32 | RNG-drawn pairs of confirmed addresses, half same-LUT, half cross-LUT: the readout must be the union of the singles; a deviation is an interaction edge |

Budget 333 = 9 + 292 + 32; a smaller budget cuts B and C where it runs out and every entry
says what it rests on. **Every record carries a `carto` block** (loop_record 1.2.0): the
phase, the probes issued, the anomaly count, a sample (≤ 8) of the entries this observation
changed, and **`map_sha256` — the board's running commitment** to its whole map (sha256 over
the canonical rendering `{"anomalies","entries":[[i,lut,init,conf,state,[seqs]]…],"pairs":
[[a,b,kind,result,seq]…],"seed","version"}`). The IDENT (app_identity 1.4.0) names
`carto-v1`, the universe digest `895baf85…` and the probe budget.

## 4. The image — a versioned successor, not an edit of the instrument

`firmware/b1/` holds the instrument's `p3_derive`, `p3_rectx`, `p3_pull`, the BSP glue and
the linker script **byte for byte** (`IMPORT.json`, hashes = the archive's pin table), plus
B1's own files: `b1_app.c` (the application with the search replaced by the cartographer;
records carry no `arm`), `b1_wire.c/h` (the record and identity writers with the two
additive fields), `b1_carto.c/h`, and `p3_data.h` generated by `host/gen_b1_data.py` from the
phenotype manifest **without** the operator block. Same wire protocol (rel-v4), same
transactions and bounds, same watchdog, same closing steps. Built by
`firmware/b1/bsp/build.sh` with the instrument's toolchain (read-only) and the 2025.2
embeddedsw BSP; two clean builds are byte-identical — `evidence/b1/build_evidence.json`
(image `7bc86a3f…`, 114 708 bytes; 13 embeddedsw inputs by hash; the compiler by hash). The
binary is not committed (as the instrument's is not) and is hash-checked by the runner.

**What does not transfer from the instrument:** its L6 calibrations (a new image has its
own period); its `board_ready` mark. B1 needs the owner's compatibility review of this
image before any board session (package §7), and the runner refuses an image not marked
`board_ready` in `manifests/b1_manifest.json`.

## 5. The guards

| guard | where | what it proves |
|---|---|---|
| header without tables | `host/gen_b1_data.py`; `tests/test_b1_leakage.py` | `p3_data.h` is fresh from its generator and contains none of `P3_LUT_*`, `P3_MUTATION_BITS`, `P3_OPERATOR_DATA_SHA256`, LUT keys |
| source include scan | same test | `b1_carto.c/h` include only `b1_carto.h` and `p3_derive.h`; the app never references the search or arm names; the build compiles no `p3_search.c` |
| binary scan | same test (when the image is present) | the image contains no LUT key, no `P3_LUT`, no arm name; it does contain `carto-v1` and the universe digest |
| verbatim imports | same test | every unmodified instrument file hashes to the archive's pin |
| permuted fixture | `host/b1_model.py`; twin + leakage tests | over a fabric with a seeded permutation of the truth, the cartographer outputs the permutation (292/292), not the truth (< 10/292): it measures |
| address-only baseline | `b1_model.address_only_baseline`; leakage test | what address structure alone predicts scores precision < 0.2 against the reference's 1.0 |
| C = Python | `tests/test_b1_twin.py` | probes, record blocks and map bytes identical over truth / permuted / dropout / interaction fixtures, every budget phase, unscored probes |
| wire contract | `tests/test_b1_wire.py` | the image's own identity (1.4.0) and record (1.2.0 + carto) bytes pass the instrument's validator |
| autonomy replay | `host/b1_adjudicate.py` | after a session the reference, fed the records' readouts, reproduces every probe the board chose and every running map hash — the board followed the algorithm on its own observations and nothing else |

## 6. Adjudication (`host/b1_adjudicate.py`) and the map v2

Binding (session B1, the plan's seed, the B1 image, the frozen prereg, the IDENT's fields)
→ the instrument's validators unchanged (run-log validation with the audit gate, the
ALL-SELF-REPORTING policy, structural / baseline / REC / rel-v4 closure and controls, the
rate report, heartbeat and CRC / bad-frame budgets, the deadline) → COMPLETED at
budget + 2 → the autonomy replay (§5) → the verifier (`host/b1_verify.py`) against the truth
held back from the executable: precision, recall, polarity errors, calibration by
confidence, sample efficiency, the holdout LUTs (`CLBLM_L.SLICEM_X0.ALUT/DLUT`, 94 addresses)
apart from the train LUTs (198), interaction edges, anomalies → the comparison with the
preregistered prediction. The reconstructed map is expanded to `self_map` 2.0.0
(`schemas/self_map_v2.schema.json`: functional relation, confidence, state, evidence
provenance, interaction edges) and written beside the evidence.

## 7. What B1 does not claim

Nothing about unattested bits (the 1 756 named by the frozen DB): a later ruling. Nothing
about routing, FF or any other class. Nothing about map *utility* (B2) or the closed loop
(B3). Nothing about another die, Linux or the ICAPE2 path. Not a human-blind result (§1).
The board's sample efficiency here (9 probes to a full provisional map) is a property of an
additive, single-position fabric — the very property that made round 1′ undecidable — and
B1 measures it rather than assumes it (phase C, the anomaly counters).
