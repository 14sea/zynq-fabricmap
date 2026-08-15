# A new OpenOCD process restores the read, with no reload

The board was **not** power-cycled and the bitstream was **not** reloaded. This is the same
configured, already-JSHUTDOWN'd fabric that run C left behind, proved by reading `plmark`
over the PS UART alone — `18cc00f0fa537908`, the marker the load set — with no carrier AXI
access, no `md` of the fabric and no writes (`plmark_precheck.txt`).

One new OpenOCD process then read `0x00400A20` and nothing else.

## The result

`0x00400A20` came back **101 of 101 words identical to `carrier_eco.bit`**, ECC consistent,
both of its discriminating bits at their exact predicted positions.

That is the same frame that came back all zero eleven minutes earlier, as the second read of
run C's session:

| run | position of A20 | CONFIG_STATUS | A20 frame |
|---|---|---|---|
| B | first of its session | `0x46107ffc` | `02fc3959…` exact |
| C | second of its session | `0x46107ffc` | `0441772f…` all zero |
| D (this run) | first of a **new process**, same load | `0x46101f8c` | `02fc3959…` exact |

**A new process restores a reliable read.** The limit is therefore not "one read per loaded
bitstream" and not anything about the address — it is bounded by the process, or by the
`JSHUTDOWN` that each process issues, or by the first `CFG_OUT` after it. This run cannot
separate those three, and does not need to: any of them makes the same practical prediction.

## What this makes affordable

A cross-frame signature search — the thing Phase 2 would need if `0x00400A20` came back as
base and the write had to be hunted for elsewhere — is now **one OpenOCD process per frame**,
which is seconds each. It does not require a reload, so a post-fault state survives the
search intact. That was the open question this round existed to answer.

`CONFIG_STATUS` differs from the earlier runs (`0x46101f8c` against `0x46107ffc`), which is
expected: this process met a device that run C had already shut down. It is recorded rather
than interpreted.

## One honest note about the verdict string

`analysis.json` says `CONTROL PARTIAL`, because the analyzer's expectation list holds all
three ECO bits and this run deliberately read only the frame carrying two of them.
`INIT[35]` is reported `NOT READ`, not `MISS`. For what was read the result is unqualified:
1 of 1 frames matched exactly, both bits hit.

Stopped here per the authorisation. The board is to be powered off next. No `known-answer`
round was started and Phase 2 remains unauthorised.
