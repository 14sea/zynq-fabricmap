# B4 — re-verifying a historical archive under the tool that produced it (v1.0, documents only, 2026-10-20)

> **Standing.** The procedure by which an archived B4 batch or gate is re-verified **with the tool version that produced it**, written
> under the owner's ruling of 2026-10-20 on the protocol-revision scope v0.2 (the historical re-verification contract, and the
> correction of the scope draft's registry step). It is a procedure, not a run: nothing here was executed, no worktree was created,
> no verifier was run, and no archive, verdict, receipt or seed is changed by it. The invariant it serves is the owner's (the gate
> execution plan §6): **an old archive is judged under the table and the method it was produced with; a table or method change is
> a ruled revision under a new commit, never silent; old evidence is never rewritten and never re-judged under a newer method.**
> The protocol identity of `docs/b4_architecture.md` §9.5, once implemented, is what makes a newer verifier refuse an older archive
> by name and point here.

## 1. The two named archives

| | `b4-sim-3` (exploration, S = 32) | `b4-gate-1` (the production gate, S = 200) |
|---|---|---|
| archive directory | `evidence/b4/sim/b4-sim-3_20261019T121833Z/` | `evidence/b4/sim/b4-gate-1_20261020T102526Z/` and `evidence/b4/gate/b4-gate-1_20261020T102526Z/` |
| **code HEAD** (the manifest's `head`; the tree the batch ran on) | `933545a6ccc39f4c4de2ddae76be3a98af58fb22` | `a243ee8ab904d23706bd6b8fee0d76d6ccb200a5` |
| **archive commit** (the commit that added the archive, nothing else) | `5c08536b7362cd6b069f3cc68c38638cd2881556` (parent `933545a`) | `507096741e80fec8bd6f0d90e8ce604bf80d6072` (parent `a243ee8`) |
| the tool files in the manifest | 23 (`tool_files`) | 25 (24 host modules and the schema); byte-identical to the accepted baseline `00336d0` |
| repository inputs in the manifest | 45 (`inputs`, by repository-relative path and digest) | 45 |
| external inputs | 6 (the hypothesis's vendor sources, by absolute path and digest) | 6 |
| the registry **at the start** (the manifest's `exclusion.registry_snapshot`) | empty — `evidence/b4/sim/` did not exist at `933545a` | exactly one entry: `b4-sim-3_20261019T121833Z` (`seeds`, `1a0d1e7b…`) |
| the registry **at the archive commit** | the snapshot **plus this batch**: `b4-sim-3` | the snapshot **plus this batch**: `b4-sim-3` and `b4-gate-1` |
| pooled exclusion at the start | 2 159 | 2 224 |
| the exposure receipt | `68764bbc1a51ec25…`, 66 values | the same |
| the verifiers of that version | `b4/host/b4_sim_verify.py` at the code HEAD | `b4/host/b4_sim_verify.py` and `b4/host/b4_gate_verify.py` at the code HEAD |

The counts above are **the recorded values of these two manifests**, read on 2026-10-20; they are not constants of the procedure. A
later archive is checked against the field shapes and the actual input list of its own manifest and schema version.

## 2. What was verified, read-only, on 2026-10-20 (the facts the procedure rests on)

- Each archive commit is **the code HEAD's tree plus the archive and nothing else**: `git diff --stat <code HEAD> <archive commit>`
  excluding the archive directories is empty for both (the owner's independent check agrees: 0 non-archive changes in both).
- `933545a` holds no `evidence/b4/sim/`; `a243ee8` holds `b4-sim-3` and not `b4-gate-1`'s batch or gate directory. Hence the
  relation of section 1's two registry rows: **start = snapshot; archive commit = snapshot + the named batch**. They are not equal and
  must not be made equal — no directory is removed to make them match.
- Every tool digest of `b4-sim-3`'s manifest is reproduced from the blobs of the `933545a` tree (`git cat-file`); `b4-gate-1`'s
  tool files equal the `00336d0` baseline (`git diff --stat 00336d0 a243ee8 -- b4/` empty; `import_check.py` 52 entries equal).
- The six external inputs (UNISIM `FDCE.v`, `FDPE.v`, `FDRE.v`, `FDSE.v`, `LDCE.v`, `LDPE.v` under
  `/home/test/Xilinx/2025.2/data/verilog/src/unisims/`) exist at their recorded sha256 on this host today.
- The verifiers compare **recorded** values only: `b4_sim_verify.py` compares the manifest's `head` with the report's; `b4_gate_verify.py`
  compares the gate report's `head` with the batch's recorded `head`; neither reads the live `git rev-parse HEAD` or `git status --porcelain`.
  A detached worktree at the archive commit is therefore a valid place to run them.
- The verifiers re-hash the formal inputs they pin (the hypothesis, the certificate, the exposure receipt) and compare the other
  input digests recorded in the manifest with those recorded in the report; `docs/b4_architecture.md`'s digest is recorded in the
  manifest (`b4_sim.ROOT_INPUTS`) and **not pinned** — a revision of that document does not change the verification of an archive.

The read-only record of these checks: `evidence/b4/unit_protocol_v2_design_2026_10_20/readonly_record/r5_git_readonly_checks.txt`.

## 3. The procedure (every step has a stop; nothing is substituted, back-filled or re-judged)

| step | action | stop condition |
|---|---|---|
| 1 | Read the archive's `manifest.json` under its own schema version: `head` (the code HEAD), `tool_files`, `inputs`, `external_inputs`, `exclusion.registry_snapshot`, `exclusion.exposure_receipt`, the thresholds block, the label and count. Read `sim_report.json`'s recorded `head` and identity. | an unreadable or schema-invalid manifest or report → stop, name it |
| 2 | Find the **archive commit**: the first commit that added the archive directory (`git log --diff-filter=A --format=%H -- <archive dir>`). Check that its parent is the code HEAD and that `git diff --stat <code HEAD> <archive commit>` **excluding the archive directories** is empty. | a different parent or any non-archive change → record the difference by name and stop; no other commit is substituted |
| 3 | `git worktree add --detach <dir> <archive commit>`. | — |
| 4 | In the worktree, hold the manifest to the tree: every `tool_files` digest equals the file's sha256; every `inputs` digest equals the file's sha256 (the list is the manifest's own, whatever its length); every `external_inputs` path exists on this host at the recorded digest; the receipt file hashes to the recorded digest. | any inequality → stop, name the file; **a missing or re-hashed external dependency is a named stop, never replaced by another copy** |
| 5 | The registry, in two comparisons: (a) the registry the batch **started** with — the run directories under `evidence/b4/sim/` of the **code HEAD's** tree — equals the manifest's `registry_snapshot` entry for entry (directory, status, `seeds.json` digest); (b) the registry of the **archive commit's** tree equals that snapshot **plus the archive's own directory** and nothing else; every entry's `seeds.json` bytes hash to the recorded digest. | any extra, missing or re-hashed entry → stop, name it; nothing is removed or added to make the sets match |
| 6 | From the worktree root, with that version's tool: `python3 -B b4/host/b4_sim_verify.py <archive dir>` (deep), and for a gate `python3 -B b4/host/b4_gate_verify.py <gate dir>` (deep); the outputs captured with a header — the archive commit, the code HEAD, the command, the UTC. | a non-zero exit or a finding is **that version's finding on that archive**, recorded as such; it is not a new verdict and it is not explained away |
| 7 | Confirm the archive bytes the verifier read are the committed bytes: `git ls-tree -r <archive commit> -- <archive dirs>` against `git hash-object` of the files in the worktree (the same commit, so equality is expected; it is recorded, not assumed). | an inequality means the worktree was modified → stop, discard the worktree, start again |
| 8 | Keep the record in the evidence directory of the unit that performed the re-verification; remove the worktree. | — |

**What the procedure keeps apart, and why.** The **code HEAD** is what ran; the **archive commit** is where the bytes live; the
**repository inputs** are the 38 historical exclusion sources, the root inputs and the hypothesis's repository sources at their
recorded digests; the **external dependencies** are files outside the repository that the hypothesis names by absolute path and digest.
A step that cannot be satisfied is a named stop: the archive is not re-verified by a newer tool, the missing input is not back-filled,
and the historical result is not re-judged.

## 4. What the procedure does not do

It does not change the historical tree, the archive, the manifest, the report, the receipt or any seed. It does not run a newer
verifier on an older archive, and it does not run an older verifier on a newer archive. It does not establish anything beyond what the
original verifier establishes (internal execution and derived-result consistency and source binding — not the truth of the
observation source, `docs/b4_architecture.md` §5.3). It is not a version selector: when the protocol identity of §9.5 exists, a
verifier that meets an archive of another identity refuses by name and points here; the person re-verifying then follows this page
with the archive's own version of the tool.

## 5. The coupling this page lives next to, and the identity now implemented

The v0.1.16 thresholds table ("section 9 (v0.1.16)") is embedded in every v0.1.16 manifest and compared by the verifier of that version as
a whole; its static pin test also asserted the architecture document's first-line version. The v0.2.0 tool unit (`b4_protocol.py`, the
owner's choice 6) implements the identity of §9.5: the method's digest no longer carries the document's revision text (the table of
v0.2.0 is "section 9"; the revision is read from `b4/architecture_revision.json`, a provenance file outside the identity's inventory, so
that a documentation-only revision touches no inventoried byte — the owner's review of 04385ae, R1), the pin test holds the document's
first line to that file's value, and every v0.2.0 manifest records the identity and its digest. **What this means for the two archives of section 1:** the
v0.2.0 verifiers (`b4_sim_verify.py`, `b4_gate_verify.py`), the judge (`b4_gate.py judge`) and the policy (`b4_gonogo.py decide`)
refuse them **by name** at their first step — "the archive carries no protocol identity: written by a tool before the identity existed
(its thresholds source … (v0.1.16) …, HEAD …) — re-verify it with its own tool at its recorded HEAD" — and write nothing; a v0.2.0 archive
whose identity differs from the verifier's is refused the same way, the differing components listed. Both named archives are therefore
re-verified by this page with the v0.1.16 tool at their archive commits, never by the v0.2.0 tool.

## 6. The third named archive — `b4-sim-4` (protocol v0.2.0), under protocol v0.3.0 (2026-10-27)

The task-v0.3 revision (`docs/b4_architecture.md` v0.3.0, §7.2) changes the task's stimulus rule, which is a component of the protocol
identity (§9.5): the v0.3.0 batch verifier (`b4_sim_verify.py`), the judge (`b4_gate.py judge`) and the policy (`b4_gonogo.py decide`)
therefore refuse the `b4-sim-4` **batch** archive **by name** — "the archive's protocol identity is not this tool's: task: …" with the
differing components listed, pointing here — and write nothing. **One qualification (the owner's P3 of 2026-10-27):** the go / no-go
**decision-record** verifier (`b4_gonogo.py verify`) validates the record's shape — its `policy` block against the current table — before
it compares the identity, so the v0.2.0 decision record `evidence/b4/gonogo/b4-sim-4_20261021T065857Z` (its policy block carries
`alpha_go`) is refused first at that step, by name, as `policy: not the table's`, without the identity line and this pointer; the
refusal is safe (nothing is written), was disclosed by the task-v0.3 unit, and needs no runtime change and no new digest. The
historical decision record is re-verified by the same recorded-HEAD procedure as the batch. The archive is re-verified by this page's
procedure (§3) **with its own tool at its recorded HEAD**, exactly as the two v0.1.16 archives are; nothing of it is re-judged, corrected
or compared under v0.3.0, and its no-go of record stands.

| | `b4-sim-4` (exploration, S = 32, protocol v0.2.0) |
|---|---|
| archive directories | `evidence/b4/sim/b4-sim-4_20261021T065339Z/` (the batch) and `evidence/b4/gonogo/b4-sim-4_20261021T065857Z/` (the go / no-go decision record) |
| **code HEAD** (the manifest's `head`; the tree the batch ran on) | `495cc360c97aba58bda959a2e867e6b43dbf4f7f` (the v0.2.0 tool unit `21db2de` plus the documents-only closure `34c607f` and the execution plan `495cc36`; the tool files byte-identical to `21db2de`) |
| **archive commits** | `580c0e5` (the batch, parent `495cc36`), `adce027` (the decision record, parent `580c0e5`); the unit record `196b358` / `5b8aabc` / `fceedd6` after them |
| the tool files in the manifest | 28 (`tool_files`: the 27 host modules and the schema) |
| repository inputs / external inputs | 45 / 6 (the same external UNISIM sources as section 1) |
| the registry **at the start** (`exclusion.registry_snapshot`) | exactly two entries: `b4-gate-1_20261020T102526Z` and `b4-sim-3_20261019T121833Z` |
| the registry **at the archive commit** | the snapshot **plus this batch** |
| pooled exclusion at the start / after | 2 625 / 2 690 |
| the protocol identity recorded | `protocol_sha256` `2f096d4a…` (the v0.2.0 method; the v0.3.0 tool's differs in the `task` component and in every module whose bytes moved) |
| the verifiers of that version | `b4/host/b4_sim_verify.py` and `b4/host/b4_gonogo.py verify` at the code HEAD (a worktree at `495cc36`, the archive copied in as §3 describes; the gonogo verifier needs the batch directory beside it) |

The counts are the recorded values of that manifest, read on 2026-10-27. The v0.3.0 tool's refusal names the differing identity
components and points here; the pointer is the whole of what the newer tool does with this archive.
