# Request: authorisation to run the location sweep (spec steps ①–⑤)

The procedure asked for here is the one already specified in `claimb_location_sweep_spec.md`,
which this document does not amend, relax or reinterpret. If the two ever disagree, the spec
wins.

Written 2026-08-20, after the other author's audit of `board_signature_search.py/2.8.0` closed
and the commit was pushed (`034536b`, `origin/main`); revised the same day after his review of
this document found six defects, one of which — a duplicate carrier load in step ③ — would have
made step ③ fail on contact.

## 0. Authorisation state (user ruling, 2026-08-20)

**Step ① is authorised. Steps ②–⑤ are not, and are still the request half of this document.**
The ruling, in its own terms:

* ① only, deliberately: it is R4's first run at 5,144 frames, and its result *and its archival*
  are to be read before ②–⑤ are ruled on;
* this revised document is to be reviewed and pushed **before** ① starts;
* the evidence root `evidence/location_sweep_<D>/` is approved;
* a GitHub release asset as the off-box archive is approved, with the archive order extended by
  an **upload/download byte comparison** (§6);
* two power cycles are accepted by the design; **only the first — before ① — is enabled now.**
  The current post-fault state has no value worth keeping and may be discarded.

## 1. What is being asked for

One execution of the five steps of `claimb_location_sweep_spec.md`, in order, each once:

| step | board action | status |
|---|---|---|
| ① | physical power cycle, precheck, one carrier load, one full acquisition | **AUTHORISED 2026-08-20** |
| ② | physical power cycle | requested |
| ③ | precheck, one post-fault capture round (`no_op` + `known_answer`, nothing else) | requested |
| ④ | one acquisition in that same boot | requested |
| ⑤ | none — offline comparison of ④ against ① | requested; named so it is not skipped |

The **acquisition portions** of steps ① and ④ use read-only JTAG. Their surrounding board
actions are not all reads: step ① first writes FCLK0 and loads the carrier into PL through
PCAP; after a fresh power cycle, step ③'s `phase_setup` performs those same two setup writes
before its two ICAP transactions. Step ③ then runs the published restore payload as the
required `no_op`, followed by the specified `known_answer`, and nothing after it — its driver's
round is at most two steps and cannot reach `_score`. Everything runs through board tools that
already exist; **no new code is asked for here**. **No mutation, no post-fault restore or
recovery transaction, no arm, no scoring, no retry, no resume**, and nothing beyond step ④
regardless of what step ④ returns.

## 2. Why now — the four things that had to be true first

**The instrument question is closed.** `2.8.0` reads all sixteen controls in every case and
requires 16/16 before any location verdict, the intended hit included; the offline judging path
enforces the same rule, so `--judge-only` cannot re-license what the acquisition refused. Suite
1144/0, signature-search mutants 25/25, five gates ACCEPTED — and the two halves of that were
verified by different people, which is the point of saying so: **I re-ran the suite (1144 OK / 0
skips), the signature-search mutants (25/25 killed) and `git diff --check` here on 2026-08-20;
the other author independently re-ran the five host-side gates and reports all five ACCEPTED.**
Neither of us re-ran what the other did.

**`--max-reads` is not a way around it.** It can only produce a deliberately incomplete
`INSTRUMENT_UNVALIDATED`; the spec forbids it in step ④, and no location verdict is reachable
with it.

**The prerequisites P1–P3 are satisfied**, verified on 2026-08-20 rather than assumed:

```
P1  evidence/phase2_2026_08_15  0 untracked files; 66 tracked at HEAD
    7  top-level
    3  sweep/index.json + verdict.json + superseded.md
    8  4 candidate FARs x (capture + child log)      -- these four have no .tcl in the tree
   48  16 controls     x (capture + child log + Tcl)
P2  off-box copy = GitHub release asset  phase2-raw-2026-08-15
    phase2_sweep_2026_08_15.tar.zst  sha256 670f7986cc64bc39…  1,329,172 bytes
    the two local copies are on one filesystem (/dev/sdc) and the manifest says so
P3  archive verified by extraction: 15,432 files, validate_index accepted 5,144,
    missing 0, 5,144 tcl digests compared, 0 mismatched
```

**Phase 2's verdict is now marked void where it lives**, additively:
`evidence/phase2_2026_08_15/sweep/superseded.md`, with the controls recomputed offline at
**0/16** on both word alignments. The original `verdict.json` is preserved verbatim by ruling.

## 3. The identity this procedure runs under

```
parent  board_signature_search.py/2.8.0     child  probe_jtag_config_read.py/2.4.0  (R4)
control-only      49c8dbcebbcb7c7557a8f5e56ee4b32d770037f9e70a98544e8142d3f3336fa6
signature-search  a20e56aae879812d9ed2960ec55ac8b1b3f57710411cf40da0cc32b1855aa95d
                  5,144 admitted FARs, pinned in tests/test_board_signature_search.py
```

Step ① is the fresh-load control **for this identity**. Nothing earlier substitutes — least of
all the four R4 acquisitions (`2.7.1` / `8d28dcf3…`) or Phase 2 (`0caf4a36…`, child `2.0.0`,
pre-R4). Any edit to either tool before or during the procedure makes a third identity and
voids the pairing; if one becomes necessary, the procedure restarts at ①.

## 4. Run book

Commands are given so the authorisation is over something concrete. `<D>` is replaced with the
run date before the first command; the evidence root is `evidence/location_sweep_<D>/`. The
shell variables used below are assigned explicitly in the same shell that runs the procedure:

```sh
CARRIER=gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier.bit
EXPECTED_CARRIER_SHA256=8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a
```

**The two steps that load the carrier do it differently on purpose**, and this is the one part
of the run book that has to be read rather than skimmed:

* **Step ① loads it by hand**, because no versioned entrypoint exists that only sets up the
  board — so `board_set_fclk50.py` and `board_uboot_fpga_load.py` are run in that order, and
  their evidence is captured by redirection.
* **Step ③ must NOT load it**: `board_claimb_postfault_capture.py` calls `phase_setup`, which
  already does the full SHA comparison, `board_set_fclk50.py`, and
  `board_uboot_fpga_load.py --op loadb --require-unconfigured`, and records each step's argv,
  return code and output tails into `record["setup"]`. A hand load before it leaves
  `PCFG_DONE = 1`, and `--require-unconfigured` then refuses — **step ③ would fail on
  contact**. Its only pre-step is the read-only precheck.

FCLK0 is not decoration: this board's FSBL leaves it at 125 MHz and the carrier is signed off
at 50, so `board_set_fclk50.py` runs before **every** `loadb`. Step ① omitting it would also
break the ①/④ pairing, since step ③'s `phase_setup` always applies it.

```
① fresh load, negative control                                   [AUTHORISED]
   [physical power cycle]
   mkdir -p evidence/location_sweep_<D>
       # precheck_fresh_power.py would create it anyway (out.parent.mkdir), so this only
       # removes the ordering dependency the redirections below would otherwise inherit.
   python3 scripts/precheck_fresh_power.py --out evidence/location_sweep_<D>/precheck_1.json

   printf '%s  %s\n' "$EXPECTED_CARRIER_SHA256" "$CARRIER" |
       sha256sum --check - > evidence/location_sweep_<D>/carrier_sha256.txt 2>&1
       # This is a mechanical gate, not a visual comparison: sha256sum --check is the final
       # process in the pipeline and returns non-zero on mismatch. Its complete result is kept
       # in the named file. A mismatch STOPS; nothing else in this procedure is valid against
       # a different carrier.

   python3 scripts/board_set_fclk50.py --port /dev/ebaz-uart \
       > evidence/location_sweep_<D>/fclk50.log 2>&1                    # FCLK0 125 -> 50 MHz
   python3 scripts/board_uboot_fpga_load.py --require-unconfigured --op loadb --bit "$CARRIER" \
       > evidence/location_sweep_<D>/carrier_load.log 2>&1
       # A non-zero exit from either STOPS. Both logs are kept whatever happens. The loader
       # prints [plmark] <marker> (setenv without saveenv, so the marker dies with the boot):
       #   grep -o '\[plmark\] [0-9a-f]*' evidence/location_sweep_<D>/carrier_load.log

   python3 scripts/board_signature_search.py --out-dir evidence/location_sweep_<D>/step1_negative \
           --plmark <marker from carrier_load.log>
   expect: 16/16 controls, A20 = base, 5,144 read, candidate signature ABSENT

② [physical power cycle]                                          [not yet authorised]

③ build the specified fault                                       [not yet authorised]
   python3 scripts/precheck_fresh_power.py --out evidence/location_sweep_<D>/precheck_2.json
   sha256sum "$CARRIER"        # optional, read-only: phase_setup compares it mechanically
   python3 scripts/board_claimb_postfault_capture.py \
           --out evidence/location_sweep_<D>/fault/record.json
       # NO hand load here. phase_setup inside the driver does SHA + fclk50 + loadb and
       # records them in record["setup"]; a second load would hit PCFG_DONE = 1 and refuse.
   expect: steps exactly [no_op: passed, known_answer: stopped],
           pass 1 all three envelopes, pass 2 stops in envelope 0,
           STATUS 0x04040082 / FAULT 0x8, CTRL_ARM and CTRL_MODE_HOLDOUT clear in every
           CTRL write, same_boot passed, no reboots, PCAP_PR restored
           (reconstructed from record["instrumentation"]["commands"] — AxiRefusal still does
            not attach the partial record)

④ the acquisition, same boot                                      [not yet authorised]
   python3 scripts/board_signature_search.py --out-dir evidence/location_sweep_<D>/step4_sweep \
           --plmark <the fault boot's marker>          # no --max-reads, no --control-only

⑤ instrument comparison, offline, BEFORE the verdict is read      [not yet authorised]
   identical instrument_digest, parent and child versions, identical 5,144-FAR authority in
   the same order, child Tcl byte-identical for every FAR both acquisitions read, plmark
   unchanged across each acquisition
```

**The asymmetry in load evidence is admitted, not hidden.** Step ③'s load is verified by code
and lands in the record; step ①'s is verified by an operator reading two logs. Closing that gap
would mean a new setup-only entrypoint — new code, its own tests, mutants and audit — and that
is a separate request, not something to slip into this one.

## 5. Budget, from measurements rather than estimates

| quantity | figure | source |
|---|---|---|
| wall clock, full sweep, pre-R4 child | 408.2 s for 5,144 frames | Phase 2 `verdict.elapsed_s` |
| wall clock, R4 child | 2.0 s for 16 frames ≈ **0.125 s/frame** | the two 2026-08-16 R4 acquisitions |
| projected, one full R4 acquisition | **≈ 11 min** (5,144 × 0.125 s) | projection, **not measured at scale** |
| projected, ① + ④ | ≈ 22 min of reading | as above |
| OpenOCD processes | one **per frame** — ≈ 10,300 across the two acquisitions | the tool reads one frame per process by design |
| power cycles | 2 by design; **1 enabled** (before ①) | spec + the 2026-08-20 ruling |
| raw evidence | **at most** 2 × 15,434 files, ≈ 2 × 124 MB | Phase 2's set is exactly this shape |

Two qualifications, because both of these are ceilings and not expectations:

* **The projection is the one number here that is not a measurement.** R4 adds fixed JTAG dwells
  per child, and no R4 acquisition has ever exceeded 32 frames. If ① takes materially longer
  than ~11 min that is worth recording, not worth stopping for.
* **Only step ① is expected to read all 5,144.** Under the target semantics step ④ stops
  legitimately after **17 FARs** (`A20` + the sixteen controls) whenever `A20` does not hold the
  base or the controls are not 16/16 — and *how far it runs is a result, not a requirement*. So
  "2 × 15,434 files" is the both-complete ceiling; the realistic range for step ④ alone is 17
  captures to 5,144, and the budget must not be read as an expectation that it sweeps.

## 6. What the record keeps, and where the raw files go

Per acquisition, **committed — whichever of these the acquisition actually produced**:
`index.json`, `verdict.json`, `reading.md`, the intended FAR and its neighbours
`0x00400A20`–`0x00400A23`, and the sixteen controls, each as capture + child log + Tcl, plus
`archive_manifest.json`. The conditional matters: a legitimate 17-FAR stop never reads
`0x00400A21`–`0x00400A23` at all, so **the keep rule is "these, if present", never "these must
exist"** — a missing file is a fact about where the acquisition stopped, and manufacturing one
to satisfy a checklist would be evidence tampering. Which of them were expected and which were
read is stated in that acquisition's `reading.md`.

Everything else is archived under the Phase 2 schema (same field names, `schema_version`
bumped) with the same determinism — `tar` posix/sorted/mtime 1970-01-01Z/uid-gid 0, then
`zstd -19`. Per the 2026-08-20 ruling the order is now **five** fixed steps:

```
archive -> verify by extraction -> validate_index over the extracted tree
        -> upload to the release, download it back, byte-compare against the local archive
        -> only then move the loose files
```

Nothing is deleted; "cleanup" means the files live at a named path outside the repository,
recorded in the manifest. The off-box copy is a **GitHub release asset**, as for Phase 2:
release assets do not consume Git LFS bandwidth, which matters, since the repository already
carries 417 MB of LFS over 202 objects against a 1 GB/month allowance.

## 7. What this run cannot answer, stated before it runs

* **If the write landed *on* one of the sixteen control frames, the acquisition fails closed**
  and locates nothing. The per-control observations record expected and observed digests, so
  the state is visible in the record, but the tool does not adjudicate it. This is a disclosed
  capability boundary, not a defect.
* **R4 is demonstrated on sixteen frames, twice — never on 5,144.** Step ① is its first
  full-device scale test. If ① passes, step ④ is still the first such scale test in the
  specified post-fault state, and "controls 16/16 but the sweep degrades further in" remains a
  real possible outcome; the spec's first reading row exists for it.
* **A hit is not yet a location.** Any single-FAR result needs independent reproduction, which
  is a separate design and a separate authorisation.
* **The third state** (`A20` holding neither base nor candidate) is recorded, not interpreted.
* `CONFIG_STATUS` takes no part in any verdict — refuted three times as a validity proxy.
* Nothing here touches Claim B itself. Claim B still has zero data points, the preregistration
  is still DRAFT with §6 unfrozen and the §10 freeze never performed, and this procedure
  unblocks §9 step 6 at best.

## 8. Stop conditions

**"Any fault stops" would contradict step ③, whose whole purpose is to build one.** The rule
is therefore stated per step:

* **Steps ① and ④ — any fault stops.** Their acquisitions are read-only, and step ①'s two
  setup writes (FCLK0, then the PCAP load) are ordinary preparation; a fault anywhere in either
  step is not part of the design.
* **Step ③ — the specified `F_READBACK` stop is the required outcome**, and the precondition
  for going on to ④: `[no_op: passed, known_answer: stopped]`, pass 2 of envelope 0,
  `STATUS 0x04040082` / `FAULT 0x8`. **Any other fault, and equally an unexpected pass, stops
  the procedure** — a pass means the state this step exists to create was not created.
* **Every step — reboot, marker mismatch, child failure, missing frame or bookkeeping anomaly
  stops it**, with all evidence kept.

A candidate signature present in step ① ends the procedure outright — the signature would not
be diagnostic of the write. Steps are not retried, and a disturbed state is not re-acquired.

Per the standing stop-on-failure rule: the report comes back at the stop, and the obvious fix
is not applied on the way.

## 9. What is still open

§0 records what was granted. What remains to be ruled on, after step ① has run and been read:

1. **Steps ②–⑤**, on the evidence of ①'s result *and* of ①'s archival — the second is
   explicitly part of the test, since two more raw sets are the largest bookkeeping commitment
   in this line so far.
2. **The second power cycle**, which is accepted by the design but not yet enabled.
3. Whether ①'s operator-mediated load evidence (§4) is good enough to keep, or whether a
   setup-only entrypoint should exist before ③ — a separate request either way.
