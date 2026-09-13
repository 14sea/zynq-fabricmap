# Transport entry-point second review and retry clarification — 2026-09-13

**Disposition: the original three P2 cases are fixed; one additional P2 keeps
software acceptance on HOLD.** Do not release the entire nine-commit fabricmap
batch as reviewed/accepted yet. This review performs no push or device access.

Reviewed implementation: `6c7a276`, observed HEAD `84be778`. Tool SHA-256:
`15460127bbcd08ffbc1e75ec7bc20d40601cd4f900e675fd41b11cdae3353a46`.
The second-review script and results are in
`evidence/b1q/review_transport_entrypoint_v2_2026_09_13/`.

## Accepted corrections

The independent CLI probes confirm:

- Continuous preflight input ends at virtual time 3.0 s, exit 3, `not_quiet`, with
  raw bytes and both counter attempts. No exposure begins.
- Detach after receiving the nonce returns exit 2; the 43 received bytes survive,
  their digest matches preflight metadata, and both counter attempts occur.
- A nonempty destination returns exit 5, makes zero writes to the port, and
  preserves the old capture byte-for-byte.
- A clean fake loopback still completes 302 frames with zero losses. Silence
  still returns exit 3. A no-op close is provided by the new fake-port adapter;
  the old probe's missing `close()` is not treated as a production defect.
- The implementation provides the requested explicit `--expect-usb` check and
  distinguishes missing/mismatched identity from generic metadata-only use.

The existing transport suite passed **124 tests, zero skips, OK (68.821 s)**.
Production B2 verify accepts S1, qualified false, refusal null, 71 B2 / 105 B1
pins. Manifest remains
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
These are focused checks, not another whole-suite clean-tree proof.

## P2 — a known provenance tool error still spends the entire exposure

`host/transport_rig.py:1458–1463,1489–1502,1516–1522`.
`attempt("provenance", provenance)` converts an exception to null and appends
an entry error, but `_device_steps` does not stop before opening the port. The
only entry-wide downgrade occurs in the stdout brief after the run returns.

The probe makes provenance raise an OSError from the start, with a clean fake
port. Observed result:

| fact | result |
|---|---|
| invocation provenance | null |
| port writes | 303: nonce plus all 302 source frames |
| exit | 0 |
| stdout | entry export error present; export_complete false |
| run.json | error null; completed_exposure true; export_complete true |
| run-level provenance | unavailable with the injected error |

The missing provenance is not concealed everywhere: it is visibly unavailable
in the nested run record and flagged in stdout. The defect is proceeding with
known tool failure despite plan §5's stop-on-tool-error contract, plus leaving
entry-wide status only on stdout. Under the real defaults this can spend the
entire exposure after failure is already known.

Required correction: treat mandatory invocation/provenance construction errors
as terminal before opening or writing the port, independently of whether the
JSON serialization itself succeeded. Persist the entry-level terminal status
and error/export state in a separate acquisition summary or an explicitly
integrated finalization step; stdout must not be its only record. Preserve
primary errors and partial evidence when failure occurs later. Do not turn
expected counter unavailability or explicitly permitted generic identity
metadata into unrelated fatal errors.

Add a real CLI test with provenance failing before acquisition: no opener calls,
no nonce or source writes, a named nonzero result, and a durable diagnostic when
the destination remains writable. Add finalization-fault coverage ensuring that
stdout and the archived entry status agree. Keep all original positive controls.

## P3 — close attempts are reported as successful closes

`host/transport_rig.py:1468–1478` builds `ports_closed` from every opened port,
even if its close call raises. A separate probe injects a real close exception
on an otherwise valid fake acquisition. The brief has both
`ports_closed: ["/dev/FAKE"]` and `close_errors: ["... synthetic close failure"]`,
still exit 0. The close error is absent from the acquisition files.

Report attempted and successful closes separately and archive the error in the
entry-level finalization record. Preserve the run's observed traffic facts; a
cleanup failure must not retroactively invent lost frames. The existing
before-fix probe's missing close method is a fixture limitation, whereas this
probe supplies a close implementation that intentionally raises.

## The loss can be recovered by retry; it cannot be erased by CRC

The supplied conversational answer begins too broadly with "neither meaning can
work" and later incorrectly implies that adding retry is necessary. The pinned
instrument already has bounded recovery:

- `zynq_psoracle/host/l5_notary.py:62–75`: frame construction and parsing use
  CRC32 over the body. This detects corruption; it does not reconstruct deleted
  bytes.
- `zynq_psoracle/host/l6_audit_pull.py:250–281`: a failed AUDIT chunk attempt is
  recorded, bounded by retry limits, and followed by another AUDITGET.
- `zynq_psoracle/host/l6_console.py:138–168,323–357`: RECGET recovery and global
  CRC ledger/budget handling already exist. rel-v4 also has IDENT, SIGNREQ and
  TERM transaction recovery.
- `host/b1_session.py:391–392`: production sessions instantiate that console
  using the plan's protocol and CRC budget.

Using these existing mechanisms needs no new pinned change. Changing their
limits, algorithms or accounting would be a change requiring its own review.
Successful retries preserve a logical record while the original damaged
attempt remains in the ledger and consumes the applicable CRC budget. Recovery
is conditional on retries, timeout and global budget remaining; it is not a
guarantee that any damaged session will pass.

The rig has a different purpose: measuring byte-exact first delivery of the
known transmitted traffic. Its observed loss remains a loss even if a separate
protocol could recover it. Do not relabel the old rig acquisition as recovered;
it performed no such recovery. One damaged expected source frame and a damaged
host echo are also different units from a session's inbound CRC counter.

The 1 / 2,257,741 received-byte observation is an empirical ratio for that TX
exposure, not an established stationary fault rate. The TX run was declared as
20 repetitions, below the registered 200-repetition/3,600-second bound. A later
clean run neither deletes this observation nor by itself establishes stability.
B1Q attempts 1 and 3 were LOST; describing three B1Q attempts as CRC-budget
losses is inaccurate.

This correction does not authorize a B2Q ruling or lift the stop-loss. Existing
recovery removes the premise that a new retry implementation must precede any
future session; deciding whether this transport is acceptable remains separate.

## Push scope and the xilinx documentation change

Fabricmap: defer blanket approval of the nine local commits until the P2 above
is closed. Original physical acquisitions retain their original tool digest;
none was rewritten or fully adjudicated in this review. The physical README's
claim that deletions exclude line noise should also be narrowed to the observed
byte deletions with cause unresolved; the deletion shape alone does not isolate
a mechanism.

`/home/test/xilinx` commit `20760a6` changes only CLAUDE.md. Correcting the
reported supply connection and withdrawing the earlier board-3.3-V attribution
is appropriate. However, "so this is not a supply brownout" is stronger than the
wiring observation establishes. Replace it with, for example:

> The module is host-USB-powered; the earlier board-3.3-V brownout attribution
> is unsupported. The reset-time dropout was observed; its cause is unresolved.

Then the documentation correction can be reviewed for push independently of
transport software acceptance. This review does not modify that repository or
execute either push. Review artifacts may be archived as received before fixes.
