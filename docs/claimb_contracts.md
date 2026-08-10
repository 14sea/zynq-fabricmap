# Contracts brought in-tree, with their sources pinned

Standing isolation rule (`docs/workflow.md`): sibling repos are **read-only sources**;
files are copied in, never referenced across trees. This file closes the *documentary*
half of that rule for Claim B.

## What was actually missing — measured, not assumed

Before writing this I checked what this repo references at runtime:

```
grep -rn 'zynq_autoehw|zynq-xpart|zynq_ehw|zynq_agentctl|/home/test/prjxray' scripts/ host/ schemas/
grep -rn 'sys.path' scripts/ host/
```

**Runtime isolation was already clean.** Every hit is a comment or a docstring citing
prior art; there is no cross-tree import, and every `sys.path.insert` resolves inside this
repository. The one external path is `extract_prjxray_subset.py --src /home/test/prjxray-db`,
which is the *offline freeze* step's default argument — `data/` is already frozen in-tree
and self-verifying, so no run depends on that path existing.

What was outside the tree was the **contract text**: Claim B's own definition and its
falsifiers, the baseline this comparison is required to run, and the schema-versioning
policy. Those are restated below so a reader of this repo alone has the whole contract.

## Sources, pinned

Read at `zynq-autoehw` commit `888261329503d3a954fbdadd55bc69b6e17f988c` (2026-08-02):

| source | sha256 |
|---|---|
| `docs/tech_report.md` | `8b8252a0e444d58fa776dfe448c1aae7ededd0ed5be5a14266ccf646549fb135` |
| `docs/schema.md` | `8d315c22013d59380e0d11b251f076f4cb5c41fcb929fdd1ca4c7e8aa199c85b` |
| `docs/workflow.md` | `0867dcb46e176c69e2eaf5ae318775e66f6531aa6858aad199c0d5dcbe215379` |

A pin is a statement about what was read, not a dependency: if those files change, this
document does not silently follow, and the difference is a review question rather than a
drift nobody notices.

## Claim B, as preregistered in the source

> A device-local map (learned or inherited inside a constrained island) can guide later
> hardware evolution more safely than raw bit mutation.

**Non-claims, from the same section.** Not a claim to reconstruct a full public 7-series
bitstream database — that is prjxray's job. The map is **device-local**, and may be
**behavioural** (recording that a source reaches a sink, a delay score, a stability
measure) rather than symbolic.

**Distinctness.** `zynq-ehw` used fixed, pre-authored substrates; it never built a map of
which local tokens are safe, observable, useful and stable, nor used one to gate selection.

## The four falsifiers — and they were already fixed

The source lists these, and `docs/claimb_preregistration.md` §5 carries the same four. That
they match is worth stating explicitly: they were **not** chosen after seeing this round's
design.

1. map-selected candidates do not beat random *safe* baselines;
2. map entries are not replayable across cold boot or reload;
3. compatibility records drift without detection;
4. the map cannot reject a known-bad composition case.

## The required baseline

From the source's baselines table:

| Baseline | Purpose | Where required |
|---|---|---|
| **Map-guided vs random-safe** | isolates the *map's* contribution from mere safe mutation | Claim B |

This is why round 1's control arm is **random-safe over the same certified universe under
the same gates**, and not random flipping across the bitstream. The comparison was fixed by
the claim before this repo existed; the preregistration adds that the wider baseline is
also *unsafe* on a working board, but the scientific reason came first.

## Schema versioning policy

Inherited from the source's `docs/schema.md`: every contract artifact carries
`schema_version` as `MAJOR.MINOR.PATCH`. A MAJOR bump may break consumers; a MINOR
addition must leave existing consumers working, so consumers ignore unknown fields rather
than refusing them.

Artifacts this repo emits under that policy, and where their rules live:

| artifact | version | schema |
|---|---|---|
| `local_map` | 1.0.0 | `schemas/local_map.schema.json` (**proposal** — the author owns the final) |
| `phenotype_manifest` | 1.0.0 | `scripts/build_phenotype_manifest.py` |
| `claimb_run_log` | 1.0.0 | `scripts/run_log.py` |
| `fabric_bit_class_certificate` | 1.6.0 | `schemas/certificate.schema.json` (author-owned) |
| `specimen_attestation` | 2.0.0 | `schemas/specimen_attestation.schema.json` (author-owned) |
| `specimen_staging` | 1.0.0 | `schemas/specimen_staging.schema.json` (author-owned) |

One deliberate exception to "ignore unknown fields": `local_map.provenance.kind` is a
**const**, not an enum. A `self_cartography` or `search_byproduct` map is a different claim
with different evidence behind it, and a round-1 verifier must refuse it outright rather
than accept it as a MINOR addition.

## What is NOT inherited

- **zynq-autoehw's M1 record.** It is closed at `m1-complete` and reproduced on a second
  die; nothing here re-litigates it, and nothing here may be cited as extending it.
- **Its engineering debt.** The NV champion store and the board-side replay bundle were
  closed in that repo at `m1-eng-complete`. This repo does not point at remainders closed
  elsewhere.
- **Claim A and Claim C.** Settled there. Round 1 tests Claim B only.
