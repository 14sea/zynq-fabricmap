# The all-zero staging copy reproduces

One authorised read-only capture, in run 2's fault boot, before any power cycle, under a
separate authorisation whose scope was exactly one question: **does the all-zero staging copy
reproduce?** It does. Nothing else is judged here — no mechanism is inferred.

`probe_ddr_capture.py/1.1.0` touches no carrier register: `echo`, `printenv plmark`, one
`md.l 0x10100000 0x65`. Output path did not exist beforehand; `--plmark` was the current fault
boot's `18cd7cb81a291de5`; slot 0 only; no acknowledgement, retry, reload or recovery.

## Run 2 against run 1

```
                       run 2 (18cd7cb81a291de5)          run 1 (18cd7785cbf1b1fd)
address                0x10100000                        0x10100000
slot / words           0 / 101                           0 / 101
nonzero_words          0                                 0
frame_sha256           0441772f66559a1c…6d7b8de9         0441772f66559a1c…6d7b8de9   identical
verdict (offline)      UNDISCRIMINATING                  UNDISCRIMINATING
equals candidate frame False                             False
equals base frame @FAR True                              True
```

Two separately built fault states, two boots, two different `plmark`s, and the staging copy of
the failing frame is byte-identical: all zero.

## What this says, and the two things it does not

* **It reproduces.** The all-zero staging observation is not a one-off of run 1.
* **It still names no address.** The offline analysis is `UNDISCRIMINATING` by its own
  criterion: an all-zero window matches 474,494 word offsets of the device stream and is
  invariant under bit-swap and word-alignment variants. Nothing here says *which* frame the
  engine read.
* **No mechanism is claimed or implied.** Why a zero frame arrived in staging while the
  addressed frame held the candidate remains the deferred question, and this capture was
  authorised as evidence for it, not as an investigation of it.

Read against step ④ of the same boot — `A20` holding the candidate, 16/16 controls — the pair
says for run 2 what it said for run 1: the write landed, and what the readback path delivered
was not the content of the frame it was addressing. That is a restatement of two committed
observations, not a new inference.

## State

Read-only. The board may now be powered down; nothing further is authorised.
