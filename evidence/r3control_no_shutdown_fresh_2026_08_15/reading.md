# R3-control: without JSHUTDOWN nothing reads, even on a device that reads

The positive control R3 needs before its result can mean anything. Physical power cycle,
precheck at the fresh reference with `PCFG_DONE=0`, repository at `3314d76` with a clean
tracked tree, the canonical `carrier.bit` (`8c3369e8…`) onto an empty PL as marker
`18cc13d89421a2c8`, **no no-op and no transaction of any kind**, then one `--control-only`.

These are rung 1's conditions exactly. The only difference is the script.

## It really was the R3 sequence

```
children whose ACTUAL tcl is the R3 sequence (no JSHUTDOWN, no runtest) : 16 of 16
tcl digests matching their capture                                      : 16 of 16
child tool versions                                                     : probe 2.3.0 ×16
```

## The result

**`INSTRUMENT_INVALID`, 0 of 16, all sixteen read.** Every frame came back all-zero.
`CONFIG_STATUS` was `0x46107ffc` in all sixteen children — the value the *valid* fresh-load
state reports.

Against rung 1, which read the same sixteen controls under the same conditions **with**
`JSHUTDOWN`:

| | rung 1 | R3-control |
|---|---|---|
| board state | fresh load, no transaction | fresh load, no transaction |
| controls | the same sixteen | the same sixteen |
| `JSHUTDOWN` | yes | no |
| result | **16/16 bit-exact** | **0/16** |

## What this settles

**`JSHUTDOWN` is necessary for this readback path to return configuration data at all, on
this device, even in a state known to be readable.**

And therefore: **R3 cannot be run.** Not "R3 failed" — the rung is unrunnable, because its
instrument reads nothing in any state, so a 0/16 from it would have carried no information
about the spoiled state whatsoever. This is precisely the outcome R3-control existed to
detect, and detecting it cost one load and twelve seconds of reading instead of a board run
whose negative result would have been quietly meaningless.

It is also a second, independent refutation of `CONFIG_STATUS` as a validity proxy. R1 and R2
reported the good values while reading 0/16 in a spoiled state; this reports the good value
in a state that is genuinely fine, while reading 0/16 because the script cannot read. The
status tracks the device, not the measurement.

## What is left of the ladder

R1, R2 and R3 exhaust the arrangements of `JSHUTDOWN` and `RCRC` that need no new
instruction — and R3's arrangement turns out not to be a legal instrument at all.

Untested, and still needing no new instruction, are the timing variants the R2 correction
already named as unsupported: a dwell longer than 1024 TCK, a wait inserted between the
`RCRC` and the first `FDRO`, and a slower TCK. R4 (`JSTART`) remains behind the allowlist
procedure, and it would now have to be `JSHUTDOWN` plus reads plus `JSTART` rather than a
replacement for the shutdown, since the shutdown is not optional.

Stopped as ruled: R3 not attempted, no sweep, no mutation, no arm, no scoring.
