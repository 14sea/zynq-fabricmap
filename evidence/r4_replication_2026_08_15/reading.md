# R4 replication: reproduced, on one instrument, across four acquisitions

A second, independent R4 pair. Physical power cycle before each acquisition, read-only
precheck at the fresh reference both times, the canonical `carrier.bit` (`8c3369e8…`) loaded
once per acquisition, and the source left untouched throughout so the instrument could not
drift — the reason the misleading `INSTRUMENT_VALID` wording is still in place.

* **control** — fresh load, no transaction, marker `18cc1794d0d627a3`
* **R4** — fresh load, one no-op passing every hard condition, marker `18cc186af4bc9869`

## The four acquisitions

| | verdict | controls | plmark | entries |
|---|---|---|---|---|
| original control | `INSTRUMENT_VALID` | **16/16** | closed | all ok |
| original R4 | `INSTRUMENT_VALID` | **16/16** | closed | all ok |
| replication control | `INSTRUMENT_VALID` | **16/16** | closed | all ok |
| replication R4 | `INSTRUMENT_VALID` | **16/16** | closed | all ok |

## One instrument, checked rather than asserted

```
one instrument_digest across all four : 8c449bcecc07da05…
one parent + child tool set           : board_signature_search.py/2.7.0, probe_jtag_config_read.py/2.4.0
identical sixteen control FARs        : yes
child Tcl byte-identical across all 4 : yes — 16 scripts per run, all identical
```

Sixty-four child reads, four acquisitions, two power cycles, one script.

## What is now established

**R4 is an independently reproduced recovery method for the state left by a clean ICAP
no-op.** The sequence

```
JSHUTDOWN → 12 TCK → JSTART → 2000 TCK → RCRC → JSHUTDOWN → 12 TCK → FDRO
```

restores a JTAG control readback that the 2.0.0 prefix returned 0/16 on, and it does so twice,
on two separate boots, with the fresh-load control passing both times to show the instrument
was sound on each occasion.

## What is still not established

**Nothing about a fault.** Every R4 acquisition so far followed a *clean* no-op. The
known-answer round ends in `F_READBACK`, and that is the state the location question needs.
Whether R4 recovers a post-fault readback is untested and must not be assumed from this.

**No mechanism.** Why a startup cycle restores what `RCRC` alone could not remains unknown.
The rung is a method, not an explanation.

**Nothing about where the candidate went.** The location question is exactly as open as it was
before the ladder started.

## What is unblocked

The deferred correction to the `INSTRUMENT_VALID` message — it says "in this post-fault state"
regardless of the state — can now be made additively. The pair it would have invalidated is
closed, and any future comparison against these four acquisitions will be against a different
`instrument_digest` by design, which is the honest way to mark the boundary.

Post-fault R4 and a location sweep both remain to be designed and authorised separately.

Stopped as ruled: no retry, no reload, no known-answer, no sweep, no mutation, no arm, no
scoring.
