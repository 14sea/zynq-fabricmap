# Freeze format — `prjxray_subset_spec` 1.0.0 / `frozen_db_subset` 1.0.0

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

**Invariants the extractor enforces**

1. **Partition, not tagging.** Within a group, a feature matching two classes is a
   fatal ambiguity — fix the spec, do not add precedence rules.
2. **Total coverage.** With `unclassified_policy: fail` (the default), a feature that
   matches no class aborts the extraction. This is what makes a narrow subset
   valuable: the frozen set is fully understood, or it does not freeze.
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
| `files[]` | per file: `path`, `source_path`, `group`, `role`, `tier`, `sha256`, `size_bytes`, `lines`, `features`, `bit_classes{}`, `cross_family{}` |
| `totals` | files, bytes, classified features |
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
