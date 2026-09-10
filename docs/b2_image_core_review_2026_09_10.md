# B2 image stages 1, 2a and 2b — offline review, 2026-09-10

Reviewed HEAD: `aef237d`, three commits ahead of local `origin/main = b951b80`:
`861649a` (search core), `c65f1e0` (record/commitment), `aef237d` (wire/import guards).
**The completed core stages pass review and may proceed to application integration.**
No blocking defect was found in the reviewed nominal search or serialization code.
One nonblocking guard defect and documentation/evidence clarifications are listed below;
complete those before presenting the full §7 image package. This is not a completed-image
compatibility review or a board authorization.

## Search core and C/Python correspondence

The C implementation has the intended 4+8 population/offspring sizes, truncation by
fitness then birth index, both mutation operators, sorted move bits, partial-generation
selection at the budget, and a separately observed champion holdout. F1 is calculated
from the tables passed to `b2_search_observe()` and `b2_search_champion_observe()`.
The C search unit contains no fabric-model evaluator. The operator's column view uses
INIT indices; LUT indices are used separately to derive the landscape's universe mask.

The reviewer compiled the native host twin with `-Wall -Wextra -Werror -pedantic` and
UBSan (`-fsanitize=undefined -fno-sanitize-recover=all`). An additional driver compared
all **10,800 candidate genomes**, parent birth indices, moves, fitness values and record
blocks for the nine pairs and both arms at budget 600. Champion genome and holdout also
matched. The nine deltas are `[2,5,6,3,4,6,1,-2,5]`.

Ten additional runs cover both arms at budgets 1, 8, 9, 31 and 600 with deliberately
perturbed readouts: a train-column bit is flipped and an otherwise unmapped marker bit
keeps the test readouts distinguishable. The opening baseline remains zero. The Python
reference is supplied the same observations through a fixture fabric, rather than its
normal additive `ModelFabric.toggle`. All candidate genomes, fitness values, search
blocks and champion holdout blocks match. This extends the evidence beyond the ideal
model's readout path. No sanitizer diagnostic was observed in these runs.

The added Python logging fields do not change the frozen prediction: a fresh complete
prediction generation remains byte-identical to the committed document. The submitted
suite also exercises the RNG, seed exclusion, mask/target, both vector sets, generation
boundaries, population selection and the final champion. The evidence currently concerns
a **native C unit**. ARM compilation, linking and silicon behavior remain later stages.

## Record commitment and wire scope

The C `search` JSON and Python rendering agree byte for byte in the tested trajectories.
`state_sha256` commits the documented arm, seeds, budget, evaluation/generation counters,
best fitness and selected population's fitness, birth indices and genomes. It is a
commitment to that defined projection, not a hash of every byte of the C search structure.
The later adjudicator still needs replay of the observations, proposed children and
selection; the digest alone is not that replay.

The wire unit's changes from B1 are confined to the B2 identity fields and the replacement
of `carto` with `search`; framing and common evidence serialization retain the B1 path.
The fixture emits compact sorted JSON (892-byte IDENT and 2,097-byte REC payloads).
Those common envelopes validate under `b1_records`.

**That validator does not validate B2 extension semantics.** The instrument's minor-version
policy ignores unknown fields. In the review probe, deleting `REC.search` still validates;
so does an identity with an invalid map digest, zero budget and an impossible pair slice.
The returned known-field dictionaries omit those extensions. This is expected legacy
behavior, not a new defect in B1. Keep the claim limited to common-envelope compatibility.
`b2_records` and the real B2 adjudicator must require and validate the B2 fields and their
cross-record bindings. They are explicitly unfinished in this submission.

The wire fixture also uses fixed artificial evidence values; it is not a coherent B2
session replay. The existing UNSCORED test stops the host twin driver at evaluation 20;
it does not run an application epoch, restoration or TERM. The forthcoming real-application
harness must cover that path, including rejection at generation boundaries and holdout.

## Guards and the remaining nonblocking defect

**P3 — comment stripping can remove string data.** `host/gen_b2_data.py:strip_comments`
uses regular expressions without tracking C string literals. For example:

```c
static const char *example = "/* certificate */";
```

becomes `static const char *example = "";`, so the declared data-only forbidden-token
scan misses the forbidden token inside the actual string. The generator and source tests
share this helper. No such forbidden string was found in the submitted sources, and the
mandatory binary scan would independently catch this literal once an image exists; this
does not block continuing the core implementation. Before the full image package, make
comment removal aware of string/character literals and escapes. Cover comments, quoted
comment markers and literal data with negative fixtures, preserving the distinction
between prose and data. Do not report the source scan as a complete binary leakage test.

The current generated header exactly matches the generator and both map digests; all 292
compiled LUT/INIT relations and the excluded-seed values match their committed sources.
The six verbatim imports were independently compared with `git show` of instrument commit
`689dde1dad374536c625bbe2b05986ee89eb4c94`, not just with their local declared hashes.
Both derived wire files match their recorded base and derived hashes.

Four BSP scaffold files (the linker script and three BSP headers) equal the B1 copies but
are not yet listed in B2's import table. Account for them when completing the cross-build
provenance and pin set. The full build evidence must cover actual linked sources, headers,
toolchain objects and image bytes as required by §7.

Two small documentation corrections should accompany integration: architecture §6 calls
the commitment `search_sha256`, while the implemented field is `state_sha256`; preregistration
§2 describes only an INIT-index column table, while the generated header also contains
LUT indices for mask derivation. Describe that separation explicitly. The operator still
uses INIT indices only; these numeric indices are distinct from forbidden LUT site keys.

## Test result and next checkpoint

The independent B2/B3 run is **132 tests, OK, skipped=2, 278.743 seconds**: 130 passed;
the two skipped tests are the binary forbidden-token and required-identity-string scans,
because no B2 image exists. The submitted count of 123 is not the complete test count
for this checkout. Of the twelve leakage tests, ten run and two await the binary.

The next checkpoint remains the complete §7 package: `b2_app.c`, actual identity-page and
session ordering, termination on non-SCORED outcomes, the cross-build and two-clean-build
evidence, real-application off-board harness, and B2 records/runner/adjudicator/pins.
Then review compatibility before freeze and B2Q. Existing ruling and transport stop-loss
requirements remain in effect. This review performs no board contact, image build, commit
or push; the sanitizer executable is host tooling only.

Artifacts are in `evidence/b2/review_core_2026_09_10/`: `verify_core.py`, its output and
diagnostic log, the focused test log, and import/header/source/hash checks. B1's 105 pins
verify and its manifest remains unchanged. The instrument checkout remains clean.
