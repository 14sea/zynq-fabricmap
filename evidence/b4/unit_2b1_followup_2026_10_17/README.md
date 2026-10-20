# B4 pre-work, unit 2b-1 follow-up — the owner's HOLD on `2bad829` (2026-10-17)

Six gaps the owner reproduced with probes (`/tmp/b4_owner_2bad829_xbsxrq0k/owner_review.py`), each fixed in
the original unit's files; `2bad829` kept; `docs/b4_architecture.md` v0.1.4; hypothesis file v0.2.

| # | gap | fix | regression |
|---|---|---|---|
| 1 P1 | the latch's clock decode: `_phys()` read CLKINV = 1 as an inverted gate, but the attested LDCE endpoint has CLKINV = 1 with `IS_G_INVERTED = 0` (`docs/ff_latch_probe.md`, "The finding worth keeping"); with G = 0, GE = 1, D = 0 the model turned INIT = 1 into 0 | `clock_mode` decoded **by storage context** in the hypothesis (`by_storage_context`: flip-flop bit 1 = inverted; latch bit 1 = not inverted, bit 0 = `unknown`); the model's gate for a latch is the slice clock itself; a latch with the bit clear is outside the model's domain and refused by name | `Latches.test_the_attested_ldce_endpoint_holds_init_with_the_gate_low` (hand-derived `[1, None, 1, None, 1, None, 1, None]`, plus the gate-open case and the forbidden inverted reading as a swap fixture); `test_a_latch_with_the_clkinv_bit_clear_is_outside_the_domain`; the hypothesis decode test |
| 2 P1 | `observe(config, [])` handed over the whole decode (primitive, INIT, SRVAL, kind, inversion); applicability and physical edges sat in the trace | the trace is the **executing side's view only** (`visibility: executing_side`; the configuration, the stimulus, per step the applied context and Q); the decode, applicability, physical edges and unknown readings are **host-only** (`diagnose`, `step_diagnostics`, `visibility: host_only`); the hypothesis file classifies every item (`observation_context.executing_side_visible` / `host_only_diagnostics`) | `TheTrace.test_every_readout_carries_the_executing_side_context_only…` (no decode-derived key anywhere in the trace), `test_an_observation_without_stimuli_hands_over_nothing` |
| 3 P1 | `load()` defaulted to no source check; the mapping loader recorded whatever digest it read | `load(path)` has **no switch**: shape and every named source re-hashed, always; a hypothesis that is not the committed file enters only through `fixture(doc, label)` and is marked `fixture: true` in every trace header; the mapping reads the committed certificate only against the pinned `CERTIFICATE_SHA256` (`c69e419f…`), any other file only with its digest given explicitly, `None` refused | `test_a_fixture_hypothesis_is_marked_and_the_default_entry_has_no_switch` (the signature of `load` is `path` alone), `test_sources_are_rehashed_by_the_default_entry`, `test_the_default_entry_is_pinned_to_the_authorised_digest` |
| 4 P2 | the mapping accepted `word = -1`, a baseline specimen that does not exist, and `expected_value = 0` with a 0 → 1 transition | ranges (far 32-bit, word 0..100, bit 0..31); both endpoints must be specimens of the certificate and on the site; per row the direct / negated reading's `expected_value` and transition must agree | `test_address_ranges_endpoints_and_the_polarity_cross_check` (seven named refusals) |
| 5 P2 | an arbitrary reading text was accepted and fell through to INIT = 1 by prefix | readings are **machine enums** (`READINGS`, validated at load, at `with_reading` and at decode; compared by equality); an unrecognised reading is refused by name; `unknown` allowed only for clock mode under a latch | `test_an_unrecognised_reading_is_refused_at_load_never_defaulted`, the swap tests |
| 6 P2 | a step dict that bypassed `set_` (`clock = 2`, `sr = -1`) was accepted | `validate_step` is the one validator, applied by the builders AND by `observe` to whatever it is handed; the configuration validated (exactly the mapping's addresses, 0 / 1, no bool); an init step allowed only with the slice clock low and SR de-asserted (the hypothesis's `initialisation_event.allowed_context`) | `test_observe_validates_whatever_it_is_handed` (seven cases), `test_the_init_step_is_allowed_only_with_the_clock_low_and_sr_de_asserted` |

## Tests (`tests.txt`)

The three modules: **Ran 41, OK**, zero skip (32 before the follow-up). Every expected trace still derived by hand.
The per-row polarity cross-check made the former NOCLKINV branch of the shared-address rule dead code; it was
removed (a mutant of it had become equivalent).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b1_mutants.py`)

**20 / 20 killed**: the eleven of the first batch (M5a re-aimed at the shared-address rule after the dead branch
was removed) and nine for the follow-up — the latch's clock decoded without its context, the decode handed over
in the trace, the source re-hash dropped from `load()`, the pinned certificate digest not held, the address range
check gone, an unrecognised reading falling through at decode, `observe` taking steps as they come, the init
step's context unchecked, an out-of-domain configuration simulated with a default.

## The owner's probes, re-run (`owner_probes_rerun.json`, `owner_review_adapted.py`)

The owner's script re-run against this tree with ONE line adapted — `hy.load(p, check_sources=True)` →
`hy.load(p)`, since the switch no longer exists. Results: `observation_without_stimuli` → zero steps and no
decode-derived key; `default_load_missing_source` → refused (absent at the vendor root); the three certificate
tampers → refused at the pinned digest (the content checks behind it are exercised by the tests with the copy's
digest given explicitly); `clock_2` / `negative_sr` → refused by name; `latch_endpoint` → the model's
`[1, None, 1, None, 1, None, 1, None]` equals the owner's expectation. `unrecognised_decode` reports *accepted*
because the probe edits the v0.1 field `bit_one_means`, which v0.2 no longer has (the edit is a no-op on the
file); the equivalent probe on the v0.2 field `bit_one` is `test_an_unrecognised_reading_is_refused_at_load_never_defaulted`.

## What this establishes, and only this

The model contract as corrected. Nothing about silicon; the latch endpoint's reading is the probe's host
measurement of a bitstream, not a behaviour; no landscape, gate, threshold or number a later unit could be
judged against.
