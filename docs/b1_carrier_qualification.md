# B1 carrier qualification — what is host-verified, what needs the board, and how the result is bound (v0.3, host-only, 2026-09-05)

> **Standing: host-only. No ruling; no board contact.** The B1 carrier (`builds/b1/b1.bit`
> `d85daef4…`) is a new bitstream and inherits none of the instrument's board-level
> guarantees (L2 non-perturbation, L3–L5 on the P3 carrier, the L6 soak). This document
> lists what is already verified on the host, what the **qualification session** (`B1Q`) —
> its own ruling pair, before the mapping session — must establish on silicon, and how its
> result becomes an **evidence chain** rather than a flag (owner's review 2026-09-05,
> blocker 3). This file is pinned by the runtime (`manifests/b1_instrument_pins.json`).

## 1. What changed and what did not

| | instrument (P3, `956379fa…`) | B1 carrier (`d85daef4…`) |
|---|---|---|
| gate | `p3_arm_gate` — readout must equal the signed tables | `b1_arm_gate`, `SEMANTIC_GATE = 0` — the same authorisation (key, nonce, tag), the same sweep, the readout raw, `tables_match` an observation |
| register file | `p3_axil` | `b1_axil` + read-only `VARIANT` (`0x2034` = `0x42310001`); the eight stable words keep their offsets; the write-once key window unchanged |
| everything else | AXI3 shim, scorer, XDC, pblock, isolation checks, constants | **identical files** (hash-equal to the instrument's imports; `tests/test_b1_carrier.py`) |
| part / top / seed | `xc7z010clg400-1` / `p3_top` / `0x9E3779B97F4A7C15` | the same part / `b1_top` / the same seed |

## 2. Host-verified (done)

| item | result | where |
|---|---|---|
| RTL diff is the parameter and the register only | siphash verbatim; gate = the instrument's + `SEMANTIC_GATE`; axil + `VARIANT` | `tests/test_b1_carrier.py::CarrierSources` |
| simulation, the instrument's scenarios that still apply + the contract's own | `tb_p3_siphash` (verbatim) PASS; `tb_b1_core` PASS — zero-table payload ARMs and the readout is the bench's fabric; a changed fabric changes the readout, no fault; attested tables still ARM (the host refuses them); unsigned / replay / wrong commit / wrong key / no key refuse; reset clears the key | `sim/b1/run.sh`; `tests/test_b1_carrier.py::Benches` |
| Vivado build (2025.2) | routed; **WNS +7.993 ns**; **ICAPE2 0**; isolation: target cells 6, flush cells 0 | `builds/b1/b1_build.json`, `isolation.txt`, `timing.rpt` |
| carrier manifest (the instrument's own generator) | validates under the instrument's schema; 12 target frames blank; positive control `0x00401420` globally unique; frame count 5144 | `builds/b1/carrier_manifest.json` |
| MMIO allowlist vs the RTL decode | app reads ⊆ RTL reads (VARIANT included), app writes ⊆ RTL writes, RTL − app = the key window only | `tests/test_b1_carrier.py::MmioAllowlist` |
| the host validator refuses an attested reply | `host/b1_records.py` rule (iii-B1) | `tests/test_b1_records.py` |
| the signer never computes semantics | the oracle's entry points are disarmed in-process in `host/b1_sign_arm.py` (a call is a refusal); the answer carries zero tables only; no host-attested `sign` op exists | `tests/test_b1_signer.py` |
| the qualification session, modelled end to end | the B1Q plan through the instrument's real host stack and validators: PASS with every silicon observation of §3 present; every break of §4 refused | `tests/test_b1_qualification.py` |

Not host-verifiable, by nature: that the silicon behaves as the routed netlist says (the
qualification session), and that the PS→PL path is undisturbed by the new register (the
same session's read-only checks).

## 3. The qualification session `B1Q` (board; its own ruling pair; before any mapping)

**Plan** (`evidence/b1q/plan.json`, pinned in the manifest as `qualification_plan`; built
by `host/b1_plan.py --qualification`): the B1 image with **budget 9** on the B1 carrier —
opening baseline, the nine code probes, closing baseline, closing unsigned control =
**11 records, every one audited**; master seed **176 359 248** = the first 4 bytes of
sha256(`b1-qualification|` ‖ the archive commit) advanced past every excluded seed **and
B1's own** (and recorded under `seeds.excluded.b1_qualification`, so the two sessions never
share a seed); 300 expected frames, CRC / bad-frame budget 2; deadline 615 s (expected span
≈ 12 s); flags `0x32`. Its prediction (`evidence/b1q/prediction.json`) pins the nine probe
genomes, every record's content-level block, the provisional content after the nine
probes, the scorer's base counters for a blank candidate `[18, 22, 20, 20, 20, 18]`, and
the STATUS observations of §3.1.

**Rulings**: `whole-of-run B1 carrier qualification` (bound to session `B1Q`, the
qualification plan's seed, the frozen prereg, the B1 image, the manifest sha256) **and its
own** `provisioning P3-K` bound to session `B1Q`. A provisioning ruling is consumed once,
so the mapping session needs another one bound to `B1`: **two sessions, two pairs, four
rulings** (package §5).

**Runner**: `host/b1q_runner.py` = the mapping runner's preflight and session function
under the QUALIFICATION profile (session `B1Q`, the qualification plan, no qualification
required of the carrier); the same preamble (precheck → identity → dcache off → clock
preflight → **B1 carrier** load, sha-gated → key provisioning → identity page with the
qualification seed and budget 9 → image load, sha-gated → `go`), the same console loop,
the same evidence files. Afterwards `host/b1q_adjudicate.py` runs over the files as written
and the qualification **record** is left beside them (§4).

### 3.1 What the adjudicator requires, record by record (`host/b1q_adjudicate.py`)

| record | required |
|---|---|
| IDENT | app_identity 1.4.0: `carrier_variant` = `0x42310001` read over the PS path, the carrier hash, carto-v1, the universe digest, budget 9 (binding — a mismatch is a refusal before any record is read) |
| every record | outcome SCORED; audited (the served words recompute the record's hashes — the instrument's audit gate); `fault_after` = 0 and STATUS bit 1 (fault) = 0; STATUS bit 2 (`configuration_valid_hw`) = 1; the signed table words zero (rule iii-B1); the nonce chain by the model |
| seq 1 and seq 11 (baselines) | readout all zero; counters = `[18, 22, 20, 20, 20, 18]`; STATUS bit 10 (`tables_match`) = **1** — a zero readout equals the zero table words: the observation, not a gate |
| seq 2..10 (code probes) | readout **not** all zero (the fabric answered); STATUS bit 10 (`tables_match`) = **0** — the PL ARMed and scored a candidate whose readout differs from the signed table words. **This is the noninterference contract observed on silicon.** |
| the session | COMPLETED at seq 11; the closing unsigned ARM refused `F_ARM_AUTH` (fault 13) — the authorisation half of the gate is the instrument's; rel-v4 closure and both seq-1 controls; heartbeat / CRC / bad-frame budgets; span within the deadline |
| replay / prediction | the nine probes are the reference's proposals and every block matches (the orchestrator ran on silicon); the content equals the pinned prediction (the readouts are what the certificate says); the provisional map complete (292 decoded) |

**No host-attested reply control on the board** (owner 2026-09-05): the nine code probes
are the direct hardware evidence — signed tables all zero, raw readout non-zero,
`tables_match` = 0, and yet `configuration_valid_hw` = 1 and SCORED. The host's refusal of
a non-zero table is a host contract, proven by `tests/test_b1_records.py`; sending
semantic tables with the instrument's signer would only manufacture an expected HOLD,
consume a ruling and violate the contract this round is about.

## 4. The evidence chain: how `qualified` is derived (`host/b1_qualification.py`)

After the preflight and **before the whole-of-run ruling is claimed and before the serial
port is opened** — the order is fixed in `b1_runner.execute` and tested as an order
(`tests/test_b1_runner.py::Order`): archive → claim → port → session; an archive failure
consumes nothing and opens nothing — the runner copies, into the evidence directory, the
exact bytes of the manifest it read (`manifest_at_run.json` — it must hash to the sha256
every binding names) and both rulings as **inert envelopes** (`ruling_whole_of_run.json`,
`ruling_provisioning.json`: `{"schema": "archived_ruling_bytes", "sha256": …,
"content_base64": …}` — the original bytes and their hash, with no top-level `ruling` /
`boardid` / `granted_by` / `date`, so the instrument's `check_ruling`, the signer's
provisioning parser and this runner's preflight all refuse them: an archive is never a
second, unconsumed authorisation; the envelope's key set is EXACT — `schema`,
`schema_version`, `sha256`, `content_base64`, `note` and nothing else — so an envelope
re-armed with ruling fields at its top level is refused by `verify()` even when every hash
in the evidence and the record was updated to match), each decoded and required to equal
what the preflight parsed; every write atomic, a failure removing what was written.
The session function refuses to start without them. During the session the summary keeps
the sha256 of the provisioning ruling's bytes as the signer was handed them (taken before
and after the call; a change is a stop).
After the session and its adjudication the B1Q runner writes **`qualification.json`**
beside them (schema `b1_carrier_qualification` 2.1.0):

```json
{"schema": "b1_carrier_qualification", "schema_version": "2.1.0", "session": "B1Q",
 "evidence_dir": "evidence/b1q/b1q_17A6_<date>",
 "files": {"run_log.json": "<sha256>", "audits.json": "…", "timeline.json": "…", "adjudication.json": "…", "summary.json": "…",
           "manifest_at_run.json": "…", "ruling_whole_of_run.json": "…", "ruling_provisioning.json": "…"},
 "outcome": "PASS",
 "rulings": {"whole_of_run": {"file": "ruling_whole_of_run.json", "envelope_sha256": "…", "bytes_sha256": "…", "content": {…the ruling as decoded…}},
             "provisioning": {"file": "ruling_provisioning.json", "envelope_sha256": "…", "bytes_sha256": "…", "content": {…}}},
 "inputs": {"plan_sha256": "dead8853…", "prediction_sha256": "d2c9293a…", "pins_sha256": "…"},
 "binding": {"session": "B1Q", "carrier_sha256": "d85daef4…", "carrier_variant": "0x42310001", "image_sha256": "31663e2d…",
             "prereg_sha256": "<frozen>", "b1_manifest_sha256": "<sha256 of manifest_at_run.json>",
             "master_seed": 176359248, "budget": 9, "psoracle_commit": "689dde1…",
             "token": "<the run log's app_identity token — read from the evidence, never supplied>"}}
```

The owner pins a PASS record with `host/b1_manifest.py --qualification <evidence dir>`,
which **verifies it first** and writes it as `carrier.qualification`; every later refresh
re-derives `carrier.qualified` from it (and migrates any value that is not a record to
null). **`verify(manifest)`** — called by the mapping runner before the port and by the
mapping adjudicator before any verdict, both of which also require the stored flag to agree
with it — requires all of:

1. the record present with `outcome: PASS`; every one of the eight evidence files still
   hashing to it;
2. `manifest_at_run.json` hashing to the record's and the run log's `b1_manifest_sha256`;
   the manifest it contains binding the same carrier hash and variant, image hash, frozen
   prereg hash and instrument commit as the current manifest, and `board_ready` true (a
   session run before the freeze never qualifies);
3. the run log's token (app_identity, notary_log, session_summary) equal to the record's;
   `summary.json` naming that token, session `B1Q` and outcome PASS, **its `ruling` equal to
   the archived whole-of-run ruling, and its `provisioning_ruling_sha256` equal to the
   archived provisioning copy's** (the signer used those bytes); the run log's binding
   naming session `B1Q` and the same manifest sha256;
4. the run log's `l6.inputs` — plan, prediction and pin-table hashes — equal to
   `manifest_at_run`'s qualification pins (a B1Q log carrying the mapping hashes is refused);
5. both rulings, decoded from their envelopes (envelope hash, bytes hash and content equal
   to the record's):
   the right texts, session `B1Q`, the plan's seed (whole-of-run), the frozen prereg, the
   image, the manifest sha256 of `manifest_at_run`, the board;
6. the stored adjudication a B1Q PASS, and the pinned evidence **re-adjudicated now** by
   `b1q_adjudicate` against `manifest_at_run` to PASS with no finding;
7. the CURRENT manifest differing from `manifest_at_run` in nothing but
   `carrier.qualification` and `carrier.qualified` — the only transition a qualification
   licenses. A pin, a plan, the image, the prereg or a note changed since means the carrier
   was qualified for another manifest.

Any break is a refusal (`tests/test_b1_qualification.py`, `test_b1_runner.py`); a HOLD
session leaves a record too (of a failed qualification) and never qualifies. The whole
lifecycle — freeze → refresh keeps `board_ready` → B1Q → pin → `qualified` derived → the
mapping preflight passes every pin — is one test (`Lifecycle`).

## 5. What this does not qualify

Long runs (the mapping session is ≈ 6 min; the L6 soak's 2 h guarantee is the P3
carrier's, not this one's — a B1 soak would be a separate decision if a long session were
ever planned); any other die; any change to the pblock or the constraints (none was made);
any other image than the pinned one (the binding names it — a new image needs a new
qualification).
