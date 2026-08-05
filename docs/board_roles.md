# Board roles and the sacrificial policy

Decided 2026-08-02 (user). Recorded here because the routing-class work in this repo
is the only thing in the whole line that can physically damage hardware, and "which
board is it safe to do that on" must be a machine-checkable fact, not a memory.

Source of truth for the boards themselves: `/home/test/test_devices/result.txt`
(acceptance) and `/home/test/test_devices/EBAZ4203_UBOOT_BRINGUP.md` (control plane).
The XC7K70T pair and the 12 V supply are **put away** — the K7 line stays on hold and
its supply is off the desk (the 12 V and the 4203's 5 V share a 5.5×2.1 centre-positive
barrel; swapping them destroys a board, so only one supply is out at a time).

## Roles

| Board | Role | Why this one |
|---|---|---|
| **EBAZ4205** (NAND, `/home/test/xilinx`) | **reference — out of the pool** | Holds the M1 golden environment and the NAND Buildroot/DFX flow. Recovery is JTAG-only, and its BOOT.BIN/FSBL is irreplaceable. Never a sacrifice candidate. |
| **EBAZ4203 `17A6`** | **verification** | The only board with the full manual acceptance *and* the board-verified TF-card U-Boot control plane. FCLK0 is already 50 MHz at POR and `bootdelay=-1` is saved, so it is the lowest-friction board for real results. |
| **EBAZ4203 `08EB`** | **sacrificial** (proposed) | Auto-accepted PASS like its siblings; the choice among `F8B3`/`3671`/`08EB` is arbitrary and must be **physically labelled** once made. |
| **EBAZ4203 `F8B3`, `3671`** | **spares** | Untouched replacements. Provision one as a second verification board only if `17A6` is lost. |

A 4203 is the right sacrifice, not the 4205: the 4203 boots from a TF card, so any
configuration disaster is recovered by writing a fresh card. There is no NAND image to
brick and no JTAG-only recovery path.

## The interlock (turn the convention into a gate)

Board identity is already queryable — the bring-up doc sets `boardid` in the saved
U-Boot environment. Extend it with a role, on every board, at provisioning time:

```
setenv boardid 08EB
setenv role sacrificial      # reference | verify | sacrificial | spare
saveenv
```

Rules for tooling in this repo:

- Any tool that writes a **routing-class** (`int_pip`) bit must read `role` over UART
  first and **refuse to proceed unless `role=sacrificial`**. No flag overrides it.
- **Content-class** writes (`clb_lut_init`, `clb_ff_config`, `clb_lutram`, `clb_mux`)
  require `role ∈ {verify, sacrificial}`.
- A board that does not answer with a role is treated as `reference`, i.e. refused.

This is cheap and it removes the failure mode where the right board is simply not the
one plugged in.

## Escalation ladder — spend the sacrificial board as late as possible

The user's constraint is "sacrifice one only if we truly must". So each step must be
exhausted before the next:

1. **Host-side certification** (where this repo is now). Free, unlimited, no board.
2. **Readback-only on the sacrificial board.** ICAP/`bitread` readback and compare
   against predictions. Reads cannot cause contention.
3. **Certified writes under the composition rules** — one driver per node; for every
   group whose bits the write touches, the resulting pattern must be a listed frozen-DB
   codeword; and the candidate diff must be fully contained in the whitelist. Codeword
   exclusivity is only a DB/group/address consistency diagnostic and cannot reject a
   bitstream when codewords are unique. All-zero is not presumed safe
   (`docs/mux_groups.md` §"Erratum"). Still expected to be non-destructive.
4. **Unconstrained routing mutation.** Only here is the board genuinely at risk, and
   only with a current-limited 5 V supply so a contention short trips the limit
   instead of cooking a die.

Physical mitigation for steps 3–4: current-limited bench supply, and no other barrel
supply on the desk.

## Wedge is not damage

Distinguish these in any incident record, because they have different consequences:

- **Wedge** — DEVCFG stuck after a bad `fpgautil` load (`Timeout waiting for
  PCFG_INIT`), or the FCLK0-gated PL-AXI read that hangs the A9 hard enough that JTAG
  halt times out. Recovery is a power cycle (the 4205's S2 button is unreliable;
  physically unplug). **The board is fine. Do not retire it.**
- **Damage** — a board that fails its acceptance regression after an incident. Only
  then does it leave the pool, and the incident goes in the blacklist with its
  fingerprint (`blacklist` schema, `reason: contention_suspected`).

Before suspecting damage, run the known-answer regression first — that lesson cost a
board swap and a torn-down harness during the 4203 bring-up
(`EBAZ4203_UBOOT_BRINGUP.md` §"Run the known-answer regression before suspecting
hardware").
