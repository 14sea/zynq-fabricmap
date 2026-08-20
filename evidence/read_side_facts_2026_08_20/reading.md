# W1 and W2 of the read-side divergence design, read honestly

Host-side only. No board contact, no network. Two offline tools over one frozen inventory:

```sh
python3 scripts/analyse_read_side_facts.py  --out evidence/read_side_facts_2026_08_20/facts.json
python3 scripts/audit_readback_evidence.py  --out evidence/read_side_facts_2026_08_20/readback_audit.json
```

Their console output is committed beside them. `scripts/read_side_evidence.py` holds the
inventory — **66 pinned files**, a closed list of **seven** engine records, **seven** staging
copies, **three** authority artifacts and the **thirty-two** positive-control captures the
landing derivation reopens — and enforces it three ways, all fail-closed:

1. every pinned artifact must exist and hash to its pinned value;
2. discovery still runs — for engine records **and for staging copies** — and each result must
   equal its frozen list **exactly, in both directions**; an extra and a missing one are both
   refusals. The staging scan is shape-based rather than name-based, because `stage_dump.json`,
   `stage_dump_2.json` and `ddr_slot0*.json` are three naming conventions for one artifact;
3. every repository module the tools actually loaded must itself be pinned. The three files of
   this deliverable cannot pin themselves and are the declared exemption; any other unpinned
   module is named and refused.

`tests/test_read_side_audit.py` is 35 tests, negative-first with positive real-tree baselines.
Its adversarial cases cover a drifted digest, a missing input, an unpinned import, a population
each population one too large and one too small, an unlisted record or staging copy
appearing on disk under any name, a broken or wholly
absent plmark chain, a missing positive control, one exact control repeated sixteen times, **a
control whose expected and observed digests agree with each other but not with `carrier.bit`**,
**a forged control capture with every digest re-stated including the verdict's**, a capture that
disagrees with its own digest, **a forged A20 capture whose digests were all re-stated so only
the words give it away**, a FAULT word that is not 8, two runs that disagree, and four ways for
the driver to have changed. The positive numbers below are worth what those refusals are worth.

## W1 — all six facts reproduce at the pinned tree

| fact | result |
|---|---|
| **F1** | 15 envelope frames, **1 distinct content**, all zero, sha256 `0441772f6655…6d7b8de9`. Each frame's manifest digest was also recomputed from its own words |
| **F2** | the `no_op` step calls `_write("restore", …)` at `board_claimb_known_answer.py:104` — read out of the driver's AST, not its prose — and `restore.actual_init` is `0x0000000000000000`. O5 read 15 frames back, **0 of them non-blank**, `rb_frames_ok = 15`, `configuration_valid = 1` |
| **F3** | the candidate touches `A20`–`A23`, each at **words (50, 51)** only; `A20`'s frame sha256 is `15cb05e6…69a5bbe7`. **Not derivation alone**: both 2026-08-20 JTAG captures are opened, their index-recorded `capture_sha256` re-checked, the 202-word split verified (`frame` is the SECOND block), and their 101 words compared to the re-derived candidate — **101/101 in both runs**, and F3 refuses to report if either disagrees |
| **F4** | both staging copies: 101 words, **0 non-zero**, same sha256, **distinct plmarks**, equal to the base at the intended FAR, unequal to the candidate |
| **F5** | the status word **and the fault's name** are read out of each record's own command replies (`md.l` of `board_uboot_axi.STATUS` and `.FAULT`), not restated: `0x04040082` and `0x00000008` in both runs. The code is masked the way `read_fault` masks it on the wire (`& 0xF`), the two runs are **required to agree**, and a code other than 8 is a refusal — so "readback" is derived, not asserted. Decoded: `fault = 1`, `rb_frames_ok = 0`, `rb_latency_words = 1`, `rb_latency_valid = 1` — the same latency the passing no-op measured |
| **F6** | see below |

**F6 gained a check it did not have.** The displacement bands are a property of the stream
ordering, so they are now computed under **both** orderings — device-configuration order from
`bitstream_frames.device_frame_sequence`, and the ascending-FAR order `analyse_ddr_capture.py`
uses. **They agree exactly**, so the bands are not an artifact of one traversal:

```
pre-write    δ ∈ [-1159,-1061] ∪ [-654,-253] ∪ [-150,+555]
post-write   δ ∈ [-1159,-1061] ∪ [-654,-253] ∪ [-150,-51] ∪ [+355,+555]
search radius ±2000 words;  all-zero windows in the full pre-write stream: 474,494
```

Every |δ| ≤ 50 is excluded post-write, and 474,494 is reproduced independently of the committed
`ddr_slot0_shutdown_read_analysis.json` that first reported it.

**F5 also settles the budget question the design's §10 had to correct.** Read out of the two
fault records: wall clock **250.5 s** and **250.4 s**, of which the `fpga loadb` alone is
**199.3 s** in both; the no-op transaction inside them took **27.126 s** and **25.886 s**. The
carrier load is *inside* that 250 s, not additional to it.

## W2 — the criterion, and what it returns

The question is not "was any word non-zero". Two committed captures are non-zero and neither is
a success. So the criterion has all three parts at once: **the expected frame is non-blank, the
returned words equal it exactly, and it is the frame whose FAR was requested.**

Scope: the **engine's** frame-data path only — what `carrier_stream` staged and handed to the
host, plus the DRAM copies of that staging RAM. JTAG captures (`probe_jtag_config_read.py`,
every sweep's `far_*.json`) are excluded by definition: they are the independent path this
question is about, not evidence from it.

```
VERDICT  NO_NONBLANK_READBACK_IN_THE_FROZEN_COMMITTED_INVENTORY

discovery == freeze: True   (engine records AND staging copies)
7 engine transactions on the erratum-006 carrier  105 frames   0 non-blank
                                                  105 of 105 = BLANK_EXPECTED_BLANK_DEGENERATE
7 staging copies, and they are NOT all of one kind:
  erratum-004 carrier ×2  101/101 non-zero  the abort status word, read twice   owed: none
  erratum-005 carrier      30/101 non-zero  bit-exact data, WRONG address       owed: none
  erratum-006 carrier ×3     0/101 non-zero NONBLANK_EXPECTED_GOT_BLANK         owed: candidate
  erratum-006 carrier ×1     0/101 non-zero BLANK_EXPECTED_BLANK_DEGENERATE     owed: base
landings verified: 2  — the new copy is not a third landing observation
```

**Two of those numbers moved for reasons worth stating.** The seventh engine record and the
seventh staging copy are the 2026-08-20 read-side run
(`evidence/read_side_divergence_2026_08_20/`). Its staging copy was taken after a diagnostic
no-op verified fifteen **blank** frames, so a correct read owed the **base** there — it is
`BLANK_EXPECTED_BLANK_DEGENERATE` and must not be filed with the three candidate-fault copies,
which would read as a fourth failing readback. And **`stage_dump_2.json` was missing from the
1.0.1 inventory altogether** — a second read of the erratum-004 window, byte-identical to the
first. The two-way staging guard is what found it, and is why the scan is by shape.

**The verdict is scoped on purpose.** "EVER" would quantify over runs nobody recorded. What is
established is a property of the **frozen committed inventory at the pinned tree**, and a test
pins that wording so it cannot drift back.

The seven transactions are `known_answer_2026_08_14_erratum006`, `location_sweep_2026_08_20`,
`location_reproduction_2026_08_20`, `phase2_2026_08_15` (VOID instrument, listed for
completeness and supporting nothing), `postfault_r4_step2_capture_2026_08_16`,
`postfault_r4_replication_2026_08_16` and `read_side_divergence_2026_08_20`. Every one of them
is a `no_op` step, and the no-op writes the blank restore payload — which is why all 105 frames
are the degenerate case rather than 105 independent confirmations.

**One classification was corrected while writing this.** The three erratum-006 candidate-fault
staging copies were first labelled "blank, and blank was expected". That is wrong: all three
were taken *after* the candidate round faulted, so a correct readback of the requested FAR at
that moment would have returned the **candidate**. Their verdict is
`NONBLANK_EXPECTED_GOT_BLANK`.

**And the rule behind that correction was itself too general.** 2.0.2 said every staging copy
was a candidate-fault copy. The 2026-08-20 read-side run broke it. What a correct readback owed
is now **per-entry data** in `read_side_evidence.STAGING` — `candidate`, `base`, or `none` for a
superseded carrier — and the classifier is handed that rather than a rule about all of them.

**And `landing_verified_in_this_instance` is now derived, not declared.** For each instance the
tool reads that instance's own step-4 evidence and requires all seven of:

* four present, well-formed plmarks, with one value across the fault record, the staging copy
  and the acquisition's start **and** end;
* the acquisition's `instrument_digest` equal to the frozen `a20e56aa…`;
* `verdict == WRITE_LANDED_AT_THE_INTENDED_FAR`, naming `0x00400a20`;
* sixteen unique control FARs whose verdict order equals the index's frozen order, all sixteen
  exact with expected == observed digests — **and all sixteen re-derived**: each control
  capture is reopened, its digest chain rechecked, and its 101 words compared against the frozen
  `carrier.bit` at that FAR, because `expected == observed` is only the acquisition tool
  agreeing with itself;
* the A20 capture hashing to the `capture_sha256` its own index records;
* the 202-word capture splitting into `pad_frame` then `frame`, with the recomputed frame
  digest equal to both the capture's and the index's;
* the 101 words equal to the re-derived candidate.

Result: **run1 and run2 verified, 101/101 words, 16/16 controls**; the 2026-08-14 capture has no
acquisition to derive from, so its flag is **false** — an absence of evidence recorded as one,
not an assumption.

## What this establishes, and what it does not

* **F2 generalises across the committed erratum-006 evidence.** This frame-data path has never
  been demonstrated to deliver non-blank configuration data correctly — not once, in seven
  transactions and 105 frames.
* It does **not** say the path is broken in a particular way. The 105 blank frames that were
  expected to be blank are consistent with a correct readback and with every hypothesis in §5
  of the design. That is the point: they discriminate nothing.
* It does **not** touch the location result, which stands at two observations, nor Claim B,
  which still has zero data points.
