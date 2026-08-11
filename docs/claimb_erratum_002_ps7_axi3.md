# Architecture erratum 002 — the carrier's PS7 interface is not an AXI4-Lite port

**Status: OPEN. It blocks every device write, including erratum 001 step 1.**
Discovered 2026-08-11 on board `17A6`, at the first read the transport ever issued.

## What happened

The no-op calibration got as far as its very first device access and stopped:

```
STOP: no prompt within 8.0s of `md.l 0x43c02004 0x1` — the engine has not answered.
```

Everything before it had passed, and the record says so:
`evidence/calibration_noop_2026_08_11/record.json` has FCLK0 verified at
`0x00400800 -> 1600.0/8/4 = 50.00 MHz`, `fpga loadb` reporting
`design filename = "carrier_top" … part number = "7z010clg400" … bytes in bitstream =
2083740`, and the identity gate accepting `boardid=17A6 role=verify
idcode=0x13722093 fclk0=50.0 MHz` **over the same console, immediately before**. Then one
read of `STATUS` and the console went silent. `Ctrl-C` returned nothing, which is the
difference between a spinning shell loop and a stalled CPU: the A9 was waiting on an AXI
read that will never complete. The board needed a power cycle.

**No candidate write and no ICAP frame write happened.** Say it that way and not
"nothing reached the fabric": `fpga loadb` had just configured the whole array — that
configuration *is* the carrier — so the fabric was very much written, through PCAP, by the
intended and reversible path. What did not happen is anything this line's write path does:
the first STATUS read is step 0 of a transaction, before the payload is staged, before
`begin_txn`, and 15 frames before ICAP is given a single word.

## The cause

`vivado/carrier/carrier_top.v` wires the PS7 primitive's `M_AXI_GP0` to `carrier_axil` with
19 ports:

```
ACLK ARESETN | AWADDR AWVALID AWREADY | WDATA WSTRB WVALID WREADY | BRESP BVALID BREADY
             | ARADDR ARVALID ARREADY | RDATA RRESP RVALID RREADY
```

That is the AXI4-**Lite** signal set. `M_AXI_GP0` is an **AXI3** master, and the ports that
are missing are not optional:

| port | direction | left unconnected means |
|---|---|---|
| `MAXIGP0RLAST` | **input to PS7** | tied 0 — **the master's read never terminates** |
| `MAXIGP0RID`, `MAXIGP0BID` | input to PS7 | tied 0 — response IDs never echo the request |
| `MAXIGP0ARLEN`, `MAXIGP0AWLEN` | output from PS7 | the slave cannot see a burst length |
| `MAXIGP0WLAST` | output from PS7 | the slave cannot see where a write burst ends |

`RLAST` is the one that was observed. The slave raises `RVALID`, the beat transfers with
`RREADY` high, `RLAST` is 0, so the master concludes the burst is unfinished and waits for
beats that will never come. The read hangs, and with it the CPU. A *write* would have
completed — `BVALID` is generated and `BID` 0 is what the PS issued — which is why this
could not be caught by trying a poke first.

## Why no test could have caught it

`vivado/carrier/tb_carrier_axil.v` drives the slave as an AXI4-Lite port, because that is
what the slave is. A bench written to the same signal set as the design has no `RLAST` to
get wrong. This is the same shape as the readback note already in `carrier_stream.v` — *the
bench's device is a model of the assumption* — and the same shape as the pacing defect found
the same day: **a bench that models the assumption cannot test the assumption.**

The host side could not have caught it either. Synthesis ties an unconnected primitive input
low without failing; place, route, timing and `write_bitstream` all pass; the isolation
checks, the INIT ECO differential and both production gates are about frame content and are
completely indifferent to whether the port protocol closes.

## What it costs, and what it does not

**Does not**: the map, the target sites, the 292 certified addresses, the frozen
reachability spec, the ECC port, the host gate, the guard, the run bundle format, the
identity interlock and the transport are all untouched. The transport's own conclusions
(the 20.97 ms watchdog budget, the one-line envelope, the inline hush interlock) stand —
they were measured against the console, not against the PL.

**Does**: `carrier_top.v` has to gain an AXI3→AXI4-Lite shim and the carrier has to be
**rebuilt**, which is Vivado work and is not authorised. A rebuild re-stamps
`write_bitstream`'s timestamp, so it invalidates by design:

* `carrier.bit`, `carrier_eco.bit`, `post_route.dcp` and their LFS pins,
* `phenotype_manifest.json` and therefore `PRODUCTION_MANIFEST_SHA256`, pinned in
  `scripts/board_carrier_exec.py`,
* `carrier_run.json`, the isolation record and the ECO differential,
* both production gates' verdicts, and the acceptance ladder from step 4 on.

The floorplan has **792 of 800 LUTs**, so the shim's cost is not a footnote. It should be
small — `RLAST` is one wire, the two ID echoes are registers of the ID width — but burst
support is not free and the design must either implement it or be able to prove the master
never bursts.

## The burst question is now decisive, not theoretical

`scripts/board_uboot_axi.py` uses `cp.l` for the bulk write because nothing else in U-Boot
is fast enough for the watchdog. `cp` is `memmove()` → ARM's assembly `memcpy` → LDM/STM
blocks. The argument that this is safe was that U-Boot maps non-DRAM as Strongly-ordered,
where accesses may not be merged, plus zynq-autoehw's board-verified precedent. That
argument is still probably right, but "probably" is exactly what just failed on the read
path, and with `ARLEN`/`AWLEN` unconnected a burst would be silently truncated instead of
refused. **The shim should decode `AWLEN`/`ARLEN` and drive `WLAST`/`RLAST` properly**, so
that a burst either works or is visibly rejected, rather than resting on a memory-attribute
argument about a copy routine.

## What must not happen

* do not re-choose the target sites, which would invalidate the frozen `local_map`
  addresses;
* do not work around this by writing only and never reading — the readback IS the evidence
  (§3b link 3), and a write-only path would be a scoring run with no verification;
* do not treat the wedge as a board fault. `docs/board_roles.md`: a wedge is a power cycle,
  not a retirement. `17A6` answered its identity gate correctly on the same console
  seconds earlier.
