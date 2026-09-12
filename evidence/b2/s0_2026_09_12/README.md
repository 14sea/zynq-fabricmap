# S0 — the B2 manifest, derived from the tree and committed (2026-09-12)

> **The digests below are superseded.** The owner's S0 transition review found a P2 in the test
> this record describes under "One test had to change"; correcting it changed a pinned test, so
> the table and the manifest were regenerated. The manifest is still the same unfrozen S0 — the
> stage, the state fields, the image and the preregistration are unchanged — but its digest is now
> `848f56528b129939d4d6bfd8d016e455789d958af180033ed668de811a62d140` and the table's is
> `50cb6f5a1d141d18bd011938355f6f900e25dcb40c1e8f2a2aa2e647c8793116`. See
> `../corrections_s0_transition_2026_09_12/`. This record is kept as written.

The owner authorised **S0 only**: derive the manifest, verify it, commit locally, do not push.
**Not in this step: S1 freeze, any ruling, any board work.** The owner's instruction also fixed
what S0 must *not* do — it does not pin the preregistration's digest.

## What was produced

    python3 host/b2_pins.py --generate
    python3 host/b2_manifest.py init --image-evidence evidence/b2/build_evidence.json
    python3 host/b2_manifest.py verify            # -> verify.json

| | |
|---|---|
| manifest | `manifests/b2_manifest.json`, schema `b2_manifest` **0.2.5** |
| **manifest sha256** | **`af2717476a518f3fcb31d5c76599a17585367fdc421f9607b06aaca424924540`** |
| status | `S0 INIT — derived from the tree; not frozen; no qualification; no plan; NO BOARD RULING` |
| verify | `stage: S0`, `qualified: false`, `refusal: null` — every check ok (`verify.json`) |

### The state fields, as the owner specified them

| field | value |
|---|---|
| `prereg.sha256` | **`null`** |
| `prereg.frozen` | **`false`** |
| `image.board_ready` | **`false`** |
| `qualified` | **`false`** |
| `qualification` / `calibration` / `plan` | `null` |
| `history` | `[]` (no transition has happened) |

## What S0 pinned

| input | digest |
|---|---|
| instrument pin table `manifests/b2_instrument_pins.json` | `e848325308ee31cf479b733bd6bd93cde466991b86bb424a70c9ed81e2d8a232` — **71** files, re-verified together with **B1's 105** |
| B2Q plan `evidence/b2/b2q_plan.json` | `3d194d76e083fd4ba3ce3cf0458af65637120fcda6761be36598833dbc659216` |
| B2Q prediction `evidence/b2/b2q_prediction.json` | `2ada4d5dab7ed08f081aa55bb4b6f138688a326bb859ab5d63f58c16e67b58aa` |
| image `firmware/b2/bsp/out/b2_app.bin` | `d164cd1d5b30aa5eb91f230b1373be8dda60d219249924e280957b26348d85f5`, 114 708 bytes (ELF `7de96ed2…`) |
| build evidence `evidence/b2/build_evidence.json` | `ce58eaf3cc79db5687e8324e77ec7c814d181e497cbeb069587fb3b66f33af5b` |
| B1 manifest (lineage) | `38238271510536bda565ad1b8321dd04d75e78e1fe77ef94d2795bf9edfd4ba8`, carrier `d85daef4…`, variant `0x42310001` |
| map `maps/self_map.json` | canonical `c6a4b23e1871e188…`, file `b6607a9a4de4ec16…`; universe 292 addresses, `895baf85…` |
| gate | `evidence/b2/gate/recomputed_2026_09_10/gate_report.json` `997317fb…`, rules **v0.3** |
| board (from the validated lineage, not from a ruling) | **`17A6`**, `xc7z010clg400-1`, idcode `0x13722093`, role `verify` |
| B2 experiment | F1, budget **600**/arm, **9** pairs, master seed **716169644**, three archived seed sets excluded |
| B2Q experiment | budget **8**, **1** pair, master seed **505806527**, **20** records, planning bound 2 807/h (a planning rate, **not** a calibration) |

`verify()` re-derives all of it from live bytes: the image binary is opened, hashed and sized;
the B1 qualification chain is re-run fresh; the B2Q plan and prediction are **rebuilt from the
rule** and compared field for field, not merely hashed.

## The preregistration — computed, reported, NOT pinned

    sha256(docs/b2_preregistration.md) = 68cde86d3f3decaf9775beac94c59731ada486ebe246006e7243156c084db8e0

This is the digest of the corrected document (the §7 review's five corrections, `474a644`,
including the `mode_holdout` fix). It is recorded here **for the owner's S1 review** and is
deliberately **absent from the manifest**: `prereg.sha256` stays `null` until the owner runs
`freeze --prereg-sha256`, which is the act that also sets `image.board_ready`.

## S0 is derivation, not permission

`s0_is_not_permission.txt` — a fresh process, the committed manifest, the real runner:

    B2:  REFUSED — B2's preregistration is not frozen (S1): host-only until the owner freezes it
    B2Q: REFUSED — B2's preregistration is not frozen (S1): host-only until the owner freezes it

Both profiles refuse at the first gate after the board authority. A committed manifest moves
nothing.

## One test had to change, and one guard fired

* `tests/test_b2_runner.py::test_there_is_no_committed_b2_manifest_yet` asserted that **no** B2
  manifest was committed — with the note "this test must change". It did: the absent-manifest
  refusal now uses an explicitly non-existent path, and a new
  `test_the_committed_manifest_is_not_permission` reads the committed manifest, asserts the six
  S0 state fields above and requires the runner to refuse it.
* Editing that test made `verify` **refuse** (`pinned files changed: tests/test_b2_runner.py`)
  until the table was regenerated and the manifest re-derived — the pin table doing its job on
  the first day it guarded a committed manifest. The digests above are the post-regeneration ones.

## The suite

    python3 -m unittest discover -s tests -p 'test_b[23]*.py'   ->  Ran 440 tests ... OK

**440 tests, zero skips** (439 before, plus the new committed-manifest test). The six modules the
manifest touches — `test_b2_lifecycle`, `test_b2_pins`, `test_b2_runner`, `test_b2_e2e`,
`test_evidence_manifests`, `test_b2_test_report` — were run again on their own first: **127, OK**.
This is not a clean-tree proof; `host/b2_test_report.py` produces that after the freeze, and it
will now bind the pin table through the manifest rather than through the table's own bytes.

## What this does not do

No freeze, no `board_ready`, no ruling, no board. The B1Q transport stop-loss is still
unresolved and its root cause unattributed; §6 puts that before scheduling B2Q. The modelled
4 490.86/h remains a virtual-clock artefact and is not a calibration.

**Supersedes** the §7 submission's §1 statement that "there is no `manifests/b2_manifest.json`
in the tree" — true when submitted (`9fa8a7a`, over `619b22b`), and now superseded by this
commit rather than rewritten there.
