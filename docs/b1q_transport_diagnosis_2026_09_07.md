# B1Q transport diagnosis — corrected off-board analysis, 2026-09-07

> **STOP-LOSS remains in force.** The observed receive-stream corruption is established;
> the component responsible is not. This revision supersedes the unsupported causal
> claims and mixed denominators in ffea0a5, including its commit message. Original session
> evidence remains unchanged. No port, cable, device attachment or board was touched.

## Recomputed observations

The independent script and input hashes are in
`evidence/b1q/diagnosis_review_2026_09_07/`. The corrected machine-readable diagnosis is
`evidence/b1q/transport_diagnosis_2026_09_07/analysis.json` (version 1.1.0).

CRC counts below exclude the two identified seq-1 forced controls in each session.
Fragments are separate. Valid RX frames exclude timeline CRC_DROP/FRAGMENT events;
bytes are the complete raw console.log file size, including framing and line terminators.

| Session | Valid RX frames | Raw bytes | Non-control CRC drops | Fragments | CRC drops per 100,000 raw bytes |
|---|---:|---:|---:|---:|---:|
| B1Q attempt 1 | 299 | 94,237 | 1 | 0 | 1.061 |
| B1Q attempt 2 | 300 | 94,250 | 0 | 0 | 0 |
| B1Q attempt 3 | 103 | 35,888 | 3 | 1 | 8.359 |
| L6 soak 2026-09-04-01-S | 233,354 | 50,642,507 | 40 | 3 | 0.079 |

The B1Q total is **four non-control CRC drops plus one fragment**, not five CRC drops.
Attempt 3 did not receive the planned approximately 300 valid frames before stopping;
3/103 is 2.913%, not 1%. These are descriptive counts under different traffic, durations
and stopping conditions, not comparable estimates of a stationary link noise rate.

## Character deletion is supported; component attribution is not

The previous audit's comparisons support these specific observations:

- Attempt-1 TERM: 13 missing payload characters against an inferred expected TERM with
  the correct session token and matching retained CRC; no same-run retransmission exists.
- Attempt-3 HB seq 2: six missing token characters; payload intact. Restoring the known
  token reproduces the retained CRC.
- Attempt-3 REC seq 3: one missing payload character against its valid retransmission.
- Attempt-3 AUDIT seq 4, chunk 4: two missing payload characters against the prior valid
  session's chunk with this session's frame token; an inferred expected frame.
- Attempt-3 SIGNREQ: a separate 288-byte prefix quarantined without its terminator.

Thus "every line is 1–6 bytes shorter than its own retransmission" was incorrect.
Remaining inside the base64url alphabet alone cannot establish the corruption mechanism.
The comparison provenance matters; none is an independent capture at the transmitter.

Missing characters do not rule out electrical/framing errors, board UART/software,
adapter/driver behavior or finite-buffer loss. For example, serial error handling can
discard characters under particular input flags; this is a general counterexample to
"electrical errors only flip bytes", not a claim that those flags caused these sessions.
[Linux serial driver documentation](https://kernel.org/doc/html/v6.15/driver-api/serial/driver.html)
describes that behavior. The necessary session-time error counters and transmitter-side
trace are absent. No cited CLAUDE.md anecdote substitutes for that evidence.

## The TX timing window does not establish full-duplex causality

All four non-control B1Q CRC events follow the last recorded host TX by 0.062–0.246 s.
All 40 non-control soak CRC events fall within 0.5 s of a host TX. However, the comparison
population is almost entirely in that same window:

| Population | Within 0.5 s of preceding host TX | Total |
|---|---:|---:|
| Soak non-control CRC events | 40 | 40 |
| Soak CRC-valid RX frames | 233,349 | 233,354 |

Normal request/reply traffic already produces this timing. The near-universal window
cannot identify host transmission as the cause of a loss. Host send timestamps are not
measurements of electrical TX-line activity. Frame length, request type, polling and
serialisation time also differ between observations. Fragment timestamps record their
quarantine/detection, sometimes around eight seconds after the last TX, not the time the
missing bytes were lost.

CH340/driver, USB/IP/WSL and other stages remain hypotheses. The post-hoc sysfs inventory
places both CH340 and FTDI under vhci_hcd; replacing the adapter while retaining that
arrangement would not independently eliminate USB/IP. One successful B1Q session proves
that session's qualification, not that the link is usually reliable or stable.

## Decision and bounded next work

**Select B as a controlled console-path isolation experiment, not as a proven cure.**
Prepare the environment inventory, topology and compatibility/diagnostic plan first.
If a native Linux host is available, prefer removing WSL/USB-IP while initially keeping
the same CH340, wiring and serial settings. Changing both host path and adapter together
would obscure which change affected the result. If that host is unavailable, submit a
separate adapter-only design with verified pinout and voltage before any rewiring.

Before execution, the plan must specify the changed variable, known transmitted bytes,
expected traffic including relevant frame lengths and host-send bursts, reference/control
conditions, received raw-byte capture, fragments, retries, timestamps and available error
counters. Prefer proving capture and replay against a separate traffic source before
using the Zynq. Bound the exposure and stopping criteria in advance; a quiet passive
capture does not represent the traffic that failed. A successful diagnostic is not a
B1Q PASS or a waiver of the qualification chain.

A is not approved: changing the CRC counter's meaning changes the acceptance contract.
The claim that A could not save attempt 3 is also unsupported: the AUDIT pull stopped
because of the old budget rule, so that stop cannot be assumed under a different rule.
The HB and all other requirements would need explicit modeling before any counterfactual
verdict. Increasing the budget remains excluded; it would change the agreed acceptance
criteria, not necessarily manufacture false underlying measurements.

C is not selected as a stand-alone quiet board capture. Measurements needed to evaluate
B belong in its controlled plan and require separate execution approval.

The owner approves pushing 98c2a0c and ffea0a5 **together with a new corrective docs/analysis
commit containing this revision and the review**. No pinned file or manifest changes are
needed for these corrections. Stop-loss remains in force: no new ruling, port open,
rewiring, attach/detach or board run is authorized. Attempt 1/3 remain LOST; attempt 2
remains a historical PASS for its original manifest.
