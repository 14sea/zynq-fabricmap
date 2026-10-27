# B4Q — the host-only observation integration (DRAFT v0.2, 2026-10-28; v0.1 held by the owner's review of `3723b91`, R1–R5 repaired — section 5a): the executing side, the PCAP links, the schemas and adapters, the offline end-to-end transaction

> **Authorisation.** The owner's disposition of 2026-10-27 (`build/wip/owner_next_b4q_2026_10_27/README.md`, section 4; archived in
> `evidence/b4/unit_b4q_integration_2026_10_27/owner_ruling_2026_10_27/`): one complete host-only engineering unit whose purpose is "an
> offline end-to-end observation transaction using the executing-side implementation and the real record / validation path, with a
> reviewable B4Q qualification plan" — the five deliverables of that section. **Not authorised, not done:** physical board access,
> power, provisioning, PCAP loading, 2d, routing, production seed derivation, search, gate, parameter sweeps, protocol / task / operator /
> threshold changes, carrier RTL changes, push / merge. The plan is `docs/b4q_plan.md`; this page is the design record of what was built,
> what it proves and what it cannot.

## 0. The one sentence

A C program that runs the contract's transaction (P1–P10 and the A5 injection protocol) on the carrier v2 register map through an
injected transport was driven, on the host, against a register-level emulation of the carrier (held to the RTL by replaying the carrier
unit's 27 archived bench traces with zero mismatches) and a minimal fake of the DevC / PCAP path; every record (`session_open`, `O`,
`F`, `X`) was built from the register trace by the accepted record layer, the executing side's digests and fitness held to the host's
view, the program's actual MMIO accesses held to the RTL decode (A7), six explicit schema files held to the code validators, three
adapters of the contract's representations read into one view, and a fresh-process verifier re-derived all of it from the retained
files — valid paths with empty findings, negatives named. **Nothing here is a physical link, silicon, A2 / A8 on a die, or a
qualification**: the emulation's fabric is the hypothesis model and its PCAP a frame store in memory.

## 1. What was built (and where)

| piece | files | what it is | held by |
|---|---|---|---|
| the executing side | `firmware/b4q/b4q_tx.{h,c}`, `b4q_hal.h`, `b4q_host_main.c`, `Makefile`, `build.sh`, `IMPORT.json` | the session opening (identity: IDCODE, VARIANT v2, the declared mechanism, key_loaded, idle; the startup readback of the loaded image's write set) and the transaction: derive → sign (link 1, the notary's) → stage → ARM (the A5 context flag only on J3) → link 2 (the staged streams re-read from DDR, parsed literally, hashed; must equal the commit) → the two envelope writes (P2) → link 3 (P2) → PRE_SAMPLE, the pre-init sample read from slot 0 with its applied inputs → INIT_REQ, waited for in STATUS (`init_done`), the witness read → link 3 (P4) → the set steps, each latched by the engine and sampled into its slot (P5) → the fitness over the full mask on the sampled values (P6) → CLEANUP (P7) → the base (genome 0) signed, staged, written, read back (P8) → RESTORE_INIT and the BASE_STATE sample (P9) → CLOSE, idle (P10); or CLOSE_INJECTION after P6 (J2). Every wait is a bounded poll of STATUS / FAULT, never a bus acknowledgement; every stop names its reason at the phase reached; the allowlist is checked at the accessor before every carrier-window access; the key window is never touched; the four DMA tuples are the archived path's | `tests/test_b4q_firmware.py` (strict build, the source audit, A7 on the actual accesses), `tests/test_b4q_session.py` (the offline e2e), the mutant battery |
| the derive unit | `firmware/b4q/b4q_derive.{h,c}`, `b4q_derive_twin.c`, `b4q_data.{h,json}`, `b4q_regmap.h`; `host/b4q_frames.py`, `b4q_gen_data.py`, `b4q_gen_regmap.py` | DERIVED from `firmware/b1/p3_derive.{h,c}` (the instrument's D1 derive): sha256 / hex / CRC / frame ECC / the stream builder and its literal parser / the FAR-ordered frames hash / the readback and cleanup commands / the nonce step **verbatim** (held function by function by the digest of each function's text); the genome codec rewritten for 21 bits; the data table B4's — the write set of section 2 — generated from the committed bitstream and the certificate mapping; the Python twin reproduces every digest over a corpus (0, all ones, each single bit, the loaded image's genome, 64 seeded genomes); the regmap header generated from the one table of record | `tests/test_b4q_derive.py` |
| the carrier emulation | `host/b4q_emu.py`, `b4q_emu_fidelity.py` | a register-level model of `rtl/b4` (the register file's acceptance rule and SLVERRs, the gate with the instrument's SipHash and the xorshift nonce, the engine's operations, faults, slots, witnesses and the GSR event with its stall) over the hypothesis model as the fabric, with a cycle model calibrated on the archived traces (a flip-flop result one cycle after the computing cycle, a LUTRAM result two); the archived 27 bench traces replay through it: every write at its recorded time, every read's data (or x pattern) and response compared — **0 mismatches** (the three bus-level scenarios the bench drives by hand are compared up to the first unlogged handshake and say so); a whole stimulus through its per-step fabric equals `observe()` row by row | `tests/test_b4q_emu.py`; the fidelity report in the unit directory |
| the host transport | `host/b4q_backend.py` | one address space: the carrier window (logged as the bench logs it, with the window offset, so the record layer reads the emulation's trace as it reads the bench's), the DevC registers with a minimal PCAP fake (submissions recorded, envelopes parsed with the pinned grammar and stored by FAR, readback commands matched to a FAR, the pad + target frame delivered, fault modes for the negatives — a simulation, never evidence that hardware stopped a DMA), the three DDR buffers, the IDCODE; the slice's configuration follows the frame store | the e2e |
| the notary | `host/b4q_notary.py` | the bench signer principal: derives the candidate's frames itself, commits in the candidate_sha256 domain, signs commit ‖ six zero table words ‖ the PL's nonce with the instrument's signer library (bound read-only); the write-set gate; a fixture key on a private file; **no attestation** (B1's non-semantic contract carried over) | the e2e; `tests/test_b4q_emu.py` (the fixture's VALID / UNSIGNED / WRONG_COMMIT / wrong key / replay under the emulated gate) |
| the session runner | `host/b4q_session.py` | starts the program, answers its every MMIO access and SIGN, inserts its marks into the trace, builds `session_open` / `O` / `F` / `X` **from the register trace** with `host/b4carrier_records.py` (the links from the backend's PCAP log — the host's view), holds the executing side's digests and fitness to the host's, binds every record to its trusted context, writes the evidence directory | `tests/test_b4q_session.py` |
| the verifier | `host/b4q_verify.py` | fresh-process: rebuilds every record from the retained trace, links and declared stimulus and compares to the stored ones; structure / binding / chain; the schema files on every record; the links recomputed from the PCAP log; the executing side's digests and fitness held to the host's; A7 on the access log; the view adapter on every valid `O`; the manifest's references against the write-set record of record; one report per directory whose per-transaction findings must equal the session's (agreement is the exit code) | `tests/test_b4q_session.py` (incl. tampered evidence found) |
| A7 | `host/b4q_a7.py` | the program's **actual** accesses against the RTL decode (parsed from `rtl/b4/b4_axil.v`), the register table of record (app reads / writes, the key window), the DevC's six registers, the three buffers, the IDCODE; the DMA submissions against the four legal tuples; mismatches only | `tests/test_b4q_firmware.py` |
| the schemas | `b4q/schemas/*.schema.json`, `host/b4q_schema.py` | the six explicit files of contract 4.4 under the owner's provisional names (`ff_observation_carrier_v1` with the complete / invalid-by-phase variants, `ff_fitness_v1`, `ff_transaction_close_v1` closed / injection_open / faulted, `ff_session_open_v1`, `ff_observation_model_raw_v1`, `ff_observation_view_v1`) and a closed JSON-Schema-subset validator; the files are the reviewable artefact, the code validators of `host/b4carrier_records.py` the authority — held to agree on every record and on the tampers | `tests/test_b4q_schema.py` |
| the adapters | `host/b4q_view.py` | contract 3.1 / 3.2: M-raw (a full model return), M-ledger / M-target / M-memo (the archive's projections, with the pair's task), C-O (the carrier record) → one logical view with every field tagged R / D / A; the digests verified only under their declared encodings (`raw-dict-default`, `proj-dict-canonical`, `list-canonical`); the source from the trusted context (3.5), a record offered under the wrong branch refused by name; exercised on the committed `b4-sim-5` target / ledger records, the `b4-sim-4` null counterexample of contract 3.4 (36 null cells), a model return and a session `O` | `tests/test_b4q_view.py` |
| the qualification readings | `host/b4q_qual.py` | the contract's rules made executable on records: the A5 decision table (5.6), the SR-evidence joint reading (6.5), the precedence-ordered A8 classification (6.7) over a 2 × 2 cross, the A2 row (7.1) | the e2e (a5 pass, a5_persist fail data, a8_cross rows, a2 rows) |
| the end-to-end driver | `host/b4q_e2e.py` | sixteen scenarios (eleven at the first delivery, five fail-closed ones after the HOLD), each its own session (section 3) | `tests/test_b4q_session.py` |
| the mutant battery | `evidence/b4/unit_b4q_integration_2026_10_27/b4q_mutants.py` | 36 single mutants + 8 combined (the repair's guards included), each one text edit restored byte for byte, probed by the e2e / the verifier / the tampers / the fault probes; every survivor named with the guard that masks it | `mutants.txt` |

## 2. The write set — a host fact, a plan question

B4's universe is the 21 certified addresses of `SLICE_X2Y25` in four frames of the CLB column `0x00400a00` (minors 0, 1, 30, 31; words
51 / 52). The instrument's PCAP grammar (kept verbatim) writes an FDRI envelope of four consecutive target frames and one flush frame.
The write set here is therefore **two envelopes**: FAR `0x00400a00` (targets `a00`–`a03`, flush `a04`) and FAR `0x00400a1c`
(targets `a1c`–`a1f`, flush `a20`); the four target frames and two flush frames that carry no certified bit are written with the
**loaded image's own content** — the committed `builds/b4/b4.bit` (`4e406f12…`, the digest `builds/b4/b4_build.json` records) parsed by
the repository's read-only frame parser, every frame ECC-consistent — so the write changes exactly the whitelisted bits and the ECC
word of the frames holding them. The candidate hash (what the notary signs) is the FAR-ordered digest of the eight frames.

**What the build of record says about the column** (`builds/b4/isolation.txt`): the target column holds exactly the 12 target cells
and nothing else; no RAM32X1S (the carrier's persistent state) lies in it; 874 foreign nets are routed through its interconnect
frames (the route inventory is evidence under erratum 001, not a verdict). Writing those frames with their own content on a live
device is what the B1–B3 sessions did on this part in this grammar; whether it is safe for THIS carrier's own logic — the frames
`a02`–`a04` and `a1c`–`a1d` carry the routing of its nets — is the plan's legal-write / composition question (`docs/b4q_plan.md`
§5), stated there with this evidence and **not decided by this unit**.

## 3. The offline end-to-end: what each scenario produced (`host/b4q_e2e.py`; the evidence directory holds one run)

| scenario | what | outcome (the verifier agrees with the session on every one) |
|---|---|---|
| `valid` | open → root → three candidates (the carrier bench's fixtures BASE, CE_SR_ASYNC, SYNC_SRVAL0) with a trusted task | `session_open` open (the startup readback = the host's view); four `O` complete, four `X` closed, three `F` equal to the host's recomputation; chain empty; A7 empty; **clean** |
| `a5` | J1 c, J2 c′ (every element driven opposite to INIT, inputs held, CLOSE_INJECTION), J3 c under the A5 flag, then a normal candidate | the J3 `O` with `predecessor.kind = a5_injection`, `initial.context = a5_injection`, `pre_init_cleanup = true`; the A5 decision table: the injection arrived and was cleared → **pass**; clean |
| `a5_persist` | the same on the hypothesis swap `init_no_effect` | the injection arrived and persisted → **fail** (the A5 fail data), the differing positions listed; the records themselves clean |
| `a8_cross` | the 2 × 2 cross on AFF (bits ff_init / ff_srval of AFF on the CE / SR-driven background) under the demonstration stimulus of contract 6.5 (section 4) | AFF: row 2 **both demonstrated** (every corner `restore`, INIT and SRVAL each tracking its own bit); BFF (a bystander): row 5 **neither demonstrated** (INIT absent, a constant restore) — the mechanics of 6.7 on the model's records, no silicon claim; clean |
| `a2_pairs` | two rows of 7.3: `ce_mode` (000000 / 000010 under a CE-low capture) and `storage_kind` (000000 / 000400) | `ce_mode` **differs**; `storage_kind` **not assessable**: the latch endpoint's x5FF elements have no model value, the carrier record is refused for its None cells — the emulation's limit (a board supplies physical values there) |
| `not_realisable` | a non-uniform `ce` vector at the third set step | `O` invalid at **P5** (`not_realisable`), the acquired prefix retained, no `X`; the next ARM refused under recovery; the chain ends |
| `wrong_key` | the carrier provisioned with another key than the notary's | the root's `O` invalid at **P1** (`arm_auth`), no `X` |
| `notary_refuses` | a genome the notary refuses | the executing side stops at P1 (`STOP_SIGN`); **no `O`**: nothing to seal (section 6, finding 2); the raw result and trace retained |
| `dma_never` | the 35th frame read never completes (the candidate's pre-event readback) | the executing side stops at P2 (`STOP_DMA`); no `O` (the link of P2 did not complete and no carrier fault stopped the acquisition); retained raw |
| `latch_unmodelled` | a latch candidate | the `O` refused by the carrier validator (None cells at every x5FF): the D1 rule seen from the host |
| `interrupt` | the transport cut after 3 000 accesses of the candidate (inside its P2 writes) | status 5 interrupted; no `O`; the prefix retained; nothing follows (a further transaction is refused without a ruling) |

The accepted record builder was extended in one place (`host/b4carrier_records.observation`, kept under `host/`): a PCAP-side
witness the instrument's path did not produce is **not written** (contract 4.2: "absent, never a placeholder") and caps the stop
phase at the last link that completed; a complete `O` still needs all four. The carrier unit's 18 record tests pass unchanged.

## 4. The demonstration stimulus of 6.5, on this carrier

The controls are slice-wide (one CE / SR pin): "the other elements held at *b*'s inputs" is realised as the same inputs on every
element. The fourteen set steps (after the init step), on the CE / SR-driven background `0x18`: C0 a capture of 0 (steps 1–2), C1 a
capture of 1 (3–4), E0 a capture of 1 as the prior (5–6), SR asserted on a level step (7), the edge with `d = 0` under SR (8), release
(9); E1 a capture of 0 (10–11), SR level (12), the edge with `d = 1` under SR (13), release (14). The six sample points `K0 K1 P0 R0 P1 R1`
are steps 1, 3, 5, 8, 10, 13 (`host/b4q_e2e.DEMO`, `DEMO_PARTS`). The `ce_mode` A2 row uses its own vectors (a capture of 0 under CE,
then a capture attempted with CE low). These are the plan's proposed vectors (`docs/b4q_plan.md` §3); the plan may fix others.

## 5. What is emulated, what is not — the limits, stated

- **The fabric is the hypothesis model.** Every sample is `b4_ff_model`'s; an element the model gives no value for reads as `x` and
  becomes None in the record, which the carrier validator refuses. On a board every element samples a physical 0 / 1. So the
  emulation cannot exercise the latch endpoints, G6's init readout or A8 itself — only the mechanics of their records and rules.
- **The PCAP is a frame store.** A readback digest here equals the staged digest by construction; link 2 / link 3 prove the executing
  side's arithmetic and sequence, not a device. The frame invariance of mechanism (b) is trivially true in the emulation.
- **The carrier emulation is held to the RTL bench, not to silicon**; its timing model reproduces the bench's cycle behaviour; the GSR's
  effect on the die, release skew and the pulse width are A8's.
- **The executing side has no board image**: no BSP, no console framing, no watchdog, no MMU attributes; the pure units compile for
  cortex-a9 (`make xcheck`, objects only). The board stage (B1's `bsp/build.sh` precedent) is later work.
- **The notary is a bench fixture** (a fixture key on a private file); provisioning on a device is a ruling (`provisioning P3-K`).

## 5a. The repair after the owner's HOLD on `3723b91` (R1–R5, 2026-10-27)

| item | what was wrong | what changed | held by |
|---|---|---|---|
| R1 fail-closed sequencing | the executing side reported link mismatches but ran on; a refused STEP_IN write launched the STEP on the stale word; the session signed after a refused opening and after an unclosed transaction | `b4q_tx.c`: the pre-event readback compared to the signed candidate **before** PRE_SAMPLE / INIT_REQ, the post-event to the pre-event **before** any STEP, the restored base to the derived base **before** RESTORE_INIT; every write response propagated (a refused STEP_IN, payload, tag or SLOT_ADDR write stops at the phase reached); `b4q_session.py`: a halt latch — a refused opening, a transaction with no sealed `O`, no closed / `injection_open` `X`, a link / F / binding finding or an interruption refuses every further transaction before anything is signed; the A5 injection exception kept (J2's `injection_open` is a legal predecessor) | the five fault scenarios of the e2e (`startup_corrupt`, `pre_event_corrupt`, `post_event_corrupt`, `base_readback_corrupt`, `step_in_slverr`) assert the ABSENCE of the later CTRL operation / DMA / signature; the mutants R1a–e |
| R2a completeness | the verifier enumerated `tx_*` directories | the manifest declares every record with its directory and ranges; the verifier refuses a declared record that is missing, an undeclared directory, a malformed manifest (shape, fields, ranges) before consuming anything, and finds an unconsumed trace / PCAP suffix, a gap or a mark count that is not the record count | `test_b4q_session.test_r2_*`; the mutants R2a / R2a2 / R2c |
| R2b the staging phase | `staging_readback_sha256` was the frame store's hash after the write | the backend retains every submitted stream's words at submission (`stream_submitted` in the PCAP log); the pre-write witness is recomputed from those bytes by the session and, independently, by the verifier (`b4q_session.staging_witness`); the executing side's `staged` / `stream` / `base_staged` digests held to the same bytes; the post-write readbacks are the separate `fabric_readback_*` witnesses | the e2e; a tampered retained stream found |
| R2c refusals | `manifest.json = []` was a traceback | `b4q_verify.load_archive`: a named `REFUSED`, exit 1 | `test_r2_*` |
| R3 qualification conclusions | conclusion files were never recomputed; A5 passed without the close witnesses | the session declares the qualification index; the verifier recomputes A2 / A5 / A8 from the retained records and holds the files to it; `a5_verdict` needs J1 / J3 closed with their cleanup and J2 `injection_open`; `a8_classify` needs every corner complete and closed; `a2_row` needs both endpoints closed; the plan's §4.1 states the data-versus-claim distinction | `test_r3_*`; the mutants R3a / R3b |
| R4 A7's DMA tuple | the memory-side endpoint, the HOLD tag and the alignment were not checked; the logged kind was trusted | every submission classified from its full registers (both endpoints, both lengths, the tag, the alignment, the exact staging slots); the logged kind held to it | `test_dma_tuples_are_classified_from_their_registers`; the mutants R4a / R4b |
| R5 the raw configuration | `config: {type: object}`; the adapter coerced with `int()` | the raw schema types the dictionary (21 address-keyed type-exact bits; the subset validator learnt `additionalProperties` as a schema and `propertyNames`); the adapters validate every consumed field by type before deriving anything; no coercion; legitimate model nulls stay | `test_raw_values_are_checked_by_type_before_any_conversion`; the mutants R5a / R5b |
| P3 setup | tests consumed the fixture by existence | `tests/b4q_fixture.py`: the executing side built and the fixture generated unless complete; prerequisites stated | the owner's two test logs kept beside the repair's |
| disposition 1 | the manifest of record stale | regenerated narrowly from the committed bitstream; the old file and the comparison archived (`manifest_regeneration/`) | `test_the_manifest_correction_is_a_recorded_before_and_after` |
| disposition 2 | no `O` for a host-side failure | kept as a named host non-success result with the raw prefix, no fabricated `O`, the stop latched (plan §4.2) | the e2e negatives |

## 6. Findings for the owner (the first delivery's; their dispositions in the HOLD review of `3723b91`)

1. **The carrier manifest of record was stale** (repaired: regenerated from the committed bitstream; before / after archived). `builds/b4/b4_carrier_manifest.json` recorded the pre-v0.4 bitstream (`52f2ea56…`) and
   per-frame digests of which **22 of the column's 36 frames differ** from the committed `b4.bit` (`4e406f12…`, the v0.4 rebuild that
   `b4_build.json`, `isolation.txt` and the carrier unit's README name); the four frames holding the 21 addresses and all 21 address
   values are equal. A session-opening readback of a v0.4-loaded device compared against that manifest's column digests would be
   **refused**. This unit binds its base to `b4_build.json`'s digest and records the loaded-image reference it derives
   (`firmware/b4q/b4q_data.json`); regenerating the manifest of record (`host/b4carrier_manifest.py builds/b4/b4.bit --json …`) touches
   a build of record and is the owner's.
2. **A host-side link failure has no fault code** (decided: no `O`, a named host non-success result, the stop latched — plan §4.2). Contract 5.7 says a link failure in P1–P5 leaves `O` invalid with a `fault`, but
   4.2's `fault.code` is the carrier's closed set (plus the host-recorded `premature_operation`); a notary refusal, a DMA that never
   completes, a stream that does not parse have no code. Under the accepted contract no `O` is sealed for them: the raw result and
   trace are retained as non-success records (5.7's interruption row). A host-recorded code (e.g. `link_failure` with the link named)
   is a contract change for the owner.
3. **The latch endpoint of the `storage_kind` A2 row** cannot be assessed on the host (section 5); the plan carries the row to the board.
4. **The bench's slice model and the hypothesis differ in one unexercised corner**: after an init event the bench's `always @(*)`
   makes a non-inverted-gate latch transparent at once (clock low → gate high), while `observe()` settles no level effect at the init
   step; no fixture of either reaches it (every latch fixture has CLKINV = 1). Noted, not resolved; the emulation follows the model.

## 7. What this unit does not do

No board, no power, no provisioning, no PCAP on a device; no production seed, search or gate; no change to the hypothesis, the task,
the protocol, the thresholds, the labels, the receipt, any archive or decision; nothing under `b4/host`, `b4/schemas`, `rtl/`,
`builds/` or `vivado/` changed; no push, no merge. It returns the package whole for review.
