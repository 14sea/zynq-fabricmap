# First silicon B2Q: archive acceptance and S2 decision

Reviewed evidence commit: `9fb9511`.
Evidence: `evidence/b2/b2q_17A6_2026-09-14-01/`, plus the committed principal
boundary record for that attempt. The tree was clean and ahead one at review start.

**Decision: accept the archived B2Q PASS. Claude may push 9fb9511. Authorize
host-only S2 qualify from this evidence using the production re-adjudicator.**
This is a new authorization for the state transition; the spent session ruling
pair did not itself authorize S2.

Claude may archive this review and `evidence/b2/review_b2q_2026_09_14/` in one
additional commit and include it with the evidence push (two commits in that case).
The S2 transition and its test report are separate local work to report back with
the actual resulting manifest hash. No S3 pinning or B2 board session is authorized
by this review.

## Independently verified

The production re-adjudicator reconstructed the session verdict, rate and policy
from the archived evidence, and its entire result equals adjudication.json:
PASS, no findings, no kills, binding_checked=true. It validates the actual audit
streams and replays the 18 search/holdout records from served readouts; 20 records
are scored and audited, 160 audit chunks are archived, and the nonce chain is 21.
The epoch closes COMPLETED / budget at seq 20. The two baselines, restore, and
unsigned control close as recorded. No pooled B2 primary is claimed.

The current S1 manifest is byte-identical to manifest_at_run.json:
`8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.
Production verification rechecked the image bytes, B1 lineage, frozen inputs,
and 71 B2 / 105 B1 pins. The final summary closes against the log and ruling
archives, and the exporter seal is included in re-adjudication.

Both archived ruling byte digests exactly match the pair issued in this conversation:

- Whole-of-run: `24e732d71c679ba86188408b4da8f0619c69dd8119b7512d887663ae2e17d1b0`.
- Provisioning: `c56f9401d829b8b52f4d695b3f0d758bbc505b86f2a126f973b12572e51a552a`.

The local consumed markers record PASS for both. The committed boundary hashes
to `c8e741b19cabc85c994af00c9502fac361ff0da80176d8e2a7d3242fe3b5bb39`, matching the
record observed at ruling issue. Its recorded checks validate at the archived
session time; it was about 693 seconds old at the first frame, within six hours.
This is a historical validation, not a new principal-boundary test.

Independent parsing of console.log gives 543 CRC-valid frames, exactly matching
the expected per-type counts, plus two CRC failures: SIGNREQ seq 1 and REC seq 1.
Each failed frame has exactly the same body as its subsequent valid retransmission;
only the CRC field differs. IDENT enables both forced controls, matching the
firmware's seq-1 control paths. The timeline records two drops, no bad frames and
no fragments. There are no observed non-control CRC drops in this archive.

The host CRC budget remains 3. The board summary's zero CRC count concerns its
receive direction; it is not the host's CRC ledger. Likewise, summary's zero
transport_rereads does not mean there were no protocol recoveries: the timeline
contains the expected SIGNGET and RECGET for the two controls.

The summary records successful provisioning, matching IDCODE, the pinned carrier
and image loads, FCLK0 50 MHz, and resolved console ttyUSB4. Physical power cycling
and J7 wiring remain operator observations; this offline review did not inspect
the live board or open any device.

## S2 preview and authorized procedure

The measured all-self-reporting rate is **2976.9824011102987/h**, reproduced by
the production rate calculation. The reported session span is 24.243723545 s and
coefficient of variation 0.018461536. Calibration is derived at S2 from this
measurement, not from the earlier modelled or planning rates.

An in-memory production qualify followed by fresh-process verification succeeded
at S2, qualified=true, refusal=null. Exactly five top-level fields change:
qualification, qualified, calibration, status, history. The qualification record
binds the required 11-file set; all 15 submitted session files remain archived.
The plan stays null. Calibration yields three sessions, at most four pairs each;
the derived future split is 4+4+1 with 10,824 records. This split was inspected but
not pinned or authorized for execution.

The current manifest CLI does not supply a re-adjudicator on qualify/verify.
Use the existing public API with the real hook; do not change pinned code to make
the CLI convenient. The relevant sequence is:

```python
import json
from pathlib import Path
import b2_manifest as bm
import b2_runner as rn

m = json.loads(bm.MANIFEST.read_text())
assert bm.sha256_file(bm.MANIFEST) == "8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35"
s2 = bm.qualify(m, Path("evidence/b2/b2q_17A6_2026-09-14-01"),
                readjudicate=rn.readjudicator(m))
assert sorted(k for k in s2 if s2[k] != m[k]) == [
    "calibration", "history", "qualification", "qualified", "status"]
assert s2["plan"] is None
bm.verify(s2, readjudicate=rn.readjudicator(s2))
bm.MANIFEST.write_text(bm.render(s2))
```

Run from the repository root with `host` on Python's import path. Re-read the
written manifest in a fresh Python process and call verify with the same production
hook. Record the actual file hash, commit the S2 transition, and then run the
whole-suite `host/b2_test_report.py` on the clean committed S2 tree. Preserve its
report and require clean_tree_proof=true before presenting S2 as tested.
Archive review artifacts before that test so they do not make the tree dirty.

Do not regenerate pins, alter frozen inputs or rewrite the session evidence to
accommodate a failure. If qualification or testing refuses, preserve the result
and return for review. The preview digest is timestamp-dependent and is not a
binding for a future ruling. No full-suite S2 proof was generated in this review.

## Scope retained

The single-attempt transport exception is spent. PASS does not establish link
stability, identify the byte-deletion cause, or lift the standing transport
stop-loss. A future B2 mapping session still requires the appropriate S3 manifest,
new boundary, separate ruling pair and explicit transport disposition.

This review changed neither the production manifest nor any archived session
bytes. It did not commit, push, provision, access a key, open a port or run the board.
