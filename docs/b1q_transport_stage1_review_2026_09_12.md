# Transport rig stage 1 review — 2026-09-12

Reviewed commit: `4528ef8`, initially clean, one commit ahead of origin/main.

**HOLD. Do not push this batch as an accepted, completed stage 1.** Five P2
findings affect measurement, the execution contract, evidence retention, or the
proposed B2Q decision. The generator and several parser controls are useful, but
they do not yet establish the claimed capture tool. No board access, production
freeze, ruling, push, or change to a pinned input was performed in this review.

## Independent checks

- The submitted 30 tests pass, with zero skips, including the PTY tests and the
  archived-session profile/count checks.
- The new public-API probes start from the exact generated stream: 302 frames,
  98,627 bytes, clean, zero losses. They then change one condition at a time.
- Production B2 verification returns S0, qualified false, refusal null. Its
  71 B2 / 105 B1 pins remain valid. The commit changes only the eight reported
  investigation files, not the frozen decision surface.
- Instrument and image verification are exercised through production B2 verify;
  no image was rebuilt and no full repository suite was rerun.

Evidence: [script and observations](../evidence/b1q/review_transport_stage1_2026_09_12/README.md).

## P2-1 — The numerator double-counts damage and the denominator is wrong

`host/transport_rig.py:302–325, 397–413`.

An invalid line is put in `crc_failed` and its expected index is also absent from
`delivered`, hence in `missing`. Adding both counts counts the same damaged frame
twice. One corrupted frame produces **2 losses**; two produce **4 losses** and
stop the condition under the nominal three-loss rule. One inserted newline in a
REC produces **3 losses**. A whole-frame deletion, in contrast, counts only once.
Thus even equal numbers of affected frames receive different weights depending
on how their damage parses. The submitted one-byte PTY example already records
this: one affected REC, `losses: 2`.

The aggregate rate then divides by `sent`, although plan section 5 specifies
received bytes. For complete silence, the observed result has zero received
bytes but denominator 98,627 and a finite rate of 306.204 per 100k bytes.

Define the elementary loss unit explicitly, account for each affected expected
frame once, and keep CRC diagnostics, unexpected bytes/frames, missing frames,
duplicates and reordering distinguishable. Do not silently revise the registered
threshold. Aggregate the actual received-byte denominator and represent a zero
denominator as unavailable, while still reporting the loss and stopping.
Acceptance must assert exact counts for one, two and three affected frames,
and a received-byte denominator under deletion and silence. The existing
`>= threshold` and clean-stream denominator assertions cannot establish this.

## P2-2 — A known index is still accepted without its known bytes

`host/transport_rig.py:290–303, 382`.

The foreign-frame fix rejects unknown indexes, but does not compare an accepted
line with `by_index[idx].line`. Keep the REC index, change a pad byte and rebuild
its valid CRC: the result reports **302 delivered, no missing frames, zero
losses**. The whole-stream divergence correctly makes `clean` false; this is not
a claim that the entire analysis returns clean. However, the delivery credit,
loss-rate numerator and loss stop rule remain incorrect.

Additionally, `Run.execute` calls `plan_frames(1)` afresh for every repetition.
Both writes are byte-for-byte identical, with the same token/index/sequence.
Replaying repetition 1 as repetition 2 produces **two clean results**. A known
expected byte string is not proof that those bytes were sent in this repetition.

Require exact expected-frame bytes, including all envelope fields and payload,
before crediting delivery. Bind deterministic traffic to an explicit run seed
and repetition identity, and record those values. Add valid-CRC mutations with
known indexes, stale-repetition delivery, and positive deterministic regeneration
controls. Also check actual write completion: the current driver ignores a
`write` return of zero; paired with a stale clean read, it reports a clean result
even though the transport double accepted no output.

## P2-3 — The production driver does not implement the planned traffic/capture

`host/transport_rig.py:250–258, 372–400`;
`evidence/b1q/transport_stage1_2026_09_12/stage1_proof.py`.

The callback trace is: write the entire source stream to one writer, send every
host command to the same writer with sleeps, then call `read` once. There are
no separate source and receiver-side TX channels; `after_frame` is never used.
For A2/B2, `tx_during_rx=False` still writes the entire source stream through
that same callback. With ordinary serial callbacks, this does not implement
the required distinction between independent source traffic and host TX during
RX. With a self-loopback, it also loops the synthetic host commands into the
captured stream. The test's `clean_transport` filters these commands away.

The host schedule is selected by `i % len(HOST_SENDS)`, not the measured schedule:
the probe generates eight AUDITGET commands, whereas the plan cites thirty in
attempt 3. A 62 ms sleep after a write is not a measured TX-to-next-RX gap.
There is no incremental reader with timestamps, source pacing, or bounded drain
of the stream. A serial `read()` may return one byte, not a complete repetition.

The exposure bound is checked only before a repetition. An offline fake-clock
run with a 0.1 s limit spends 2.232 s sending host commands before its first read,
then reports a completed repetition. A blocking callback can exceed the bound
indefinitely; the three-loss rule is evaluated only after that callback returns.

The PTY proof does not call `Run.execute`: it separately pumps one direction,
calls `analyse`, and samples counters on another fresh PTY. It therefore cannot
validate the driver's ordering, overlap, deadline, stop rule or counter lifetime.

Implement and test an explicit two-direction driver with incremental capture,
write completion, timestamped events, paced source/host traffic, actual schedule
consumption and a deadline that bounds the operations. Drive that production
entry point in an offline PTY acceptance run for both TX conditions. If a
transport adapter owns these obligations, make it part of the deliverable and
test it; the current two callbacks do not provide them by themselves.

## P2-4 — Tool errors lose the final result and skip counter completion

`host/transport_rig.py:391–415`.

After one successful repetition, inject a read error in the next. The API raises
`RigError`, returns no result, and samples counters only **once**. The earlier
analysis remains only in the Run object's memory. There is no production
capture archive: raw received bytes and per-read timestamps are not retained,
and the error path cannot return the promised before/after record. The submitted
proof writes a summary, but is a different path and archives no raw capture.

Provide an independently guarded finalization path that retains raw bytes,
timestamps, expected/source bytes or their reproducible binding, completed and
partial repetition results, primary stop reason, and attempted counter capture.
Counter failure must remain explicitly unavailable. Preserve the original tool
error if exporting or final counter sampling also fails. Include fault injection
after partial capture and prove the resulting on-disk evidence is readable.
Hashing this one Python file alone does not describe the full execution: also
record the instrument/framing dependency and run parameters used by the driver.

## P2-5 — The B2Q exposure argument compares different units

`docs/b1q_transport_stage1_2026_09_12.md:78–80`.

The proposed exception says 20 B2Q **records** versus 302 B1Q **frames** means a
much shorter exposure. Production `qualification_session_plan` instead derives
**20 records / 543 expected frames**, including 160 AUDIT and 320 HB frames.
That is planning arithmetic, not an observed run; it does not by itself measure
bytes, duration or retry exposure. B1Q had 11 candidate records.

Withdraw the shorter-exposure rationale. Any new owner disposition must compare
like units using declared frame, byte and duration estimates and applicable
controls/retries. This review does not grant a stop-loss exception. Completing
host-only fixes does not require answering the physical inventory questions yet.

## P3 — `bytes_to_resync` only finds a newline

`host/transport_rig.py:314–319`.

Inserting a newline inside a REC produces `bytes_to_resync: 1`, even though the
bytes after that newline are the remainder of a broken frame. No valid expected
frame is established there. Rename this field to what it actually measures, or
locate a verified expected-frame boundary and record corresponding expected and
received offsets. A first divergence and a total length delta do not localize
every subsequent loss or establish a unique byte alignment in repeated padding.

## Scope correction and next acceptance

The reviewed plan's stage 1 explicitly includes a separate serial device or
physical self-loopback. A software PTY check is valuable preparatory evidence,
but cannot replace that physical acceptance without a stated plan revision.
For now report generator/analyser software progress and the missing driver and
physical acceptance separately; withdraw "stage 1 in full". No hardware action
is requested by this review.

First complete the offline execution and error-path acceptance above. Preserve
the existing evidence with a superseding note rather than rewriting its results.
Then review the corrected batch before Claude pushes it as an accepted delivery.
Physical rig inventory and any authorized experiment follow separately. Keeping
this investigation outside the B1/B2 pinned namespaces is appropriate while no
verdict depends on it; no frozen-pin churn is requested.

Current verified bindings remain:

- B2 S0 manifest: `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`
- B2 pin table: `8d6f64a5fed1fa222b2c29a0dddac6c6fd3346b23481ade1f00a3f104a907ebf`
- Unfrozen prereg: `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`

The B2 image compatibility conclusion is unaffected. The transport stop-loss
remains unresolved.
