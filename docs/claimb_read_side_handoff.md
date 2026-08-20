# Read-side divergence — W3, W4 and the handoff

Host-side only. Companion to `claimb_read_side_divergence_design.md`; W1 and W2 of that
document's §9 are in `evidence/read_side_facts_2026_08_20/`. Nothing here authorises board
contact, and nothing here changes RTL.

---

## W3 — which clause of the device-model contract each surviving hypothesis puts in doubt

`claimb_icape2_readback_sequence.md` §7 states the device model as a seven-clause contract, and
`vivado/carrier/icape2_model.v` implements it. The benches pass at read latencies 0/1/3/5/7/12
against devices demanding 32/40/48/64 flush clocks, and `scripts/mutate_carrier_readback.sh`
carries twelve mutants of the read sequence, each with the outcome it must produce.

**What that green does and does not mean.** It shows the RTL implements the model. It cannot
show that a model clause is true of silicon — the clause is where the assumption lives, not
where a bug would be. Every surviving hypothesis is therefore a place where the contract and
this die may disagree, and **none of them is a defect the benches could have caught**. That is
the same shape as errata 002, 003, 004, 005 and 006, a seventh time, and saying so is cheaper
than paying for it again.

| hypothesis | clause it puts in doubt | the clause, as the model implements it | what silicon would have to be doing instead |
|---|---|---|---|
| **H-STALE** | **5** (serve frames out of configuration memory) with **4** (the one-frame write buffer) | `icape2_model.v` serves an FDRO read from the memory *as it stands after the burst*, with exactly the last frame of a burst left uncommitted in the frame buffer | the read port observing memory as of before the burst — a deeper or later commit than clause 4 models, so that the four target frames are not yet visible when the readback runs |
| **H-PAD** | **5** (the pad's identity and length) | the model's header says it outright: *"the first frame a readback returns is the frame buffer's content, not the addressed frame"*, one frame long | a pad of a different length, a pad in a different position, or no pad — any of which makes the engine's `rb_skip = rb_lat + 101` discard the wrong words |
| **H-ADDR** | **3** (memory keyed by FAR, successors computed from the address format) and the erratum-006 execute-on-FAR-load rule | `pend_rcfg`/`pend_wcfg` hold what CMD was given and a write to `REG_FAR` executes it; successors come from `[22]` top/bottom, `[21:17]` row, `[16:7]` column, `[6:0]` minor, never a table | the FAR write not taking, or taking somewhere else, in a way the model cannot express because it always serves from the FAR it was given |
| **H-IDLE** | **6** (refuse what the hardware refuses) | the model refuses a missing sync, a missing RCFG (`E_NO_RCFG`), an `RDWRB` move with `CSIB` Low (`E_ABORT`), a gap in an active FDRO read (`E_FDRO_GAP`) — and otherwise **always serves** | accepting the transaction and serving nothing, with no modelled error. The model has no state for "accepted, and quiet", so nothing in simulation can produce it |

The asymmetry worth carrying forward: H-STALE, H-PAD and H-ADDR each name a clause the model
*states* and could be re-stated differently. H-IDLE names a state the model does not have at
all — and §3 property 2 of the design says the engine cannot see it either.

## W4 — what the engine cannot know, stated as an instrumentation gap

Three facts about the read path as built, all in `vivado/carrier/carrier_stream.v`:

1. **The capture window is timed, not qualified.** `icap_rd_valid <= !icap_csib && icap_rdwrb`
   (`:479`) is a one-clock-delayed copy of the engine's *own* bus control. There is no signal
   from the device saying a word was served. "The device answered" and "I clocked an idle
   interface" are the same event to this engine.
2. **The discarded words are never recorded.** `RB_SKIP` (`:810`) drops `rb_lat + 101` words
   with no observation of any of them. The pad frame — the single artifact that would settle
   H-PAD — passes through and is lost.
3. **The probe records a count, not a value.** `RB_PROBE` (`:739`) counts words until one
   matches `DEVICE_ID_LOW`, and only the count survives, in STATUS bits 25:18. **The value of
   the words before the IDCODE is the one measurement that would separate "idle drives zeros"
   from "idle drives the abort pattern"** — H-IDLE from the rest — and it is thrown away.

Two shapes could close it, and both are recorded as candidates rather than proposals:

* preserve the pad frame in a second staging slot, so the discarded frame becomes readable;
* latch the first N words after each turnaround, so the interface's idle value is observable.

**Their cost and safety have not been designed.** The staging RAM, the floorplan (RULED FINAL
2026-08-11, 305/400 slices), the AXI register map, the host decoder and the tests that pin the
reserved STATUS bits are all in the blast radius. Nothing here says either is cheap. Neither is
implemented in this pass.

## W5 — the handoff

**The location question is closed as far as one instrument can close it.** Two observations,
`WRITE_LANDED_AT_THE_INTENDED_FAR`, 16/16 positive controls in both, `A20` equal to the
candidate word for word, the same frame sha256 across runs. It remains a replication, not an
independent method: same host, cable, tool bytes, carrier and board.

**The read-side question has four live hypotheses** — H-STALE, H-PAD, H-ADDR, H-IDLE. Two died
on committed evidence, not on the board: H-REF, because a correct read of the candidate could
not have produced an all-zero staging window; and H-LAT as stated, because every displacement
of at most 50 words is excluded post-write. H-ADDR survives only in a local form inside the
searched bands; an arbitrary distant misaddress is unconstrained.

**W2 makes F2 general.** In six engine transactions on the erratum-006 carrier, ninety frames
came back, every one blank, every one expected to be blank. This frame-data path has never been
demonstrated to deliver non-blank configuration data correctly.

**One fork is probeable with the existing carrier and the rest are not.** A single no-op
transaction into the already-faulted carrier, same boot and no reload, identifies strict
H-STALE positively — its staged frame would be the candidate, which would also be the first
non-blank frame this path has ever returned. Its negative branch is **conditional**: the run
deliberately performs no R4/JTAG read between the fault and the second transaction, so it never
observes that *that* instance held the candidate beforehand. Separating H-PAD from H-ADDR from
H-IDLE needs internal read-path instrumentation or a carrier with distinctive non-blank targets;
PCAP/devcfg answers independent-method and systematic-error risk and does **not** separate that
internal fork. It requires one new non-scoring, no-reload entrypoint, which does not exist, must
reuse `board_claimb_known_answer._write("restore", …)`, and is not authorised.

**Claim B still has zero data points.** The preregistration is still DRAFT, §6's budget is
unfrozen and §10's freeze has never been performed. Nothing in this line of work is a Claim B
measurement, and none of it can be until §9 step 6 runs through.
