# B4 pre-work, unit 2b-1 follow-up 2 — the owner's HOLD on `b91162c` (2026-10-17)

Three boundaries and one shape rule the owner reproduced with probes (`/tmp/b4_owner_b91162c_5dl4ogqn/owner_review.py`);
fixed in the original unit's files; `2bad829` and `b91162c` kept; `docs/b4_architecture.md` v0.1.5; hypothesis file
0.2.1 (`b4/hypothesis/ff_behaviour_v0.2.json`, now pinned by digest in its loader).

| # | gap | fix | regression |
|---|---|---|---|
| 1 P1 | the refusal path leaked the decode: an out-of-domain configuration was refused with "no attested reading for clock_mode bit 0 under latch" | `DomainRefusal` — the executing side receives the **fixed code** `REFUSED: configuration outside the model's domain (DOMAIN)` and nothing else; the reason is host-only (`diagnose().unknown_readings`); the hypothesis file's `domain_refusal` block rules that such a refusal is never a specimen, a redraw condition or a map-update signal (2b-2 inherits it) | `Latches.test_a_latch_with_the_clkinv_bit_clear_is_outside_the_domain_and_the_refusal_says_only_that` (the message equals the code; no clock / latch / unknown / bit / reading / inverted / storage word in it; with and without stimuli) |
| 2 P1 | an external, altered but valid hypothesis loaded as formal (`load(path)` → `fixture = False`) | `load()` takes **no path**: it reads the committed file only, holds it to `HYPOTHESIS_SHA256` pinned in the module, then the shape and every source; every other document — a byte-identical copy at another path included — enters through `fixture()` / `fixture_file()` and is marked `fixture: true` in every trace (`formal_input` block) | `test_a_valid_external_copy_is_a_fixture_never_the_formal_hypothesis` (a byte-identical copy is a fixture; the altered copy's trace says fixture; `load(p)` has no such call), `test_the_formal_entry_holds_the_committed_file_to_its_pinned_digest`, `test_the_formal_entry_consults_the_source_rehash`, the signature test (`load` takes nothing) |
| 3 P2 | per-row self-consistency replaced the polarity constraint: `negated`, `expected_value` and the transition changed together made NOCLKINV read in CLKINV's direction, and AFF.ZINI read backwards while the mapping still declared INIT = 0 | each token's reading **direction is the class's** (`TOKENS[...][3]`: every token direct — the bit set in its feature endpoint — but NOCLKINV, negated); a row whose `negated` flag is not the token's direction is refused, then `expected_value` / transition are held to that direction; the shared address must carry one direct and one negated reading (the branch is back, now with teeth) | `test_a_coordinated_re_labelling_of_a_token_s_direction_is_refused` (the owner's two edits, refused by name), `test_the_shared_address_rule`, the polarity cases |
| — | `unknown` loaded in the flip-flop context of clock_mode | `UNKNOWN_ALLOWED = {("clock_mode", "latch")}` in the shape check; `domain_refusal` and `formal_input` required blocks | `test_an_unrecognised_reading_is_refused_at_load_never_defaulted` (the flip-flop-context case), the absent-block cases |

## Tests (`tests.txt`)

The three modules: **Ran 45, OK**, zero skip (41 before). Shape refusals are now driven through the fixture
boundary (the only entry for a document that is not the committed file) and asserted equal to `shape_findings`;
the source re-hash is tested through `source_findings` by name and, for `load()`, by a patched `source_findings`
(started and stopped inside the test — R7).

## Mutants (`mutants.txt`; `build/wip/scratch_2026_10_17/b4_2b1_mutants.py`)

**25 / 25 killed**: the twenty of the previous rounds and five for this one — the domain refusal carrying the
reason, `load()` not holding the pinned digest, the token's direction not checked (a self-consistent re-labelled
row accepted), `unknown` accepted in any clock-mode context, `fixture_file` returning an unmarked object.

## The owner's probes, re-run (`owner_probes_rerun.json`, `owner_review_adapted.py`)

Two lines adapted: `hy.load(p)` no longer exists (the formal entry takes no path), so a `TypeError` is reported
as the refusal of the formal entry, and the `unknown`-in-flip-flop document is additionally tried through
`fixture_file`, where the shape check refuses it by name. Results: `latch_endpoint_q` as expected (hold with the
gate low, D passes with the gate high); `public_refusal` = the fixed code only; `external_hypothesis` → refused
(no call); `coordinated_NOCLKINV` and `coordinated_AFF.ZINI` → refused by the token's direction;
`unknown_in_flipflop_context` → refused (no call) and, as a fixture, refused by the shape check.

## What this establishes, and only this

The model contract with its three boundaries closed. Nothing about silicon; no landscape, gate, threshold or
number a later unit could be judged against.
