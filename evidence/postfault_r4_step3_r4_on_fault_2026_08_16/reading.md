# Post-fault R4, step ③: R4 reads 16/16 on the faulted state — first observation

One `--control-only` acquisition on the post-fault state built by step ②, in **the same boot**,
with nothing between them but this run. No power cycle, no reload, no ACK, no carrier AXI, no
second transaction.

## One instrument, checked before the verdict was read

The verdict is not admissible unless step ① and step ③ are the same instrument, so that was
established first:

```
tool               board_signature_search.py/2.7.1        identical to step ①
child              probe_jtag_config_read.py/2.4.0        identical
mode               control-only                           identical
instrument_digest  8d28dcf3cae515b28cd60eff1e2ed84032516fb52c1c721dd155fe9ec332516b   identical
the sixteen FARs   identical, in the same order
the sixteen child Tcl files   byte-for-byte identical to step ①'s
plmark             18cc352c956bf6bd at start and at end — the boot that faulted
```

The capture files and child logs were re-hashed independently rather than trusted from the
tool's exit status: 32 files, no mismatch, and the sixteen `frame_sha256` in the index are the
sixteen `observed_sha256` in the verdict.

## The result

**`INSTRUMENT_VALID` — 16 of 16 whole-frame bit-exact at their own FARs.** Not partial: all
sixteen, every entry `ok`, every child returncode 0, `positive_controls_not_read` empty, no
frame read back all-zero. The non-zero word counts are identical to step ①'s, frame for frame:
48, 66, 71, 46, 84, 14, 2, 82, 57, 3, 13, 55, 30, 14, 2, 3.

The verdict file's own wording is the weaker "at least one"; the count above is what the
authorisation ruled on, and it is 16/16.

Timing matches step ① (1.9 s versus 1.7 s total, 0.06–0.12 s per child versus 0.06–0.07 s), so
there is no bookkeeping or pairing anomaly to disqualify the run.

## What this does and does not establish

**R4 read a post-fault state that carries the specified `F_READBACK` fault, and read it
bit-exactly, sixteen times out of sixteen.** Every earlier R4 success followed a *clean* no-op;
this is the first time the recovery has been applied to a state carrying a fault, which is the
state the location question actually needs.

Three limits, and none of them are small:

1. **Single trial.** The four earlier R4 acquisitions were on a clean-no-op state and needed a
   replication before they were called a method. This is one acquisition on one fault, and it
   needs the same treatment before it becomes one.
2. **The control is historical, not paired.** No non-R4 prefix was run on *this* state — that
   would have been a second acquisition and was not authorised. What makes 16/16 meaningful is
   that this state contains rung 2's spoiling condition (step ②'s no-op passed, and a clean
   no-op alone drove the 2.0.0 prefix from 16/16 to 0/16) *plus* a fault, and that Phase 2's
   pre-R4 instrument reproduced **zero** known non-zero frames on a post-fault state. Those are
   comparisons across runs. A within-state paired control does not exist and is not claimed.
3. **It says nothing about where the write landed.** No sweep was run and none is implied.

## The state now

The board was not touched after the acquisition returned. It is still powered, still in boot
`18cc352c956bf6bd`, still holding the faulted carrier, and still perishable.

What a result like this would unlock — a location sweep with the R4 prefix gated by these
sixteen controls — is a separate design and a separate authorisation. It was explicitly not
started.
