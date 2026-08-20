# R1 — REPRODUCED. The A20 location result is two observations.

Run 2 of the location result, executed 2026-08-20 at `bda72a9`, source unmodified, as the one
authorised chain ⓪–⑤ of `docs/claimb_location_reproduction_spec.md`. Every outcome below was
written down before the run; this reading only records which branch was taken.

**Branch: R1.** Fault shape as specified, controls **16/16**, `A20` **== candidate exactly**.

## ⓪ Freeze preflight (host only, no board contact)

```
git status --porcelain -- scripts                              empty
HEAD:scripts                     c0bb137139b937fc94302d6940cada3a9bc58b2c   PASS
HEAD:…erratum006 (canonical run) 98d7721ec8095ea08944f2c50c515d3a003ee879   PASS
0cc5aa4:…/step4_sweep            c721277fd506f7211271d300ddee9772962adbac   PASS
FAR count / ordered FAR sha256   5144 / 2eaa5c2d…06e592                     PASS
instrument_digest recomputed     a20e56aa…5aa95d                            PASS
```

Commands, output and return codes: `freeze_preflight.txt`.

## ① The negative control

```
precheck   5/5      PCFG_DONE=0, FPGA0_CLK_CTRL=0x00400800, plmark undefined
sha gate   OK       carrier.bit 8c3369e8…, mechanical --check, rc 0
FCLK0      50.00 MHz before and after (1600/8/4 — this is the 4203)
loadb      2,083,740 bytes, PCFG_DONE=1, plmark 18cd7bffb555339b
acquisition  NOT_FOUND_COMPLETE — 16/16 controls, A20 == base, 5,144/5,144 read,
             not_attempted 0, all entries ok, plmark stable, 496.8 s (0.0966 s/frame)
             candidate signature ABSENT at all four FARs
```

The pre-registered stop — signature present before any transaction — did not fire. As in run 1,
`verdict.json`'s fixed wording ends "the write did not reach the fabric"; **step ① performs no
write**, so only the first half is claimed.

## ③ The fault, reconstructed from `record.json`, not accepted by exit code

The driver exits 1 because the specified fault is a fail-closed stop. What was checked:

```
steps        [no_op: passed, known_answer: stopped]      exactly two
stop         AxiRefusal — pass 2 of envelope 0, fault_code 8 (readback)
STATUS       0x04040082        FAULT 0x00000008
CTRL writes  32; PASS1|env0/1/2 twice each (both transactions completed pass 1 across all
             three envelopes), PASS2|env0 twice, PASS2|env1 and env2 once each (only the
             no_op finished pass 2); CTRL_ARM / CTRL_MODE_HOLDOUT set in none
identity     boardid 17A6, role verify, FCLK0 50.0 MHz, pss_idcode 0x13722093
same_boot    plmark 18cd7cb81a291de5, passed
console      353 commands, 0 rebooted, prompt returned on every one
PCAP_PR      0x4e00e07f -> 0x4600e07f -> restored 0x4e00e07f, read back
```

Same recorded shape as run 1 and as the two accepted 2026-08-16 records.

## ⑤ Pairing first, verdict second

The old side of every comparison was read from the **pinned `0cc5aa4` blobs**, never from a
mutable path.

```
instrument_digest    equal, and equal to the pinned a20e56aa…5aa95d
parent / mode        board_signature_search.py/2.8.0, signature-search — equal
child                probe_jtag_config_read.py/2.4.0 in both
control FARs + order equal
child Tcl            byte-identical for all 17 FARs both runs read
plmark               18cd7cb81a291de5 vs 18cd7785cbf1b1fd — different boots, each stable
```

Only then the verdict:

```
verdict      WRITE_LANDED_AT_THE_INTENDED_FAR
controls     16 / 16 exact
entries      17 read, all ok; not_attempted 5,127; 1.8 s
A20          == candidate exactly; == base false; non-zero at words 50 and 51 only
```

Re-derived from the frozen authority rather than taken from the verdict, and compared across
runs:

```
A20 frame == candidate                                  yes, all 101 words
A20 frame word-for-word identical to run 1              yes
A20 frame_sha256                                        15cb05e68adbff6c962053bb5220c33d…
                                                        — the value pinned in the spec, and the
                                                        same one analyse_ddr_capture.py derived
                                                        as expected_frame_sha256 by another route
16 controls identical to run 1                          16/16
16 controls == carrier.bit's own base frames            16/16
```

## What is now established, and what is not

* **Two independent observations, one instrument.** In a post-fault state built the specified
  way, the intended frame holds the candidate. Run 1 was not a fluke of one boot or one
  transaction.
* **Still not an independent *method*.** Same host, cable, tool bytes, carrier and board, as
  §2 of the spec said in advance: a systematic instrument error would reproduce faithfully.
  Seeing that needs a different readback path, and remains a separate design.
* **§9 step 6 still does not pass.** The interlock still faults; `restore` and the baseline
  re-run are downstream of it and never execute. This is not a Claim B data point.
* **No mechanism is claimed.** Why the engine's pass-2 readback disagrees while JTAG reproduces
  the addressed frame is the deferred question. No DDR slot-0 read was taken this run — it was
  explicitly outside this authorisation.

## Archive

Step ①'s 15,432 raw files: deterministic archive rebuilt to the same digest, extracted and
sha256-compared member by member (0 missing, 0 differing), `validate_index` re-run in full over
the extracted tree under the layout the child argv records (5,144 accepted), 5,144 Tcl digests
compared, release asset downloaded back and `cmp` byte-identical — **and only then** 15,372
loose files moved out, 62 kept. Step ④'s 53 files are all keepers, so nothing was archived and
`archive_manifest_step4.json` records that rather than leaving it inferred.

## State

Read-only JTAG throughout ① and ④. The board is powered, in the post-fault state ③ built, and
nothing has run since step ④. Nothing further is authorised.
