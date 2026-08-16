# R4 on a post-fault state, independently reproduced: 16/16 a second time

A full re-run of the steps ①–③ specification, from a second physical power cycle and a
second, separately built fault. Nothing from the first run was reused except the pinned
instrument and the sixteen controls — which is the point.

## What was run, in order

| # | what | result |
|---|---|---|
| 1 | physical power cycle, then the five fresh-power preconditions | all five matched; **raw console text preserved this time** |
| 2 | canonical carrier loaded once, no transaction; control-only | **16/16**, boot `18cc38b5e1635534` |
| 3 | physical power cycle | — |
| 4 | fresh-power preconditions again | all five matched, raw preserved |
| 5 | `board_claimb_postfault_capture.py/1.0.0` | stopped at the **specified** fault, boot `18cc3925aa6d3be5` |
| 6 | control-only in that same boot | **16/16** |

Stopped there, as ruled. No sweep, no retry, no arm, no scoring.

## The fault is the specified one, re-verified from the wire

Not from the exit code — reconstructed from `instrumentation.commands`, and identical to
step ②'s in every checked respect:

```
round.steps          [no_op: passed, known_answer: stopped]   — no third step
no-op                pass 1 env 0/1/2, pass 2 env 0/1/2       — completed
known-answer         pass 1 env 0/1/2, then pass 2 env 0      — stopped there
STATUS / FAULT       0x04040082 / 0x00000008 = readback
CTRL writes          12, and CTRL_ARM + CTRL_MODE_HOLDOUT clear in every one
353 commands         0 rebooted, 0 without a returned prompt
same_boot            passed, plmark 18cc3925aa6d3be5
carrier              8c3369e8…, PCAP_PR restored
```

## The result

**16 of 16 whole-frame bit-exact**, every entry `ok`, every child returncode 0, none unread,
no frame read back all-zero, non-zero word counts identical frame for frame to every earlier
acquisition: 48, 66, 71, 46, 84, 14, 2, 82, 57, 3, 13, 55, 30, 14, 2, 3.

One instrument across all four acquisitions — this one, this run's control, step ① and
step ③ — checked before the verdict was read:

```
parent 2.7.1 / child 2.4.0, digest 8d28dcf3cae515b2…332516b
the same sixteen FARs in the same order
the sixteen child Tcl files byte-identical to all three of the others
```

The 32 capture files and child logs were re-hashed here rather than trusted from the tool's
exit status; no mismatch.

## What may now be said, and what may not

**Starting from the specified `F_READBACK` fault state, running the recovery sequence restores
all sixteen known non-zero control frames to bit-exact readability — and this has now been
reproduced on a second, independently built fault state, in a different boot, after a separate
power cycle.** R4 is a recovery method for the specified post-fault state.

The phrasing matters and was corrected once already: R4 does **not** read an unaltered fault
state. Its `JSTART` and `JSHUTDOWN` change the configuration engine's state by design. What is
measured is readability *after* the recovery, starting *from* the fault.

Two limits survive the replication intact:

1. **The control is still historical, not paired.** No non-R4 prefix was run on either fault
   state — that would be an extra acquisition, and neither authorisation allowed one. What
   makes 16/16 meaningful is still the cross-run comparison: a clean no-op alone drove the
   2.0.0 prefix from 16/16 to 0/16, and Phase 2's pre-R4 instrument reproduced **zero** known
   non-zero frames post-fault. A within-state paired control does not exist and is not claimed.
2. **Nothing here says where the write landed.** No sweep was run and none is implied. A
   location sweep with the R4 prefix gated by these sixteen controls is a separate design and a
   separate authorisation.

`config_status` was `0x46101f8c` + `0x46106ffd` here and in step ③, against `0x46107ffc` on
both fresh-load controls. Recorded as an observation only: it has been refuted three times as a
validity proxy and takes no part in any verdict.

## Note on a tool defect found during this run

The first attempt at step 2's acquisition was **refused** because a tracked file differed from
HEAD: `evidence/postfault_r4_step3_r4_on_fault_2026_08_16/verdict.json`. An independent
`--judge-only` re-verification had rewritten the **published** verdict in place. Every
substantive field was unchanged — `INSTRUMENT_VALID`, the same sixteen matches — and the only
delta was `elapsed_s`, from `1.9` (the acquisition) to `0.4` (the judging).

The published bytes were restored, which is what preserved the record rather than altering it,
and the refusal is the authority gate working correctly. But `--judge-only` overwriting the
acquisition's own verdict file is a genuine provenance hazard: it silently replaces an
acquisition timing with a judging timing in evidence that has already been published. It should
write elsewhere or refuse. Not fixed here — that is production code, and this was a board
procedure.
