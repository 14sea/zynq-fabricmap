# B4 pre-work, the v0.3 model revision (2026-10-18; the owner's ruling on the v0.3 scope draft, after D1′'s PASS on `e0b5f04` and X-A's PASS on `c0689f8`)

**Scope delivered (the ruling, verbatim in `owner_ruling_2026_10_18.md`):** the model document, the formal loader's pointer and
digest, the related tests, `b4/IMPORT.json`, `docs/b4_architecture.md` and this evidence. **Not changed:** the behaviour state
machine (`b4_ff_model.py` logic), the engine, the cartographer, the replay, the mapping, the certificate, the D1′ evidence,
every old pinned input. No landscape, no seed scan, no threshold, no τ, no board.

## The six rulings and the three corrections, and where each lives

| ruling | where |
|---|---|
| L1 labelled **host correspondence**, attempt 2's `probe_report.json` pinned; the reading rests on named premises; status unverified | `b4/hypothesis/ff_behaviour_v0.3.json`: a `repository_document` source `evidence/b4/unit_d1prime_latch_ginv_attempt2_2026_10_18/probe_report.json` (sha256 `af482824…`, re-hashed by `load()` on every load), `decode.clock_mode.basis`, `valid_configuration.status`; `status` stays `"unverified"` (the loader refuses anything else). Tests: `TheFile.test_it_loads_and_every_source_hashes` (the two repository documents in order, G1–G6 present, the four context tables), mutants V3 / V5 |
| the v0.2 file kept, **bytes unchanged**; `v021_hole` built from it after its old digest is checked, as a marked fixture | `b4/hypothesis/ff_behaviour_v0.2.json` untouched (sha256 `1118bedf…`, held in `b4/IMPORT.json` and in `b4_test_fixtures.V021_SHA256`); `b4_test_fixtures.v021_hole_hypothesis()` reads it, refuses with an `AssertionError` if the bytes do not hash to the 0.2.1 digest, and enters it through `hy.fixture(…, "v021_hole")` (marked, version 0.2.1, path `fixture:v021_hole`). Tests: `test_every_assignment_is_in_the_v03_domain_and_the_v02_file_is_kept_as_a_marked_fixture`; mutants V8 / V9 / V10 |
| the `mechanics` fixture kept | `b4_test_fixtures.mechanics_hypothesis()` unchanged; the engine / replay / execution mechanism tests still run under it |
| the stale IMPORT references and the architecture title in this unit | `b4/IMPORT.json`: the six `external_sources` and the certificate's `used_by` no longer name the removed `v0.1.json`; `docs/b4_architecture.md` line 1 now v0.1.12 (the revision notes already reached v0.1.11) |
| the `unknown` enum, the DOMAIN mechanism and the existing refusal coverage kept | `READINGS`, `UNKNOWN_ALLOWED`, `shape_findings`, `decode`, `DomainRefusal`, `observe`'s domain check unchanged; the DOMAIN tests that used the formal hypothesis's hole now run on `v021_hole` with their assertions unchanged (`test_a_latch_with_the_clkinv_bit_clear_is_outside_the_v021_domain_and_the_refusal_says_only_that`, `test_domain_becomes_a_terminal_event_with_the_state_before_the_call`, the kept F termination fact); the injected-DOMAIN tests unchanged |
| §5.3 / §13 say: v0.3 fills a hole the model itself defined, **under an added assumption**; not gate-ready | `docs/b4_architecture.md` §4.4 (the three layers L1 / L2 / L3), §5.0, §5.3 ("The F fact, under each hypothesis revision"), K7, §13, §14, the v0.1.12 note |

| correction | where |
|---|---|
| LATCH and CLKINV fixed leave **19 free bits** | the file's `valid_configuration.rule` and G1; §5.0; the test draws the 19 free bits at random under the hole and holds every draw in v0.3's domain and outside 0.2.1's |
| F's base + probes = 22; a complete run **B + 23** (B search evaluations, one holdout) | `Termination.test_under_the_formal_v03_hypothesis_f_s_probe_pass_completes`: `cost = {base 1, probes 21, search B, holdout 1}`, `port.calls = r.observations = B + 23` for B = 24, 24, 16; the file's revision note; §5.3. Mutant V17 (the base double-counted: invisible to the ledger and to the replay) is caught by that assertion alone — the test-mutant V14 shows the weakened test lets it live |
| the hand-derived trace follows the model's order: the new D settled at the **old** clock first, then the clock change; closing the gate while changing D passes the new D; the init step's atomic, unsettled assignment is a named model abstraction; A8 unresolved | `Latches.test_the_inverted_gate_latch_is_transparent_while_the_slice_clock_is_low` (the five-step derivation in the docstring; `set(clk 1, d 0x0F)` gives `[1, -, 1, -, 0, -, 0, -]`, not the old Q; with CE **tied high** the init readout is INIT only by the atomic step and the first low-clock step passes D); the file's `initialisation_event.assumption` / `status` and G6; `b4_ff_model.py`'s docstring. Mutants V11 / V12 / V13 |

## What v0.3 says, in three layers (the file keeps them in separate source entries)

- **L1 host endpoint correspondence** — `docs/ff_latch_probe.md` (bit 1 = not inverted, `IS_G_INVERTED = 0`) and the D1′ pair
  (`IS_G_INVERTED` 0 → 1 clears CLKINV, LATCH kept, no other same-class mover; two attempts, identical readbacks; the rebuilt
  `main_latch` equal frame for frame to the 2026-08-04 endpoint). One recipe, one site, Vivado 2025.2. Not a certificate, not silicon.
- **L2 vendor primitive behaviour** — `LDCE.v` lines 63–71 (`G_in = G xor IS_G_INVERTED`), 117–119 (GSR → INIT), 183–209 (the UDP
  table). The lines were already adopted in 0.2.1; v0.3 adds no UNISIM line and applies them to one more configuration.
- **L3 generalisation assumptions G1–G6**, each an item of the `project_decode_assumption` source: the other 19 bits do not change
  the reading; the property is realised as the slice-level clock inversion on silicon; the vendor's model describes the silicon
  gate; tool- and recipe-invariance; four main elements speak for the per-slice bit; the init readout under an open gate rests on
  the model's atomic, unsettled init step.

The reading "latch, CLKINV bit 0 ⇒ gate inverted" is L1 ∧ L2 ∧ L3. The domain is complete because of L3. Nothing here is an
observation of silicon; `status` is unverified; A8 (which event restores INIT on the board) is unresolved.

## Tests (`tests.txt`)

The eleven B4 modules: **Ran 131, OK**, zero skip (128 before). Per module: test_b4_carto 12, test_b4_engine 16, test_b4_execution 6,
test_b4_ff_hypothesis 12, test_b4_ff_mapping 14, test_b4_ff_model 22, test_b4_landscape 5, test_b4_probe_latch_ginv 15,
test_b4_replay 23, test_b4_rng 2, test_b4_stats 4. The three new tests: the v0.3 domain and the kept v0.2 file; the inverted-gate
latch's hand-derived trace; F completing under v0.3. Two tests renamed and moved onto `v021_hole` (the refusal's wording; the F
termination fact); the execution boundary's DOMAIN case moved onto it.

## Mutants (`mutants.txt`; `b4_v03_mutants.py`, a copy of the ignored `build/wip/scratch_2026_10_18/` script; hermetic whole-tree copies carrying the certificate and the D1′ probe report, no other evidence; a kill only with Ran N > 0 and FAILED)

**16 / 16 killed**, plus one test-mutant check: the file's bit 0 back to `unknown` (re-pinned); bit 0 as `not_inverted` (the
mechanics reading as formal; re-pinned); the probe report dropped from the sources; G1–G6 dropped; `status` set to verified;
the formal pointer left on v0.2; the digest not rotated; the kept v0.2 file altered by one byte; the hole fixture without its
digest check; the hole fixture built from the formal file; the model ignoring the inversion under a latch; the model settling
the new inputs only after the clock change; the init step settling level effects; the engine skipping the last probe; the
`latch_gate_inverted` swap made equal to the formal reading; the base observation double-counted. **V14** (a mutant of the
test: the B + 23 assertion removed) lets the double-counting engine mutant V17 live — the assertion the owner asked for is
load-bearing, not decorative.

## Not done here, and what this does not establish

No exploration run, no gate number, no threshold or τ (2b-3), no board work; push / merge unauthorised. v0.3 does not make the
design gate-ready and does not establish any behaviour of the fabric; it changes what the model refuses, under an assumption it
names. The D1′ evidence, the certificate, the mapping and every old pinned input are unchanged.
