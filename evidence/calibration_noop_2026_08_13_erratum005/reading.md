# Reading the erratum-005 stage dump

Source: `stage_dump.json` (`probe_stage_dump.py/2.0.0`, read-only, verdict `DUMPED`,
101 words, `sha256_be 5ab96691…`), taken from the *same* boot as `record.json`
(plmark `18cb61fca9437fed`) with the board still in its post-fault state
(`STATUS 0x04040082`, `FAULT 8`, `rb_latency_words=1`, `rb_latency_valid=1`).

Machine-checkable form: `dump_analysis.json`, produced offline by
`scripts/analyse_stage_offset.py`, which measures and deliberately attributes nothing.

```
python3 scripts/analyse_stage_offset.py \
  --run-dir gate_runs/claimb_round1_carrier_2026_08_13_erratum005 \
  --dump    evidence/calibration_noop_2026_08_13_erratum005/stage_dump.json \
  --out     evidence/calibration_noop_2026_08_13_erratum005/dump_analysis.json
```

`analyse_stage_dump.py` was NOT used: it is pinned to the erratum-004 run and to that
erratum's 606-word model, which does not describe a per-frame 202-word readback. It is
left untouched so the erratum-004 artefact stays reproducible from HEAD.

---

## MEASURED

### The content is new

| | |
|---|---|
| digest | `5ab96691…` — **not** the earlier `c402e1b0…` |
| values | 21 distinct, 71 zero, 30 non-zero — **not** 101 × `0xFFFFFFDA` |

**The `0xFFFFFFDA` constant pattern is gone, and this is the first time the staging window
has held bit-exact configuration data.** That is the whole of what the content change
licenses. It is not a statement about whether the interface did or did not abort.

### The 71/101 against the requested frame is an artefact

`FAR 0x00400A20` is **all zero** in `carrier.bit` — as are all 15 guard frames, correctly:
they are the evolvable region the ECO writes into, while the design's 994 LUTs sit in 428
other frames. The dump contains 71 zeros, so 71/101 is the **all-zero floor** and carries
no information. Every frame-aligned "best match" sits at that same floor.
`dump_analysis.json` reports the floor next to every count for this reason.

### One unique exact window, at an arbitrary offset

Stream = 5,144 addressed frames + 8 pad = **520,352 words**.

* frame-aligned search over all 5,144 frames: **no exact match**
* search at every word offset (exact, on the packed big-endian bytes): **exactly one hit**

```
offset 268658  =  FAR 0x00400A81 word 99
                  .. FAR 0x00400A82 word 98
```

### The offset

```
requested   FAR 0x00400A20 = frame #2654, offset 268054
observed                                  offset 268658
delta                                            +604 words
604 = 5 * 101 + 99  =  6 * 101 - 2
```

Both decompositions are recorded; neither is privileged.

---

## NOT SETTLED BY THIS DUMP

* **Whether the `−2 words` is a pipeline-latency error.** It is consistent with one, and
  `rb_latency_words = 1` is a measured value it could be compared against, but a single
  window at a single offset does not distinguish a latency error from an addressing error
  that happens to land two words short. **Inference, not measurement.**
* **Whether the `+N frames` arises inside one transaction or across the five.** A 202-word
  burst cannot reach two frames past its own target, but that observation constrains the
  explanation without choosing one.

### `RB_WORDS = 202` is correct — do not change it

An earlier draft of this reading called `RB_WORDS = 2 * FRAME_WORDS = 202` a length defect
because `rb_skip = rb_lat + SKIP_FRAME` plans to consume `rb_lat + 101 + 101` words. That
was wrong. UG470 specifies the FDRO Type-2 word count as

```
101 * (frames to read + 1 pad frame)  =  101 * 2  =  202
```

and specifies readback data as valid only after a fixed number of pipeline clocks once
CSIB is asserted. **Pipeline latency clocks are not part of the Type-2 word count.**
`RB_WORDS` stays 202.

---

## LEADING HYPOTHESIS: the command order, not the length

`carrier_stream.v`'s `RB_SETUP` emits, in `rb_k` order:

```
0: FAR header   1: frame_far   2: CMD header   3: RCFG   4: NOOP   5: FDRO   6: Type-2 len
```

so **FAR is loaded before RCFG is written**. UG470's readback sequence is

```
RCFG -> NOOP -> FAR -> FDRO
```

and UG470 further states that a command written to CMD executes when FAR is loaded. Under
that rule the RTL loads FAR at a moment when RCFG has not been issued, so the FAR write
cannot take effect as the read address.

The simulation does not catch this. `icape2_model.v` sets `rcfg <= 1'b1` on receiving the
`CMD_RCFG` payload (line 444) and only tests `E_NO_RCFG` at FDRO time (lines 509, 523) —
never at FAR load. **The model therefore treats the defective order as legal**, which is
why every bench passes.

This fits where the dump landed. Pass 2 writes `A20, A21, A22, A23, A80`; the FAR then
sits at `A81`. The observed window is `A81`/`A82` — the auto-incremented address, not the
requested `A20`.

**Still a hypothesis.** What would settle it is a model change first: make the model
enforce UG470's ordering so `FAR → RCFG` fails in simulation, and only then reorder the
RTL to `RCFG → NOOP → FAR → FDRO`.

---

## Verdict

Erratum 005 changed the observed content: the `0xFFFFFFDA` pattern is gone and the staging
window holds bit-exact configuration data for the first time. It is **not a sufficient
fix** — the engine still faults, and the captured window is 604 words from the frame that
was asked for.

Board was left untouched: read-only, no reload, no transaction, no PCAP_PR, no ack, no arm.
