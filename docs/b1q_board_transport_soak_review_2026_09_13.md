# Board transport soak review — 2026-09-13

**HOLD: six P2 findings in the proposed measurement and implementation.**
Do not push `1986bd4` as accepted software or run the board probe yet. No ruling
is issued by this review. No port, board, firmware, frozen input or instrument
was changed. The existing transport stop-loss remains in force.

Reviewed HEAD: `1986bd4`. The independent offline probe and observed output are
in `evidence/b1q/review_board_soak_2026_09_13/`. The new ten-test suite passes
(10 tests, zero skips, OK, 3.022 s); the probes below show gaps those tests miss.
The previously accepted 130-test transport suite was not rerun in this review.

## P2-1 — the proposed measurement does not establish a B2Q loss bound

The handoff's estimate of approximately 3.6 drops appears to scale the two drops
in a clean B1Q run by 543/300. Those two drops are deliberate SIGNREQ/REC controls,
not a measured background loss rate. Production B2Q planning explicitly enables
both controls (`host/b2_runner.py:276–283`); they are fixed session events, not
random events whose count scales with the number of frames. The documented
543-frame arithmetic and budget 3 do not establish an expected random loss of
3.6 or that failure is the most likely result. Keep controls, real CRC drops,
fragments and retransmissions separate. Do not change the frozen budget.

There is also no established mapping from this probe's damaged **reads** per byte
to B2Q's failed **frames**. One md read contains many short lines; one or many
changed words in the entire window both count as one damaged read. The loop sends
the next command after the prior prompt, so it does not reproduce the sustained
reply TX during frame RX pattern under investigation. More aggregate bytes do
not establish equivalent traffic or an upper bound on another protocol's loss.
The denominator additionally includes the baseline, which was selected for
acceptance and was not tested against an independent answer.

A first syntactically valid read is a reference observation, not independently
known transmitted bytes or proof that DDR is stable. The probe corrupts the
same hex value in the baseline and every later response: the tool reports zero
damage. A changed word can also reflect changed source memory. One observation
cannot distinguish source variation from transport corruption. The current
claim that any difference is necessarily transport damage must be withdrawn.

Required decision before more implementation: narrow this to a U-Boot repeated
read consistency control, with explicit unknown cause and no B2Q loss-bound
claim, or supply independently established source content/stability and an
appropriate traffic design. State the new unit and prospective stopping rule:
current code stops after three damaged reads across the entire run, while its
comments claim damaged lines within a repetition. Neither is interchangeable
with the existing rig's three lost expected frames within one repetition.

## P2-2 — the parser accepts damaged output as byte-exact delivery

`host/board_transport_soak.py:45,70–86,242–249`.
`MD_LINE_RE.findall` takes matching prefixes and silently ignores unmatched
bytes; comparison then checks parsed integers only. There is no byte-exact
per-line comparison.

Two independent real-CLI probes return exit 0, zero damaged reads and complete
exports:

- delete one byte from the ASCII rendering column of every post-baseline reply;
- append a ninth hex digit to the fourth word, changing `cafef00d` to
  `cafef00d0`; the parser still consumes the first eight digits and ignores the
  extra byte.

Required correction: define and validate the complete response grammar and its
line boundaries, explicitly accounting for command echo, prompt, whitespace and
ASCII rendering. If claiming byte-exact delivery, compare all bytes in the
specified measurement unit, with only declared framing exclusions. A normalized
word-value comparison can be useful but must have a different claim. Add intact
controls and deletions/insertions in every response region, not only the first
hex word, plus multi-line damage and accounting tests.

## P2-3 — failure handling regresses the accepted rig entry-point contract

`host/board_transport_soak.py:147–176,183–220,233–236`.
Importing Port and helpers does not import the rig's acquisition/finalization
control flow. The new implementation independently repeats defects already
closed in the rig:

| probe | observed result |
|---|---|
| provenance raises before open | port opens, sync/baseline/two reads execute, exit 0 |
| detach after 20 bytes of first soak response | OSError escapes, one counter attempt, no partial read file, no soak.json or entry.json |
| baseline.bin export raises | both later reads execute anyway, exit 0; export_complete false |
| entry.json export raises | no entry.json, but stdout still says export_complete true |

The partial bytes live only inside `_read_until_prompt` and disappear when it
raises. The outer finally closes the port but never reaches finalization.
Export errors must not be converted into permission to continue an acquisition
without mandatory evidence.

Required correction: mandatory construction/initial export failures stop before
further port activity; preserve partial raw data on read/write errors; attempt
both counters and all finalization components independently; persist a terminal
entry result; recompute export_complete after every export attempt. Keep the
primary exception distinct from secondary archive failures and counter
unavailability. Exercise the new CLI with the same adverse cases as the rig.

## P2-4 — the exposure deadline does not bound the active command

`host/board_transport_soak.py:98–123,227–233`.
The exposure time is checked only between commands. Each command writes with an
independent three-second budget and then starts another three-second read
budget; reads are not capped to remaining exposure. `sync` also discards whether
it actually saw a prompt before the first md command is sent.

With `--seconds 0.01`, a fake board that stops answering after the baseline
runs to virtual time 3.15 s and is labelled `board_disruption`. The exposure
clock began at 0.10 s, so the active read consumed approximately 3.05 s despite
the 0.01 s allowance. No boot banner was supplied. Lack of a prompt by a timeout
could be a transport loss, a command failure or cutoff; it does not establish
board reset or another board-specific cause.

Required correction: use a monotonic deadline shared by write/read operations
within each declared phase, cap by remaining exposure, preserve cutoff data and
classify an unexplained timeout separately from an observed boot banner. Refuse
an unsuccessful prompt sync before issuing md. Test active read/write expiry,
missing/damaged prompts and observed reboot as distinct cases.

## P2-5 — the claimed DDR-only scope is not enforced by CLI inputs

`host/board_transport_soak.py:211,300–309`.
`--addr` and `--words` accept arbitrary integers; no alignment, range, positive
length or end-address check precedes device access. The offline probe supplies
`--addr 0x40000000` and observes actual command emission
`md.l 0x40000000 0x4`, followed by a successful fake run.

The repository's B2 BSP records DDR through `0x1fffffff`
(`firmware/b2/bsp/include/xparameters.h:26–28`). The probe address is outside
that recorded DDR range. A tool that permits arbitrary memory reads cannot claim
that PL AXI or other side-effecting MMIO is excluded by construction. This
review performs no such hardware read.

Required correction: define an explicitly reviewed, reserved DDR window for this
probe and reject accesses outside it before opening. Check start alignment,
positive bounded word count, overflow and end address. Independently establish
that the chosen window is not used by the running U-Boot. Validate finite
positive exposure parameters too. A successful first read is not that proof.

## P2-6 — provenance identifies the helper instead of the acquisition tool

`host/board_transport_soak.py:39–42,191,265` imports `provenance` and
`self_sha256` directly from transport_rig. Those functions retain the helper's
module globals: their `__file__` is transport_rig.py.

The clean probe's invocation names `host/transport_rig.py`, and soak.json's
`tool_sha256` is
`e2af873d521b340d2f42d1c9248e2a28f9669687b2d24c762638dd05a5543478`.
The actual board tool digest is
`331c8c446c61d8ec96c952703423129956dbc77af4f3baadb97d7c3970f47f60`.
Thus later edits to the board tool are not reflected by its declared tool hash.
The inherited loss_unit also names expected frames, not this tool's reads.

The proposed ruling names the correct board-tool digest but an obsolete B1
manifest digest `38363973…`. Current committed B1 manifest is
`38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`.
The CLI currently does not read that ruling or bind its parameters. A USB
VID:PID check also does not independently establish board identity 17A6.

Required correction: record the actual board tool and imported dependencies
separately, with the actual measurement unit. Prepare any later authorization
against current reviewed hashes and explicit DDR/exposure bounds. State which
bindings are checked by the program and which are mandatory operator checks;
do not treat an illustrative JSON draft as implemented authorization. No ruling
is signed here and none should be inferred from this document.

## What remains authorized and verified

Host-only revision and offline testing can continue. The useful narrow question
is whether repeated U-Boot responses are consistent under specified conditions;
that is different from predicting B2Q failure or excluding memory variation.
The present results do not support bypassing the stop-loss or classifying a new
failure as exempt merely because it is called a soak.

Production B2 verify still accepts S1, qualified false, refusal null, with
71 B2 / 105 B1 pins and unchanged manifest
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
Only this review and its offline probes were added. Existing evidence, source,
image, frozen preregistration, instrument and rulings were left untouched.
