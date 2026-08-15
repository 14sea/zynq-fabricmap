# R4: a startup cycle restores the readback after a transaction

Physical power cycle, precheck at the fresh reference with `PCFG_DONE=0`, repository at
`f8f0e61` with the tool untouched so the instrument would be identical to the control's, the
canonical `carrier.bit` (`8c3369e8…`) onto an empty PL, one no-op passing every hard
condition — 15/15 and none differing, digest matching, `fault=0`, `recovery_required=0`, three
latencies valid, no reboots — as marker `18cc16d61c655a90`. Then one `--control-only` in that
boot.

## The pair is valid

Checked before the verdict was read, because a pair that is not one instrument decides
nothing:

```
instrument_digest identical  : yes — 8c449bcecc07da05…
parent tool identical        : yes — board_signature_search.py/2.7.0
child versions identical     : yes — probe_jtag_config_read.py/2.4.0
same sixteen control FARs    : yes
child Tcl byte-identical     : 16 of 16
```

## The result

| | controls |
|---|---|
| R4-control — fresh load, no transaction | **16/16 bit-exact** |
| R4 — after one clean no-op | **16/16 bit-exact** |

All sixteen read, none unread, every entry `ok`, plmark identical at both ends. Expected and
observed non-zero word counts agree frame for frame: 48/48, 66/66, 71/71, 46/46, 84/84, 14/14,
and so on through all sixteen.

**The sequence `JSHUTDOWN → 12 TCK → JSTART → 2000 TCK → RCRC → JSHUTDOWN → 12 TCK` restores
the JTAG control readback in a state where the 2.0.0 prefix returned 0/16.**

This is the first positive result of the recovery ladder. R1 and R2 moved the `RCRC` around
and failed; R3 removed the shutdown and could not read at all; R4 adds a complete
shutdown/startup transition in front of the documented Table 6-6 prefix, and the readback
comes back.

## What it does not yet establish

**It is one trial.** By the rule this line has applied to every other result, a recovery needs
independent reproduction before it becomes a stable method. Nothing should be built on it
until it has been repeated on a fresh spoiled state.

**It was tested after a clean no-op, not after a fault.** The known-answer round ends in
`F_READBACK`, and that is a different state from this one. Whether R4 recovers the readback
after a *fault* is untested, and it is the state the location question actually needs.

**It is not an explanation.** Why a startup cycle restores what an `RCRC` alone could not is
unknown, and this run offers no mechanism — only that it does.

## What it reopens

Rung 2 closed a route: the location question could not be answered by JTAG readback after the
transaction that writes the candidate, because reading needed a state no transaction had
touched. R4, if it reproduces and if it also works after a fault, **reopens exactly that
route** — a post-fault sweep taken with the R4 prefix and gated by the sixteen controls would
be a measurement rather than the noise Phase 2 produced.

That is two conditionals and neither is met yet.

## The status, once more, is not the verdict

`CONFIG_STATUS` here reads `0x46106ffd` in child #1 — the spoiled state as found, since the
STAT read precedes everything — and `0x46101f8c` in children #2–16. That is the **same
transition R1 and R2 produced while reading 0/16**. The status moved identically whether the
readback was restored or not, which is the third independent confirmation that it is not a
proxy for validity in either direction.

Stopped as ruled: no retry, no reload, no location search, no mutation, no arm, no scoring.
