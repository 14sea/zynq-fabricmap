# The transport rig's five P2s — corrected, 2026-09-12

The owner's review: `docs/b1q_transport_stage1_review_2026_09_12.md`, against `4528ef8`, with
its counterexamples in `evidence/b1q/review_transport_stage1_2026_09_12/`. Every one is real and
every one was reproduced from the public API with a pristine generated stream as the control.

`acceptance.py` runs the owner's own probes against the corrected code and prints each
observation **beside theirs**; `acceptance.json` is its output. Their `probe_rig.py` cannot
simply be re-run — `Run.execute` no longer takes two bare callables, because the missing
execution contract *was* P2-3.

| | at `4528ef8` | now |
|---|---|---|
| one corrupted frame | **2** losses | **1** |
| two corrupted frames | **4** losses, and the three-loss stop fired | **2** losses, the condition keeps running |
| silence | denominator **98 627** (bytes *sent*), rate **306.204** per 100k | denominator **0**, rate **null**, "unavailable: nothing was received", **302** losses, and it still stops |
| valid CRC over bytes never sent, known index | **302 delivered, 0 losses** | **301 delivered, 1 loss**, `damaged: [10]`, `{"altered": 1}` |
| repetition 0's capture replayed as repetition 1 | both **clean**; both writes byte-identical | `[clean, NOT clean]`, second repetition **302** losses; the two streams differ |
| a write that accepts 0 bytes | reported a **clean** run | `REFUSED: short write, 0 of 1048 bytes accepted` |
| the driver | **1** source write, **1** read, `after_frame` unused, 8 AUDITGET | **302** source writes, **125** host writes on the host port, **430** reads, interleaved `source → read → host → read → source …` |
| a 0.1 s deadline | ran **2.232 s** and reported "1 repetitions completed" | stops **inside** the repetition after 2 frames, at 0.13 s (the limit plus at most one scheduled gap) |
| a tool error after one good repetition | no result returned, **1** counter sample, nothing on disk | result returned **and exported**, **2** counter samples, 2 raw captures plus their event logs on disk and readable, `OSError` preserved as the cause |
| an inserted newline | `bytes_to_resync: 1`, **3** losses | `bytes_to_next_newline: 1` **and** `resynchronised_at` naming verified frame 11 at 2 512 bytes later; **1** loss |
| B2Q exposure | "20 records vs 302 frames — much shorter" | **withdrawn**: production `qualification_session_plan` gives **543 expected frames** for B2Q against B1Q's 302, and that is planning arithmetic, not an observed run |

## What changed in the tool

* **One loss unit** — an expected frame not delivered byte-exact, counted once, however its
  damage parses. A bit flip, a dropped byte, a rebuilt-CRC alteration, an inserted newline and
  an outright deletion of the same frame now all weigh **1**, which a test asserts case by case.
  CRC failures, altered frames, foreign epochs, unexpected indexes, duplicates, reordering and
  host echo remain separately visible. **The registered three-loss threshold is unchanged**;
  only the unit it counts is now correct.
* **Received-byte denominator**, with "no denominator" as a first-class answer.
* **Byte-exact delivery**, and a **per-repetition epoch token** (`token_for(run_id, repetition)`)
  carried in the field rel-v4 already reserves for it — so a stale capture is not equal-looking
  traffic, it is another epoch, and the analyser says which.
* **A real two-direction driver**: frame-by-frame writes with completion checked, the host's
  replies on the host port at the points the recorded session emits them, incremental
  timestamped reads, a bounded final drain, and a deadline checked around every operation.
  The host schedule is **derived** — `host_schedule_from_timeline` reads the clean session's own
  `timeline.json` (302 rx / 125 tx) and the rule it exhibits is what the rig emits: IDENT→IDENTACK,
  SIGNREQ→SIGNOK, AUDIT_READY→AUDITGET, each AUDIT→AUDITGET except a record's last chunk→AUDITDONE,
  REC→RECACK, TERM→TERMACK. The measured tx→next-rx gap (min 0.041 s, median 0.065 s) comes from
  the same file.
* **`host_echo`** — on a self-loopback the rig's own host traffic returns in the capture. It is
  classified, counted and excluded from the defects, and the run records the **topology**
  (`one device: source, host and capture are the same port …`) instead of a test helper quietly
  filtering it away.
* **A finalisation that always lands** — raw capture, per-read events, partial results, the stop
  reason and attempted counters exported even when the run dies; the original error preserved
  and carried on the exception with the result and the export path.
* **Provenance** beyond one file's hash: the tool's sha256, the instrument's framing module and
  its sha256, the instrument root, the loss unit and the run parameters.

`tests/test_transport_rig.py` is now **49 tests**, including the exact-count cases for one, two
and three affected frames, the received-byte denominator under deletion and silence, the
valid-CRC mutation, the stale repetition, the short write, the driver's ordering and overlap,
the deadline bounding the operations, the export on the error path, and the production entry
point over a pty for **both** §3 TX conditions.

## What is still NOT done

The plan's stage 1 also requires a **physical** acceptance — a separate serial device or a
physical self-loopback. That has not happened, a pseudo-terminal cannot replace it, and this is
therefore a **partial software delivery**, not a completed stage. A pty has no UART framing,
parity or overrun and loses nothing. Nothing here attributes anything, lifts the stop-loss, or
authorises a board session; no pinned file moved and the B2 manifest is untouched.
