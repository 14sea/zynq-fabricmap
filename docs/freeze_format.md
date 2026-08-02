# Freeze format — `prjxray_subset_spec` 1.0.0 / `frozen_db_subset` 1.1.0

> `frozen_db_subset` 1.1.0 is a MINOR bump over 1.0.0: it adds `files[].classified`
> and `totals.provenance_features`. Both are additive; a 1.0.0 consumer stays valid.

The contract for `data/`. Written so a second author can build verifiers, fixtures
and the certificate consumers against it without reading the extractor.

Two documents, one generator:

```
data/subset_spec.json   (input,  schema prjxray_subset_spec 1.0.0)   hand-maintained
        |
        |  scripts/extract_prjxray_subset.py --src <prjxray-db>
        v
data/prjxray/**         verbatim upstream bytes, at upstream paths
data/MANIFEST.json      (output, schema frozen_db_subset 1.0.0)      generated
```

Versioning follows the house policy from `zynq-autoehw/docs/schema.md`: MAJOR = an
incompatible field change, MINOR = an additive optional field. A consumer must
reject a MAJOR it does not support and must ignore unknown fields within a MINOR.
The extractor enforces this on the spec it reads (`SUPPORTED_SPEC_MAJOR`).

---

## 1. `prjxray_subset_spec` — what gets frozen

Top level: `schema`, `schema_version`, `spec_id`, `source`, `target`,
`cross_family_reference`, `groups[]`, `bit_classes[]`, `unclassified_policy`,
`notes[]`.

**`groups[]`** — a set of upstream files that share a role.

| field | meaning |
|---|---|
| `id` | referenced by `bit_classes[].from_groups` |
| `tier` | `content` \| `routing` \| `geometry` \| `provenance` — the board-risk tier, not a directory |
| `role` | `segbits` \| `ppips` \| `mask` \| `geometry` \| `part` \| `index` \| `provenance`; drives parsing |
| `cross_family_check` | if true, each file is compared against its artix7 counterpart at extraction time |
| `files[]` | paths **relative to the prjxray-db root**, reproduced verbatim under `data/prjxray/` |
| `rationale` | why this repo needs it (required — an unexplained file does not get frozen) |

**`bit_classes[]`** — the taxonomy. A class is a *predicate over feature names*, not
a set of files: one `.db` file contributes to several classes.

| field | meaning |
|---|---|
| `id` | class name; the unit of certification |
| `tier` | `content` (a wrong write is logic garbage) or `routing` (contention-capable) |
| `priority` | certification order; 1 first |
| `from_groups[]` | scopes which files the regex is applied to |
| `feature_regex` | anchored regex over the full feature name (e.g. `CLBLL_L.SLICEL_X0.ALUT.INIT[0]`) |
| `board_safety` | free text, but it is what decides which board a class may ever be exercised on |

**Which files participate in classification (normative).** A group lists both the
rule files and their `*.origin_info.db` companions, but **only files with
`role: segbits` or `role: ppips` that are not `*.origin_info.db` contribute features
to the taxonomy.** The other two kinds are frozen for provenance and diffing, not for
counting:

- `*.origin_info.db` restates its parent file's feature set with an added
  `origin:<fuzzer>` token. Counting it double-counts the taxonomy.
- `role: mask` files have no features at all; their lines are `bit <F>_<B>`.

Every `.db` record in the manifest carries an explicit `classified: true|false` so
this rule is machine-readable and not a matter of reading prose. `totals` reports
`classified_features` and `provenance_features` separately; for the current freeze
they are 10,896 and 10,038, and their sum, 20,934, is the count of all feature lines
in the frozen `.db` files — **not** the size of the taxonomy.

**Invariants the extractor enforces**

1. **Partition, not tagging.** Within a group, a feature matching two classes is a
   fatal ambiguity — fix the spec, do not add precedence rules.
2. **Total coverage.** With `unclassified_policy: fail` (the default), a feature in a
   classified file that matches no class aborts the extraction. This is what makes a
   narrow subset valuable: the frozen set is fully understood, or it does not freeze.
3. **Verbatim.** Files are copied byte-for-byte. Any transformation belongs in a
   derived artifact, never in `data/prjxray/`.

Adding a tile class (IOB, BRAM, DSP …) = add a group, add the classes covering every
feature in it, re-extract. That is a MINOR spec bump.

## 2. `frozen_db_subset` — what was frozen

| key | contents |
|---|---|
| `spec` | path, `spec_id`, version and **sha256** of the spec that produced this manifest |
| `target` | family / device / part / board |
| `source` | spec's source block **plus** extraction-time git provenance: `commit`, `commit_date`, `remote`, `worktree_clean` |
| `cross_family_check` | `files_checked`, `byte_identical`, `rule_equivalent_only`, `differing[]` |
| `device_summary` | `tiles_total` + full tile-type histogram, parsed from the frozen `tilegrid.json` |
| `consistency` | `unclassified_features` (must be 0), `origin_info_feature_mismatch[]`, `origin_info_empty_upstream[]` |
| `bit_classes[]` | per class: `entries`, `distinct_features`, `tile_types[]`, `sample_features[]`, and a `certification` slot |
| `files[]` | per file: `path`, `source_path`, `group`, `role`, `tier`, `sha256`, `size_bytes`, `lines`, `classified`, `features`, `bit_classes{}`, `cross_family{}` |
| `totals` | `files`, `bytes`, `classified_features`, `provenance_features` |
| `freeze_stamp` | UTC time of extraction — **the one volatile field** |

**Cross-family semantics.** `identical` is a byte comparison. When bytes differ, `.db`
files get a rule-level comparison (`rule_equivalent`, `only_here`, `only_there`,
`conflicting_payloads`, `examples`) computed after dropping `origin:<fuzzer>`
provenance tokens — which fuzzer emitted a rule is not a rule difference. Only
genuine rule deltas land in `cross_family_check.differing[]`. Current state and its
interpretation: `data/README.md`.

## 3. `--verify`, and what it deliberately ignores

`scripts/extract_prjxray_subset.py --verify` rebuilds the manifest **from `data/`
alone** — no prjxray-db, no Vivado — and reports drift. It detects: a changed byte in
any frozen file, a file missing from `data/`, a file present in `data/prjxray/` but
not in the manifest, a count/histogram/classification that no longer matches, and a
`subset_spec.json` edited after the freeze.

It ignores three things by construction, because they are not knowable from `data/`:

- `freeze_stamp`;
- the extraction-time git provenance inside `source` (`path`, `commit`,
  `commit_date`, `remote`, `worktree_clean`);
- `cross_family_check` and the per-file `cross_family` blocks.

To re-establish those, run a real extraction against a prjxray-db checkout; the
provenance fields are then re-derived rather than trusted.

`--verify` also does **not** compare the `certification` slots (§4) — those are
written after the freeze, by a different tool.

## 4. The certification slot — handoff to the prediction gate

Each `bit_classes[]` entry carries:

```json
"certification": {"status": "uncertified", "gate": null, "certificate": null,
                  "tp": null, "fp": null}
```

`status` ∈ `uncertified` | `certified` | `failed` | `not_applicable`. The
specimen-diff prediction gate (mine → holdout → emit → fresh-gold, TP=1 / FP=0,
ported from the EP4CE6 campaign) is what writes it: `gate` names the gate run,
`certificate` points at the standalone certificate file, `tp`/`fp` carry its
accounting.

**Staleness rule.** A certificate pins the `spec.sha256` and the `sha256` of every
frozen file it consumed. A re-extraction resets the slots to `uncertified`; a
certificate whose pinned hashes do not match the current manifest is stale by
construction and must not be honoured. The manifest slot is a convenience pointer —
the certificate itself is the authority, and the frozen db is only an index.

Certified classes are what instantiate `local_map` (`zynq-autoehw/docs/schema.md`
§3): a class certificate is the evidence behind a token's `symbolic` field, while
`spatial_scope` comes from the frozen `tilegrid.json`. That link is the Claim B
foundation; it is not implemented yet.

---

## 5. Bit address arithmetic (normative)

`feature name + tile instance -> absolute configuration bit` is shared contract, not
an implementation detail: the gate and any independent fixture must compute the same
address or neither can adjudicate the other. This section is the specification both
sides code against. **It is a shared *contract*, not a shared implementation — an
independent fixture reimplements it from this text and the frozen data, never by
reading `scripts/`.** Every constant below was read out of the frozen files; the
commands are given so it can be re-derived rather than believed.

### 5.1 Inputs

- `data/prjxray/zynq7/segbits_<tiletype>.db` — lines `FEATURE <tok> [<tok> ...]`,
  each token `[!]<F>_<B>`.
- `data/prjxray/zynq7/mask_<tiletype>.db` — lines `bit <F>_<B>`, same coordinate
  space, no feature and no polarity.
- `data/prjxray/zynq7/xc7z010/tilegrid.json` — per tile instance:
  `bits.<block>.{baseaddr, frames, offset, words}`.

### 5.2 Block selection

Every tile in the frozen subset exposes exactly one block, **`CLB_IO_CLK`** — the
configuration-array block. Use it unconditionally for `CLBLL_*`, `CLBLM_*`, `INT_*`.
(`BLOCK_RAM`, the separate BRAM-content array, appears only on BRAM tiles, which are
not in this subset. If a future group adds them, block selection becomes a real
decision and this section gets a MAJOR bump.)

### 5.3 The mapping

For tile instance `T` and segbit token `[!]F_B`:

```
blk  = tilegrid[T].bits["CLB_IO_CLK"]
FAR        = int(blk.baseaddr, 16) + F        # requires 0 <= F < blk.frames
word_index = blk.offset + B // 32             # word within the 101-word frame
bit_index  = B % 32                           # LSB-first within that word
expected   = 0 if the token was "!"-negated else 1
```

A feature is **asserted** iff *every* non-negated token's bit is 1 **and** *every*
negated token's bit is 0. Polarity is part of the prediction: a certificate that
records only a bit set, without the expected value per bit, cannot express what
`INT_L.BYP_ALT0.FAN_BOUNCE2 21_07 !22_07 23_07 24_07 25_07` actually predicts.

### 5.4 Constraints, and what they are worth

Read off the frozen data (`data/prjxray/zynq7/`), so a fixture can assert them:

| constraint | value | how to re-derive |
|---|---|---|
| block, all frozen tile types | `CLB_IO_CLK` only | keys of `bits` in `tilegrid.json` |
| `words` per tile | 2 → `0 <= B <= 63` | `tilegrid.json`; max `B` seen is 63 |
| `frames` per tile | CLB 36, INT 28 | max `F` seen is 35 (CLB) / 25 (INT) |
| `offset` values | `0,2,…,48, 51,53,…,99` | 50 distinct values, 108 tiles each |
| negated tokens exist | 3264 in `segbits_int_l.db` alone | count tokens starting `!` |

**`offset` already skips frame word 50** — the observed jump 48 → 51 is the clock-row
word, and `tilegrid.json` has accounted for it. Do not apply a second skip. Likewise
`baseaddr` already encodes block type / half / row / column: add `F` to it, never
re-derive it from the grid coordinates.

### 5.5 Site to feature prefix

CLB feature names are tile-local (`CLBLM_L.SLICEM_X0.…`), while a Vivado constraint
names a device site (`SLICE_X8Y0`). The mapping is positional: within a tile's `sites`
dict, the site with the **lower X** is index 0 and the higher X is index 1, and the
`SLICEL`/`SLICEM` token must match that site's type. Example from the frozen grid:
`CLBLM_L_X6Y0` has `SLICE_X8Y0: SLICEM` and `SLICE_X9Y0: SLICEL`, so `SLICEM_X0` is
`SLICE_X8Y0` and `SLICEL_X1` is `SLICE_X9Y0`.

### 5.6 Frame geometry, and what is *not* yet certified

A 7-series configuration frame is 101 words × 32 bits, word 50 being the clock row.
That is the only claim in this section not derivable from the frozen data alone — it
comes from UG470 and from the whole `zynq-xpart` ICAP line working. The frame layout
is what the first specimen run measures, and a fixture may treat it as an assumption
to be discharged rather than as established fact.

Everything above describes an address. **Nothing in this section is evidence that the
bit at that address means what the feature name says** — that is exactly what the
prediction gate is for, and why prjxray stays an index until a certificate exists.
