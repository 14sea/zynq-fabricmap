# Post-fault R4, step ②: the specified fault state exists, and the scorer was never armed

Executed at `58ae1fb` with the source unmodified, using `board_claimb_postfault_capture.py/1.0.0`
— the fixed two-transaction entrypoint built precisely because the full-round driver would have
continued into evaluation had the candidate passed. The old driver was not used.

## The five fresh-power preconditions, read rather than assumed

The board had been power-cycled, but that is a hint. These are the precondition, and all five
matched step ①'s reference exactly, read-only, before anything else happened:

```
devcfg CTRL          0xf8007000 = 0x4e00e07f
devcfg INT_STS       0xf800700c = 0xa802000b   PCFG_DONE = 0 (PL empty)
devcfg STATUS        0xf8007014 = 0x40000a30
SLCR FPGA0_CLK_CTRL  0xf8000170 = 0x00400800
printenv plmark      → '## Error: "plmark" not defined'
```

`plmark_only.py` could not serve for the fifth: it asserts a *known* marker is still set, and
here the variable's absence is the pass. A separate read-only check was used.

## The outcome

The CLI exited 1 with `STOP`. That is the expected interface and decides nothing — everything
below is reconstructed from `record["instrumentation"]["commands"]`, since `AxiRefusal` does not
attach the partial transaction to the round step (`failure_evidence` is empty, as anticipated).

**The round was exactly two steps:**

```
round.steps = [no_op: passed, known_answer: stopped]
```

The five later stages — `candidate_train`, `candidate_holdout`, `restore`,
`post_baseline_train`, `post_baseline_holdout` — do not appear. There was no third step to
reach.

**The envelope structure, decoded from the writes to `CTRL 0x43c02000`:**

| | no-op (restore) | known-answer (candidate) |
|---|---|---|
| BEGIN_TXN | `[158]` | `[340]` |
| pass 1 | env 0, 1, 2 — all three | env 0, 1, 2 — **all three** |
| pass 2 | env 0, 1, 2 — all three | **env 0, then nothing** |
| final STATUS | `0x0407fa44`, stable over three reads | `0x04040082` |
| FAULT read | none | `0x00000008` |

So the stop is in **pass 2 of envelope 0**, with **`fault_code 8`**. `FAULT_NAMES` gives 8 =
`readback`; the table keeps code 12 `rbsync` deliberately distinct for "the read path never came
up at all", so this is the wrong-data code, not the no-data one. This is the same reading as
rung 2 and Phase 2, which gave the identical `STATUS 0x04040082` / `FAULT 0x8`.

**The scorer was never armed.** Twelve writes reached `CTRL` across both transactions, and
`CTRL_ARM` (bit 6) and `CTRL_MODE_HOLDOUT` (bit 7) are clear in **every one of them**. That is
evidence from the wire, not an inference from the absence of a scoring step.

**Bookkeeping**, all checked:

```
same_boot.passed          true, plmark 18cc352c956bf6bd start and end
rebooted                  0 of 353 commands
missing prompt_returned   0 of 353 commands
carrier_sha256            8c3369e8e4755da5aceeb7844690d5e132b2e65647004c0a46c0e868e34f0b8a
identity                  boardid 17A6, role verify, pss_idcode 0x13722093, FCLK0 50.0 MHz
PCAP_PR                   restored to 0x4E00E07F; devcfg read back 0x4e00e07f
```

The `PCAP_PR` restore ran on **both** transactions, including the faulting one — `[351]` writes
it back and `[352]` reads `0x4e00e07f` after the fault, which is the try/finally path doing what
it claims.

## What this establishes, and what it does not

**A post-fault state of the specified kind exists in this boot**, built once, from a verified
fresh power-on, on the canonical carrier, with no evaluation of any kind. That is the entire
claim.

It establishes **nothing about R4**. No readback was attempted after the fault. Whether the
recovery sequence restores a post-fault readback — the question the whole procedure exists to
ask — is untouched by this run.

## The state on the shelf

The board was not touched after the driver returned. It is powered, holding the faulted carrier
of boot `18cc352c956bf6bd`, and the state is perishable: any power loss destroys it, and it
would have to be rebuilt from a fresh power-on.

Step ③ was not run and needs its own authorisation.
