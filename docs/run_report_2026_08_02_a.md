# Run report — `run_2026_08_02_a`, first certified bit class

**Result: `clb_lut_init` is certified. Holdout 262/262, fp=0, fn=0.**
First certificate accepted by `host/verify_certificate.py --require-production`.

```
CERTIFICATE VERIFY: OK — status=passed tp=262 fp=0 fn=0
```

## What the claim is, precisely

The frozen prjxray `clb_lut_init` rules predict, **bit-exactly and in advance**, which
configuration bits Vivado 2025.2 moves when a LUT's INIT changes — across two tile
types, both SLICEL and SLICEM, two BELs and twelve specimens.

**What it is not.** It is not evidence that those bits *mean* what their names say on
silicon. Nothing here has been loaded onto a board. That is a separate experiment with
a different risk profile, and the certificate's `scope` field says so in the manifest
slot. The distinction matters because the whole point of demoting prjxray to an index
was to replace "the database says so" with "we measured it" — and what we measured is
addressing, not semantics.

## Method — the ordering is the evidence

| step | artifact | tool |
|---|---|---|
| 1. pre-register | `predictions.json`, sha256 `590b28be…`, **committed in `5250cd0` before any bitstream existed** | `gate_emit.py` (never touches Vivado) |
| 2. build | 12 specimens + attestations | `gate_build.py` (reads the plan, never composes one) |
| 3. measure | `measurement.json` | `gate_measure.py` (refuses to score unless the hash still matches) |
| 4. certify | `certificate.json` | `gate_certify.py` (copies preregistered fields verbatim) |
| 5. verify | `CERTIFICATE VERIFY: OK` | `host/verify_certificate.py --require-production` (author-owned) |
| 6. record | manifest slot `clb_lut_init: certified` | `manifest_certify.py` (enforces the staleness rule) |

A gate whose predictions are written after the diffs are known proves only that we can
describe what we saw. Every step above exists to make that impossible rather than
merely unlikely.

## Coverage

| | |
|---|---|
| specimens | 12 (24 bitstreams incl. bases) |
| sites | `SLICE_X2Y25` (CLBLL_L, **mine only**), `SLICE_X8Y25` (SLICEM), `SLICE_X9Y25` (SLICEL_X1 of CLBLM_L) |
| BELs | `A6LUT`, `D6LUT` |
| patterns | two seeded random 64-bit INITs per (site, BEL), seed `0xB17D` |
| predictions | 388 pairs — 126 mine, **262 holdout** |
| result | mine 126/126, holdout 262/262, fp=0, fn=0, 0 unattributed bits, 0 ECC-only frames |
| class coverage | 262 of 2048 `clb_lut_init` entries attested |

`SLICE_X2Y25` is mine-only on purpose: the harness rules — the address arithmetic, the
frame-ECC exclusion, the `LOCK_PINS` requirement — were all established on its
evidence, so it can inform predictions and can never score them.

## Four things that had to be found, not assumed

1. **LUT input pin swapping.** Vivado permutes `I0..I5` onto `A1..A6` and rewrites
   INIT to compensate, so the logical INIT bit index is not the physical truth-table
   index. Measured: logical bit 1 landed on the database's `INIT[04]`. Bits 0 and 63
   agree either way, being invariant under any input permutation — so a gate that
   certified only the endpoints would have passed with every interior bit silently
   wrong. `LOCK_PINS` is now mandatory and the resolved mapping is attested, not
   assumed.
2. **Frame ECC.** Word 50 bits 0..12 are recomputed whenever anything in the frame
   changes, so a one-bit edit appears as ~10 changed bits. They are excluded by an
   explicit, listed rule, and an ECC change in a frame with no other change is a
   finding rather than an exclusion.
3. **Frame geometry.** 101 words/frame was an assumption; it is now discharged — 5,144
   frames from `part.yaml` plus 8 pad frames at 101 words each consume a real
   bitstream's FDRI payload exactly.
4. **Segbit token text.** The frozen data writes `%02d_%02d` (`32_09`, not `32_9`) in
   all 14,142 tokens. `freeze_format.md` §5 originally said only `[!]<F>_<B>`, and the
   two implementations read it two ways — the producer copied the db text, the
   consumer reconstructed it unpadded. The first real certificate failed on 117
   findings, every one with `bit_offset < 10`. The spec was at fault; it now pins the
   format and says to compare against the db text rather than a reconstruction.

Item 4 is the argument for the two-implementation split in one paragraph: the bug was
invisible to every self-consistency check, because producer-side predictions,
measurements and certificate all carried the same string. Only a second implementation
written from the spec alone could hit it.

## Artifact chain

```
data/subset_spec.json           sha256 ffe4fb9f…   (pinned by the certificate)
data/MANIFEST.json              freeze 2026-08-02T…, clb_lut_init -> certified
gate_runs/run_2026_08_02_a/
  predictions.json              sha256 590b28be…   committed 5250cd0, pre-build
  measurement.json              holdout 262/262, decision PASS
  certificate.json              1.2.0, profile production, accepted
build/gate/<site>_<bel>/
  attestation.json              resolved LOC/BEL/LOCK_PINS + pin mapping, per build
```

`build/` is gitignored; the attestations are reproducible from the committed plan, and
representative samples live in `tests/samples/`.

## What is next

- **Certify the remaining content classes** against the same machinery:
  `clb_ff_config` (176), `clb_lutram` (42), `clb_mux` (500). `clb_mux` is the first
  class where the one-selected-input-per-mux-group composition rule actually bites.
- **`int_pip` (7272)** can be certified host-side at any time; that is inventory, not
  permission. Nothing routing-class goes near a working board — see
  `docs/board_roles.md`.
- **Semantics, not addressing** is the real next claim, and it is the first step that
  needs silicon.
