# Formal FF attestation and staging contract

Status: consumer contract, 2026-08-06. This is the answer to the four consumer-side
blockers recorded after the mine-only `clb_ff_config` diagnostic. It does not authorise
or describe a partial holdout run.

Machine-readable contracts:

- `schemas/specimen_attestation.schema.json` — legacy 1.x plus formal-FF 2.0.0;
- `schemas/specimen_staging.schema.json` — exact staged set 1.0.0;
- `schemas/certificate.schema.json` — the `clb_ff_config` certificate 1.6.0 selection
  rules;
- `host/verify_certificate.py` — cross-file rules JSON Schema cannot express.

## 1. Why attestation 2.0 is a MAJOR version

Attestation 1.x describes one target with singular `requested_bel`, `resolved_bel`,
`LOCK_PINS` and pin mapping. A formal FF specimen is a routed design containing:

- eight target storage cells, except `latch` and `latch_base`, which contain four;
- eight target LUTs in every variant;
- four anchor cells plus two reduction LUTs at the anchor site;
- one clocked keeper at the keeper site (six anchor/keeper cells total).

Treating one of those cells as “the target” would make the rest omissions, and an
omission proves nothing. Version 2.0 therefore replaces the singular resolved shape
with a complete `cells[]` list. Version 1.x is retained as a distinct legacy branch;
its accepted records and meaning do not change.

## 2. Routed facts and independently rebuilt summaries

Every 2.0 record identifies the specimen, commitment and embedded source stamp. Each
cell carries a stable logical name/BEL and role, requested and resolved REF/LOC/BEL,
raw properties, `LOCK_PINS`, resolved pin mapping, and local pin-to-net facts. The
record also preserves routed net facts. LUTs without both `LOCK_PINS` and pin mapping
evidence are invalid.

`requested` is pinned producer intent, not a second Vivado readback. Comparing it with
`resolved` rejects an internally contradictory record and preserves what the recipe
claims to have asked for; it does **not** independently prove Vivado received or
honoured that request. The checks with independent teeth are the routed `resolved`
facts against the consumer-derived topology: exact 4/8 storage, 8 target LUT and 6
anchor/keeper cell sets, including their BEL and site roles.

Likewise, `resolved.nets` is preserved evidence, not a second implementation of the
builder's tier-2 gate. The 2.0 host verifier validates the record shape but does not
recompute dedicated-net membership or pairwise T2 equality. Those remain producer
gate responsibilities. In particular, calling `ff_formal_attestation_errors()`
directly with an empty `nets` object exercises no net rule (the full JSON Schema at
least requires a non-empty object); neither path proves the net set is complete.

The verifier derives the exact expected cell topology from the committed `variant`:

| topology | storage BELs | target LUT BELs | support cells |
|---|---:|---:|---:|
| ordinary and derived | 8 (`AFF`, `A5FF`, …, `D5FF`) | 8 | 6 |
| `latch`, `latch_base` | 4 (`AFF`, `BFF`, `CFF`, `DFF`) | 8 | 6 |

Missing, duplicate or extra cells are format failures. Requested and resolved
placement must agree, target cells must resolve at the target site, and every named
anchor/keeper cell must resolve at its committed role's site and BEL.

The frozen predictions already name scalar JSON pointers such as
`/resolved/ff_init/AFF` and `/resolved/clock_mode`. Those fields remain so the public
commitment does not move, but they are summaries only. The verifier rebuilds them:

- `ff_init` from each storage cell's routed `INIT` property;
- `ff_srval` from the routed primitive (`FDSE`/`FDPE` set, reset/clear primitives
  clear);
- `ce_mode` and `sr_mode` from whether every relevant control pin is driven or tied;
- `sr_kind` from synchronous versus asynchronous primitive families;
- `storage_kind` from FF versus latch primitive;
- `clock_mode` from routed `IS_C_INVERTED`, with `LATCH` separate.

Mixed, missing or unsupported raw facts do not let the producer choose a summary.
They make the attestation invalid. A correct copied summary with contradictory cells
is rejected before its semantic result can pass.

## 3. Source stamp and checkpoint chain

`source_build` embeds the completed `ff_formal_stamp/1` record: node identity, target /
anchor / keeper mapping, attempt ID, recipe source hashes, commitment and frozen-plan
hashes, part, tool version, raw Tcl arguments, seed and artifact hashes. The verifier
checks current repository source bytes, specimen identity, seed, part/tool,
commitment, staged bitstream and checkpoint against it.

An implementation pins `base.dcp`. A derived specimen pins `derived.dcp` and a source
`{specimen_id, base.dcp hash}`. That source must equal both the embedded
`derived_from` record and the independently staged source specimen's checkpoint.
Changing all fields inside the derived record to one self-consistent but wrong source
still fails the cross-specimen check.

These hashes are integrity anchors. They detect substitution; they do not prove that
Vivado produced the bitstream from the checkpoint. Re-establishing that relation still
requires rebuilding with Vivado.

## 4. Exact staging before measurement

The builder's native layout is `<site>/<variant>/`. Certificate 1.6 does not consume
that layout directly. After producer verification, the stager emits one root with
exactly:

```text
<staging-root>/
  <specimen_id>/
    spec.bit
    attestation.json
```

and a pinned `specimen_staging` manifest. The verifier independently requires set
equality among:

1. every specimen in the prediction commitment;
2. every manifest entry;
3. every directory in the single staging root;
4. every certificate specimen.

Each directory contains exactly the two named files. Missing, extra or duplicate IDs,
paths, directories or files fail. Both files are hashed, and the staged bitstream hash
must equal the certificate, attestation output and embedded source stamp.

For the published `clb_ff_config` commitment this rule means exactly 184 directories,
not “up to 184” and not a successfully built subset. The generic conformance fixture
uses four synthetic specimens so every rejection path can run without Vivado; a test
separately pins the public commitment's 184 unique IDs and 184/176/154 totals.

Consequently there is no such thing as a valid mine-only staging manifest for the
published commitment. Before holdout, the 23 mine attestations may be checked one by
one with the same attestation routine, and exact staging can be exercised against the
consumer's synthetic commitment. A reduced copy of `predictions.json` is forbidden:
it would create a second commitment-shaped artifact that could later be mistaken for
the public one. Formal staging is evaluated only when all 184 committed specimens
exist.

The verifier cannot observe a producer calling a Python function named
`verified_state()`. The contract therefore does not accept a `verified: true` claim.
It preserves and checks the completed source stamp, recipe and artifact hashes that
the function is supposed to validate. That is the strongest host-verifiable form of
the boundary.

## 5. Paths and portability

All artifact references in a certificate, staging manifest or attestation are
repository-relative: commitment, manifest, staged bitstream, attestation and recipe
source paths. Absolute references and `..` escapes are invalid.

Raw `recipe.tclargs[]` is different: it is an invocation record and may contain the
original absolute build-tree paths. No verifier treats those strings as artifact
locations. Preserving them verbatim does not make the certificate non-portable,
because every file the consumer opens has its own repository-relative reference.

## 6. Conformance falsifiers

`tests/test_round11.py` constructs a complete on-disk 1.6 fixture and verifies a
positive multi-cell record including a derived checkpoint chain. Independent
mutations require rejection for:

- a missing target cell;
- a preregistered semantic JSON pointer which does not exist;
- a locally self-consistent but cross-specimen-wrong derived source checkpoint;
- a substituted staged bitstream;
- missing, extra or duplicate staging specimens/paths;
- an incomplete source stamp;
- an extra file in a staged specimen directory;
- an absolute certificate artifact reference and a direct absolute-path call at the
  filesystem boundary.

Additional routed-fact fixtures exercise `latch`, `latch_base`, `zrst_AFF`,
`ce_tied`, `sr_tied`, and `async`. They pin the four-cell latch topology, LDCE latch
classification, FDSE set value, constant CE/SR detection and asynchronous reset
classification. Separate falsifiers remove LUT `LOCK_PINS`/pin mapping and break the
source-stamp bitstream link. These cases exist specifically so those rules cannot be
changed while the CLKINV/NOCLKINV fixture remains green.

The synthetic recipe input is the consumer-owned
`tests/fixtures/ff20_recipe_source.txt`; the known answer does not read or imitate the
producer's builder source. The older Run A and Run B production certificates continue
to validate under their original 1.2 and 1.4 contracts.
