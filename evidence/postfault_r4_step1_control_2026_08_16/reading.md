# Post-fault R4, step ①: the instrument is verified under the new identity

The fresh-load control that the post-fault procedure requires before a fault state may be
built. Executed at `9b76ec9` with the source unmodified.

## The five preconditions, read rather than assumed

"The board was restarted" is a hint; these are the precondition, and all five were met:

```
devcfg INT_STS  0xa802000b   PCFG_DONE = 0
devcfg STATUS   0x40000a30   (unconfigured)
devcfg CTRL     0x4e00e07f
FPGA0_CLK_CTRL  0x00400800
printenv plmark → "## Error: \"plmark\" not defined"
```

Then the canonical `carrier.bit`, its full digest checked rather than its prefix —
`8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a` — loaded once onto the
empty PL as marker `18cc31f32a543603`, **no transaction of any kind**, and one
`--control-only`.

## The result

**`INSTRUMENT_VALID` — 16 of 16 whole-frame bit-exact.** Every success condition the
authorisation named:

```
16/16 whole-frame bit-exact   PASS      parent board_signature_search.py/2.7.1   PASS
none unread                   PASS      child  probe_jtag_config_read.py/2.4.0   PASS
all entries ok                PASS      digest 8d28dcf3cae515b2…                 PASS
plmark start == end           PASS      per-child tcl digests match              PASS
```

Expected and observed non-zero word counts agree frame for frame: 48/48, 66/66, 71/71, 46/46,
84/84, and so on through all sixteen.

## What it establishes

**The R4 instrument is verified under the new `2.7.1` identity.** The four earlier
acquisitions were taken under `2.7.0` and `validate_index` refuses them by tool version, so
they could not have stood in for this — which is the point of a new identity rather than an
inconvenience of it. Step ② is now permitted to be authorised.

It establishes nothing about a fault. No transaction of any kind has been run in this boot.

## Note carried forward for step ②

`AxiRefusal` failures do not attach `execute_transaction`'s partial record to the round step,
so the envelope and fault code of a known-answer stop must be reconstructed from
`record["instrumentation"]["commands"]` — the same reading used for rung 2 and Phase 2, where
the trailing `md.l 0x43c02004` and `0x43c02008` replies gave `STATUS 0x04040082` and
`FAULT 0x8`. The complete command evidence is present, so the step ② acceptance criteria
remain checkable; the reading itself should be pinned when step ② is authorised.

Also observed, not interpreted: `CONFIG_STATUS` is `0x46107ffc` in child #1 and `0x46101f8c`
in children #2–16 — the fresh-load pattern, unchanged by the wording fix, and still not part
of any verdict.

Stopped as ruled: step ② not started, and it needs another physical power cycle and its own
authorisation.
