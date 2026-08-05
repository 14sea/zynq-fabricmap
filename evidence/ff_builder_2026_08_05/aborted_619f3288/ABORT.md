# Aborted-attempt INCIDENT RECORD — builder `619f3288`, 2026-08-05

> **This is an incident record, not evidence.** Nothing here can be verified: the
> attempt's bitstreams, stamps, checkpoints, readbacks and logs no longer exist. Call it
> an incident record and never "abort evidence" — the shorter name invites a reader to
> assume there is something left to check.

**Abort reason: the builder source was edited while the run was in flight, so every node
it produced was stamped with a recipe that no longer exists in the repository.**

The run was internally consistent — `recipe()` is evaluated once at startup, so all its
nodes shared one hash — and that is exactly why it had to be discarded. Internal
consistency is not the property the recipe domain protects. The property is that a build
corresponds to *committed, reproducible sources*, and by the time the run was stopped it
no longer did.

| recipe source | in the run's stamps | committed at `7f61a43` | match |
|---|---|---|---|
| `vivado/specimen/specimen_ff_formal.v` | `47b2e3fa` | `47b2e3fa` | yes |
| `vivado/specimen/build_ff_formal.tcl` | `a54a546a` | `a54a546a` | yes |
| `vivado/specimen/derive_ff_formal.tcl` | `9f3ebcfb` | `9f3ebcfb` | yes |
| `vivado/specimen/ff_formal_readback.tcl` | `ad69919d` | `ad69919d` | yes |
| `scripts/gate_build_ff_formal.py` | **`619f3288`** | **`4bda6899`** | **NO** |

The edit was the extraction of the `--instance` scope check into `check_instance_scope()`,
made after `base` and `zrst_AFF` had already completed. The builder is itself a recipe
source, so that refactor — which changed no behaviour — invalidated the run.

**The completion count did not show any of this.** At the moment of abort the run read 8
of 15 implementations complete, with every node's own stamp verifying against its own
recipe. Only a comparison of the stamped source hashes against the committed tree exposed
it. That is the reason the run-level check must compare hashes across all 23 specimens
rather than count finished nodes.

## What survives here, and what does not

**Preserved:** `gate_build_ff_formal.py.619f3288` — the exact builder source that produced
the aborted attempt, sha256
`619f328828eabf2057200625f81b6fdd417779fe4b1cf26389b2aed2993df5da`. It was recovered from a
working copy taken during mutation testing; it was never committed, so this file is the
only record of it.

**Destroyed, and this was my error:** the attempt's `stamp.json` files, `vivado.log`,
`run.out`, checkpoints, bitstreams and readbacks. I removed the build tree with `rm -rf`
when aborting, before the instruction to archive aborted attempts was given. The retry
contract in `docs/ff_builder_design.md` §8 says evidence is moved and never deleted, and
`archive_node()` implements exactly that — but I bypassed the builder and deleted the tree
by hand, which is the one path the contract cannot defend. The artifacts are not
recoverable.

## What was known about the attempt before it was destroyed

Recorded here because it is all that remains, and it should be read as a session record
rather than as artifacts:

- **Nodes completed:** `base`, `zrst_AFF`, `zrst_A5FF`, `zrst_BFF`, `zrst_B5FF`,
  `zrst_CFF`, `zrst_C5FF` — seven implementations. `zrst_DFF` was mid-`route_design` when
  the run was stopped and had produced no artifacts.
- **One pairwise comparison was run** on `base` ↔ `zrst_AFF`: the dedicated-net set
  computed to nine and matched `EXPECTED_DEDICATED`; tier 1 = 0 differences, tier 2 = 0,
  tier 3 = 1 (`rst_IBUF` sinks, because `AFF` is `FDSE` in that variant and its control pin
  is `S` rather than `R`). It is the case that would have been a false failure under
  revision 2's untiered comparison.
- **No holdout instance was touched**, in this attempt or any other.

## The erratum in `7c8d619` still owes an independent reproduction

That docs erratum — the dedicated set is nine, not four — was measured against an artifact
that has since been destroyed. **A destroyed measurement is not a result.** It stands as a
claim until the `4bda6899` run reproduces it from artifacts that exist and can be
re-derived by someone else.

If the new run computes a different set, or different tier-3 findings, **the new artifacts
arbitrate and a further correction is written.** The conclusion reached from deleted data
is not carried forward on the grounds that it was reached first.

None of the above is offered as certification evidence. The attempt produced no certifiable
result, its artifacts are gone, and the replacement run rebuilds all 23 specimens from the
frozen sources.
