# Review — B2 preregistration draft v0.3, round 2

Reviewed `b2-lifecycle-2` at `800899e`.  Read-only review: no plan, pin table, manifest,
freeze, ruling, push, port or board action.

## Result: HOLD — prior findings closed; one P2 and two P3 corrections remain

The three P2 findings and P3 wording issue from the first review are closed.  The built image
and evidence are accurately named; `init` emits an accurate note in both image-present and
image-absent cases; the targeted fresh-process test passes; post-S1 and final S3 proofs are now
required in the correct places; all four old manifest identities are named; and the
StageCoverage claim is properly limited to the two summary-guard removal controls.

### P2 — step 8 combines four separately controlled actions

Section 8a says “each step [is] a separately authorised transition,” but numbered step 8
contains all of these:

1. issue the B2Q ruling pair;
2. run the board B2Q session;
3. apply the S2 qualification transition; and
4. run and archive the S2 clean-tree proof.

These actions do not share one permission boundary.  A ruling pair authorizes a particular
session; producing a PASS does not itself authorize the manifest transition; and S2 still needs
its own proof before S3.  Split them into distinct numbered steps.  Keep the post-S1 proof before
the ruling pair and the final S3 proof before B2 rulings.

### P3-1 — `fa0271e` is paired with a manifest produced later

The lifecycle-1 table labels S0 as `fa0271e` but gives manifest `86393ed7…`.
`manifests/b2_manifest.json` at `fa0271e` hashes to `af271747…`; `86393ed7…` first appears at
`01acb5f` after the pre-freeze corrections and is the final S0 identity that S1 consumed.
Label the row as the final pre-freeze S0 (`01acb5f`, later pushed at `9429088`), or record both
the initial and final S0 identities explicitly.

### P3-2 — the draft no longer changes exactly three things

The status paragraph still says v0.3 changes “exactly three things.”  This revision now also
changes the image pin from “not built” to the existing binary and adds the accurate
image-record-note contract implemented in `b2_manifest.init`.  Add that as a fourth change or
remove the exact count.

After these text-only corrections, rerun the v0.3 consistency probe and present the final draft
hash.  Do not regenerate `plan.json` until the draft is accepted.

No authorization for plan generation, pin regeneration, S0/S1, a ruling, push or board access
is given by this review.
