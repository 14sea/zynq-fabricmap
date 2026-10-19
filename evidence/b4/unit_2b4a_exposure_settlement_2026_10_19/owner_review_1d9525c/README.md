# Owner review — B4 exposure settlement (`8955647` + `1d9525c`)

Reviewed 2026-10-19. **HOLD: one P2 remains in the new receipt-to-record binding.** The historical reconstruction and effective exclusion content checked in this review agree. This is not a rejection of the chosen settlement policy or authorization to choose another label, anchor, threshold or seed set.

## P2 — coordinated wrong receipt counts pass the deep verifier

Locations: `b4/host/b4_seeds.py:364-375` (`receipt_reference_findings`), `b4/host/b4_sim_verify.py:212-216` (cross-file binding); callers include the seeds and manifest validators.

The reference validator requires a pinned path/digest and any nonnegative exact-int count. The deep verifier then requires the seeds and manifest counts to be equal. Neither binds that common count to the actual pooled list of the pinned receipt, which has 66 entries.

Independent reproduction, only the already exposed literal mechanics pair (7,11):

1. Build a clean hermetic input repository from the delivered snapshot and run one `b4-mech-1` fixture batch with explicit schedule; no seed derivation. Baseline completes and deep verification returns `{}`.
2. Change `seeds.json.exclusion.exposure_receipt.count` and the manifest's corresponding field together to **0**, **1**, or **67**. Leave the actual receipt, its pinned path and digest, all raw readouts and all other data unchanged.
3. Refresh the manifest's seeds-file digest, report identities and every file index using the existing `reindex` helper. Each case starts from the pristine baseline.
4. For all three cases, the seeds validator returns `[]`, manifest validator returns `[]`, and **deep verification returns `{}`**, despite the false count. Preserved archives are named in `probes_results.json`.

The restored archive also verifies cleanly, and a separate seeds-schema downgrade/removal of the receipt reference is correctly rejected by linkage. The finding is specifically a coordinated metadata lie accepted as consistent; it does not show that the normal producer omitted any of the 66 exclusion values.

Fix criterion: compare every current-schema receipt reference to the authoritative length of the pooled list of the hash-verified pinned receipt, rather than only to another record's count. Keep exact scalar typing, digest/path checks, legacy archive ingestion and fail-closed receipt loading. Avoid introducing an independently maintained unexplained `66` as a second source of authority. Add whole-archive negatives changing BOTH counts together, with all indexes refreshed, and assert a named count finding; pristine correct count remains clean. The existing helper restores the archive after each `findings()` call, so the delivered single-field tests are isolated, but they do not exercise this coordinated case. A targeted mutant removing the new authoritative-count check should fail for that reason.

This narrow fix is within the existing settlement scope. Preserve the delivered commits and receipt bytes. Do not rerun historical reconstruction to change the timestamp/digest merely to fix a reference check. Rerun the B4 suite and affected mutants after the fix, refresh IMPORT and archive the raw results; no full B1/B2/B3 proof or scientific exploration is needed.

## Checks completed

Historical seed-only reconstruction was independently repeated from the git blobs at `edfc93c`, importing historical derivation and PRNG code into a separate process. Only the two retired labels were derived. See `reconstruction_check.py`, JSON and stdout.

- Historical empty-registry base pool: **2,093** integers, digest agrees with the receipt.
- **V1–V9**: masters, pairs, every X/D control seed, and per-variant historical pool counts all agree.
- **22/22** preserved records agree, including source contents and exposed literals, not merely source count. Their recorded digests agree.
- Reconstructed union: **66** values; current pooled exclusion size **2,159**.
- All **93** preexisting exposure files are byte-identical to `82e863e`.
- IMPORT **49** entries, copied-base/function digests and listed repository/external sources agree. Protected B1/B2/B3 paths are unchanged; source/docs whitespace check passes.
- Original owner ruling is copied byte-for-byte.
- Independent selected mutant battery: **14/14 killed**, exit 0, 119 s, each Ran N > 0 / FAILED: M1, M3, M4, M35, M52, M57, M68–M75. This is a focused rerun, not an independent rerun of all 75. The author's full raw log separately has 75 unique killed rows with positive test counts and no bad markers.
- Independent full B4 suite: **254 tests, OK**, exit 0, 225.098 s. No production derivation reached the outer guard. Raw output: `tests.txt`; driver: `suite_driver.py`.

The suite and archive probes use mechanics fixture schedules. An outer suite guard forbids production-master derivation; the harness test classes also guard both derivation functions. Archive probes guard both functions. No b4-sim-3 or gate master/pairs were derived, no S=32 or S=200 batch was run, and no real evidence/b4/sim namespace was created.

## Coverage and remaining boundary

The reconstruction proves coverage of the stated committed-recipe envelope; it cannot recover deleted readouts or prove a complete historical execution inventory. The receipt and README explicitly leave uncommitted development versions outside that envelope. That limit remains permanent and is not converted into a claim that every possible historical exposure was excluded or that the new label guarantees unseen data. This review does not extend the envelope or authorize inventing missing histories.

Original evidence, wrong-count archives, scripts and raw independent results are retained. Real tracked worktree and refs are unchanged: b4-prework remains `1d9525c`, main `d5bf815`. Push, merge, exploration, formal gate, 2c/2d, full proof, procurement and board work remain unauthorised. Unit closure waits for the P2 repair.
