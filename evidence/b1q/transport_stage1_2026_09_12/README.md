# B1Q transport — stage 1 executed offline, 2026-09-12

`docs/b1q_transport_plan_2026_09_07.md` §4 **stage 1**: *build the generator/capture tool and
prove it against a separate traffic source, not the Zynq.* This is that, and only that.

- `stage1_proof.py` — regenerates all three artifacts. `python3 -B` from the repository root.
- `profiles.json` — the transmitted shape of **all four** recorded B1Q sessions, derived from
  the committed `console.log` bytes: per frame class, count, byte range, valid vs CRC-failed,
  and every damaged frame with its **byte offset**.
- `generated.json` — what the generator emits, beside that measured shape.
- `pty_run.json` — a bounded run over a raw pty pair: a clean control, then the same stream
  with one byte removed.

## What it establishes

| | |
|---|---|
| known transmitted bytes | the stream is generated, so a divergence is measured against what was **sent**, not against a retransmission of unknown provenance — the provenance weakness the plan names |
| per-byte localisation | first divergence offset, the frame and the offset inside it, the bytes to resynchronisation |
| the counters no session had | `TIOCGICOUNT` framing / parity / overrun / break, sampled before and after. On a pty it is **unavailable and says so**; it is never reported as zero |
| a pre-registered stop | plan §5: 200 repetitions or 60 minutes, early stop at 3 losses in one repetition, stop on any tool error |

`tests/test_transport_rig.py` — **30 tests** — injects every fault the real sessions
showed and requires each to be detected *and* localised: a byte dropped inside a 2.6 kB REC, a
bit flipped in a 66-byte HB, a frame excised, a 200-byte run dropped, a duplicate, a swap, a
truncation, silence, line noise, and a well-formed frame the rig never sent. A tool that
reports clean runs is worth nothing until it is shown to report dirty ones.

**One real defect was found by those tests and fixed:** a frame with a valid CRC whose payload
the rig never transmitted was being counted as *delivered*. That is precisely the
known-transmitted-bytes property the rig exists to provide, and it was broken until the
negative case ran.

## Two independent checks against the record

1. **The plan's §2 table is now derived, not transcribed.** The frozen `SESSION_PROFILE`
   (302 frames: IDENT 1, SIGNREQ 12, HB 176, REC 12, AUDIT 88, AUDIT_READY 11, CLOSE 1,
   TERM 1) is re-derived from the clean session's bytes and compared class by class.
2. **The owner's corrected count reproduces.** The transport review of 2026-09-07 withdrew the
   claim of five non-control CRC events and corrected it to **four, plus one fragment**.
   Deriving it from the committed bytes gives exactly that:

   | session | forced controls | non-control CRC events | fragment |
   |---|---|---|---|
   | 2026-09-06-01 | SIGNREQ seq 1 @1105, REC seq 1 @6463 | **TERM @93526** | — |
   | 2026-09-06-02 | the same two | — | — |
   | 2026-09-06-03 | SIGNREQ seq 1 @1105, REC seq 1 @6751 | **HB @12747, REC @26111, AUDIT @35426** | malformed SIGNREQ retransmission @1475 |
   | 2026-09-08-01 (attempt 4) | the same two | — | — |

   The two forced controls sit at the **same offsets** in every complete session — a
   deterministic session feature, not a transport event — which is why the rig transmits none:
   every CRC failure a rig run sees is a transport event with no control to subtract. The
   controls are identified by the session's rule (first damaged SIGNREQ seq 1, first damaged
   REC seq 1), not by a byte offset that happens to be true today.

## What it does NOT establish

- **A pty is not a UART.** It has no framing, parity or overrun and it does not lose bytes. The
  run proves the generator, the capture and the analysis end to end; it proves nothing about
  any link.
- **No condition of plan §3 was run.** A1 / A2 / B1 / B2 are stage 2 and need hosts and a rig
  the owner must supply (plan §7's three open questions).
- **Nothing is attributed.** Plan §6 stands: CH340/driver, USB-IP/WSL, wiring, board UART and
  host handling all remain open. The stop-loss is not lifted, no board session is authorised,
  and attempt 4's single clean session still does not establish transport stability.
- **Not a B2 verdict input.** `host/transport_rig.py` and its tests are deliberately outside
  **both** pinned globs. `host/b1q_*.py` is B1Q's decision surface and `host/b2_*.py` is B2's;
  a file in either must be in that frozen table, and B1's pin guard refused this file when it
  was first written as `host/b1q_transport_rig.py` — correctly, because an investigation tool
  in a verdict namespace either churns a frozen manifest or claims an authority it does not
  have. Provenance comes instead from the tool's own sha256, recorded beside every result. If a
  transport measurement ever becomes an input to a verdict it must be pinned by that decision — and per the plan, instrumenting a *session* is a pinned change that lands,
  is reviewed and is re-qualified **before** the session that counts.
