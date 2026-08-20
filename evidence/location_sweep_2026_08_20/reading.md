# Location sweep, step ①: the negative control passes, and R4 holds at 5,144 frames

The fresh-load negative control the location sweep requires before a fault state may be built.
Executed 2026-08-20 at `010d496` with the source unmodified, under the authorisation that
covers **step ① alone**. Steps ②–⑤ were not started.

## What ran, in the run book's order

```
precheck_fresh_power.py/1.0.1      devcfg CTRL     0x4e00e07f            OK
                                   devcfg INT_STS  0xa802000b  PCFG_DONE=0  OK
                                   devcfg STATUS   0x40000a30            OK
                                   FPGA0_CLK_CTRL  0x00400800            OK
                                   plmark          not defined           OK
sha256sum --check                  carrier.bit: OK                       exit 0
board_set_fclk50.py                before 0x00400800 -> 1600.0/8/4 = 50.00 MHz
                                   after  0x00400800 -> 1600.0/8/4 = 50.00 MHz   PASS
board_uboot_fpga_load.py           carrier_top, 7z010clg400, 2026/08/13 16:01:42,
                                   2,083,740 bytes, PCFG_DONE=1 after the load   exit 0
                                   plmark 18cd75d67713f2f0
board_signature_search.py/2.8.0    child probe_jtag_config_read.py/2.4.0 (R4)
                                   digest a20e56aae879812d…855aa95d
```

`before` and `after` are the same word because this is the **EBAZ4203 `17A6`**, whose SPL
already leaves FCLK0 at 50 MHz; it is the 4205 that reverts to 125 on every reset. The script
decodes the PLLs rather than comparing a constant, which is why it is safe to run on either.

## The result

**`NOT_FOUND_COMPLETE`, with all sixteen controls passing in the same acquisition** — which is
what makes the verdict mean something here, and is exactly what Phase 2's identical string
could not claim.

| | |
|---|---|
| positive controls | **16 / 16 exact.** `expected_sha256 == observed_sha256` for every one, and the non-zero word counts agree frame for frame: 48/48, 66/66, 71/71, 46/46, 84/84, 14/14, 2/2, 82/82, 57/57, 3/3, 13/13, 55/55, 30/30, 14/14, 2/2, 3/3 |
| intended FAR `0x00400A20` | holds the **base** — whole-frame equal to the carrier's own frame |
| sweep | **5,144 of 5,144 read, `frames_not_searched` empty, `not_attempted` empty**, all 5,144 index entries `ok` |
| candidate signature | **absent at all four** of `0x00400A20`–`0x00400A23` |
| `plmark` | `18cd75d67713f2f0` at start **and** at end |
| wall clock | **517.7 s = 8 min 38 s**, 0.1007 s per frame |

**The pre-registered stop did not fire**: the candidate signature had to be absent before any
transaction, or the whole procedure would have been over. It is absent.

### The verdict string says more than this step can support

`verdict.json`'s `reading` field is the tool's fixed wording for `NOT_FOUND_COMPLETE`: *"No
candidate frame appears anywhere in the 5144 frames of the device sequence. The write did not
reach the fabric as a whole frame anywhere."* Only the **first** sentence is claimed here.
**Step ① performs no write at all** — no ICAP transaction of any kind runs in this boot — so
the second sentence is not false so much as inapplicable: there is no write for it to be about.
What this acquisition establishes is exactly *"the candidate signature is absent before any
transaction"*, which is what a negative control is for.

`verdict.json`, the acquisition's stdout and the production tool are **left exactly as
generated**. Correcting an automatic string in a record would change the artefact the ①/④
pairing is built on, and the tool's own bytes are part of `instrument_digest`. The correction
belongs here, additively — the same rule that governs Phase 2's `verdict.json`.

## The one thing not to over-read

`0x00400A20`'s frame **in the base carrier is all zero**, so "A20 holds the base" is here a
zero-floor equality, not a discriminating one — the same weakness that made Phase 2's 771
zero-zero matches worthless on their own. What carries the information is the sixteen controls,
every one of which is a known **non-zero** frame reproduced bit-exactly, in this acquisition,
by this instrument.

## R4 at scale — the number this step was really for

R4 had never read more than 32 frames. It has now read **5,144 in one acquisition with 0
missing and 0 non-`READ` captures**, so the recovery does not degrade across the device.

The request document projected ≈11 min from the 16-frame acquisitions' 0.125 s/frame. The
measured cost is **0.1007 s/frame**, so the projection was slightly conservative and the true
figure for step ④'s budget is **≈8.6 min**. (An extrapolation made 60 s into the run suggested
~0.4 s/frame and ~30 min; that was wrong — it counted the tool's one-time authority derivation
and bitstream parse as if they were per-frame cost.)

## What this does **not** establish

* **Nothing about a post-fault state.** R4's 5,144-frame result here is on a freshly loaded,
  never-transacted device. Step ④ remains the first full-device acquisition in the specified
  post-fault state, and "controls 16/16 here but degrading there" is still a live outcome.
* **No board identity gate ran in this step.** `gate_board_identity.py` (`boardid 17A6`,
  `role verify`, `FCLK0 50.0`) is on the transaction path, which step ① never enters. The five
  precheck registers are consistent with that board, and step ③'s driver does gate it, but this
  acquisition asserts the board's identity nowhere.
* It says nothing about Claim B, which still has zero data points.

## The archive, verified in the ruled order

```
archive        location_sweep_step1_2026_08_20.tar.zst
               sha256 5f5c57117c23549c121e95ae515baccbf4bf4402ea97b8b82cb377e7dae3f1ab
               1,168,618 bytes, 15,432 files, tar posix/sorted/mtime 0/uid-gid 0 + zstd -19
determinism    rebuilt from the same inputs -> identical sha256
extraction     15,432 extracted, every member sha256-compared against the tree: 0 missing, 0 differing
validate_index re-extracted under the relative layout the child argv records, then re-run in
               full: 5,144 accepted, instrument digest recomputed and equal
tcl digests    5,144 compared against the extracted scripts, 0 mismatched
off-box        uploaded as release asset location-sweep-step1-2026-08-20, downloaded back,
               `cmp` byte-identical
move           only then: 15,372 loose files moved to
               /home/test/fabricmap_archives/location_sweep_step1_loose_2026_08_20/
kept in repo   62 files -- index, verdict, the four candidate FARs and the sixteen controls,
               each as capture + child log + Tcl
```

Details and the manifest's own digests: `archive_manifest.json` beside this file.

## A recorded exception: `git diff --check` is not clean on this commit

It reports **28 trailing-whitespace warnings**, every one of them inside the two board console
records (`carrier_load.log` and the precheck's `.txt` sidecar) — U-Boot's `Zynq> ` prompts and
the CR bytes of its own output. **They are kept.** These files exist to be the bytes the board
actually sent; stripping them to make a linter green, or hiding them behind a `.gitattributes`
rule, would edit evidence to satisfy a tool. The warning is expected on any commit that carries
raw console capture, and is recorded here rather than silenced.

## State

Step ② has **not** been started and is not authorised. The board is powered, holding the
freshly loaded carrier, with no transaction of any kind run in this boot — the acquisition was
read-only JTAG throughout. Nothing was retried, nothing resumed, nothing repaired.
