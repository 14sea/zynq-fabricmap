# W1 and W2 of the read-side divergence design, read honestly

Host-side only. No board contact, no network. Two offline tools, both read-only, both hashing
every input into their output:

```sh
python3 scripts/analyse_read_side_facts.py  --out evidence/read_side_facts_2026_08_20/facts.json
python3 scripts/audit_readback_evidence.py  --out evidence/read_side_facts_2026_08_20/readback_audit.json
```

Their console output is committed beside them. `analyse_read_side_facts.py` refuses outright if
any of the ten pinned inputs has drifted from the digest `docs/claimb_read_side_divergence_design.md`
§2 froze, so what follows is a re-derivation rather than a new measurement wearing the old name.

## W1 — all six facts reproduce at the pinned tree

| fact | result |
|---|---|
| **F1** | 15 envelope frames, **1 distinct content**, all zero, sha256 `0441772f6655…6d7b8de9`. Each frame's manifest digest was also recomputed from its own words |
| **F2** | the `no_op` step calls `_write("restore", …)` at `board_claimb_known_answer.py:104` — read out of the driver's AST, not its prose — and `restore.actual_init` is `0x0000000000000000`. O5 read 15 frames back, **0 of them non-blank**, `rb_frames_ok = 15`, `configuration_valid = 1` |
| **F3** | the candidate touches `A20`–`A23`, each at **words (50, 51)** only; `A20`'s frame sha256 is `15cb05e6…69a5bbe7` |
| **F4** | both staging copies: 101 words, **0 non-zero**, same sha256, **distinct plmarks**, equal to the base at the intended FAR, unequal to the candidate |
| **F5** | the status word is **read out of each record's own command replies** (`md.l` of `board_uboot_axi.STATUS`), not restated: `0x04040082` in both runs, FAULT register `0x00000008` in both. Decoded: `fault = 1`, `rb_frames_ok = 0`, `rb_latency_words = 1`, `rb_latency_valid = 1` — the same latency the passing no-op measured |
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
VERDICT  NO_NONBLANK_READBACK_HAS_EVER_BEEN_RETURNED

6 engine transactions on the erratum-006 carrier   90 frames   0 non-blank
                                                   90 of 90 = BLANK_EXPECTED_BLANK_DEGENERATE
5 staging copies
  erratum-004 carrier   101/101 non-zero   the abort status word
  erratum-005 carrier    30/101 non-zero   bit-exact device data at the WRONG address
  erratum-006 carrier ×3   0/101 non-zero  NONBLANK_EXPECTED_GOT_BLANK
```

The six transactions are `known_answer_2026_08_14_erratum006`, `location_sweep_2026_08_20`,
`location_reproduction_2026_08_20`, `phase2_2026_08_15` (VOID instrument, listed for
completeness and supporting nothing), `postfault_r4_step2_capture_2026_08_16` and
`postfault_r4_replication_2026_08_16`. Every one of them is a `no_op` step, and the no-op writes
the blank restore payload — which is why all ninety frames are the degenerate case rather than
ninety independent confirmations.

**One classification was corrected while writing this.** The three erratum-006 staging copies
were first labelled "blank, and blank was expected". That is wrong: all three were taken *after*
the candidate round faulted, so a correct readback of the requested FAR at that moment would
have returned the **candidate**. Their verdict is `NONBLANK_EXPECTED_GOT_BLANK`. The record
carries `landing_verified_in_this_instance` per capture — true only for the two 2026-08-20 runs,
which have a location acquisition; for the 2026-08-14 capture the expectation is a reproduced
prior, not a measurement in that instance.

## What this establishes, and what it does not

* **F2 generalises across the committed erratum-006 evidence.** This frame-data path has never
  been demonstrated to deliver non-blank configuration data correctly — not once, in six
  transactions and ninety frames.
* It does **not** say the path is broken in a particular way. Ninety blank frames that were
  expected to be blank are consistent with a correct readback and with every hypothesis in §5
  of the design. That is the point: they discriminate nothing.
* It does **not** touch the location result, which stands at two observations, nor Claim B,
  which still has zero data points.
