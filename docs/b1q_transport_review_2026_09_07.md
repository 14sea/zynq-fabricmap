B1Q transport diagnosis review and option decision — 2026-09-07

**Decision: select B for controlled console-path isolation planning. Approve pushing
98c2a0c and ffea0a5 together with a corrective documentation/analysis commit containing
this review and the corrected diagnosis. Stop-loss remains in force.** This decision
does not authorize opening a port, rewiring, attaching/detaching USB or executing a board
session. No new ruling pair is issued.

The original diagnosis overstated the evidence. Independently recomputed statistics
from the three B1Q timelines and the instrument's saved soak timeline show:

- Four non-control B1Q CRC events, not five; the additional observation is a fragment.
- The timing comparison lacks discrimination: 40/40 soak CRC events are within 0.5 s
  after host TX, but so are 233349/233354 CRC-valid received frames. It cannot establish
  electrical TX activity as the cause. The fragment times are detection times.
- The attempt-1 TERM comparison involves 13 missing characters and an inferred frame,
  not an intact same-run retransmission. The attempt-3 HB loss is in its token. Only the
  cited attempt-3 REC comparison directly uses its own valid retransmission.
- The prior attempt-3 rate mixed three CRC events with a four-event numerator including
  the fragment. Using exact raw-file bytes gives 3/35888, or 8.359 CRC events per 100000
  bytes. Using the observed 103 valid frames gives 2.913%, not the rate from 300 planned
  frames. Different stopping conditions prevent a simple stationary noise-rate comparison.
- Character loss does not establish which UART, electrical, buffering, adapter, driver
  or host component caused it. The board and those mechanisms have not been excluded.
  The old-rule AUDIT budget stop also cannot establish what a differently defined
  counterfactual budget rule would have done.

The corrected diagnosis and analysis.json supersede those assertions in ffea0a5,
including its commit-message claims. No history rewrite or original-evidence modification
is required. Reproduction script, per-session input hashes and recomputed counts are in
evidence/b1q/diagnosis_review_2026_09_07/.

B is selected as an engineering investigation, not a confirmed cure. Prefer a native
Linux host with the same adapter, wiring and serial settings if available, changing the
host/USB-IP path first. Otherwise prepare an adapter-only alternative with verified
electrical details. The next authorized work is the offline inventory and reviewable
test plan: one changed variable, known transmitted bytes, representative frame lengths
and bidirectional traffic, reference/control conditions, capture provenance, error
counters, bounded exposure and stopping criteria. Keep physical changes pending review.

A is not approved because it changes the acceptance contract rather than demonstrating
a transport repair. C is not selected as a separate quiet board capture; any measurements
for B must be designed to represent the failing workload and separately authorized.
No budget increase, qualification pinning or new experimental session is approved.

Validation: the descriptive statistics were independently recomputed, including normal
RX traffic as the timing comparison population. All 105 fabricmap pins and 128 archived
instrument pins verify; the instrument worktree is clean. Manifest remains
38363973c10c48244dc04f08044647b1159d1446b00dec5776d9478b9aad0a0e.
This is a docs/analysis correction; no runtime change or full-suite rerun was necessary.
The reviewer did not commit, push, change a pinned file, open a device or touch the board.
