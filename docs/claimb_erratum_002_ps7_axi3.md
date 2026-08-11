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

## The fit question — measured 2026-08-11, and it needs an architecture ruling

The shim is built, benched and minimised, and **it does not fit the frozen 800-site
region**. The numbers, all measured:

| | LUTs |
|---|---|
| carrier without the shim, post-synthesis | 780 |
| carrier without the shim, post-route (the published build) | 732 |
| the shim alone, out-of-context | **64** (49 FFs) |
| carrier with the shim, post-synthesis | 843 |
| carrier with the shim, **post-`opt_design`** | **837** |
| `pb_logic` = `SLICE_X0Y0:SLICE_X1Y99` | **800 sites** |

`place_design` fails outright — first on four `scorer` instances, then, after the shim
lost 32 LUTs of RDATA mux, on `stream/watchdog` and `stream/icap_din`. It is not close:
37 LUTs over before placement begins.

**The shim cannot absorb that.** Its 64 LUTs are the ID echo, the address incrementer, the
beat counter and the FSM — every one of them named in the acceptance line. Two rounds of
reduction (a shared `id` split into two registers; the read data path turned into a
pass-through) bought 6 LUTs, because Vivado had already done the rest. Getting to ~25 would
mean giving up burst conversion or ID echo, which is the same defect erratum 002 is about,
re-entered by the front door.

### The measurement that answers it

A scratch feasibility probe — **not a build, nothing published, the pblock in
`build_carrier.tcl` is unchanged** — placed and routed the same netlist with the nearest
*free* slice column pair added:

```
pb_logic = SLICE_X0Y0:SLICE_X1Y99  +  SLICE_X6Y0:SLICE_X7Y99
  -> place + route OK
  -> WNS +7.305 ns   (the published build is +5.598)
  -> CELL ISOLATION OK: target=6  flush=0
  -> post-route 794 LUTs
  -> route inventory: flush 415, target 560, foreign 554
     (the published build records flush 159, target 374, foreign 368)
```

`SLICE_X6`/`X7` sit in majors 22–23, between the flush column (major 21) and the second
target column (major 24), and are in **no written frame** — which is not an argument but a
machine-checked result: the isolation check's two verdict criteria, target cells 6 and
flush cells 0, both hold.

### Why this is a ruling and not a decision to take quietly

The region is `SLICE_X0Y0:SLICE_X1Y99` because the ORIGINAL authority was minimising nets
that cross the written columns — the right-hand floorplan was rejected at 124 crossers and
a left-hand one with a BRAM buffer at 190. **Erratum 001 retired that authority**: crossing
nets are an evidence record, cell ownership is the verdict, and bit invariance against the
routed base is what makes a candidate legal. Under erratum 001 the two-column region is
therefore tighter than anything now requires — the crossing count rising from 368 to 554
foreign nets is a bigger number in a record, not a violated rule, because those routes are
part of the base and every candidate rewrites them identically.

That said, it is a floorplan change to a frozen artifact, and the standing instruction is
not to widen the region without a ruling. Three options, with what each costs:

1. **add `SLICE_X6Y0:SLICE_X7Y99`** — measured above: fits, timing improves, verdicts hold.
   Cheapest and the most direct consequence of erratum 001.
2. **shrink `carrier_stream`** (609 of the 843 LUTs, 497 of them logic). It is the verified
   engine, its CRC commitment and byte-count assertion are load-bearing, and the science
   depends on it. Not advisable to touch for 40 LUTs.
3. **weaken the shim** — refuse bursts instead of converting them. It would fit, and it
   contradicts the acceptance line.

## The shim did not change the symptom — 2026-08-11, second attempt

The rebuilt carrier was loaded and the calibration stopped at **exactly the same place**:

```
STOP: no prompt within 8.0s of `md.l 0x43c02004 0x1`
```

`evidence/calibration_noop_2026_08_11_erratum002/record.json`: FCLK0 verified 50.00 MHz,
`fpga loadb` reported the NEW bitstream (`SW_CRC=cf3db964`, `time = 19:26:04`, against the
old `c8a91664` / `14:38:57`), the identity gate accepted `17A6 role=verify` over the same
console seconds before, and then the first read stalled the CPU. `Ctrl-C` returned nothing
again.

**That identity of symptom is evidence, and it points away from the protocol.** The shim
completes every transaction the bench can construct — single beat, 16-beat burst, both
directions, backpressure, FIXED, early and late WLAST, mismatched WID, unsupported size and
burst — and 17 of 17 mutations of it are caught, including "RLAST never", which is the
erratum-002 defect itself. A design that answers every one of those in simulation and then
hangs identically to the design that had no RLAST at all is not failing at the protocol
layer. **The leading hypothesis is now that the slave never runs at all**: no `FCLK0` at the
PL, or `FCLKRESETN[0]` held asserted, so `carrier_axil`'s `s_rvalid` can never rise and the
master waits forever exactly as it did before.

`carrier_top` takes `clk` from `fclkclk[0]` and `rst_n` from `fclkresetn[0]`, and `MAXIGP0ACLK`
from the same `clk`. If FCLK0 is not toggling, every one of those is dead together and no
amount of correct AXI3 logic can answer a read.

Two things already checked and NOT the cause:

* the level shifters and the PL reset — U-Boot's `zynq_slcr_devcfg_enable()` writes
  `LVL_SHFTR_EN = 0xF` and `FPGA_RST_CTRL = 0` for any full bitstream, which is exactly what
  the vendor's `ps7_post_config` does. The `INFO:post config was not run` line U-Boot prints
  after `fpga loadb` refers to that same pair, so it is informational here, not a gap.
* the constraint: `carrier.xdc` does `create_clock -period 20.000 -name fclk0
  [get_pins ps7/FCLKCLK[0]]`, and the build reports WNS +6.716 ns against it.

### The diagnostic the next power-on must run, before touching any AXI address

A read of the carrier's window is what wedges the CPU, so every one of these is a **PS**
register and none of them can hang:

| address | register | what would explain the hang |
|---|---|---|
| `0xF8000170` | `FPGA0_CLK_CTRL` | divisors — already known good (`0x00400800`) |
| `0xF8000178` | `FPGA0_THR_CNT` | **bit 0 is the FCLK0 gate** Linux's `clkc` driver uses (`fclk_ctrl_reg + 8`, `CLK_GATE_SET_TO_DISABLE`): 1 means FCLK0 is OFF |
| `0xF8000240` | `FPGA_RST_CTRL` | non-zero means `FCLKRESETN[0]` is held and the whole design is in reset |
| `0xF8000900` | `LVL_SHFTR_EN` | not `0xF` means the PS-PL boundary is not open |
| `0xF8007000` | devcfg `CTRL` | `PCAP_PR`, and whether the PL is under PCAP or ICAP |
| `0xF800700C` | devcfg `INT_STS` | bit 2 `PCFG_DONE` — did configuration actually complete |
| `0xF8007014` | devcfg `STATUS` | corroborates the above |

Read them **before** `fpga loadb` and again after, so the delta is visible.

The right instrument for the AXI side is JTAG, not the console: with the 4203's FT4232 pod
attached, `mem_ap` reads the PL window through the DAP and returns a WAIT timeout instead of
stalling the CPU —

```
openocd -f <4203 cfg> -c "target create zynq.ahb mem_ap -dap zynq.dap -ap-num 0" \
        -c init -c "zynq.ahb mdw 0x43c02004 1" -c shutdown
```

That turns "one hypothesis per power cycle" into an experiment that can be repeated.
