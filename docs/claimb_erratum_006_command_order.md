# Erratum 006 — a CMD command executes when FAR is loaded

**Status**: RTL and model changed, benches and mutation green, offline only.
No board contact since the 2026-08-13 read-only stage dump.

## What was wrong

`carrier_stream.v`'s readback setup emitted its seven words in this order:

```
FAR header, frame_far, CMD header, RCFG, NOOP, FDRO header, Type-2 length
```

UG470 orders readback

```
RCFG -> NOOP -> FAR -> FDRO
```

and configuration

```
CMD = WCFG -> FAR -> FDRI
```

for the same underlying reason: **loading FAR is what executes the command CMD is
holding**. The old order therefore loaded the read address at a moment when no read had
been established, and then wrote an RCFG that nothing ever ran.

The carrier's *write* path already used the documented order — the pinned-stream self
check has `CMD1, WCFG, …, FAR1, …, FDRI0` at indices 16, 17, 19, 21. Only the readback
path had it backwards.

## Why no bench caught it

`icape2_model.v` set `rcfg` on receiving the `CMD_RCFG` payload and tested `E_NO_RCFG`
only when FDRO arrived — never at FAR load. Order was therefore **unobservable to the
model**, so a stream that wrote FAR and only then RCFG established a read anyway. Every
bench passed against RTL that did not follow the documented sequence.

`tb_icape2_model.v`'s own `seq_readback` helper had the same order baked in, because it
was written to match the RTL. A bench and a model that agree with the implementation
rather than with the specification cannot find this class of defect.

## What the board showed

`evidence/calibration_noop_2026_08_13_erratum005/` — the authorised read-only dump of the
staging window after the erratum-005 calibration faulted with `F_READBACK`.

* the `0xFFFFFFDA` constant pattern is gone; the window held **bit-exact configuration
  data** for the first time
* exactly **one** exact 101-word window exists in the 520,352-word device stream, at
  offset 268658 = `0x00400A81` word 99 … `0x00400A82` word 98
* that is **+604 words** from the requested `0x00400A20`

Pass 2 writes `A20, A21, A22, A23, A80`, which leaves FAR sitting at `A81`. The window is
`A81`/`A82`. **Consistent with**, not proof of, a readback that used the leftover
auto-incremented address instead of the one it asked for.

## The change

**Model** (`icape2_model.v`) — `pend_wcfg` / `pend_rcfg` hold the command CMD was given;
a write to `REG_FAR` executes it and clears the pending state. CMD holds one command, so a
second write before the FAR load replaces the first. `DESYNC` and `RCRC` stay immediate:
DESYNC ends the transaction and no FAR follows it, and RCRC is accepted-but-unmodelled.

**RTL** (`carrier_stream.v`, `RB_SETUP`) — the same seven words, reordered to
`CMD1, RCFG, NOOP, FAR1, frame_far, FDRO0, RDLEN`. Same length, same timing, same
everything else.

**`RB_WORDS` stays 202.** An earlier reading called `RB_WORDS = 2 * FRAME_WORDS` a length
defect against `rb_skip = rb_lat + SKIP_FRAME`. That was wrong and is retracted: UG470
defines the FDRO Type-2 count as `101 * (frames + 1 pad) = 202`, and pipeline latency
clocks are not part of a word count.

## Evidence that the fix is held in place

**The failure, before the RTL changed.** With the corrected model and the *unchanged*
RTL, `tb_carrier_readback` fails 1527 checks and the device reports error 2, `E_NO_RCFG`:
`evidence/erratum006_model_first_2026_08_13/rtl_unchanged_readback.txt`.

**`tb_icape2_model.v` section 12** pins the rule three ways: the defective order serves no
data and reports `E_NO_RCFG`; the documented order serves data with no error; the write
path is undisturbed and its frames still land.

**Mutation** — `far_before_rcfg` reorders the seven words back to the defective order and
changes nothing else. It is killed, device error 2. Before this erratum that mutant was
undetectable, which is exactly why the defect shipped.

```
12 as expected, 0 unexpected
```

**Benches** — all 14 runs OK, including the eight-configuration readback sweep.

## What this does NOT establish

That the board will now read the frame it asks for. The dump is consistent with the
command-order defect and the defect is real and now fixed, but the board has not been
touched since, and one misaligned window at one offset does not by itself exclude a
further latency or addressing error underneath this one. That is a question for the next
calibration, after a new carrier is built, gated and published.
