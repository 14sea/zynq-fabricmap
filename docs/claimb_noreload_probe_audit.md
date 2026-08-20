# Audit — the no-reload diagnostic no-op

> **1.0.1, after two rounds of adversarial review.** The first found three hard gaps in 1.0.0
> (§§0.1–0.3); the second found that the fix for §0.1 had been applied to the exception path
> and not to the other two places the same verdict could be minted (§0.4). All are closed, each
> with its own tests and mutants, and the defects are recorded because a fix whose defect is not
> written down is a fix nobody can check. 1.0.0 was pushed but never run, so nothing downstream
> depends on it; 1.0.1 has not been published yet.

## 0. What 1.0.0 got wrong

### 0.1 The B1 test exercised a path the hardware cannot take

A clean second transaction does **not** return. The transport completes all three envelopes,
reads the final status, and then refuses on the sticky `recovery_required` that
`fault_since_reset` latched (`board_uboot_axi.py:638`) — so `status_after`, `readback_frames`
and the session's saved transaction are never assigned (`gate_board_identity.py:414`), and
1.0.0's test injected a returned transaction record that no board would produce. Real B1 left
only a raw command trace, and the structured `status_before` the test asserted did not exist.

**Fixed** by recognising the shape instead of assuming it. `classify_stop` reconstructs the
final STATUS word from the run's **own command telemetry** — the reads already happened inside
the transaction, so nothing is re-read from the board — and B1 is declared only when the
refusal is the sticky-recovery one **and** the reconstructed status shows
`rb_frames_ok = 15`, `configuration_valid = 1`, `fault = 0`, `recovery_required = 1`. Anything
short of all five is `NOT_A_CLEAN_SECOND_TRANSACTION` and gets no conditional-negative verdict.

The tests now drive the **real** `InstrumentedTransport`, because the telemetry is the thing
under test: a mocked transport would let the entrypoint pass a test the board could not
reproduce. Two of them exist only to stop the recognition being a rubber stamp — one changes
the recorded STATUS reply and requires the shape to change with it, one supplies the sticky
refusal with no STATUS at all and requires the verdict to be withheld.

### 0.2 An unlogged Ctrl-C after every refusal

1.0.0 called `transport.interrupt()` on any `AxiRefusal`, copied from the post-fault capture
where it releases a console still inside a wait. Here it is not that: by the time the specified
`FAULT = 8` is read, pass 2, STATUS and FAULT have all returned prompts. So it was an extra
board action, and one that does **not** appear in the command telemetry. An adversarial probe
measured `interrupt_calls = 1`.

**Fixed** by removing it entirely. The console is left exactly as it was found, the record says
so in `no_interrupt`, `.interrupt(` is on the gate's forbidden list, and a test asserts zero
interrupts across all six stop paths.

### 0.3 Evidence was overwritten, and writability was proved too late

`os.replace` replaced an existing `<out>` without a word, and nothing established that the
destination was writable until after the board had been touched — so a run could do its board
work and then discover it had nowhere to put the result.

**Fixed** by `reserve_evidence`, which runs **before the tty is opened**: it refuses an existing
`<out>`, refuses a stale `<out>.part` from a killed run, and creates the `.part` exclusively,
which proves the directory is writable and claims the name in one step. A refusal there leaves
the old bytes byte-for-byte untouched with zero transports opened and zero writes.

---


**Offline implementation only. This entrypoint has never been run against a board, and nothing
here authorises running it.** The ruling that commissioned it was explicit: implement, audit,
push, and then rule separately on the board experiment. This document is the audit half.

What was built:

| file | what it is |
|---|---|
| `scripts/board_claimb_noreload_noop.py` | the entrypoint: one restore transaction into an already-loaded carrier, no setup phase, no loader, no second step |
| `scripts/gate_claimb_noreload_probe.py` | the structural gate — the rules below, checked against the AST rather than promised in a docstring |
| `scripts/mutate_claimb_noreload_probe.py` | the mutation gate: eight defects reintroduced one at a time, each required to die |
| `tests/test_claimb_noreload_probe.py` | fourteen tests over the pre-registered outcome shapes |

`gate_claimb_board_driver` could not be reused: it **requires** `cal.phase_setup`, which is
exactly what this driver must never call. Several of the new gate's rules are its inverse, and
that is why the gate is a separate file rather than a parameter.

---

## The contract, clause by clause

### 1. Only `--port` / `--plmark` / `--out`; no force, retry, continue or score option

The CLI is three literal options. The gate collects every `parser.add_argument` first argument,
requires each to be a literal string visible to review, requires the sorted set to be exactly
`['--out', '--plmark', '--port']`, and separately refuses any option whose name contains
`force`, `skip`, `allow`, `retry`, `continue`, `score`, `arm`, `holdout` or `reload`.

*Proven by*: mutant **`relaxation_flag`** adds `--force` and nothing else — killed. Test
`test_the_cli_offers_nothing_but_the_three_permitted_options` also refuses the strings outright.

### 2. No `phase_setup`, no loader, no reload path

The gate holds a forbidden-reference list and refuses the source if **any of these appears
anywhere in it, comments and docstrings included**: `phase_setup`, `loadb`,
`board_uboot_fpga_load`, `require_unconfigured`, plus the evaluation and second-write names of
clauses 4 and 5. The rule is deliberately a plain substring scan, not an AST reference search:
a name that cannot be written cannot be reached by an alias either.

This cost the first draft a refusal — its docstring *explained* that it does not call
`cal.phase_setup`, and the gate rejected the mention. The docstring was reworded rather than the
rule weakened.

*Proven by*: mutant **`reload`** re-inserts the setup call — killed. `phase_setup` is called
from four sites in the repository and this module is not one of them.

### 3. Two gates precede the tty; identity and same-boot precede any write

**A correction to 1.0.0's wording**, which claimed all three gates ran before the transport was
opened. Only two can: identity and same-boot are console commands and need an open tty by
construction. What is true, and what the gate checks by line number rather than by presence:

```
reserve_evidence(args.out)           <- before the tty is opened at all
require_plmark(args.plmark)          <- before the tty is opened at all
ident.SerialTransport(args.port)
session.verify_identity("content")   <- needs the transport; before same_boot
axi.same_boot(transport, expected_plmark)   <- needs the transport; before the round
run_noreload_noop(authority, known, session)
```

So the first two refusals cost **zero board contact**, and the second two cost **zero
transactions**. Those are different guarantees and the document now says which is which.

`require_plmark` refuses anything that is not sixteen lowercase hex digits. The marker lives in
RAM because the loader sets it with `setenv` and never `saveenv`, so that is the only shape it
can have; a paraphrase or an uppercased transcription is a typo, and a typo must not reach a
same-boot comparison. It runs **before `SerialTransport`**, so a bad argument costs no board
contact whatsoever — not even an open tty.

`same_boot` is one `printenv plmark`. It has to be asked before anything reads the carrier: if
the PL is no longer configured, reading the window stalls the CPU and costs a power cycle.

`reserve_evidence` runs before `require_plmark` on purpose: a marker refusal still writes an
evidence record, and it may only do so into a destination this run claimed. The gate enforces
that ordering too.

*Proven by*: `test_a_malformed_marker_refuses_before_the_tty_is_opened` drives five malformed
markers and asserts **zero transports opened and zero writes**;
`test_a_marker_mismatch_costs_zero_transactions` and
`test_an_identity_refusal_costs_zero_transactions` assert zero writes and no `round` key in the
evidence; the four `TheEvidenceDestinationIsClaimedFirst` tests cover an existing record, a
stale reservation, an unwritable directory and the absence of a leftover `.part`. Mutants
**`skip_same_boot`**, **`overwrite_evidence`** and **`reserve_after_the_tty`** — all killed.

### 4. Exactly one reuse of `_write("restore", …)`, and no new low-level write site

The round contains one call to `known_driver._write`, and the gate requires its first argument
to be the **literal** `"restore"`. The module contains no call to `run_candidate_on_board`,
`write_sequence` or `execute_transaction`, and cannot: all three are on the forbidden-reference
list of clause 2.

The repository-wide inventory is unchanged by this work:

```
run_candidate_on_board   board_calibrate_noop.main, board_claimb_known_answer._write
write_sequence           board_carrier_exec.board_uboot_transmit.transmit
execute_transaction      gate_board_identity.BoardSession.write_sequence
```

`tests/test_single_write_entrypoint.py` — which pins that inventory, and which existed before
this work — still passes unchanged. The module also never names the carrier's AXI window, which
that test requires to appear in `board_uboot_axi.py` alone.

*Proven by*: mutant **`write_the_candidate`** renames the single write's payload — killed by
observation, not by the gate: the stub records which payloads were actually written.

### 5. Scorer, ARM, HOLDOUT and the candidate are structurally unreachable

`_score`, `score_last_transaction`, `arm_scorer`, `CTRL_ARM`, `CTRL_MODE_HOLDOUT`,
`run_known_answer_round` and `run_postfault_capture` are all on the forbidden list. The gate
additionally refuses the round if the string `"candidate"` appears among its constants.

*Proven by*: mutants **`scoring`** (an evaluation call after the no-op) and
**`second_transaction`** (a candidate write after the no-op) — both killed by observing the
stub, which counts evaluation calls and records payload names.

### 6. A pass and a fault both preserve evidence and stop; no recovery, no retry, no interrupt

The round has one step, no loop, and one `except` arm that re-raises. The gate enforces all
three: it refuses a `for`/`while`/`async for` anywhere in the round ("a retry is expressible"),
and refuses any `except` handler that contains no `raise`.

`main()` treats a pass as a **stop**: `verdict = "STOP"`, exit code 1, evidence written into the
reservation this run claimed before it touched the board, then `os.replace`d into place. That is
deliberate and is the same shape the post-fault capture already uses — an unexpected success is
evidence, not a green light. And there is **no interrupt on any path** (§0.2).

**The pass verdict is worded as a conditional negative and cannot drift.** It reads: *"THE
DIAGNOSTIC NO-OP PASSED; CONDITIONAL NEGATIVE FOR STRICT H-STALE — this run did not observe its
own starting content, so this is not a refutation."* A test asserts the phrase
`CONDITIONAL NEGATIVE` is present and that the words `REFUTED`, `refutes`, `DISPROVED` and
`PROVEN` are absent from both the round verdict and the CLI stop reason.

*Proven by*: mutants **`continue_after_pass`** (a second step after the pass) and
**`retry_after_fault`** (the fault swallowed and the write repeated) — both killed by
observation: the first shows two steps where the baseline shows one, the second shows two write
attempts where the baseline shows one.

### 7. Tests cover the pre-registered outcome shapes

| reading | what the tool produces | test |
|---|---|---|
| **A1 / A2 / A3** | `fault_code 8 (readback)`, one stopped step, exactly one payload written, the round claiming no verdict | `test_the_specified_fault_stops_with_its_shape_preserved`, `test_the_fault_branch_never_writes_again` |
| **B1** | the sticky-recovery refusal, recognised from the message **and** a status reconstructed from telemetry as 15/15 + `configuration_valid` + no fault + `recovery_required`; exit 1, `STOP`, the conditional-negative wording | `test_a_clean_second_transaction_is_recognised_from_the_refusal`, `test_the_four_fields_are_reconstructed_from_the_telemetry`, `test_the_reconstruction_reads_the_run_s_own_recorded_reply`, `test_a_sticky_refusal_without_the_status_is_not_promoted`, `test_the_pass_verdict_is_conditional_and_never_a_refutation` |
| **not B1** | a normal return: `UNEXPECTED_NORMAL_RETURN`, `verdict: None`, and the phrase "CONDITIONAL NEGATIVE" absent from the **whole** record | `test_a_normal_return_stops_without_a_conditional_negative`, `test_only_the_classifier_can_issue_the_conditional_negative` |
| **B2** | the other fault code recorded **as itself**, not folded into the A-family | `test_another_fault_code_is_recorded_as_itself` |
| **C1** | *not this tool's verdict* — whether step ① produced the specified fault is judged at step ①. What this tool guarantees is that every STATUS word it saw survives verbatim in the telemetry, so the pre-state and the final state are both reconstructable | the reconstruction tests above |
| **C2** | every interlock refusal costs zero transactions; a malformed marker or a taken/unwritable destination costs zero board contact | `TheC2Interlocks` ×3, `TheEvidenceDestinationIsClaimedFirst` ×4 |

A1, A2 and A3 are **separated by the step-③ staging capture, not by this tool**, and a test
asserts the module never names them — so the evidence cannot be read as if the tool had decided
which of the three it was.

### 8. Mutants

```
second_transaction    KILLED — payloads written: ['restore', 'candidate']
scoring               KILLED — evaluation calls: 1
continue_after_pass   KILLED — steps taken: ['diagnostic_no_op', 'second_no_op']
retry_after_fault     KILLED — write attempts after the fault: 2
write_the_candidate   KILLED — payloads written: ['candidate']
skip_same_boot        KILLED — main must call axi.same_boot exactly once, found 0
reload                KILLED — the driver names the reload path: ['phase_setup']
relaxation_flag       KILLED — CLI options are ['--force', '--out', '--plmark', '--port']
interrupt_after_fault   KILLED — the driver names ['.interrupt(']
overwrite_evidence      KILLED — main must call reserve_evidence exactly once, found 0
reserve_after_the_tty   KILLED — reserve_evidence must precede opening the transport
bypass_classifier       KILLED — main must call classify_stop exactly once, found 0
normal_return_is_b1     KILLED — PASS_VERDICT referenced outside classify_stop, in ['main']
round_mints_the_verdict KILLED — PASS_VERDICT referenced outside classify_stop, in
                                 ['run_noreload_noop']
14/14
```

Five are killed **behaviourally** — the round is executed against a stubbed write path and the
gate reports what it actually did — and nine structurally. The harness verifies the unmutated
round first, on both the pass and the fault path, so a "kill" cannot be an artifact of a broken
stub, and `reserve_after_the_tty` is parsed with `ast` before it is judged so that it cannot be
"killed" for being a syntax error instead of for being wrong.

---

## What this does not establish

* **It has never touched a board.** Every result above is from AST inspection and stubs. The
  first real transaction is a separate ruling.
* **It does not make §9 step 6 pass.** Restore and a post-restore baseline remain downstream.
* **It cannot separate H-PAD from H-ADDR from H-IDLE.** That needs internal read-path
  instrumentation or a carrier with distinctive non-blank targets; PCAP/devcfg answers a
  different question. `claimb_read_side_divergence_design.md` §7.2 is the argument.
* **A pass would remain a conditional negative.** The run performs no R4/JTAG read between the
  fault and the transaction, because that read perturbs the configuration engine, so it never
  observes its own starting content. Nothing in the implementation or its output is permitted to
  upgrade that, and a test holds the wording.

## Verification performed

```
tests/test_claimb_noreload_probe.py        24/24 OK
gate_claimb_noreload_probe.py              CLAIM-B NO-RELOAD PROBE ACCEPTED
mutate_claimb_noreload_probe.py            14/14 killed
adversarial re-probe, round 1              interrupts 0; old evidence bytes unchanged with
                                           0 transports opened and 0 writes; B1 recognised as
                                           CLEAN_SECOND_TRANSACTION with 15/15, cv=1, fault=0,
                                           recovery_required=1
adversarial re-probe, round 2              a normal return with STATUS 0x0407FA44 gives
                                           UNEXPECTED_NORMAL_RETURN, verdict None, and no
                                           "CONDITIONAL" anywhere in the record; the gate
                                           refuses a source that defines classify_stop and
                                           then bypasses it
gate_claimb_board_driver.py                ACCEPTED   (unchanged neighbour)
gate_claimb_postfault_capture.py           ACCEPTED   (unchanged neighbour)
mutate_claimb_postfault_capture.py         3/3 killed (unchanged neighbour)
full suite                                 1194 tests, OK, 0 skips on the clean tree
py_compile, git diff --check               clean
board                                      untouched, powered down
```
