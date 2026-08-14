# Reading the known-answer round and its DRAM capture

Three files, in the order they were produced:

| file | what it is |
|---|---|
| `record.json` | the authorised board round, stopped at step 2 |
| `ddr_slot0.json` | the read-only capture of the failing frame, taken before any power cycle |
| `ddr_slot0_analysis.json` | what that capture can and cannot say, recomputed offline |

## What the round established

Step 1, the all-zero no-op, passed: 15/15 frames, readback digest `67fc9c21…`,
`rb_latency_valid` on all three envelopes. Step 2, the 26-bit candidate, faulted on the
first readback frame — `STATUS 0x04040082`, `FAULT 0x8`, `rb_frames_ok=0`,
`recovery_required=1`, bit-identical to the erratum-004 and erratum-005 fault word.

`pass1_complete=1` and `env_committed=7` in the intermediate status words say the three
envelopes finished their **pass 1**, which validates the host's words and commits one CRC
per frame. Pass 1 does not write the fabric; the staging buffer is written in `P_PASS2`
only (`carrier_stream.v:411`).

F_READBACK is the carrier's own local interlock (`carrier_stream.v:855-868`): it CRCs the
frame out of the staging RAM and compares it against the CRC pass 1 committed for that
frame. So the fault establishes that **the readback staging bytes are not the input bytes
pass 1 committed and pass 2 re-verified** — and nothing about where those bytes physically
landed, because the committed CRC is an authority over the input, not over a location.

What the round did buy is the discrimination it was built for: an all-zero candidate cannot
distinguish a correct address from a wrong one, and 26 non-zero bits made the disagreement
appear on the first frame.

## What the capture established

`pass2_line()` archives every readback frame to `CAPTURE_ADDR = 0x10100000` under the
watchdog, so the fault did not lose the data. The capture read slot 0 and nothing else.

The frame is **101 words, every one of them zero** (`0441772f…`), byte-identical to the base
frame at the requested FAR `0x00400A20`. The expected candidate frame differs from that base
in only 2 of its 101 words — the packed content bits and the recomputed ECC — and neither
appeared.

`ddr_slot0_analysis.json` measures how much that can mean: the window matches **474,494 word
offsets** of the 519,544-word device stream (4,716 of 5,144 frames are all-zero). It names
no address. Bit-swap and word-alignment variants separate nothing either — an all-zero
window is invariant under both.

* **Ruled out**: the readback did not return mangled non-zero data, and it did not land on
  one of the 428 non-zero frames.
* **Still open, and this capture cannot separate them**: the pass-2 ICAP write never landed,
  or the read reached a different frame that is also still zero.

Slots 1–4 were not read, and would not have helped: after the first frame's CRC comparison
faulted the FSM is in `P_FAULT`, `stage_rb_we` no longer asserts, and the rest of the same
U-Boot line copies the unchanged staging RAM into the remaining slots. They are mechanical
copies of slot 0, not four independent observations.

## Provenance caveat on `ddr_slot0.json`

The capture was taken with `probe_ddr_capture.py/1.0.0`, which sent three commands —
`echo`, `printenv plmark`, `md.l` — judged all three for a boot banner, and preserved the
replies of the last two. The sync reply is therefore not in the record. The tool is now
1.1.0: it preserves all three replies and additionally requires a prompt in each. **This
file is not re-captured**, because re-capturing means touching a board whose post-fault
state is the only remaining evidence for the next discriminator.

## What would actually separate the two open cases

Not a read of some other base-non-zero frame: that is a read-path positive control and
cannot show that `0x00400A20` in particular is addressed correctly. The separating
measurements are an independent readback that does not go through the carrier —
PCAP or JTAG — of the **current post-fault** `0x00400A20`:

* reads back the candidate → the write landed and the read side is misaddressed;
* reads back the base → the write did not land at `0x00400A20`, and only a search for the
  signature elsewhere can then separate "never written" from "written somewhere else".

That is why the board is being left powered and untouched.
