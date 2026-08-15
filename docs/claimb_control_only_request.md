# Request: a production `--control-only` mode, and the hardware gradient it serves

**Authorisation as it stands.** The board is powered but must be treated as merely rebooted;
a read-only devcfg precheck showing `PCFG_DONE=0` is required before anything. No board run
is authorised by this document. The implementation is offline work; it is audited, pushed,
and only then does a board ruling follow.

## Why a mode, rather than another sweep

The Phase 2 acquisition was flawless and its location verdict was void: in that post-fault
state not one known non-zero base frame came back bit-exact, only 82 of 4,292 non-zero
captured frames were even ECC-consistent, and no base frame appeared anywhere in the stream
under five transforms. The `2.2.0` gate now refuses to reach a location verdict without a
positive control, which is the right refusal — but nothing has yet *passed* that gate on
this board in any state.

So the next board contact should ask one question and only that: **can this JTAG path read a
known frame in state X?** Reading 5,144 frames to find out is 5,143 frames of noise.

## The gradient, and what each rung reads

1. **fresh load → control-only.** Load the canonical carrier onto an empty PL, do not run a
   transaction, read the controls.
2. **fresh boot → no-op passes → control-only.** The no-op is a complete ICAP transaction
   that has never faulted.
3. **known-answer fault → control-only.** Only after 1 and 2 are readable.

| outcome | reading |
|---|---|
| rung 1 fails | the JTAG method or the control set itself is wrong; nothing downstream means anything |
| 1 passes, 2 fails | **any** ICAP transaction spoils subsequent JTAG readback |
| 1 and 2 pass, 3 fails | the fault state itself spoils it |
| 3 passes | and only then may a location search be attempted again |

Each rung is one load and one short read. Rungs are separate board rulings.

## The contract for `--control-only`

* **Reads the sixteen pinned positive controls and nothing else.** Not the intended FAR, not
  a sweep, no `--far` to widen it. `EXPECTED_POSITIVE_CONTROL_FARS` stays the only set, still
  derived and still refusing to drift.
* **Emits only `INSTRUMENT_VALID` / `INSTRUMENT_INVALID` / `INSTRUMENT_UNVALIDATED`.** It
  must be structurally unable to produce a location verdict — no `signature_hits`, no
  `WRITE_LANDED_*`, no `NOT_FOUND_*` — because the mode exists precisely for states where
  those would be lies.
* Everything `2.2.0` already enforces is unchanged and reused rather than re-implemented:
  one child per FAR spawning the reviewed probe, the canonical authority bound to HEAD and to
  the reviewed artifact, atomic captures and index, `validate_index()` on every path, plmark
  read before and after with the closure belonging to the invocation, failed children landing
  their stdout/stderr/argv, and coverage recomputed rather than read from the index.
* **A control-only index and a sweep index must not be mistakable for one another.** Record
  the mode in the index and refuse to resume or judge one as the other.
* **Record `CONFIG_STATUS` per capture in the index.** The `2.1.0` index dropped it and it had
  to be read back out of the captures for `evidence/config_status_observation.json`. It is now
  a classifier candidate and belongs in the summary.
* Fail-closed stays fail-closed: no controls read is `INSTRUMENT_UNVALIDATED`, never a
  cheerful nothing.

## What the tests and mutants have to pin

* the mode reads exactly the sixteen control FARs — no more, no fewer, and none outside them;
* a mutant that lets `--control-only` emit any location verdict is killed;
* a mutant that widens the read set beyond the pinned controls is killed;
* a mutant that lets a control-only index be judged as a sweep, or resumed as one, is killed;
* the three verdicts are reachable and distinguishable on synthetic captures, including the
  wrong-but-non-zero case that `any_nonzero_control_passes` already covers.

## One observation to carry, not to act on

`evidence/config_status_observation.json`: every readback that reproduced a known frame
reported `0x46107ffc` or `0x46101f8c`; the 5,144 captures of the state where none did all
reported `0x46106ffd`, uniformly. That is recorded as a classifier candidate and nothing more
— three exact runs against one invalid run is not a test, and two of the three exact runs
share a device state as well as a status. The gradient above will produce the data that
would make it a finding or discard it.
