# The formal FF converter and stager (producer side)

`scripts/gate_stage_ff_formal.py` turns what the builder wrote — `readback.tsv` +
`stamp.json` under `<build-root>/<site>/<variant>/` — into `specimen_attestation` 2.0.0
records, and stages the committed set in the layout certificate 1.6 consumes
(`<run-root>/specimens/<specimen_id>/{spec.bit,attestation.json}` beside a
`specimen_staging` 1.0.0 manifest — see "Layout" below for why the nesting is
load-bearing).

It is the answer to the last mismatch in the handoff: the builder's native layout is
`<site>/<variant>/`, and the measurement needs `<specimen_id>/` — which from 1.6 it no
longer knows how to spell, and reads only out of this manifest (§2b). Nothing else about
the build changes; in particular **no Vivado run is required**, because
`ff_formal_readback.tcl` already records every cell and pin fact 2.0 asks for and
`stamp.json` already *is* the `ff_formal_stamp/1` record the schema embeds.

## 1. Two modes, and why they are not one flag apart

```
scripts/gate_stage_ff_formal.py --build build/gate_ff_formal --instance SLICE_X2Y25 --check
scripts/gate_stage_ff_formal.py --build build/gate_ff_formal --stage staging/<run_id>
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

**The whole structural gate runs before anything is converted or written**, and
verification runs before any artifact is read. `--stage` calls the builder's
`structural_gate()`, which passes every node through `verified_state()` first and only
then opens readbacks, and it covers all three parts of `ready_for_measurement` —
verification, the committed pair gate and the derived gate — because enforcing a subset
of a conjunction enforces nothing. The identities it must cover come from the commitment,
so a report that lost records cannot pass by having every surviving record pass.

The run report is deliberately *not* consulted: a stager that trusted a producer-written
verdict would accept exactly the run this gate exists to stop.
On 2026-08-06 it would have, because `run_report.complete` meant "everything was built"
while one committed pair was structurally incomparable
(`evidence/ff_holdout_2026_08_06_t2fail/`). `--check` reports the same gate, and over a
complete scope its exit code follows it; over a half-built tree the pairs it cannot
compare are out of scope rather than failures — that selects which pairs are judged, it
never changes the rule.

### Layout: nested, and why the extra level exists

```
staging/<run_id>/
├── staging_manifest.json
└── specimens/
    └── <specimen_id>/
        ├── spec.bit
        └── attestation.json
```

`--stage` takes the **run root**. The consumer derives *its* staging root from the artifact
paths, so its root is `specimens/` — holding exactly the committed specimen directories and
no files — and the manifest is that root's sibling. Every reference inside the manifest
spells `specimens/<id>/…` verbatim and points at the final tree, never at the `.partial`.

This tool used to write the manifest **into** the root, and
`host/verify_certificate.load_feature_staging` requires the root it derives to contain only
those directories, so every staging it produced was uncertifiable. Nobody had staged for
real, so the two rules had never met; the 1.6 certifier's pre-emission verification is what
made them meet, answering:

```
CERTIFICATE VERIFY: FAIL — 1 finding(s)
  - staging root contents differ from committed specimen set (missing=0 extra=0 root_files=1)
```

Ruled nested 2026-08-10 rather than relaxing the verifier, which would have widened a
consumer rule to fit a producer habit. `tests/test_ff_stager.py` keeps both shapes as one
case: the staged tree is handed to `load_feature_staging` itself and must load with zero
errors, and the same artifacts with the manifest moved back inside the root must still
answer `root_files=1`.

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

## 2b. What consumes it: `gate_measure_ff.py` 1.6

The measurement is now the manifest's only reader, and it has no other door. There is no
`--build`: it cannot open a build tree, cannot join `<root>/<specimen_id>/spec.bit` and
does not create `run/attestations/`.

```
scripts/gate_measure_ff.py --run gate_runs/<run> \
  --staging-manifest staging/<run_id>/staging_manifest.json \
  --expect-sha256 <committed> --out gate_runs/<run>/measurement.json
```

That closes three things at once. The tool used to read artifacts no fresh clone has; the
`<specimen_id>/` layout it assumed was a **second naming rule** beside this one, free to
drift from it; and the attestation each record pointed at was a *copy the measurement
made*, so its hash described the copy. Certificate 1.6 requires the certificate's
attestation reference to equal the staging entry **verbatim**
(`load_feature_staging` compares the dicts), and a re-hashed copy in the run directory
can never satisfy that.

Before one frame is parsed, `load_staging()` establishes, independently:

* the manifest validates against `schemas/specimen_staging.schema.json` — fatal on its
  own, because every check below it reads named fields;
* its own sha256, **recomputed from the bytes** and carried into the measurement as
  `staging_manifest`, which the certifier then copies rather than re-deriving. The
  manifest and every attestation are **hashed and parsed in one read**: hash a path, then
  re-open it, and a swap in between yields a record pinning bytes nobody scored;
* the commitment it pins is the one being scored: hash equal to `predictions.json`'s, the
  path resolving to *that* file, and `schema_version`/`seed`/`totals` recomputed from the
  commitment document rather than read back from the manifest;
* **exact set equality with the 184 committed specimens** — missing, extra or duplicated
  ids each refuse, and so do two entries naming one file. That identity is decided on the
  **resolved** path: `d/spec.bit` and `d/./spec.bit`, or a symlink alias, are two
  reference strings and one artifact, which a string-keyed check would count as two
  staged specimens. The raw strings still travel into the record unchanged;
* every artifact hash recomputed from the staged bytes, every path resolved through
  `safe_child` (the schema's `repo_path` pattern already rejects `..` and absolute paths;
  the resolver catches the symlink that neither spelling shows). A bitstream is streamed
  rather than held — 184 of them — so `frames_of()` re-reads it and re-checks the pinned
  hash immediately before parsing, and hands the parser **those bytes** (`parse_frames(…,
  data=…)`) instead of a path it would read a third time;
* every staged **bitstream is what HEAD says it is**, read with `git cat-file` from the
  HEAD blob and never from the working file — a pointer-only checkout has bytes on disk
  that are not the bitstream, and a materialised one has the bitstream whatever HEAD
  holds, so neither is a witness for what a clone resolves. The blob must be a well-formed
  LFS pointer whose **oid equals the manifest's pinned sha256** (the oid *is* the content
  hash, so that equality is what ties the published object to the measured bytes), the
  path must be governed by the LFS filter, and `.gitattributes` — the file that decides
  that — must itself be in HEAD. An ordinary blob and a damaged pointer are reported as
  different things on purpose: one means the filter never ran, the other means the pointer
  was edited, and a pointer is required to be exactly `version`/`oid`/`size` in that
  order — nothing here produces extension fields, so one that appeared was written by
  something other than the filter this gate confirms ran. The other references are
  checked the other way round, and that set is **the manifest, the prediction commitment
  and every attestation**: a pointer standing in for any of them means a mis-scoped rule
  has moved reviewable evidence out of the repository. Which kind a reference is comes
  from the caller, not from a file extension the gate guesses at;
* every reference — the manifest, the commitment and all 184×2 artifacts — **published**:
  present in HEAD and identical to what is on disk. Tracked is not the property: a staging
  only `git add`ed, or committed and then edited, is tracked and is not what a verifier's
  clone would get. So the order is stage → **commit the staging** → measure. **Without git
  authority this refuses**, unlike the stager's `is_ignored()`, which guards against a
  mistake before evidence exists; here the answer *is* the evidence. A cold `git archive`
  export can exercise the function against a scratch repository and can never satisfy it,
  so such an export cannot produce a measurement — intended, not incidental.

  "Identical to HEAD" means two different things by file kind, and the distinction is not
  cosmetic (§2c). For the manifest, the commitment and every `attestation.json` — ordinary
  Git files — **the HEAD blob is those bytes**. For `staging/**/*.bit` under Git LFS, HEAD
  holds a *pointer*, and the property wanted is that the pointer's oid reconstructs exactly
  the working bytes the measurement hashed.

  Which check establishes which part matters, because they are not interchangeable:

  * `git ls-tree HEAD` — the path **exists in HEAD**;
  * `git diff HEAD` — Git's own view, filters included, shows **no uncommitted drift**;
  * the **working bytes' SHA-256 against the manifest pin** — and this is the only one of
    the three that shows the tree actually **has the bitstream** rather than a pointer.

  A pointer-only checkout is the case to keep in mind: with the filter configured but the
  objects never fetched, `git diff HEAD` is generally **clean**, because what it compares
  is the cleaned working file against the pointer blob, and cleaning a pointer yields that
  pointer. So `git diff` does *not* prove materialisation and must not be read as proving
  it. What refuses such a tree is the hash comparison — a pointer file is 130-odd bytes and
  does not hash to the pinned bitstream — which `load_staging()` already performs on every
  artifact, and which `frames_of()` repeats before parsing;
* per specimen, that the staged record describes *that committed specimen*: id, variant,
  instance, build seed, completion, and both bitstream hashes. Whether the routed facts
  rebuild is `ff_formal_attestation_errors`' question and the verifier asks it — a
  producer-side imitation of the consumer's rule in this path could only drift.

Any of those refuses the **whole run before anything is written**: a measurement over the
specimens that happened to verify would carry the accounting of a complete one.

## 2b-ii. And what certifies it: `gate_certify_ff.py` 1.6

```
scripts/gate_certify_ff.py --run gate_runs/<run> --out gate_runs/<run>/certificate.json
```

**Only a `gate_measurement` 1.6.0 is accepted** — an equality, not a floor. A 1.4 or 1.5
record is refused however consistent it is, because consistency is all it can ever
demonstrate: it was produced by a tool that built its own artifact paths under a gitignored
tree and copied attestations into the run directory, and no field inside such a record
shows that. The version is the only honest discriminator.

The `staging_manifest` object is **copied from the measurement**, deep-copied and never
rebuilt from its parts, while the certifier independently re-resolves it, re-reads it in
one read, recomputes its sha256 and re-validates it against the schema. Copying rather
than reconstructing is load-bearing: a rebuilt reference would silently drop anything the
certificate cannot express, and dropping evidence is a producer deciding what evidence
means. Everything else is cross-checked rather than believed — the commitment recomputed
from `predictions.json`, the specimen set required to equal *both* the manifest's and the
commitment's, every `bitstream`/`attestation` reference required to equal its manifest
entry field for field (the verifier compares those dicts for equality), and every
specimen's site/tile/split/build seed recomputed from the committed plan.

A certificate carries **no bitstream path**. The pinned staging manifest is the path
authority and each specimen carries only `bitstream_sha256`; the certifier has already
required the measurement's full bitstream reference to equal the manifest entry, so a
second copy of the path in the certificate would be a redundant field that can drift from
the one that matters. Ratified 2026-08-10.

Finally, **the candidate is verified by the real consumer before it is put in place**:
`host/verify_certificate.py --require-production` runs against a `.candidate` file, and
only a certificate it accepts is renamed into position. A rejected one leaves nothing —
not a draft, not a `.rejected`. That check is what found the two contract breaks recorded
here: the staging-root layout above, and `design_source_sha256`.

**`design_source_sha256`, ruled (2026-08-10, user): kept, and defined.** Certificate 1.6
requires it on every specimen while a `specimen_attestation` 2.0 has no
`inputs.design_sha256` — 2.0 replaced the single design input with a recipe `sources` map.
For 2.0 / `ff_formal` the field is now defined as **the SHA-256 of the single `.v` source
in `source_build.recipe.sources`**, and the producer's "exactly one, or refuse" rule is
accepted. The consumer half is **not done and must land before staging**: the verifier has
to **independently recompute** that value and compare it, not merely check the field's
format, with three fixtures that must all FAIL —

1. a certificate whose `design_source_sha256` differs from the single `.v`'s hash;
2. a recipe with **no** `.v`;
3. a recipe with **two**.

## 2c. The 365.7 MiB question, ruled: LFS for `.bit`, ordinary Git for everything else

Requiring publication has a price, and it is not small: the committed set is **365.7 MiB**
of bitstream that has to enter the repository before a measurement may read it.

**Ruled (2026-08-09, user): keep certificate 1.6's repo-relative artifact model; carry the
`.bit` files in Git LFS.** The manifest, the attestations, the measurement and the
certificate stay ordinary Git files — they are what gets reviewed and diffed. Nothing in
any schema changes: the materialised working-tree paths are the same paths and the SHA-256
values are the same values, which is why this is a storage decision and not an evidence
one.

**None of it is implemented yet, and formal staging is blocked until it is.** What has to
land, deliberately as its own change rather than folded into the measurement:

1. a `.gitattributes` scoped to **`staging/**/*.bit` only** — no repository-wide rule;
2. the stager and the publication gate refuse a staged bitstream that did **not** go
   through the LFS filter, so a misconfigured tree cannot quietly push 366 MiB of ordinary
   blobs into history — the one mistake that cannot be undone by a later commit;
3. the measurement keeps verifying the **working bytes'** SHA-256 (it already does — and
   that is the check that distinguishes a materialised bitstream from a pointer), and
   **must** additionally check that **HEAD's LFS pointer oid sha256 equals the manifest
   pin**. Not "should": without it, HEAD could name a different object than the one on
   disk while both the ls-tree and the diff look right;
4. acceptance is a **fresh clone that actually materialises LFS**, re-hashes all 184
   artifacts and runs the verifier — not a clone that resolved pointers to nothing;
5. if remote LFS is unavailable, **stop**. The fallbacks are both forbidden: untracked
   staging (a measurement no verifier can repeat) and ordinary giant blobs (unrecoverable
   history). The next move in that case is the consumer's — change the artifact model.

### What has to land before a staging may be published, as of 2026-08-10

Three items, **one still open**, and staging is blocked until all three are done and
cross-reviewed:

* ~~**consumer** — independent recomputation of `design_source_sha256` plus the three
  failing fixtures (§2b-ii)~~ **done** (`acd7e05`);
* ~~**producer** — the nested staging layout (§1)~~ **done**;
* **both** — the Git LFS policy: ~~the pointer-oid gate~~ **done** (measurement side,
  above; exercised against real local LFS repositories), ~~and remote availability~~
  **answered 2026-08-10** — a one-off throwaway branch pushed a 2.2 KB object, the remote
  accepted it, and a fresh clone materialised it back to the exact bytes
  (`evidence/lfs_remote_probe_2026_08_10/`), so the ruling's "stop and hand back" branch
  is not taken. Still open: this repository's own `.gitattributes`, and the **fresh-clone
  materialisation acceptance for the real set** — 184 artifacts, 365.7 MiB, re-hashed with
  the verifier run against them.

  The probe also produced the empirical form of the §2b correction: in a pointer-only
  clone the path is in HEAD, `git diff HEAD` is **clean**, and the pointer gate passes,
  while the working file is 129 bytes of pointer text. Only the working-bytes hash against
  the manifest pin refuses that tree.

Measurement is not authorised either, and none of this authorises it.

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
* `tests/test_ff_stager.py`: 58 cases, all synthetic except one clearly named
  artifact-dependent case, so the suite runs on a cold checkout. Two of them cost
  nothing and pin what a docs command line assumes: the tool carries a shebang **and**
  the executable bit, and `scripts/gate_stage_ff_formal.py --help` actually runs. Mode
  `100644` makes every command line in this file exit 126.
* 34 adversarial mutations of this tool and the shared gate, **33 caught** — including
  reading a readback while verification is failing, ignoring the required identity set,
  tolerating duplicate or miscounted records, dropping the derived half of the
  conjunction, and an exit code that follows build completeness. The survivor — filling
  `requested` from the readback — is an equivalent mutant while the three drift guards
  stand, because they make the two values provably equal; `test_requested_is_the_plan_
  intent_spelled_out` exercises the intent path on its own so the table cannot move
  unnoticed.

The measurement also stopped keeping every parsed bitstream. 365.7 MiB of `.bit` becomes
several GB once parsed — ~20 MB of Python objects per specimen, times 184 — and the old
unbounded dict simply never met a set this size. `FrameCache` is a small LRU (4), sized so
both endpoints of the pair under comparison stay resident and the shared baseline survives
across an instance; the footprint is now a constant that does not move when the committed
set grows. Eviction is also a small integrity gain: a re-parse goes back through the same
loader, so the pinned-hash check covers every use of a specimen rather than the first.

For the consumer side of §2b, `tests/test_ff_measure_staging.py`: **45 cases**, every one
synthetic — no real bitstream is touched, because measuring the committed 184 is not
something a test may decide to do. The bitstreams in those fixtures are deliberately not
bitstreams, so a case that started to reach frame parsing would fail loudly rather than
quietly measure something. Five cases run `main()` end to end with frame parsing stubbed,
which is what pins the record shape: `schema_version` 1.6.0, the `staging_manifest`
reference, and each specimen's `attestation`/`bitstream` reference equal to the manifest
entry. The publication check runs against **purpose-built scratch repositories** rather
than this one, so its four states — clean HEAD, index-only, edited-after-commit, no git —
are real git answers that still run from a cold checkout. Three tamper hooks cover the
windows a single pass cannot: a file rewritten during the read (the parse must see the
verified bytes), a bitstream swapped between `load_staging` and scoring, and a bitstream
swapped while it is evicted (refused on its next use). The cache bound is held to be a
memory decision and not an evidence one by running one committed set twice — once with
room for every specimen, once with a cache small enough to evict on nearly every access —
and requiring the two measurements to be equal. **26 adversarial mutations, all caught.** One
further mutation is kept out of that count and left alive on purpose — keeping an
attestation that failed its own identity checks. It is equivalent while any problem
refuses the whole run, and is commented as such in the source rather than removed: it
becomes reachable the moment one of those refusals is softened into a report.

The certifier's own cases are `tests/test_ff_certifier.py`: **21**, every bundle built by
the **consumer's** `Feature16Bundle` and every happy path confirmed by running
`host/verify_certificate.py --require-production` on what the certifier emitted. The old
1.4 certifier fixture in `tests/test_ff_plan.py` survives only as a refusal — bumping its
version so the old shape passed would have deleted the evidence that the gate exists — and
the semantic isolation it used to cover is re-established on a real 1.6 bundle with a
genuine attested mismatch, where `status` stays `passed` while `semantic_status` fails.
**21 adversarial mutations of the certifier, all caught**, including a floor instead of an
equality, a rebuilt staging reference, and a candidate written without verification.

Two operational consequences worth stating plainly rather than discovering later. The
staging must be **committed before it can be measured** — that is what "published" means
above, and it is a real cost: 184 bitstreams, 365.7 MiB, enter the repository, which is
what §2c rules on. And measuring is still not authorised: this contract says what a
measurement would have to satisfy, not that one may run.

Holdout stays where it was: the 161 unbuilt specimens are not authorised by this tool
existing. What it removes is the excuse that the staging format was unknown.
