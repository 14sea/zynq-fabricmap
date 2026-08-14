# Claim B — the known-answer round: request to the other author

**Authorisation, exactly (user ruling, 2026-08-14).** The offline construction and review of
this round are authorised. **The board is not.** A single board run will be ruled on
separately, *after* the full chain has a dry run, negative cases and structural entrypoint
tests. Nothing in this document authorises a device write.

Board state as this is written: the PL holds the erratum-006 carrier, clean
(`fault=0`, `recovery_required=0`, `configuration_valid=1`) after the passing no-op of
2026-08-14. Any later board run needs a **fresh power cycle** first — `PCFG_DONE` is set now
and `board_uboot_fpga_load.py --require-unconfigured` will refuse.

## 1. Why this round exists, stated as narrowly as the evidence allows

The erratum-006 no-op passed on silicon: all three envelopes committed and read back, 15/15
frames equal to the pinned base, `rb_latency_valid=1` on every envelope
(`evidence/calibration_noop_2026_08_14_erratum006/record.json`).

That establishes **the readback sequence is legal to the device**. It does **not** establish
**the address**, and the reason is arithmetic, not caution: all 15 pinned frames in
`phenotype_manifest.json` are all-zero — verified, **1515 words, 0 nonzero** — so a readback
of some *other* all-zero frame is byte-indistinguishable from a correct one. This is the
same all-zero floor that made the 71/101 count meaningless in the erratum-005 analysis.

**The known-answer round is the discriminator.** Its whole value is that it writes a
*non-zero* pattern whose exact word/bit set is pinned in advance, so a correct address and a
wrong one produce different bytes. Design every deliverable to serve that, and the round
pays for itself even if the score is uninteresting.

## 2. The candidate is already selected, mechanically. Do not re-draw it.

First entry of the frozen production report,
`gate_runs/claimb_round1_reachability_2026_08_10/reachability_report.json` → `per_lut[0]`:

```
site SLICE_X2Y25   bel A6LUT   target_truth_table 64'h517A5CEA46B05DE4
draw_index 0   discarded_draws []   mutable_count 49   exhausted false
blocked_positions [5, 23, 25, 33, 49, 56]   attainable_ceiling 58
```

The other five LUTs stay **exactly** at base. Non-writable positions stay at base.

### 2a. What is actually written: 26 content bits, not 49

`64'h517A5CEA46B05DE4` is the **target**, not the candidate. The candidate is the target
masked by what is writable:

```
mutable_mask  = 0xDA7D5FE96D7FFFDF      (49 bits)
actual INIT   = target & mutable_mask
              = 0x517A5CEA46B05DE4 & 0xDA7D5FE96D7FFFDF
              = 0x50785CE844305DC4      (26 bits set)
```

**49 is the count of mutable positions; only 26 bits actually change** from the all-zero
base. The mask is not an input to be trusted — it is **derivable, and was derived**, from
`local_map.json`: the 49 `CLBLL_L.SLICEL_X0.ALUT.INIT[n]` features give exactly that mask,
bit for bit. Do the same rather than copying the constant from here.

The 15 non-mutable positions are `5, 23, 25, 28, 31, 33, 34, 36, 45, 47, 49, 55, 56, 58, 61`.
Of them, **exactly 6 want a 1** — `5, 23, 25, 33, 49, 56`, the report's `blocked_positions`
— and the other 9 want 0, which the all-zero base already satisfies.

### 2b. The expected scores are two six-element vectors, not a single number

The hardware scorer runs **train 40 / holdout 24** (`order`, `train_count`, `holdout_count`
in `vivado/carrier/generated/carrier_constants.json`; the order is a permutation of 0..63,
verified disjoint and complete) and returns **an independent count per LUT, for all six**.
Recomputed here from the frozen constants:

| | LUT0 `SLICE_X2Y25/A6LUT` | LUT1 | LUT2 | LUT3 | LUT4 | LUT5 |
|---|---|---|---|---|---|---|
| candidate, train | **35** | 22 | 20 | 20 | 20 | 18 |
| candidate, holdout | **23** | 10 | 12 | 12 | 12 | 14 |
| base / restore, train | **18** | 22 | 20 | 20 | 20 | 18 |
| base / restore, holdout | **14** | 10 | 12 | 12 | 12 | 14 |

**Pin both vectors. Do not pin a single `58`.** 58 is LUT0's candidate total (35 + 23) and
nothing else; the dry run must match all twelve numbers and then check that total.

Two internal cross-checks the harness should assert, because they catch a wrong partition
rather than a wrong score:

* the six blocked positions split **5 in train, 1 in holdout** (`5, 25, 33, 49, 56` and
  `23`), which is exactly why the candidate scores `40 − 5 = 35` and `24 − 1 = 23`;
* every target has popcount 32, so each **untouched** LUT scores `64 − 32 = 32`, and
  **LUT1..LUT5 are identical in both rows**. That identity is the structural evidence that
  the round touched only LUT0 — assert it.

Base/restore LUT0 is `18 + 14 = 32` for the same reason, and that is the post-baseline
expectation.

### 2b. Which frames it touches, and the precedent artifact for exactly this LUT

`local_map.json`'s universe (292 addresses, 12 FARs) is the source of truth for
truth-table-bit → `FAR/word/bit`. Its features are **tile-relative**
(`CLBLL_L.SLICEL_X0.ALUT.INIT[n]`), not board site names, so the site→`SLICEL_Xn` step is
yours to make explicit and to justify in the artifact rather than assume.

Two facts that constrain it, both verified:

* the candidate touches **4 of the 15 pinned frames** — but the reason is the **26 bits it
  actually sets**, not the 49 addresses that exist. Mapping each set bit of
  `0x50785CE844305DC4` through `local_map.json`:

  | FAR | content bits set |
  |---|---|
  | `0x00400A20` | 6 |
  | `0x00400A21` | 7 |
  | `0x00400A22` | 2 |
  | `0x00400A23` | 11 |
  | **total** | **26** |

  (For contrast, the 49 *mapped addresses* distribute 14/11/11/13 over the same four FARs.
  Quoting that as the reason a frame is touched conflates capacity with content.) **The ECC
  of each touched frame is recomputed independently**, not derived from this table.
* `gate_runs/claimb_round1_carrier_2026_08_13_erratum006/carrier_eco.json` is a **published,
  gate-accepted artifact for this exact cell**: `cell evolvable_0`, `loc SLICE_X2Y25`, `bel SLICEL.A6LUT`,
  `init_before 64'h0…0` → `init_after 64'h0000000900000001`. `gate_init_eco.py` already
  accepts it as *"2 of 5144 frames differ, exactly the 2 the map predicts; 3 predicted bits
  moved, no stray bits, every ECC a correct recomputation."*

**Reuse that verifier's shape.** The known-answer artifact is the same claim at **26 content
bits over 4 frames** that the ECO already makes at 3 bits over 2, and the existing gate is
the model for the consumer check rather than something to invent.

## 3. Producer deliverables — all pinned, all in one artifact

Built against the current authority: run
`gate_runs/claimb_round1_carrier_2026_08_13_erratum006`, `PRODUCTION_MANIFEST_SHA256`
`e45f466d…`, `carrier.bit` `8c3369e8…`.

1. exact **frame words** after the mutation, for every frame it touches;
2. the **ECC** of each such frame, recomputed (`scripts/frame_ecc.py`), not copied;
3. the **serialized payload SHA-256**, over the same byte sequence
   `board_uboot_axi.py` would put on the wire;
4. the **expected non-zero word/bit set** — the discriminator of §1. State it as
   `FAR/word/bit` triples, not as a digest alone: a digest cannot be diffed against a
   readback that lands at the wrong address;
5. the **expected train/holdout score vectors** — both six-element rows of §2b, for the
   candidate and for base/restore, with their derivation in the artifact itself;
6. the **restore-to-base** payload and its own SHA, pinned in the same artifact — restoring
   is part of the round, not an afterthought.

## 4. Consumer: independent recomputation, no producer self-attestation

The consumer recomputes every item of §3 from the frozen inputs (`local_map.json`, the
manifest, the report) and compares. It must be able to **fail** — ship the known-bad
fixtures alongside, in the style already used for the reachability verifier. A consumer that
reads the producer's numbers and re-prints them is not a check, and this repo has struck
that pattern before.

## 5. The scorer-arm path — the one genuinely new production surface

There is **no scoring entrypoint today**, and that is currently a *structural guarantee*:
`CTRL_ARM` / `CTRL_MODE_HOLDOUT` are defined only as constants at
`scripts/board_uboot_axi.py:113-114`, and `tests/test_single_write_entrypoint.py:133` pins
that nothing else in the repository names them.

Adding the arm path therefore **changes what that test asserts**. Change it *deliberately*,
to "exactly one production path arms the scorer, and it is this one" — never by loosening or
deleting the assertion. Requirements:

* a single arm path, reachable **only** after a host gate has established, in this order:
  readback SHA equals the pinned expected SHA, `configuration_valid=1`,
  `recovery_required=0`;
* no `--force`, no `--skip`, no `--allow`, matching `board_calibrate_noop.py`'s CLI;
* the guard refuses rather than reboots (erratum 003's rule);
* `board_uboot_axi.py` stays the only script that names the carrier's AXI window —
  `tests/test_single_write_entrypoint.py` greps for `0x43c0`. Derive addresses from
  `axi.RDBACK` / `axi.FRAME_WORDS`.

## 6. Orchestration — one transaction chain, dry run only

`no-op → known-answer → readback → score → restore base → post-baseline`, in one session, in
that order. Offline this exists as a **dry run** against the simulation model plus negative
cases; the board is not authorised.

Budget facts it has to fit, from the board records:

* the watchdog is **2^20 cycles of 50 MHz FCLK0 = 20.97 ms per phase**, loaded at pass start
  and at readback entry, **not per frame**;
* therefore **one console line per envelope** carrying the pass, all frame copies and all
  acks. A poll→`md`→ack loop is ~14 ms/frame and cannot fit — do not attempt it;
* U-Boot `CBSIZE` is 2048; the longest existing line is ~750 chars;
* the interlock must be **inline, not an env script** (`setenv` strips a quoting level and
  hush then runs the bare `&` as a background operator; all quoting variants were tried on
  the board and all fail);
* the readback window is **101 words: first `RDBACK`, last `RDBACK+0x190`**;
* `board_serial.SYNC_COMMAND` is `"echo"`. **Never send a bare CR or an empty line** — U-Boot
  repeats the last command, `md` resumes from an already-advanced address, and the unmapped
  read reboots the board.

## 7. Traps in this repository that have each cost a session

* **`RB_WORDS = 202` is correct — do not "fix" it to 203.** UG470: FDRO Type-2 count is
  `101 × (frames + 1 pad)`; pipeline latency clocks are not part of the word count.
* Evidence files must **not** end in `.log` — `.gitignore` has `*.log` and
  `tests/test_evidence_manifests.py` forbids gitignored files under `evidence/`.
* Editing RTL stales the string anchors in `scripts/mutate_carrier_readback.sh`. Repoint the
  anchor; never loosen the assert.
* Authority-bound tests **skip** on a dirty tree, so a mutation can "survive" for the wrong
  reason. Verify mutations in a `git worktree` where the mutation is committed.
* Publication order: authority half (scripts/tests/docs) commits **first**, then the run
  root, then `gate_publish_carrier_run.py`, then the artifacts alone. After moving
  `PRODUCTION_MANIFEST_SHA256`, repoint `test_board_carrier_exec`,
  `test_board_carrier_guard`, `test_carrier_run_gates` or authority tests silently skip.
* The `routed nodes` / `routed pips` sha256 in `isolation.txt` is a **tile-namespace**
  digest. It stays identical across builds that route differently. Never read it as
  "the routing is unchanged".
* Route inventory is the `EVIDENCE` block of `isolation.txt` (lines ~9–13), not the net
  listings below it.

## 8. What the gate on the returned code will be

Run against a clean tree, and reported from commands, not from a summary:

1. full suite green with **0 skips** (`python3 -m unittest discover -s tests -t tests` —
   there is no pytest, and `tests/` is not a package, so `-t .` and root discovery both
   fail);
2. `run_carrier_benches.sh` green; mutation harness green, with **a new mutant for the arm
   path** — an arm that cannot be killed by a mutant is not gated;
3. consumer recomputation reproduces §3 from the frozen inputs, and the known-bad fixtures
   **fail** as designed;
4. the §5 structural test asserts the single arm path positively;
5. the dry run produces the expected non-zero word/bit set and **all twelve** score numbers
   of §2b — including LUT1..LUT5 being identical between candidate and base;
6. every claim in the returned write-up traceable to a file in the repo. Claims about
   silicon must say what the all-zero floor still does not settle.
