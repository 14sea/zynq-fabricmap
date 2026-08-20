# The read-side divergence experiment — B1

One authorised conditional chain, `docs/claimb_read_side_divergence_design.md` §7.4 steps ①–④,
run 2026-08-20 under a ruling that fixed every stop condition in advance. It reached step ④ and
stopped there. **No command was sent to the board after the DDR capture.** The operator then
powered it down, which was confirmed the only way it can be without touching the board — from
the host: the CH340 gone from `lsusb`, `/dev/ebaz-uart` absent, and one `ch341-uart …
disconnected` in the kernel log with no re-attach after it.

## The one sentence

> After the specified fault, a diagnostic no-op run in the same boot **without a reload**
> completed fifteen of fifteen frames. That is a **conditional negative** for strict H-STALE,
> not an unconditional refutation. **H-PAD, H-ADDR and H-IDLE all survive.**

## What ran, and what each step returned

| step | tool | result |
|---|---|---|
| ① | `precheck_fresh_power.py/1.0.1` | **PASS**, five of five. `devcfg CTRL 0x4e00e07f`, `INT_STS 0xa802000b` (`PCFG_DONE=0`), `STATUS 0x40000a30`, `FPGA0_CLK_CTRL 0x00400800`, `plmark` undefined |
| ② | `board_claimb_postfault_capture.py/1.0.0` | the specified fault. `[no_op: passed, known_answer: stopped]`, pass 2 of envelope 0, `STATUS 0x04040082`, `FAULT 0x00000008`, `rb_latency_words = 1` valid, identity `17A6`, same-boot, PCAP_PR restored, scorer unarmed, no-op verified 15/15. Wall **250.5 s** — the two 2026-08-20 builds were 250.5 s and 250.4 s |
| ③ | `board_claimb_noreload_noop.py/1.0.1` | **B1.** `CLEAN_SECOND_TRANSACTION`; the sticky-recovery refusal with `final_status = 0x0407FAC4` → `rb_frames_ok = 15`, `configuration_valid = 1`, `fault = 0`, `recovery_required = 1`. One step, one payload, no reload |
| ④ | `probe_ddr_capture.py/1.1.0` | slot 0: 101 words, **0 non-zero**, sha256 `0441772f6655…6d7b8de9` |

`plmark` is `18cd905081d10912` in all five places it appears: the loader's own output, the fault
record's `same_boot`, the no-op's `same_boot`, the DDR capture's expected marker, and the DDR
capture's observed marker. One boot, end to end.

## Why B1 is conditional, and stays conditional

The pre-registered reading (design §8, row B1) is a **conditional** negative and this run does
not upgrade it. The chain deliberately performed **no R4, no JTAG readback, no DDR read and no
reload between the fault and the diagnostic no-op** — an R4 acquisition changes the
configuration-engine state this experiment is about. So the run **never observed that this
instance held the candidate at `0x00400A20` before the no-op wrote over it.**

The unconditional finding is therefore only: *after the specified fault, the diagnostic no-op
passed.* O1 and O2 established the landing for **their** instances and may not be borrowed as a
same-run measurement for this one.

**One wording correction, on the record.** "No board action after the fault" would be false.
`board_claimb_postfault_capture.py/1.0.0` sends its own `<INTERRUPT>` after an `AxiRefusal` and
then restores PCAP_PR — both recorded in its evidence (`interrupt_reply`, and the closing
`mw 0xf8007000 0x4e00e07f` with its readback). That is the frozen fault builder's existing,
documented behaviour and part of building the state, not something this experiment added.
`board_claimb_noreload_noop.py/1.0.1` sends no console action of its own — no `interrupt_reply`
in its record, and its `no_interrupt` field says so. The accurate statement is the one above:
**nothing between the fault and the no-op read, addressed or reconfigured the fabric.**

## The slot-0 capture, and what it is *not*

`analysis_ddr_slot0.json` (`analyse_ddr_capture.py/1.0.0`): **`UNDISCRIMINATING`**. All zero,
equal to the base frame at `0x00400A20`, unequal to the candidate, matching **474,494** word
offsets of the device stream. It names no address, and an all-zero window is invariant under
bit-swap and word-alignment variants.

**Its provenance is different from the two earlier captures, and the bytes matching does not
make it a third instance of them.** The 2026-08-20 captures in `location_sweep_…` and
`location_reproduction_…` were taken after the **candidate** round faulted, so slot 0 held the
**failing** frame's staging. This one was taken after the **no-op completed 15/15**, so slot 0
holds that transaction's own readback of envelope 0 frame 0 — blank content written, blank
content read, blank content verified. Identical bytes, different question answered. It is
consistent with the blank-returning family and adds no discriminating information, which is
exactly what the design predicted for this branch.

## What this run does establish, unconditionally

The engine's readback path can complete a **full fifteen-frame transaction in a second
transaction, into an already-faulted carrier, with no reload** — reaching `configuration_valid`
and refusing only on the sticky `recovery_required` that `fault_since_reset` latched. That had
never been run before.

It says nothing about content. All fifteen frames of the write envelope are byte-identical and
all zero (F1), and the no-op writes exactly that content (F2), so this is another instance of
the degenerate control, not a demonstration that the frame-data path delivers what it addresses.

## What it does not establish

* **Not a refutation of H-STALE.** Conditional, for the reason above.
* **H-PAD, H-ADDR and H-IDLE are untouched.** This experiment cannot separate them and was never
  going to: every frame the engine can address is blank before the write (design §7.2).
* **Claim B still has ZERO data points.** The preregistration remains DRAFT, §6's budget unfrozen
  and §10's freeze never performed.
* **§9 step 6 has not advanced.** Restore and a post-restore baseline remain downstream of an
  interlock that still faults.
* **Still one instrument.** Same host, cable, tool bytes, carrier and board; a systematic
  instrument error would reproduce faithfully.

## What this run did to the frozen inventory

This run added a seventh engine record and a seventh staging copy, so W2's closed population
moved and its two-way guard refused until the inventory was extended deliberately — which is
what that guard is for. The extension, the new counts (7 transactions / 105 frames / 0
non-blank) and one omission the guard exposed in the old list are recorded in
`evidence/read_side_facts_2026_08_20/reading.md`. **The verdict is unchanged in substance.**

The one thing to carry across: this run's staging copy is classified
`BLANK_EXPECTED_BLANK_DEGENERATE`, not with the three `NONBLANK_EXPECTED_GOT_BLANK`
candidate-fault copies, for the provenance reason given above.

## Provenance

Nine raw files, byte-for-byte as the tools wrote them, plus this reading, the offline analysis
and `manifest.json`. Digests for every file are in the manifest; it does not hash itself.

```
HEAD at run time   a9b5f1c41491503a8f8526c786619791c12929a7
HEAD:scripts       169ac116c8d7514c3daa6dc8354e755653bc0088
working tree       clean
board              powered down by the operator after step ④
```
