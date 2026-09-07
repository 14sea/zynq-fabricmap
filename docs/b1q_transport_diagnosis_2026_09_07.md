# B1Q transport diagnosis — off-board investigation, 2026-09-07

> **Standing: off-board only.** Authorised by the owner's ruling of the attempt-3 loss
> (`docs/b1q_session3_audit_2026_09_07.md`): analysis of the saved logs, in-memory replay
> and diagnostic design — no port opened, no cable changed, no re-attach, no board run, no
> CRC-budget change, no pinning of a HOLD record, no new ruling pair. Machine-readable
> figures: `evidence/b1q/transport_diagnosis_2026_09_07/analysis.json`. Nothing here changes
> a pinned file's meaning; it is a finding for the owner to rule on.

## The question

Attempt 3 lost the epoch to `PROTOCOL_CRC_BUDGET: 5 > 4` at seq 3, while attempt 2 passed
cleanly and the L6 soak ran two hours on the same transport. Is the fault the board, the
instrument, or the link — and what, if anything, is the fix.

## What the saved evidence shows

**The losses are dropped bytes, not corrupted bytes.** Every CRC-failing line, diffed
against its own intact retransmission, is *shorter* by one to six bytes; the payload never
leaves the base64url alphabet and no byte is changed in place. Attempt 3: a REC (seq 3)
short one byte at payload offset 896 — and retransmitted intact; the HB (seq 2) token short
six characters; the AUDIT (seq 4) payload short two; and one SIGNREQ head torn so badly the
reader quarantined it as a fragment. This is a receive-path byte drop, not electrical line
corruption (which flips bytes) and not a large-block buffer overflow (which loses a
contiguous run).

**Every drop follows a host transmission.** Across the three B1Q sessions all five real
CRC drops land 0.06–0.25 s after the preceding host→board frame (IDENTACK, AUDITDONE,
SIGNOK, AUDITGET, RECACK); across the 2-hour soak, **40 of 40** real drops fall within
0.5 s of a host transmission. The board→host bytes are being dropped while, or just after,
the host drives the board←host line. That is a full-duplex interaction on the link, not
random noise and not something the board originates.

**The rate is low but bursty.** Real byte-loss runs about 0.017 % per frame on the soak
(40 drops in 233 350 frames over two hours, spread out, a median of 106 s apart). Attempt 2
saw none. Attempt 3 saw three real drops in ~300 frames — roughly 1 %, about sixty times
the baseline — in a fifteen-second burst.

| session | span | rx frames | rx bytes | real drops | rate | end |
|---|---|---|---|---|---|---|
| B1Q 2026-09-06-01 | 13.6 s | 299 | 93.9 kB | 1 | 1.06 / 100 kB | PROTOCOL (the lost TERM; budget 2, pre-v2.4) |
| B1Q 2026-09-06-02 | 14.0 s | 300 | 93.9 kB | 0 | 0 | COMPLETED / PASS |
| B1Q 2026-09-06-03 | 15.2 s | 103 | 35.8 kB | 3 | 11.18 / 100 kB | PROTOCOL_CRC_BUDGET 5 > 4 |
| L6 soak 2026-09-04-01 | 6764 s | 233 350 | — | 40 | 0.017 %/frame | COMPLETED (budget 934) |

## Attribution

The fault is in the **transport**, not the board: the loss shape (dropped RX bytes) and the
timing (100 % correlated with host TX) both point at the receive path of the CH340
full-speed link through WSL's `vhci_hcd`, and `CLAUDE.md` already records this path as
unstable (brownout drop, ghost-stuck `ttyUSB`, unstable across detach/reattach). It is
**not yet separable** into "the CH340 adapter" versus "USB/IP": the FTDI JTAG pod
(480 Mbit high-speed) traverses the same `vhci_hcd`, so a clean A/B needs the console on a
different physical channel, which the FTDI pins are not wired for.

## Why the soak survived and B1Q did not

The soak absorbed forty drops because its budget was 934 over 233 k frames and its span was
two hours. A B1Q session is deliberately nine probes — about 300 frames — with a CRC budget
of 4: the D-s4 noise allowance of 2 plus the two forced seq-1 controls. That leaves a real-
noise margin of **two**, which a fifteen-second burst exhausts. The mismatch is structural:
a tiny-sample session has no room for the transport's occasional spikes. Attempt 2 is not
proof the link is fine; it is proof the link is *usually* fine.

## What is not the fix

Raising the B1Q budget — the owner's explicit exclusion — would trade the PROTOCOL-death
ceiling for a false PASS on a genuinely noisy link. The ceiling is doing its job: it
refused to certify a session it could not carry cleanly. The problem to solve is the
transport, or the session's dependence on it, not the number.

## Options for the owner (none executed)

- **A — the CRC budget counts only *unrecovered* transport failures.** Today a corrupt
  frame counts toward `PROTOCOL_CRC` even when the protocol then recovers it (a REC
  retransmitted intact on RECGET, an AUDIT chunk re-pulled intact). Counting only losses
  that are never recovered removes the brittleness of the common single-recovered-drop
  case. It would **not** have saved attempt 3 (its HB is fire-and-forget and unrecoverable,
  and its AUDIT pull hit the ceiling), and it changes the instrument's protocol contract and
  the frozen plan/prereg, so it is a measurement-integrity decision with its own review, not
  a bug fix.
- **B — change the physical console transport.** Move the console off the CH340 onto the
  FTDI pod's spare high-speed UART, or off WSL usbipd onto a native-Linux host. This
  addresses the implicated path directly, but it is hardware/environment work (rewiring, a
  new transport compatibility review), not host-only.
- **C — characterise the transport passively first.** A longer capture to size the loss
  rate and confirm the full-duplex hypothesis before choosing A or B. Opening the port is
  board contact and needs its own ruling.

**Assessment:** the cause is a transport fault; option B addresses it, option A only softens
the symptom (and does not recover attempt 3), option C buys certainty at the cost of board
time. The choice is the owner's. Attempt 2 remains a valid PASS under its own manifest, and
attempt 3 remains LOST; the stop-loss stays in force until the owner rules a fix and it is
proven.
