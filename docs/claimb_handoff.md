# Claim B round 1 — handoff: what I must not write myself

`docs/workflow.md` puts the `local_map` schema, the verifiers that judge its output and
the known-answer fixtures on the **author's** side, for the reason that makes this line
work: *a gate written by the party that wrote the thing under test is not a gate.* I have
written the producer half and a schema **proposal**; the items below are requested, not
specified, and the author is free to reject the shape as well as the content.

The producer half is at `origin/main` plus the Claim B commits: `scripts/build_local_map.py`,
`scripts/build_phenotype_manifest.py`, `scripts/icap_sequence.py`, `scripts/gate_candidate.py`,
`scripts/gate_board_identity.py`, `scripts/run_log.py`, and `maps/clb_lut_init_v1.local_map.json`.

Read `docs/claimb_preregistration.md` first — it is a **DRAFT** and §6's budget is
deliberately unfrozen.

---

## 1. `local_map` schema — the authority version

`schemas/local_map.schema.json` is mine and is marked a proposal. What it currently
asserts, so you can disagree with specifics rather than reverse-engineer intent:

- provenance `kind` is a **const** `certificate_inherited`, not an enum. A
  `self_cartography` or `search_byproduct` map is a different claim with different evidence
  behind it, and a round-1 verifier should refuse it outright rather than accept it as a
  MINOR addition. If you think that belongs in the version rather than the field, say so.
- the certificate must be `status: passed` **and** `profile: production` — a conformance
  certificate is a self-test against synthetic fixtures and says nothing about this device.
- the universe is exclusive: 292 addresses, and the class's other 1756 entries are named by
  the frozen DB but were never attested.
- `class_entry_count` sits next to `attested_count` so the gap is visible in the artifact.

## 2. An independent verifier that can FAIL my map

The important word is *independent*: written against `docs/freeze_format.md`, the
certificate schema and the preregistration — **not** against `scripts/build_local_map.py`.
Reading my implementation to make a fixture pass destroys the separation that justifies the
round trip.

It should be able to answer, from the artifacts alone:

- does the map's universe equal what the certificate attests, address for address?
- does every `expected_value` match the certificate's polarity?
- are `by_far` and `by_lut` exactly a re-indexing — no address in an index that is not in
  the universe, and none missing?
- does the map descend from a passing production certificate whose hash it pins?
- does `collateral.frame_ecc` match the certificate's own exclusion rule, rather than a
  constant the producer chose?

## 3. Adversarial fixtures — including one gap round-1 data cannot cover

**The polarity gap, and it is real.** All 292 certified bits have `expected_value = 1`.
There is not one `!`-negated token in the set, so **polarity handling is completely
unexercised by round-1 data**: an operator or gate that inverted negated bits would pass
every test I can write against the real map. A synthetic map with negated entries is the
only way to test that path, and it is the fixture I most want.

Also wanted, each of which must be **rejected**:

- a map whose universe silently includes an unattested class entry;
- a map whose `by_lut` groups two different LUTs' bits into one truth table;
- a map pinning a certificate hash that does not match the file;
- a map derived from a `failed` or `conformance` certificate;
- a candidate whose ECC is *correct* but whose content leaves the whitelist — my own
  `KnownBadCompositionTests` does this, and an independent version would be worth more.

## 4. Review the two gate semantics

Ruled 2026-08-10 and implemented in `scripts/gate_candidate.py`:

| frames | what may differ |
|---|---|
| 12 target | only the 292 whitelisted bits, plus a **correctly recomputed** ECC |
| 3 flush | **nothing** — 101 words verbatim, ECC included |

The question worth an independent eye: is `target_frame_findings` complete? It checks bits
outside the whitelist, the ECC against a recomputation, and word 50 outside the ECC field.
I believe those partition the ways a target frame can differ, and a second opinion on that
belief is worth more than another test I write.

## 5. Facts a reviewer should not have to re-derive

Each was measured here, not assumed, and each cost a wrong first attempt:

- **The flush frame is not FAR+1.** Two of the three target groups end at the last minor of
  their column; `0x00400A24` does not exist. The FAR auto-increment continues into the next
  column — `0x00400A23`→`0x00400A80`, `0x00400C23`→`0x00400C80` — so two flush frames belong
  to *different logic*. Only `0x00400C1D`→`0x00400C1E` stays in column.
- **No LUT is fully writable**: 49/49/49/51/50/44 of 64 INIT bits over 6 LUTs, 92
  uncertified. A fitness that assumes a free 64-bit INIT is misspecified.
- **Consecutive INIT bits alternate frames** (INIT[0]→`…A20`, INIT[1]→`…A21`, INIT[2]→`…A20`).
  That is the structure a map encodes and a blind operator cannot know.
- **The frame-ECC port is validated, not assumed**: 24 bitstreams / 123,456 frames verified,
  plus 16 edit-and-regenerate known answers reproducing Vivado's frame byte for byte.
- **Transfer size** is 3 envelopes × 536 words = 6,432 bytes, or ~11.2 KB if it degrades to
  one envelope per FAR. It is *not* 12 × 101 words.

## 6. What I am NOT asking for

- The carrier design. Evolvable LUTs, scorer and HWICAP/control logic with separated frame
  ownership is mine to build, and it does not exist yet.
- The board-side FAR/FDRI guard firmware. Also mine, and it must refuse **independently** of
  the host gate — the sibling `icaphw.c`'s env-overridable `ICAPHW_FAR_LO`/`HI`/`MAX_FDRI`
  must not be carried across as they are.
- Anything that would freeze §6's budget. That comes from a measured calibration, and
  calibration is a device write which is not authorised.
