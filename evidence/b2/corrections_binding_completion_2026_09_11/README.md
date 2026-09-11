# The offline binding's two P2s — corrected, 2026-09-11

The owner's binding-completion review (`docs/b2_binding_completion_review_2026_09_11.md`, against
`4d135be`) accepted the export seal, the 11-file record and the deadline comparison, and left two
P2 gaps. Both are corrected. `acceptance.json` is `acceptance.py`'s output — the review's own
cases driven through the production functions, each with a zero-finding positive control first.

| the review's case | before | now |
|---|---|---|
| wrong IDENT `carrier_sha256` | PASS, `binding_checked: true` | `IDENT carrier_sha256: … != …` |
| wrong IDENT `universe_sha256` | PASS | `IDENT universe_sha256: … != …` |
| removed `l6.inputs` | PASS | `the run log's l6 carries no inputs block` |
| wrong manifest digest inside `l6.inputs` | PASS | `inputs: the log's b2_manifest_sha256 is …` |
| B2Q plan's `inputs` member | absent, so the check was silently skipped | present and compared |
| either ruling archive replaced by `not JSON` | PASS | `no readable ruling archive at …` |
| an archive naming another master seed / image / session / board / ruling text | PASS | each named |
| `summary.json` replaced by `not JSON` | PASS | `summary.json is not readable JSON` |
| `summary.json` with a different outcome | not checked | `is not the adjudication's 'PASS'` |
| the record builder over an unparseable archive | built an 11-file record | **REFUSED** at acceptance |

## How each was corrected

- **P2-1.** `expected_identity` is now the ONE `app_identity` 1.5.0 contract, used by the online
  check before the board's identity is acknowledged AND by `binding_findings` when the evidence
  is re-adjudicated later — carrier digest, carrier variant and universe digest included, and the
  binding block declares them too. `qualification_session_plan` builds its `inputs` contract, the
  preflight's producer/reconstructor consistency list compares `inputs`, and `binding_findings`
  now **requires** the inputs contract: a missing expectation is a finding, never a pass.
- **P2-2.** `archived_ruling_findings` decodes both archives through the instrument's own strict
  envelope reader and rebinds them — text, board, session, image, preregistration, manifest, and
  the whole-of-run master seed — and requires the two to name the same board. An archive is INERT:
  it is read, never claimed, never consumed, and nothing here reactivates it.
  `b2_manifest.reconstruct_qualification_record` refuses an archive it cannot parse, so an invalid
  declaration is caught at acceptance instead of having its digest preserved.
  `b2_manifest.summary_findings` cross-checks the final summary — outcome, token, the archived
  whole-of-run ruling and the provisioning ruling's byte digest — at the **post-finalisation
  lifecycle boundary**, because `b1_session.run` persists `summary.json` after the adjudication
  callback: requiring it inside the callback would create a positive path that cannot exist.

## Why the review's own script now exits non-zero

`probe_binding_completion.py` asserts `transport_control == PASS` — a relabelled B1Q transcript
whose IDENT does not satisfy the B2 identity contract, which is exactly what the correction now
holds it to — and it stops earlier still at `reconstruct_qualification_record`, which refuses the
unparseable archive its own case supplies. Its per-case results before that point all HOLD with
named findings.

## Still not done

**There is still no modelled B2/B2Q session.** The complete offline S1 → B2Q → S2 → S3 →
fresh-process verification remains the next deliverable, and this runner has still never produced
a PASS. Every positive control here is a component driven directly or the archived B1/B1Q
transport with the B2 replay doubled.

## Tests

46 runner tests (was 32), 13 lifecycle tests, **B2/B3 377, zero skips**. Reverting only
`host/b2_runner.py` and `host/b2_manifest.py` fails or errors 15 cases across those two suites.
