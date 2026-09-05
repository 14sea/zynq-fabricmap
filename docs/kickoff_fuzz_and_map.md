# M2 Prework — Fuzzing × Evolution, prjxray zynq7 Audit, local_map Bootstrap

> **▶ 2026-09-05 — superseded, additively (this text is historical and unchanged):** §5's placement of routing-class autonomous fuzzing on "K7 sacrificial boards" no longer holds. `docs/board_roles.md` (2026-08-02) ruled Zynq-first, and the whole instrument line (psmap / P3) is a PS-looks-at-PL architecture that does not exist on a K7; the sacrificial board is an EBAZ4203 (`08EB`, once provisioned). The current plan is `docs/autonomous_cartography_roadmap.md`.


> Copied verbatim from `zynq-autoehw/docs/m2_prework_fuzz_and_map.md` (origin/main `c495b62`)
> as the kickoff record for this repo. The original stays in place there; do not
> edit history on either side — record new decisions below or in new documents.

Status: discussion record + audited facts, 2026-07-11 (same day as M1 closure).
No M2 decision is ratified yet; this document exists so the M2 kickoff can start
from settled facts instead of re-deriving them. Author: Claude (board/gate side),
discussion with user. ChatGPT has not seen this yet.

---

## 1. Premise correction: what the EBAZ "safe subset" actually is

The safe subset on EBAZ is **not** "LUTs are incompletely documented". It is the
opposite: LUT-INIT is the *complete, silicon-proven* part (the entire zynq-ehw
EHW-1.2/2/5.5 ladder and zynq-xpart M7.5 ran on it). What is excluded is
**routing (INT PIPs)**, for two independent reasons:

1. **Database layer** — prjxray zynq7 was believed partially covered (see §3 for
   the audit that revises this), and the official fuzzers are pinned to Vivado
   2017.2 with upstream archived.
2. **Electrical layer** — a wrong evolved routing config can create a
   double-driven wire (contention) → physical damage or DEVCFG wedge on the
   only EBAZ board. **Completing the database does not remove this layer.**
   This is the real reason routing stays off EBAZ and why the K7 line buys two
   sacrificial XC7K70T boards.

Consequence: "complete the map first" and "safe to evolve routing on EBAZ" are
unrelated propositions. Map completeness changes *whether we can trust a bit's
semantics*; it does not change *what a wrong write does to the board*.

## 2. The EP4CE6 method chain ports, and is already in the plan

`Cyclone_CRAM_Mapper` (~/EP4CE6) is the existence proof that the whole
fuzz-then-evolve pipeline can be built from **zero public documentation**:
directed specimen compile → bitstream diff → per-key mining → holdout →
prediction gate (mine → holdout → emit → unseen-gold, fresh-gold TP=1/FP=0
byte-identical) → silicon (NEORV32 + Linux). The K7-2 "per-PIP validation
harness" in `zynq-ehw/docs/future_plan.md` is exactly this method generalized.

Porting to 7-series has two structural advantages over the Cyclone campaign:

- **Mining is host-side only** (Vivado 2025.2 specimen + `bitread` diff — the
  m75 self-check methodology). Zero board risk; can run before any board
  exists.
- **7-series does not have the Cyclone composition trap.** EP4CE6's two hardest
  falsifications — route composition not byte-identical (Pitfall #14 / A3
  NO-GO) and LI-MUX global-routing dependence (track_d DO_NOT_FLASH) — are
  family properties of Cyclone IV, not method properties. On Xilinx, INT PIPs
  are independent bit encodings and `fasm2frames` composes full designs
  routinely (F4PGA built working Zybo Z7 bitstreams from this db). Remaining
  7-series hazards: electrical contention from a bad config + db errors — which
  is what single-driver checking + per-PIP certificates + sacrificial boards
  address.

Two family-specific assumptions that must be **re-verified per new family**
(they are not method invariants): (a) composition composability — decides
free-composition vs ζ-style gold-anchoring; (b) context dependence of bit
semantics (EP4CE6 found per-N canon and per-driver MUX config; the mining key
itself had to evolve to a 5-tuple).

## 3. prjxray zynq7 disk audit (2026-07-11, `/home/test/prjxray-db`)

Verified on disk, not from memory. Headline: **the "partial coverage" label is
misleading for our purposes — the fabric rules are byte-identical to artix7.**

| File | artix7 | zynq7 | md5 |
|---|---|---|---|
| `segbits_int_l.db` (INT PIP rules) | 3636 lines | 3636 lines | identical (`abd25cf6…`) |
| `segbits_int_r.db` | 3636 | 3636 | identical |
| `segbits_clblm_l.db` (CLB) | 703 | 703 | identical (`da401a17…`) |
| `segbits_clbll_l.db` | 680 | 680 | identical |
| `segbits_lioi3.db` (IOB routing) | — | — | identical (`8015ed49…`) |

7-series shares one fabric; prjxray's zynq7 db reuses the artix7 rule files —
so everything evolution touches (INT PIPs, CLB LUT/FF/MUX, IOB) carries the
best-tested rules in the prjxray ecosystem. Zynq7-specific data all present:
`zynq7/xc7z010/{tilegrid,tileconn,node_wires}.json`, and full part data for
**our exact part** `xc7z010clg400-1` (`part.yaml`, `package_pins.csv`,
`required_features.fasm`).

What zynq7 actually lacks vs artix7 (full diff of file lists):
- **GTP transceivers + PCIe** — the 7z010 die has neither. Irrelevant.
- **XADC MONITOR tile jsons** — die has XADC; evolution never touches it.
- **`cells_data/`** — techmap metadata for `fasm2bels` (netlist back-inference
  only). Not needed.
- **`gridinfo/`, `harness/`** — ROI harnesses; we have our own DFX flow.

**No gap intersects with anything evolution needs.** Empirical backing: the
whole xpart/ehw/autoehw LUT-INIT line did dozens of silicon verifications on
this db; F4PGA built working full Zybo Z7 bitstreams (routing composition
validated in practice by third parties).

License: **CC0 1.0** (checked `LICENSE`) — vendoring into a public repo is
unencumbered.

## 4. Decisions recommended (not yet ratified)

1. **Do NOT "complete" prjxray zynq7.** The gaps have no consumer; completion =
   archaeology on archived, 2017.2-pinned fuzzers producing self-made segbits
   with no ground truth. (Same argument that decided the K7 whitelist-first
   strategy; the §3 audit makes it stronger — the fabric rules were never
   incomplete.)
2. **Extract + freeze the usable subset; demote prjxray to a prior.**
   - Dependency risk of an archived repo is *tool* rot, not *data* rot — the
     .db files are static text. Freezing a copy + provenance note fully
     resolves the dependency; re-mining is unnecessary.
   - Extract: `segbits_int_l/r.db`, `segbits_clb*.db`, `ppips_int_*.db`,
     `zynq7/xc7z010/{tilegrid,tileconn}.json`, `xc7z010clg400-1/part.*` — a few
     MB.
   - **Independence comes from validation, not re-derivation**: every bit class
     enters the whitelist only through our own Vivado 2025.2 specimen-diff
     prediction gate (EP4CE6 gate ported: mine → holdout → emit → fresh-gold
     TP=1/FP=0). This simultaneously certifies that the 2017.2-era db holds for
     2025.2 bitstreams (7-series format is frozen; the gate turns "should hold"
     into a certificate). After this, the authority is **our certificates**;
     prjxray is an index. This is precisely the `local_map` schema
     (`docs/schema.md`) instantiated — the foundation of Claim B.
3. **Completion becomes lazy**: if evolution ever needs a bit class not in the
   db, do a targeted one-tile-class mini-fuzz with our own modern-Vivado
   harness. Never resurrect the old fuzzers.

## 5. Fuzzing × evolution = Claim B's mechanism (three levels)

Claim B ("device-local map guides evolution safer than raw mutation") is still
NOT TESTED. The fuzz/evolve fusion is its implementation space:

1. **Offline fuzz feeds evolution** (safest): host-side mining extends the
   whitelist; search space grows from "LUT INIT only" to "LUT + certified
   PIPs". Fuzzing and evolution stay decoupled.
2. **On-board self-cartography** (the `local_map` intent in future_plan): the
   device validates bit semantics itself via ICAP readback + probe circuits;
   evolution constrained to self-certified bits. Per-entry certificates = the
   EP4CE6 gate pattern verbatim.
3. **Evolution *as* fuzzing** (the novel research claim): every GA evaluation
   is a specimen — log (bit-flip → behavior delta) pairs; the local map
   accumulates as a *byproduct* of search and then feeds back into the mutation
   operator. Thompson's 1996 observation made systematic; CoBEA did not do this
   (it used the known iCE40 db). "Device autonomously mines and validates its
   own map" appears to be unclaimed territory.

Safety split: levels 2/3 restricted to **content-bit classes** (LUT INIT, FF
init — worst case is functional garbage, not contention) run on EBAZ = M2.
Routing-class autonomous fuzzing (full levels 2/3) → K7 sacrificial boards.
Host-side routing mining (level 1's db part) can start now, so the whitelist
has inventory when a K7 board arrives.

## 6. Generalization: fuzz-then-evolve on FPGAs with no prior project

Prerequisites (each one absent breaks the method):
1. Scriptable vendor toolchain with placement pinning (LOC-level constraints)
   — needed to isolate single bits by diffing.
2. Plaintext, deterministic, compression-off bitstream with recoverable CRC.
   Mandatory signing/encryption (some newest families) kills the diff method.
3. SRAM configuration. OTP is impossible; flash-configured parts (endurance
   ~1e3) can't afford evolutionary eval counts.
4. An acceptable loss model for the routing phase: sacrificial board +
   current-limited supply, or content-bits-only scope.

Cost curve (and the key insight — **evolution does not need completion**):
- Container format (frames, addressing, CRC): days.
- Content bits (LUT/BRAM INIT): weeks — *and this already suffices to run most
  of an EHW ladder* (zynq-ehw 0→5.5 used LUT INIT only). Self-validating:
  truth-table-diff bits are content bits; wrong writes are logic errors, not
  shorts.
- Routing: months, most pitfalls live here, whitelist + per-PIP gates, never
  full coverage.

Correct shape on an unknown device: **start evolving at the content-bit layer;
routing fuzzing proceeds in parallel** — not serial "map everything first".
Fuzz-first is a *safety layer*, not an optimization: its minimal job is the
3-way classification {certified-safe (evolvable) / known-dangerous
(routing-class, whitelist-gated) / unknown (don't touch)}. Endgame = Claim B's
full form: host fuzzing only bootstraps the minimal safety whitelist; the
platform then extends and certifies its own map during evolution. At that point
"does this FPGA have a prjxray" only changes bootstrap cost (days vs weeks),
not feasibility.

## 7. Proposed M2 first drop (if M2 is chosen)

**Extraction + certification** — pure host-side, zero board risk, directly
produces `local_map` v1:
1. Vendor the frozen prjxray subset into `data/` with provenance + CC0 notice.
2. Port the EP4CE6 prediction gate; certify CLB content-bit classes first (M2
   consumes immediately), INT-PIP classes second (K7 inventory).
3. Wire certificates into the `local_map` schema (`schema_version` per
   `docs/schema.md`).

Open questions for the kickoff: whether ChatGPT authors the gate tooling (per
workflow contract) with Claude auditing + running Vivado, or extraction is
Claude-side since it is infrastructure not RTL; and whether M2's board leg
reuses the M1 DFX shell (likely yes — the island/mailbox pattern is proven).
