# B3 image stage 5 — engineering acceptance (2026-10-12)

**Decision (the owner, 2026-10-12): image stage 5 is closed on its engineering exit — PASS.** The
review of `5b6cbc2` (b3-image-stack 1.8.0, the DMA unit) is PASS; the owner independently ran the 15
relevant tests and the 14 DMA mutants, all as expected. **The formal result is unchanged:**
`stack.status = FINDINGS`, `readiness.image_ready = false` (`evidence/b3/build_evidence.json`). The
tool defines `image_ready` as "the complete analysis passes"; this acceptance does not redefine it.

This is engineering progress accepted on limited evidence. It does not claim the image is safer, and
it does not change B3's research criteria. **It authorises no board session, no pin table, no S0 and
no board_ready**; S1 and each session's transport disposition remain separate decisions. Stage 6
(hostapp) needs its own scope and authorisation.

## 0. The exit criterion (the owner, 2026-10-12)

The earlier requirement — that the stack unit first prove memory safety for the whole image (all
1 169 unplaced write sites placed, findings at zero) — was the owner's own review expansion and is
withdrawn. Stage 5 is accepted on:

1. a reproducible final image whose sources, IMPORT, toolchain and build evidence agree, with the
   existing functional and byte-level comparisons passing;
2. a stack assessment of that same ELF that separates what is established, what is conditional,
   what is a diagnostic estimate, and every remaining finding — DMA, frame cells, start-up and
   exceptions included;
3. every remaining item classified as an **accepted premise**, a **model limitation** or an
   **actual defect** (a reproduced functional defect must still be fixed, not renamed a premise).

**The image:** `b3/firmware/bsp/out/b3_app.bin` sha256 `28c80eca…8299`, `b3_app.elf` sha256
`0d0f99a6…d7a1` (firmware unchanged since `3b4ea86`, the B-2 unit). **The assessment:**
b3-image-stack 1.8.0 at `5b6cbc2` (analyzer sha256 `311b33b7…`).

## 1. Criterion 1 — reproducible, consistent, functional and byte-level checks

| check | result |
|---|---|
| two clean builds, binary **and** ELF byte-identical | `reproduced_byte_identical: true` |
| the tracked `b3_app.bin` / `b3_app.elf` after the rebuild | unchanged |
| sources, IMPORT, BSP inputs, toolchain digests | recorded in the build evidence and checked by its verifier |
| the b3 suite, incl. the byte-level comparisons (`test_b3_carto_twin`, `test_b3_record_twin`, `test_b3_orch_twin`, `test_b3_wire_contract`, `test_b3_app_audit`) | Ran 771, OK, no skip (4 145 s, final tree) |
| B2, every `tests/test_b2*` | Ran 445, OK |
| B2 manifest verify | `S3 True None aec84514` (unchanged) |
| the stack assessment under hash seeds 0 / 4242 / 777 | 224 findings each, equal to the evidence in content and order; entries / rules / newlib / modes / masks equal |
| DMA-unit mutants (a hermetic copy) | 14 / 14 killed (each `Ran 10` and FAILED) |

## 2. Criterion 2 — the stack assessment of this ELF

### 2A-1. Facts checked directly in the ELF (pinned objdump / readelf / the ELF's words)

- The four read-only I/O tables are in `.rodata`: REC_IO `0x2015350`/28 B, TX_IO `0x201536c`/28 B,
  PULL_IO `0x2015388`/40 B, APP_RX `0x20153b0`/16 B; their words are the callbacks the source names
  (E1); no data word holds an address inside them, and they are materialised only in application
  units (E2).
- The four DMA descriptors are real `.rodata` objects directly after the tables
  (`0x20153d0..0x2015410`); `devcfg_dma` (`0x2001a64`) reads `dst` / lengths from them at run time and
  stores them to the DevC DMA registers in UG585's order, `DMA_DEST_LEN` last (`0x2001ad0`);
  `devcfg_dma` is entered by exactly four `bl` (`0x2002800`, `0x200332c`, `0x2003340`, `0x2003394`)
  and its address appears nowhere else; its error / timeout path returns −1 without stopping the DMA.
- `XExc_VectorTable` (`0x20196f8`, `.data`) initially points every slot at a handler that is a single
  `b .`; the vector entries write only their mode's stack (and, for the aborts and undefined, one
  fixed global) before dispatching.
- `boot.S` clears the CPSR A bit; the image has no `cpsie`, no `sev`, and no constant for the CPU1
  start word; `CheckEFUSE`'s CPU1 reset is conditional on an eFUSE bit.

### 2A-2. Results of the analyzer's model, the ABI and the source contracts

Not unconditional proofs: they rest on b3-image-stack's value model (synchronous paths only), on
**B2** (the AAPCS: callee-saved registers are preserved across a call) and on **B3** (each named
contract is its source's semantics, bound to the source and code digests), as the assessment states.

- The SP is tracked along every path; each mode's stack capacity: SYS 16 384, SVC 4 096, IRQ / FIQ /
  ABT / UND 2 048 each. The image's CPSR writes clear only the A mask.
- newlib's `__sbprintf` recursion is bounded by the verified source rule (`_vfiprintf_r` ≤ 2,
  `__sbprintf` ≤ 1; libc and version-header digests bound).
- The write inventory: 3 001 stores, 1 565 hand-overs, 1 DMA command; 2 214 placed, 519 placed at the
  callers, 49 by contract; **1 170 sites not placed** (1 169 plus the DMA command).
- Placed writes overlapping a read-only table: **0**. Placed writes overlapping a protected object:
  only newlib's initialisation of `__sf`, `__stdio_exit_handler` and `__atexit` (3 findings, 33 sites).
- DMA, over the placed writes: one command site (`devcfg_dma` `0x2001ad0`), four constant descriptors;
  no placed write into another DMA-capable PS master (DMAC, GEM, USB, SDIO).

### 2B. Conditional results (every premise listed; none proved)

- **APP_RX and PULL_IO — the CPU-analysis part holds under the listed premises** (T2): no CPU write
  of the image changes their bytes, given P_OBJ, P_EXC, B2 and B3, with routes R1–R4 closed by image
  evidence and R5 by P_EXC. **This is not a derivation of the tables' invariance for the whole
  image:** F-SUB and F-PL are not excluded, and the DMA part rests on P_DESC / P_DEC.
- **The image's own DMA** writes memory only at **`0x10300000..0x10300328` (808 B)**, overlapping no
  protected object, descriptor or stack — on P_DESC and P_DEC; the word unit of the lengths and "a
  PCAP destination writes no memory" are INFERRED. In the formal inventory the command is a write
  that is **not placed**; its window has **no shown end** (F-WIN).
- **TX_IO and REC_IO do not hold** under T2 (`p3_tx_run`'s incoming stack is not pinned and the
  frames that hold them leak — a frame-cell blocker, not lifted).

### 2C. Diagnostic estimates — not bounds, not a worst-case upper bound

- **main: a graph-walk maximum of 5 112 B** on this ELF (M0e, PYTHONHASHSEED 46571484, no taint, no
  recursion; budget 0x2000). The run loaded the 1.8.0 working tree before two finding-text edits in
  `_assess_once`, which the M0 walk does not call. It means something **only together with all of**:
  1. **C-1** — the six `io->` indirect calls in `p3_tx_run` (`0x200b960`, `0x200b9a4`, `0x200b9f0`,
     `0x200ba68`, `0x200babc`, `0x200bb14`) reach only the union of the **16** application callbacks;
  2. **P-RO** for APP_RX and PULL_IO — **a direct assumption** that the two tables are not written.
     §2B's CPU-analysis result supports it in part; it does not derive it. (Excluding TX_IO from
     P-RO leaves the number unchanged.)
  3. none of the assessment's 224 findings — unplaced writes that may reach a saved LR or a frame
     cell, the 38 unresolved cells, writes off the synchronous paths, the DMA after return — is
     reflected in M0;
  4. exception entry, nesting and the start-up window are outside it.
  The 5 112 B measured on 2026-10-08 was on the ELF before B-2; re-measured here, the number is the
  same and the union fall-backs drop from 35 sites to 6.
- **The six exception entries: 24 B each** (`push {r0-r3, ip, lr}`), computed and unpublished (they
  dispatch through memory). P_EXC is scoped to the table conclusion and is **not** used to publish them.

### 2D. Every remaining finding

The evidence has **224**:

| class | count | content |
|---|---|---|
| unplaced writes | 150 | one line per routine for 149 routines (1 169 sites: newlib 693, application 461, BSP 15) and `devcfg_dma`'s DMA command |
| unresolved frame cells | 38 | `b3_carto_observe`, `run_candidate`, `main`, … |
| main's walk refused | 20 | PULL_IO 8, TX_IO 6, REC_IO 6 ("the read-only table may be written") |
| no bound published | 7 | the six exception entries and `b2_search_state_hex`'s chain |
| a printf format not proved | 1 | `b2_search_record_json` `0x200692c` |
| placed writes overlapping a protected object | 3 | newlib initialising `__sf`, `__stdio_exit_handler`, `__atexit` |
| DMA | 5 | F-DEC with F-WIN (one line), F-SUB (one), F-PL (three) |

Outside the evidence, and not omitted: TX_IO / REC_IO do not hold under T2; the start-up window,
exception entry / nesting and the handlers' writes are outside the analysis (synchronous paths only).

## 3. Criterion 3 — classification

| item | class | note |
|---|---|---|
| P_OBJ — every unplaced write stays in the object its pointer points to (1 169 sites; the list is kept, none is called proved) | accepted premise | the owner's ruling of 2026-10-12; for the four tables' CPU-analysis conclusion only |
| P_EXC — at an exception's dispatch the handler fields still point at this ELF's checked non-returning handlers | accepted premise | the owner's ruling of 2026-10-12; table conclusion only; lifts no frame-cell, start-up or exception-stack blocker |
| P_DESC, P_DEC | accepted **as diagnostic premises** | not confirmed to hold on the hardware |
| X1 — no bus master writes the image's memory other than the image's own DevC DMA, **including the whole period after the image reconfigures the PL**, not only activity the loader left; X2 (CPU1 held in WFE); X3 (the loaded bytes are `b3_app.bin`); X4 (memory integrity) | accepted **as diagnostic premises** | not confirmed to hold on the hardware |
| C-1 (the six `io->` sites' target set) | accepted **as a diagnostic premise** | for the 5 112 B estimate only |
| B2, B3 | the analyzer's stated premises | unchanged |
| 1 169 unplaced write sites | model limitation | the analysis cannot place them; not evidence of a faulty write |
| 38 frame cells; 20 refused walk sites; 7 unpublished bounds; 1 printf format | model limitation | |
| 3 overlaps with newlib's own objects | model limitation | legitimate initialisation; listed by the inventory, handled by the rules |
| TX_IO, REC_IO not holding | model limitation | frame-cell class; not lifted |
| F-SUB | model limitation | follows from the unplaced writes |
| F-DEC | model limitation and an external-evidence gap | needs UG585's address-map text, or a read-only board read of the DDRC mapping |
| **F-WIN** | **known behaviour limitation** | the error / timeout path does not stop the DMA. No firmware hardening unit is opened. **Stage 6 is to fault-inject timeout, error and late DMA completion and check the program's behaviour — a simulation, never evidence that the hardware stopped.** |
| F-PL | open; bounded by X1 as worded above | whether the reconfigured PL can master PS memory is the carrier's design, not decided by the image |
| start-up window, exception entry / nesting, handlers' writes | model limitation (out of scope) | synchronous paths only |
| **actual defects** | **none** | no item here is a reproduced functional defect |

## 4. Names kept honest

- 5 112 B is stated only with §2C's complete premises; it is not a worst-case upper bound.
- `FINDINGS` / `image_ready = false` stay; this document records the stage-5 engineering PASS beside
  them.

## 5. Sources

- Commit `5b6cbc2` and `evidence/b3/build_evidence.json`.
- UG585 quotations used by the DMA rule are in github.com/14sea/zynq-psmap at `191ab05`:
  `docs/s0_ug585_discharge.md` lines 114–115 (N3, N4) and `docs/s0_derived_sequence.md` lines 37–38
  (the PCAP endpoint). Hardware semantics without a quotation are INFERRED.
- The scratch measurements behind §2B–2C (T2, M0e, the DMA mutants) are summarised here; the raw
  files were kept outside the repository.
