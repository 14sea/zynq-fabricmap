# Repeated-read consistency control review — 2026-09-13

**HOLD: four P2 findings remain at `fd89516`.** The narrower experimental
question is accepted as a consistency observation, with unknown cause and no
B2Q loss bound. The withdrawal of the forced-control extrapolation is correct.
The outstanding findings concern implementing that narrower contract.

Do not release the three-commit board-control batch as accepted software or run
it on the board yet. This review opens no port and issues no ruling. It changes
only review documents and offline evidence.

## P2-1 — mandatory capture export failures still permit later commands

`host/board_transport_soak.py:388,407–420,443` ignores the result of `attempt`
for sync, reference and repeated-read raw exports. An error is collected for the
final brief but does not stop acquisition.

Independent CLI injections against the current file names show:

| failing file | later behavior |
|---|---|
| sync.bin | reference and all four repeated reads still issued |
| reference.bin | all four repeated reads still issued |
| read_0000.bin | remaining three reads still issued |

Every case returns exit 0 and `exposure_repetitions`, with export_complete false.
The error is disclosed, but the stop-on-tool-error contract is not enforced.
This is the same mandatory-evidence issue from the previous P2-3. The handoff's
claim that an equivalent reference-export fault was covered is not supported by
the submitted tests: they fault control.json and entry.json, not reference.bin.
The old probe's baseline.bin injection indeed no longer addresses the code.

Required correction: after a required acquisition export fails, stop before the
next command, retain the primary export error and any preceding transport error,
attempt the remaining finalization components and both counters, and return a
named nonzero tool state. Final entry/control writes happen after acquisition
and cannot stop past commands, but must retain truthful completeness. Test each
acquisition file separately with command-count assertions and valid controls.

## P2-2 — framing removal erases response-body mutations

`host/board_transport_soak.py:153–169` uses `body.find(command)` anywhere in the
reply, then removes that substring as an echo. An injected copy of
`md.l 0x00100000 0x4` inside the ASCII column is therefore removed from the data
body. The CLI reports four identical responses, zero mismatches, exit 0.

A separate probe prepends an extra CRLF to one post-reference reply. It is also
reported identical because arbitrary leading/trailing CR/LF runs are stripped.
The declared exclusions list only the command echo and trailing prompt; it does
not declare this unbounded normalization. Even if limited separator normalization
is chosen prospectively, data-region command strings must never be removed.

Required correction: recognize a complete optional command-echo line only at its
allowed framing position, with explicit separators; recognize the prompt only
at its allowed terminal position. Account for every other byte. Define exact
permitted line endings, including whether any are excluded, and test additional
and missing separators as well as command-like text inside data. Preserve a
legitimate echo/prompt positive control and the existing ASCII/hex mutations.

## P2-3 — a reboot banner followed by a prompt is not treated as a reboot

`host/board_transport_soak.py:450–475` checks BOOT_BANNER_RE only when exchange
reports no prompt. A normal-shaped reboot transcript can include both a banner
and a fresh prompt. The probe supplies a banner followed by `Zynq> ` on the first
repeated read. The tool counts one ordinary mismatch, issues the remaining three
commands and ends exit 0 / exposure_repetitions.

Required correction: classify an observed boot banner independently of prompt
presence, before ordinary consistency comparison and before another command.
Preserve the bytes and stop as board_reset under the declared rule. Apply the
classification consistently to the acquisition phases. Test banner with prompt,
banner without prompt, prompt timeout without banner and clean prompt responses.
No new claim about the physical cause of an unexplained timeout is needed.

## P2-4 — unclassified partial responses produce contradictory statistics

`host/board_transport_soak.py:502–515` and `_finalise` divide mismatches by all
records, including the terminal record that has no comparison outcome. The
persistent flag filters out absent outcomes and then calls all() on an empty
sequence, which returns true.

Two independent cases reproduce the same contradiction:

- Detach after 20 bytes of the first repeated response: exit 2/tool_error.
- Exposure cutoff before a response completes: exit 0/exposure_seconds.

Both have zero identical responses and zero classified mismatches, yet report
`mismatches_per_100_responses: 0.0` and
`all_observed_responses_differ: true`. Raw data is preserved and the terminal
condition is named; the aggregate conclusions are nevertheless unsupported.

Required correction: report attempted/completed/compared/unclassified counts
separately. A comparison rate must use its explicitly named compared-response
denominator and be null when that denominator is zero. A statement about all
observed responses cannot become true by discarding unclassified observations;
use unknown/null, or rename and precisely limit a statistic to classified data.
Do not turn cutoff/partial data into either a confirmed match or a confirmed
mismatch. Test zero compared, mixed completed-plus-cutoff, and completed positive
and mismatch controls in both the archive and stdout.

## Validation and retained corrections

- Existing board-control suite: **26 tests, zero skips, OK**, 0.057 s.
- Independent CLI probes: one valid control plus eight adverse cases, using the
  submitted fake-board adapter and temporary directories. Production parsing,
  command loop, accounting and finalization execute unchanged.
- The changed scope, separate tool/dependency provenance, DDR/exposure input
  checks, construction-error refusal and preservation of partial bytes are
  improvements retained by this review. The four cases above are not reasons to
  restore the old broader experiment.
- Production B2 verify accepts S1, qualified false, refusal null, 71 B2 / 105 B1
  pins; manifest remains
  `8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
- The unchanged rig suite and the previous 37-test gate suite were not rerun;
  live production verification was rerun. No whole-suite clean-tree proof is
  claimed.

## Next experimental decision

The withdrawn 3.6-drop argument settles neither B2Q success nor B2Q failure.
It also does not erase the recorded transport losses or release the stop-loss.
The repeated-read control is optional for its own narrow question; it should
not become a mandatory detour marketed as evidence about B2Q reliability.

My recommendation remains preparation of the existing native-Linux comparison,
using the same adapter, wiring, baud, traffic and exposure definitions as the
comparison condition. That tests the host-path question more directly. Board
consistency acquisition and any exception allowing B2Q require separate explicit
authorization after their prerequisites are established. This review authorizes
only host-only corrections and offline checks, not either physical action.
