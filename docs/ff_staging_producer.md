# The formal FF converter and stager (producer side)

`scripts/gate_stage_ff_formal.py` turns what the builder wrote — `readback.tsv` +
`stamp.json` under `<build-root>/<site>/<variant>/` — into `specimen_attestation` 2.0.0
records, and stages the committed set in the layout certificate 1.6 consumes
(`<staging-root>/<specimen_id>/{spec.bit,attestation.json}` plus a `specimen_staging`
1.0.0 manifest).

It is the answer to the last mismatch in the handoff: the builder's native layout is
`<site>/<variant>/` and `gate_measure_ff.py` reads `<specimen_id>/`. Nothing else about
the build changes; in particular **no Vivado run is required**, because
`ff_formal_readback.tcl` already records every cell and pin fact 2.0 asks for and
`stamp.json` already *is* the `ff_formal_stamp/1` record the schema embeds.

## 1. Two modes, and why they are not one flag apart

```
scripts/gate_stage_ff_formal.py --build build/gate_ff_formal --instance SLICE_X2Y25 --check
scripts/gate_stage_ff_formal.py --build build/gate_ff_formal --stage build/ff_staging
```

`--check` converts and validates specimen by specimen and **writes nothing**. It is how a
partially built tree is exercised — today the mine instance, 23 of 184. Naming
`--instance` asserts *that instance*: 22 of its 23 specimens converting exits non-zero,
because a "22/22 clean" line about a set nobody chose is exactly the shape of a false
success. Without `--instance` the mode is diagnostic and a partial tree is legitimate; an
empty tree never is, in either mode.

`--stage` is **all or nothing**. If any committed specimen is unbuilt it refuses, and it
refuses before creating anything, so a failed staging leaves no directory behind. This is
not defensive politeness: certificate 1.6 requires set equality between the commitment,
the manifest, the staging directories and the certificate's specimens, so a
"successfully built subset" is not a smaller staging — it is no staging. `--instance`
and `--stage` are mutually exclusive for the same reason.

There is deliberately **no flag naming a commitment file**. The commitment is
`gate_build_ff_formal.load_commitment()` — hash-pinned to
`5440ef27…d1b2e51` — or nothing. A tool that can be pointed at a reduced
`predictions.json` is a tool that can stage a mine-only set and call it complete.

Staging roots are refused outside the repository (manifest paths must be
repository-relative), inside `gate_runs/`, `data/`, `evidence/` or any source namespace,
and on top of an existing directory.

Two guarantees make "all or nothing" true rather than intended:

* the write phase builds `<root>.partial` and only ever ends in the rename or in
  removing that directory, including when the failure arrives *after* files are written
  (a manifest that does not validate). A half-written staging root that survives looks
  like output. The cleanup is **not** `ignore_errors`: if the partial root cannot be
  removed, the tool says which path is left rather than re-raising the original error as
  if the tree were clean;
* `verified_state()` checks a source bitstream *before* it is read. What gets published
  is the **copy**, so its hash is recomputed after writing and compared with the hash the
  stamp and the attestation pin. A source edited inside that window would otherwise be
  staged with its own new hash agreeing with itself everywhere the manifest looks.

## 2. `requested` is plan intent, and that is the whole reason this file has a table

`readback.tsv` records only what Vivado **resolved**. Filling `requested` from it would
make the consumer's requested-versus-resolved comparison compare a value with itself. So
`requested` is derived from the pinned plan intent — the primitive, BEL and site each
cell was *constrained* to, which follows from the variant plus `sites_for()` — and the
readback is then **required to agree**, cell by cell, or the record is not produced.

| cells | requested BEL | requested primitive |
|---|---|---|
| 8 target storage (4 for `latch`/`latch_base`) | `FF_ORDER` / `MAIN_FFS` | `LDCE` for `latch`; `FDCE` for `latch_base` and `async`; `FDSE` for the named FF of `zrst_*`; `FDRE` otherwise (including every `zini_*`, which reuses `base`'s routed checkpoint) |
| 8 target LUTs | `A6 B6 C6 D6 A5 B5 C5 D5` | `LUT5` |
| `anchor_lut1/2`, `q_reduce1/2` | `A6 B6 C6 D6` at the anchor site | `LUT6` |
| `anchor_ff` / `anchor_ff2` | `AFF` at the anchor / keeper site | `FDRE` |

That table mirrors `vivado/specimen/build_ff_formal.tcl`, whose hash every stamp pins.
`check_tcl_intent()` re-reads the Tcl on every run and refuses if the mirror has drifted,
so the duplication cannot rot silently.

The five `/resolved/*` summaries are written because the schema requires them; the
consumer's verifier rebuilds every one of them from `cells` and rejects disagreement, so
nothing the producer puts there is load-bearing.

## 3. What this does not prove

* The record is an **integrity anchor**, not a provenance proof: hashes detect
  substitution, they do not show that Vivado produced this bitstream from that
  checkpoint. Re-establishing that relation needs a rebuild.
* `resolved.nets` is preserved verbatim from the readback. The consumer does not
  recompute it, so **tier-2 dedicated-net identity remains the producer gate's job**
  (`gate_measure_ff.py`), not the certificate's.
* Nothing here has been on silicon. The class is address prediction from frozen rules.

## 4. Acceptance

Recorded from commands, not from a report:

* `--check` over the built mine instance: **23/23 convert**, each record passing both the
  JSON schema and the consumer's own `ff_formal_attestation_errors`, with zero problems.
  Every variant family is represented — `base`, `clkinv`, `ce_tied`, `sr_tied`, `async`,
  `latch`, `latch_base`, 8× `zrst_*`, 8× `zini_*`.
* `--stage` against the same tree refuses with *23 of 184 committed specimens are built
  (missing 161)* and writes nothing.
* hiding one mine specimen makes `--check --instance SLICE_X2Y25` exit 1 with
  *asserts all 23 of its committed specimens; 22 are built*, where it previously reported
  a clean 22/22.
* `tests/test_ff_stager.py`: 30 cases, all synthetic except one clearly named
  artifact-dependent case, so the suite runs on a cold checkout. Two of them cost
  nothing and pin what a docs command line assumes: the tool carries a shebang **and**
  the executable bit, and `scripts/gate_stage_ff_formal.py --help` actually runs. Mode
  `100644` makes every command line in this file exit 126.
* 21 adversarial mutations of this tool, **20 caught**. The survivor — filling
  `requested` from the readback — is an equivalent mutant while the three drift guards
  stand, because they make the two values provably equal; `test_requested_is_the_plan_
  intent_spelled_out` exercises the intent path on its own so the table cannot move
  unnoticed.

Holdout stays where it was: the 161 unbuilt specimens are not authorised by this tool
existing. What it removes is the excuse that the staging format was unknown.
