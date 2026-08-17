# Location sweep: where did the ICAP write land?

Specification only. **No board action is authorised by this document**, and none of the five
steps is authorised by the authorisation of any other.

**Amended 2026-08-17: the target semantics below are implemented.** The two conflicts recorded
in the next section are closed in `board_signature_search.py/2.8.0` — all sixteen controls are
read in every case and 16/16 is required before any location verdict, the intended hit included
— with four new behavioural mutants and the offline judging path changed to match, so
`--judge-only` cannot re-license what the acquisition refused. The prerequisites and the five
steps are unchanged, and **still unauthorised**. The recomputed identity is pinned below.

This is the measurement Phase 2 attempted and could not make. What has changed since is not
the question but the instrument: R4 restores a post-fault readback, reproduced across two
independently built faults, so a "not found" taken after a fault can now be made to mean
something — provided the controls prove it in the same acquisition that reports it.

## The two conflicts with the tools as they were, read out of the source

The first draft of this specification described a procedure the code did not implement. Both
gaps were found in review and confirmed here against `scripts/board_signature_search.py`; both
are **closed as of 2.8.0**, and the description is kept because it is what the four R4
acquisitions and the whole Phase 2 record were taken under.

**1. A full sweep is the exception, not the rule.** `run()` reads the intended FAR first and
then branches on what it holds:

| `A20` holds | what actually happens today |
|---|---|
| the candidate | line 736 skips the control block **entirely** — `control` stays `None` and `WRITE_LANDED_AT_THE_INTENDED_FAR` is emitted **with no control read at all** |
| neither base nor candidate | controls are read until the first one matches, then `break`; the sweep never starts |
| the base | controls are read until the first match, and only then do the remaining FARs get read |

So "the sweep reads all 5,144 frames" is true in one case out of three, and the intended-hit
case — the most consequential verdict the tool can emit — is the one with the least evidence
behind it.

**2. One control is enough to license a location verdict.** `judge_positive_controls()`
returns `INSTRUMENT_VALID` on `if matched:`, and that branch does not look at `missing` at
all. Fifteen wrong and one right passes; so does **one right and fifteen never read**. The
docstring says so on purpose ("One exact known-nonzero frame is sufficient"), so this is a
design decision to be revisited, not a bug to be quietly patched.

The four R4 acquisitions were in fact 16 of 16 — that is a counted fact in their readings, and
the step ③ reading already noted that the verdict file's own wording was the weaker "at least
one". The point here is that the tool would have accepted 1, and a location verdict is a much
stronger claim than an instrument check.

## Target semantics — implemented in 2.8.0 on 2026-08-17

* **`A20` is always read first**, unchanged.
* **All sixteen controls are read, and 16/16 exact is required, before *any* location verdict
  is emitted — including `WRITE_LANDED_AT_THE_INTENDED_FAR`.** An intended hit is a location
  claim like any other and does not get an exemption for being convenient.
* `A20` = candidate → `A20` + 16 controls, then stop and adjudicate.
* `A20` = neither → `A20` + 16 controls, then stop; recorded as the third state.
* `A20` = base **and** controls 16/16 → continue and complete the remaining frames.
* Controls not 16/16, in any of those cases → no location verdict, and the sweep does not
  start.

**Version, digest and mutants.** Implementing this changed the file, and `instrument_digest()`
hashes the file's own bytes, so both mode digests changed as predicted. The values this
document quoted in its first draft — control-only `452afe50…2a9a`, signature-search
`7701f39d…f0d0` — were **2.7.2's** and are not this procedure's identity. **This procedure's
identity, recomputed at implementation time on 2026-08-17 and pinned in
`tests/test_board_signature_search.py`:**

```
board_signature_search.py/2.8.0    child probe_jtag_config_read.py/2.4.0

control-only      49c8dbcebbcb7c7557a8f5e56ee4b32d770037f9e70a98544e8142d3f3336fa6
signature-search  a20e56aae879812d9ed2960ec55ac8b1b3f57710411cf40da0cc32b1855aa95d
                  (5,144 admitted FARs)
```

Both are new, so **step ① is the fresh-load control for this identity and nothing earlier can
substitute for it** — least of all the four R4 acquisitions, which are `2.7.1` / `8d28dcf3…`.
The two modes remain two instruments: a 16-frame control-only acquisition can never be the
control for a full sweep. Any further edit to the tool makes a third identity; the pin is a
test, so it fails rather than drifts.

New mutants, all four implemented and killed behaviourally in
`scripts/mutate_signature_search.py` (25/25):

* an intended hit that reaches a location verdict without the controls — split into two, because
  the defect had two halves: `intended_hit_reads_no_control` (never reads them) and
  `intended_hit_ignores_failed_controls` (reads them, reports the hit anyway);
* a verdict accepting one matching control instead of sixteen — `one_matching_control_is_enough`;
* a verdict accepting fifteen read controls and one unread —
  `unread_controls_simply_do_not_count`;
* a sweep that starts before the controls have all passed —
  `sweep_starts_before_the_controls_pass`, killed by the FARs it reads, not by its verdict.

Each is killed **behaviourally**, by driving the module and reading the verdict or the read set —
a string search would prove nothing about control flow. Two pre-existing mutants
(`defer_the_intended_decision`, `neither_bypasses_control`) and two anchors had to be re-pointed
at the new shape rather than loosened, and `missing_not_attempted_means_complete` needed a larger
read budget to reach the coverage arithmetic at all now that the control block precedes it.

An audit by the other author is still owed on this implementation, and this document still
authorises no board action.

## Prerequisites — settled before any board action, because they cannot be settled after

A sweep's raw output is **15,432 files = 5,144 × (capture + child log + Tcl)**; with
`index.json` and `verdict.json` the directory holds **15,434**. Phase 2's is exactly that, and
its current state is **10 tracked + 15,424 untracked**, 124 MB. This procedure produces two
more such sets, so doing it first would mean three sets and a debt.

**P1. Phase 2's loose files leave the working tree.** *Moved*, never `.gitignore`d — hiding
124 MB behind an ignore rule is the same weight with less honesty. What stays tracked is the
established shape plus one addition: `index.json`, `verdict.json`, the four candidate-FAR
captures with their child logs, **and the sixteen controls**. The controls license the
verdict, and a reader should not have to unpack an archive to check them.

**P2. An off-box copy of the archive exists.** `/home/test/fabricmap_archives` and `…_2` are
both on `/dev/sdc`: two files, not two stores, as the existing manifest already admits.
**A destination has to be chosen before P1 runs** — moving the loose files while the only
archive lives on one disk would be the worst moment for that disk to fail.

**P3. The pipeline is exercised end to end on Phase 2's set first.** Archive → verify by
extraction → `validate_index` over the extracted tree → move → confirm the tracked files
survive. A first use of an archival process on irreplaceable new evidence is not a process.

## What gets kept, and what gets archived

Per sweep, **committed**: `index.json`, `verdict.json`, the intended FAR and its neighbours
(`0x00400a20`–`0x00400a23`) and the sixteen control FARs — each as capture + child log + Tcl —
plus `archive_manifest.json` and `reading.md`.

Everything else is **archived** under the existing schema (`phase2_raw_archive`, generalised:
keep the field names, bump `schema_version`), with the determinism the Phase 2 archive already
demonstrates:

```
tar: posix, sorted, mtime 1970-01-01Z, uid/gid 0     then zstd -19
manifest records: sha256, bytes, file count, contents breakdown,
                  binds_to {commit, plmark, index_sha256, instrument_digest},
                  verified {extracted_files, validate_index_accepted, missing, tcl_digests},
                  copies[] and an explicit copies_caveat if they share a filesystem
```

**Order is fixed:** archive → verify by extraction → `validate_index` → *then* move. Nothing is
deleted; "cleanup" means the files live at a named path outside the repository, recorded in the
manifest.

## The five steps

### ① Fresh load, full acquisition — the negative control

Physical power cycle, then `precheck_fresh_power.py/1.0.1`. Canonical `carrier.bit`
`8c3369e8…` loaded once onto an empty PL, **no transaction of any kind**, then one
signature-search acquisition.

Two things must both hold, pre-registered here rather than read off afterwards:

* **the sixteen controls pass, 16/16** — the instrument is valid in full mode;
* **the candidate signature is absent** wherever the acquisition looked.

**If the candidate signature is present before any transaction, the procedure is over.** The
signature would not be diagnostic of the write, and no step ④ result could be attributed to
it. That is a stop, not a puzzle to reinterpret.

On a fresh load `A20` should hold the base, so this step is expected to complete the full
5,144. If it does not, that itself is the finding, and it stops here.

### ② Physical power cycle

Not optional. Step ① has read the device thousands of times.

### ③ Build the specified fault

`precheck_fresh_power.py`, then `board_claimb_postfault_capture.py/1.0.0`. The only acceptable
outcome is the one produced four times now: `round.steps` exactly `[no_op: passed,
known_answer: stopped]`, pass 1 completing all three envelopes, pass 2 stopping in envelope 0,
`STATUS 0x04040082` / `FAULT 0x8`, `CTRL_ARM` and `CTRL_MODE_HOLDOUT` clear in every CTRL
write, `same_boot` passed, no reboots, `PCAP_PR` restored — reconstructed from
`instrumentation.commands`, since `AxiRefusal` still does not attach the partial record.

Anything else stops the procedure.

### ④ The acquisition, in that same boot

One signature-search acquisition, `--plmark` the fault boot's marker. No `--max-reads`: a
capped acquisition cannot produce a "not found".

How far it runs is a **result, not a requirement**. Under the target semantics it reads `A20`
and the sixteen controls in every case, and completes the remaining frames only when `A20`
holds the base and the controls are 16/16.

### ⑤ Verify the instrument before reading the verdict

Checked against step ①, **before** the location verdict is looked at:

```
identical instrument_digest (the implementation's, recomputed and pinned then)
identical parent and child versions
identical admitted 5,144-FAR authority, in the same order
child Tcl byte-identical for every FAR the two acquisitions BOTH read
plmark unchanged across the acquisition
```

The Tcl comparison is over the children actually run in common. Requiring 5,144 Tcl files from
step ④ would contradict the semantics above, under which a legitimate early stop is one of the
possible answers.

A pair that is not one instrument decides nothing, and neither does an acquisition whose
controls failed within it.

## Reading the outcome

| ④ | reading |
|---|---|
| controls not 16/16 | **the acquisition answers nothing.** This is Phase 2's failure mode, and it stays a live possibility: R4 is demonstrated on sixteen frames, twice, **not** on 5,144 |
| controls 16/16, `A20` = candidate | **the write landed at the intended FAR** — and now, unlike today's tool, with sixteen controls behind it. First location evidence in this line; needs independent reproduction before it is a location |
| controls 16/16, `A20` = neither | the third state: `A20` holds something that is neither base nor candidate. Recorded, not interpreted; it is not a location |
| controls 16/16, `A20` = base, signature at exactly one other FAR | **the write landed there.** Needs independent reproduction |
| controls 16/16, `A20` = base, signature at several FARs | not a location; record every FAR and stop |
| controls 16/16, `A20` = base, signature absent from all 5,144 | the write did not land anywhere the readback can see — a real answer, and a different one from Phase 2's void `NOT_FOUND_COMPLETE`, **because the controls passed in the same acquisition** |
| any missing frame, child failure, marker mismatch, bookkeeping anomaly | not interpretable; stop and keep everything |

`CONFIG_STATUS` takes no part. It has been refuted three times as a validity proxy.

## Standing limits

Each step runs **once**. No retries, no resumes of an earlier directory, no second acquisition
on a disturbed state, no mutation, no arm, no scoring. Any fault, reboot, marker mismatch,
child failure or evidence anomaly stops the procedure where it happened, with the evidence
kept.

Whatever ④ returns, the procedure ends there. What a single-FAR hit would unlock — reading the
map at that location, or a second transaction to confirm it — is a separate design and a
separate authorisation, and is not implied by success here.
