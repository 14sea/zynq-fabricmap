# Post-fault R4: does the recovery work on the state the location question needs?

Specification only. **No board action is authorised by this document.** Step ① is authorised
separately, and steps ② and ③ separately again.

## What is being asked, and why it is not settled

R4 is an independently reproduced recovery: four acquisitions on one instrument, 16/16 each
time, restoring a readback that the 2.0.0 prefix returned 0/16 on. Every one of those followed
a **clean no-op**. The known-answer round ends in `F_READBACK`, and that is a different state —
the one the location question actually needs. Whether R4 recovers it is untested.

The state is **re-creatable but single-use**: the known-answer round has faulted identically on
five separate occasions, so a spoiled instance can be rebuilt, but an instance that has been
disturbed cannot be un-disturbed. The care below is about not wasting one, not about a state
that can never be had again.

## Fixed entrypoints

The first version of this specification named `board_claimb_known_answer.py` for step ②.
Review found that an unexpected candidate pass would make that full-round driver continue
into evaluation, violating this procedure's no-arm boundary. The procedure stopped before
step ②, and `claimb_postfault_capture_request.md` recorded the required correction.

Step ② now uses `board_claimb_postfault_capture.py/1.0.0`, whose fixed round is exactly
`no_op → known_answer` and has no third step on either the fault or pass path. Steps ① and ③
continue to use `board_signature_search.py --control-only`. If any later step turns out to
need orchestration that does not exist, the same rule applies: stop and hand it back —
implementation, tests, mutants, audit and push come first.

## Step ① — the fresh-load control, under the new identity

"The board was restarted" is a **hint, not a precondition**. The precondition is what the
read-only precheck reports:

```
devcfg INT_STS  0xA802000B   with PCFG_DONE = 0
devcfg STATUS   0x40000A30   (unconfigured)
devcfg CTRL     0x4E00E07F
FPGA0_CLK_CTRL  0x00400800
printenv plmark → not defined
```

Any of those wrong: stop, and do not rebuild the state by hand.

Then: canonical `carrier.bit` (`8c3369e8…`) loaded once, **no transaction of any kind**, and
one `--control-only` with

```
parent  board_signature_search.py/2.7.1
child   probe_jtag_config_read.py/2.4.0
digest  8d28dcf3cae515b2…
```

**16/16 whole-frame bit-exact, or the whole procedure stops.** The four 2.7.0 acquisitions
cannot stand in for this: `validate_index` refuses them by tool version, which is the point of
the new identity rather than an inconvenience of it.

## Between ① and ② — a physical power cycle

Not optional. Step ① has itself read the device sixteen times, and R0 established that a
probed state is not the state that was probed.

## Step ② — build the fault with the fixed capture driver, and accept only the specified one

The driver executes these stages, and the record must show all of them:

1. `PublishedCarrierAuthority.load()` and `KnownAnswerAuthority.load()` — both bound to the
   HEAD blob and a clean tree;
2. `phase_setup`: `board_set_fclk50.py`, then `board_uboot_fpga_load.py --op loadb
   --require-unconfigured`, then the `plmark` capture;
3. `InstrumentedTransport` wrapping the serial transport **before** the session exists;
4. `BoardSession.verify_identity("content")`;
5. `axi.same_boot(transport, plmark)`;
6. `transport.mark("before run_known_answer_round")`;
7. the round: `no_op` then `known_answer`.

**The only acceptable outcome is a stop at `known_answer`, in pass 2 of envelope 0, with
`fault_code 8 (readback)`.** Anything else — a different fault code, a different envelope, a
pass, a stop in `no_op` — is not the state this procedure is about, and the answer is to stop
rather than to reinterpret.

The fault state must simultaneously satisfy, checked from the record:

* `round.steps` is exactly `[no_op: passed, known_answer: stopped]` — **the five later stages
  (`candidate_train`, `candidate_holdout`, `restore`, `post_baseline_train`,
  `post_baseline_holdout`) must not appear**;
* `same_boot.passed` true;
* zero commands with `rebooted`, zero without `prompt_returned`;
* `pcap_pr` reports `PCAP_PR restored to 0x4E00E07F`;
* the scorer was never armed — no `score` step ran, and the arm is unreachable without a
  digest match in any case.

## Between ② and ③ — nothing

No reload, no acknowledgement, no recovery attempt, no AXI transaction, no second look at the
carrier. The only permitted actions are the `plmark` check over the PS UART alone and the
step ③ acquisition itself.

## Step ③ — R4 on the fault, in the same boot

One `--control-only`, and it must match step ① on every axis:

```
identical instrument_digest   8d28dcf3cae515b2…
identical parent and child versions
identical sixteen control FARs
child Tcl byte-identical between ① and ③
```

Checked **before** the verdict is read. A pair that is not one instrument decides nothing.

## The verdict

Sixteen controls, whole-frame bit-exact at their own FARs. `CONFIG_STATUS` does not
participate — it has been refuted three times, twice reporting good values while reading 0/16.
Captured content is not compared across runs — R0 showed two runs of one rung disagree on nine
frames of sixteen.

| outcome | reading |
|---|---|
| ① not 16/16 | the instrument is unverified under the new identity; stop, and ② is not run |
| ② not the specified fault | there is no post-fault state; stop |
| ③ 16/16 | **R4 recovers a post-fault readback — first observation, and it needs independent reproduction before it is a method for this state** |
| ③ 0/16 | this run does not support R4 recovering the fault state |
| ③ partial or bookkeeping anomaly | not interpretable; stop and keep everything |

## Standing limits

Each step runs **once**. No retries, no reloads, no location sweep, no mutation, no arm, no
scoring. Any fault, reboot, marker mismatch, child failure or evidence anomaly stops the
procedure where it happened, with the evidence kept.

What a `③ 16/16` would unlock is a location sweep with the R4 prefix gated by the sixteen
controls — the measurement Phase 2 could not make. That is a separate design and a separate
authorisation, and it is not implied by success here.
