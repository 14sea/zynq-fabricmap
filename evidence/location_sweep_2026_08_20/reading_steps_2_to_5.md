# Location sweep, steps ②–⑤: **the write landed at the intended FAR**

Executed 2026-08-20 at `746d287`, source unmodified, as one authorised chain: power cycle →
fault → acquisition in that same boot → instrument pairing → archive. Nothing was retried,
resumed, restored, armed or scored. **No board action of any kind ran after step ④**; step ⑤
is host-side only — comparing the two acquisitions' records and writing this reading.

**Result: `WRITE_LANDED_AT_THE_INTENDED_FAR`, with sixteen of sixteen positive controls exact
in the same acquisition.** `0x00400A20` holds the candidate frame bit-for-bit, so **this
transaction's** `F_READBACK` stop is a **read-side disagreement** and its write is not
missing.

That claim is deliberately about **this transaction only**. The earlier known-answer stops
share this one's *recorded fault shape*; **no location was ever observed for any of them**, so
nothing here retro-diagnoses them. Whether they too landed their writes is a question this run
does not answer.

## ③ — the specified fault, reconstructed rather than taken on the driver's word

`board_claimb_postfault_capture.py/1.0.0`, one run, exit 1 (`STOP`, which is this step's
required outcome).

```
round.steps        [no_op: passed, known_answer: stopped]                    exactly two
stop_reason        AxiRefusal — pass 2 of envelope 0, fault_code 8 (readback)
STATUS (last read) 0x04040082          FAULT 0x00000008
identity gate      boardid 17A6, role verify, FCLK0 50.0 MHz (1600/8/4),
                   pss_idcode 0x13722093        <- the gate step ① never enters
same_boot          plmark 18cd7785cbf1b1fd, passed
console            353 commands, 0 rebooted, prompt returned on every one
PCAP_PR            0x4e00e07f -> 0x4600e07f (ICAP) -> restored 0x4e00e07f, read back
CTRL writes        32, of which 0 had CTRL_ARM (bit 6) or CTRL_MODE_HOLDOUT (bit 7) set
```

**"pass 1 completed all three envelopes" is a decoded fact, not a paraphrase of the stop
string.** Expanding every CTRL write: `0x04` = PASS1|env0, `0x14` = PASS1|env1, `0x24` =
PASS1|env2 each appear **twice** — both transactions completed pass 1 across all three
envelopes. `0x08` = PASS2|env0 appears twice, but `0x18` = PASS2|env1 and `0x28` = PASS2|env2
appear **once each**: only the `no_op` finished pass 2. That is exactly the specified shape.

Cross-check against the two accepted fault records of 2026-08-16
(`postfault_r4_step2_capture`, `postfault_r4_replication/fault_capture`): identical command
count (353), identical CTRL-write multiset, identical envelope-upload count, identical step
states. This fault has the **same recorded fault shape** as those two — which is a
statement about the records, not proof that the same thing happened inside the engine.

## ④ — the acquisition, in that same boot

```
verdict            WRITE_LANDED_AT_THE_INTENDED_FAR
positive controls  16 / 16 exact         sweep_needed  False
entries            17 read, all ok       not_attempted 5,127
plmark             18cd7785cbf1b1fd at start and at end
elapsed            1.8 s
```

**The early stop is legitimate and its missing files are not manufactured.** Under 2.8.0 the
tool reads `A20` first; because `A20` holds the *candidate*, it reads the sixteen controls,
adjudicates, and stops — a full 5,144-frame sweep happens only when `A20` holds the base. So
`0x00400A21`–`0x00400A23` were never read and **no file was created for them**. How far it ran
is the result.

### Verified independently, against the frozen authority

The candidate frame differs from the base frame at **exactly two words**, and the capture
reproduces both:

```
word 50   base 0x00000000   candidate 0x0000100e   observed 0x0000100e
word 51   base 0x00000000   candidate 0x00005213   observed 0x00005213
                                                   (all 101 words equal, not just these two)
```

Controls re-checked from the raw captures against `carrier.bit`'s own frames: **16/16 exact**,
independent of the tool's verdict.

### One correction, because it nearly produced a false alarm

A capture is **202 words**: `pad_frames = 1`, so the probe records `pad_frame` = words[0:101]
and `frame` = words[101:202]. **The real frame is the second block.** My first independent pass
compared words[0:101] and appeared to contradict the tool ("observed == candidate: False");
that was the *pad* frame, which is all zero here, and the tool was right. Re-run on `frame`,
every check agrees with the verdict. Phase 2's `superseded.md` is unaffected — it tested both
halves and found 0/16 either way — but the mental model "either alignment might be the frame"
is wrong and is corrected here.

## ⑤ — the instrument pairing, checked before the verdict was used

```
instrument_digest   identical, a20e56aae879812d…855aa95d   (it hashes the admitted FAR list
                    and its order, so an identical digest pins the 5,144-FAR authority)
parent              board_signature_search.py/2.8.0, both
child               probe_jtag_config_read.py/2.4.0, both
mode                signature-search, both
control FAR list    identical in both indexes
child Tcl           byte-identical for all 17 FARs the two acquisitions both read
plmark              ① 18cd75d67713f2f0 start == end; ④ 18cd7785cbf1b1fd start == end;
                    and the two differ, as two boots must
```

One instrument, two states. That is what licenses reading ④ against ①.

## What this establishes, and what it does not

* **The write reaches the frame it asks for.** Level L1's blocking question — "we do not know
  whether the write landed" — is answered for this transaction: it landed, at the intended
  FAR, exactly.
* **`F_READBACK` / `fault_code 8` is a read-side disagreement**, which is what the fault's own
  name said and what the `csib_gap_in_burst` mutation implied, now with direct evidence from
  the frame rather than from the engine's own complaint.
* **It is one observation.** A location claim needs independent reproduction — a second
  power cycle, a second fault, a second acquisition — and that is a separate authorisation.
* **It does not say why the engine's readback disagrees** while a JTAG readback of the same
  frame reproduces the candidate exactly. That is the next question, not this one's answer.
* **Claim B still has zero data points.** This unblocks §9 step 6; it is not a step-7 arm.

## Archive

**Nothing to archive, and that is a fact about the acquisition rather than a skipped step.**
The keep-list is `index.json`, `verdict.json`, this reading, the candidate FARs *that were
read*, and the sixteen controls — each as capture + child log + Tcl. Step ④ produced exactly
17 FARs × 3 = 51 files plus index and verdict, and **all 53 are in the keep set**, so there is
no raw remainder to compress, verify, upload or move. `archive_manifest_step4.json` records
that with the same fields the Phase 2 schema uses, rather than leaving the absence unexplained.

Step ①'s archive is unaffected and stays as verified: release asset
`location-sweep-step1-2026-08-20`, sha256 `5f5c5711…`, byte-identical on download.

## State

The board is powered and in the post-fault state step ③ built; step ④ was read-only JTAG. **No
board action of any kind has run since step ④** — step ⑤ read the two acquisitions' files on
the host and produced this reading, and the archive step moved nothing because there was
nothing to move. Nothing further is authorised.
