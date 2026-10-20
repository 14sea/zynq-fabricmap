# B4 — the protocol revision v0.2.0, documents unit (2026-10-20): the design record

**What this unit is.** The documents-only unit the owner authorised on 2026-10-20 after the PASS of the scope proposal v0.2 ("a
complete host-only documents unit, not an implementation, an exploration, a gate or a silicon acceptance"): the branch `b4-protocol-v2`
from `d19cc2f`, one local commit, holding `docs/b4_architecture.md` DRAFT v0.2.0, `docs/b4_archive_reverification.md`, this directory,
and the two pending document items of the executed gate unit (`evidence/b4/unit_gate1_execution_2026_10_20/`: the timing P3 folded into
its README §2, the owner's review archived with a source note). **No program, hypothesis, import table, thresholds table, archive, seed,
receipt or verdict changed; nothing run** (no test, model, replay, verifier, mechanics batch, exploration, gate or seed derivation); no
push, no merge, no board. v0.2.0 is a protocol design version to be implemented by a separate tool unit; it is not a version that has
passed any gate, and the owner's review of these documents is not a tool acceptance.

## 1. What changed in the documents, and where

| file | change |
|---|---|
| `docs/b4_architecture.md` | header → DRAFT v0.2.0 (revised 2026-10-20); the revision note v0.2.0 (the gate-1 result and its correct statement, the seven choices, the consequences for the existing tools); **§7.1** task-v0.2 (T-i target, H access contract, the task digest, setup and persistence, failure records, isolation, cost expectation, replay, non-triviality from the R arm's base trace, the holdout's two axes, the disclosure); **§9 K9 row** gains (b′) beside (b); **§9.2** labels consumed / reserved, the anchor unchanged, the identity not in the anchor; **§9.3 clause 6** conditional applicability and the two records; **§9.4** the go / no-go policy; **§9.5** the protocol identity; §12, §13 (2b-4 delivered and executed; the v0.2.0 rows), §14. Every pinned text of `b4_thresholds.PINS` is kept verbatim in its row (checked by reading the document, not by running the test) |
| `docs/b4_archive_reverification.md` | new: the two named archives (code HEAD, archive commit, inputs, external inputs, registry at start versus at the archive commit), the facts verified read-only, the eight-step procedure with stops, what it does not do, the coupling note |
| `evidence/b4/unit_gate1_execution_2026_10_20/README.md` | §2: the 31.7 min (batch + judgement) and 49.6 min (with the two verifications) figures separated (the owner's P3 on `d19cc2f`); §8: the owner's review archived |
| `evidence/b4/unit_gate1_execution_2026_10_20/owner_review_d19cc2f_2026_10_20/` | the owner's review record copied byte for byte, SHA256SUMS verified, `SOURCE.txt` |

## 2. The consequences for the existing tools, disclosed

- `b4/tests/test_b4_thresholds.py::test_the_document_version_is_the_table_s` asserts the architecture's first line reads `(DRAFT v0.1.16,`;
  at this commit it reads `(DRAFT v0.2.0,` and that assertion **fails by design** — the document-version coupling of the gate execution
  plan §6 / the 2c skeleton §12 item 5, resolved by the identity of §9.5 when implemented. Not run here; not hidden.
- Every other pinned text of `PINS` is still in its row (36 of 36, by a read of the document).
- `b4_sim.ROOT_INPUTS` records `docs/b4_architecture.md`'s digest in each manifest without pinning it; the verifiers compare recorded
  values. No archive's verification reads the document; a future batch would record the new digest.
- The thresholds table of record stays "section 9 (v0.1.16)" with `b4-gate-1` / `b4-sim-3` as its labels until the tool unit.

## 3. Sources (how each was obtained; digests below)

| item | file(s) here | origin |
|---|---|---|
| the scope draft v0.1 (HOLD) | `scope_draft_v0.1.md` | `build/wip/b4_protocol_revision_scope_draft_2026_10_20.md`, written 2026-10-20 in the session; copied unchanged |
| the owner's HOLD on v0.1 (R1–R6, D1–D3) | `owner_review_v0.1_HOLD/` | the owner's record under `build/wip/owner_review_b4_protocol_revision_scope_2026_10_20/`; SHA256SUMS verified; `SOURCE.txt` |
| the scope draft v0.2 (PASS as scope) | `scope_draft_v0.2.md` | `build/wip/b4_protocol_revision_scope_draft_v2_2026_10_20.md`; copied unchanged |
| the owner's PASS and seven binding choices on v0.2 | `owner_ruling_v0.2_PASS/` | the owner's record under `build/wip/owner_review_b4_protocol_revision_v2_2026_10_20/`; SHA256SUMS verified; `SOURCE.txt`; `review_metadata.json` names the reviewed scope's sha256 `e955a607…` = `scope_draft_v0.2.md`'s |
| the read-only aggregation (scripts, outputs, git checks) | `readonly_record/` | `build/wip/b4_protocol_revision_readonly_2026_10_20/`, kept at the owner's D3; copied unchanged, not re-run; the owner's `provided_readonly_records_sha256` agree with the copies: True |

The owner's decisions were relayed by the user as summaries in the session; the files above are the records the owner named as
complete, and the summaries are not reproduced here as verbatim originals.

## 4. Data influence and choice rationale (the disclosure the owner's choice 1 requires)

| observation | source | what it drove | status of the inference |
|---|---|---|---|
| `b4-gate-1`: Ω − R mean negative at all ten budgets; every arm's median 41 at B = 256; best observed 51 / 64; holdout ≈ 40 / 80 for every arm | `readonly_record/read_curves.out.txt`; the owner's `readonly_aggregate.json` | the **motivation** for a new task contract (§7.1) | descriptive; **does not** establish task, grouping, operator or cartographer as the cause (the owner's R1); nothing in §7.1 is set from these values |
| `b4-sim-3`: `ff_srval` median 0.427; the owner's configuration-only bound 0.5 | the sim-3 record; the owner's audit of 2026-10-19 | the direction of K9 (b′) | the bound is a deduction from the model (`sr_tied_low_when_not_driven`); the old (b) judged correctly by its own definition |
| `b4-gate-1`: tied-low pairs covered 0 (38 400 pairs); driven + sync + FF 0.575; driven-only per-seed median 0.8125; `sr_kind` exactly 0.5 in 103 seeds | `readonly_record/read_k9.out.txt`, `read_k9_k7_extra.out.txt` | the wording of (b′) as a conditional estimand (§9.3 clause 6); `sr_kind` included | post hoc; the 0.575 ≈ 1 − (3/4)³ explanation is a mechanism note under stated premises, not a validation; the 0.8125 is a description of the old sample under the new definition, **not** a basis or a validation of v0.2.0 |
| the generator's "reachability NOT guaranteed"; B2's D2 | `b4_landscape.py`; `docs/b2_architecture.md` §3 | the **form** of the planted target | a design difference that existed before any data; the owner: not equivalent to B2 D2 |
| `PublicTask` carries the seed; the engine's context carries it | `b4_execution.py`, `b4_engine.py` (read) | the H boundary (§7.1) | a fact of the code |
| the scorer gives None no score; latch x5FF read None | `b4_landscape.py`, the hypothesis (read) | T-i and the latch-region disclosure | a fact of the code and the model |
| the archive commits equal code HEAD + archive; the verifiers read recorded heads only; six external inputs present | git and file reads (`readonly_record/r5_git_readonly_checks.txt`) | the re-verification procedure | facts |
| the two scope drafts and the owner's reviews | this directory | every choice of v0.2.0 | the owner's rulings are the authority for the choices; the drafts are their motivation |

**What none of this is:** a validation of v0.2.0, a cause of v0.1.16's FAIL, or a prediction of `b4-sim-4` or `b4-gate-2`.

## 5. Not authorised and not done

No tool unit; no derivation of `b4-sim-4` or `b4-gate-2` (reserved names); no exploration, gate, test, model, replay, verifier or
mechanics batch; no change to `b4/`, the hypothesis, `b4/IMPORT.json`, `b4/host/b4_thresholds.py`, `docs/b4_gate_execution_plan.md`
(the historical plan of `b4-gate-1`) or the 2c skeleton; no push, merge, RTL, provisioning, routing or board work. R0 (stopping this
research line) remains a policy option the owner may take at any time.

## 6. Files and digests (sha256; `README.md` excluded)

| file | sha256 |
|---|---|
| `owner_review_v0.1_HOLD/README.md` | `b58af3485dc15f31ff5083e8ed58a5bb6d51a5d6403cc6dce1ce7ee7233fdb35` |
| `owner_review_v0.1_HOLD/SHA256SUMS` | `1f24a41c39ff1f0d919761e25eef75a9274987d8fd19af6830b400119dd5d196` |
| `owner_review_v0.1_HOLD/SOURCE.txt` | `e10a95d405dcd0da56f3dbafd7f56d62233e2c74d48d6b75eadeafa85a9e1d2f` |
| `owner_review_v0.1_HOLD/readonly_aggregate.json` | `29c7f74a7b6cb426b7c973f1fa8a54a602be65d87ab5a854ce3a3dc18a93a27b` |
| `owner_review_v0.1_HOLD/review_metadata.json` | `cf7ab4da31633ad09d9d66650f3e87196eb8d5b4a8d22a25d36bdbaec94ab4cd` |
| `owner_review_v0.1_HOLD/reviewed_scope.md` | `7d0602ad34644c24900eecd75c85b6db69633ddf141824f20cbda2a1c27eac92` |
| `owner_ruling_v0.2_PASS/README.md` | `3fbbe2c44c9cb40afc8454b29948d26791805c5fef32c9ed0d9ad8662509bedc` |
| `owner_ruling_v0.2_PASS/SHA256SUMS` | `be0cc7ba2d9faf6bfdf8ef56ba4b67d1b026bfad49395b28fede6189fdc78d9b` |
| `owner_ruling_v0.2_PASS/SOURCE.txt` | `e10a95d405dcd0da56f3dbafd7f56d62233e2c74d48d6b75eadeafa85a9e1d2f` |
| `owner_ruling_v0.2_PASS/review_metadata.json` | `ef70ca886592109faa381358770e2a23b6e4635b60d1335be31d986cd57635d9` |
| `owner_ruling_v0.2_PASS/reviewed_scope_v2.md` | `e955a6074deca6f2c101bbc160ce508c8edf931f61596b6cebe2670fff003318` |
| `readonly_record/README.md` | `55dbfa13a19af97dd9be5f3e8ea85fcb7557eca5eaad4a490983083b1501dd87` |
| `readonly_record/SOURCE.txt` | `391559fc936f565aa2f5f5f0c600582f4ab29d461f3e132cab15dc51321118bc` |
| `readonly_record/r5_git_readonly_checks.txt` | `77a4035da5fe0fa161921db771713c2b57e5246b64c7e2f20074c8ac23ca3f9b` |
| `readonly_record/read_curves.out.txt` | `5f43d6641a7d9186d2203796fdf80a5b7e93003dacceb21a281bfad42ef89297` |
| `readonly_record/read_curves.py` | `d45daea3501df8cb20d749080a87ba549b621d04064d4f5d921796699981309b` |
| `readonly_record/read_k9.out.txt` | `118d6898fcf6e51a15781ac0708863532c1567f1d9f2b2fdfa3cf1eadf2a9797` |
| `readonly_record/read_k9.py` | `098fa05c3ee825459314b14690a247f0527195951ed46f963b2e70c2ff446e64` |
| `readonly_record/read_k9_k7_extra.out.txt` | `f155c7aecda047b48fa52f7323f107c4e48dbe4938d6259cacc4a6cb848f1fae` |
| `readonly_record/read_k9_k7_extra.py` | `d21716354a2ac93e72a9ba62af2b8f039068885dbb1b01416532ddbea01408b3` |
| `scope_draft_v0.1.md` | `7d0602ad34644c24900eecd75c85b6db69633ddf141824f20cbda2a1c27eac92` |
| `scope_draft_v0.2.md` | `e955a6074deca6f2c101bbc160ce508c8edf931f61596b6cebe2670fff003318` |
