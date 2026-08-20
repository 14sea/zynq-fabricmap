# Audit — the no-reload diagnostic no-op

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

### 3. Identity, same-boot and the marker gate all precede any write

Order in `main()`, and the gate checks the order by line number, not by presence:

```
require_plmark(args.plmark)          <- before the tty is opened at all
ident.SerialTransport(args.port)
session.verify_identity("content")   <- before same_boot
axi.same_boot(transport, expected_plmark)
run_noreload_noop(authority, known, session)
```

`require_plmark` refuses anything that is not sixteen lowercase hex digits. The marker lives in
RAM because the loader sets it with `setenv` and never `saveenv`, so that is the only shape it
can have; a paraphrase or an uppercased transcription is a typo, and a typo must not reach a
same-boot comparison. It runs **before `SerialTransport`**, so a bad argument costs no board
contact whatsoever — not even an open tty.

`same_boot` is one `printenv plmark`. It has to be asked before anything reads the carrier: if
the PL is no longer configured, reading the window stalls the CPU and costs a power cycle.

*Proven by*: `test_a_malformed_marker_refuses_before_the_tty_is_opened` drives five malformed
markers and asserts **zero transports opened and zero writes**;
`test_a_marker_mismatch_costs_zero_transactions` and
`test_an_identity_refusal_costs_zero_transactions` assert zero writes and no `round` key in the
evidence. Mutant **`skip_same_boot`** removes the interlock — killed.

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

### 6. A pass and a fault both preserve evidence and stop; no recovery, no retry

The round has one step, no loop, and one `except` arm that re-raises. The gate enforces all
three: it refuses a `for`/`while`/`async for` anywhere in the round ("a retry is expressible"),
and refuses any `except` handler that contains no `raise`.

`main()` treats a pass as a **stop**: `verdict = "STOP"`, exit code 1, evidence written
atomically through a `.part` file and `os.replace`. That is deliberate and is the same shape
the post-fault capture already uses — an unexpected success is evidence, not a green light.

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
| **B1** | exit 1, `STOP`, one passed step, the conditional-negative wording | `test_an_unexpected_pass_is_still_a_stop`, `test_the_pass_verdict_is_conditional_and_never_a_refutation` |
| **B2** | the other fault code recorded **as itself**, not folded into the A-family | `test_another_fault_code_is_recorded_as_itself` |
| **C1** | *not this tool's verdict* — whether step ① produced the specified fault is judged at step ①. What this tool guarantees is that the pre-state survives into the record, via the transaction's own `status_before` | `test_the_pre_state_survives_into_the_record` |
| **C2** | every interlock refusal costs zero transactions; a malformed marker costs zero board contact | the three `TheC2Interlocks` tests |

A1, A2 and A3 are **separated by the step-③ staging capture, not by this tool**, and a test
asserts the module never names them — so the evidence cannot be read as if the tool had decided
which of the three it was.

### 8. Mutants

```
second_transaction   KILLED — payloads written: ['restore', 'candidate']
scoring              KILLED — evaluation calls: 1
continue_after_pass  KILLED — steps taken: ['diagnostic_no_op', 'second_no_op']
retry_after_fault    KILLED — write attempts after the fault: 2
write_the_candidate  KILLED — payloads written: ['candidate']
skip_same_boot       KILLED — main must call axi.same_boot exactly once, found 0
reload               KILLED — the driver names the reload path: ['phase_setup']
relaxation_flag      KILLED — CLI options are ['--force', '--out', '--plmark', '--port']
8/8
```

Five are killed **behaviourally** — the round is executed against a stubbed write path and the
gate reports what it actually did — and three structurally. The harness verifies the unmutated
round first, on both the pass and the fault path, so a "kill" cannot be an artifact of a broken
stub.

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
tests/test_claimb_noreload_probe.py        14/14 OK
gate_claimb_noreload_probe.py              CLAIM-B NO-RELOAD PROBE ACCEPTED
mutate_claimb_noreload_probe.py            8/8 killed
gate_claimb_board_driver.py                ACCEPTED   (unchanged neighbour)
gate_claimb_postfault_capture.py           ACCEPTED   (unchanged neighbour)
mutate_claimb_postfault_capture.py         3/3 killed (unchanged neighbour)
full suite                                 1184 tests, OK, 0 skips
py_compile, git diff --check               clean
board                                      untouched, powered down
```
