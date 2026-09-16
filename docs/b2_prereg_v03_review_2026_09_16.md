# Review — B2 preregistration draft v0.3

Reviewed `b2-lifecycle-2` at `e20705c`.  Read-only review: no plan, pin table, manifest,
freeze, ruling, push, port or board action.

## Result: HOLD — three P2 corrections before regenerating the plan

The committed-plan stage rule is correctly stated, the prediction bytes are unchanged
(`a611b8e0…`), and the lifecycle-1 B2Q PASS/rate are explicitly excluded as inputs to lifecycle
2.  Three contradictions remain in the document that would be frozen.

### P2-1 — the image pin still says the image is not built

Section 2 says `B2 image | not built`, while §8a says the existing byte-identical image and
build evidence may be carried.  The binary exists at `firmware/b2/bsp/out/b2_app.bin`, is
114,708 bytes, and hashes to `d164cd1d…`; its build evidence exists and the current manifest
pins both.

The same stale statement is produced by `host/b2_manifest.py`: `init` starts with the note
`no B2 image exists yet` and does not replace the note when build evidence supplies an image.
Thus merely correcting the prereg text would still make lifecycle 2's new S0 contain a false
declaration.

Before repinning:

1. make the §2 image row state the built image, digest, size, ELF/build-evidence identity and
   the fact that lifecycle 2 re-hashes it at S0;
2. make `b2_manifest.init` emit an accurate note when build evidence names an existing image;
3. add a production-driven test that would fail if a populated image record again says no image
   exists.  This is another pinned-file edit and belongs before the one table regeneration.

### P2-2 — the lifecycle order omits the required post-freeze and final proofs

Section 8a currently orders a full-suite proof at S0, then S1 freeze, then directly B2Q.  The
accepted S1 boundary requires the actual S1 manifest hash to be followed by a clean-tree report;
lifecycle 1 did exactly that in `test_report_2026-09-13T053400Z.json`, whose artifact snapshot
is bound to S1 manifest `86997677…`.  A proof taken at S0 cannot prove the subsequently changed
manifest or frozen prereg bytes.

The containment decision also requires a new whole-suite clean-tree proof after the new S3,
before any B2 ruling pair.  Amend the sequence to include at least:

- a clean-tree proof bound to the actual frozen S1 manifest before the B2Q ruling pair; and
- a final clean-tree proof after S3 before B2 ruling pairs.

An S0 proof may remain as an additional transition check; it cannot replace either one.

### P2-3 — the lifecycle-1 binding identities are incomplete and one is mislabeled

The history writes `S1 freeze (68cde86d…)`.  That digest is the v0.2 preregistration, not the
S1 manifest to which the B2Q ruling and evidence were bound.  The actual transition was:

- S0 manifest `86393ed781cb25c971aeb7a4ea3bf485b5aba5a353ef94968b3128050d5b2da1`;
- preregistration `68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0`;
- S1 manifest `8699767744b8f7c1f68a49252acddd91af0e9d1732a0a772476fc0f257949b35`.

The non-input list then calls only the S2 and S3 hashes “the lifecycle-1 manifests.”  Name all
four lifecycle-1 manifest identities (S0–S3), label the prereg digest separately, and state that
none is an input to lifecycle 2.  This removes ambiguity around the exact old identity that the
B2Q PASS remains valid for historically.

## P3 — narrow the StageCoverage claim

The plan row says StageCoverage tests “each guard removed.”  The mutation control removes each
of the two new summary guards; status and plan-digest guards have negative cases but no
guard-removal mutation.  Change the phrase to “each new summary guard removed,” or add equivalent
load-bearing controls for the other guards.

No authorization for plan generation, pin regeneration, S0/S1, a ruling, push or board access
is given by this review.
