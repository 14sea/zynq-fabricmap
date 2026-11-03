# Prior art

Added 2026-11-03 after a full-text literature review (≈75 papers, 8 external code
bases, AMD UG470/UG585/UG480/PG134/DS187/XAPP538/UG908). This file is additive: it does
not change any preregistration, pinned document, ruling or result.

**Bottom line:** knowledge-guided mutation beating standard mutation in circuit
evolution is an established result (in simulation), safe-address filters and
constrained representations for bitstream edits exist, and on-chip ICAP LUT rewriting
is old. What was **not found** in the 2026-11 search is the combination this repo
tests: a map **built by the device itself on silicon**, used to guide intrinsic
evolution on that silicon, compared against a random-safe arm inside the same certified
range at equal budget, under preregistration. "Not found" is provisional — three other
such verdicts were overturned during the same review.

## 1. What the tested claim is

The source preregistration (quoted in `docs/claimb_contracts.md` and
`docs/claimb_findings.md`) words Claim B as guiding evolution "more safely than raw bit
mutation". That comparison was never run: the B2/B3 arms are map-guided versus
**random-safe within the same certified range**. The supported statement is therefore
about **search quality against random-safe** (B3: 8/0/0, p = 0.00390625, one die), not
about safety against raw mutation. The preregistered wording is left as written.

## 2. Closest prior work

| Topic | Prior work | Where it stands relative to this repo |
|---|---|---|
| Guided / semantic / learned mutation beats standard mutation in circuit evolution | Hodaň, Mrázek, Vašíček, SOMO (GECCO 2020; GPEM 22:539–572, 2021); Češka et al., SagTree (Swarm Evol. Comput. 69, 2022); Möller et al. 2020 (RL adaptive mutation); Galeta & Sekanina, CEC 2026 (transformer mutation); Hurta et al. 2026 (ML, symbolic regression) | Same direction of result, **all in CPU simulation**, guidance computed from genotype/semantics. Their baseline (POINT mutation) corresponds to our random-safe arm; they also compare SAM (mutate active genes only). None uses a random-sampling baseline or preregistration |
| Intrinsic (on-hardware) mutation improvements | Yan 2007; Wang, Piao, Lee 2007; He, Li, Shi 2009 (self-adaptive mutation *rate*) | Rate adaptation only, no map |
| Safe-address filter for configuration edits | Fleming & Thomas, "Injecting FPGA configuration faults in parallel" (FPT 2018 per Fibich 2023's citation): a static word-50 filter learned from exhaustive fault injection on 7-series | Fault injection, not evolution; our writes already avoid word 50 structurally (all 292 addresses are in words 51/52) |
| Constrained representation instead of raw bits | Fritzsch, Hoffmann, Bogdan, CEC 2022 (iCE40: routing fixed, every gene a LUT truth table); Levi & Guccione 1999 (XC4000 single-driver local routing); Upegui 2006 (LUT-as-mux, no PIP edits) | Same safety idea; Fritzsch claims the routing problem "can be considered solved" by legal encodings, with no raw baseline |
| Short circuits from partial reconfiguration | Beckhoff, Koch, Torresen, FPL 2010 | Relevant to B4: intermediate states of multi-frame writes must also be legal |
| Configuration-bit maps | prjxray (symbolic, fuzzing); AMD essential bits (XAPP538 v1.0: "an algorithm", not published; ISE BitGen flow; UG908 v2026.1 lists no 7-series/Zynq-7000 essential-bits option); Fibich et al., DATE 2023 (iCE40/Artix-7 single-bit statistics) | Our map is behavioural and device-local; it can be cross-checked against essential bits, not replaced by them |
| On-chip LUT rewriting via ICAP / PCAP readback | Blodget et al. 2003 (XPART/HWICAP); ZyEHW 2013–15; García et al. 2020 (IMPRESS); SEM IP / readback CRC (UG470) | Mechanism inherited |
| Evolving native routing (B4 routing class) | Thompson 1996 (XC6200); Levi & Guccione 1999 (XC4000 local lines); Yao et al., IEICE ELEX 20(13), 2023 (Virtex-5: on-chip MicroBlaze + HWICAP, LUT + routing co-evolution from a restricted PIP database); Bozzoli & Sterpone, AHS 2017 (Z-7010 on-chip router core; results evaluated in XDL/Timing Analyzer, not written back to silicon) | On 7-series, routing **evolution** was not found; routing via a legal-code allowlist is not a new mechanism |

## 3. Open question this review raises for the next Claim B round (owner decision)

The B1–B3 substrate is LUT INIT, whose semantics prjxray decodes completely. A
SOMO-style semantic arm could compute the same guidance without a device map. The
question a reviewer will ask is therefore **what the device-local map adds over semantic
guidance**. Candidate answers (none tested): which bits are actually effective and
certified on this die; device-specific behaviour; regions where semantics cannot be
computed. A three-arm design (random-safe / semantic / map), a budget sweep and a second
die would answer it; on a fully decoded substrate a tie is the most likely outcome and
would itself be a useful negative result.

## 4. Safety facts from vendor documentation relevant to B4

- XADC over-temperature automatic shutdown is **off by default**: it needs
  `BITSTREAM.CONFIG.OVERTEMPPOWERDOWN ENABLE` (UG908 Table 47, default Disable) **and**
  the low four bits of XADC register 53h set to `0011b` (UG480 v1.11). It cannot be
  assumed as a safety net.
- ICAPE2 clock max 100 MHz (DS187 v1.21).
- HWICAP read FIFO depth is selectable, 128 or 256 (PG134); the older note that it is
  "not a parameter on the stock IP" (quoted from `zynq-xpart` in
  `docs/claimb_jtag_gate_review.md`) is wrong.

## 5. References

- Hodaň, Mrázek, Vašíček. GECCO 2020, doi:10.1145/3377930.3390188; GPEM 22:539–572, 2021, doi:10.1007/s10710-021-09416-6.
- Češka, Matyáš, Mrázek et al. SagTree. Swarm and Evolutionary Computation 69:100986, 2022.
- Möller, Bernardino, Gonçalves, Soares. LNCS 2020, doi:10.1007/978-3-030-61380-8_2.
- Galeta, Sekanina. CEC 2026, doi:10.1109/cec69861.2026.11727165.
- Hurta, Drahošová, Mrázek. LNCS 2026, doi:10.1007/978-3-032-36229-2_17.
- Fleming, Thomas. Injecting FPGA configuration faults in parallel. Code: github.com/STFleming/parflip.
- Fritzsch, Hoffmann, Bogdan. Evolving hardware by direct bitstream manipulation of a modern FPGA. CEC 2022.
- Levi, Guccione. GeneticFPGA. EH 1999, doi:10.1109/EH.1999.785430.
- Beckhoff, Koch, Torresen. Short-circuits on FPGAs caused by partial runtime reconfiguration. FPL 2010.
- Fibich et al. Bitstream-level interconnect fault characterization for SRAM-based FPGAs. DATE 2023.
- Yao, Liang, Qian, Zhang, Tian. IEICE Electronics Express 20(13), 2023, doi:10.1587/elex.20.20220518.
- Bozzoli, Sterpone. AHS 2017, doi:10.1109/AHS.2017.8046362.
- Le. Soft error mitigation using prioritized essential bits. Xilinx XAPP538 v1.0, 2012.
- AMD UG470 v1.17, UG480 v1.11, UG908 v2026.1, PG134 v3.0, DS187 v1.21.
