# Request: a post-fault capture entrypoint that cannot score

Step ② of the post-fault R4 procedure is **blocked** until this exists. No board action is
authorised by this document.

## The blocker, confirmed from the source

`run_known_answer_round` runs its seven steps in sequence:

```python
step("known_answer", lambda: _write("candidate", authority, known, session))
for mode in ("train", "holdout"):
    step(f"candidate_{mode}", lambda mode=mode: _score("candidate", mode, known, session))
```

If `known_answer` **does not raise** — that is, if the write and its readback digest both
succeed — control falls straight into `_score`, which reaches
`BoardSession.score_last_transaction` and then `axi.arm_scorer`, and the hardware scorer is
armed.

Every authorisation for months has said "no arm, no scoring". That has held because the
known-answer write has faulted on all five occasions it has been run. **That is a contingency,
not a mechanism.** "Stop unless it is the specified `F_READBACK`" is currently an acceptance
rule applied to the record afterwards, and the acceptance rule cannot prevent the arm it would
later report.

The `No new code` clause of the post-fault specification therefore applies: stop, build the
entrypoint, and come back.

## What the entrypoint must be

A **capture entrypoint** whose only purpose is to produce a post-fault state and its evidence.

* It runs **`no_op` then `known_answer`, and nothing else.** There is no third step to reach.
* **A fault at `known_answer`**: record everything, stop, report.
* **An unexpected pass at `known_answer`**: record everything, stop, report — and **never call
  `_score`**. A pass is a legitimate outcome to observe and an illegitimate one to build on;
  it means the state this procedure exists to create was not created, which is a stop, not a
  reason to continue.
* **No `--continue`, `--score`, `--force`, `--allow` or any other relaxation.** The only
  arguments are the logistics ones the existing drivers take.
* It **reuses** `cal.phase_setup`, the identity check, `axi.same_boot` and the
  `InstrumentedTransport` rather than reimplementing any of them — the same rule that has
  applied to every board tool here.
* Its own tool identity and version, so its evidence cannot be confused with a full
  known-answer round's.

## What must be structurally impossible, not merely absent

The existing `tests/test_single_write_entrypoint.py` pins that `score_last_transaction` is
called from exactly one production site. **The new module must not become a second one**, and
the structural test should be extended to assert the new module never names `_score`,
`score_last_transaction`, `arm_scorer`, `CTRL_ARM` or `CTRL_MODE_HOLDOUT` at all.

That is the difference between "this code path does not score" and "this code cannot score",
and the whole point of the rewrite is to move from the first to the second.

## Tests

* the round is **at most two steps**, asserted on the emitted record rather than on the source;
* **the success path does not arm** — drive the round with a session stub whose
  `known_answer` write *succeeds*, and assert the run stops with both steps recorded and no
  scoring call made. This is the case the current driver gets wrong, so it is the case the
  test must cover;
* the fault path records the failed step, keeps the child evidence, and stops;
* the usual bookkeeping: atomic evidence, `same_boot`, plmark, no reload.

## Mutants

At least one, killed **behaviourally**: put the `_score` call back after `known_answer` and
show that the probe observes a scoring attempt on the success path. A mutant killed by a string
search would prove nothing here, because the thing being prevented is a call, not a spelling.

## Kept from the post-fault specification

The acceptance criteria for step ② are unchanged: only a stop at `known_answer` in pass 2 of
envelope 0 with `fault_code 8`, with `same_boot` passed, no reboots, `PCAP_PR` restored, the
scorer never armed, and the later stages absent — and **the envelope and fault code are still
reconstructed from `record["instrumentation"]["commands"]`**, since `AxiRefusal` does not
attach the partial transaction to the round step.

Optional, and explicitly not required by this request: the new entrypoint could perform that
reconstruction itself and record the result, which would make the evidence self-describing
instead of leaving the reading to whoever opens it later. If it does, the reconstruction must
be recorded **beside** the raw commands rather than replacing them.

## After it exists

Implementation, tests, mutants, audit and push come first. Step ② is then re-authorised
separately, and the board is not touched before that.
