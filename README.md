# zynq-fabricmap

Device-local fabric cartography on a Zynq-7000 (XC7Z010): can a board map enough
of its own fabric to guide its own evolution — and is map-guided evolution
measurably safer or better than raw mutation?

**Status: the frozen database subset is in (2026-08-02).** The approach is ratified
(see below), `data/` is frozen and self-verifying, and no bit class is certified
yet. Nothing has been board-verified from this repo.

## Relationship to the other repos

This is the successor line to [zynq-autoehw](https://github.com/14sea/zynq-autoehw),
whose M1 closed at tag `m1-complete` with beats-random confirmed on silicon
(+113/1024, Set B), later reproduced bit-identically on a second die.

- It tests **Claim B** of `zynq-autoehw/docs/tech_report.md` — *a device-local
  map guides evolution better/safer than raw mutation*. Claim A (autonomous
  runtime) and the beats-random subclaim of Claim C are already settled there and
  are **not** re-litigated here.
- It is a **separate repo on purpose**: different claim, different board-risk
  envelope (bitstream/routing-level manipulation, not plumbing), different
  cadence (exploratory — it is expected to falsify its own ideas repeatedly).
  Keeping it out of zynq-autoehw leaves that repo's published M1 record frozen
  and citable.
- zynq-autoehw's own engineering debt (NV champion store, board-side replay
  bundle) is **not** here — it stays in that repo as an M1 engineering addendum,
  so the M1 record never points at remainders closed somewhere else.

Earlier lines, for provenance: [zynq-ehw](https://github.com/14sea/zynq-ehw)
(closed at v1.2.0), [zynq-xpart](https://github.com/14sea/zynq-xpart) (DFX / ICAP
/ prjxray), [zynq-agentctl](https://github.com/14sea/zynq-agentctl).

## What is already settled (read this before proposing anything)

`docs/kickoff_fuzz_and_map.md` is the audited prework, copied verbatim from
zynq-autoehw. Its load-bearing findings:

- **prjxray's zynq7 fabric rules are md5-identical to artix7** — 7-series shares
  one fabric. "Partial coverage" is a misleading label; the real gaps (GTP, PCIe,
  XADC MONITOR, cells_data/gridinfo) do not intersect what evolution needs.
- **Recommendation, not yet ratified:** do *not* try to complete prjxray. Extract
  and freeze the needed subset, then certify it per bit-class with our own
  Vivado specimen-diff prediction gate (the EP4CE6 mine → holdout → emit →
  fresh-gold TP=1/FP=0 method). Certificates become the authority; prjxray is
  demoted to an index.
- **Fuzz × evolve has three levels**: offline fuzz feeds a whitelist / on-board
  self-cartography / evolution *as* fuzzing (the map is a byproduct of search).
  The third is the unclaimed territory.
- **Safety split**: content-bit classes (worst case: logic garbage) are fine on
  the EBAZ boards; autonomous *routing*-class fuzzing goes to sacrificial
  hardware, never the working boards.

## ★ Ratified 2026-08-02 — the approach is now decided, not proposed

The prework's core recommendation is **approved by the user**. It is no longer a
recommendation; it is what this repo does:

- **Do not complete prjxray.** Its fuzzers are archived and pinned to Vivado
  2017.2, there is no ground truth in them, and nothing here consumes them.
- **Extract the needed subset and freeze it into `data/`.** The 2026-07-11 audit
  established that the zynq7 fabric rules are md5-identical to artix7 (7-series
  shares one fabric) and that the real gaps — GTP, PCIe, XADC MONITOR,
  cells_data/gridinfo — do not intersect what evolution needs. Licence is CC0, so
  vendoring is clean.
- **Certify per bit-class with our own Vivado specimen-diff prediction gate**,
  porting the EP4CE6 method (mine → holdout → emit → fresh-gold, TP=1 / FP=0).
  The certificates become the authority.
- **prjxray is demoted to an index**, and completion becomes lazy: targeted
  mini-fuzz only where a certificate actually fails.

This instantiates the `local_map` schema and is the foundation for Claim B.

### First drop, concretely

Pure host-side, zero board risk. Split per the inversion below:

| side | owns |
|---|---|
| Claude | the extraction + certification infrastructure: subset extractor into `data/`, Vivado specimen-diff harness, the prediction gate itself, and its TP/FP accounting |
| author | `local_map` schema instantiation, host verifiers over the emitted certificates, and known-answer fixtures the gate must reproduce |

### Landed so far

**Step 1 — extraction + freeze format (done).**

```bash
scripts/extract_prjxray_subset.py --src /path/to/prjxray-db   # (re-)freeze
scripts/extract_prjxray_subset.py --verify                    # integrity gate, no deps
```

- `data/subset_spec.json` declares the subset and the bit-class taxonomy; it is the
  only place the subset is defined.
- `data/prjxray/` holds 46 verbatim upstream files (16.6 MB) from prjxray-db
  `0a0adde`, CC0; `data/MANIFEST.json` pins every hash, count and provenance field.
- **10,896 features, 100% classified** into six classes — `clb_lut_init` (2048),
  `clb_mux` (500), `clb_ff_config` (176), `clb_lutram` (42), `int_pip` (7272),
  `ppip_bitless` (858). An unclassifiable feature aborts the extraction on purpose.
- The 2026-07-11 "7-series shares one fabric" audit is now **machine-checked at every
  extraction**: 28/34 rule files byte-identical to artix7, 2 rule-equivalent
  (provenance labels only) — and 4 CLB mask files carry a real 4-bit delta, recorded
  rather than smoothed over (`data/README.md`).
- Format contract for the other author: `docs/freeze_format.md`, including the
  `certification` slot the prediction gate writes back into and its staleness rule.

**Step 2 — the Vivado specimen-diff harness and the prediction gate itself — is next.**

## Planning decisions carried in (2026-08-02)

**The first drop inverts the usual division of labour.** In the sibling repos the
default is: the other author writes code, Claude gates and boards it. That
assumes host-side logic. Extraction + per-bit-class certification is a Vivado
specimen-diff activity end to end, so here **Claude builds the infrastructure and
the author writes schemas, host verifiers and known-answer fixtures against it.**
Rationale is concrete: in the M1 engineering addendum, five of six blockers
across six rounds were invisible on the authoring side (no RISC-V toolchain, no
Vivado). Keeping the default split for a Vivado-centric drop would make that
ratio worse. See `zynq-autoehw/docs/workflow.md`.

**No sacrificial hardware is being bought yet.** The prework's safety split says
content-bit classes are safe on the EBAZ boards; only *routing*-class autonomous
fuzzing needs sacrificial silicon. The XC7K70T's original rationale is also
materially weaker than when it was proposed — the 2026-07-11 prjxray audit killed
the coverage argument, four spare same-part Zynqs killed the sacrificial-economics
argument, and its J7 UART header is unpopulated while this whole control plane is
UART-mailbox based, a cost the old plan never carried. **Revisit only when this
line actually hits the routing wall.**

## Hardware

Board plumbing is copied in from zynq-autoehw and is deliberately board-agnostic
(it drives both an EBAZ4205 and an EBAZ4203):

- `scripts/board_serial.py` — prompt regex matching `zynq-uboot>` (4205 vendor
  U-Boot) and `Zynq>` (4203 mainline U-Boot); `/dev/ebaz-uart` follows either
  board's CH340.
- `scripts/board_set_fclk50.py` — pins FCLK0 to the 50 MHz signoff clock by
  *decoding the PLLs*, because the divisor constant is board-specific: the 4205's
  magic `0x00200a00` written onto a 4203 (IO PLL 1600 MHz, not 1000) yields
  80 MHz, silently out of signoff.
- `scripts/board_uboot_fpga_load.py` — `loady` + ymodem + `fpga loadb`.
- `scripts/board_carousel_extract.py` — rebuilds a mailbox carousel
  **positionally** from a monitor trace, never from a first-seen set.

Copies, not shared code: the source repos are never modified from here.
