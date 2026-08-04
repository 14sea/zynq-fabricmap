# Round 9 ruling — accepted, and what the producer builds against

Author's ruling on `docs/round9_request.md`, received 2026-08-03. This file is the
producer-side record of what was decided; the normative text belongs in
`docs/certificate_schema.md` once 1.4 lands. Where the two ever disagree, the schema
doc wins and this file is the one that is wrong.

## 1. Candidate B is adopted

Certificate **1.4 = one feature namespace + verifier-derived group consistency.**
`clb_ff_config` and `clb_lutram` both go through **feature keys**
`(specimen_id, feature)`. `evidence_model: mixed` is **not** adopted; it is reconsidered
only if a class genuinely needs both models at once.

Candidate A's full specification stays in `round9_request.md` as the rejected
alternative — a record of what was weighed, not a spec to build. The A-only fixtures
(1–3, 6, 8 in that document's negative list) are correspondingly out of scope.

Consequence for this class: 176 entries, one key space, coverage denominator 176, no
cross-namespace bookkeeping, no conjunctive status. The 8 `CLKINV`/`NOCLKINV` relations
are **derived by the verifier from the frozen DB**, never asserted by the producer.

## 2. Vacuity and counting

| statement | disposition |
|---|---|
| codeword collision within a group | **frozen-group ambiguity → format FAIL** |
| `group_exclusivity` | DB-consistency **diagnostic**, never in `address_pass` |
| decode-validity (level 2) | **diagnostic**, not scored |
| strict preregistered codeword equality (level 3) | **the only** address pass |
| `member_identity` (semantic) | fully isolated, as in 1.3 |

Run B, re-emitted under 1.4, must read **falsifiable 16/16 + vacuous 16**. The decision
does not change; `clb_mux` stays certified.

### Host-side check of the new format-FAIL rule, run today

The ambiguity rule is new, so the producer measured whether it fires anywhere in the
freeze before anyone writes code that assumes it does not. Groups are the maximal sets
sharing one polarity-free coordinate set; a collision is two distinct feature names
carrying the same codeword over that scope.

| class | entries | bitless | groups | multi-member | codeword collisions |
|---|---|---|---|---|---|
| `clb_lut_init` | 2048 | 0 | 2048 | 0 | **0** |
| `clb_ff_config` | 176 | 0 | 168 | 8 | **0** |
| `clb_lutram` | 42 | 0 | 36 | 6 | **0** |
| `clb_mux` | 500 | 0 | 170 | 72 | **0** |
| `int_pip` | 7272 | 0 | 4824 | 816 | **0** |
| `ppip_bitless` | 858 | **858** | 0 | 0 | n/a |

**Zero across every bit-bearing class**, `int_pip` included — so the rule never fires on
the current freeze, and if it ever does, that is a real signal about the database rather
than a routine rejection. `ppip_bitless` is out of the rule's scope entirely: all 858
entries carry a keyword (`always` 498, `hint` 232, `default` 128) and no bits, which is
what its name says. An earlier count of "354 collisions" there was a producer parser
artifact — keywords read as bit tokens — and is retracted here rather than left in a
scratch buffer.

## 3. FP definition — fixed, not per-run

```
FP =  ownership_unknown
    ∪ unattributed
    ∪ { db_attributed bits in an asserted tile that are claimed by a feature of THIS
        bit class and fall in no preregistered scope }
```

The per-run declared-policy fallback the request offered is **refused**: the producer
does not choose its own strictness. Counting and decision:

- FP is counted **once per `(pair, address)`**;
- TP/FN come **only** from each holdout feature's preregistered assignment and expected
  transition — never from the diff;
- `status: passed` requires **all four**: completeness, `partition_exact`, `FN == 0`,
  `FP == 0`.

## 4. Also pinned

- **Observation consistency.** Same `(specimen_id, address)` ⇒ same observed value,
  across every result. Recomputed by the verifier.
- **`in_scope` coverage, not ownership.** Every `in_scope` bit must be covered **at least
  once** by a scope in the pair's commitment. Endpoint duplication is legal — both
  endpoints of a pair assert the same scope, which is why all 24 of run B's movers have
  two owners. No uniqueness-per-result rule.
- **No all-zero-safe assumption.** A listed codeword is required only for groups the
  pre-registration declares *selected*, or that a write touches. "All-zero = unset =
  safe" is not assumed anywhere, so the raw unlisted-pattern counts (844 / 160 / 30)
  stand without an exemption.

## Producer's work queue, in order, once 1.4 + verifier + fixtures land

Pre-registration stays **held** until the schema, the verifier and the fixtures are in
and passing. Nothing below emits a commitment hash before then.

1. `gate_emit_ff.py` — 176 `(specimen, feature)` predictions, one commitment, split over
   specimens, sha256 committed before any bitstream exists.
2. `gate_measure_ff.py` — FP per §3, TP/FN from the preregistered assignment only,
   five-bucket accounting per pair, observation-consistency data emitted per address.
3. `gate_certify_ff.py` — 1.4 record, vacuity labels, diagnostics separated from
   `address_pass`.
4. Re-emit run B's certificate under 1.4 (same predictions, same measurement, same
   specimens — recounted only) and update `data/MANIFEST.json`'s `clb_mux`
   `address_accounting` to carry the vacuous count.
   **DONE 2026-08-04**, out of order and ahead of 1–3: it needs no commitment, so it did
   not wait on the pre-registration hold. `gate_certify_mux.py` emits 1.4;
   `gate_runs/run_2026_08_02_b/certificate.json` now reports `address_pass=16`,
   `vacuous=16 ambiguity=0`, `decode_validity 16/16`, `semantic 16/16`, and verifies
   under `--require-production`. The gate timestamp was preserved rather than redated
   (`--gate-timestamp`) — the gate ran on 2026-08-02; only the record was rewritten. The
   1.3 record is archived at `tests/fixtures/certificate_group13_run_b.json` so round 9's
   own derivation test still starts from 1.3 evidence, and `tests/test_run_b_erratum.py`
   proves nothing but the accounting moved.
5. `clb_lutram` follows the same route; its shape is already known to match
   (42 entries → 36 groups, 30 singleton + 6 complementary, all one bit wide).

The specimen harness is already in place: `vivado/specimen/specimen_ff.v` and
`build_ff.tcl`, with FF `INIT` taking the one-P&R route.
